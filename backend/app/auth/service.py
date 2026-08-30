"""Auth business logic: register, login, refresh, Google OAuth."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.utils.errors import APIError, UnauthorizedError
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a user by email (case-insensitive)."""
    norm_email = email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == norm_email))
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
    norm_email = email.strip().lower()
    existing = await get_user_by_email(db, norm_email)
    if existing is not None:
        raise APIError(409, "An account with this email already exists", "EMAIL_ALREADY_REGISTERED")

    user = User(
        email=norm_email,
        hashed_password=hash_password(password),
        name=norm_email.split('@')[0],
        full_name=norm_email.split('@')[0],
    )
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
    norm_email = email.strip().lower()
    user = await get_user_by_email(db, norm_email)

    # Auto-provision / repair demo account on demand
    if norm_email == "demo@contextiq.com":
        if user is None:
            user = User(
                email=norm_email,
                hashed_password=hash_password(password),
                name="Demo User",
                full_name="Demo User",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("Auto-created demo user demo@contextiq.com")
        elif not verify_password(password, user.hashed_password):
            user.hashed_password = hash_password(password)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("Updated password for demo user demo@contextiq.com")

    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password", "INVALID_CREDENTIALS")

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return user, access, refresh


async def get_user_by_google_id(
    db: AsyncSession, google_id: str
) -> Optional[User]:
    """Fetch a user by Google OpenID Connect sub claim."""
    result = await db.execute(select(User).where(User.google_id == google_id))
    return result.scalar_one_or_none()


async def get_or_create_google_user(
    db: AsyncSession,
    google_id: str,
    email: str,
    **profile: str,
) -> User:
    """Find or create a user from Google profile data.

    Lookup order:
      1. By google_id (existing Google-linked user)
      2. By email (existing email/password user — link their account)
      3. Create a brand new user

    If the user already exists, their profile fields are updated when
    the Google-supplied values differ.
    """
    user = await get_user_by_google_id(db, google_id)
    if user is not None:
        changed = _update_profile_if_needed(user, profile)
        if changed:
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("Updated Google profile for user %s", user.id)
        return user

    user = await get_user_by_email(db, email)
    if user is not None:
        user.google_id = google_id
        changed = _update_profile_if_needed(user, profile)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Linked Google account to existing user %s", user.id)
        return user

    full_name_val = profile.get("name") or profile.get("given_name") or email.split('@')[0]
    user = User(
        email=email,
        google_id=google_id,
        hashed_password=None,
        name=profile.get("name") or full_name_val,
        full_name=full_name_val,
        picture=profile.get("picture"),
        given_name=profile.get("given_name"),
        family_name=profile.get("family_name"),
        locale=profile.get("locale"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Created new user from Google login: email=%s", email)
    return user


def _update_profile_if_needed(user: User, profile: Dict[str, str]) -> bool:
    """Update the user's profile fields if Google returned different values.

    Returns True if any field changed.
    """
    changed = False
    for field in ("name", "picture", "given_name", "family_name", "locale"):
        new_value = profile.get(field)
        current = getattr(user, field, None)
        if new_value and new_value != current:
            setattr(user, field, new_value)
            changed = True
    return changed


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
