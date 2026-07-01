"""Auth-related request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Requests ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Responses ---


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    locale: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    """Returned on login: access token in body, refresh token set as cookie."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class ErrorDetail(BaseModel):
    """Standard error envelope per Section 11."""

    detail: str
    code: str
