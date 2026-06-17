"""
Pydantic v2 schemas for the authentication endpoints.
"""
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ── Helpers ───────────────────────────────────────────────────────────────────

_PASSWORD_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


def _validate_password(value: str) -> str:
    if not _PASSWORD_RE.match(value):
        raise ValueError(
            "Password must be at least 8 characters and contain "
            "at least one uppercase letter and one digit."
        )
    return value


# ── Request bodies ────────────────────────────────────────────────────────────


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


# ── Response bodies ───────────────────────────────────────────────────────────


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponseOut(BaseModel):
    token: TokenOut
    user: UserOut