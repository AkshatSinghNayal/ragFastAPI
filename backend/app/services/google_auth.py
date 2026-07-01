"""Google OAuth 2.0 / OpenID Connect service using Authlib."""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import User

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=settings.GOOGLE_OPENID_CONFIG_URL,
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid email profile",
    },
)


async def get_google_login_url(request: Request) -> str:
    """Generate the Google OAuth authorization URL and redirect.

    Authlib stores the CSRF state in the session automatically.
    The returned value is a RedirectResponse.
    """
    redirect_uri = f"{settings.BACKEND_URL}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def process_google_callback(
    request: Request,
    db: AsyncSession,
) -> Tuple[User, str, str]:
    """Handle the full Google OAuth callback pipeline.

    1. Authlib validates the state parameter (CSRF protection).
    2. Exchanges the authorization code for tokens.
    3. Parses & verifies the OpenID Connect ID token.
    4. Rejects unverified emails.
    5. Finds or creates the user in the database.
    6. Generates application JWT access + refresh tokens.

    Returns:
        (user, access_token, refresh_token)

    Raises:
        ValueError: email not verified or userinfo missing
        OAuthError: state mismatch / code exchange failure
    """
    token = await oauth.google.authorize_access_token(request)
    userinfo: Dict[str, Any] | None = token.get("userinfo")

    if not userinfo:
        id_token = token.get("id_token")
        if id_token:
            claims = await oauth.google.parse_id_token(token, leeway=120)
            userinfo = dict(claims)
        else:
            raise ValueError("No user info or ID token returned from Google")

    email_verified = userinfo.get("email_verified", False)
    if not email_verified:
        raise ValueError("Google account email is not verified")

    google_id: str = userinfo["sub"]
    email: str = userinfo["email"]
    profile = {
        "name": userinfo.get("name", ""),
        "picture": userinfo.get("picture", ""),
        "given_name": userinfo.get("given_name", ""),
        "family_name": userinfo.get("family_name", ""),
        "locale": userinfo.get("locale", ""),
    }

    from app.auth.service import get_or_create_google_user

    user = await get_or_create_google_user(
        db,
        google_id=google_id,
        email=email,
        **profile,
    )

    from app.utils.security import create_access_token, create_refresh_token

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    logger.info("Google login successful: email=%s google_id=%s", email, google_id)
    return user, access_token, refresh_token
