# app/models/session.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.user import User


class Session(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hash of the raw refresh token — never store the raw value
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    # Browser/device fingerprint for anomaly detection
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # IPv4 or IPv6 (max 45 chars)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Absolute expiry of this refresh token
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Set when token is explicitly revoked or reuse is detected
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_sessions_token_hash"),
        # Partial index: fast lookup of active (non-revoked) sessions per user
        Index(
            "ix_sessions_user_active",
            "user_id",
            postgresql_where="revoked_at IS NULL",
        ),
        Index("ix_sessions_expires_at", "expires_at"),
        Index("ix_sessions_revoked_at", "revoked_at"),
    )

    @property
    def is_active(self) -> bool:
        from datetime import timezone
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} active={self.is_active}>"
