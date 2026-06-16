# app/models/emotion_snapshot.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.emotion_session import EmotionSession


class EmotionSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "emotion_snapshots"

    VALID_EMOTIONS = ("happy", "sad", "angry", "fear", "disgust", "surprise", "neutral")

    emotion_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emotion_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Primary classified emotion for this frame
    dominant_emotion: Mapped[str] = mapped_column(String(16), nullable=False)
    # Confidence of the dominant emotion (0.0–1.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Number of faces detected in frame
    face_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # S3 key for archived frame image (optional, privacy-configurable)
    frame_s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Full probability distribution across all 7 emotion classes
    # e.g. {"happy": 0.82, "neutral": 0.10, "sad": 0.04, ...}
    raw_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Processing metadata
    model_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # ── Relationships ────────────────────────────────────────────────────────
    emotion_session: Mapped["EmotionSession"] = relationship(
        "EmotionSession", back_populates="snapshots"
    )

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "dominant_emotion IN ('happy','sad','angry','fear','disgust','surprise','neutral')",
            name="ck_snapshot_dominant_emotion",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_snapshot_confidence_range",
        ),
        CheckConstraint(
            "face_count >= 0",
            name="ck_snapshot_face_count",
        ),
        Index("ix_snapshot_session_time", "emotion_session_id", "captured_at"),
        Index("ix_snapshot_dominant_emotion", "dominant_emotion"),
        Index("ix_snapshot_captured_at", "captured_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<EmotionSnapshot id={self.id} emotion={self.dominant_emotion} "
            f"confidence={self.confidence:.2f}>"
        )