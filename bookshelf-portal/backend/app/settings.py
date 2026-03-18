from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    bookshelf_base_url: str = "http://localhost:8787"
    bookshelf_api_key: str = "changeme"
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
