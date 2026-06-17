import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


# ── Track Schemas ─────────────────────────────────────────────────────────────

class TrackOut(BaseModel):
    id: uuid.UUID
    external_id: str
    provider: str
    title: str
    artist: str
    album: Optional[str] = None
    album_art_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    youtube_url: Optional[str] = None
    duration_ms: Optional[int] = None
    channel_name: Optional[str] = None
    valence: Optional[float] = None
    energy: Optional[float] = None
    mood_tags: Optional[list[str]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Playlist Schemas ──────────────────────────────────────────────────────────

class PlaylistTrackOut(BaseModel):
    position: int
    added_at: datetime
    track: TrackOut

    model_config = {"from_attributes": True}


class PlaylistOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    emotion_context: Optional[str] = None
    is_auto_generated: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime
    track_count: int = 0

    model_config = {"from_attributes": True}


class PlaylistDetailOut(PlaylistOut):
    tracks: list[PlaylistTrackOut] = []

    model_config = {"from_attributes": True}


class PlaylistCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False


class PlaylistUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    cover_image_url: Optional[str] = None


# ── YouTube Import Schemas ────────────────────────────────────────────────────

class YouTubeImportIn(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        # Accept full URLs or bare playlist IDs
        is_youtube_url = "youtube.com" in v or "youtu.be" in v
        is_playlist_id = v.startswith(("PL", "RD", "UU", "LL", "FL", "OL"))
        if not (is_youtube_url or is_playlist_id):
            raise ValueError("Must be a valid YouTube URL or playlist ID")
        return v


class PlaylistImportOut(BaseModel):
    id: uuid.UUID
    source_url: str
    source_type: str
    external_playlist_id: Optional[str] = None
    external_title: Optional[str] = None
    external_channel: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str
    total_tracks: int
    synced_tracks: int
    failed_tracks: int
    auto_sync_enabled: bool
    last_synced_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    playlist_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class SyncResultOut(BaseModel):
    import_id: uuid.UUID
    status: str
    total: int
    added: int
    skipped: int
    removed: int
    failed: int
    error: Optional[str] = None