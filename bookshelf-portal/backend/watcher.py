#!/usr/bin/env python3
"""
Phase 5 watcher — polls rTorrent / SABnzbd for completed downloads,
runs calibredb add, and updates the v2 history DB.

Designed to run as a cron job every minute:
    * * * * * /home/jackbr4/apps/bookshelf-portal/bookshelf-portal/backend/venv/bin/python \
        /home/jackbr4/apps/bookshelf-portal/bookshelf-portal/backend/watcher.py \
        --env /home/jackbr4/apps/bookshelf-portal/bookshelf-portal/.env.dev \
        >> /home/jackbr4/logs/v2_watcher.log 2>&1

Without --env it reads from the production .env next to settings.py.
"""

import argparse
import logging
import ssl
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from base64 import b64encode
import json
import urllib.parse

# ---------------------------------------------------------------------------
# Bootstrap: load env file before importing settings
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--env", default=None)
args, _ = parser.parse_known_args()

if args.env:
    from dotenv import load_dotenv
    load_dotenv(args.env, override=True)

# Now settings picks up the correct env vars
sys.path.insert(0, str(Path(__file__).parent))
from app.settings import settings
from app.history import HistoryDB
from app.calibre_client import CalibreClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [watcher] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EPUB/PDF formats we want to import
# ---------------------------------------------------------------------------

BOOK_EXTENSIONS = {".epub", ".pdf"}


# ---------------------------------------------------------------------------
# rTorrent XMLRPC (sync, plain urllib — no async needed in a cron script)
# ---------------------------------------------------------------------------

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _rt_call(method: str, *params) -> bytes:
    param_xml = "".join(
        f"<param><value><string>{p}</string></value></param>" for p in params
    )
    body = (
        '<?xml version="1.0"?>'
        "<methodCall>"
        f"<methodName>{method}</methodName>"
        f"<params>{param_xml}</params>"
        "</methodCall>"
    ).encode()

    auth = b64encode(
        f"{settings.rtorrent_user}:{settings.rtorrent_password}".encode()
    ).decode()
    req = Request(
        settings.rtorrent_url,
        data=body,
        headers={
            "Content-Type": "text/xml",
            "Authorization": f"Basic {auth}",
        },
    )
    with urlopen(req, context=_ssl_ctx, timeout=15) as resp:
        return resp.read()


def rt_is_complete(info_hash: str) -> bool:
    """Return True if the torrent is finished downloading."""
    try:
        raw = _rt_call("d.complete", info_hash)
        root = ET.fromstring(raw)
        for tag in ("i8", "i4", "int"):
            el = root.find(f".//{tag}")
            if el is not None:
                return int(el.text) == 1
    except Exception as exc:
        logger.warning("[rtorrent] d.complete failed for %s: %s", info_hash[:12], exc)
    return False


def rt_base_path(info_hash: str) -> Optional[str]:
    """Return the base path (file or directory) for a torrent."""
    try:
        raw = _rt_call("d.base_path", info_hash)
        root = ET.fromstring(raw)
        el = root.find(".//string")
        return el.text if el is not None else None
    except Exception as exc:
        logger.warning("[rtorrent] d.base_path failed for %s: %s", info_hash[:12], exc)
    return None


def rt_set_category(info_hash: str, category: str):
    """Relabel a torrent to the imported category."""
    try:
        _rt_call("d.custom1.set", info_hash, category)
        logger.info("[rtorrent] relabelled %s → %s", info_hash[:12], category)
    except Exception as exc:
        logger.warning("[rtorrent] relabel failed for %s: %s", info_hash[:12], exc)


# ---------------------------------------------------------------------------
# SABnzbd (sync HTTP)
# ---------------------------------------------------------------------------

