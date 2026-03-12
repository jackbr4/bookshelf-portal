import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from fastapi import HTTPException

from .models import SearchResponse, BookResult, SeriesResult, ItemStatus, AddResponse
from .search_adapter import search_books, SearchBookResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data (used when MOCK_MODE=true)
# ---------------------------------------------------------------------------

MOCK_BOOKS = [
    BookResult(id="book_1", title="Dune", author="Frank Herbert", year=1965, series_name="Dune", status=ItemStatus.available),
    BookResult(id="book_2", title="Dune Messiah", author="Frank Herbert", year=1969, series_name="Dune", status=ItemStatus.already_in_library),
    BookResult(id="book_3", title="The Way of Kings", author="Brandon Sanderson", year=2010, series_name="The Stormlight Archive", status=ItemStatus.available),
    BookResult(id="book_4", title="Words of Radiance", author="Brandon Sanderson", year=2014, series_name="The Stormlight Archive", status=ItemStatus.already_monitored),
    BookResult(id="book_5", title="Project Hail Mary", author="Andy Weir", year=2021, status=ItemStatus.available),
]

# Series mock kept for future use when series search is redesigned.
MOCK_SERIES: list[SeriesResult] = []


def _parse_author_name(author_title: str) -> str:
    """Extract author name from Bookshelf's 'lastname, firstname booktitle' format."""
    parts = author_title.split(" ")
    name_parts = []
    for part in parts:
        name_parts.append(part)
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
            timeout=25.0,  # Increased from 15s — Bookshelf lookup can be slow
        )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def search(self, query: str) -> SearchResponse:
        if self.mock_mode:
            return self._mock_search(query)

        try:
            # Fetch book lookup results and library books concurrently.
            # Series lookup is intentionally omitted — the Bookshelf series
            # endpoint is unreliable. Series search may be reintroduced later
            # using a different metadata strategy.
            raw_books, library_books = await asyncio.gather(
                self._lookup_books(query),
                self._get_library_books(),
            )

            results = search_books(query, raw_books, library_books)
            books = [self._adapter_result_to_book_result(r) for r in results]

            return SearchResponse(books=books, series=[])

        except HTTPException:
            raise
        except httpx.RequestError as e:
            logger.error("Bookshelf connection error during search: %s", e)
            raise HTTPException(status_code=502, detail="Cannot connect to Bookshelf")

    async def add_book(
        self,
        book_id: str,
        title: Optional[str],
        author: Optional[str],
        foreign_author_id: Optional[str],
        foreign_edition_id: Optional[str],
    ) -> AddResponse:
        if self.mock_mode:
            return AddResponse(ok=True, message="Book added successfully (mock)")

        try:
            root_folder, quality_profile_id, metadata_profile_id = await self._get_default_profiles()

            raw_book = await self._fetch_lookup_result(book_id, title, author)
            if not raw_book:
                raise HTTPException(status_code=404, detail="Book not found in Bookshelf lookup")

            logger.info("Add book payload base: id=%s edition=%s",
                        raw_book.get("foreignBookId"), raw_book.get("foreignEditionId"))

            resolved_author_id = foreign_author_id
            if not resolved_author_id:
                author_name = (
                    _parse_author_name(raw_book["authorTitle"]) if raw_book.get("authorTitle")
                    else author
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

    async def add_series(self, series_id: str) -> AddResponse:
        """
        Add a series to Bookshelf monitoring.
        Series are not currently surfaced in search results, but this endpoint
        is preserved for potential future use.
        """
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

    # -----------------------------------------------------------------------
    # Private helpers — network calls
    # -----------------------------------------------------------------------

    async def _lookup_books(self, query: str) -> list[dict]:
        """
        Call /api/v1/book/lookup with one retry on timeout.
        Returns raw list of book dicts (may be empty on failure).
        """
        for attempt in range(2):
            try:
                resp = await self._client.get("/api/v1/book/lookup", params={"term": query})
                if resp.status_code == 200:
                    data = resp.json()
                    return data if isinstance(data, list) else []
                if resp.status_code >= 500:
                    logger.warning("Book lookup returned %s for %r", resp.status_code, query)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Search failed for this title. "
                            "Try including the author's name (e.g. \"Walden Thoreau\")."
                        ),
                    )
                logger.warning("Book lookup returned %s for %r", resp.status_code, query)
                return []
            except HTTPException:
                raise
            except httpx.TimeoutException as e:
                if attempt == 0:
                    logger.warning("Book lookup timed out for %r, retrying…", query)
                    continue
                logger.error("Book lookup timed out twice for %r: %s", query, e)
                raise HTTPException(status_code=504, detail="Search timed out. Please try again.")
            except Exception as e:
                logger.warning("Book lookup failed for %r: %s", query, e)
                return []
        return []

    async def _get_library_books(self) -> list[dict]:
        """
        Fetch all books currently in the Bookshelf library.
        Returns full book dicts so the search adapter can match on both
        foreignBookId and normalised (title, author) pairs.
        """
        try:
            resp = await self._client.get("/api/v1/book")
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("Could not fetch library books (status checks disabled): %s", e)
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

    async def _fetch_lookup_result(
        self,
        foreign_book_id: str,
        title: Optional[str],
        author: Optional[str] = None,
    ) -> Optional[dict]:
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

    # -----------------------------------------------------------------------
    # Private helpers — data mapping
    # -----------------------------------------------------------------------

    def _adapter_result_to_book_result(self, result: SearchBookResult) -> BookResult:
        """Convert a SearchBookResult (search adapter output) to the API BookResult model."""
        if result.status_label == "already_monitored":
            status = ItemStatus.already_monitored
        elif result.status_label == "already_in_library":
            status = ItemStatus.already_in_library
        else:
            status = ItemStatus.available

        return BookResult(
            id=result.foreign_id or "",
            title=result.title,
            author=result.author,
            year=result.year,
            series_name=result.series_name,
            cover_url=result.cover_url,
            status=status,
            foreign_author_id=None,  # resolved at add time via author lookup
            foreign_edition_id=result.foreign_edition_id,
        )

    # -----------------------------------------------------------------------
    # Monitoring fix (post-add background task)
    # -----------------------------------------------------------------------

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

            await self._client.put("/api/v1/book/monitor", json={
                "bookIds": [book_internal_id],
                "monitored": True,
            })

            if author_added_str:
                added_dt = datetime.fromisoformat(author_added_str.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - added_dt).total_seconds()
                if age_seconds > 60:
                    logger.info("Author already existed (%ds old), leaving other books unchanged", int(age_seconds))
                    return

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

    # -----------------------------------------------------------------------
    # Mock search
    # -----------------------------------------------------------------------

    def _mock_search(self, query: str) -> SearchResponse:
        q = query.lower()
        books = [b for b in MOCK_BOOKS if q in b.title.lower() or q in b.author.lower()]
        return SearchResponse(books=books, series=[])
