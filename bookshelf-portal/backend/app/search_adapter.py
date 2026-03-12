"""
Search adapter: normalisation, scoring, deduplication, and library annotation
for Bookshelf book lookup results.

This module sits between the raw Bookshelf API response and the API response
returned to the frontend.  It does not make any network calls — it only
transforms and ranks the data passed in.

Future series support should be added here as a separate pipeline once a
reliable metadata source is identified.
"""

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SCORE_THRESHOLD = 10
MAX_RESULTS = 10

# Edition-noise patterns stripped during normalisation (for scoring only —
# the display title is never mutated).
_EDITION_NOISE = re.compile(
    r"\b(enhanced|illustrated|deluxe|annotated|revised|expanded|"
    r"collector[''s]*|special|anniversary|unabridged|omnibus)\s+edition\b"
    r"|\(epub\)|\(mobi\)|\(azw3\)",
    re.IGNORECASE,
)

# Junk-book patterns.  Deliberately specific to avoid penalising legitimate
# titles that happen to contain a common word (e.g. "Guide" in "The
# Hitchhiker's Guide to the Galaxy", "Notes" in "Notes from Underground").
_JUNK_PHRASES = {
    "summary of",
    "a summary",
    "workbook for",
    "study guide",
    "reading guide",
    "readers guide",        # "reader's guide" normalises to this
    "a guide to",           # "A Guide to Dune" — NOT "Hitchhiker's Guide to the Galaxy"
    "literary analysis",
    "critical analysis",
    "a companion to",
    "readers companion",    # "reader's companion" normalises to this
    "readers notes",        # "reader's notes" normalises to this
    "critical essays",
    "abridged edition",
    "abridged version",
}

# Mild penalty keywords — legitimate books can contain these but they usually
# indicate a non-standard edition.
_EDITION_PENALTY_TERMS = {"enhanced edition", "illustrated", "deluxe edition", "annotated"}

# English language identifiers.
_ENGLISH_LANG = {"en", "eng", "english"}


# ---------------------------------------------------------------------------
# Internal result model
# ---------------------------------------------------------------------------

def _parse_author_from_raw(raw: dict) -> str:
    """
    Extract a human-readable author name from a Bookshelf lookup result.

    Bookshelf uses several different shapes depending on whether the result
    comes from a library entry or a lookup:
      - raw["author"]["authorName"]  (nested dict)
      - raw["authorTitle"]           ("Lastname, Firstname Book Title Here")
      - raw["authorName"]            (flat string, less common)
    """
    if isinstance(raw.get("author"), dict):
        name = raw["author"].get("authorName", "")
        if name:
            return name

    if raw.get("authorTitle"):
        return _parse_author_title(raw["authorTitle"])

    return raw.get("authorName", "")


def _parse_author_title(author_title: str) -> str:
    """Convert Bookshelf 'Lastname, Firstname Book Title' → 'Firstname Lastname'."""
    parts = author_title.split(" ")
    name_parts: list[str] = []
    for part in parts:
        name_parts.append(part)
        if len(name_parts) >= 2 and name_parts[0].endswith(","):
            break
    if len(name_parts) >= 2:
        last = name_parts[0].rstrip(",")
        first = name_parts[1]
        return f"{first} {last}"
    return parts[0] if parts else ""


@dataclass
class SearchBookResult:
    foreign_id: Optional[str]
    title: str
    normalized_title: str
    author: str
    normalized_author: str
    year: Optional[int]
    language: Optional[str]
    cover_url: Optional[str]
    series_name: Optional[str]
    foreign_edition_id: Optional[str]
    score: float = 0.0
    can_add: bool = True
    status_label: str = "available"
    # Preserve the raw dict so we can re-use it downstream without re-fetching
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Return a normalised string suitable for scoring/comparison.
    The original display text is never touched.

    Steps:
    1. Unicode NFKC normalisation (handles special quotes, ligatures, etc.)
    2. Lowercase + strip
    3. Fix trailing-article form: "Game of Thrones, A" → "a game of thrones"
    4. Strip edition noise
    5. Remove punctuation (replace with space)
    6. Collapse whitespace
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()

    # "title, a/an/the" → "a/an/the title"
    text = re.sub(r"^(.*),\s+(a|an|the)$", r"\2 \1", text)

    text = _EDITION_NOISE.sub(" ", text)

    # Remove apostrophes/smart-quotes without inserting a space (so "hitchhiker's"
    # → "hitchhikers", not "hitchhiker s").
    text = re.sub(r"[''`]", "", text)

    # Replace remaining punctuation with space
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize_query(query: str) -> list[str]:
    return [t for t in normalize_text(query).split(" ") if t]


def extract_language(raw: dict) -> Optional[str]:
    return raw.get("language") or raw.get("metadataLanguage") or None


# ---------------------------------------------------------------------------
# Normalise raw Bookshelf result → SearchBookResult
# ---------------------------------------------------------------------------

