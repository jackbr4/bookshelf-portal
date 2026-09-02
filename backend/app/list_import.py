"""
List import: turn an article URL (or pasted text) into {title, author}
book candidates using trafilatura for boilerplate removal and a single
Claude call with a JSON-schema-constrained output.

No searching happens here — the candidates feed the review UI, which then
kicks off a resolve job.
"""
import json
import logging
import re
from typing import Optional

import httpx
import trafilatura
from pydantic import BaseModel, ValidationError

from .models import BookCandidate

logger = logging.getLogger(__name__)

# Browser-ish UA: many publishers 403 obvious bots but are fine with this.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Keep the LLM input bounded even for very long articles. Book lists are
# rarely this long; the cap mostly protects against pasting a whole book.
_MAX_TEXT_CHARS = 60_000

_SYSTEM_PROMPT = """You extract book recommendations from articles.

Given the text of an article or web page, list the books it actually recommends, reviews, or presents as part of its list. Rules:
- Include only books that are the subject of the article (a "best of" list, a reading list, a roundup, an author's recommendations, etc.).
- Exclude books mentioned only in passing, in ads, in "related articles", in sidebars, in comments, or as comparison points ("if you liked X").
- Exclude the article author's own promotional plugs unless the article is explicitly about that book.
- Give the title as it would appear on the cover; drop subtitles only when they are clearly editorial. Do not add series names unless they are part of the title.
- Author is the writer's name as commonly published. If the author is not stated and you are not certain, leave author empty rather than guessing.
- confidence is "high" when both title and author are clearly stated for that book, "low" when you inferred either one or the mention is ambiguous.
- Preserve the order the books appear in the article. Do not deduplicate across editions; do deduplicate exact repeats.
- If the page contains no book list, return an empty books array.
"""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "books": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "low"]},
                },
                "required": ["title", "author", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["books"],
    "additionalProperties": False,
}

MOCK_BOOKS = [
    BookCandidate(title="The Left Hand of Darkness", author="Ursula K. Le Guin", confidence="high"),
    BookCandidate(title="Piranesi", author="Susanna Clarke", confidence="high"),
    BookCandidate(title="The Overstory", author="Richard Powers", confidence="high"),
    BookCandidate(title="Stoner", author="", confidence="low"),
    BookCandidate(title="A Visit from the Goon Squad", author="Jennifer Egan", confidence="low"),
    BookCandidate(title="Trust", author="Hernan Diaz", confidence="high"),
]


