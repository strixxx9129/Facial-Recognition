"""
YouTube Integration API

POST /youtube/import          — import a YouTube playlist
POST /youtube/imports/{id}/sync — manually trigger re-sync
GET  /youtube/imports         — list all imports for current user
GET  /youtube/imports/{id}    — import detail
PATCH /youtube/imports/{id}   — toggle auto_sync, etc.
DELETE /youtube/imports/{id}  — delete import (and optionally its playlist)
"""
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.playlist_imports import PlaylistImport
from src.models.user import User
from src.schemas.playlist import (
    PlaylistImportOut,
    SyncResultOut,
    YouTubeImportIn,
)
from src.services.playlist_sync import import_youtube_playlist, sync_playlist_import
from src.services.youtube_service import extract_playlist_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/youtube", tags=["YouTube Integration"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/import",
    response_model=PlaylistImportOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a YouTube playlist",
)
async def import_playlist(
    body: YouTubeImportIn,
    current_user: CurrentUser,
    db: DB,
):
    """
    Import a YouTube playlist by URL or playlist ID.

    - Fetches all tracks from YouTube Data API v3
    - Creates local Playlist + Track records
    - Schedules daily auto-sync
    - Idempotent: re-importing same playlist triggers a re-sync
    """
    try:
        pi, sync_result = await import_youtube_playlist(
            db=db,
            user_id=current_user.id,
            url=body.url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        # e.g. YOUTUBE_API_KEY not configured
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if sync_result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=sync_result.error or "YouTube import failed",
        )

    return PlaylistImportOut.model_validate(pi)


@router.post(
    "/imports/{import_id}/sync",
    response_model=SyncResultOut,
    summary="Manually re-sync a YouTube playlist",
)
async def resync_import(
    import_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    """Trigger an immediate re-sync for an existing import."""
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.id == import_id,
            PlaylistImport.user_id == current_user.id,
        )
    )
    pi = result.scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="Import not found")

    _, sync_result = await sync_playlist_import(db, pi)
    return SyncResultOut(**sync_result.to_dict())


@router.get(
    "/imports",
    response_model=list[PlaylistImportOut],
    summary="List all YouTube imports for current user",
)
async def list_imports(
    current_user: CurrentUser,
    db: DB,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    q = select(PlaylistImport).where(PlaylistImport.user_id == current_user.id)
    if status_filter:
        q = q.where(PlaylistImport.status == status_filter)
    q = q.order_by(PlaylistImport.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    imports = result.scalars().all()
    return [PlaylistImportOut.model_validate(pi) for pi in imports]


@router.get(
    "/imports/{import_id}",
    response_model=PlaylistImportOut,
    summary="Get a specific import by ID",
)
async def get_import(
    import_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.id == import_id,
            PlaylistImport.user_id == current_user.id,
        )
    )
    pi = result.scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="Import not found")
    return PlaylistImportOut.model_validate(pi)


@router.patch(
    "/imports/{import_id}",
    response_model=PlaylistImportOut,
    summary="Update import settings (e.g. toggle auto-sync)",
)
async def update_import(
    import_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    auto_sync_enabled: bool | None = None,
):
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.id == import_id,
            PlaylistImport.user_id == current_user.id,
        )
    )
    pi = result.scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="Import not found")

    if auto_sync_enabled is not None:
        pi.auto_sync_enabled = auto_sync_enabled

    await db.commit()
    await db.refresh(pi)
    return PlaylistImportOut.model_validate(pi)


@router.delete(
    "/imports/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an import (does not delete the local playlist)",
)
async def delete_import(
    import_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.id == import_id,
            PlaylistImport.user_id == current_user.id,
        )
    )
    pi = result.scalar_one_or_none()
    if not pi:
        raise HTTPException(status_code=404, detail="Import not found")

    await db.delete(pi)
    await db.commit()