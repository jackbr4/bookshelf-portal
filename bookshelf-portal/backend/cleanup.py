#!/usr/bin/env python3
"""
Torrent cleanup — removes completed book torrents and their files after a
configurable number of weeks. Designed to run as a daily cron job.

Only targets torrents in the 'books-imported' or 'readarr-imported' categories
(i.e. confirmed imported to Calibre by the watcher or Readarr).

Usage:
    cleanup.py [--env /path/to/.env] [--weeks N] [--dry-run]

Cron (daily at 3am):
    0 3 * * * /path/to/venv/bin/python /path/to/cleanup.py \
        --env /path/to/.env >> ~/logs/v2_cleanup.log 2>&1
"""

import argparse
import logging
import shutil
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from base64 import b64encode
from pathlib import Path
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Bootstrap: load env file before importing settings
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Remove old imported book torrents and files.")
parser.add_argument("--env", default=None, help="Path to .env file")
parser.add_argument("--weeks", type=int, default=12, help="Remove torrents finished more than N weeks ago (default: 12)")
parser.add_argument("--dry-run", action="store_true", help="Print what would be removed without deleting anything")
args, _ = parser.parse_known_args()

if args.env:
    from dotenv import load_dotenv
    load_dotenv(args.env, override=True)

sys.path.insert(0, str(Path(__file__).parent))
from app.settings import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [cleanup] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

IMPORTED_CATEGORIES = {"books-imported", "readarr-imported"}
CUTOFF_SECONDS = args.weeks * 7 * 24 * 3600

# ~/Downloads/ is the old retired download path — everything there is eligible
# regardless of age. ~/files/Downloads/ is the active path — age filter applies.
OLD_DOWNLOADS = Path.home() / "Downloads"
NEW_DOWNLOADS = Path.home() / "files" / "Downloads"

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# rTorrent XMLRPC
# ---------------------------------------------------------------------------

def _rt_request(body: bytes) -> ET.Element:
    auth = b64encode(
        f"{settings.rtorrent_user}:{settings.rtorrent_password}".encode()
    ).decode()
    req = Request(
        settings.rtorrent_url,
        data=body,
        headers={"Content-Type": "text/xml", "Authorization": f"Basic {auth}"},
    )
    with urlopen(req, context=_ssl_ctx, timeout=30) as resp:
        return ET.fromstring(resp.read())


def _rt_call(method: str, *params) -> ET.Element:
    param_xml = "".join(
        f"<param><value><string>{p}</string></value></param>" for p in params
    )
    body = (
        '<?xml version="1.0"?>'
        f"<methodCall><methodName>{method}</methodName>"
        f"<params>{param_xml}</params></methodCall>"
    ).encode()
    return _rt_request(body)


def _scalar(root: ET.Element) -> str:
    for tag in ("i8", "i4", "int", "string"):
        el = root.find(f".//{tag}")
        if el is not None:
            return el.text or ""
    return ""


def fetch_all_torrents() -> list[dict]:
    """Return all torrents in one multicall with name/category/finished/path/hash."""
    body = (
        '<?xml version="1.0"?>'
        '<methodCall><methodName>d.multicall2</methodName><params>'
        '<param><value><string></string></value></param>'
        '<param><value><string>default</string></value></param>'
        '<param><value><string>d.name=</string></value></param>'
        '<param><value><string>d.custom1=</string></value></param>'
        '<param><value><string>d.timestamp.finished=</string></value></param>'
        '<param><value><string>d.base_path=</string></value></param>'
        '<param><value><string>d.hash=</string></value></param>'
        '</params></methodCall>'
    ).encode()
    root = _rt_request(body)

    torrents = []
    for torrent_el in root.findall("./params/param/value/array/data/value"):
        vals = []
        for field_el in torrent_el.findall("./array/data/value"):
            for child in field_el:
                if child.tag in ("string", "i8", "i4", "int"):
                    vals.append(child.text or "")
                    break
            else:
                vals.append("")

        if len(vals) >= 5:
            ts_raw = vals[2]
            torrents.append({
                "name":        vals[0],
                "category":    vals[1],
                "finished_ts": int(ts_raw) if ts_raw.isdigit() else 0,
                "base_path":   vals[3],
                "hash":        vals[4],
            })

    return torrents

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cutoff = time.time() - CUTOFF_SECONDS
    dry = args.dry_run

    logger.info(
        "%s — old path: remove all | new path: remove if finished before %s",
        "DRY RUN" if dry else "LIVE",
        time.strftime("%Y-%m-%d", time.localtime(cutoff)),
    )

    try:
        all_torrents = fetch_all_torrents()
    except Exception as exc:
        logger.error("Failed to fetch torrent list from rTorrent: %s", exc)
        sys.exit(1)

    logger.info("%d total torrents in rTorrent", len(all_torrents))

    def is_eligible(t: dict) -> bool:
        p = Path(t["base_path"]) if t["base_path"] else None
        if p is None:
            return False

        cat = t["category"]
        in_old = p == OLD_DOWNLOADS or str(p).startswith(str(OLD_DOWNLOADS) + "/")
        in_new = p == NEW_DOWNLOADS or str(p).startswith(str(NEW_DOWNLOADS) + "/")

        if not (in_old or in_new):
            return False  # not a book download path — never touch it

        # Accept confirmed-imported labels OR no label at all (unlabelled in Downloads)
        if cat not in IMPORTED_CATEGORIES and cat != "":
            return False

        # Old retired path: remove unconditionally
        if in_old:
            return True
        # Active path: apply age filter
        return t["finished_ts"] > 0 and t["finished_ts"] < cutoff

    candidates = [t for t in all_torrents if is_eligible(t)]

    if not candidates:
        logger.info("No torrents eligible for removal.")
        return

    logger.info("%d torrent(s) eligible for removal.", len(candidates))

    removed = errors = 0

    for t in sorted(candidates, key=lambda x: x["finished_ts"]):
        age_days = int((time.time() - t["finished_ts"]) / 86400) if t["finished_ts"] else 0
        finished = time.strftime("%Y-%m-%d", time.localtime(t["finished_ts"])) if t["finished_ts"] else "unknown"
        bp = t["base_path"]
        if bp.startswith(str(OLD_DOWNLOADS) + "/") or bp == str(OLD_DOWNLOADS):
            reason = "old-path"
        elif t["category"] == "":
            reason = f"unlabelled/{age_days}d old"
        else:
            reason = f"{age_days}d old"
        logger.info(
            "%s %r  finished=%s  reason=%s  path=%s",
            "Would remove" if dry else "Removing",
            t["name"], finished, reason, t["base_path"],
        )

        if dry:
            removed += 1
            continue

        try:
            # Delete files first
            if t["base_path"]:
                p = Path(t["base_path"])
                if p.exists():
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                    logger.info("Deleted path: %s", t["base_path"])
                else:
                    logger.info("Path already gone: %s", t["base_path"])

            # Remove torrent record from rTorrent
            _rt_call("d.erase", t["hash"])
            logger.info("Erased torrent %s from rTorrent", t["hash"][:12])
            removed += 1

        except Exception as exc:
            logger.error("Error processing %r: %s", t["name"], exc)
            errors += 1

    logger.info(
        "Done — %s=%d  errors=%d",
        "would_remove" if dry else "removed",
        removed,
        errors,
    )


if __name__ == "__main__":
    main()
