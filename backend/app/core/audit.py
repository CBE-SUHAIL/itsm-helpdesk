"""Append-only audit records. G01.

`REQUIREMENTS.md` and `API_CONTRACT.md` agree on the rule this module enforces:
one entry is written **in the same transaction as the change it describes**, so
a rolled-back change leaves no entry, and no route ever updates or deletes one.

`action` and `entity_type` are deliberately free strings — `docs/DATA_MODEL.md`
leaves the vocabulary to this row rather than freezing it in the schema. The
strings used by the API are:

===============  =================  ===========================================
action           entity_type        written by
===============  =================  ===========================================
login_success    user               POST /auth/login        (A01)
login_failure    auth               POST /auth/login        (A01)
user_create      user               POST /users             (A06)
user_update      user               PATCH /users/{id}        (A06)
ticket_create    ticket             POST /tickets           (T01)
ticket_update    ticket             status, assignment, priority, category
settings_update  settings           PATCH /settings          (unassigned)
===============  =================  ===========================================

Ticket changes reuse the single `ticket_update` action with the changed field in
`old_value`/`new_value`, because `ticket_history` already records each field
change in detail; the audit entry records that the change happened, by whom.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.role import utc_now


def record_audit(
    session: Session,
    *,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    """Add one audit entry to the caller's transaction; never commit here."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        created_at=utc_now(),
    )
    session.add(entry)
    return entry
