# app/models/user_preferences.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, String,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserPreferences(Base, UUIDMixin):
    __tablename__ = "user_preferences"

    PROVIDERS = ("spotify", "apple_music", "youtube_music", "none")

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Music taste
    preferred_genres: Mapped[Optional[list]] = mapped_column(
        ARRAY(String(64)), nullable=True
    )
    blocked_genres: Mapped[Optional[list]] = mapped_column(
        ARRAY(String(64)), nullable=True
    )
    blocked_artists: Mapped[Optional[list]] = mapped_column(
        ARRAY(String(256)), nullable=True
    )
    # Preferred streaming provider
    music_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="spotify", server_default="spotify"
    )
    # Auto-play recommendation when emotion session ends
    auto_play: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Save face frames to S3 for ML improvement (user consent)
    allow_frame_storage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Show emotion overlay on camera preview
    show_emotion_overlay: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Minimum confidence before triggering recommendation
    confidence_threshold: Mapped[float] = mapped_column(
        nullable=False, default=0.60, server_default="0.60"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="preferences")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user"),
        Index("ix_user_preferences_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserPreferences user_id={self.user_id} provider={self.music_provider}>"