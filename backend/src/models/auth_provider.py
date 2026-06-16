# app/models/auth_provider.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthProvider(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "auth_providers"

    PROVIDERS = ("email", "google", "apple")

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Provider name: 'email' | 'google' | 'apple'
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # External identity (e.g. Google sub, Apple sub, or user email for 'email')
    provider_user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    # AES-256-GCM encrypted OAuth access token
    access_token_enc: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # AES-256-GCM encrypted OAuth refresh token
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Argon2id hash — only populated for provider='email'
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Raw profile data from provider (name, picture, etc.)
    provider_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    provider_display_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    provider_avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="auth_providers")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id",
            name="uq_auth_provider_pid",
        ),
        CheckConstraint(
            "provider IN ('email', 'google', 'apple')",
            name="ck_auth_provider_name",
        ),
        Index("ix_auth_providers_user_provider", "user_id", "provider"),
        Index("ix_auth_providers_provider_uid", "provider", "provider_user_id"),
    )

    def __repr__(self) -> str:
        return f"<AuthProvider id={self.id} user_id={self.user_id} provider={self.provider}>"