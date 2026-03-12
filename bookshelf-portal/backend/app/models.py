from pydantic import BaseModel
from typing import List, Optional
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
