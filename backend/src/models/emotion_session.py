# app/models/emotion_session.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey,
    Index, Integer, String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.emotion_snapshot import EmotionSnapshot
    from app.models.recommendation import Recommendation


class EmotionSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "emotion_sessions"

    VALID_STATUSES = ("active", "completed", "failed", "cancelled")
    VALID_EMOTIONS = ("happy", "sad", "angry", "fear", "disgust", "surprise", "neutral")

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    total_snapshots: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Set after session completes — aggregated across all snapshots
    dominant_emotion: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Mood profile string used for recommendation lookup
    mood_profile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="emotion_sessions")
    snapshots: Mapped[List["EmotionSnapshot"]] = relationship(
        "EmotionSnapshot",
        back_populates="emotion_session",
        cascade="all, delete-orphan",
        order_by="EmotionSnapshot.captured_at",
        lazy="selectin",
    )
    recommendation: Mapped[Optional["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="emotion_session",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','completed','failed','cancelled')",
            name="ck_emotion_session_status",
        ),
        CheckConstraint(
            "dominant_emotion IN ('happy','sad','angry','fear','disgust','surprise','neutral')"
            " OR dominant_emotion IS NULL",
            name="ck_emotion_session_emotion",
        ),
        CheckConstraint(
            "avg_confidence >= 0.0 AND avg_confidence <= 1.0 OR avg_confidence IS NULL",
            name="ck_emotion_session_confidence",
        ),
        CheckConstraint(
            "total_snapshots >= 0",
            name="ck_emotion_session_snapshot_count",
        ),
        Index("ix_emotion_sessions_user_status", "user_id", "status"),
        Index("ix_emotion_sessions_user_started", "user_id", "started_at"),
        Index("ix_emotion_sessions_started_at", "started_at"),
        Index(
            "ix_emotion_sessions_active",
            "user_id",
            postgresql_where="status = 'active'",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<EmotionSession id={self.id} user_id={self.user_id} "
            f"status={self.status} emotion={self.dominant_emotion}>"
        )