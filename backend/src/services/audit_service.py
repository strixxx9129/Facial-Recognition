"""
Audit logging service — writes immutable AuditLog records.
"""
import logging
import uuid
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Persist a single immutable audit event.

    Never raises — failures are logged as warnings so that a broken audit
    trail never rolls back a legitimate user action.
    """
    try:
        ip_address: Optional[str] = None
        user_agent: Optional[str] = None
        request_id: Optional[str] = None

        if request is not None:
            # Respect X-Forwarded-For set by a trusted reverse proxy
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                ip_address = forwarded_for.split(",")[0].strip()
            else:
                ip_address = (
                    request.client.host if request.client else None
                )
            user_agent = request.headers.get("User-Agent")
            request_id = request.headers.get("X-Request-ID")

        entry = AuditLog(
            action=action,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        db.add(entry)
        await db.flush()  # flush so the record is written inside the caller's txn

    except Exception:
        logger.warning("Failed to write audit log for action=%r", action, exc_info=True)