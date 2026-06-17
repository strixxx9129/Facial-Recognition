import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey,
    Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.playlist import Playlist


class PlaylistImport(Base, UUIDMixin, TimestampMixin):
    """
    Tracks YouTube playlist imports and their sync state.
    One PlaylistImport → one Playlist (the local copy of the YouTube playlist).
    """
    __tablename__ = "playlist_imports"

    VALID_STATUSES = ("pending", "syncing", "completed", "failed", "partial")

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The local playlist created from this import
    playlist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playlists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Source Info ───────────────────────────────────────────────────────────
    # Full YouTube playlist URL or video URL
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Currently only 'youtube' — extensible for future providers
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="youtube", server_default="youtube"
    )
    # YouTube playlist ID (e.g. PLxxxxxxxxxx)
    external_playlist_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # YouTube-provided title for this playlist
    external_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # YouTube channel name
    external_channel: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # YouTube playlist thumbnail
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # ── Sync State ────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    total_tracks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    synced_tracks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_tracks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Last time this import was synced (used by auto-sync scheduler)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Next scheduled sync (set by scheduler after each successful sync)
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Auto-sync enabled flag (user can disable per import)
    auto_sync_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="true"
    )
    # Last error message for failed syncs
    last_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User")
    playlist: Mapped[Optional["Playlist"]] = relationship("Playlist")

    # ── Constraints & Indexes ─────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','syncing','completed','failed','partial')",
            name="ck_playlist_import_status",
        ),
        CheckConstraint(
            "source_type IN ('youtube')",
            name="ck_playlist_import_source_type",
        ),
        CheckConstraint(
            "total_tracks >= 0",
            name="ck_playlist_import_total_tracks",
        ),
        CheckConstraint(
            "synced_tracks >= 0",
            name="ck_playlist_import_synced_tracks",
        ),
        # One user can import the same YouTube playlist only once
        UniqueConstraint(
            "user_id", "external_playlist_id",
            name="uq_playlist_import_user_external",
        ),
        Index("ix_playlist_imports_user_id", "user_id"),
        Index("ix_playlist_imports_status", "status"),
        Index("ix_playlist_imports_next_sync", "next_sync_at"),
        # Partial index for pending auto-syncs
        Index(
            "ix_playlist_imports_pending_sync",
            "next_sync_at",
            postgresql_where="auto_sync_enabled = true AND status != 'syncing'",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PlaylistImport id={self.id} user={self.user_id} "
            f"status={self.status} tracks={self.synced_tracks}/{self.total_tracks}>"
        )