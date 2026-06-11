import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .settings import settings
from .bookshelf_client import BookshelfClient
from .calibre_library import CalibreLibrary
from .test_page import TEST_PAGE_HTML
from .admin_page import ADMIN_PAGE_HTML
from .history import HistoryDB
from .prowlarr_client import ProwlarrClient
from .download_client import DownloadClient
from .models import (
    AuthRequest, AuthResponse,
    SearchResponse,
    AddBookRequest, AddSeriesRequest, AddResponse,
    ReleaseItem, ReleasesResponse,
    DownloadRequest, DownloadResponse,
    HistoryItem, HistoryResponse,
)
from .auth import get_session, create_session_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Bookshelf Portal")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

calibre_library = CalibreLibrary(library_path=settings.calibre_library_path)

bookshelf = BookshelfClient(
    base_url=settings.bookshelf_base_url,
    api_key=settings.bookshelf_api_key,
    mock_mode=settings.mock_mode,
    google_books_api_key=settings.google_books_api_key,
    calibre_library=calibre_library,
)

history_db = HistoryDB(settings.history_db_path)

prowlarr = ProwlarrClient(
    base_url=settings.prowlarr_base_url,
    api_key=settings.prowlarr_api_key,
)

download_client = DownloadClient(
    torrent_client=settings.torrent_client,
    rtorrent_url=settings.rtorrent_url,
    rtorrent_user=settings.rtorrent_user,
    rtorrent_password=settings.rtorrent_password,
    rtorrent_download_dir=settings.rtorrent_download_dir,
    rtorrent_category=settings.rtorrent_category,
    rtorrent_imported_category=settings.rtorrent_imported_category,
    qbittorrent_url=settings.qbittorrent_url,
    qbittorrent_user=settings.qbittorrent_user,
    qbittorrent_password=settings.qbittorrent_password,
    qbittorrent_download_dir=settings.qbittorrent_download_dir,
    qbittorrent_category=settings.qbittorrent_category,
    qbittorrent_imported_category=settings.qbittorrent_imported_category,
    sabnzbd_base_url=settings.sabnzbd_base_url,
    sabnzbd_api_key=settings.sabnzbd_api_key,
    sabnzbd_category=settings.sabnzbd_category,
)


@app.post("/portal/auth", response_model=AuthResponse)
@limiter.limit("10/minute")
async def auth(request: Request, response: Response, body: AuthRequest):
    if body.access_code != settings.app_password:
        logger.warning("Failed login attempt from %s", request.client.host)
        raise HTTPException(status_code=401, detail="Incorrect access code")

    logger.info("Successful login from %s", request.client.host)
    token, expires_at = create_session_token()
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(settings.session_ttl_hours * 3600),
    )
    return AuthResponse(ok=True, session_token=token, expires_at=expires_at.isoformat())


@app.post("/portal/logout")
async def logout(response: Response):
    response.delete_cookie("session_token")
    return {"ok": True}


@app.get("/portal/search", response_model=SearchResponse)
async def search(q: str, request: Request, session=Depends(get_session)):
    if not q.strip():
        return SearchResponse(books=[], series=[])

    logger.info("Search query: %r", q)
    try:
        results = await bookshelf.search(q.strip())
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search error: %s", e)
        raise HTTPException(status_code=502, detail="Search failed")


