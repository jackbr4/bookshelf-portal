"""
Direct Prowlarr client for release search.

Queries /api/v1/search with the book title + author, applies the release
filter, and returns scored results ready for the UI.
"""

import logging
import re
import time
from typing import Optional

import httpx

from .release_filter import (
    extract_formats,
    best_format,
    filter_release,
    score_release,
)

logger = logging.getLogger(__name__)


class ReleaseResult:
    """Structured release from Prowlarr, after filtering and scoring."""

    __slots__ = (
        "guid", "title", "indexer", "indexer_id", "protocol",
        "size_bytes", "size_mb", "detected_format", "seeders", "leechers",
        "age_days", "download_url", "publish_date", "score",
        "rejected", "reject_reason",
    )

    def __init__(self, raw: dict, detected_format: Optional[str], score: int):
        self.guid = raw.get("guid", "")
        self.title = raw.get("title", "")
        self.indexer = raw.get("indexer", "")
        self.indexer_id = raw.get("indexerId")
        self.protocol = raw.get("protocol", "")
        self.size_bytes = raw.get("size", 0) or 0
        self.size_mb = round(self.size_bytes / 1024 / 1024, 1)
        self.detected_format = detected_format
        self.seeders = raw.get("seeders")
        self.leechers = raw.get("leechers")
        self.age_days = raw.get("age")
        self.download_url = raw.get("downloadUrl", "")
        self.publish_date = raw.get("publishDate")
        self.score = score
        self.rejected = False
        self.reject_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "guid": self.guid,
            "title": self.title,
            "indexer": self.indexer,
            "protocol": self.protocol,
            "size_mb": self.size_mb,
            "detected_format": self.detected_format,
            "seeders": self.seeders,
            "age_days": self.age_days,
            "download_url": self.download_url,
            "publish_date": self.publish_date,
            "score": self.score,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
        }


# Stop issuing fallback queries once this many accepted releases are found.
EARLY_STOP_ACCEPTED = 5

# How long a (title, author, content_type) search result is reused before a
# fresh Prowlarr/MAM query is made. Book listicles frequently repeat the
# same classics, and duplicate/near-duplicate lookups are common within one
# import — this makes those instant instead of re-querying MAM, cutting
# both latency and indexer load for the exact case that motivated it.
_CACHE_TTL_SECONDS = 600
# Prune expired entries once the cache grows past this size, so a long-running
# process doesn't accumulate stale entries indefinitely.
_CACHE_MAX_ENTRIES = 500