def sab_is_complete(nzo_id: str) -> tuple[bool, Optional[str]]:
    """
    Return (complete, storage_path).

    Searches both the history and active queue. Returns (True, path) when done,
    (False, None) when still downloading or not found.
    """
    base = settings.sabnzbd_base_url.rstrip("/")
    api_key = settings.sabnzbd_api_key

    # Check history first (completed downloads)
    url = (
        f"{base}/api?apikey={api_key}&output=json"
        f"&mode=history&limit=100&search={urllib.parse.quote(nzo_id)}"
    )
    try:
        with urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        for slot in data.get("history", {}).get("slots", []):
            if slot.get("nzo_id") == nzo_id and slot.get("status") == "Completed":
                return True, slot.get("storage")
    except Exception as exc:
        logger.warning("[sabnzbd] history check failed for %s: %s", nzo_id, exc)

    return False, None


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_book_file(base_path: str) -> Optional[Path]:
    """
    Find the first epub or pdf file at or under base_path.

    For single-file torrents, base_path is the file itself.
    For multi-file torrents, base_path is the directory.
    """
    p = Path(base_path)
    if p.is_file() and p.suffix.lower() in BOOK_EXTENSIONS:
        return p
    if p.is_dir():
        for ext in (".epub", ".pdf"):
            matches = sorted(p.rglob(f"*{ext}"))
            if matches:
                return matches[0]
    return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def process_record(record: dict, db: HistoryDB, calibre: CalibreClient):
    record_id = record["id"]
    download_id = record["download_id"]
    protocol = record["protocol"]
    title = record["title"]
    author = record["author"]

    if protocol == "torrent":
        if not rt_is_complete(download_id):
            logger.debug("[watcher] %r still downloading (torrent)", title)
            return

        base_path = rt_base_path(download_id)
        if not base_path:
            logger.warning("[watcher] no base_path for %r — skipping", title)
            return

        book_file = find_book_file(base_path)
        if book_file is None:
            logger.warning(
                "[watcher] no epub/pdf found under %s for %r", base_path, title
            )
            db.update_download_status(record_id, "error", "no epub/pdf found")
            return

        logger.info("[watcher] %r complete — importing %s", title, book_file.name)

    elif protocol == "usenet":
        complete, storage = sab_is_complete(download_id)
        if not complete:
            logger.debug("[watcher] %r still downloading (usenet)", title)
            return
        if not storage:
            logger.warning("[watcher] SABnzbd completed but no storage path for %r", title)
            db.update_download_status(record_id, "error", "no storage path from SABnzbd")
            return

        book_file = find_book_file(storage)
        if book_file is None:
            logger.warning("[watcher] no epub/pdf found in %s for %r", storage, title)
            db.update_download_status(record_id, "error", "no epub/pdf found")
            return

        logger.info("[watcher] %r complete — importing %s", title, book_file.name)

    else:
        logger.warning("[watcher] unknown protocol %r for %r", protocol, title)
        return

    # Mark as importing so we don't pick it up again on the next run
    db.update_download_status(record_id, "importing")

    calibre_id = calibre.add_book(str(book_file))
    if calibre_id is None:
        db.update_download_status(record_id, "error", "calibredb add failed")
        db.create_import(record_id, str(book_file), "error", error="calibredb add failed")
        return

    db.create_import(record_id, str(book_file), "imported", calibre_id=calibre_id)
    db.update_download_status(record_id, "imported")

    # Relabel torrent so it leaves the active readarr queue
    if protocol == "torrent":
        rt_set_category(download_id, settings.rtorrent_imported_category)

    logger.info(
        "[watcher] imported %r by %s → calibre_id=%d", title, author, calibre_id
    )


def main():
    db = HistoryDB(settings.history_db_path)
    calibre = CalibreClient(
        library_path=settings.calibre_library_path,
        image=settings.calibre_image,
    )

    pending = db.get_downloading()
    if not pending:
        logger.debug("[watcher] no pending downloads")
        return

    logger.info("[watcher] checking %d pending download(s)", len(pending))
    for record in pending:
        try:
            process_record(record, db, calibre)
        except Exception as exc:
            logger.exception(
                "[watcher] unexpected error processing %r: %s",
                record.get("title"), exc,
            )


if __name__ == "__main__":
    main()
