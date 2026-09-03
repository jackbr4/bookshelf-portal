"""
Integration tests — run against the live container on localhost:8788.

Requires APP_PASSWORD env var (extracted from .env in the deploy script).
Does NOT make real Prowlarr searches or dispatch real downloads.
"""
import os
from contextlib import contextmanager

import httpx
import pytest

BASE = "http://localhost:8788"
PASSWORD = os.environ.get("APP_PASSWORD", "changeme")
PROWLARR_BASE = "http://localhost:29254"


@contextmanager
def _authed_client():
    with httpx.Client(base_url=BASE) as client:
        r = client.post("/portal/auth", json={"access_code": PASSWORD})
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        yield client


# ── Public endpoints ──────────────────────────────────────────────────────────

def test_health():
    r = httpx.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_portal_redirects_to_request():
    r = httpx.get(f"{BASE}/portal", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/request")


def test_portal_test_redirects():
    r = httpx.get(f"{BASE}/portal/test", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/request")


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_auth_wrong_password():
    r = httpx.post(f"{BASE}/portal/auth", json={"access_code": "notthepassword"})
    assert r.status_code == 401


def test_auth_correct_password():
    r = httpx.post(f"{BASE}/portal/auth", json={"access_code": PASSWORD})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "session_token" in r.cookies


def test_logout():
    with _authed_client() as client:
        r = client.post("/portal/logout")
        assert r.status_code == 200


# ── Protected endpoints reject unauthenticated requests ───────────────────────

@pytest.mark.parametrize("method,path,kwargs", [
    ("GET",  "/portal/releases", {"params": {"title": "test"}}),
    ("GET",  "/portal/history",  {}),
    ("POST", "/portal/download", {"json": {
        "title": "t", "author": "a", "release_title": "t",
        "indexer": "i", "protocol": "torrent",
        "download_url": "http://example.com/bad",
    }}),
])
def test_unauthenticated_returns_401(method, path, kwargs):
    r = httpx.request(method, f"{BASE}{path}", **kwargs)
    assert r.status_code == 401


# ── Security: authenticated but invalid requests ──────────────────────────────

def test_download_ssrf_rejected():
    """Non-Prowlarr download_url must be rejected even when authenticated."""
    with _authed_client() as client:
        r = client.post("/portal/download", json={
            "title": "t", "author": "a", "release_title": "t",
            "indexer": "i", "protocol": "torrent",
            "download_url": "http://evil.example.com/file.torrent",
        })
    assert r.status_code == 400


def test_download_bad_protocol_rejected():
    """Invalid protocol must be rejected (SSRF check passes, protocol check fails)."""
    with _authed_client() as client:
        r = client.post("/portal/download", json={
            "title": "t", "author": "a", "release_title": "t",
            "indexer": "i", "protocol": "ftp",
            "download_url": f"{PROWLARR_BASE}/dl/test.torrent",
        })
    assert r.status_code == 400
