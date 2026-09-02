"""
Resolve jobs for list import: run BookResolver.resolve_book over a list of
candidate books in the background and expose progress for polling.

Jobs live in memory only (single-process app) and expire after JOB_TTL.
They are deliberately ephemeral — the import page polls one to completion
and the result is never needed again.
"""
import asyncio
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from .models import (
    HistoryMatch,
    ImportBookInput,
    ImportResolveItem,
    ImportResolveStatus,
    ReleaseItem,
    ReleasesResponse,
)
from .resolver import BookResolver

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = 15 * 60
# Prowlarr fans each search out to every indexer; keep the aggregate load
# from all running jobs bounded.
RESOLVE_CONCURRENCY = 3


def _status_for(releases: ReleasesResponse) -> str:
    if releases.calibre_title or releases.audiobooks_title:
        return "in_library"
    if releases.history_match is not None:
        return "requested"
    if releases.ebook_accepted or releases.audiobook_accepted:
        return "available"
    return "not_found"


class _Job:
    __slots__ = ("id", "created_at", "results", "completed", "task", "include_audiobooks")

    def __init__(self, job_id: str, books: list[ImportBookInput], include_audiobooks: bool = True):
        self.id = job_id
        self.include_audiobooks = include_audiobooks
        self.created_at = time.monotonic()
        self.results = [
            ImportResolveItem(index=i, title=b.title.strip(), author=b.author.strip())
            for i, b in enumerate(books)
        ]
        self.completed = 0
        self.task: Optional[asyncio.Task] = None

    @property
    def done(self) -> bool:
        return self.completed >= len(self.results)

    def status(self) -> ImportResolveStatus:
        return ImportResolveStatus(
            job_id=self.id,
            done=self.done,
            total=len(self.results),
            completed=self.completed,
            results=list(self.results),
        )


class ResolveJobStore:
    def __init__(self, resolver: BookResolver, mock_mode: bool = False, ttl: float = JOB_TTL_SECONDS):
        self._resolver = resolver
        self._mock_mode = mock_mode
        self._ttl = ttl
        self._jobs: dict[str, _Job] = {}
        self._sem = asyncio.Semaphore(RESOLVE_CONCURRENCY)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def create(self, books: list[ImportBookInput], include_audiobooks: bool = True) -> _Job:
        self._purge_expired()
        job = _Job(secrets.token_urlsafe(12), books, include_audiobooks=include_audiobooks)
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        logger.info(
            "[import-resolve] job %s started: %d books%s",
            job.id, len(books), "" if include_audiobooks else " (ebooks only)",
        )
        return job

    def get(self, job_id: str) -> Optional[_Job]:
        self._purge_expired()
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        logger.info("[import-resolve] job %s cancelled", job_id)
        return True

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _purge_expired(self) -> None:
        now = time.monotonic()
        for job_id in [j.id for j in self._jobs.values() if now - j.created_at > self._ttl]:
            job = self._jobs.pop(job_id)
            if job.task and not job.task.done():
                job.task.cancel()

    async def _run(self, job: _Job) -> None:
        try:
            await asyncio.gather(*(self._resolve_one(job, item) for item in job.results))
            logger.info("[import-resolve] job %s finished", job.id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # gather itself shouldn't raise; belt and braces
            logger.error("[import-resolve] job %s crashed: %s", job.id, exc)
            for item in job.results:
                if item.status == "pending":
                    item.status = "error"
                    item.error = "Resolve job failed"
            job.completed = len(job.results)

    async def _resolve_one(self, job: _Job, item: ImportResolveItem) -> None:
        async with self._sem:
            try:
                if not item.title and not item.author:
                    raise ValueError("title or author is required")
                if self._mock_mode:
                    releases = await _mock_resolve(item.title, item.author)
                    if not job.include_audiobooks:
                        releases.audiobook_accepted = []
                        releases.audiobook_rejected = []
                else:
                    releases = await self._resolver.resolve_book(
                        item.title, item.author,
                        include_audiobooks=job.include_audiobooks,
                    )
                item.releases = releases
                item.status = _status_for(releases)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[import-resolve] %r by %r failed: %s", item.title, item.author, exc)
                item.status = "error"
                item.error = str(exc) or exc.__class__.__name__
            finally:
                job.completed += 1


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

def _mock_release(guid: str, title: str, fmt: str, size_mb: float, score: int, protocol: str = "torrent") -> ReleaseItem:
    return ReleaseItem(
        guid=guid,
        title=title,
        indexer="MyAnonamouse" if protocol == "torrent" else "NZBgeek",
        protocol=protocol,
        size_mb=size_mb,
        detected_format=fmt,
        seeders=42 if protocol == "torrent" else None,
        age_days=120,
        download_url=f"http://localhost:29254/{guid}",
        score=score,
    )


async def _mock_resolve(title: str, author: str) -> ReleasesResponse:
    """
    Deterministic fake results keyed off the title so the import page can be
    exercised locally: every 4th book is already in the library, every 5th
    has nothing, one in ten errors out, one in seven was requested before,
    the rest have releases.
    """
    await asyncio.sleep(0.6 + (len(title) % 5) * 0.15)
    h = sum(ord(c) for c in title.lower())
    if h % 10 == 3:
        raise RuntimeError("Prowlarr search timed out (mock)")
    if h % 5 == 0:
        return ReleasesResponse()
    if h % 4 == 0:
        return ReleasesResponse(calibre_title=title, audiobooks_title=None)
    label = f"{title} by {author}" if author else title
    requested = h % 7 == 1
    releases = ReleasesResponse(
        ebook_accepted=[
            _mock_release(f"{h}-eb1", f"{label} [ENG / EPUB]", "EPUB", 1.8, 72),
            _mock_release(f"{h}-eb2", f"{label} [ENG / MOBI]", "MOBI", 2.1, 60),
            _mock_release(f"{h}-eb3", f"{label} (epub)", "EPUB", 1.6, 55, protocol="usenet"),
        ],
        audiobook_accepted=(
            [_mock_release(f"{h}-ab1", f"{label} [ENG / M4B]", "M4B", 480.2, 64)] if h % 2 == 0 else []
        ),
    )
    if requested:
        releases.ebook_accepted[0].already_requested = True
        releases.history_match = HistoryMatch(
            status="downloading",
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            release_title=releases.ebook_accepted[0].title,
            media_type="ebook",
            protocol="torrent",
        )
    return releases
