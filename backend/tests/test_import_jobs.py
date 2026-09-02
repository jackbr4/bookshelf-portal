"""
Unit tests for ResolveJobStore: background resolution, progress reporting,
status classification, per-book error isolation, concurrency bound,
cancellation, TTL expiry and mock mode.  No live services required.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.import_jobs import ResolveJobStore, RESOLVE_CONCURRENCY, _status_for
from app.models import ImportBookInput, ReleaseItem, ReleasesResponse


def _release(guid="g1", protocol="torrent") -> ReleaseItem:
    return ReleaseItem(
        guid=guid, title="Dune [EPUB]", indexer="MAM", protocol=protocol,
        size_mb=1.2, download_url="http://prowlarr/x", score=50,
    )


def _resolver(side_effect=None, return_value=None) -> MagicMock:
    r = MagicMock()
    r.resolve_book = AsyncMock(side_effect=side_effect, return_value=return_value or ReleasesResponse())
    return r


def _books(*titles: str) -> list[ImportBookInput]:
    return [ImportBookInput(title=t, author="Someone") for t in titles]


async def _wait_done(store: ResolveJobStore, job_id: str, timeout: float = 5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        job = store.get(job_id)
        assert job is not None, "job vanished"
        if job.done:
            return job
        assert asyncio.get_event_loop().time() < deadline, "job did not finish in time"
        await asyncio.sleep(0.01)


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------

def test_status_for_prefers_in_library_then_available():
    assert _status_for(ReleasesResponse()) == "not_found"
    assert _status_for(ReleasesResponse(ebook_accepted=[_release()])) == "available"
    assert _status_for(ReleasesResponse(audiobook_accepted=[_release()])) == "available"
    # Rejected-only results are not "available"
    assert _status_for(ReleasesResponse(ebook_rejected=[_release()])) == "not_found"
    assert _status_for(ReleasesResponse(calibre_title="Dune", ebook_accepted=[_release()])) == "in_library"
    assert _status_for(ReleasesResponse(audiobooks_title="Dune")) == "in_library"


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def test_job_resolves_every_book_and_reports_progress():
    async def scenario():
        resolver = _resolver(return_value=ReleasesResponse(ebook_accepted=[_release()]))
        store = ResolveJobStore(resolver)
        job = store.create(_books("A", "B", "C"))

        first = job.status()
        assert first.total == 3 and first.done is False
        assert [r.status for r in first.results] == ["pending", "pending", "pending"]
        assert [r.index for r in first.results] == [0, 1, 2]

        job = await _wait_done(store, job.id)
        final = job.status()
        assert final.done is True and final.completed == 3
        assert all(r.status == "available" for r in final.results)
        assert all(r.releases is not None and len(r.releases.ebook_accepted) == 1 for r in final.results)
        assert [r.title for r in final.results] == ["A", "B", "C"]  # input order preserved
        assert resolver.resolve_book.await_count == 3
        resolver.resolve_book.assert_any_await("A", "Someone")

    asyncio.run(scenario())


def test_one_failing_book_does_not_poison_the_job():
    async def scenario():
        async def resolve(title, author):
            if title == "B":
                raise RuntimeError("Prowlarr exploded")
            return ReleasesResponse(calibre_title=title)

        store = ResolveJobStore(_resolver(side_effect=resolve))
        job = await _wait_done(store, store.create(_books("A", "B", "C")).id)
        by_title = {r.title: r for r in job.status().results}
        assert by_title["A"].status == "in_library"
        assert by_title["C"].status == "in_library"
        assert by_title["B"].status == "error"
        assert "Prowlarr exploded" in by_title["B"].error
        assert by_title["B"].releases is None

    asyncio.run(scenario())


def test_blank_book_is_an_error_without_calling_resolver():
    async def scenario():
        resolver = _resolver()
        store = ResolveJobStore(resolver)
        job = await _wait_done(store, store.create([ImportBookInput(title="  ", author="")]).id)
        item = job.status().results[0]
        assert item.status == "error"
        resolver.resolve_book.assert_not_awaited()

    asyncio.run(scenario())


def test_concurrency_is_bounded():
    async def scenario():
        in_flight = 0
        peak = 0

        async def resolve(title, author):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.02)
            in_flight -= 1
            return ReleasesResponse()

        store = ResolveJobStore(_resolver(side_effect=resolve))
        # Two jobs at once share the same semaphore
        j1 = store.create(_books(*[f"A{i}" for i in range(6)]))
        j2 = store.create(_books(*[f"B{i}" for i in range(6)]))
        await _wait_done(store, j1.id)
        await _wait_done(store, j2.id)
        assert peak == RESOLVE_CONCURRENCY

    asyncio.run(scenario())


def test_cancel_stops_work_and_forgets_the_job():
    async def scenario():
        started = 0

        async def resolve(title, author):
            nonlocal started
            started += 1
            await asyncio.sleep(10)
            return ReleasesResponse()

        store = ResolveJobStore(_resolver(side_effect=resolve))
        job = store.create(_books("A", "B", "C", "D", "E"))
        await asyncio.sleep(0.02)
        assert store.cancel(job.id) is True
        assert store.get(job.id) is None
        assert store.cancel(job.id) is False
        await asyncio.sleep(0.02)
        assert job.task.cancelled()
        # Only the first RESOLVE_CONCURRENCY got through the semaphore before cancel
        assert started == RESOLVE_CONCURRENCY

    asyncio.run(scenario())


def test_expired_jobs_are_purged():
    async def scenario():
        store = ResolveJobStore(_resolver(), ttl=0.05)
        job = await _wait_done(store, store.create(_books("A")).id)
        assert store.get(job.id) is not None
        await asyncio.sleep(0.08)
        assert store.get(job.id) is None

    asyncio.run(scenario())


def test_unknown_job_is_none():
    async def scenario():
        store = ResolveJobStore(_resolver())
        assert store.get("nope") is None

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

def test_mock_mode_produces_a_mix_of_statuses_without_touching_prowlarr():
    async def scenario():
        resolver = _resolver()
        store = ResolveJobStore(resolver, mock_mode=True)
        titles = [f"Mock Book {i}" for i in range(20)]
        job = await _wait_done(store, store.create(_books(*titles)).id, timeout=30)
        statuses = {r.status for r in job.status().results}
        assert statuses >= {"available", "not_found", "in_library", "requested"}
        resolver.resolve_book.assert_not_awaited()
        available = [r for r in job.status().results if r.status == "available"]
        assert available and available[0].releases.ebook_accepted
        # Mock download URLs must pass the /portal/download prowlarr_base_url check
        assert all(rel.download_url.startswith("http://localhost:29254/")
                   for r in available for rel in r.releases.ebook_accepted)

    asyncio.run(scenario())


def test_status_for_requested_ranks_below_in_library_and_above_available():
    from app.models import HistoryMatch
    hm = HistoryMatch(status="downloading", created_at="2026-09-01T10:00:00+00:00")
    assert _status_for(ReleasesResponse(history_match=hm, ebook_accepted=[_release()])) == "requested"
    assert _status_for(ReleasesResponse(history_match=hm)) == "requested"
    assert _status_for(ReleasesResponse(history_match=hm, calibre_title="Dune")) == "in_library"
