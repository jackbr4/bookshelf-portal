import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
import httpx
from fastapi import HTTPException

from .models import SearchResponse, BookResult, SeriesResult, ItemStatus, AddResponse
from .search_adapter import search_books, SearchBookResult

# ---------------------------------------------------------------------------
# Library cache — avoids re-fetching all books on every search
# ---------------------------------------------------------------------------
_LIBRARY_CACHE_TTL = 300  # seconds (5 minutes)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data (used when MOCK_MODE=true)
# ---------------------------------------------------------------------------

MOCK_BOOKS = [
    BookResult(id="book_1", title="Dune", author="Frank Herbert", year=1965, series_name="Dune", status=ItemStatus.available, language="en"),
    BookResult(id="book_2", title="Dune Messiah", author="Frank Herbert", year=1969, series_name="Dune", status=ItemStatus.already_in_library, language="en"),
    BookResult(id="book_3", title="The Way of Kings", author="Brandon Sanderson", year=2010, series_name="The Stormlight Archive", status=ItemStatus.available, language="en"),
    BookResult(id="book_4", title="Words of Radiance", author="Brandon Sanderson", year=2014, series_name="The Stormlight Archive", status=ItemStatus.already_monitored, language="en"),
    BookResult(id="book_5", title="Project Hail Mary", author="Andy Weir", year=2021, status=ItemStatus.available, language="en"),
    BookResult(id="book_6", title="The Last Wish", author="Andrzej Sapkowski", year=1993, series_name="The Witcher", status=ItemStatus.available, language="en"),
    BookResult(id="book_7", title="Ostatnie życzenie", author="Andrzej Sapkowski", year=1993, series_name="Wiedźmin", status=ItemStatus.available, language="pl"),
    BookResult(id="book_8", title="Krew elfów", author="Andrzej Sapkowski", year=1994, series_name="Wiedźmin", status=ItemStatus.available, language="pl"),
    BookResult(id="book_9", title="De Ontdekking van de Hemel", author="Harry Mulisch", year=1992, status=ItemStatus.available, language="nl"),
]

# Series mock kept for future use when series search is redesigned.
MOCK_SERIES: list[SeriesResult] = []


_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_APOSTROPHES = re.compile(r"[''`\u2018\u2019\u02bc]")


