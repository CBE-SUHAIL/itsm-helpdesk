"""Attachment metadata. D04.

The contract's Attachment shape fixes these columns: id, ticket_id, uploader_id,
file_name, content_type, size_bytes, created_at — and says the storage path is
never returned. The bytes do not live in PostgreSQL, so the table carries one
column the contract deliberately hides: `storage_name`, a server-generated name
resolved against the configured upload root at read time.

No `updated_at`: there is no attachment update or delete route in v1, so a row is
written once and only read.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.user import User
from app.models.role import utc_now


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("btrim(file_name) <> ''", name="file_name_not_blank"),
        CheckConstraint(
            "btrim(storage_name) <> ''", name="storage_name_not_blank"
        ),
        # The API enforces the upper limit from settings; the database only
        # rejects the nonsense value.
        CheckConstraint("size_bytes >= 0", name="size_bytes_not_negative"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    uploader_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # The client's original name, for display only. Never used to build a path.
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Generated server-side, unique, stored without any directory part, and
    # never returned by a route. See the D04 decision on storage layout.
    storage_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="attachments")
    uploader: Mapped["User"] = relationship("User", back_populates="attachments")
