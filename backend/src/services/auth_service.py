"""
Authentication service — business logic for all auth flows.
Keeps the router thin; all DB mutations live here.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.crypto import decrypt, encrypt
from src.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from src.models.auth_provider import AuthProvider
from src.models.session import Session
from src.models.user import User
from src.schemas.auth import AuthResponseOut, TokenOut, TokenRefreshOut, UserOut
from src.services.audit_service import log_event

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_token_out(user: User) -> tuple[TokenOut, str]:
    """
    Generate access + refresh tokens for *user*.

    Returns ``(TokenOut, raw_refresh_token)`` — the caller must persist the
    hashed refresh token in a new Session record.
    """
    access_token = create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    raw_refresh, _ = create_refresh_token()
    token_out = TokenOut(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
    )
    return token_out, raw_refresh


async def _create_session(
    db: AsyncSession,
    user: User,
    raw_refresh: str,
    request: Optional[Request] = None,
) -> Session:
    """Persist a new hashed Session record and return it."""
    from src.core.config import settings

    hashed = hash_token(raw_refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    session = Session(
        user_id=user.id,
        refresh_token_hash=hashed,
        expires_at=expires_at,
        ip_address=(
            request.client.host
            if request and request.client
            else None
        ),
        user_agent=(
            request.headers.get("User-Agent") if request else None
        ),
    )
    db.add(session)
    await db.flush()
    return session


# ── Email / Password ──────────────────────────────────────────────────────────


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: Optional[str],
    request: Optional[Request] = None,
) -> AuthResponseOut:
    """Create a new user with email/password credentials."""
    # Uniqueness check
    existing = await db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    if existing:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        display_name=display_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()  # get user.id

    provider = AuthProvider(
        user_id=user.id,
        provider="email",
        provider_user_id=email,
        password_hash=hash_password(password),
        provider_email=email,
    )
    db.add(provider)
    await db.flush()

    token_out, raw_refresh = _build_token_out(user)
    await _create_session(db, user, raw_refresh, request)

    await log_event(
        db,
        action="user.register",
        user_id=user.id,
        entity_type="User",
        entity_id=user.id,
        request=request,
    )
    await db.commit()

    return AuthResponseOut(token=token_out, user=UserOut.model_validate(user))


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
    request: Optional[Request] = None,
) -> AuthResponseOut:
    """Authenticate via email + password and issue tokens."""
    from fastapi import HTTPException, status

    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    if not user or not user.is_active:
        raise _invalid

    auth_provider = await db.scalar(
        select(AuthProvider).where(
            AuthProvider.user_id == user.id,
            AuthProvider.provider == "email",
        )
    )
    if not auth_provider or not auth_provider.password_hash:
        raise _invalid

    if not verify_password(password, auth_provider.password_hash):
        raise _invalid

    token_out, raw_refresh = _build_token_out(user)
    session = await _create_session(db, user, raw_refresh, request)

    await log_event(
        db,
        action="user.login",
        user_id=user.id,
        entity_type="User",
        entity_id=user.id,
        after_state={"provider": "email"},
        request=request,
    )
    await db.commit()

    return AuthResponseOut(token=token_out, user=UserOut.model_validate(user))


async def refresh_session(
    db: AsyncSession,
    raw_refresh_token: str,
    request: Optional[Request] = None,
) -> TokenRefreshOut:
    """Rotate a refresh token — revoke old, issue new."""
    from fastapi import HTTPException, status

    token_hash = hash_token(raw_refresh_token)
    session = await db.scalar(
        select(Session).where(Session.refresh_token_hash == token_hash)
    )

    if not session or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, session.user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
        )

    # Revoke old session (token rotation)
    session.revoked_at = datetime.now(timezone.utc)
    db.add(session)
    await db.flush()

    # Issue new tokens
    access_token = create_access_token({"sub": str(user.id), "email": user.email})
    raw_new, _ = create_refresh_token()
    new_session = await _create_session(db, user, raw_new, request)

    await log_event(
        db,
        action="session.refresh",
        user_id=user.id,
        entity_type="Session",
        entity_id=new_session.id,
        request=request,
    )
    await db.commit()

    return TokenRefreshOut(
        access_token=access_token,
        refresh_token=raw_new,
        token_type="bearer",
    )


async def logout_user(
    db: AsyncSession,
    current_user: User,
    raw_refresh_token: str,
    request: Optional[Request] = None,
) -> None:
    """Revoke the provided refresh token."""
    from fastapi import HTTPException, status

    token_hash = hash_token(raw_refresh_token)
    session = await db.scalar(
        select(Session).where(
            Session.refresh_token_hash == token_hash,
            Session.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    session.revoked_at = datetime.now(timezone.utc)
    db.add(session)

    await log_event(
        db,
        action="user.logout",
        user_id=current_user.id,
        entity_type="Session",
        entity_id=session.id,
        request=request,
    )
    await db.commit()


# ── OAuth (shared logic) ──────────────────────────────────────────────────────


async def find_or_create_oauth_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    display_name: Optional[str],
    avatar_url: Optional[str],
    access_token: Optional[str],
    refresh_token: Optional[str],
    token_expires_at: Optional[datetime],
    request: Optional[Request] = None,
) -> AuthResponseOut:
    """
    Shared handler for Google and Apple OAuth callbacks.

    Finds an existing user by email or provider_user_id, or creates one.
    Updates the AuthProvider record with fresh (encrypted) OAuth tokens.
    """
    # 1. Look up by provider + provider_user_id first (most precise)
    auth_provider = await db.scalar(
        select(AuthProvider).where(
            AuthProvider.provider == provider,
            AuthProvider.provider_user_id == provider_user_id,
        )
    )

    if auth_provider:
        user = await db.get(User, auth_provider.user_id)
    else:
        # Fall back: match by email
        user = await db.scalar(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )

    if not user:
        user = User(
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            is_active=True,
            is_verified=True,  # Email verified by OAuth provider
        )
        db.add(user)
        await db.flush()

    # Create or update the AuthProvider record
    if auth_provider is None:
        auth_provider = AuthProvider(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        db.add(auth_provider)

    auth_provider.provider_email = email
    auth_provider.provider_display_name = display_name
    auth_provider.provider_avatar_url = avatar_url
    auth_provider.token_expires_at = token_expires_at

    if access_token:
        auth_provider.access_token_enc = encrypt(access_token)
    if refresh_token:
        auth_provider.refresh_token_enc = encrypt(refresh_token)

    # Update user profile fields if richer data came from OAuth
    if not user.display_name and display_name:
        user.display_name = display_name
    if not user.avatar_url and avatar_url:
        user.avatar_url = avatar_url

    db.add(user)
    await db.flush()

    token_out, raw_refresh = _build_token_out(user)
    session = await _create_session(db, user, raw_refresh, request)

    await log_event(
        db,
        action="user.login",
        user_id=user.id,
        entity_type="User",
        entity_id=user.id,
        after_state={"provider": provider},
        request=request,
    )
    await db.commit()

    return AuthResponseOut(token=token_out, user=UserOut.model_validate(user))