import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from fastapi import HTTPException

from .models import SearchResponse, BookResult, SeriesResult, ItemStatus, AddResponse

logger = logging.getLogger(__name__)

MOCK_BOOKS = [
    BookResult(id="book_1", title="Dune", author="Frank Herbert", year=1965, series_name="Dune", status=ItemStatus.available),
    BookResult(id="book_2", title="Dune Messiah", author="Frank Herbert", year=1969, series_name="Dune", status=ItemStatus.already_in_library),
    BookResult(id="book_3", title="The Way of Kings", author="Brandon Sanderson", year=2010, series_name="The Stormlight Archive", status=ItemStatus.available),
    BookResult(id="book_4", title="Words of Radiance", author="Brandon Sanderson", year=2014, series_name="The Stormlight Archive", status=ItemStatus.already_monitored),
    BookResult(id="book_5", title="Project Hail Mary", author="Andy Weir", year=2021, status=ItemStatus.available),
]

MOCK_SERIES = [
    SeriesResult(id="series_1", title="Dune", author="Frank Herbert", book_count=6, status=ItemStatus.already_monitored),
    SeriesResult(id="series_2", title="The Stormlight Archive", author="Brandon Sanderson", book_count=5, status=ItemStatus.available),
    SeriesResult(id="series_3", title="The Expanse", author="James S.A. Corey", book_count=9, status=ItemStatus.available),
]


def _parse_author_name(author_title: str) -> str:
    """Extract author name from Bookshelf's 'lastname, firstname booktitle' format."""
    # authorTitle format: "lastname, firstname Book Title Here"
    # Split off the book title by finding where the name ends
    # Names are "word, word" at the start
    parts = author_title.split(" ")
    name_parts = []
    for part in parts:
        name_parts.append(part)
        # Stop after we have "lastname," and "firstname"
        if len(name_parts) >= 2 and name_parts[0].endswith(","):
            break
    if len(name_parts) >= 2:
        last = name_parts[0].rstrip(",")
        first = name_parts[1]
        return f"{first} {last}"
    return author_title.split(" ")[0]  # fallback


