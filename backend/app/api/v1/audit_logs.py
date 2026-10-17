"""G01: the read side of the append-only audit log.

Writes happen through `app/core/audit.record_audit`, called inside the
transaction of the change it describes, so a rolled-back change leaves no entry.
This module exposes the one route `docs/API_CONTRACT.md` allows: an admin-only
`GET /audit-logs`. No route creates, updates, or deletes an entry directly.

The `action` and `entity_type` vocabularies are documented in
`app/core/audit.py` rather than constrained in the schema, because the contract
names them as filter values without fixing the set. An unknown filter value is
therefore a valid query that matches nothing, not a 422.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import AuditLogOut, AuditLogPage
from app.core.db import get_db
from app.core.security import require_roles
from app.models import AuditLog, User


router = APIRouter(tags=["audit"])


@router.get(
    "/audit-logs",
    response_model=AuditLogPage,
    summary="Read the audit log",
)
def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    _: User = Depends(require_roles("Admin")),
    session: Session = Depends(get_db),
) -> AuditLogPage:
    """Newest first. Admin only; the filters are exact matches on the columns.

    A failed sign-in has no actor, so `actor_id` is nullable in the response and
    `actor_id=` as a filter matches the entries that have that actor.
    """
    where = []
    if actor_id is not None:
        where.append(AuditLog.actor_id == actor_id)
    if action is not None:
        where.append(AuditLog.action == action)
    if entity_type is not None:
        where.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        where.append(AuditLog.entity_id == entity_id)
    if created_from is not None:
        where.append(AuditLog.created_at >= created_from)
    if created_to is not None:
        where.append(AuditLog.created_at <= created_to)

    total = (
        session.scalar(select(func.count()).select_from(AuditLog).where(*where)) or 0
    )
    entries = session.scalars(
        select(AuditLog)
        .where(*where)
        # Several entries can share a timestamp, so `id` breaks the tie and
        # keeps paging reproducible between reads.
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditLogPage(
        items=[AuditLogOut.from_audit(entry) for entry in entries], total=total
    )
