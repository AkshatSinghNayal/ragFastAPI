"""Centralized API error classes and FastAPI exception handlers.

All errors use the shape `{ "detail": str, "code": str }` per Section 11.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class APIError(HTTPException):
    """Base API error with a snake_case error code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"detail": detail, "code": code},
            headers=headers,
        )
        self.code = code


# --- Concrete errors ---


class UnauthorizedError(APIError):
    def __init__(self, detail: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, code)


class TokenExpiredError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "Access token has expired",
            "TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidTokenError(APIError):
    def __init__(self, detail: str = "Invalid token", code: str = "INVALID_TOKEN"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, code)


class InvalidRefreshTokenError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or missing refresh token",
            "INVALID_REFRESH_TOKEN",
        )


class ForbiddenError(APIError):
    def __init__(self, detail: str = "You do not have access to this resource"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, "FORBIDDEN")


class DuplicateDocumentError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            "A document with this filename already exists for your account",
            "DUPLICATE_DOCUMENT",
        )


class DocumentNotReadyError(APIError):
    def __init__(self, status_value: str = "processing") -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"Document is not ready for chat (current status: {status_value})",
            "DOCUMENT_NOT_READY",
        )


class UnreadablePDFError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "The uploaded PDF contains no extractable text",
            "UNREADABLE_PDF",
        )


class LLMUnavailableError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_502_BAD_GATEWAY,
            "The language model is currently unavailable. Please try again.",
            "LLM_UNAVAILABLE",
        )


# --- Handlers ---


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    """Handle APIError subclasses — they already carry the proper payload."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {"detail": str(exc.detail), "code": exc.code},
        headers=getattr(exc, "headers", None),
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Normalize plain FastAPI HTTPException into the {detail, code} shape."""
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    # Map well-known status codes to default codes.
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": str(exc.detail) if exc.detail else "Error",
            "code": code_map.get(exc.status_code, "ERROR"),
        },
    )


async def validation_exception_handler(_: Request, exc: Any) -> JSONResponse:
    """Pydantic v2 validation errors → 422 VALIDATION_ERROR."""
    try:
        details = exc.errors()
    except Exception:
        details = []
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "code": "VALIDATION_ERROR",
            "errors": details,
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch-all → 500 INTERNAL_ERROR (never leak stack traces)."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred", "code": "INTERNAL_ERROR"},
    )
