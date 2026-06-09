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
            # Add sync_from column to existing goodreads_profiles tables that predate it
            try:
                conn.execute("ALTER TABLE goodreads_profiles ADD COLUMN sync_from TEXT")
            except Exception:
                pass  # column already exists

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

                CREATE TABLE IF NOT EXISTS goodreads_seen (
                    goodreads_id        TEXT PRIMARY KEY,
                    title               TEXT NOT NULL,
                    author              TEXT NOT NULL,
                    status              TEXT NOT NULL,
                    download_record_id  TEXT,
                    first_seen_at       TEXT NOT NULL,
                    last_checked_at     TEXT NOT NULL
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

                CREATE TABLE IF NOT EXISTS goodreads_profiles (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    user_id     TEXT NOT NULL,
                    shelf       TEXT NOT NULL DEFAULT 'to-read',
                    sync_from   TEXT,
                    active      INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT NOT NULL
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

    # ------------------------------------------------------------------
    # Goodreads shelf sync
    # ------------------------------------------------------------------

    def goodreads_already_seen(self, goodreads_id: str) -> bool:
        """
        True if this Goodreads book should be skipped this run.
        - 'queued' and 'in_calibre': skip forever.
        - 'no_release': retry after 14 days so newly-available releases are caught.
        """
        from datetime import timedelta
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status, last_checked_at FROM goodreads_seen WHERE goodreads_id=?",
                (goodreads_id,),
            ).fetchone()
        if row is None:
            return False
        if row["status"] in ("queued", "in_calibre"):
            return True
        if row["status"] == "no_release":
            last = datetime.fromisoformat(row["last_checked_at"])
            return (datetime.now(timezone.utc) - last) < timedelta(days=14)
        return False

    def goodreads_mark_seen(
        self,
        goodreads_id: str,
        title: str,
        author: str,
        status: str,
        download_record_id: Optional[str] = None,
    ):
        now = _now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO goodreads_seen
                   (goodreads_id, title, author, status, download_record_id,
                    first_seen_at, last_checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(goodreads_id) DO UPDATE SET
                       status=excluded.status,
                       download_record_id=excluded.download_record_id,
                       last_checked_at=excluded.last_checked_at""",
                (goodreads_id, title, author, status, download_record_id, now, now),
            )

    # ------------------------------------------------------------------
    # Goodreads profiles
    # ------------------------------------------------------------------

    def get_goodreads_profiles(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM goodreads_profiles WHERE active=1 ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_goodreads_profile(
        self,
        name: str,
        user_id: str,
        shelf: str = "to-read",
        sync_from: Optional[str] = None,
    ) -> str:
        profile_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO goodreads_profiles (id, name, user_id, shelf, sync_from, active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (profile_id, name, user_id, shelf, sync_from, _now()),
            )
        return profile_id

    def delete_goodreads_profile(self, profile_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE goodreads_profiles SET active=0 WHERE id=?",
                (profile_id,),
            )
