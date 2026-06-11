"""
Release filtering and scoring for Prowlarr results.

Keeps the rules in one place so they're easy to tune without touching
the client or route logic.
"""

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ACCEPTED_FORMATS = {"epub", "pdf"}
ACCEPTED_FORMATS_AUDIO = {"m4b", "mp3", "m4a"}

REJECTED_FORMATS = {"mp3", "m4a", "m4b", "aac", "flac", "wav", "ogg", "aiff", "mp4", "mobi", "azw3"}
AUDIO_FORMATS    = {"mp3", "m4a", "m4b", "aac", "flac", "wav", "ogg", "aiff", "mp4"}

REJECTED_KEYWORDS = {
    "audiobook", "audio book", "abridged", "unabridged",
    "summary of", "a summary", "workbook for", "study guide",
    "reading guide", "readers guide", "literary analysis",
    "critical analysis", "a companion to", "cliff notes", "cliffsnotes",
    "sample", "preview", "excerpt",
}
# Keywords only relevant for ebooks (drop them in audiobook mode)
_EBOOK_ONLY_KEYWORDS = {"audiobook", "audio book", "unabridged"}

MIN_SIZE_BYTES = 512 * 1024          # 0.5 MB — applied to newsgroup results only
MAX_SIZE_BYTES = 200 * 1024 * 1024   # 200 MB — above this is likely an audiobook or bundle
MAX_SIZE_BYTES_AUDIO = 2 * 1024 * 1024 * 1024  # 2 GB for audiobooks

# Format score: higher wins
FORMAT_SCORE = {"epub": 30, "pdf": 5}
FORMAT_SCORE_AUDIO = {"m4b": 30, "m4a": 20, "mp3": 5}

# Indexer preference bonus applied by score_release()
INDEXER_SCORE_BONUS = 10

# Loaded from settings at import time so tests can override settings before importing.
def _load_indexer_config() -> tuple[frozenset[str], frozenset[str]]:
    from .settings import settings
    return (
        frozenset(settings.filter_trusted_indexers),
        frozenset(settings.filter_preferred_indexers),
    )

_TRUSTED_INDEXERS, _PREFERRED_INDEXERS = _load_indexer_config()

# ---------------------------------------------------------------------------
# Format extraction
# ---------------------------------------------------------------------------

# Matches patterns like: [ENG / EPUB], [ENG / MOBI EPUB], [FR / PDF]
_FORMAT_BRACKET = re.compile(
    r"\[(?:[A-Z]{2,3}\s*/\s*)?([\w\s]+)\]",
    re.IGNORECASE,
)

# Also catches bare format words at end of title: "Book Title EPUB"
_FORMAT_BARE = re.compile(
    r"\b(epub|mobi|azw3|pdf|mp3|m4a|m4b|aac)\b",
    re.IGNORECASE,
)


def extract_formats(title: str) -> set[str]:
    """Return all format tokens found in a release title, lowercased."""
    found: set[str] = set()

    for match in _FORMAT_BRACKET.finditer(title):
        for word in match.group(1).split():
            found.add(word.lower())

    for match in _FORMAT_BARE.finditer(title):
        found.add(match.group(1).lower())

    return found


def best_format(formats: set[str], content_type: str = "ebook") -> Optional[str]:
    """Return the highest-scoring accepted format from the set, or None."""
    if content_type == "audiobook":
        score_map = FORMAT_SCORE_AUDIO
        accepted = ACCEPTED_FORMATS_AUDIO
    else:
        score_map = FORMAT_SCORE
        accepted = ACCEPTED_FORMATS

    best = None
    best_score = -1
    for fmt in formats:
        if fmt in accepted and score_map.get(fmt, 0) > best_score:
            best = fmt
            best_score = score_map[fmt]
    return best


# ---------------------------------------------------------------------------
# Rejection logic
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    accepted: bool
    reason: Optional[str] = None
    detected_format: Optional[str] = None


