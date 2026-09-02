from pydantic import BaseModel
from typing import List, Optional, Literal
from enum import Enum


class ItemStatus(str, Enum):
    available = "available"
    already_in_library = "already_in_library"
    already_monitored = "already_monitored"


class BookResult(BaseModel):
    id: str
    title: str
    author: str
    year: Optional[int] = None
    series_name: Optional[str] = None
    cover_url: Optional[str] = None
    status: ItemStatus
    foreign_author_id: Optional[str] = None
    foreign_edition_id: Optional[str] = None
    language: Optional[str] = None


class SeriesResult(BaseModel):
    id: str
    title: str
    author: str
    book_count: Optional[int] = None
    cover_url: Optional[str] = None
    status: ItemStatus


class SearchResponse(BaseModel):
    books: List[BookResult]
    series: List[SeriesResult]
    filtered_books: List[BookResult] = []


class AuthRequest(BaseModel):
    access_code: str


class AuthResponse(BaseModel):
    ok: bool
    session_token: Optional[str] = None
    expires_at: Optional[str] = None


class AddBookRequest(BaseModel):
    book_id: str
    title: Optional[str] = None
    author: Optional[str] = None
    foreign_author_id: Optional[str] = None
    foreign_edition_id: Optional[str] = None


class AddSeriesRequest(BaseModel):
    series_id: str


class AddResponse(BaseModel):
    ok: bool
    message: str


class ReleaseItem(BaseModel):
    guid: str
    title: str
    indexer: str
    protocol: str
    size_mb: float
    detected_format: Optional[str] = None
    seeders: Optional[int] = None
    age_days: Optional[int] = None
    download_url: str
    publish_date: Optional[str] = None
    score: int = 0
    rejected: bool = False
    reject_reason: Optional[str] = None
    # This exact release was already sent to the download client (per history.db)
    already_requested: bool = False


class HistoryMatch(BaseModel):
    """A past download of (what looks like) the same book."""
    status: str              # downloading | imported
    created_at: str          # ISO-8601 UTC
    release_title: Optional[str] = None
    media_type: Optional[str] = None
    protocol: Optional[str] = None


class ReleasesResponse(BaseModel):
    ebook_accepted: List[ReleaseItem] = []
    ebook_rejected: List[ReleaseItem] = []
    audiobook_accepted: List[ReleaseItem] = []
    audiobook_rejected: List[ReleaseItem] = []
    calibre_title: Optional[str] = None
    audiobooks_title: Optional[str] = None
    # Most recent non-failed download of this book, if any
    history_match: Optional[HistoryMatch] = None


class DownloadRequest(BaseModel):
    title: str
    author: str
    release_title: str
    indexer: str
    protocol: str
    download_url: str
    media_type: Optional[str] = None


class DownloadResponse(BaseModel):
    ok: bool
    record_id: str
    download_id: str
    message: str


class HistoryItem(BaseModel):
    id: str
    title: str
    author: str
    download_id: Optional[str] = None
    release_title: Optional[str] = None
    indexer: Optional[str] = None
    protocol: Optional[str] = None
    source: Optional[str] = None
    media_type: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    error: Optional[str] = None


class HistoryResponse(BaseModel):
    items: List[HistoryItem]


# --- List import ---

class ImportExtractRequest(BaseModel):
    """Exactly one of url / text must be provided."""
    url: Optional[str] = None
    text: Optional[str] = None


class BookCandidate(BaseModel):
    title: str
    author: str = ""
    confidence: Literal["high", "low"] = "high"


class ImportExtractResponse(BaseModel):
    books: List[BookCandidate]
    source: Literal["url", "text"]
    # Page <title> (URL source) so the UI can label the list; None for pasted text.
    source_title: Optional[str] = None


class ImportBookInput(BaseModel):
    title: str
    author: str = ""


class ImportResolveRequest(BaseModel):
    books: List[ImportBookInput]


class ImportResolveCreated(BaseModel):
    job_id: str
    total: int


ImportResolveItemStatus = Literal["pending", "in_library", "requested", "available", "not_found", "error"]


class ImportResolveItem(BaseModel):
    index: int
    title: str
    author: str
    status: ImportResolveItemStatus = "pending"
    # Full release search result once resolved (same shape as /portal/releases),
    # so the import page can reuse the existing release components.
    releases: Optional[ReleasesResponse] = None
    error: Optional[str] = None


class ImportResolveStatus(BaseModel):
    job_id: str
    done: bool
    total: int
    completed: int
    results: List[ImportResolveItem]
