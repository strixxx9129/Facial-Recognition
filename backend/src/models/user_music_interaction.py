# app/models/user_music_interaction.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.track import Track


class UserMusicInteraction(Base, UUIDMixin):
    __tablename__ = "user_music_interactions"

    INTERACTION_TYPES = ("play", "skip", "like", "dislike", "add_to_playlist", "share")

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Type of interaction with this track
    interaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Explicit rating 1–5 (optional, only for 'like'/'dislike' types)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Playback percentage completed (0–100), useful for skip analysis
    play_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Emotion context at time of interaction
    emotion_context: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    interacted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="music_interactions")
    track: Mapped["Track"] = relationship("Track", back_populates="interactions")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "interaction_type IN ('play','skip','like','dislike','add_to_playlist','share')",
            name="ck_interaction_type",
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5 OR rating IS NULL",
            name="ck_interaction_rating",
        ),
        CheckConstraint(
            "play_pct >= 0 AND play_pct <= 100 OR play_pct IS NULL",
            name="ck_interaction_play_pct",
        ),
        Index("ix_interactions_user_track", "user_id", "track_id"),
        Index("ix_interactions_user_type", "user_id", "interaction_type"),
        Index("ix_interactions_track_type", "track_id", "interaction_type"),
        Index("ix_interactions_interacted_at", "interacted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserMusicInteraction user={self.user_id} "
            f"track={self.track_id} type={self.interaction_type}>"
        )
