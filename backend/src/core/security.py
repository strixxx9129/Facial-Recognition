"""
Security utilities: password hashing (Argon2id), JWT access tokens,
refresh token generation, SHA-256 hashing, and OAuth state tokens.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return an Argon2id hash of *plain*."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches *hashed*."""
    return pwd_context.verify(plain, hashed)


# ── JWT access tokens ─────────────────────────────────────────────────────────


def create_access_token(data: dict[str, Any]) -> str:
    """
    Create a signed JWT access token.

    *data* must contain at least ``"sub"`` (user_id as string) and
    ``"email"``.  Expiry is set from ``JWT_ACCESS_TOKEN_EXPIRE_MINUTES``.
    """
    from src.core.config import settings  # avoid circular at module level

    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update(
        {
            "iat": now,
            "exp": expire,
            "type": "access",
        }
    )
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Raises ``jose.JWTError`` on failure.
    """
    from src.core.config import settings

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ── Refresh tokens ────────────────────────────────────────────────────────────


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a cryptographically random refresh token.

    Returns ``(raw_token, hashed_token)`` where *raw_token* is sent to the
    client (once, never stored) and *hashed_token* is persisted to the DB.
    """
    raw = secrets.token_urlsafe(64)
    hashed = hash_token(raw)
    return raw, hashed


def hash_token(raw: str) -> str:
    """Return the SHA-256 hex digest of *raw*."""
    return hashlib.sha256(raw.encode()).hexdigest()


# ── OAuth state tokens (CSRF protection) ─────────────────────────────────────

_STATE_TOKEN_EXPIRE_SECONDS = 300  # 5 minutes


def create_oauth_state_token(provider: str) -> str:
    """
    Create a short-lived signed JWT used as the OAuth ``state`` parameter.

    *provider* must be ``"google"`` or ``"apple"``.
    """
    from src.core.config import settings

    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "oauth_state",
        "provider": provider,
        "iat": now,
        "exp": now + timedelta(seconds=_STATE_TOKEN_EXPIRE_SECONDS),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_oauth_state_token(token: str) -> str:
    """
    Verify an OAuth state JWT and return the provider name.

    Raises ``ValueError`` on invalid / expired tokens.
    """
    from src.core.config import settings

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise ValueError(f"Invalid OAuth state token: {exc}") from exc

    if payload.get("purpose") != "oauth_state":
        raise ValueError("Token purpose mismatch.")

    provider = payload.get("provider")
    if provider not in ("google", "apple"):
        raise ValueError(f"Unknown provider in state token: {provider!r}")

    return provider