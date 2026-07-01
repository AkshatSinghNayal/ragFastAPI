"""FastAPI application entry point.

Wires routers, exception handlers, startup (Qdrant collection ensure),
shutdown (Qdrant client close), and CORS middleware.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware

from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.config import settings
from app.documents.router import router as documents_router
from app.utils.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.vector.qdrant_client import close_client, ensure_collection_exists

# Heavy SDK imports are deferred to keep /health cheap.
from fastapi import HTTPException

logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure Qdrant collection exists. Shutdown: close client."""
    logger.info("Starting RAG Chat API in %s mode", settings.ENVIRONMENT)
    try:
        await ensure_collection_exists()
    except Exception:
        logger.exception("Failed to ensure Qdrant collection on startup — continuing")
    yield
    await close_client()
    logger.info("Shutdown complete")


app = FastAPI(
    title="RAG Document Chat API",
    version="1.0.0",
    description="Upload PDFs and chat with them using Gemini + Qdrant.",
    lifespan=lifespan,
)

# --- Session (for OAuth state persistence) ---
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,
    max_age=600,  # 10 min — long enough for OAuth flow
    same_site="lax",  # must be lax for OAuth redirect to send session cookie
    https_only=settings.COOKIE_SECURE,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,  # required for the refresh cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception handlers ---
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# --- Routers ---
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)


# --- Health ---
@app.get("/health", tags=["system"])
async def health() -> dict:
    """Lightweight uptime ping endpoint (used by cron-job.org)."""
    return {"status": "ok"}