@app.post("/portal/request/book", response_model=AddResponse)
async def add_book(body: AddBookRequest, request: Request, session=Depends(get_session)):
    logger.info("Add book: %s", body.book_id)
    try:
        result = await bookshelf.add_book(body.book_id, body.title, body.author, body.foreign_author_id, body.foreign_edition_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("Add book error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to add book: {e}")


@app.post("/portal/request/series", response_model=AddResponse)
async def add_series(body: AddSeriesRequest, request: Request, session=Depends(get_session)):
    logger.info("Add series: %s", body.series_id)
    try:
        result = await bookshelf.add_series(body.series_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Add series error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to add series")


@app.post("/portal/download", response_model=DownloadResponse)
@limiter.limit("20/minute")
async def dispatch_download(body: DownloadRequest, request: Request, session=Depends(get_session)):
    if not body.download_url.startswith(settings.prowlarr_base_url):
        logger.warning("Rejected download_url not from Prowlarr: %s", body.download_url[:80])
        raise HTTPException(status_code=400, detail="Invalid download URL")
    if body.protocol not in ("torrent", "usenet"):
        raise HTTPException(status_code=400, detail="Invalid protocol")
    if body.media_type not in (None, "ebook", "audiobook"):
        raise HTTPException(status_code=400, detail="Invalid media_type")

    logger.info("Download dispatch: %r by %r via %s (%s)", body.title, body.author, body.protocol, body.media_type or "ebook")
    try:
        download_id = await download_client.dispatch(
            protocol=body.protocol,
            download_url=body.download_url,
            title=body.title,
        )
        record_id = history_db.create_download(
            title=body.title,
            author=body.author,
            release_title=body.release_title,
            indexer=body.indexer,
            protocol=body.protocol,
            download_id=download_id,
            media_type=body.media_type,
        )
        return DownloadResponse(
            ok=True,
            record_id=record_id,
            download_id=download_id,
            message=f"Sent to {'rTorrent' if body.protocol == 'torrent' else 'SABnzbd'}",
        )
    except Exception as e:
        logger.error("Dispatch error: %s", e)
        raise HTTPException(status_code=502, detail=f"Dispatch failed: {e}")


@app.get("/portal/releases", response_model=ReleasesResponse)
async def get_releases(
    request: Request,
    session=Depends(get_session),
    title: str = "",
    author: str = "",
    media_type: str = "ebook",
):
    if not title.strip() and not author.strip():
        raise HTTPException(status_code=400, detail="title or author is required")
    if media_type not in ("ebook", "audiobook"):
        raise HTTPException(status_code=400, detail="Invalid media_type")

    logger.info("Release search: title=%r author=%r media_type=%r", title, author, media_type)
    try:
        accepted, rejected = await prowlarr.search_releases(title.strip(), author.strip(), content_type=media_type)
        return ReleasesResponse(
            accepted=[ReleaseItem(**r.to_dict()) for r in accepted],
            rejected=[ReleaseItem(**r.to_dict()) for r in rejected],
        )
    except Exception as e:
        logger.error("Release search error: %s", e)
        raise HTTPException(status_code=502, detail="Release search failed")


@app.get("/portal/history", response_model=HistoryResponse)
async def get_history(session=Depends(get_session), limit: int = 500):
    items = history_db.get_recent(limit=min(limit, 1000))
    return HistoryResponse(items=[HistoryItem(**i) for i in items])


@app.get("/portal", response_class=HTMLResponse, include_in_schema=False)
async def portal_page():
    return HTMLResponse(content=TEST_PAGE_HTML)


@app.get("/portal/test", include_in_schema=False)
async def portal_test_redirect():
    return RedirectResponse(url="/portal", status_code=301)


@app.get("/portal/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(session=Depends(get_session)):
    return HTMLResponse(content=ADMIN_PAGE_HTML)


@app.get("/portal/goodreads-profiles", include_in_schema=False)
async def list_goodreads_profiles(session=Depends(get_session)):
    return JSONResponse({"profiles": history_db.get_goodreads_profiles()})


@app.post("/portal/goodreads-profiles", include_in_schema=False)
async def add_goodreads_profile(
    session=Depends(get_session),
    body: dict = Body(...),
):
    name = (body.get("name") or "").strip()
    user_id = (body.get("user_id") or "").strip()
    shelf = (body.get("shelf") or "to-read").strip()
    # sync_from=None means full backlog; a date string means new additions only from that date
    sync_from = body.get("sync_from")  # already None or a YYYY-MM-DD string
    if not name or not user_id:
        raise HTTPException(status_code=400, detail="name and user_id are required")
    profile_id = history_db.add_goodreads_profile(
        name=name, user_id=user_id, shelf=shelf, sync_from=sync_from,
    )
    logger.info("Added Goodreads profile: %s (%s) sync_from=%s", name, user_id, sync_from)
    return JSONResponse({"ok": True, "id": profile_id})


@app.delete("/portal/goodreads-profiles/{profile_id}", include_in_schema=False)
async def delete_goodreads_profile(profile_id: str, session=Depends(get_session)):
    history_db.delete_goodreads_profile(profile_id)
    logger.info("Deleted Goodreads profile: %s", profile_id)
    return JSONResponse({"ok": True})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/portal", status_code=302)


# Serve the built React frontend for all non-API routes (SPA fallback).
# This only activates when the static directory exists (i.e. in production).
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Serve exact file if it exists, otherwise fall back to index.html
        candidate = _static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
