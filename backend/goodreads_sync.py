#!/usr/bin/env python3
"""
Goodreads shelf sync — polls a Goodreads RSS shelf feed, checks each book
against Calibre, and auto-dispatches downloads for books not yet in the library.

Runs as a daily cron job. Limits dispatches per run (GOODREADS_MAX_PER_RUN)
to avoid flooding the download queue. Books with no Prowlarr result are
retried automatically after 14 days.

Usage:
    goodreads_sync.py [--env /path/to/.env] [--dry-run] [--max N]

Cron (daily at 8am):
    0 8 * * * /path/to/venv/bin/python /path/to/goodreads_sync.py \
        --env /path/to/.env >> ~/logs/v2_goodreads_sync.log 2>&1
"""

import argparse
import asyncio
import email.utils
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Bootstrap: load env before importing settings
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Sync Goodreads shelf → download queue")
parser.add_argument("--env", default=None, help="Path to .env file")
parser.add_argument("--dry-run", action="store_true", help="Search but don't dispatch")
parser.add_argument("--max", type=int, default=None, help="Override max dispatches per run")
args, _ = parser.parse_known_args()

if args.env:
    from dotenv import load_dotenv
    load_dotenv(args.env, override=True)

sys.path.insert(0, str(Path(__file__).parent))
from app.settings import settings
from app.history import HistoryDB
from app.calibre_library import CalibreLibrary
from app.prowlarr_client import ProwlarrClient
from app.download_client import DownloadClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [goodreads] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Goodreads RSS
# ---------------------------------------------------------------------------

def fetch_shelf(user_id: str, shelf: str) -> list[dict]:
    """
    Fetch all books from a Goodreads RSS shelf feed (paginates automatically).
    Returns list of {goodreads_id, title, author} dicts.
    The shelf must be public for the RSS feed to be accessible.
    """
    books: list[dict] = []
    page = 1

    while True:
        url = (
            f"https://www.goodreads.com/review/list_rss/{user_id}"
            f"?shelf={shelf}&per_page=200&page={page}"
        )
        try:
            req = Request(url, headers={"User-Agent": "bookshelf-portal/1.0"})
            with urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except URLError as exc:
            logger.error("Failed to fetch Goodreads RSS page %d: %s", page, exc)
            break

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            logger.error("Failed to parse Goodreads RSS: %s", exc)
            break

        items = root.findall(".//item")
        if not items:
            break

        for item in items:
            gr_id = (item.findtext("book_id") or item.findtext(".//book/id") or "").strip()
            title = (item.findtext("title") or "").strip()
            author = (item.findtext("author_name") or "").strip()
            date_added = _parse_gr_date(item.findtext("user_date_added") or "")

            if gr_id and title:
                books.append({"goodreads_id": gr_id, "title": title, "author": author, "date_added": date_added})

        if len(items) < 200:
            break
        page += 1

    logger.info("Fetched %d book(s) from shelf %r (user %s)", len(books), shelf, user_id)
    return books


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_gr_date(s: str):
    """Parse a Goodreads RSS user_date_added string → date, or None on failure."""
    if not s:
        return None
    try:
        tt = email.utils.parsedate(s.strip())
        if tt:
            return date(*tt[:3])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Calibre dedup
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _title_variants(title: str) -> set[str]:
    """
    Return all normalized forms of a title to use for matching.
    Handles:
    - Goodreads series markers: "Neuromancer (Sprawl, #1)" → "Neuromancer"
    - Subtitles on either side: "Train Dreams: A Novella" ↔ "Train Dreams"
    - Non-series parentheticals in Calibre: "The Three-Body Problem (The Three-Body Trilogy)"
    """
    variants = set()
    variants.add(_norm(title))
    # Strip all parentheticals
    no_parens = re.sub(r"\s*\([^)]*\)", "", title).strip()
    variants.add(_norm(no_parens))
    # Base title (before first colon)
    variants.add(_norm(no_parens.split(":")[0].strip()))
    variants.add(_norm(title.split(":")[0].strip()))
    variants.discard("")
    return variants


def in_calibre(title: str, author: str, library: list[dict]) -> bool:
    """
    Match on normalized title variants (stripping subtitles and series markers)
    and on author word-set (handles "Last, First" / "Last| First" storage in Calibre).
    """
    cands = _title_variants(title)
    an_words = set(_norm(author).split()) if author else set()

    for book in library:
        if _title_variants(book["title"]) & cands:
            if not an_words:
                return True
            if set(_norm(book["author"]).split()) == an_words:
                return True
    return False


# ---------------------------------------------------------------------------
# Release picking
# ---------------------------------------------------------------------------

