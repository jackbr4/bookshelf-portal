"""
Unit tests for the MAM slot guard: XMLRPC parsing in
DownloadClient.get_mam_slot_status and the caching/threshold logic in
MamStatusService.  No live services required.
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

from app.download_client import DownloadClient
from app.mam_status import MamStatusService


def _make_client() -> DownloadClient:
    return DownloadClient(
        torrent_client="rtorrent",
        rtorrent_url="https://localhost/xmlrpc",
        rtorrent_user="u",
        rtorrent_password="p",
        rtorrent_download_dir="/downloads",
        rtorrent_category="books",
        rtorrent_imported_category="books-imported",
        qbittorrent_url="http://localhost:8080",
        qbittorrent_user="",
        qbittorrent_password="",
        qbittorrent_download_dir="/downloads",
        qbittorrent_category="books",
        qbittorrent_imported_category="books-imported",
        sabnzbd_base_url="http://localhost:8080",
        sabnzbd_api_key="",
        sabnzbd_category="books",
    )


def _xmlrpc_response(torrents: list[tuple[int, str]]) -> str:
    """Build a d.multicall2 response: list of (finished_at, label)."""
    rows = "".join(
        "<value><array><data>"
        f"<value><i8>{finished}</i8></value>"
        f"<value><string>{label}</string></value>"
        "</data></array></value>"
        for finished, label in torrents
    )
    return (
        '<?xml version="1.0"?><methodResponse><params><param>'
        f"<value><array><data>{rows}</data></array></value>"
        "</param></params></methodResponse>"
    )


def _status_with_response(text: str) -> dict:
    client = _make_client()
    resp = AsyncMock()
    resp.text = text
    resp.raise_for_status = lambda: None
    with patch.object(client._rt_client, "post", AsyncMock(return_value=resp)):
        return asyncio.run(client.get_mam_slot_status())


# ── get_mam_slot_status parsing ───────────────────────────────────────────────

def test_counts_unsatisfied_and_earliest_free():
    now = int(time.time())
    recent = now - 3600            # seeded 1 h — unsatisfied
    older = now - 10 * 3600        # seeded 10 h — unsatisfied, but earlier finish
    satisfied = now - 80 * 3600    # seeded 80 h — satisfied
    status = _status_with_response(_xmlrpc_response([
        (recent, "books"),
        (older, "books-imported"),
        (satisfied, "books"),
        (now - 50, "movies"),      # other category — ignored
    ]))
    assert status["unsatisfied"] == 2
    assert status["next_free_at"] == older + 72 * 3600


def test_still_downloading_torrents_have_no_eta():
    status = _status_with_response(_xmlrpc_response([
        (0, "books"),
        (0, "books-imported"),
    ]))
    assert status["unsatisfied"] == 2
    assert status["next_free_at"] is None


def test_unreachable_rtorrent_returns_none():
    client = _make_client()
    with patch.object(
        client._rt_client, "post", AsyncMock(side_effect=OSError("connect refused"))
    ):
        status = asyncio.run(client.get_mam_slot_status())
    assert status["unsatisfied"] is None
    assert status["next_free_at"] is None


def test_unparseable_response_returns_none():
    status = _status_with_response("this is not xml")
    assert status["unsatisfied"] is None


def test_count_wrapper_fails_open():
    client = _make_client()
    with patch.object(
        client._rt_client, "post", AsyncMock(side_effect=OSError("down"))
    ):
        assert asyncio.run(client.count_mam_unsatisfied()) == 0


def test_non_rtorrent_client_reports_zero():
    client = _make_client()
    client._torrent_client = "qbittorrent"
    status = asyncio.run(client.get_mam_slot_status())
    assert status == {"unsatisfied": 0, "next_free_at": None}


# ── MamStatusService ──────────────────────────────────────────────────────────

def _service(unsatisfied, next_free_at=None, threshold=145, limit=150):
    client = AsyncMock()
    client.get_mam_slot_status = AsyncMock(
        return_value={"unsatisfied": unsatisfied, "next_free_at": next_free_at}
    )
    return MamStatusService(client, limit=limit, block_threshold=threshold), client


def test_service_open_below_threshold():
    svc, _ = _service(unsatisfied=100)
    status = asyncio.run(svc.get_status())
    assert status["blocked"] is False
    assert status["slots_free"] == 45
    assert status["limit"] == 150
    assert status["block_threshold"] == 145


def test_service_blocked_at_threshold():
    svc, _ = _service(unsatisfied=145, next_free_at=12345)
    status = asyncio.run(svc.get_status())
    assert status["blocked"] is True
    assert status["slots_free"] == 0
    assert status["next_free_at"] == 12345


def test_service_fails_closed_when_unverifiable():
    svc, _ = _service(unsatisfied=None)
    status = asyncio.run(svc.get_status())
    assert status["blocked"] is True
    assert status["unsatisfied"] is None
    assert status["slots_free"] is None


def test_service_caches_within_ttl():
    svc, client = _service(unsatisfied=10)
    asyncio.run(svc.get_status())
    asyncio.run(svc.get_status())
    assert client.get_mam_slot_status.await_count == 1


def test_dispatch_decrements_cached_slots():
    svc, _ = _service(unsatisfied=144)
    assert asyncio.run(svc.get_status())["blocked"] is False
    svc.note_torrent_dispatched()
    assert asyncio.run(svc.get_status())["blocked"] is True


def test_mock_mode_exhausted():
    svc = MamStatusService(
        AsyncMock(), limit=150, block_threshold=145,
        mock_mode=True, mock_exhausted=True,
    )
    status = asyncio.run(svc.get_status())
    assert status["blocked"] is True
    assert status["unsatisfied"] == 150
    assert status["next_free_at"] > time.time()


def test_mock_mode_normal():
    svc = MamStatusService(
        AsyncMock(), limit=150, block_threshold=145, mock_mode=True,
    )
    status = asyncio.run(svc.get_status())
    assert status["blocked"] is False
    assert status["unsatisfied"] == 143
