from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    # --- Bookshelf / Readarr integration (optional) ---
    bookshelf_base_url: str = "http://localhost:8787"
    bookshelf_api_key: str = "changeme"
    bookshelf_enabled: bool = True

    # --- Prowlarr ---
    prowlarr_base_url: str = "http://localhost:29254"
    prowlarr_api_key: str = "changeme"

    # --- Torrent client: "rtorrent" or "qbittorrent" ---
    torrent_client: str = "rtorrent"

    # --- rTorrent ---
    rtorrent_url: str = "https://localhost:443/xmlrpc"
    rtorrent_user: str = ""
    rtorrent_password: str = ""
    rtorrent_download_dir: str = "/downloads"
    rtorrent_category: str = "books"
    rtorrent_imported_category: str = "books-imported"

    # --- qBittorrent ---
    qbittorrent_url: str = "http://localhost:8080"
    qbittorrent_user: str = "admin"
    qbittorrent_password: str = "adminadmin"
    qbittorrent_download_dir: str = "/downloads"
    qbittorrent_category: str = "books"
    qbittorrent_imported_category: str = "books-imported"

    # --- SABnzbd ---
    sabnzbd_base_url: str = "http://localhost:8080"
    sabnzbd_api_key: str = "changeme"
    sabnzbd_category: str = "books"

    # --- Calibre ---
    calibre_library_path: str = "/calibre/library"
    calibre_image: str = "lscr.io/linuxserver/calibre:latest"
    calibredb_books_dir: str = "/books"

    # --- Audiobookshelf ---
    audiobooks_dir: str = "/home/jackbr4/files/audiobooks"

    # --- History DB ---
    history_db_path: str = "./history.db"

    # --- App ---
    app_password: str = "changeme"
    app_session_secret: str = "changeme-secret"
    session_ttl_hours: float = 8.0
    cookie_secure: bool = False
    mock_mode: bool = True
    port: int = 8788
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:4173"]
    google_books_api_key: Optional[str] = None

    # --- Goodreads shelf sync ---
    goodreads_user_id: str = ""
    goodreads_shelf: str = "to-read"
    goodreads_max_per_run: int = 3
    # MAM (VIP class) enforces a 150-torrent cap on unsatisfied (seeding
    # < 72 h) downloads. Requesting a download while AT the cap blocks the
    # account for 24 hours, so dispatch is refused at mam_block_threshold —
    # a buffer below the real cap that absorbs status staleness and
    # concurrent writers (Goodreads cron, manual rTorrent use).
    mam_max_unsatisfied: int = 150
    mam_block_threshold: int = 145
    # Local-dev only: with mock_mode, report the slot limit as exhausted so
    # the banner/countdown UI can be exercised without a real rTorrent.
    mock_mam_exhausted: bool = False

    # --- List import (article URL/text → book candidates via LLM) ---
    anthropic_api_key: str = ""
    extraction_model: str = "claude-haiku-4-5"
    list_import_max_books: int = 40
    list_import_fetch_timeout: float = 20.0
    # Hard cap on fetched page bytes; anything larger is refused rather than
    # streamed through the LLM.
    list_import_fetch_max_bytes: int = 2 * 1024 * 1024

    # --- Release filter tuning ---
    # Indexers matching any of these substrings (case-insensitive) skip the
    # 512 KB minimum-size check.  Useful for curated trackers where short
    # books (< 512 KB) are legitimate.
    filter_trusted_indexers: List[str] = ["myanon", "mam"]
    # Indexers matching any of these substrings receive a +10 score bonus,
    # pushing their results toward the top of the list.
    filter_preferred_indexers: List[str] = ["myanon", "mam"]

    @field_validator("filter_trusted_indexers", "filter_preferred_indexers", mode="before")
    @classmethod
    def _parse_csv(cls, v):
        if isinstance(v, str):
            return [s.strip().lower() for s in v.split(",") if s.strip()]
        return v

    class Config:
        env_file = ".env"


settings = Settings()
