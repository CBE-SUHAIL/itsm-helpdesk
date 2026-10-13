"""Ticket comments. D03.

The contract's Comment shape fixes these columns: id, ticket_id, author_id,
body, created_at. There is no `updated_at` because there is no
`PATCH /tickets/{id}/comments` route: a comment is never edited, and there is no
delete route either, so the row is written once and only ever read.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.role import utc_now


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("btrim(body) <> ''", name="body_not_blank"),
        # GET /tickets/{id}/comments filters by ticket and orders oldest first,
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
    author_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
