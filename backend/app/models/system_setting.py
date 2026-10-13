"""System settings: one row, read as a singleton. D05.

The contract's Settings shape fixes the values: `sla_targets` (a
`first_response_hours`/`resolution_hours` pair for each Low, Medium, High, and
Critical priority), `max_attachment_bytes`, and `allowed_attachment_types`.
The shape carries no timestamps, but this table follows the project-wide
convention and keeps `created_at` and `updated_at`, because settings *are*
editable (`PATCH /settings`) and the change is audited by G01.

This is the one table that is not a collection: exactly one row exists, holding
the defaults `REQUIREMENTS.md` describes as "seeded defaults editable by an
admin". `is_singleton` plus its unique constraint is what makes a second row
impossible, and it keeps the UUID primary key convention the other tables follow.

Tickets do **not** read their deadlines from here at read time: D02 copies the
targets onto the ticket when it is created, so editing settings never rewrites an
existing deadline.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.role import utc_now


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        CheckConstraint("is_singleton", name="is_singleton_true"),
        # Every priority the SLA table in REQUIREMENTS.md names must be present
        # as a key; the inner pair of hours is the API's to validate.
        CheckConstraint(
            "sla_targets->>'Low' IS NOT NULL AND sla_targets->>'Medium' IS NOT NULL "
            "AND sla_targets->>'High' IS NOT NULL "
            "AND sla_targets->>'Critical' IS NOT NULL",
            name="sla_targets_priorities",
        ),
        CheckConstraint("max_attachment_bytes > 0", name="max_attachment_bytes_positive"),
        CheckConstraint(
            "cardinality(allowed_attachment_types) >= 1",
            name="allowed_attachment_types_not_empty",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    is_singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, unique=True
    )
    sla_targets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    max_attachment_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allowed_attachment_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
