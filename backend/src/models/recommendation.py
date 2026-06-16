# app/models/recommendation.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey,
    Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.emotion_session import EmotionSession
    from app.models.user import User
    from app.models.track import Track


class Recommendation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recommendations"

    # 1-to-1 with EmotionSession — one session = one recommendation batch
    emotion_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emotion_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Mood profile slug used for this recommendation run
    # e.g. 'euphoric', 'melancholic', 'calm', 'tense'
    mood_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    # Overall confidence from the emotion aggregation
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Cached count of tracks in this recommendation
    track_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Version of the recommendation model/algorithm used
    model_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # User feedback: did they like this set of recommendations?
    user_feedback: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1=thumbs up, -1=thumbs down

    # ── Relationships ────────────────────────────────────────────────────────
    emotion_session: Mapped["EmotionSession"] = relationship(
        "EmotionSession", back_populates="recommendation"
    )
    user: Mapped["User"] = relationship("User")
    tracks: Mapped[List["RecommendationTrack"]] = relationship(
        "RecommendationTrack",
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="RecommendationTrack.position",
        lazy="selectin",
    )

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("emotion_session_id", name="uq_recommendation_session"),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_recommendation_confidence",
        ),
        CheckConstraint(
            "track_count >= 0",
            name="ck_recommendation_track_count",
        ),
        CheckConstraint(
            "user_feedback IN (-1, 1) OR user_feedback IS NULL",
            name="ck_recommendation_user_feedback",
        ),
        Index("ix_recommendation_user_generated", "user_id", "generated_at"),
        Index("ix_recommendation_mood_profile", "mood_profile"),
    )

    def __repr__(self) -> str:
        return (
            f"<Recommendation id={self.id} mood={self.mood_profile} "
            f"tracks={self.track_count}>"
        )


class RecommendationTrack(Base, UUIDMixin):
    __tablename__ = "recommendation_tracks"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Normalized relevance score 0.0–1.0 (higher = more relevant to mood)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Display position in the recommendation list (1-based)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    recommendation: Mapped["Recommendation"] = relationship(
        "Recommendation", back_populates="tracks"
    )
    track: Mapped["Track"] = relationship("Track", lazy="selectin")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id", "position",
            name="uq_rec_track_position",
        ),
        UniqueConstraint(
            "recommendation_id", "track_id",
            name="uq_rec_track_unique",
        ),
        CheckConstraint(
            "relevance_score >= 0.0 AND relevance_score <= 1.0",
            name="ck_rec_track_relevance",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_rec_track_position",
        ),
        Index("ix_rec_tracks_recommendation_id", "recommendation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<RecommendationTrack rec={self.recommendation_id} "
            f"track={self.track_id} pos={self.position}>"
        )