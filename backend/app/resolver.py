"""
Book resolution: library presence checks + Prowlarr release search.

Shared by GET /portal/releases (interactive single-book lookup) and the list
import resolve job, which runs the same resolution once per candidate book.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from .calibre_library import CalibreLibrary
from .history import HistoryDB
from .models import HistoryMatch, ReleaseItem, ReleasesResponse
from .prowlarr_client import ProwlarrClient

logger = logging.getLogger(__name__)

# Fuzzy fallback for the presence checks. Exact normalised-variant matching
# runs first; these thresholds only catch metadata drift ("Dune: Messiah" vs
# "Dune Messiah", a stray subtitle, a typo). A false "in library" is cheap
# here — the releases stay one click away — so lean towards recall.
FUZZY_TITLE_THRESHOLD = 90
# Without an author to corroborate, short titles collide easily ("Circe" vs
# "Circle" scores 91), so demand a near-exact title.
FUZZY_TITLE_THRESHOLD_NO_AUTHOR = 96
FUZZY_AUTHOR_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Title / author normalisation
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _title_variants(title: str) -> set[str]:
    variants = {_norm(title)}
    no_parens = re.sub(r"\s*\([^)]*\)", "", title).strip()
    variants.add(_norm(no_parens))
    variants.add(_norm(no_parens.split(":")[0].strip()))
    variants.add(_norm(title.split(":")[0].strip()))
    # Strip leading articles so "Deer Park" matches "The Deer Park" and vice versa
    for v in list(variants):
        stripped = re.sub(r"^(?:the|a|an) ", "", v).strip()
        if stripped:
            variants.add(stripped)
    variants.discard("")
    return variants


def _author_matches(wanted: str, candidate: str) -> bool:
    """Empty `wanted` matches anything; otherwise word-set equality or a fuzzy ratio."""
    w = _norm(wanted)
    if not w:
        return True
    c = _norm(candidate)
    if set(w.split()) == set(c.split()):
        return True
    return fuzz.token_sort_ratio(w, c) >= FUZZY_AUTHOR_THRESHOLD


def _authors_subset(author: str, library: list[dict]) -> list[dict]:
    """Library entries whose author matches the query author (all of them if
    the query has no author -- same permissive default as _author_matches)."""
    return [b for b in library if _author_matches(author, b["author"])]


# Words in a scene-release title that don't indicate a different book:
# language/format tags and the connective "by". (Author words are removed
# separately, per-candidate, since they vary per book.)
_RELEASE_NOISE_WORDS = {
    "by", "a", "an", "the",
    "eng", "english", "epub", "mobi", "azw3", "pdf",
    "mp3", "m4a", "m4b", "aac", "unabridged", "audiobook",
}

# How many release-title words may remain unexplained (after removing the
# matched title, the candidate's author, and known noise) before we decide
# this is probably a *different* book that merely contains the candidate's
# title as a substring ("Careful Little Eyes" contains "Little Eyes").
_MAX_UNEXPLAINED_WORDS = 1

_BRACKETED = re.compile(r"\[[^\]]*\]|\([^)]*\)")


def _strip_bracketed(s: str) -> str:
    """
    Remove [...] and (...) segments. Scene-release titles routinely carry
    series/volume and format/edition info this way -- e.g. "[Chronicles of
    Dune 05]", "(epub)", "(retail)" -- which is real metadata but isn't part
    of the book's title, and shouldn't count as "unaccounted-for" words
    against a genuine match.
    """
    return _BRACKETED.sub(" ", s)


def _all_authors_by_id(library: list[dict]) -> dict[int, set[str]]:
    """
    Book id -> the union of normalised author-name words across every
    co-author row for that book. Calibre's schema has one row per (book,
    author) pair, so a co-authored book appears once per author -- a release
    crediting *all* co-authors would otherwise leave whichever ones aren't on
    the matched row "unexplained" and wrongly fail the check below.
    """
    result: dict[int, set[str]] = {}
    for book in library:
        result.setdefault(book["id"], set()).update(_norm(book["author"]).split())
    return result


def _find_calibre_match_for_release(
    release_title: str, candidates: list[dict], all_authors_by_id: dict[int, set[str]]
) -> Optional[dict]:
    """
    Does this release's raw (scene-formatted) title look like one of the
    given Calibre books? `candidates` should already be filtered to plausible
    matches for the search query -- this does the release-specific check.

    A whole-word substring match alone isn't enough: "Little Eyes" is a
    genuine substring of "Careful Little Eyes", a different book. So beyond
    the substring match, this also requires that removing the matched title,
    *all* the book's co-authors, and known format/language noise -- after
    first stripping bracketed/parenthetical scene-release metadata -- leaves
    almost nothing unexplained -- i.e. the release title isn't hiding extra,
    unaccounted-for *title* words that would mean it's really a different book.
    """
    norm_release = _norm(_strip_bracketed(release_title))
    if not norm_release:
        return None
    release_words = set(norm_release.split())
    for book in candidates:
        author_words = all_authors_by_id.get(book["id"], set())
        for variant in _title_variants(book["title"]):
            if not variant or not re.search(rf"\b{re.escape(variant)}\b", norm_release):
                continue
            unexplained = release_words - set(variant.split()) - author_words - _RELEASE_NOISE_WORDS
            if len(unexplained) <= _MAX_UNEXPLAINED_WORDS:
                return book
    return None


def _book_matches(title: str, author: str, cand_title: str, cand_author: str) -> bool:
    """
    Does (cand_title, cand_author) look like the same book as (title, author)?
    Exact normalised-variant overlap first, then a fuzzy title ratio.
    """
    if not _author_matches(author, cand_author):
        return False
    wanted = _title_variants(title)
    if _title_variants(cand_title) & wanted:
        return True
    best = max((fuzz.ratio(v, _norm(cand_title)) for v in wanted), default=0)
    threshold = FUZZY_TITLE_THRESHOLD if _norm(author) else FUZZY_TITLE_THRESHOLD_NO_AUTHOR
    return best >= threshold


class BookResolver:
    def __init__(
        self,
        prowlarr: ProwlarrClient,
        calibre_library: CalibreLibrary,
        audiobooks_dir: str,
        history_db: Optional[HistoryDB] = None,
        calibre_web_url: str = "",
    ):
        self.prowlarr = prowlarr
        self.calibre_library = calibre_library
        self.audiobooks_dir = audiobooks_dir
        self.history_db = history_db
        self.calibre_web_url = calibre_web_url.rstrip("/")

    # -----------------------------------------------------------------------
    # Library presence checks
    # -----------------------------------------------------------------------

    async def check_in_calibre(self, title: str, author: str) -> Optional[str]:
        try:
            library = await asyncio.get_event_loop().run_in_executor(
                None, self.calibre_library.get_library_books
            )
            for book in library:
                if _book_matches(title, author, book["title"], book["author"]):
                    return book["title"]
        except Exception as exc:
            logger.warning("Calibre presence check failed: %s", exc)
        return None

    async def check_in_audiobooks(self, title: str, author: str) -> Optional[str]:
        try:
            ab_dir = Path(self.audiobooks_dir)
            if not ab_dir.is_dir():
                return None
            for entry in ab_dir.iterdir():
                if not entry.is_dir():
                    continue
                # Directory names are "Author - Title". Split the raw name
                # before normalising — _norm strips the hyphen, so splitting
                # afterwards never finds the separator.
                orig_parts = entry.name.split(" - ", 1)
                dir_title = orig_parts[-1].strip()
                dir_author = orig_parts[0] if len(orig_parts) == 2 else ""
                if _book_matches(title, author, dir_title, dir_author):
                    return dir_title
        except Exception as exc:
            logger.warning("Audiobooks presence check failed: %s", exc)
        return None

    # -----------------------------------------------------------------------
    # Download history
    # -----------------------------------------------------------------------

    async def check_history(self, title: str, author: str) -> tuple[Optional[HistoryMatch], set[str]]:
        """
        Look for earlier non-failed downloads of this book.

        Returns (most recent matching download or None, normalised release
        titles of *all* non-failed downloads) — the latter lets callers flag
        individual releases that were already sent regardless of how the
        book was titled at the time.
        """
        if self.history_db is None:
            return None, set()
        try:
            rows = await asyncio.get_event_loop().run_in_executor(
                None, self.history_db.get_active_downloads
            )
        except Exception as exc:
            logger.warning("History check failed: %s", exc)
            return None, set()

        sent_titles = {_norm(r["release_title"]) for r in rows if r.get("release_title")}
        for r in rows:  # already newest-first
            if _book_matches(title, author, r["title"], r["author"]):
                return HistoryMatch(
                    status=r["status"],
                    created_at=r["created_at"],
                    release_title=r.get("release_title"),
                    media_type=r.get("media_type"),
                    protocol=r.get("protocol"),
                ), sent_titles
        return None, sent_titles

    # -----------------------------------------------------------------------
    # Full resolution
    # -----------------------------------------------------------------------

    async def resolve_book(
        self, title: str, author: str, include_audiobooks: bool = True
    ) -> ReleasesResponse:
        """
        Resolve one book: Calibre + audiobook presence, download history, and
        Prowlarr ebook + audiobook release searches, all run concurrently.

        include_audiobooks=False skips the audiobook Prowlarr search (halving
        indexer load); the local audiobook-folder presence check still runs.

        Callers pass already-stripped, non-empty title/author (at least one
        must be non-empty). Raises on unexpected failure; callers decide how
        to surface it (HTTP 502 for the endpoint, per-book error for the job).
        """
        async def _no_releases():
            return [], []

        (eb_acc, eb_rej), (ab_acc, ab_rej), library, cal_title, ab_title, (history, sent) = await asyncio.gather(
            self.prowlarr.search_releases(title, author, content_type="ebook"),
            self.prowlarr.search_releases(title, author, content_type="audiobook")
            if include_audiobooks else _no_releases(),
            asyncio.get_event_loop().run_in_executor(None, self.calibre_library.get_library_books),
            self.check_in_calibre(title, author),
            self.check_in_audiobooks(title, author),
            self.check_history(title, author),
        )

        # Pre-computed once per search (not per release) -- both are the
        # same for every release in this response.
        author_candidates = _authors_subset(author, library)
        all_authors_by_id = _all_authors_by_id(library)

        def item(r) -> ReleaseItem:
            d = r.to_dict()
            lib_match = _find_calibre_match_for_release(d.get("title") or "", author_candidates, all_authors_by_id)
            library_url = (
                f"{self.calibre_web_url}/book/{lib_match['id']}"
                if lib_match and self.calibre_web_url else None
            )
            return ReleaseItem(
                **d,
                already_requested=_norm(d.get("title") or "") in sent,
                already_in_library=lib_match is not None,
                library_title=lib_match["title"] if lib_match else None,
                library_url=library_url,
            )

        return ReleasesResponse(
            ebook_accepted=[item(r) for r in eb_acc],
            ebook_rejected=[item(r) for r in eb_rej],
            audiobook_accepted=[item(r) for r in ab_acc],
            audiobook_rejected=[item(r) for r in ab_rej],
            calibre_title=cal_title,
            audiobooks_title=ab_title,
            history_match=history,
        )
