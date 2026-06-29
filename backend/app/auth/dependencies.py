"""FastAPI dependencies for authentication and ownership checks."""
from __future__ import annotations

import uuid
from typing import Optional

import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.models import Document, User
from app.utils.errors import ForbiddenError, TokenExpiredError, UnauthorizedError
from app.utils.security import decode_token


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> User:
    """Extract and verify the bearer access token, return the User row.

    Raises:
        UnauthorizedError: missing/malformed Authorization header
        TokenExpiredError: access token expired (frontend should silent-refresh)
        InvalidTokenError: signature invalid / wrong type
    """
    from app.utils.errors import InvalidTokenError

    if not authorization:
        raise UnauthorizedError("Missing Authorization header", "MISSING_AUTH_HEADER")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Malformed Authorization header", "MALFORMED_AUTH_HEADER")

    token = parts[1]
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        raise InvalidTokenError()

    if payload.get("type") != "access":
        raise InvalidTokenError("Wrong token type", "INVALID_TOKEN_TYPE")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenError()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise InvalidTokenError()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User no longer exists", "USER_NOT_FOUND")
    return user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Same as get_current_user but returns None instead of raising.

    Useful for health checks / public endpoints that optionally personalize.
    """
    if not authorization:
        return None
    try:
        return await get_current_user(db=db, authorization=authorization)
    except Exception:
        return None


async def verify_document_ownership(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Fetch a document and verify it belongs to the current user.

    Per spec Section 6: returns 403 (never 404) on ownership mismatch to
    prevent document enumeration.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        # Return 403 — never reveal existence.
        raise ForbiddenError()
    if document.user_id != user.id:
        raise ForbiddenError()
    return document