def _has_rejected_keyword(title: str) -> Optional[str]:
    lower = title.lower()
    for kw in REJECTED_KEYWORDS:
        if kw in lower:
            return kw
    return None


def _is_trusted(indexer: str) -> bool:
    lower = indexer.lower()
    return any(k in lower for k in _TRUSTED_INDEXERS)


def filter_release(
    title: str,
    size_bytes: int,
    formats: set[str],
    indexer: str = "",
    content_type: str = "ebook",
) -> FilterResult:
    """Return a FilterResult indicating whether a release should be shown."""
    is_audio = content_type == "audiobook"

    # Size limits differ by type
    max_size = MAX_SIZE_BYTES_AUDIO if is_audio else MAX_SIZE_BYTES
    if size_bytes > max_size:
        return FilterResult(accepted=False, reason=f"too large ({size_bytes // 1024 // 1024}MB)")

    # Minimum size only applies to newsgroup ebook sources
    if not is_audio and not _is_trusted(indexer) and size_bytes < MIN_SIZE_BYTES:
        return FilterResult(accepted=False, reason=f"too small ({size_bytes // 1024}KB)")

    # Reject on title keywords (audiobook mode drops audio-specific noise words)
    active_keywords = (REJECTED_KEYWORDS - _EBOOK_ONLY_KEYWORDS) if is_audio else REJECTED_KEYWORDS
    lower = title.lower()
    for kw in active_keywords:
        # Use word-boundary check for "abridged" so it doesn't match inside "unabridged"
        if kw == "abridged":
            if re.search(r'\babridged\b', lower):
                return FilterResult(accepted=False, reason=f"rejected keyword ({kw!r})")
        elif kw in lower:
            return FilterResult(accepted=False, reason=f"rejected keyword ({kw!r})")

    # Accept if an accepted format is present
    fmt = best_format(formats, content_type)
    if fmt:
        return FilterResult(accepted=True, detected_format=fmt)

    # No accepted format — reject with a precise reason
    if is_audio:
        bad_formats = formats - ACCEPTED_FORMATS_AUDIO
        if formats:
            detected = ", ".join(sorted(formats))
            return FilterResult(accepted=False, reason=f"unsupported format ({detected})")
        return FilterResult(accepted=True, detected_format=None)

    bad_formats = formats & REJECTED_FORMATS
    if bad_formats:
        bad = bad_formats.pop()
        reason = "audio format" if bad in AUDIO_FORMATS else "ebook format not supported"
        return FilterResult(accepted=False, reason=f"{reason} ({bad})")

    if formats:
        detected = ", ".join(sorted(formats))
        return FilterResult(accepted=False, reason=f"unsupported format ({detected})")

    # No format detected at all — give it a chance
    return FilterResult(accepted=True, detected_format=None)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_release(
    detected_format: Optional[str],
    indexer: str,
    seeders: Optional[int],
    size_bytes: int,
    age_days: Optional[int],
    content_type: str = "ebook",
) -> int:
    score = 0
    is_audio = content_type == "audiobook"

    # Format preference
    score_map = FORMAT_SCORE_AUDIO if is_audio else FORMAT_SCORE
    score += score_map.get(detected_format or "", 0)

    # Preferred indexer bonus
    lower_indexer = indexer.lower()
    if any(k in lower_indexer for k in _PREFERRED_INDEXERS):
        score += INDEXER_SCORE_BONUS

    # Seeders (torrent health) — log-scaled so 100 seeders isn't wildly better than 10
    if seeders:
        import math
        score += min(int(math.log2(seeders + 1) * 3), 20)

    # File-size preference: ebooks prefer small (bundle avoidance); audiobooks skip this
    if not is_audio:
        mb = size_bytes / 1024 / 1024
        if mb < 5:
            score += 5
        elif mb < 20:
            score += 10

    # Prefer newer releases (NZB age)
    if age_days is not None:
        if age_days < 365:
            score += 5
        elif age_days < 730:
            score += 2

    return score
