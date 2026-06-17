from functools import lru_cache
import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── OAuth: Google ─────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── OAuth: Apple ──────────────────────────────────────────────────────────
    APPLE_CLIENT_ID: str = os.getenv("APPLE_CLIENT_ID", "")          # Service ID (com.yourapp.auth)
    APPLE_TEAM_ID: str = os.getenv("APPLE_TEAM_ID", "")
    APPLE_KEY_ID: str = os.getenv("APPLE_KEY_ID", "")
    APPLE_PRIVATE_KEY: str = os.getenv("APPLE_PRIVATE_KEY", "")        # PEM string from .p8 file
    APPLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/apple/callback"

    # ── YouTube Data API ──────────────────────────────────────────────────────
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
    YOUTUBE_API_BASE_URL: str = "https://www.googleapis.com/youtube/v3"
    # Max items per page (YouTube cap is 50)
    YOUTUBE_MAX_RESULTS_PER_PAGE: int = 50
    # Daily sync hour in UTC (0–23)
    YOUTUBE_SYNC_HOUR_UTC: int = 3

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    APP_VERSION: str = "1.0.0"

    # ── Encryption key for OAuth tokens (AES-256 — 32 bytes, base64-encoded) ─
    TOKEN_ENCRYPTION_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()