def pick_best_release(accepted):
    """
    From accepted Prowlarr releases (pre-sorted by score desc), return the
    best one — epub preferred, then highest score regardless of format.
    """
    if not accepted:
        return None
    epub = [r for r in accepted if r.detected_format == "epub"]
    return epub[0] if epub else accepted[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run():
    max_run  = args.max if args.max is not None else settings.goodreads_max_per_run
    dry      = args.dry_run

    logger.info("%s — max_per_run=%d", "DRY RUN" if dry else "LIVE", max_run)

    db          = HistoryDB(settings.history_db_path)

    # Migrate legacy env-based profile to DB on first run
    profiles = db.get_goodreads_profiles()
    if not profiles and settings.goodreads_user_id:
        logger.info(
            "Migrating env profile to DB: user=%s shelf=%r",
            settings.goodreads_user_id, settings.goodreads_shelf,
        )
        db.add_goodreads_profile(
            name="Brendan",
            user_id=settings.goodreads_user_id,
            shelf=settings.goodreads_shelf,
        )
        profiles = db.get_goodreads_profiles()

    if not profiles:
        logger.error("No Goodreads profiles configured — add one via the portal Admin page or set GOODREADS_USER_ID in .env")
        sys.exit(1)

    logger.info("Loaded %d profile(s): %s", len(profiles), ", ".join(p["name"] for p in profiles))

    calibre_lib = CalibreLibrary(library_path=settings.calibre_library_path)
    prowlarr    = ProwlarrClient(
        base_url=settings.prowlarr_base_url,
        api_key=settings.prowlarr_api_key,
    )
    dl_client = DownloadClient(
        torrent_client=settings.torrent_client,
        rtorrent_url=settings.rtorrent_url,
        rtorrent_user=settings.rtorrent_user,
        rtorrent_password=settings.rtorrent_password,
        rtorrent_download_dir=settings.rtorrent_download_dir,
        rtorrent_category=settings.rtorrent_category,
        rtorrent_imported_category=settings.rtorrent_imported_category,
        qbittorrent_url=settings.qbittorrent_url,
        qbittorrent_user=settings.qbittorrent_user,
        qbittorrent_password=settings.qbittorrent_password,
        qbittorrent_download_dir=settings.qbittorrent_download_dir,
        qbittorrent_category=settings.qbittorrent_category,
        qbittorrent_imported_category=settings.qbittorrent_imported_category,
        sabnzbd_base_url=settings.sabnzbd_base_url,
        sabnzbd_api_key=settings.sabnzbd_api_key,
        sabnzbd_category=settings.sabnzbd_category,
    )

    # Check MAM seeding slot availability before doing anything.
    # Only auto-cap when --max wasn't explicitly passed (preserves dry-run reports).
    mam_unsatisfied = await dl_client.count_mam_unsatisfied()
    # Cap against the block threshold (buffer below MAM's real 150 cap),
    # shared with the portal's interactive dispatch guard.
    mam_limit = settings.mam_block_threshold
    mam_slots = max(0, mam_limit - mam_unsatisfied)
    logger.info(
        "MAM unsatisfied=%d/%d (cap %d) → %d slot(s) available",
        mam_unsatisfied, mam_limit, settings.mam_max_unsatisfied, mam_slots,
    )
    if args.max is None and not dry:
        max_run = min(max_run, mam_slots)
        if mam_slots == 0:
            logger.warning("MAM slot limit reached — no downloads this run")

    library = calibre_lib.get_library_books()
    logger.info("Calibre library: %d books", len(library))

    dispatched = 0

    for profile in profiles:
        if dispatched >= max_run:
            break

        user_id = profile["user_id"]
        shelf   = profile["shelf"]
        name    = profile["name"]

        logger.info("--- Profile: %s (user=%s shelf=%r) ---", name, user_id, shelf)
        shelf_books = fetch_shelf(user_id, shelf)

        sync_from_date = None
        if profile.get("sync_from"):
            try:
                sync_from_date = date.fromisoformat(profile["sync_from"])
                logger.info("Filtering to books added on or after %s", sync_from_date)
            except ValueError:
                pass

        for book in shelf_books:
            if dispatched >= max_run:
                logger.info("Reached max_per_run=%d — stopping for today", max_run)
                break

            gr_id  = book["goodreads_id"]
            title  = book["title"]
            author = book["author"]

            if sync_from_date is not None:
                book_date = book.get("date_added")
                if book_date is not None and book_date < sync_from_date:
                    logger.debug("Skip (added %s, before sync_from %s): %r", book_date, sync_from_date, title)
                    continue

            if db.goodreads_already_seen(gr_id):
                logger.debug("Skip (already seen): %r", title)
                continue

            if in_calibre(title, author, library):
                logger.info("Already in Calibre: %r by %s", title, author)
                db.goodreads_mark_seen(gr_id, title, author, status="in_calibre")
                continue

            logger.info("Searching: %r by %s", title, author)
            accepted, _ = await prowlarr.search_releases(title, author)
            release = pick_best_release(accepted)

            if release is None:
                logger.warning("No release found for %r — will retry in 14 days", title)
                db.goodreads_mark_seen(gr_id, title, author, status="no_release")
                continue

            logger.info(
                "%s %r  release=%r  fmt=%s  %.1fMB  score=%d  via %s",
                "Would dispatch" if dry else "Dispatching",
                title, release.title, release.detected_format or "?",
                release.size_mb, release.score, release.indexer,
            )

            if dry:
                dispatched += 1
                continue

            try:
                download_id = await dl_client.dispatch(
                    protocol=release.protocol,
                    download_url=release.download_url,
                    title=title,
                )
                record_id = db.create_download(
                    title=title,
                    author=author,
                    release_title=release.title,
                    indexer=release.indexer,
                    protocol=release.protocol,
                    download_id=download_id,
                    source=f"goodreads:{name}",
                )
                db.goodreads_mark_seen(
                    gr_id, title, author, status="queued",
                    download_record_id=record_id,
                )
                logger.info(
                    "Dispatched %r → download_id=%s record=%s",
                    title, download_id[:12], record_id[:8],
                )
                dispatched += 1
            except Exception as exc:
                logger.error("Dispatch failed for %r: %s", title, exc)
                db.goodreads_mark_seen(gr_id, title, author, status="error")

    logger.info(
        "Done — %s=%d  profiles=%d",
        "would_dispatch" if dry else "dispatched",
        dispatched, len(profiles),
    )


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
