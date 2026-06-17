"""
FastAPI dependency injection helpers.
"""
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import decode_access_token
from src.db.dependencies import get_db
from src.models.user import User

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the JWT Bearer token and return the authenticated User.

    Raises 401 on any token problem or if the user no longer exists / is
    inactive.
    """
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        import uuid
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise credentials_exception

    return user