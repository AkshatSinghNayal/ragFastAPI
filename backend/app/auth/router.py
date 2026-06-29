"""Auth endpoints: /auth/register, /auth/login, /auth/refresh, /auth/logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.service import (
    authenticate_user,
    register_user,
    rotate_refresh_token,
)
from app.config import settings
from app.database import get_db
from app.models.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.utils.errors import InvalidRefreshTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach an httpOnly, Secure (in prod), SameSite=Strict refresh cookie."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_cookie_max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh cookie."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path="/auth",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account and immediately log them in."""
    user = await register_user(db, payload.email, payload.password)
    from app.utils.security import create_access_token, create_refresh_token

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate the user and return an access token + refresh cookie."""
    user, access, refresh = await authenticate_user(db, payload.email, payload.password)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Issue a new access token using the httpOnly refresh cookie.

    We also rotate the refresh token to limit replay windows.
    """
    cookie_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not cookie_token:
        raise InvalidRefreshTokenError()

    user, access, new_refresh = await rotate_refresh_token(db, cookie_token)
    _set_refresh_cookie(response, new_refresh)
    return RefreshResponse(access_token=access)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    _: User = Depends(get_current_user),
) -> LogoutResponse:
    """Clear the refresh cookie. Access token lives in memory and simply expires."""
    _clear_refresh_cookie(response)
    return LogoutResponse()


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return UserOut.model_validate(current_user)
