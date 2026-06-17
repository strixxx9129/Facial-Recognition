# app/models/playlist.py  (FINAL — corrected added_at field)
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    Index, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.track import Track


class Playlist(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "playlists"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    emotion_context: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="playlists")
    playlist_tracks: Mapped[List["PlaylistTrack"]] = relationship(
        "PlaylistTrack",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistTrack.position",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_playlists_user_id", "user_id"),
        Index(
            "ix_playlists_user_active",
            "user_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index("ix_playlists_emotion_context", "emotion_context"),
    )

    def __repr__(self) -> str:
        return f"<Playlist id={self.id} name={self.name}>"


class PlaylistTrack(Base, UUIDMixin):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="playlist_tracks")
    track: Mapped["Track"] = relationship(
        "Track", back_populates="playlist_entries", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("playlist_id", "track_id", name="uq_playlist_track"),
        UniqueConstraint("playlist_id", "position", name="uq_playlist_track_position"),
        CheckConstraint("position >= 1", name="ck_playlist_track_position"),
        Index("ix_playlist_tracks_playlist_id", "playlist_id"),
    )

    def __repr__(self) -> str:
        return f"<PlaylistTrack playlist={self.playlist_id} pos={self.position}>"
