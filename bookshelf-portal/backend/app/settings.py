from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # --- Existing Bookshelf integration (gated by bookshelf_enabled) ---
    bookshelf_base_url: str = "http://localhost:8787"
    bookshelf_api_key: str = "changeme"
    bookshelf_enabled: bool = True

    # --- Prowlarr ---
    prowlarr_base_url: str = "http://localhost:29254"
    prowlarr_api_key: str = "changeme"

    # --- rTorrent ---
    rtorrent_url: str = "https://localhost:443/xmlrpc"
    rtorrent_user: str = ""
    rtorrent_password: str = ""
    rtorrent_download_dir: str = "/home/jackbr4/files/Downloads"
    rtorrent_category: str = "readarr"
    rtorrent_imported_category: str = "readarr-imported"

    # --- SABnzbd ---
    sabnzbd_base_url: str = "http://localhost:8080"
    sabnzbd_api_key: str = "changeme"
    sabnzbd_category: str = "readarr"

    # --- Calibre ---
    calibre_library_path: str = "/calibre/library"
    calibre_image: str = "lscr.io/linuxserver/calibre:latest"
    calibredb_books_dir: str = "/home/jackbr4/files/Books"

    # --- History DB ---
    history_db_path: str = "./history.db"

    # --- App ---
    app_password: str = "family"
    app_session_secret: str = "changeme-secret"
    session_ttl_hours: float = 8.0
    mock_mode: bool = True
    port: int = 8788
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:4173"]
    google_books_api_key: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