def _build_query_fallbacks(query: str) -> list[str]:
    """
    Return a list of query strings to try in order when Bookshelf returns 5xx.

    Bookshelf's lookup endpoint fails on certain phrasings. Common fixes:
    - Strip apostrophes ("Philosopher's Stone" → "Philosophers Stone")
    - Strip a leading article ("The Hobbit" → "Hobbit")
    - Use only the first two words for long queries
    """
    queries = [query]

    # Fallback 1: remove apostrophes — Bookshelf/Readarr sometimes 5xx on them
    sanitized = _APOSTROPHES.sub("", query).strip()
    if sanitized and sanitized.lower() != query.lower():
        queries.append(sanitized)

    # Fallback 2: strip leading "The" / "A" / "An"
    stripped = _LEADING_ARTICLE.sub("", query).strip()
    if stripped and stripped.lower() != query.lower() and stripped not in queries:
        queries.append(stripped)

    # Fallback 3: first two words (helps with very long titles)
    words = query.split()
    if len(words) > 3:
        short = " ".join(words[:2])
        if short not in queries:
            queries.append(short)

    return queries


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
    def __init__(self, base_url: str, api_key: str, mock_mode: bool = False, google_books_api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mock_mode = mock_mode
        self._google_books_api_key = google_books_api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Api-Key": self.api_key},
            timeout=30.0,
        )
        # In-memory library cache: (books_list, fetched_at_monotonic)
        self._library_cache: tuple[list[dict], float] | None = None
        # Separate client for Open Library (no auth, different base URL)
        self._ol_client = httpx.AsyncClient(
            base_url="https://openlibrary.org",
            timeout=10.0,
        )
        # Separate client for Google Books (no auth required; key passed as param)
        self._gb_client = httpx.AsyncClient(
            base_url="https://www.googleapis.com",
            timeout=10.0,
        )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def search(self, query: str) -> SearchResponse:
        if self.mock_mode:
            return self._mock_search(query)

        try:
            # Run Bookshelf lookup, Google Books enrichment, and library fetch concurrently.
            raw_books, gb_books, library_books = await asyncio.gather(
                self._lookup_books(query),
                self._search_google_books(query),
                self._get_library_books(),
            )

            if not raw_books:
                logger.info("[search] Bookshelf returned no results — trying Open Library fallback")
                raw_books = await self._search_open_library(query)

            # Bookshelf results first so they win dedup tiebreaks over gb: IDs.
            all_raw = raw_books + gb_books
            logger.info("[search] merged raw results: bookshelf=%d gb=%d total=%d",
                        len(raw_books), len(gb_books), len(all_raw))

            results, filtered_out = search_books(query, all_raw, library_books)
            books = [self._adapter_result_to_book_result(r) for r in results]
            filtered_books = [self._adapter_result_to_book_result(r) for r in filtered_out]

            return SearchResponse(books=books, series=[], filtered_books=filtered_books)

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
        Call /api/v1/book/lookup, with two fallback strategies when Bookshelf
        returns 5xx or times out:

        Attempt 1 — original query
        Attempt 2 — strip leading article ("The Hobbit" → "Hobbit")
        Attempt 3 — first two words only (for long queries that confuse Bookshelf)

        Returns raw list of book dicts, or raises HTTPException on total failure.
        """
        queries_to_try = _build_query_fallbacks(query)

        last_error: Exception | None = None
        for attempt, term in enumerate(queries_to_try):
            try:
                logger.info("[lookup] attempt %d query=%r", attempt + 1, term)
                resp = await self._client.get("/api/v1/book/lookup", params={"term": term}, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data if isinstance(data, list) else []
                    logger.info("[lookup] attempt %d returned %d results", attempt + 1, len(results))
                    return results
                if resp.status_code >= 500:
                    logger.warning("[lookup] attempt %d got %s for %r — trying fallback",
                                   attempt + 1, resp.status_code, term)
                    last_error = Exception(f"Bookshelf returned {resp.status_code}")
                    continue  # try next fallback query
                logger.warning("[lookup] attempt %d got %s for %r", attempt + 1, resp.status_code, term)
                return []
            except httpx.TimeoutException as e:
                logger.warning("[lookup] attempt %d timed out for %r", attempt + 1, term)
                last_error = e
                continue  # retry with next fallback
            except Exception as e:
                logger.warning("[lookup] attempt %d failed for %r: %s", attempt + 1, term, e)
                return []

        # All Bookshelf attempts exhausted — return empty so caller can try fallback.
        # Only propagate timeout as an error; 5xx failures are handled by OL fallback.
        if isinstance(last_error, httpx.TimeoutException):
            logger.warning("[lookup] all attempts timed out for %r", query)
        else:
            logger.warning("[lookup] all attempts failed for %r — will try Open Library", query)
        return []

    async def _get_library_books(self) -> list[dict]:
        """
        Fetch all books currently in the Bookshelf library.

        Results are cached in memory for _LIBRARY_CACHE_TTL seconds (5 min) so
        that consecutive searches don't each pay the full round-trip cost.
        If the fresh fetch times out or fails, the stale cache is returned so
        search results are still annotated with library status.
        """
        now = time.monotonic()

        # Return cached data if still fresh
        if self._library_cache and (now - self._library_cache[1]) < _LIBRARY_CACHE_TTL:
            logger.debug("[library] using cached data (%d books)", len(self._library_cache[0]))
            return self._library_cache[0]

        try:
            resp = await self._client.get("/api/v1/book", timeout=12.0)
            resp.raise_for_status()
            data = resp.json()
            books = data if isinstance(data, list) else []
            self._library_cache = (books, now)
            logger.info("[library] fetched %d books (cache refreshed)", len(books))
            return books
        except asyncio.TimeoutError:
            logger.warning("[library] fetch timed out — using stale cache or empty")
        except Exception as e:
            logger.warning("[library] fetch failed — using stale cache or empty: %s", e)

        # Return stale cache if available, otherwise empty (search still works,
        # just without library status annotations)
        return self._library_cache[0] if self._library_cache else []

    async def _search_open_library(self, query: str) -> list[dict]:
        """
        Search Open Library as a fallback when Bookshelf cannot handle the query.

        Results are mapped to the same raw-dict shape that normalize_raw_book_result
        expects, with foreignBookId prefixed "ol:" so the add flow knows to re-lookup
        in Bookshelf by title rather than by ID.
        """
        try:
            resp = await self._ol_client.get("/search.json", params={
                "q": query,
                "fields": "key,title,author_name,first_publish_year,cover_i,language",
                "limit": 20,
            })
            if resp.status_code != 200:
                logger.warning("[ol] search returned %s for %r", resp.status_code, query)
                return []
            docs = resp.json().get("docs", [])
            logger.info("[ol] returned %d docs for %r", len(docs), query)
            return [self._open_library_to_raw_dict(d) for d in docs if d.get("title")]
        except Exception as e:
            logger.warning("[ol] search failed for %r: %s", query, e)
            return []

    @staticmethod
    def _open_library_to_raw_dict(doc: dict) -> dict:
        """Map an Open Library search doc to the internal raw-book dict shape."""
        authors = doc.get("author_name") or []
        author_name = authors[0] if authors else ""

        cover_i = doc.get("cover_i")
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg" if cover_i else None

        # Use the first language tag if available; default to "en" (OL is primarily English)
        languages = doc.get("language") or []
        language = languages[0] if languages else "en"

        year = doc.get("first_publish_year")
        release_date = f"{year}-01-01" if year else None

        return {
            "foreignBookId": f"ol:{doc.get('key', '')}",
            "title": doc.get("title", ""),
            "authorName": author_name,
            "releaseDate": release_date,
            "remoteCover": cover_url,
            "language": language,
            "foreignEditionId": None,
            "seriesTitle": None,
        }

    async def _search_google_books(self, query: str) -> list[dict]:
        """
        Search Google Books as a parallel enrichment source alongside Bookshelf.

        Returns results mapped to the same raw-dict shape as _open_library_to_raw_dict,
        with foreignBookId prefixed "gb:" so the add flow knows to re-lookup in
        Bookshelf by title at add time.

        Requests up to 40 results to maximise language coverage (English + Polish + Dutch).
        Uses GOOGLE_BOOKS_API_KEY if configured; falls back to unauthenticated (1000 req/day cap).
        """
        try:
            params: dict = {"q": query, "maxResults": 40}
            if self._google_books_api_key:
                params["key"] = self._google_books_api_key
            resp = await self._gb_client.get("/books/v1/volumes", params=params)
            if resp.status_code != 200:
                logger.warning("[gb] search returned %s for %r", resp.status_code, query)
                return []
            items = resp.json().get("items") or []
            logger.info("[gb] returned %d items for %r", len(items), query)
            return [
                self._google_books_to_raw_dict(i)
                for i in items
                if i.get("volumeInfo", {}).get("title")
            ]
        except Exception as e:
            logger.warning("[gb] search failed for %r: %s", query, e)
            return []

    @staticmethod
    def _google_books_to_raw_dict(item: dict) -> dict:
        """Map a Google Books volume to the internal raw-book dict shape."""
        info = item.get("volumeInfo", {})
        authors = info.get("authors") or []
        author_name = authors[0] if authors else ""

        cover_url = info.get("imageLinks", {}).get("thumbnail")
        # Google Books thumbnails sometimes come back as http — upgrade to https
        if cover_url and cover_url.startswith("http://"):
            cover_url = "https://" + cover_url[7:]

        published_date = info.get("publishedDate", "") or ""

        return {
            "foreignBookId": f"gb:{item.get('id', '')}",
            "title": info.get("title", ""),
            "authorName": author_name,
            "releaseDate": published_date if published_date else None,
            "remoteCover": cover_url,
            "language": info.get("language"),
            "foreignEditionId": None,
            "seriesTitle": None,
        }

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
        """
        Get the full Bookshelf lookup result needed to build an add payload.

        For native Bookshelf IDs: match by foreignBookId.
        For Open Library IDs (prefixed "ol:"): return the first Bookshelf result
        for the title+author query — Bookshelf orders by relevance so first is best.
        """
        is_ol_id = foreign_book_id.startswith("ol:")
        is_gb_id = foreign_book_id.startswith("gb:")

        search_terms = []
        if title:
            if author:
                search_terms.append(f"{title} {author}")
            search_terms.append(title)

        for term in search_terms:
            try:
                resp = await self._client.get("/api/v1/book/lookup", params={"term": term})
                if resp.status_code == 200:
                    data = resp.json()
                    books = [b for b in (data if isinstance(data, list) else [data]) if isinstance(b, dict)]

                    if is_ol_id or is_gb_id:
                        # For OL/GB results take the first (most relevant) Bookshelf match
                        if books:
                            source = "OL" if is_ol_id else "GB"
                            logger.info("%s add: using first Bookshelf result for %r (id=%s)",
                                        source, term, books[0].get("foreignBookId"))
                            return books[0]
                    else:
                        for book in books:
                            if str(book.get("foreignBookId", "")) == str(foreign_book_id):
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
            language=result.language,
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
