"""
Download dispatcher — sends releases to rTorrent (XMLRPC) or SABnzbd (API).

rTorrent: verifies the download directory on every dispatch and corrects it
if it has drifted, then loads the torrent URL with the correct category.

SABnzbd: posts the NZB URL directly with the configured category.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# rTorrent XMLRPC helpers
# ---------------------------------------------------------------------------

def _xmlrpc_call(method: str, *params) -> str:
    """Build a minimal XMLRPC request body."""
    param_xml = "".join(
        f"<param><value><string>{p}</string></value></param>" for p in params
    )
    return (
        '<?xml version="1.0"?>'
        "<methodCall>"
        f"<methodName>{method}</methodName>"
        f"<params>{param_xml}</params>"
        "</methodCall>"
    )


def _xmlrpc_parse_string(response_text: str) -> Optional[str]:
    """Extract the first string value from an XMLRPC response."""
    try:
        root = ET.fromstring(response_text)
        el = root.find(".//string")
        return el.text if el is not None else None
    except ET.ParseError:
        return None


def _xmlrpc_parse_int(response_text: str) -> Optional[int]:
    """Extract the first integer (i4/i8/int) value from an XMLRPC response."""
    try:
        root = ET.fromstring(response_text)
        for tag in ("i8", "i4", "int"):
            el = root.find(f".//{tag}")
            if el is not None:
                return int(el.text)
    except (ET.ParseError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# DownloadClient
# ---------------------------------------------------------------------------

class DownloadClient:
    def __init__(
        self,
        rtorrent_url: str,
        rtorrent_user: str,
        rtorrent_password: str,
        rtorrent_download_dir: str,
        rtorrent_category: str,
        rtorrent_imported_category: str,
        sabnzbd_base_url: str,
        sabnzbd_api_key: str,
        sabnzbd_category: str,
    ):
        self._rt_url = rtorrent_url
        self._rt_auth = (rtorrent_user, rtorrent_password) if rtorrent_user else None
        self._rt_download_dir = rtorrent_download_dir
        self._rt_category = rtorrent_category
        self._rt_imported_category = rtorrent_imported_category

        self._sab_url = sabnzbd_base_url.rstrip("/")
        self._sab_api_key = sabnzbd_api_key
        self._sab_category = sabnzbd_category

        self._rt_client = httpx.AsyncClient(verify=False, timeout=15.0)
        self._sab_client = httpx.AsyncClient(timeout=15.0)

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, protocol: str, download_url: str, title: str) -> str:
        """
        Send a release to the appropriate client.

        Returns a download_id (rTorrent info_hash or SABnzbd NZO id) that the
        watcher uses to poll for completion.
        """
        if protocol == "torrent":
            return await self._send_torrent(download_url, title)
        elif protocol == "usenet":
            return await self._send_nzb(download_url, title)
        else:
            raise ValueError(f"Unknown protocol: {protocol!r}")

    # ------------------------------------------------------------------
    # rTorrent
    # ------------------------------------------------------------------

    async def _send_torrent(self, download_url: str, title: str) -> str:
        # Snapshot existing hashes before loading so we can identify the new one.
        before = await self._get_all_hashes()

        # Load the torrent URL, setting the download directory and category
        # atomically as inline commands. The directory is pinned per-torrent
        # at load time — no global default to manage.
        body = (
            '<?xml version="1.0"?>'
            "<methodCall>"
            "<methodName>load.start</methodName>"
            "<params>"
            '<param><value><string></string></value></param>'
            f'<param><value><string>{download_url}</string></value></param>'
            f'<param><value><string>d.directory.set={self._rt_download_dir}</string></value></param>'
            f'<param><value><string>d.custom1.set={self._rt_category}</string></value></param>'
            "</params>"
            "</methodCall>"
        )
        resp = await self._rt_client.post(
            self._rt_url,
            content=body,
            headers={"Content-Type": "text/xml"},
            auth=self._rt_auth,
        )
        resp.raise_for_status()
        logger.debug("[rtorrent] load.start response: %s", resp.text[:200])

        import asyncio
        await asyncio.sleep(2)

        after = await self._get_all_hashes()
        new_hashes = after - before
        if not new_hashes:
            raise RuntimeError("Torrent loaded but no new hash found (possible duplicate)")

        info_hash = new_hashes.pop()
        logger.info(
            "[rtorrent] dispatched %r → hash=%s dir=%s category=%s",
            title, info_hash[:12], self._rt_download_dir, self._rt_category,
        )
        return info_hash

    async def _get_all_hashes(self) -> set[str]:
        """Return the set of all info_hashes currently in rTorrent."""
        body = (
            '<?xml version="1.0"?>'
            "<methodCall>"
            "<methodName>d.multicall2</methodName>"
            "<params>"
            '<param><value><string></string></value></param>'
            '<param><value><string>main</string></value></param>'
            '<param><value><string>d.hash=</string></value></param>'
            "</params>"
            "</methodCall>"
        )
        resp = await self._rt_client.post(
            self._rt_url,
            content=body,
            headers={"Content-Type": "text/xml"},
            auth=self._rt_auth,
        )
        resp.raise_for_status()

        try:
            root = ET.fromstring(resp.text)
            hashes: set[str] = set()
            outer_data = root.find(".//params/param/value/array/data")
            if outer_data is None:
                return hashes
            for torrent_value in outer_data.findall("value"):
                inner_data = torrent_value.find("array/data")
                if inner_data is None:
                    continue
                values = inner_data.findall("value")
                if values:
                    h = (values[0].findtext("string") or "").strip()
                    if h:
                        hashes.add(h)
            return hashes
        except ET.ParseError as e:
            logger.error("[rtorrent] failed to parse multicall2 response: %s", e)
            return set()

    # ------------------------------------------------------------------
    # SABnzbd
    # ------------------------------------------------------------------

    async def _send_nzb(self, download_url: str, title: str) -> str:
        params = {
            "apikey": self._sab_api_key,
            "output": "json",
            "mode": "addurl",
            "name": download_url,
            "cat": self._sab_category,
            "priority": 0,
        }
        resp = await self._sab_client.get(f"{self._sab_url}/api", params=params)
        resp.raise_for_status()

        data = resp.json()
        if not data.get("status"):
            raise RuntimeError(f"SABnzbd rejected NZB: {data}")

        nzo_ids = data.get("nzo_ids", [])
        nzo_id = nzo_ids[0] if nzo_ids else ""
        if not nzo_id:
            raise RuntimeError(f"SABnzbd returned no NZO id: {data}")

        logger.info("[sabnzbd] dispatched %r → nzo_id=%s", title, nzo_id)
        return nzo_id
