"""
Unit tests for the search_releases result cache in ProwlarrClient: repeat
lookups within the TTL are served from cache (no new HTTP calls / MAM hits),
expired entries are refetched, and cache keys are per (title, author,
content_type) with whitespace/case-insensitive matching on title/author.
"""
import asyncio
from unittest.mock import AsyncMock

from app.prowlarr_client import ProwlarrClient, EARLY_STOP_ACCEPTED, _CACHE_TTL_SECONDS, _CACHE_MAX_ENTRIES


def _raw_item(n, fmt="EPUB") -> dict:
    return {
        "guid": f"guid-{n}",
        "title": f"Some Book {n} {fmt}",
        "size": 2_000_000,
        "indexer": "MyAnonamouse",
        "protocol": "torrent",
        "seeders": 10,
        "age": 100,
        "downloadUrl": "http://prowlarr/dl",
    }


def _enough_batch(prefix="", content_type="ebook") -> list[dict]:
    """A batch with enough accepted items (in the right format for
    content_type) to trip the early stop, so a single search_releases() call
    makes exactly one HTTP request."""
    fmt = "M4B" if content_type == "audiobook" else "EPUB"
    return [_raw_item(f"{prefix}{i}", fmt) for i in range(EARLY_STOP_ACCEPTED)]


class _FakeClock:
    """Manually-advanced clock so cache-expiry tests don't touch the real
    time.monotonic — asyncio's own scheduling reads that too."""
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _client_with_batches(*batches: list[dict], clock=None) -> ProwlarrClient:
    client = ProwlarrClient(base_url="http://localhost:29254", api_key="x", clock=clock or (lambda: 0.0))
    responses = []
    for batch in batches:
        resp = AsyncMock()
        resp.is_success = True
        resp.json = lambda b=batch: b
        responses.append(resp)
    client._client.get = AsyncMock(side_effect=responses)
    return client


def test_repeat_lookup_within_ttl_is_served_from_cache():
    client = _client_with_batches(_enough_batch())
    a1, _ = asyncio.run(client.search_releases("Dune", "Frank Herbert"))
    a2, _ = asyncio.run(client.search_releases("Dune", "Frank Herbert"))

    assert client._client.get.await_count == 1
    assert a1 == a2


def test_cache_key_is_case_and_whitespace_insensitive():
    client = _client_with_batches(_enough_batch())
    asyncio.run(client.search_releases("  Dune ", "Frank Herbert"))
    asyncio.run(client.search_releases("dune", "  frank  herbert  "))

    assert client._client.get.await_count == 1


def test_different_content_type_is_a_cache_miss():
    client = _client_with_batches(_enough_batch("eb-", "ebook"), _enough_batch("ab-", "audiobook"))
    asyncio.run(client.search_releases("Dune", "Frank Herbert", content_type="ebook"))
    asyncio.run(client.search_releases("Dune", "Frank Herbert", content_type="audiobook"))

    assert client._client.get.await_count == 2


def test_different_book_is_a_cache_miss():
    client = _client_with_batches(_enough_batch("a-"), _enough_batch("b-"))
    asyncio.run(client.search_releases("Dune", "Frank Herbert"))
    asyncio.run(client.search_releases("1984", "George Orwell"))

    assert client._client.get.await_count == 2


def test_expired_entry_triggers_a_fresh_query():
    clock = _FakeClock()
    client = _client_with_batches(_enough_batch("a-"), _enough_batch("b-"), clock=clock)
    asyncio.run(client.search_releases("Dune", "Frank Herbert"))
    clock.advance(_CACHE_TTL_SECONDS + 1)
    asyncio.run(client.search_releases("Dune", "Frank Herbert"))

    assert client._client.get.await_count == 2


def test_entry_still_fresh_just_under_ttl_is_a_cache_hit():
    clock = _FakeClock()
    client = _client_with_batches(_enough_batch(), clock=clock)
    asyncio.run(client.search_releases("Dune", "Frank Herbert"))
    clock.advance(_CACHE_TTL_SECONDS - 1)
    asyncio.run(client.search_releases("Dune", "Frank Herbert"))

    assert client._client.get.await_count == 1


def test_cache_prunes_expired_entries_once_it_grows_large():
    clock = _FakeClock()
    client = _client_with_batches(
        *[_enough_batch(f"{i}-") for i in range(_CACHE_MAX_ENTRIES + 1)], clock=clock
    )
    # First entry cached "long ago"; everything else cached "now" — once the
    # prune trigger fires, the stale one should be gone, the fresh ones kept.
    asyncio.run(client.search_releases("Book 0", ""))
    clock.advance(_CACHE_TTL_SECONDS + 1)
    for i in range(1, _CACHE_MAX_ENTRIES + 1):
        asyncio.run(client.search_releases(f"Book {i}", ""))

    assert ("book 0", "", "ebook") not in client._cache
    assert len(client._cache) <= _CACHE_MAX_ENTRIES
