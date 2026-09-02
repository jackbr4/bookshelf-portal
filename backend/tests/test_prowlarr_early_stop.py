"""
Unit tests for the fallback-query early stop in ProwlarrClient.search_releases:
once a query yields EARLY_STOP_ACCEPTED accepted releases, remaining fallback
queries are skipped — halving indexer load for well-known titles.
"""
import asyncio
from unittest.mock import AsyncMock

from app.prowlarr_client import ProwlarrClient, EARLY_STOP_ACCEPTED, _build_queries


def _raw_item(n: int) -> dict:
    # epub from a trusted indexer, comfortably over minimum size → accepted
    return {
        "guid": f"guid-{n}",
        "title": f"Some Book {n} EPUB",
        "size": 2_000_000,
        "indexer": "MyAnonamouse",
        "protocol": "torrent",
        "seeders": 10,
        "age": 100,
        "downloadUrl": "http://prowlarr/dl",
    }


def _client_with_batches(*batches: list[dict]) -> ProwlarrClient:
    client = ProwlarrClient(base_url="http://localhost:29254", api_key="x")
    responses = []
    for batch in batches:
        resp = AsyncMock()
        resp.is_success = True
        resp.json = lambda b=batch: b
        responses.append(resp)
    client._client.get = AsyncMock(side_effect=responses)
    return client


def test_build_queries_primary_then_title_fallback():
    assert _build_queries("Dune", "Frank Herbert") == ["Dune Frank Herbert", "Dune"]
    assert _build_queries("Dune", "") == ["Dune"]


def test_skips_fallback_when_first_query_has_enough_accepted():
    first = [_raw_item(i) for i in range(EARLY_STOP_ACCEPTED)]
    client = _client_with_batches(first, [_raw_item(99)])
    accepted, rejected = asyncio.run(client.search_releases("Dune", "Frank Herbert"))

    assert client._client.get.await_count == 1
    assert len(accepted) == EARLY_STOP_ACCEPTED


def test_runs_fallback_when_first_query_is_thin():
    first = [_raw_item(1)]
    second = [_raw_item(i) for i in range(10, 20)]
    client = _client_with_batches(first, second)
    accepted, rejected = asyncio.run(client.search_releases("Obscure Title", "Nobody"))

    assert client._client.get.await_count == 2
    assert len(accepted) == 11


def test_rejected_results_do_not_trigger_early_stop():
    # Plenty of results, but all rejected (mobi-only) → fallback still runs.
    first = [
        {**_raw_item(i), "title": f"Some Book {i} MOBI"}
        for i in range(EARLY_STOP_ACCEPTED * 2)
    ]
    client = _client_with_batches(first, [_raw_item(99)])
    accepted, rejected = asyncio.run(client.search_releases("Dune", "Frank Herbert"))

    assert client._client.get.await_count == 2
    assert len(accepted) == 1


def test_single_query_never_early_stops_short():
    # Author-less search builds one query; result should just be processed.
    batch = [_raw_item(i) for i in range(EARLY_STOP_ACCEPTED + 3)]
    client = _client_with_batches(batch)
    accepted, _ = asyncio.run(client.search_releases("Dune", ""))

    assert client._client.get.await_count == 1
    assert len(accepted) == EARLY_STOP_ACCEPTED + 3
