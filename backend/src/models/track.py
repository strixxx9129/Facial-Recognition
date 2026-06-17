# app/models/track.py
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CheckConstraint, Float, Index, Integer,
    String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.recommendation import RecommendationTrack
    from src.models.playlist import PlaylistTrack
    from src.models.user_music_interaction import UserMusicInteraction


class Track(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tracks"

    PROVIDERS = ("spotify", "apple_music", "youtube_music")

    # External provider's track ID (e.g. Spotify track ID)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    # Music provider: 'spotify' | 'apple_music' | 'youtube_music'
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    artist: Mapped[str] = mapped_column(String(512), nullable=False)
    album: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    album_art_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    preview_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Audio Features (from Spotify API / Apple Music API) ──────────────────
    # Beats per minute
    tempo_bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Positivity: 0.0 (dark/sad) → 1.0 (happy/euphoric)
    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Intensity: 0.0 (calm/quiet) → 1.0 (loud/energetic)
    energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # How suitable for dancing: 0.0 → 1.0
    danceability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Presence of spoken word: 0.0 (pure music) → 1.0 (pure speech)
    speechiness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Acousticness: 0.0 (electric) → 1.0 (acoustic)
    acousticness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Computed mood classification tags (e.g. ['melancholic', 'rainy_day'])
    mood_tags: Mapped[Optional[list]] = mapped_column(
        ARRAY(String(64)), nullable=True
    )
    
    youtube_url: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
    )

    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
    )

    channel_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    release_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    recommendation_entries: Mapped[List["RecommendationTrack"]] = relationship(
        "RecommendationTrack", back_populates="track", lazy="dynamic"
    )
    playlist_entries: Mapped[List["PlaylistTrack"]] = relationship(
        "PlaylistTrack", back_populates="track", lazy="dynamic"
    )
    interactions: Mapped[List["UserMusicInteraction"]] = relationship(
        "UserMusicInteraction", back_populates="track", lazy="dynamic"
    )

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_track_provider_external"),
        CheckConstraint(
            "provider IN ('spotify','apple_music','youtube_music')",
            name="ck_track_provider",
        ),
        CheckConstraint(
            "valence >= 0.0 AND valence <= 1.0 OR valence IS NULL",
            name="ck_track_valence",
        ),
        CheckConstraint(
            "energy >= 0.0 AND energy <= 1.0 OR energy IS NULL",
            name="ck_track_energy",
        ),
        CheckConstraint(
            "danceability >= 0.0 AND danceability <= 1.0 OR danceability IS NULL",
            name="ck_track_danceability",
        ),
        CheckConstraint(
            "duration_ms > 0 OR duration_ms IS NULL",
            name="ck_track_duration_positive",
        ),
        Index("ix_tracks_provider_external", "provider", "external_id"),
        # Composite index for mood-based track lookup
        Index("ix_tracks_valence_energy", "valence", "energy"),
        Index("ix_tracks_artist", "artist"),
        Index("ix_tracks_mood_tags", "mood_tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Track id={self.id} artist={self.artist} title={self.title}>"
