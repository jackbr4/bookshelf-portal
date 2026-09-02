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

from .calibre_library import CalibreLibrary
from .models import ReleaseItem, ReleasesResponse
from .prowlarr_client import ProwlarrClient

logger = logging.getLogger(__name__)


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


class BookResolver:
    def __init__(
        self,
        prowlarr: ProwlarrClient,
        calibre_library: CalibreLibrary,
        audiobooks_dir: str,
    ):
        self.prowlarr = prowlarr
        self.calibre_library = calibre_library
        self.audiobooks_dir = audiobooks_dir

    # -----------------------------------------------------------------------
    # Library presence checks
    # -----------------------------------------------------------------------

    async def check_in_calibre(self, title: str, author: str) -> Optional[str]:
        try:
            library = await asyncio.get_event_loop().run_in_executor(
                None, self.calibre_library.get_library_books
            )
            cands = _title_variants(title)
            an_words = set(_norm(author).split()) if author.strip() else set()
            for book in library:
                if _title_variants(book["title"]) & cands:
                    if not an_words or set(_norm(book["author"]).split()) == an_words:
                        return book["title"]
        except Exception as exc:
            logger.warning("Calibre presence check failed: %s", exc)
        return None

    async def check_in_audiobooks(self, title: str, author: str) -> Optional[str]:
        try:
            ab_dir = Path(self.audiobooks_dir)
            if not ab_dir.is_dir():
                return None
            cands = _title_variants(title)
            an_words = set(_norm(author).split()) if author.strip() else set()
            for entry in ab_dir.iterdir():
                if not entry.is_dir():
                    continue
                # Directory names are "Author - Title". Split the raw name
                # before normalising — _norm strips the hyphen, so splitting
                # afterwards never finds the separator.
                orig_parts = entry.name.split(" - ", 1)
                dir_title = orig_parts[-1].strip()
                dir_author = orig_parts[0] if len(orig_parts) == 2 else ""
                if _title_variants(dir_title) & cands:
                    if not an_words:
                        return dir_title
                    if set(_norm(dir_author).split()) == an_words:
                        return dir_title
        except Exception as exc:
            logger.warning("Audiobooks presence check failed: %s", exc)
        return None

    # -----------------------------------------------------------------------
    # Full resolution
    # -----------------------------------------------------------------------

    async def resolve_book(self, title: str, author: str) -> ReleasesResponse:
        """
        Resolve one book: Calibre + audiobook presence, plus Prowlarr ebook
        and audiobook release searches, all run concurrently.

        Callers pass already-stripped, non-empty title/author (at least one
        must be non-empty). Raises on unexpected failure; callers decide how
        to surface it (HTTP 502 for the endpoint, per-book error for the job).
        """
        (eb_acc, eb_rej), (ab_acc, ab_rej), cal_title, ab_title = await asyncio.gather(
            self.prowlarr.search_releases(title, author, content_type="ebook"),
            self.prowlarr.search_releases(title, author, content_type="audiobook"),
            self.check_in_calibre(title, author),
            self.check_in_audiobooks(title, author),
        )
        return ReleasesResponse(
            ebook_accepted=[ReleaseItem(**r.to_dict()) for r in eb_acc],
            ebook_rejected=[ReleaseItem(**r.to_dict()) for r in eb_rej],
            audiobook_accepted=[ReleaseItem(**r.to_dict()) for r in ab_acc],
            audiobook_rejected=[ReleaseItem(**r.to_dict()) for r in ab_rej],
            calibre_title=cal_title,
            audiobooks_title=ab_title,
        )
