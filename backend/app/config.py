"""Centralized application configuration.

All environment variables are loaded here exactly once and exposed through
the `settings` singleton. No other module should call os.getenv directly —
import `settings` instead.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pydantic import Field, computed_field, field_validator
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

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def sanitize_database_url(cls, v: str) -> str:
        """Sanitize DATABASE_URL for asyncpg driver."""
        if not v:
            return v
        url = v.strip()
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]

        parsed = urlparse(url)
        if parsed.query:
            query_params = parse_qs(parsed.query)
            if "sslmode" in query_params:
                sslmode = query_params.pop("sslmode")[0]
                if sslmode in ("require", "verify-ca", "verify-full", "prefer"):
                    query_params["ssl"] = ["require"]
                elif sslmode in ("disable", "allow"):
                    query_params["ssl"] = ["disable"]
            query_params.pop("channel_binding", None)
            new_query = urlencode(query_params, doseq=True)
            url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )
        return url

    # --- Qdrant ---
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: str = Field(default="")
    QDRANT_COLLECTION: str = Field(default="document_chunks")

    # --- Gemini ---
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash")
    GEMINI_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001")
    EMBEDDING_DIMENSIONS: int = Field(default=768)

    # --- JWT / Auth ---
    JWT_SECRET: str = Field(default="change-me-please-32-chars-minimum-secret")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    FRONTEND_URL: str = Field(default="http://localhost:5173")
    BACKEND_URL: str = Field(default="http://localhost:8000")
    GOOGLE_OPENID_CONFIG_URL: str = Field(
        default="https://accounts.google.com/.well-known/openid-configuration"
    )

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
    COOKIE_SAMESITE: str = Field(default="lax")

    @computed_field  # type: ignore[misc]
    @property
    def is_cookie_secure(self) -> bool:
        """Return True if explicitly requested or if backend URL uses https."""
        return self.COOKIE_SECURE or self.BACKEND_URL.startswith("https://")

    @computed_field  # type: ignore[misc]
    @property
    def effective_cookie_samesite(self) -> str:
        """Return 'none' for HTTPS production environments to support cross-domain cookies."""
        if self.is_cookie_secure:
            return "none"
        return self.COOKIE_SAMESITE.lower() if self.COOKIE_SAMESITE else "lax"

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
