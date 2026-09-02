"""
MAM slot-status service — cached view of unsatisfied-torrent usage plus the
dispatch guard that keeps the account clear of MAM's 150-unsatisfied cap.

MAM (VIP class) blocks the account for 24 hours if a download is requested
while at the cap, so the guard refuses torrent dispatches at a configurable
threshold below the real limit and fails CLOSED when the status cannot be
verified.  Usenet dispatches never count against MAM and are never blocked.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30.0


class MamStatusService:
    def __init__(
        self,
        download_client,
        limit: int,
        block_threshold: int,
        mock_mode: bool = False,
        mock_exhausted: bool = False,
    ):
        self._client = download_client
        self._limit = limit
        self._threshold = block_threshold
        self._mock_mode = mock_mode
        self._mock_exhausted = mock_exhausted
        self._cached: Optional[dict] = None
        self._cached_at: float = 0.0

    async def get_status(self) -> dict:
        """
        Return the current slot status:
            {
              "unsatisfied": int | None,   # None = cannot verify
              "limit": int,
              "block_threshold": int,
              "slots_free": int | None,    # relative to block_threshold
              "blocked": bool,             # torrent dispatch would be refused
              "next_free_at": int | None,  # unix ts of earliest slot free-up
              "server_time": int,
            }
        Cached for CACHE_TTL_SECONDS to avoid hammering rTorrent XMLRPC.
        """
        now = time.time()
        if self._cached is None or (now - self._cached_at) > CACHE_TTL_SECONDS:
            self._cached = await self._fetch()
            self._cached_at = now
        return self._render(self._cached)

    def note_torrent_dispatched(self) -> None:
        """
        Bump the cached unsatisfied count after a successful torrent dispatch
        so bursts within one cache window can't overshoot the threshold.
        """
        if self._cached and self._cached.get("unsatisfied") is not None:
            self._cached["unsatisfied"] += 1

    async def _fetch(self) -> dict:
        if self._mock_mode:
            if self._mock_exhausted:
                return {
                    "unsatisfied": self._limit,
                    "next_free_at": int(time.time()) + 2 * 3600 + 14 * 60,
                }
            return {"unsatisfied": 143, "next_free_at": int(time.time()) + 5 * 3600}
        return await self._client.get_mam_slot_status()

    def _render(self, raw: dict) -> dict:
        unsatisfied = raw.get("unsatisfied")
        if unsatisfied is None:
            slots_free = None
            blocked = True  # fail closed
        else:
            slots_free = max(0, self._threshold - unsatisfied)
            blocked = unsatisfied >= self._threshold
        return {
            "unsatisfied": unsatisfied,
            "limit": self._limit,
            "block_threshold": self._threshold,
            "slots_free": slots_free,
            "blocked": blocked,
            "next_free_at": raw.get("next_free_at"),
            "server_time": int(time.time()),
        }
