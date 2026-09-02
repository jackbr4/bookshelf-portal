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
    ):
        self.prowlarr = prowlarr
        self.calibre_library = calibre_library
        self.audiobooks_dir = audiobooks_dir
        self.history_db = history_db

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

    async def resolve_book(self, title: str, author: str) -> ReleasesResponse:
        """
        Resolve one book: Calibre + audiobook presence, download history, and
        Prowlarr ebook + audiobook release searches, all run concurrently.

        Callers pass already-stripped, non-empty title/author (at least one
        must be non-empty). Raises on unexpected failure; callers decide how
        to surface it (HTTP 502 for the endpoint, per-book error for the job).
        """
        (eb_acc, eb_rej), (ab_acc, ab_rej), cal_title, ab_title, (history, sent) = await asyncio.gather(
            self.prowlarr.search_releases(title, author, content_type="ebook"),
            self.prowlarr.search_releases(title, author, content_type="audiobook"),
            self.check_in_calibre(title, author),
            self.check_in_audiobooks(title, author),
            self.check_history(title, author),
        )

        def item(r) -> ReleaseItem:
            d = r.to_dict()
            return ReleaseItem(**d, already_requested=_norm(d.get("title") or "") in sent)

        return ReleasesResponse(
            ebook_accepted=[item(r) for r in eb_acc],
            ebook_rejected=[item(r) for r in eb_rej],
            audiobook_accepted=[item(r) for r in ab_acc],
            audiobook_rejected=[item(r) for r in ab_rej],
            calibre_title=cal_title,
            audiobooks_title=ab_title,
            history_match=history,
        )