class ExtractionError(Exception):
    """
    User-facing extraction failure. `code` is stable for the frontend:
      fetch_failed     - couldn't fetch the URL (network, 4xx/5xx, wrong type, too big)
      no_content       - fetched but no article text found (JS-rendered, paywall)
      not_configured   - no API key
      llm_failed       - the model call failed or returned unusable output
    Every fetch/no_content error should push the user to the paste-text tab.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class _ExtractedBooks(BaseModel):
    books: list[BookCandidate]


class ListExtractor:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_books: int,
        fetch_timeout: float,
        fetch_max_bytes: int,
        mock_mode: bool = False,
    ):
        self._api_key = api_key
        self._model = model
        self._max_books = max_books
        self._fetch_timeout = fetch_timeout
        self._fetch_max_bytes = fetch_max_bytes
        self._mock_mode = mock_mode
        self._anthropic = None  # created lazily so import/startup never needs a key

    # -----------------------------------------------------------------------
    # Public entry points
    # -----------------------------------------------------------------------

    async def extract_from_url(self, url: str) -> tuple[list[BookCandidate], Optional[str]]:
        """Returns (books, page_title)."""
        if self._mock_mode:
            return list(MOCK_BOOKS), "Mock: 6 novels worth your time"
        html = await self._fetch(url)
        text, title = self._clean(html, url)
        return await self._extract(text), title

    async def extract_from_text(self, text: str) -> list[BookCandidate]:
        if self._mock_mode:
            return list(MOCK_BOOKS)
        text = text.strip()
        if not text:
            raise ExtractionError("no_content", "No text to extract from")
        return await self._extract(text)

    # -----------------------------------------------------------------------
    # Steps
    # -----------------------------------------------------------------------

    async def _fetch(self, url: str) -> str:
        if not re.match(r"^https?://", url, re.I):
            raise ExtractionError("fetch_failed", "URL must start with http:// or https://")
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._fetch_timeout,
                headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5"},
            ) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise ExtractionError(
                            "fetch_failed", f"The page returned HTTP {resp.status_code}"
                        )
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype and not (ctype.startswith("text/") or ctype in ("application/xhtml+xml", "application/xml")):
                        raise ExtractionError(
                            "fetch_failed", f"The URL is not a web page (content-type {ctype})"
                        )
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > self._fetch_max_bytes:
                        raise ExtractionError("fetch_failed", "The page is too large to import")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > self._fetch_max_bytes:
                            raise ExtractionError("fetch_failed", "The page is too large to import")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    encoding = resp.charset_encoding or "utf-8"
                    try:
                        return body.decode(encoding, errors="replace")
                    except LookupError:
                        return body.decode("utf-8", errors="replace")
        except ExtractionError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("[list-import] fetch failed for %s: %s", url, exc)
            raise ExtractionError("fetch_failed", "Couldn't reach that page")

    def _clean(self, html: str, url: str) -> tuple[str, Optional[str]]:
        """Strip boilerplate; returns (article_text, page_title)."""
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if not text or len(text.strip()) < 80:
            raise ExtractionError(
                "no_content",
                "Couldn't find any article text on that page (it may need JavaScript or a login)",
            )
        title = None
        try:
            meta = trafilatura.extract_metadata(html, default_url=url)
            if meta and meta.title:
                title = meta.title.strip() or None
        except Exception:  # metadata is nice-to-have only
            pass
        return text, title

    async def _extract(self, text: str) -> list[BookCandidate]:
        if not self._api_key:
            raise ExtractionError("not_configured", "List import is not configured (no API key)")
        if len(text) > _MAX_TEXT_CHARS:
            text = text[:_MAX_TEXT_CHARS]

        import anthropic  # deferred so the app imports without the SDK in odd envs

        if self._anthropic is None:
            self._anthropic = anthropic.AsyncAnthropic(api_key=self._api_key, max_retries=2)

        user_msg = (
            f"Extract up to {self._max_books} books from this article. "
            f"If there are more than {self._max_books}, keep the first {self._max_books} in article order.\n\n"
            f"<article>\n{text}\n</article>"
        )
        try:
            response = await self._anthropic.messages.create(
                model=self._model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
            )
        except anthropic.AuthenticationError:
            logger.error("[list-import] Anthropic rejected the API key")
            raise ExtractionError("not_configured", "List import API key was rejected")
        except anthropic.APIError as exc:
            logger.error("[list-import] Anthropic call failed: %s", exc)
            raise ExtractionError("llm_failed", "The extraction service is unavailable — try again shortly")

        if response.stop_reason == "refusal":
            raise ExtractionError("llm_failed", "The extraction service declined to process this text")

        raw = next((b.text for b in response.content if b.type == "text"), "")
        try:
            parsed = _ExtractedBooks.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error("[list-import] unusable model output: %s / %r", exc, raw[:200])
            raise ExtractionError("llm_failed", "Couldn't read the extraction result — try again")

        logger.info(
            "[list-import] extracted %d books (model=%s, in=%s out=%s)",
            len(parsed.books), self._model,
            response.usage.input_tokens, response.usage.output_tokens,
        )
        return _tidy(parsed.books)[: self._max_books]


def _tidy(books: list[BookCandidate]) -> list[BookCandidate]:
    """Trim whitespace, drop empties and exact repeats (case-insensitive)."""
    out: list[BookCandidate] = []
    seen: set[tuple[str, str]] = set()
    for b in books:
        title = " ".join(b.title.split())
        author = " ".join(b.author.split())
        if not title:
            continue
        key = (title.lower(), author.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(BookCandidate(title=title, author=author, confidence=b.confidence))
    return out
