"""
SQLite history DB — tracks downloads and imports for the v2 pipeline.

All timestamps are ISO-8601 UTC strings. The DB is created automatically
on first use; no migrations needed at this stage.
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryDB:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id              TEXT PRIMARY KEY,
                    title           TEXT NOT NULL,
                    author          TEXT NOT NULL,
                    release_title   TEXT,
                    indexer         TEXT,
                    protocol        TEXT,
                    download_id     TEXT,
                    status          TEXT NOT NULL DEFAULT 'downloading',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    error           TEXT
                );

                CREATE TABLE IF NOT EXISTS imports (
                    id              TEXT PRIMARY KEY,
                    download_id     TEXT REFERENCES downloads(id),
                    file_path       TEXT,
                    calibre_id      INTEGER,
                    status          TEXT NOT NULL,
                    imported_at     TEXT,
                    error           TEXT
                );
            """)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def create_download(
        self,
        title: str,
        author: str,
        release_title: str,
        indexer: str,
        protocol: str,
        download_id: str,
    ) -> str:
        record_id = str(uuid.uuid4())
        now = _now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO downloads
                   (id, title, author, release_title, indexer, protocol,
                    download_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'downloading', ?, ?)""",
                (record_id, title, author, release_title, indexer,
                 protocol, download_id, now, now),
            )
        return record_id

    def update_download_status(
        self,
        record_id: str,
        status: str,
        error: Optional[str] = None,
    ):
        with self._conn() as conn:
            conn.execute(
                "UPDATE downloads SET status=?, updated_at=?, error=? WHERE id=?",
                (status, _now(), error, record_id),
            )

    def get_downloading(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM downloads WHERE status='downloading' ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_download_by_id(self, download_id: str) -> Optional[dict]:
        """Look up a download record by the external client ID (torrent hash / NZO id)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM downloads WHERE download_id=? AND status='downloading'",
                (download_id,),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------

    def create_import(
        self,
        download_id: str,
        file_path: str,
        status: str,
        calibre_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> str:
        record_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO imports
                   (id, download_id, file_path, calibre_id, status, imported_at, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (record_id, download_id, file_path, calibre_id,
                 status, _now(), error),
            )
        return record_id

    def get_imports_for_download(self, download_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM imports WHERE download_id=? ORDER BY imported_at DESC",
                (download_id,),
            ).fetchall()
        return [dict(r) for r in rows]
