"""
CalibreLibrary — read-only access to Calibre's metadata.db for library status annotation.

Returns {id, title, author} dicts. `id` is Calibre's own book id (metadata.db
primary key), which doubles as the path segment for a Calibre-Web book page
(/book/<id>) -- used to link "already in library" results back to Calibre-Web.
Results are cached for 60 seconds so repeated searches within the same minute
don't each hit the DB.
"""

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL = 60.0


class CalibreLibrary:
    def __init__(self, library_path: str):
        self._db_path = str(Path(library_path) / "metadata.db")
        self._cache: Optional[tuple[list[dict], float]] = None
        # Resolver calls get_library_books() from more than one concurrent
        # coroutine per request (the presence check and the main lookup),
        # each dispatched to a different executor thread. Without a lock,
        # concurrent cache misses each ran their own full metadata.db query
        # instead of one filling the cache for the other.
        self._lock = threading.Lock()

    def get_library_books(self) -> list[dict]:
        """
        Return all books in the Calibre library as {title, author} dicts.

        Opens the DB read-only so it never interferes with calibredb writes
        happening in the watcher.  Uses a 60-second in-memory cache.
        """
        now = time.monotonic()
        if self._cache and (now - self._cache[1]) < _CACHE_TTL:
            return self._cache[0]

        with self._lock:
            # Re-check: another thread may have just filled the cache while
            # we were waiting for the lock.
            now = time.monotonic()
            if self._cache and (now - self._cache[1]) < _CACHE_TTL:
                return self._cache[0]
            return self._load(now)

    def _load(self, now: float) -> list[dict]:
        try:
            conn = sqlite3.connect(
                f"file:{self._db_path}?mode=ro",
                uri=True,
                check_same_thread=False,
                timeout=5,
            )
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT b.id, b.title, a.name AS author
                FROM   books b
                JOIN   books_authors_link ba ON b.id = ba.book
                JOIN   authors a             ON a.id = ba.author
            """).fetchall()
            conn.close()

            books = [{"id": row["id"], "title": row["title"], "author": row["author"]} for row in rows]
            self._cache = (books, now)
            logger.info("[calibre_library] loaded %d books from metadata.db", len(books))
            return books

        except Exception as exc:
            logger.warning("[calibre_library] failed to read metadata.db: %s", exc)
            if self._cache:
                logger.info("[calibre_library] returning stale cache (%d books)", len(self._cache[0]))
                return self._cache[0]
            return []
