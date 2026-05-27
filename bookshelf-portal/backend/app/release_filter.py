"""
Release filtering and scoring for Prowlarr results.

Keeps the rules in one place so they're easy to tune without touching
the client or route logic.
"""

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Config (move to settings.py / config.yaml if rules need user control)
# ---------------------------------------------------------------------------

ACCEPTED_FORMATS = {"epub", "pdf"}

REJECTED_FORMATS = {"mp3", "m4a", "m4b", "aac", "flac", "wav", "ogg", "aiff", "mp4", "mobi", "azw3"}

REJECTED_KEYWORDS = {
    "audiobook", "audio book", "abridged", "unabridged",
    "summary of", "a summary", "workbook for", "study guide",
    "reading guide", "readers guide", "literary analysis",
    "critical analysis", "a companion to", "cliff notes", "cliffsnotes",
    "sample", "preview", "excerpt",
}

MIN_SIZE_BYTES = 512 * 1024        # 0.5 MB — below this is almost certainly junk
MAX_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB — above this is likely an audiobook or bundle

# Format score: higher wins
FORMAT_SCORE = {"epub": 30, "pdf": 5}

# Indexer score bonus
INDEXER_SCORE = {"myanonymouse": 10, "myanonmouse": 10, "mam": 10}

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


def best_format(formats: set[str]) -> Optional[str]:
    """Return the highest-scoring accepted format from the set, or None."""
    best = None
    best_score = -1
    for fmt in formats:
        if fmt in ACCEPTED_FORMATS and FORMAT_SCORE.get(fmt, 0) > best_score:
            best = fmt
            best_score = FORMAT_SCORE[fmt]
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


def filter_release(title: str, size_bytes: int, formats: set[str]) -> FilterResult:
    """Return a FilterResult indicating whether a release should be shown."""

    # Reject if size is clearly wrong
    if size_bytes < MIN_SIZE_BYTES:
        return FilterResult(accepted=False, reason=f"too small ({size_bytes // 1024}KB)")
    if size_bytes > MAX_SIZE_BYTES:
        return FilterResult(accepted=False, reason=f"too large ({size_bytes // 1024 // 1024}MB)")

    # Reject if any detected format is audio
    if formats & REJECTED_FORMATS:
        bad = (formats & REJECTED_FORMATS).pop()
        return FilterResult(accepted=False, reason=f"audio format ({bad})")

    # Reject on title keywords
    kw = _has_rejected_keyword(title)
    if kw:
        return FilterResult(accepted=False, reason=f"rejected keyword ({kw!r})")

    # Must have at least one accepted format (or no format detected at all —
    # give unknown formats a chance rather than silently dropping them)
    fmt = best_format(formats)
    if not fmt and formats:
        # Formats were detected but none are accepted
        detected = ", ".join(sorted(formats))
        return FilterResult(accepted=False, reason=f"unsupported format ({detected})")

    return FilterResult(accepted=True, detected_format=fmt)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_release(
    detected_format: Optional[str],
    indexer: str,
    seeders: Optional[int],
    size_bytes: int,
    age_days: Optional[int],
) -> int:
    score = 0

    # Format preference
    score += FORMAT_SCORE.get(detected_format or "", 0)

    # Indexer preference (MAM preferred)
    for key, bonus in INDEXER_SCORE.items():
        if key in indexer.lower():
            score += bonus
            break

    # Seeders (torrent health) — log-scaled so 100 seeders isn't wildly better than 10
    if seeders:
        import math
        score += min(int(math.log2(seeders + 1) * 3), 20)

    # Prefer smaller files within accepted range (less likely to be bundles)
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
