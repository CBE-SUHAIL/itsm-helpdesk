"""Tickets, the core table. D02.

The contract's Ticket shape fixes these columns. Two of them are worth reading
before editing anything here:

- `response_due_at` and `resolution_due_at` are **copied onto the ticket when it
  is created**, from the SLA targets in force at that moment. They are never
  recomputed on read, so a later settings change cannot rewrite an existing
  deadline.
- `response_overdue` and `resolution_overdue` appear in the ticket *response*
  but are derived from those deadlines and the clock, so they are deliberately
  **not** columns here (see docs/DATA_MODEL.md).

Status and priority are text plus a check constraint rather than PostgreSQL
`enum` types, the F05 convention for every closed set. The allowed values match
REQUIREMENTS.md exactly. The legal *transitions* between them are business rules
owned by T02, not a database constraint.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.category import Category
    from app.models.comment import Comment
    from app.models.notification import Notification
    from app.models.ticket_history import TicketHistory
    from app.models.user import User
from app.models.role import utc_now


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Open', 'Assigned', 'In Progress', 'Resolved', 'Closed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name="priority_allowed",
        ),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(description) <> ''", name="description_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable: a ticket starts unassigned and only an agent or admin assigns it.
    assignee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Open")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="Medium")
    response_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolution_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    first_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # D07. `creator` and `assignee` both point at users, so each relationship
    # names its foreign key explicitly rather than relying on inference.
    category: Mapped["Category"] = relationship("Category", back_populates="tickets")
    creator: Mapped["User"] = relationship(
        "User", back_populates="tickets_created", foreign_keys="Ticket.creator_id"
    )
    assignee: Mapped["User | None"] = relationship(
        "User", back_populates="tickets_assigned", foreign_keys="Ticket.assignee_id"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="ticket"
    )
    history: Mapped[list["TicketHistory"]] = relationship(
        "TicketHistory", back_populates="ticket"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="ticket"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="ticket"
    )
