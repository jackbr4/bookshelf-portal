import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .settings import settings
from .bookshelf_client import BookshelfClient
from .models import (
    AuthRequest, AuthResponse,
    SearchResponse,
    AddBookRequest, AddSeriesRequest, AddResponse
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

bookshelf = BookshelfClient(
    base_url=settings.bookshelf_base_url,
    api_key=settings.bookshelf_api_key,
    mock_mode=settings.mock_mode,
    google_books_api_key=settings.google_books_api_key,
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


@app.get("/health")
async def health():
    return {"status": "ok"}


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
