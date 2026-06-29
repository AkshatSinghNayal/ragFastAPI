"""Auth business logic: register, login, refresh."""
from __future__ import annotations

import uuid
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.utils.errors import APIError, UnauthorizedError
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a user by email (case-sensitive)."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Fetch a user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a new user account.

    Raises:
        APIError(409): email already registered
    """
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise APIError(409, "An account with this email already exists", "EMAIL_ALREADY_REGISTERED")

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Tuple[User, str, str]:
    """Verify credentials and issue access + refresh tokens.

    Returns:
        (user, access_token, refresh_token)

    Raises:
        UnauthorizedError: invalid credentials
    """
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password", "INVALID_CREDENTIALS")

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return user, access, refresh


async def rotate_refresh_token(
    db: AsyncSession, refresh_token: str
) -> Tuple[User, str, str]:
    """Validate a refresh token and issue a fresh access + refresh pair.

    Raises:
        InvalidRefreshTokenError: token missing/invalid/expired
    """
    import jwt
    from app.config import settings
    from app.utils.errors import InvalidRefreshTokenError

    if not refresh_token:
        raise InvalidRefreshTokenError()
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise InvalidRefreshTokenError()
    except jwt.InvalidTokenError:
        raise InvalidRefreshTokenError()

    if payload.get("type") != "refresh":
        raise InvalidRefreshTokenError()

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidRefreshTokenError()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise InvalidRefreshTokenError()

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise InvalidRefreshTokenError()

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return user, access, refresh
