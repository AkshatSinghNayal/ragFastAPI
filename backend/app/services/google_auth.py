"""Google OAuth 2.0 / OpenID Connect using Authlib + manual state management."""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional, Tuple

import jwt as pyjwt
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import Request, Response
from joserfc import jwk as jose_jwk
from sqlalchemy.ext.asyncio import AsyncSession

import os
from app.config import settings
from app.models.models import User

# Allow insecure OAuth transport (HTTP) for local development if backend URL is HTTP
if settings.BACKEND_URL.startswith("http://"):
    os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "1"


logger = logging.getLogger(__name__)

GOOGLE_OPENID_CONFIG_URL = "https://accounts.google.com/.well-known/openid-configuration"


async def _fetch_openid_config() -> Dict[str, Any]:
    """Fetch Google's OpenID Connect discovery document."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_OPENID_CONFIG_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()


async def _fetch_jwks(jwks_uri: str) -> list:
    """Fetch Google's JWKS (public keys for ID token verification)."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_uri, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    return data.get("keys", [])


async def get_google_login_url(request: Request) -> Tuple[str, str]:
    """Generate the Google OAuth authorization URL.

    Returns:
        (state, authorization_url)

    The caller is responsible for persisting the state (e.g. as a cookie).
    """
    config = await _fetch_openid_config()
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.BACKEND_URL}/auth/google/callback"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }

    import urllib.parse
    auth_url = f"{config['authorization_endpoint']}?{urllib.parse.urlencode(params)}"
    return state, auth_url


async def process_google_callback(
    request: Request,
    db: AsyncSession,
    expected_state: str,
) -> Tuple[User, str, str]:
    """Handle the Google OAuth callback pipeline.

    Args:
        request: The incoming callback request.
        db: Database session.
        expected_state: The OAuth state value that was stored earlier (e.g. in a cookie).

    Returns:
        (user, access_token, refresh_token)

    Raises:
        ValueError: state mismatch, email not verified, or token validation failed.
    """
    query_params = dict(request.query_params)
    state = query_params.get("state", "")
    code = query_params.get("code", "")

    if not code:
        raise ValueError("Missing authorization code in callback")

    if not state or state != expected_state:
        raise ValueError("OAuth state mismatch - possible CSRF attack")

    config = await _fetch_openid_config()

    redirect_uri = f"{settings.BACKEND_URL}/auth/google/callback"

    auth_resp = str(request.url)
    if settings.BACKEND_URL.startswith("https://") and auth_resp.startswith("http://"):
        auth_resp = auth_resp.replace("http://", "https://", 1)

    async with AsyncOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    ) as client:
        token = await client.fetch_token(
            config["token_endpoint"],
            authorization_response=auth_resp,
            grant_type="authorization_code",
            redirect_uri=redirect_uri,
        )

    id_token_str: Optional[str] = token.get("id_token")
    if not id_token_str:
        raise ValueError("No ID token returned from Google")

    jwks = await _fetch_jwks(config["jwks_uri"])
    id_token = _verify_id_token(id_token_str, jwks)

    if not id_token.get("email_verified"):
        raise ValueError("Google account email is not verified")

    userinfo = dict(id_token)
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


def _verify_id_token(id_token_str: str, jwks: list) -> Dict[str, Any]:
    """Verify and decode a Google ID token using Authlib's JWT utilities.

    Validates signature, issuer, audience, and expiration.
    Returns the decoded claims as a dict.
    """
    unverified_header = pyjwt.get_unverified_header(id_token_str)
    kid = unverified_header.get("kid")

    jwk_data = None
    for key in jwks:
        if key.get("kid") == kid:
            jwk_data = key
            break

    if not jwk_data:
        raise ValueError(f"No matching JWK found for kid={kid}")

    public_key = jose_jwk.import_key(jwk_data)
    pem_key = public_key.as_pem()
    try:
        claims = pyjwt.decode(
            id_token_str,
            pem_key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Google ID token has expired")
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Google ID token validation failed: {e}")

    return claims
