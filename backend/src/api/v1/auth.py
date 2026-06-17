"""
Authentication endpoints — all under /api/v1/auth.

Supported flows:
  • Email + Password  (register / login / refresh / logout / me)
  • Google OAuth 2.0
  • Apple Sign In
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.config import settings
from src.core.security import (
    create_oauth_state_token,
    decode_access_token,
    verify_oauth_state_token,
)
from src.db.dependencies import get_db
from src.models.user import User
from src.schemas.auth import (
    AuthResponseOut,
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    TokenRefreshOut,
    UserOut,
)
from src.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Email / Password ──────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=AuthResponseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user with email + password",
)
async def register(
    body: RegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponseOut:
    return await auth_service.register_user(
        db=db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        request=request,
    )


@router.post(
    "/login",
    response_model=AuthResponseOut,
    summary="Login with email + password",
)
async def login(
    body: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponseOut:
    return await auth_service.login_user(
        db=db,
        email=body.email,
        password=body.password,
        request=request,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshOut,
    summary="Rotate a refresh token to obtain new tokens",
)
async def refresh_token(
    body: RefreshIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenRefreshOut:
    return await auth_service.refresh_session(
        db=db,
        raw_refresh_token=body.refresh_token,
        request=request,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Revoke the current refresh token session",
)
async def logout(
    body: LogoutIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await auth_service.logout_user(
        db=db,
        current_user=current_user,
        raw_refresh_token=body.refresh_token,
        request=request,
    )
    return {"message": "Logged out"}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the authenticated user's profile",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)


# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get(
    "/google",
    summary="Initiate Google OAuth 2.0 authorization flow",
    response_class=RedirectResponse,
)
async def google_login() -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured.",
        )
    state = create_oauth_state_token("google")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{query}")


@router.get(
    "/google/callback",
    response_model=AuthResponseOut,
    summary="Google OAuth 2.0 callback — exchange code for tokens",
)
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponseOut:
    # CSRF check
    try:
        verify_oauth_state_token(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state: {exc}",
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

    if token_resp.status_code != 200:
        logger.error("Google token exchange failed: %s", token_resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Google authorization code.",
        )

    token_data = token_resp.json()
    google_access_token: str = token_data["access_token"]
    google_refresh_token: Optional[str] = token_data.get("refresh_token")
    expires_in: int = token_data.get("expires_in", 3600)
    token_expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    token_expires_at += timedelta(seconds=expires_in)

    # Fetch user profile
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
            timeout=10,
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch Google user info.",
        )

    userinfo = userinfo_resp.json()
    provider_user_id: str = userinfo["sub"]
    email: str = userinfo["email"]
    display_name: Optional[str] = userinfo.get("name")
    avatar_url: Optional[str] = userinfo.get("picture")

    return await auth_service.find_or_create_oauth_user(
        db=db,
        provider="google",
        provider_user_id=provider_user_id,
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
        access_token=google_access_token,
        refresh_token=google_refresh_token,
        token_expires_at=token_expires_at,
        request=request,
    )


# ── Apple Sign In ─────────────────────────────────────────────────────────────

_APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
_APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
_APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


def _build_apple_client_secret() -> str:
    """
    Generate a signed JWT to use as the Apple client secret.
    Apple requires this instead of a static secret.
    """
    import time
    payload = {
        "iss": settings.APPLE_TEAM_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 180,  # 6-month max
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_CLIENT_ID,
    }
    return jwt.encode(
        payload,
        settings.APPLE_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": settings.APPLE_KEY_ID},
    )


@router.get(
    "/apple",
    summary="Initiate Apple Sign In authorization flow",
    response_class=RedirectResponse,
)
async def apple_login() -> RedirectResponse:
    if not settings.APPLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apple Sign In is not configured.",
        )
    state = create_oauth_state_token("apple")
    params = {
        "client_id": settings.APPLE_CLIENT_ID,
        "redirect_uri": settings.APPLE_REDIRECT_URI,
        "response_type": "code id_token",
        "scope": "name email",
        "response_mode": "form_post",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{_APPLE_AUTH_URL}?{query}")


@router.post(
    "/apple/callback",
    response_model=AuthResponseOut,
    summary="Apple Sign In callback — Apple uses POST with form data",
)
async def apple_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str = Form(...),
    state: str = Form(...),
    id_token: str = Form(...),
    user: Optional[str] = Form(None),  # JSON string, only on first login
) -> AuthResponseOut:
    # CSRF check
    try:
        verify_oauth_state_token(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state: {exc}",
        )

    # Fetch Apple's public keys to verify id_token
    async with httpx.AsyncClient() as client:
        keys_resp = await client.get(_APPLE_KEYS_URL, timeout=10)

    if keys_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch Apple public keys.",
        )

    apple_keys = keys_resp.json()

    # Decode header to find the right key
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg", "RS256")

    matching_key = next(
        (k for k in apple_keys["keys"] if k.get("kid") == kid),
        None,
    )
    if matching_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Apple public key not found for this token.",
        )

    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    from cryptography.hazmat.backends import default_backend
    import base64

    def _b64_to_int(val: str) -> int:
        padded = val + "=" * (4 - len(val) % 4)
        return int.from_bytes(base64.urlsafe_b64decode(padded), "big")

    pub_numbers = RSAPublicNumbers(
        e=_b64_to_int(matching_key["e"]),
        n=_b64_to_int(matching_key["n"]),
    )
    public_key = pub_numbers.public_key(default_backend())

    try:
        id_token_payload = jwt.decode(
            id_token,
            public_key,
            algorithms=[alg],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Apple id_token verification failed: {exc}",
        )

    provider_user_id: str = id_token_payload["sub"]
    email: Optional[str] = id_token_payload.get("email")

    # 'user' field comes as JSON only on the very first login
    display_name: Optional[str] = None
    if user:
        try:
            user_data = json.loads(user)
            name_parts = user_data.get("name", {})
            first = name_parts.get("firstName", "")
            last = name_parts.get("lastName", "")
            display_name = f"{first} {last}".strip() or None
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse Apple user JSON field.")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by Apple; please grant email access.",
        )

    # Exchange code for Apple tokens (stored encrypted)
    client_secret = _build_apple_client_secret()
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            _APPLE_TOKEN_URL,
            data={
                "client_id": settings.APPLE_CLIENT_ID,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.APPLE_REDIRECT_URI,
            },
            timeout=10,
        )

    apple_access_token: Optional[str] = None
    apple_refresh_token: Optional[str] = None
    if token_resp.status_code == 200:
        token_data = token_resp.json()
        apple_access_token = token_data.get("access_token")
        apple_refresh_token = token_data.get("refresh_token")
    else:
        logger.warning("Apple token exchange returned %s", token_resp.status_code)

    return await auth_service.find_or_create_oauth_user(
        db=db,
        provider="apple",
        provider_user_id=provider_user_id,
        email=email,
        display_name=display_name,
        avatar_url=None,  # Apple does not provide a profile picture
        access_token=apple_access_token,
        refresh_token=apple_refresh_token,
        token_expires_at=None,
        request=request,
    )