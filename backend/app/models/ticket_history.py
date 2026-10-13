"""Immutable ticket history, one row per changed field. D03.

The contract's TicketHistory shape fixes these columns: id, ticket_id, actor_id,
field, old_value, new_value, reason, created_at. There is deliberately no
`updated_at`: the table is append-only, written in the same transaction as the
change it describes, so a rolled-back change leaves no entry.

`reason` is where the resolution note lives — the contract's Ticket shape has no
such field, while `POST /tickets/{id}/status` requires one when moving to
Resolved (see docs/DATA_MODEL.md).

`old_value` and `new_value` are text: a status or priority label, or the string
form of a UUID for assignee and category changes.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.role import utc_now


class TicketHistory(Base):
    __tablename__ = "ticket_history"
    __table_args__ = (
        CheckConstraint(
            "field IN ('status', 'assignee_id', 'category_id', 'priority')",
            name="field_allowed",
        ),
        # GET /tickets/{id}/history filters by ticket and orders oldest first,
        # so one composite index serves both the filter and the ordering.
        Index(None, "ticket_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
