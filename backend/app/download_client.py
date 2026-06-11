"""
Download dispatcher — sends releases to rTorrent (XMLRPC), qBittorrent (Web
API), or SABnzbd (API).

Torrent client is selected via settings.torrent_client ("rtorrent" or
"qbittorrent").  SABnzbd handles all usenet (NZB) dispatches regardless.
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
        torrent_client: str,
        rtorrent_url: str,
        rtorrent_user: str,
        rtorrent_password: str,
        rtorrent_download_dir: str,
        rtorrent_category: str,
        rtorrent_imported_category: str,
        qbittorrent_url: str,
        qbittorrent_user: str,
        qbittorrent_password: str,
        qbittorrent_download_dir: str,
        qbittorrent_category: str,
        qbittorrent_imported_category: str,
        sabnzbd_base_url: str,
        sabnzbd_api_key: str,
        sabnzbd_category: str,
    ):
        self._torrent_client = torrent_client.lower()

        self._rt_url = rtorrent_url
        self._rt_auth = (rtorrent_user, rtorrent_password) if rtorrent_user else None
        self._rt_download_dir = rtorrent_download_dir
        self._rt_category = rtorrent_category
        self._rt_imported_category = rtorrent_imported_category

        self._qbt_url = qbittorrent_url.rstrip("/")
        self._qbt_user = qbittorrent_user
        self._qbt_password = qbittorrent_password
        self._qbt_download_dir = qbittorrent_download_dir
        self._qbt_category = qbittorrent_category
        self._qbt_imported_category = qbittorrent_imported_category

        self._sab_url = sabnzbd_base_url.rstrip("/")
        self._sab_api_key = sabnzbd_api_key
        self._sab_category = sabnzbd_category

        self._rt_client = httpx.AsyncClient(verify=False, timeout=15.0)
        self._qbt_client = httpx.AsyncClient(timeout=15.0)
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
            if self._torrent_client == "qbittorrent":
                return await self._send_qbittorrent(download_url, title)
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

    async def count_mam_unsatisfied(self) -> int:
        """
        Count rTorrent torrents from MyAnonamouse that haven't yet satisfied the
        72-hour seeding requirement (still downloading OR seeded < 72 h).

        Returns 0 if rTorrent is unreachable so the caller can still attempt
        dispatches (which will fail on their own if rTorrent is down).
        """
        if self._torrent_client != "rtorrent":
            return 0

        # d.tracker_url= silently breaks d.multicall2 on this rTorrent build.
        # Instead we identify MAM torrents by the category label our dispatcher
        # sets (d.custom1): "books" while downloading, "books-imported" after
        # the watcher moves the file into Calibre.  Both count against MAM's limit.
        body = (
            '<?xml version="1.0"?>'
            "<methodCall>"
            "<methodName>d.multicall2</methodName>"
            "<params>"
            '<param><value><string></string></value></param>'
            '<param><value><string>main</string></value></param>'
            '<param><value><string>d.timestamp.finished=</string></value></param>'
            '<param><value><string>d.custom1=</string></value></param>'
            "</params>"
            "</methodCall>"
        )
        try:
            resp = await self._rt_client.post(
                self._rt_url,
                content=body,
                headers={"Content-Type": "text/xml"},
                auth=self._rt_auth,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[rtorrent] failed to query MAM slot count: %s", exc)
            return 0

        import time
        now = time.time()
        unsatisfied = 0

        def _int_val(el) -> int:
            for tag in ("i8", "i4", "int"):
                v = el.findtext(tag)
                if v is not None:
                    return int(v)
            return 0

        try:
            root = ET.fromstring(resp.text)
            outer_data = root.find(".//params/param/value/array/data")
            if outer_data is None:
                return 0
            for torrent_val in outer_data.findall("value"):
                inner_data = torrent_val.find("array/data")
                if inner_data is None:
                    continue
                fields = inner_data.findall("value")
                if len(fields) < 2:
                    continue
                label = (fields[1].findtext("string") or "").strip()
                if label not in (self._rt_category, self._rt_imported_category):
                    continue
                finished_at = _int_val(fields[0])
                seeding_seconds = (now - finished_at) if finished_at > 0 else 0
                if seeding_seconds < 72 * 3600:
                    unsatisfied += 1
        except (ET.ParseError, ValueError) as exc:
            logger.warning("[rtorrent] failed to parse MAM slot response: %s", exc)
            return 0

        logger.info("[rtorrent] MAM unsatisfied torrents: %d", unsatisfied)
        return unsatisfied

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
    # qBittorrent
    # ------------------------------------------------------------------

    async def _qbt_login(self) -> str:
        """Login to qBittorrent Web UI and return the SID cookie value."""
        resp = await self._qbt_client.post(
            f"{self._qbt_url}/api/v2/auth/login",
            data={"username": self._qbt_user, "password": self._qbt_password},
        )
        resp.raise_for_status()
        if resp.text.strip() != "Ok.":
            raise RuntimeError(f"qBittorrent login failed: {resp.text!r}")
        sid = resp.cookies.get("SID")
        if not sid:
            raise RuntimeError("qBittorrent login returned no SID cookie")
        return sid

    async def _qbt_get_hashes(self, sid: str) -> set[str]:
        resp = await self._qbt_client.get(
            f"{self._qbt_url}/api/v2/torrents/info",
            cookies={"SID": sid},
        )
        resp.raise_for_status()
        return {t["hash"] for t in resp.json()}

    async def _send_qbittorrent(self, download_url: str, title: str) -> str:
        sid = await self._qbt_login()
        before = await self._qbt_get_hashes(sid)

        resp = await self._qbt_client.post(
            f"{self._qbt_url}/api/v2/torrents/add",
            cookies={"SID": sid},
            data={
                "urls": download_url,
                "savepath": self._qbt_download_dir,
                "category": self._qbt_category,
            },
        )
        resp.raise_for_status()
        if resp.text.strip() not in ("Ok.", "Fails."):
            pass  # some versions return empty body on success
        if resp.text.strip() == "Fails.":
            raise RuntimeError(f"qBittorrent rejected torrent: {download_url!r}")

        import asyncio
        await asyncio.sleep(2)

        after = await self._qbt_get_hashes(sid)
        new_hashes = after - before
        if not new_hashes:
            raise RuntimeError("Torrent loaded but no new hash found (possible duplicate)")

        info_hash = new_hashes.pop()
        logger.info(
            "[qbittorrent] dispatched %r → hash=%s dir=%s category=%s",
            title, info_hash[:12], self._qbt_download_dir, self._qbt_category,
        )
        return info_hash

    async def get_seeding_info(self) -> list[dict]:
        """Return [{hash, finished_at}] for rTorrent torrents in the imported category."""
        if self._torrent_client != "rtorrent":
            return []
        body = (
            '<?xml version="1.0"?>'
            "<methodCall>"
            "<methodName>d.multicall2</methodName>"
            "<params>"
            '<param><value><string></string></value></param>'
            '<param><value><string>main</string></value></param>'
            '<param><value><string>d.hash=</string></value></param>'
            '<param><value><string>d.custom1=</string></value></param>'
            '<param><value><string>d.complete=</string></value></param>'
            '<param><value><string>d.timestamp.finished=</string></value></param>'
            "</params>"
            "</methodCall>"
        )
        try:
            resp = await self._rt_client.post(
                self._rt_url,
                content=body,
                headers={"Content-Type": "text/xml"},
                auth=self._rt_auth,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[rtorrent] get_seeding_info failed: %s", exc)
            return []

        items: list[dict] = []
        try:
            root = ET.fromstring(resp.text)
            outer_data = root.find(".//params/param/value/array/data")
            if outer_data is None:
                return []
            for torrent_val in outer_data.findall("value"):
                inner_data = torrent_val.find("array/data")
                if inner_data is None:
                    continue
                fields = inner_data.findall("value")
                if len(fields) < 4:
                    continue
                h = (fields[0].findtext("string") or "").strip()
                label = (fields[1].findtext("string") or "").strip()
                complete = 0
                for tag in ("i8", "i4", "int"):
                    el = fields[2].find(tag)
                    if el is not None:
                        complete = int(el.text)
                        break
                finished_at = 0
                for tag in ("i8", "i4", "int"):
                    el = fields[3].find(tag)
                    if el is not None:
                        finished_at = int(el.text)
                        break
                if h and label == self._rt_imported_category and complete == 1:
                    items.append({"hash": h, "finished_at": finished_at})
        except (ET.ParseError, ValueError) as exc:
            logger.warning("[rtorrent] failed to parse seeding info: %s", exc)
        return items

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