def normalize_raw_book_result(raw: dict) -> SearchBookResult:
    title = raw.get("title") or ""
    author = _parse_author_from_raw(raw)

    # Cover URL: prefer remoteCover, fall back to images[].remoteUrl
    cover_url: Optional[str] = raw.get("remoteCover")
    if not cover_url and raw.get("images"):
        cover_url = raw["images"][0].get("remoteUrl")

    # Year from releaseDate ISO string or plain year field
    year: Optional[int] = None
    if raw.get("releaseDate"):
        try:
            year = int(str(raw["releaseDate"])[:4])
        except (ValueError, TypeError):
            pass

    return SearchBookResult(
        foreign_id=str(raw.get("foreignBookId") or raw.get("id") or ""),
        title=title,
        normalized_title=normalize_text(title),
        author=author,
        normalized_author=normalize_text(author),
        year=year,
        language=extract_language(raw),
        cover_url=cover_url,
        series_name=raw.get("seriesTitle") or None,
        foreign_edition_id=raw.get("foreignEditionId"),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _contains_junk_phrase(title: str) -> bool:
    normalised = normalize_text(title)
    return any(phrase in normalised for phrase in _JUNK_PHRASES)


def score_result(query: str, query_tokens: list[str], result: SearchBookResult) -> float:
    score: float = 0.0
    nq = normalize_text(query)
    title = result.normalized_title
    author = result.normalized_author

    # --- Positive signals ---

    # Exact title match
    if title == nq:
        score += 100

    # Title starts with the full query
    if title.startswith(nq) and nq:
        score += 25

    # All query tokens present in title
    if query_tokens and all(tok in title for tok in query_tokens):
        score += 20

    # Fuzzy title similarity (token_sort_ratio handles word-order variation)
    if nq and title:
        similarity = fuzz.token_sort_ratio(nq, title)
        if similarity >= 95:
            score += 50
        elif similarity >= 90:
            score += 35
        elif similarity >= 85:
            score += 20
        elif similarity >= 75:
            score += 5
        else:
            score -= 20
    else:
        score -= 20

    # Author token bonus (useful for "george martin game of thrones" style queries)
    if query_tokens and author:
        hits = sum(1 for tok in query_tokens if tok in author)
        if hits:
            score += min(hits * 10, 20)

    # Language preference
    if result.language:
        lang = result.language.lower().strip()
        if lang in _ENGLISH_LANG:
            score += 15
        else:
            score -= 20

    # Series name relevance (weak signal)
    if result.series_name and nq:
        normalised_series = normalize_text(result.series_name)
        if nq in normalised_series:
            score += 10

    # --- Negative signals ---

    # Mild edition noise penalty (shouldn't outrank clean editions)
    lowered = result.title.lower()
    if any(term in lowered for term in _EDITION_PENALTY_TERMS):
        score -= 5

    # Strong junk penalty (targeted phrases only — see _JUNK_PHRASES)
    if _contains_junk_phrase(result.title):
        score -= 40

    return score


# ---------------------------------------------------------------------------
# Grouping (deduplicate editions)
# ---------------------------------------------------------------------------

def group_duplicate_editions(results: list[SearchBookResult]) -> list[SearchBookResult]:
    """
    Keep only the highest-scoring result per (normalised_title, normalised_author) pair.
    This collapses multiple editions of the same book into one display row.
    """
    best: dict[str, SearchBookResult] = {}
    for result in results:
        key = f"{result.normalized_title}::{result.normalized_author}"
        if key not in best or result.score > best[key].score:
            best[key] = result
    return list(best.values())


# ---------------------------------------------------------------------------
# Library annotation
# ---------------------------------------------------------------------------

def annotate_existing_or_monitored(
    results: list[SearchBookResult],
    library_books: list[dict],
) -> list[SearchBookResult]:
    """
    Mark results that are already in the Bookshelf library.

    Matching priority:
    1. foreignBookId exact match
    2. Normalised (title, author) pair match
    """
    foreign_id_set: set[str] = set()
    title_author_set: set[tuple[str, str]] = set()

    for book in library_books:
        fid = str(book.get("foreignBookId") or "")
        if fid:
            foreign_id_set.add(fid)

        t = normalize_text(book.get("title") or "")
        # Author may be nested or flat depending on library endpoint shape
        if isinstance(book.get("author"), dict):
            a = normalize_text(book["author"].get("authorName") or "")
        else:
            a = normalize_text(book.get("authorName") or book.get("author") or "")
        if t:
            title_author_set.add((t, a))

    for result in results:
        if result.foreign_id and result.foreign_id in foreign_id_set:
            result.can_add = False
            result.status_label = "already_in_library"
            continue
        pair = (result.normalized_title, result.normalized_author)
        if pair in title_author_set:
            result.can_add = False
            result.status_label = "already_in_library"

    return results


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def search_books(
    query: str,
    raw_books: list[dict],
    library_books: list[dict],
) -> list[SearchBookResult]:
    """
    Full search pipeline:
      raw Bookshelf results → normalise → score → filter → deduplicate
      → rank → annotate library status → return top N

    Args:
        query:         The user's original search string.
        raw_books:     Raw dicts from /api/v1/book/lookup.
        library_books: Raw dicts from /api/v1/book (the library).
    """
    t0 = time.monotonic()
    logger.info("[search] query=%r  raw_results=%d  library_size=%d",
                query, len(raw_books), len(library_books))

    query_tokens = tokenize_query(query)

    # --- Normalise ---
    normalised = [normalize_raw_book_result(r) for r in raw_books]
    logger.info("[search] normalised=%d", len(normalised))

    # --- Score ---
    for result in normalised:
        result.score = score_result(query, query_tokens, result)

    # --- Filter below threshold ---
    filtered = [r for r in normalised if r.score >= MIN_SCORE_THRESHOLD]
    logger.info("[search] after_filter=%d  (threshold=%d)", len(filtered), MIN_SCORE_THRESHOLD)

    # --- Deduplicate editions ---
    grouped = group_duplicate_editions(filtered)
    logger.info("[search] after_dedup=%d", len(grouped))

    # --- Rank ---
    ranked = sorted(grouped, key=lambda r: r.score, reverse=True)

    # --- Annotate library status ---
    annotated = annotate_existing_or_monitored(ranked, library_books)

    final = annotated[:MAX_RESULTS]
    elapsed = time.monotonic() - t0
    logger.info("[search] final=%d  elapsed=%.2fs", len(final), elapsed)

    return final
