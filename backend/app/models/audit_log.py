"""Append-only audit log. D04.

The contract's AuditLog shape fixes these columns: id, actor_id, action,
entity_type, entity_id, old_value, new_value, created_at. There is no
`updated_at`, because no route creates, updates, or deletes an audit record
directly: each entry is written in the same transaction as the change it
describes, so a rolled-back change leaves no entry.

`actor_id` is nullable because a failed sign-in has no actor: the attempted email
is stored in `new_value` instead.

The `action` and `entity_type` vocabularies are deliberately **not** constrained
here. The contract names filter values but never fixes the set, and G01 owns the
exact strings; inventing them in the schema would freeze a vocabulary nobody has
agreed. `entity_id` has no foreign key for the same reason it can point at
different tables: it identifies whatever `entity_type` names.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.role import utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("btrim(action) <> ''", name="action_not_blank"),
        CheckConstraint("btrim(entity_type) <> ''", name="entity_type_not_blank"),
        # GET /audit-logs pages newest first, and a record's own history is
        # looked up by (entity_type, entity_id).
        Index(None, "created_at"),
        Index(None, "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # JSONB rather than JSON: the contract says "nullable JSON", and only JSONB
    # can be indexed if a later report needs to query inside a value.
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
