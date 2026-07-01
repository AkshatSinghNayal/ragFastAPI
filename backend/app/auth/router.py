"""Auth endpoints: register, login, refresh, logout, Google OAuth."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
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
from app.services.google_auth import get_google_login_url, process_google_callback
from app.utils.errors import InvalidRefreshTokenError

OAUTH_STATE_COOKIE = "oauth_state"

logger = logging.getLogger(__name__)

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


# --- Google OAuth ---


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the user to Google's OAuth consent page.

    Generates a CSRF state value and stores it in a signed cookie
    for validation when Google redirects back.
    """
    state, auth_url = await get_google_login_url(request)

    redirect = RedirectResponse(url=auth_url, status_code=302)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Handle the OAuth 2.0 callback from Google.

    On success: sets the httpOnly refresh cookie and redirects to
    FRONTEND_URL/auth/callback.

    On failure: redirects to FRONTEND_URL/auth/callback?error=<code>.
    """
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected_state:
        error_param = "google_auth_failed"
        redirect = RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error={error_param}",
            status_code=302,
        )
        redirect.delete_cookie(
            key=OAUTH_STATE_COOKIE,
            path="/",
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            httponly=True,
        )
        return redirect

    try:
        user, access_token, refresh_token = await process_google_callback(
            request, db, expected_state
        )
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc)
        redirect = RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=google_auth_failed",
            status_code=302,
        )
        redirect.delete_cookie(
            key=OAUTH_STATE_COOKIE,
            path="/",
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            httponly=True,
        )
        return redirect

    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback",
        status_code=302,
    )

    redirect.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        httponly=True,
    )
    redirect.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_cookie_max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/auth",
    )

    return redirect
