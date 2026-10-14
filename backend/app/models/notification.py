"""In-app notifications. D05.

The contract's Notification shape fixes these columns: id, recipient_id,
ticket_id (nullable), type, message, read_at (nullable), dismissed_at
(nullable), created_at.

Read and dismissed are **independent** states, which is the F02 review decision:
a notification may be read and still listed, or dismissed without being read.
Both are timestamps, so neither loses when it happened, and dismissing is not a
delete.

`ticket_id` is nullable because not every notification is about a ticket.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.user import User
from app.models.role import utc_now


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('assignment', 'comment', 'resolution', 'closure', 'sla_breach')",
            name="type_allowed",
        ),
        CheckConstraint("btrim(message) <> ''", name="message_not_blank"),
        # The default list is the current user's notifications, newest first,
        # with dismissed ones filtered in or out. One composite index serves it.
        Index(None, "recipient_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    recipient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ticket_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    recipient: Mapped["User"] = relationship("User", back_populates="notifications")
    # Optional: not every notification is about a ticket.
    ticket: Mapped["Ticket | None"] = relationship(
        "Ticket", back_populates="notifications"
    )
