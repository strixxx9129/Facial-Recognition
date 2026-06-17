"""
Database session dependency for FastAPI endpoints.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession for the duration of a single request.
    The session is committed or rolled back by the service layer;
    this dependency only ensures it is always closed afterwards.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise