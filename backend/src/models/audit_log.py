# app/models/audit_log.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, UUIDMixin):
    """
    Immutable audit trail — never updated or soft-deleted.
    Partitioned by created_at month in production for retention management.
    """
    __tablename__ = "audit_logs"

    # Nullable: system-level actions may not have a user
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Dot-namespaced action: 'user.login', 'session.revoke', 'emotion.session.start'
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # ORM model name of the affected entity, e.g. 'User', 'Session'
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # PK of the affected entity
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # Full JSONB snapshot before change (null for create actions)
    before_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Full JSONB snapshot after change (null for delete actions)
    after_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Correlation ID for tracing across services
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    # ── Constraints & Indexes ────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_audit_logs_action_date", "action", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_user_date", "user_id", "created_at"),
        Index("ix_audit_logs_request_id", "request_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action} "
            f"user_id={self.user_id} entity={self.entity_type}:{self.entity_id}>"
        )