def _cache_key_part(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


class ProwlarrClient:
    def __init__(self, base_url: str, api_key: str, clock=time.monotonic):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Api-Key": self.api_key},
            timeout=30.0,
        )
        self._cache: dict[tuple[str, str, str], tuple[float, tuple[list[ReleaseResult], list[ReleaseResult]]]] = {}
        # Injectable so tests can control cache expiry without touching the
        # real clock (asyncio's own scheduling also reads time.monotonic,
        # so patching it globally in tests is not safe).
        self._clock = clock

    async def search_releases(
        self, title: str, author: str, content_type: str = "ebook"
    ) -> tuple[list[ReleaseResult], list[ReleaseResult]]:
        """
        Search Prowlarr for releases matching title + author, cached for
        _CACHE_TTL_SECONDS per (title, author, content_type).

        content_type: "ebook" (default) or "audiobook" — controls categories and filtering.
        Returns (accepted, rejected) — both lists are sorted by score descending.
        Rejected entries include a reject_reason for UI display.
        """
        key = (_cache_key_part(title), _cache_key_part(author), content_type)
        cached = self._cache.get(key)
        if cached is not None:
            cached_at, result = cached
            if self._clock() - cached_at < _CACHE_TTL_SECONDS:
                logger.info("[prowlarr] cache hit: title=%r author=%r (%s)", title, author, content_type)
                return result
            del self._cache[key]

        result = await self._search_releases_uncached(title, author, content_type)
        self._cache[key] = (self._clock(), result)
        if len(self._cache) > _CACHE_MAX_ENTRIES:
            self._prune_expired()
        return result

    def _prune_expired(self) -> None:
        now = self._clock()
        expired = [k for k, (cached_at, _) in self._cache.items() if now - cached_at >= _CACHE_TTL_SECONDS]
        for k in expired:
            del self._cache[k]

    async def _search_releases_uncached(
        self, title: str, author: str, content_type: str = "ebook"
    ) -> tuple[list[ReleaseResult], list[ReleaseResult]]:
        if content_type == "audiobook":
            categories = [("categories", 3030), ("categories", 100013)]
        else:
            categories = [("categories", 7020), ("categories", 107020)]

        queries = _build_queries(title, author)
        raw_results: list[dict] = []
        seen_guids: set[str] = set()
        accepted: list[ReleaseResult] = []
        rejected: list[ReleaseResult] = []

        for i, query in enumerate(queries):
            try:
                logger.info("[prowlarr] searching (%s): %r", content_type, query)
                resp = await self._client.get(
                    "/api/v1/search",
                    params=[
                        ("query", query),
                        ("type", "search"),
                        ("limit", 100),
                    ] + categories,
                )
                if not resp.is_success:
                    logger.warning("[prowlarr] search returned %s for %r", resp.status_code, query)
                    continue

                batch = resp.json()
                if not isinstance(batch, list):
                    continue

                added = 0
                for item in batch:
                    guid = item.get("guid", "")
                    if guid and guid not in seen_guids:
                        seen_guids.add(guid)
                        raw_results.append(item)
                        added += 1

                logger.info("[prowlarr] query %r → %d new results (%d total)", query, added, len(raw_results))

            except httpx.RequestError as e:
                logger.warning("[prowlarr] request error for %r: %s", query, e)

            accepted, rejected = self._process(raw_results, content_type=content_type)
            # Fallback queries only rescue books the primary query missed —
            # skip them once we have enough accepted candidates, halving
            # indexer load and latency for well-known titles.
            if len(accepted) >= EARLY_STOP_ACCEPTED and i + 1 < len(queries):
                logger.info(
                    "[prowlarr] %d accepted after %r — skipping %d fallback quer%s",
                    len(accepted), query, len(queries) - i - 1,
                    "y" if len(queries) - i - 1 == 1 else "ies",
                )
                break

        return accepted, rejected

    def _process(
        self, raw: list[dict], content_type: str = "ebook"
    ) -> tuple[list[ReleaseResult], list[ReleaseResult]]:
        accepted: list[ReleaseResult] = []
        rejected: list[ReleaseResult] = []

        for item in raw:
            title = item.get("title", "")
            size = item.get("size", 0) or 0
            indexer = item.get("indexer", "")
            formats = extract_formats(title)
            result = filter_release(title, size, formats, indexer, content_type=content_type)

            fmt = result.detected_format or best_format(formats, content_type)
            release = ReleaseResult(
                raw=item,
                detected_format=fmt,
                score=score_release(
                    detected_format=fmt,
                    indexer=item.get("indexer", ""),
                    seeders=item.get("seeders"),
                    size_bytes=size,
                    age_days=item.get("age"),
                    content_type=content_type,
                ) if result.accepted else 0,
            )

            if result.accepted:
                accepted.append(release)
            else:
                release.rejected = True
                release.reject_reason = result.reason
                rejected.append(release)

        accepted.sort(key=lambda r: r.score, reverse=True)
        rejected.sort(key=lambda r: r.title)

        logger.info(
            "[prowlarr] processed %d results → %d accepted, %d rejected",
            len(raw), len(accepted), len(rejected),
        )
        return accepted, rejected


def _build_queries(title: str, author: str) -> list[str]:
    """
    Return 1-2 query strings to try. More queries = more results but slower.

    Both title and author are optional; at least one must be non-empty.
    Primary:   "Title Author" — most specific, best relevance
    Fallback:  "Title" alone — catches releases that omit the author name
               "Author" alone — when only author is provided
    """
    title = title.strip()
    author = author.strip()

    queries = []
    if title and author:
        queries.append(f"{title} {author}")
    if title:
        queries.append(title)
    elif author:
        queries.append(author)
    return queries
