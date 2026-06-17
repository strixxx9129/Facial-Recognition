"""
Playlist CRUD API

GET    /playlists          — list user playlists
POST   /playlists          — create playlist
GET    /playlists/{id}     — playlist detail with tracks
PATCH  /playlists/{id}     — update playlist
DELETE /playlists/{id}     — soft delete
POST   /playlists/{id}/tracks/{track_id} — add track
DELETE /playlists/{id}/tracks/{track_id} — remove track
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.playlist import Playlist, PlaylistTrack
from src.models.track import Track
from src.models.user import User
from src.schemas.playlist import (
    PlaylistCreateIn,
    PlaylistDetailOut,
    PlaylistOut,
    PlaylistTrackOut,
    PlaylistUpdateIn,
    TrackOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/playlists", tags=["Playlists"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


async def _get_playlist_or_404(
    db: AsyncSession, playlist_id: uuid.UUID, user_id: uuid.UUID
) -> Playlist:
    result = await db.execute(
        select(Playlist).where(
            Playlist.id == playlist_id,
            Playlist.user_id == user_id,
            Playlist.deleted_at.is_(None),
        )
    )
    pl = result.scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return pl


def _playlist_out(pl: Playlist) -> PlaylistOut:
    return PlaylistOut(
        id=pl.id,
        name=pl.name,
        description=pl.description,
        cover_image_url=pl.cover_image_url,
        emotion_context=pl.emotion_context,
        is_auto_generated=pl.is_auto_generated,
        is_public=pl.is_public,
        created_at=pl.created_at,
        updated_at=pl.updated_at,
        track_count=len(pl.playlist_tracks),
    )


@router.get("", response_model=list[PlaylistOut])
async def list_playlists(
    current_user: CurrentUser,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Playlist)
        .where(Playlist.user_id == current_user.id, Playlist.deleted_at.is_(None))
        .order_by(Playlist.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    playlists = result.scalars().all()
    return [_playlist_out(pl) for pl in playlists]


@router.post("", response_model=PlaylistOut, status_code=status.HTTP_201_CREATED)
async def create_playlist(
    body: PlaylistCreateIn,
    current_user: CurrentUser,
    db: DB,
):
    pl = Playlist(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        is_public=body.is_public,
    )
    db.add(pl)
    await db.commit()
    await db.refresh(pl)
    return _playlist_out(pl)


@router.get("/{playlist_id}", response_model=PlaylistDetailOut)
async def get_playlist(
    playlist_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    pl = await _get_playlist_or_404(db, playlist_id, current_user.id)

    tracks_out = [
        PlaylistTrackOut(
            position=pt.position,
            added_at=pt.added_at,
            track=TrackOut.model_validate(pt.track),
        )
        for pt in pl.playlist_tracks
    ]

    return PlaylistDetailOut(
        id=pl.id,
        name=pl.name,
        description=pl.description,
        cover_image_url=pl.cover_image_url,
        emotion_context=pl.emotion_context,
        is_auto_generated=pl.is_auto_generated,
        is_public=pl.is_public,
        created_at=pl.created_at,
        updated_at=pl.updated_at,
        track_count=len(tracks_out),
        tracks=tracks_out,
    )


@router.patch("/{playlist_id}", response_model=PlaylistOut)
async def update_playlist(
    playlist_id: uuid.UUID,
    body: PlaylistUpdateIn,
    current_user: CurrentUser,
    db: DB,
):
    pl = await _get_playlist_or_404(db, playlist_id, current_user.id)

    if body.name is not None:
        pl.name = body.name
    if body.description is not None:
        pl.description = body.description
    if body.is_public is not None:
        pl.is_public = body.is_public
    if body.cover_image_url is not None:
        pl.cover_image_url = body.cover_image_url

    await db.commit()
    await db.refresh(pl)
    return _playlist_out(pl)


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(
    playlist_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    pl = await _get_playlist_or_404(db, playlist_id, current_user.id)
    pl.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.post(
    "/{playlist_id}/tracks/{track_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Add a track to a playlist",
)
async def add_track(
    playlist_id: uuid.UUID,
    track_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    pl = await _get_playlist_or_404(db, playlist_id, current_user.id)

    # Verify track exists
    result = await db.execute(select(Track).where(Track.id == track_id))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Check not already in playlist
    existing = await db.execute(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == pl.id,
            PlaylistTrack.track_id == track_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Track already in playlist")

    # Get max position
    max_pos_result = await db.execute(
        select(func.max(PlaylistTrack.position)).where(
            PlaylistTrack.playlist_id == pl.id
        )
    )
    max_pos = max_pos_result.scalar() or 0

    pt = PlaylistTrack(
        playlist_id=pl.id,
        track_id=track_id,
        position=max_pos + 1,
    )
    db.add(pt)
    await db.commit()
    return {"message": "Track added", "position": max_pos + 1}


@router.delete(
    "/{playlist_id}/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a track from a playlist",
)
async def remove_track(
    playlist_id: uuid.UUID,
    track_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
):
    pl = await _get_playlist_or_404(db, playlist_id, current_user.id)

    result = await db.execute(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == pl.id,
            PlaylistTrack.track_id == track_id,
        )
    )
    pt = result.scalar_one_or_none()
    if not pt:
        raise HTTPException(status_code=404, detail="Track not in playlist")

    await db.delete(pt)
    await db.commit()