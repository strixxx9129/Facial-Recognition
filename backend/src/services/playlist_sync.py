"""
Playlist sync engine.

Responsibilities:
- Import a new YouTube playlist (create Playlist + Tracks + PlaylistTracks)
- Re-sync an existing import (add new tracks, remove deleted ones)
- Idempotent: safe to run multiple times without duplicating data
- Handles quota errors gracefully (marks import as 'partial')
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.playlist import Playlist, PlaylistTrack
from src.models.playlist_imports import PlaylistImport
from src.models.track import Track
from src.services.youtube_service import (
    YouTubeAPIError,
    YouTubePlaylistMeta,
    YouTubeQuotaError,
    YouTubeTrack,
    fetch_full_playlist,
)

logger = logging.getLogger(__name__)


class SyncResult:
    __slots__ = (
        "import_id", "status", "total", "added",
        "skipped", "removed", "failed", "error"
    )

    def __init__(self, import_id: uuid.UUID):
        self.import_id = import_id
        self.status: str = "pending"
        self.total: int = 0
        self.added: int = 0
        self.skipped: int = 0
        self.removed: int = 0
        self.failed: int = 0
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


async def _upsert_track(db: AsyncSession, yt: YouTubeTrack) -> Track:
    """
    Insert a track if it doesn't exist, otherwise return the existing one.
    Uses (provider, external_id) unique constraint for idempotency.
    """
    result = await db.execute(
        select(Track).where(
            Track.provider == "youtube_music",
            Track.external_id == yt.video_id,
        )
    )
    track = result.scalar_one_or_none()

    if track:
        # Update mutable fields in case they changed on YouTube
        track.title = yt.title
        track.channel_name = yt.channel_name
        track.thumbnail_url = yt.thumbnail_url
        track.album_art_url = yt.thumbnail_url
        track.youtube_url = yt.youtube_url
        if yt.duration_ms:
            track.duration_ms = yt.duration_ms
        return track

    track = Track(
        external_id=yt.video_id,
        provider="youtube_music",
        title=yt.title,
        artist=yt.channel_name,       # YouTube channel = artist equivalent
        channel_name=yt.channel_name,
        album_art_url=yt.thumbnail_url,
        thumbnail_url=yt.thumbnail_url,
        preview_url=None,
        youtube_url=yt.youtube_url,
        duration_ms=yt.duration_ms,
    )
    db.add(track)
    await db.flush()  # get ID without committing
    return track


async def _sync_playlist_tracks(
    db: AsyncSession,
    playlist: Playlist,
    yt_tracks: list[YouTubeTrack],
) -> tuple[int, int, int]:
    """
    Sync YouTube tracks into PlaylistTrack rows.

    Returns: (added, skipped, removed)
    """
    # Existing track external IDs in this playlist
    result = await db.execute(
        select(PlaylistTrack, Track)
        .join(Track, Track.id == PlaylistTrack.track_id)
        .where(PlaylistTrack.playlist_id == playlist.id)
    )
    existing_rows = result.all()
    existing_video_ids: set[str] = {t.external_id for _, t in existing_rows}
    existing_pt_by_video_id: dict[str, PlaylistTrack] = {
        t.external_id: pt for pt, t in existing_rows
    }

    incoming_video_ids: set[str] = {yt.video_id for yt in yt_tracks}

    added = skipped = removed = 0

    # ── Add new tracks ────────────────────────────────────────────────────────
    for yt in yt_tracks:
        if yt.video_id in existing_video_ids:
            # Update position if it changed
            pt = existing_pt_by_video_id.get(yt.video_id)
            if pt and pt.position != yt.position:
                pt.position = yt.position
            skipped += 1
            continue

        track = await _upsert_track(db, yt)

        # Ensure no position conflict (shift if needed)
        pt = PlaylistTrack(
            playlist_id=playlist.id,
            track_id=track.id,
            position=yt.position,
        )
        db.add(pt)
        added += 1

    # ── Remove tracks no longer in YouTube playlist ───────────────────────────
    stale_video_ids = existing_video_ids - incoming_video_ids
    for video_id in stale_video_ids:
        pt = existing_pt_by_video_id.get(video_id)
        if pt:
            await db.delete(pt)
            removed += 1

    return added, skipped, removed


async def import_youtube_playlist(
    db: AsyncSession,
    user_id: uuid.UUID,
    url: str,
) -> tuple[PlaylistImport, SyncResult]:
    """
    Import a YouTube playlist for a user.

    - Fetches playlist from YouTube API
    - Creates a local Playlist record
    - Upserts all Tracks
    - Creates PlaylistTrack junction rows
    - Creates PlaylistImport tracking record
    - Idempotent: re-importing same playlist returns existing import

    Returns: (PlaylistImport, SyncResult)
    """
    from src.services.youtube_service import extract_playlist_id
    playlist_id_yt = extract_playlist_id(url)

    # Check if already imported by this user
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.user_id == user_id,
            PlaylistImport.external_playlist_id == playlist_id_yt,
        )
    )
    existing_import = result.scalar_one_or_none()

    if existing_import:
        logger.info("Playlist %s already imported, triggering re-sync", playlist_id_yt)
        return await sync_playlist_import(db, existing_import)

    # ── Create import record in 'syncing' state ───────────────────────────────
    pi = PlaylistImport(
        user_id=user_id,
        source_url=url,
        source_type="youtube",
        external_playlist_id=playlist_id_yt,
        status="syncing",
    )
    db.add(pi)
    await db.flush()

    sync_result = SyncResult(pi.id)

    try:
        meta: YouTubePlaylistMeta = await fetch_full_playlist(url)
    except YouTubeQuotaError as exc:
        pi.status = "failed"
        pi.last_error = f"API quota exhausted: {exc}"
        sync_result.status = "failed"
        sync_result.error = pi.last_error
        await db.commit()
        return pi, sync_result
    except (YouTubeAPIError, ValueError) as exc:
        pi.status = "failed"
        pi.last_error = str(exc)
        sync_result.status = "failed"
        sync_result.error = pi.last_error
        await db.commit()
        return pi, sync_result

    # ── Update import with YouTube metadata ───────────────────────────────────
    pi.external_title = meta.title
    pi.external_channel = meta.channel_name
    pi.thumbnail_url = meta.thumbnail_url
    pi.total_tracks = meta.total_items

    # ── Create local Playlist ─────────────────────────────────────────────────
    playlist = Playlist(
        user_id=user_id,
        name=meta.title or "YouTube Playlist",
        description=f"Imported from YouTube • {meta.channel_name}",
        cover_image_url=meta.thumbnail_url,
        is_auto_generated=False,
        is_public=False,
    )
    db.add(playlist)
    await db.flush()

    pi.playlist_id = playlist.id

    # ── Sync tracks ───────────────────────────────────────────────────────────
    added, skipped, removed = await _sync_playlist_tracks(db, playlist, meta.tracks)

    # ── Finalise import record ────────────────────────────────────────────────
    pi.synced_tracks = len(meta.tracks)
    pi.status = "completed"
    pi.last_synced_at = datetime.now(timezone.utc)
    pi.next_sync_at = datetime.now(timezone.utc) + timedelta(days=1)

    sync_result.status = "completed"
    sync_result.total = meta.total_items
    sync_result.added = added
    sync_result.skipped = skipped
    sync_result.removed = removed

    await db.commit()
    logger.info(
        "Import complete: playlist=%s added=%d skipped=%d removed=%d",
        playlist_id_yt, added, skipped, removed,
    )
    return pi, sync_result


async def sync_playlist_import(
    db: AsyncSession,
    pi: PlaylistImport,
) -> tuple[PlaylistImport, SyncResult]:
    """
    Re-sync an existing PlaylistImport from YouTube.
    Safe to call concurrently — marks status as 'syncing' first.
    """
    sync_result = SyncResult(pi.id)

    # Guard: skip if already syncing (concurrent scheduler run)
    if pi.status == "syncing":
        logger.warning("PlaylistImport %s is already syncing, skipping", pi.id)
        sync_result.status = "skipped"
        return pi, sync_result

    pi.status = "syncing"
    pi.last_error = None
    await db.flush()

    try:
        meta: YouTubePlaylistMeta = await fetch_full_playlist(pi.source_url)
    except YouTubeQuotaError as exc:
        pi.status = "partial"
        pi.last_error = f"Quota exhausted during sync: {exc}"
        sync_result.status = "partial"
        sync_result.error = pi.last_error
        await db.commit()
        return pi, sync_result
    except (YouTubeAPIError, ValueError) as exc:
        pi.status = "failed"
        pi.last_error = str(exc)
        sync_result.status = "failed"
        sync_result.error = pi.last_error
        await db.commit()
        return pi, sync_result

    # Fetch the local playlist
    result = await db.execute(
        select(Playlist).where(Playlist.id == pi.playlist_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        # Playlist was deleted locally — recreate
        playlist = Playlist(
            user_id=pi.user_id,
            name=meta.title or pi.external_title or "YouTube Playlist",
            description=f"Re-imported from YouTube • {meta.channel_name}",
            cover_image_url=meta.thumbnail_url,
            is_auto_generated=False,
            is_public=False,
        )
        db.add(playlist)
        await db.flush()
        pi.playlist_id = playlist.id

    # Update playlist name/cover if changed on YouTube
    if meta.title:
        playlist.name = meta.title
    if meta.thumbnail_url:
        playlist.cover_image_url = meta.thumbnail_url

    added, skipped, removed = await _sync_playlist_tracks(db, playlist, meta.tracks)

    pi.total_tracks = meta.total_items
    pi.synced_tracks = len(meta.tracks)
    pi.status = "completed"
    pi.last_synced_at = datetime.now(timezone.utc)
    pi.next_sync_at = datetime.now(timezone.utc) + timedelta(days=1)
    pi.external_title = meta.title
    pi.external_channel = meta.channel_name
    pi.thumbnail_url = meta.thumbnail_url

    sync_result.status = "completed"
    sync_result.total = meta.total_items
    sync_result.added = added
    sync_result.skipped = skipped
    sync_result.removed = removed

    await db.commit()
    logger.info(
        "Re-sync complete: import=%s added=%d skipped=%d removed=%d",
        pi.id, added, skipped, removed,
    )
    return pi, sync_result


async def run_due_syncs(db: AsyncSession) -> list[SyncResult]:
    """
    Find all imports due for sync and process them.
    Called by the APScheduler daily job.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PlaylistImport).where(
            PlaylistImport.auto_sync_enabled.is_(True),
            PlaylistImport.status != "syncing",
            PlaylistImport.next_sync_at <= now,
        )
    )
    due_imports = result.scalars().all()

    logger.info("Auto-sync: %d playlists due for sync", len(due_imports))

    results = []
    for pi in due_imports:
        try:
            _, sync_result = await sync_playlist_import(db, pi)
            results.append(sync_result)
        except Exception as exc:
            logger.exception("Unexpected error syncing import %s: %s", pi.id, exc)
            pi.status = "failed"
            pi.last_error = f"Unexpected: {exc}"
            await db.commit()

    return results