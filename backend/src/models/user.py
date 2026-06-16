# app/models/user.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.auth_provider import AuthProvider
    from app.models.session import Session
    from app.models.emotion_session import EmotionSession
    from app.models.playlist import Playlist
    from app.models.user_preferences import UserPreferences
    from app.models.user_music_interaction import UserMusicInteraction
    from app.models.audit_log import AuditLog


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="UTC", nullable=False, server_default="UTC"
    )

    # ── Relationships ────────────────────────────────────────────────────────
    auth_providers: Mapped[List["AuthProvider"]] = relationship(
        "AuthProvider",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    emotion_sessions: Mapped[List["EmotionSession"]] = relationship(
        "EmotionSession",
        back_populates="user",
        lazy="dynamic",
    )
    playlists: Mapped[List["Playlist"]] = relationship(
        "Playlist",
        back_populates="user",
        lazy="dynamic",
    )
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    music_interactions: Mapped[List["UserMusicInteraction"]] = relationship(
        "UserMusicInteraction",
        back_populates="user",
        lazy="dynamic",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="dynamic",
    )

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index(
            "ix_users_email_active",
            "email",
            postgresql_where="deleted_at IS NULL",
        ),
        Index("ix_users_is_active", "is_active"),
        Index("ix_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"