class BookshelfClient:
    def __init__(self, base_url: str, api_key: str, mock_mode: bool = False):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mock_mode = mock_mode
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Api-Key": self.api_key},
            timeout=15.0,
        )

    async def search(self, query: str) -> SearchResponse:
        if self.mock_mode:
            return self._mock_search(query)

        try:
            # Run all 4 requests concurrently
            library_books, library_series, raw_books, raw_series = await asyncio.gather(
                self._get_library_books(),
                self._get_library_series(),
                self._safe_book_lookup(query),
                self._safe_series_lookup(query),
            )

            # No author lookups during search — foreignAuthorId is resolved at add time
            books = [self._normalize_book(b, library_books) for b in raw_books[:10]]
            series = [self._normalize_series(s, library_series) for s in raw_series[:5]]

            return SearchResponse(books=books, series=series)
        except HTTPException:
            raise
        except httpx.RequestError as e:
            logger.error("Bookshelf connection error: %s", e)
            raise HTTPException(status_code=502, detail="Cannot connect to Bookshelf")

    async def add_book(self, book_id: str, title: Optional[str], author: Optional[str], foreign_author_id: Optional[str], foreign_edition_id: Optional[str]) -> AddResponse:
        if self.mock_mode:
            return AddResponse(ok=True, message="Book added successfully (mock)")

        try:
            root_folder, quality_profile_id, metadata_profile_id = await self._get_default_profiles()

            # Re-fetch the full lookup result so we have all required fields (including fresh edition IDs)
            raw_book = await self._fetch_lookup_result(book_id, title, author)
            if not raw_book:
                raise HTTPException(status_code=404, detail="Book not found in Bookshelf lookup")

            logger.info("Add book payload base: id=%s edition=%s", raw_book.get("foreignBookId"), raw_book.get("foreignEditionId"))

            # Resolve foreignAuthorId if not provided
            resolved_author_id = foreign_author_id
            if not resolved_author_id:
                author_name = (
                    _parse_author_name(raw_book["authorTitle"]) if raw_book.get("authorTitle")
                    else author  # fallback: author name passed from frontend search result
                )
                if author_name:
                    resolved_author_id = await self._lookup_foreign_author_id(author_name)

            if not resolved_author_id:
                raise HTTPException(status_code=502, detail="AUTHOR_NOT_FOUND")

            payload = dict(raw_book)
            payload["monitored"] = True
            payload["author"] = {
                "foreignAuthorId": resolved_author_id,
                "qualityProfileId": quality_profile_id,
                "metadataProfileId": metadata_profile_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "monitorNewItems": "new",
            }
            payload["editions"] = [{
                "foreignEditionId": raw_book.get("foreignEditionId", foreign_edition_id or ""),
                "monitored": True,
            }]
            payload["addOptions"] = {"searchForNewBook": True}

            resp = await self._client.post("/api/v1/book", json=payload)
            if resp.status_code == 409:
                raise HTTPException(status_code=409, detail="Book already in library")
            if not resp.is_success:
                body = resp.text[:500]
                logger.error("Bookshelf API add book %s: %s", resp.status_code, body)
                raise HTTPException(status_code=502, detail="BOOKSHELF_ERROR")

            book_resp = resp.json()
            asyncio.create_task(self._delayed_fix_monitoring(book_resp, book_id))
            return AddResponse(ok=True, message="Book added successfully")
        except HTTPException:
            raise
        except httpx.RequestError as e:
            logger.error("Add book connection error: %s", e)
            raise HTTPException(status_code=502, detail="CONNECTION_ERROR")
        except Exception as e:
            import traceback
            logger.error("Add book error: %s\n%s", e, traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Failed to add book: {type(e).__name__}: {e}")

    async def _delayed_fix_monitoring(self, book_resp: dict, foreign_book_id: str) -> None:
        """Wait for Bookshelf to finish async book discovery, then fix monitoring."""
        await asyncio.sleep(30)
        await self._fix_book_monitoring(book_resp, foreign_book_id)

    async def _fix_book_monitoring(self, book_resp: dict, foreign_book_id: str) -> None:
        """Ensure only the requested book is monitored, not the entire author catalog."""
        try:
            book_internal_id = book_resp.get("id")
            author_id = book_resp.get("authorId")
            author_added_str = (book_resp.get("author") or {}).get("added", "")

            if not (book_internal_id and author_id):
                return

            # Always ensure the requested book itself is monitored
            await self._client.put("/api/v1/book/monitor", json={
                "bookIds": [book_internal_id],
                "monitored": True,
            })

            # Only unmonitor other books if this author was just created by our request
            if author_added_str:
                added_dt = datetime.fromisoformat(author_added_str.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - added_dt).total_seconds()
                if age_seconds > 60:
                    logger.info("Author already existed (%ds old), leaving other books unchanged", int(age_seconds))
                    return

            # New author — unmonitor all books except the one we just added
            books_resp = await self._client.get("/api/v1/book", params={"authorId": author_id})
            if not books_resp.is_success:
                return
            to_unmonitor = [
                b["id"] for b in books_resp.json()
                if b.get("monitored") and b.get("id") != book_internal_id
            ]
            if to_unmonitor:
                logger.info("Unmonitoring %d other books for new author (id=%s)", len(to_unmonitor), author_id)
                await self._client.put("/api/v1/book/monitor", json={
                    "bookIds": to_unmonitor,
                    "monitored": False,
                })
        except Exception as e:
            logger.warning("Monitoring cleanup failed (non-fatal): %s", e)

    async def add_series(self, series_id: str) -> AddResponse:
        if self.mock_mode:
            return AddResponse(ok=True, message="Series added successfully (mock)")

        try:
            resp = await self._client.post("/api/v1/series", json={
                "foreignSeriesId": series_id,
                "monitored": True,
            })
            if resp.status_code == 409:
                raise HTTPException(status_code=409, detail="Series already monitored")
            resp.raise_for_status()
            return AddResponse(ok=True, message="Series added successfully")
        except HTTPException:
            raise
        except httpx.HTTPStatusError as e:
            logger.error("Add series HTTP error: %s %s", e.response.status_code, e.response.text[:200])
            raise HTTPException(status_code=502, detail=f"Bookshelf API error {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Add series error: %s", e)
            raise HTTPException(status_code=502, detail="Cannot connect to Bookshelf")

    async def _get_library_books(self) -> set:
        try:
            resp = await self._client.get("/api/v1/book")
            resp.raise_for_status()
            return {str(b.get("foreignBookId", "")) for b in resp.json()}
        except Exception:
            return set()

    async def _get_library_series(self) -> set:
        try:
            resp = await self._client.get("/api/v1/series")
            resp.raise_for_status()
            return {str(s.get("foreignSeriesId", "")) for s in resp.json()}
        except Exception:
            return set()

    async def _safe_book_lookup(self, query: str) -> list:
        try:
            resp = await self._client.get("/api/v1/book/lookup", params={"term": query})
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            if resp.status_code >= 500:
                logger.warning("Book lookup returned %s for %r", resp.status_code, query)
                raise HTTPException(
                    status_code=400,
                    detail="Search failed for this title. Try including the author's name (e.g. \"Walden Thoreau\")."
                )
            logger.warning("Book lookup returned %s for %r", resp.status_code, query)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Book lookup failed for %r: %s", query, e)
        return []

    async def _safe_series_lookup(self, query: str) -> list:
        try:
            resp = await self._client.get("/api/v1/series/lookup", params={"term": query})
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Series lookup returned %s for %r", resp.status_code, query)
        except Exception as e:
            logger.warning("Series lookup failed for %r: %s", query, e)
        return []

    async def _lookup_foreign_author_id(self, author_name: str) -> Optional[str]:
        try:
            resp = await self._client.get("/api/v1/author/lookup", params={"term": author_name})
            if resp.status_code == 200:
                authors = resp.json()
                if authors:
                    return str(authors[0].get("foreignAuthorId", ""))
        except Exception as e:
            logger.warning("Author lookup failed for %r: %s", author_name, e)
        return None

    async def _fetch_lookup_result(self, foreign_book_id: str, title: Optional[str], author: Optional[str] = None) -> Optional[dict]:
        """Get the full book lookup result needed to build an add payload."""
        search_terms = []
        if title:
            search_terms.append(title)
            if author:
                search_terms.append(f"{title} {author}")
        for term in search_terms:
            try:
                resp = await self._client.get("/api/v1/book/lookup", params={"term": term})
                if resp.status_code == 200:
                    data = resp.json()
                    books = data if isinstance(data, list) else [data]
                    for book in books:
                        if isinstance(book, dict) and str(book.get("foreignBookId", "")) == str(foreign_book_id):
                            return book
                    logger.warning("Book %s not found in lookup for %r", foreign_book_id, term)
                else:
                    logger.warning("Lookup returned %s for %r", resp.status_code, term)
            except Exception as e:
                logger.warning("Lookup by %r failed: %s", term, e)

        # Fallback: minimal payload (may fail if Bookshelf requires full data)
        logger.warning("Falling back to minimal payload for book %s", foreign_book_id)
        return {"foreignBookId": foreign_book_id}

    async def _get_default_profiles(self):
        """Return (rootFolderPath, qualityProfileId, metadataProfileId)."""
        try:
            rf_resp = await self._client.get("/api/v1/rootfolder")
            rf_resp.raise_for_status()
            root_folders = rf_resp.json()
            root_folder = root_folders[0]["path"] if root_folders else "/files/Books"
            quality_profile_id = root_folders[0].get("defaultQualityProfileId", 1) if root_folders else 1
            metadata_profile_id = root_folders[0].get("defaultMetadataProfileId", 1) if root_folders else 1
            return root_folder, quality_profile_id, metadata_profile_id
        except Exception as e:
            logger.warning("Could not fetch profiles, using defaults: %s", e)
            return "/files/Books", 1, 1

    def _normalize_book(self, raw: dict, library_ids: set) -> BookResult:
        foreign_id = str(raw.get("foreignBookId", raw.get("id", "")))
        in_library = foreign_id in library_ids
        monitored = raw.get("monitored", False) and in_library

        if monitored:
            status = ItemStatus.already_monitored
        elif in_library:
            status = ItemStatus.already_in_library
        else:
            status = ItemStatus.available

        # Parse author name from authorTitle (format: "lastname, firstname booktitle")
        author_name = ""
        if raw.get("author"):
            author_name = raw["author"].get("authorName", "")
        elif raw.get("authorTitle"):
            author_name = _parse_author_name(raw["authorTitle"])

        cover_url = raw.get("remoteCover")
        if not cover_url and raw.get("images"):
            cover_url = raw["images"][0].get("remoteUrl")

        return BookResult(
            id=foreign_id,
            title=raw.get("title", "Unknown"),
            author=author_name,
            year=int(raw["releaseDate"][:4]) if raw.get("releaseDate") else None,
            series_name=raw.get("seriesTitle"),
            cover_url=cover_url,
            status=status,
            foreign_author_id=None,  # resolved at add time via author lookup
            foreign_edition_id=raw.get("foreignEditionId"),
        )

    def _normalize_series(self, raw: dict, library_ids: set) -> SeriesResult:
        foreign_id = str(raw.get("foreignSeriesId", raw.get("id", "")))
        in_library = foreign_id in library_ids
        status = ItemStatus.already_monitored if in_library else ItemStatus.available

        return SeriesResult(
            id=foreign_id,
            title=raw.get("title", "Unknown"),
            author=raw.get("author", {}).get("authorName", "") if isinstance(raw.get("author"), dict) else "",
            book_count=raw.get("bookCount"),
            status=status,
        )

    def _mock_search(self, query: str) -> SearchResponse:
        q = query.lower()
        books = [b for b in MOCK_BOOKS if q in b.title.lower() or q in b.author.lower()]
        series = [s for s in MOCK_SERIES if q in s.title.lower() or q in s.author.lower()]
        return SearchResponse(books=books, series=series)
