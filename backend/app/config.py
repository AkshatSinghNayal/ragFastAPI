"""Centralized application configuration.

All environment variables are loaded here exactly once and exposed through
the `settings` singleton. No other module should call os.getenv directly —
import `settings` instead.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---
    ENVIRONMENT: str = Field(default="development")

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ragchat"
    )

    # --- Qdrant ---
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: str = Field(default="")
    QDRANT_COLLECTION: str = Field(default="document_chunks")

    # --- Gemini ---
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    GEMINI_EMBEDDING_MODEL: str = Field(default="text-embedding-004")
    EMBEDDING_DIMENSIONS: int = Field(default=768)

    # --- JWT / Auth ---
    JWT_SECRET: str = Field(default="change-me-please-32-chars-minimum-secret")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # --- CORS ---
    ALLOWED_ORIGINS: str = Field(default="http://localhost:5173")

    # --- Ingestion tuning ---
    CHUNK_MAX_TOKENS: int = Field(default=500)
    CHUNK_OVERLAP_TOKENS: int = Field(default=50)
    RAG_TOP_K: int = Field(default=5)
    RAG_HISTORY_MESSAGES: int = Field(default=6)

    # --- Cookie ---
    REFRESH_COOKIE_NAME: str = Field(default="refresh_token")
    COOKIE_SECURE: bool = Field(default=False)
    COOKIE_SAMESITE: str = Field(default="strict")

    @computed_field  # type: ignore[misc]
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list, trimming whitespace."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def refresh_cookie_max_age(self) -> int:
        """Cookie max-age in seconds."""
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
