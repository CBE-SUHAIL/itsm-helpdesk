"""D05: create notifications and system_settings, and seed the settings row

Revision ID: 20261014_d05_notify_settings
Revises: 20261014_d04_attachments_audit
Create Date: 2026-10-14

`notifications` holds read and dismissed as two independent nullable timestamps,
which is the F02 decision: read leaves the notification listed, dismiss removes
it from the default list, and neither is a delete.

`system_settings` is a singleton: `is_singleton` plus its unique constraint makes
a second row impossible while keeping the UUID primary key convention.

This is the first migration that writes a row rather than only schema. It seeds
the single settings row with the defaults REQUIREMENTS.md documents, so the SLA
targets and attachment limits exist before any ticket needs them, and
`PATCH /settings` edits that row in place. Demo *users and tickets* stay in D08;
this is reference data the system cannot run without.

The revision id is 28 characters, inside the varchar(32) limit on
`alembic_version.version_num` that D02 discovered.
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_d05_notify_settings"
down_revision: Union[str, Sequence[str], None] = "20261014_d04_attachments_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The one settings row. A fixed UUID, so the API can address it without a lookup
# by "the only row".
SETTINGS_ROW_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# From the SLA table in REQUIREMENTS.md. Calendar hours, and the values a ticket
# copies onto itself at creation.
DEFAULT_SLA_TARGETS = {
    "Low": {"first_response_hours": 24, "resolution_hours": 72},
    "Medium": {"first_response_hours": 8, "resolution_hours": 48},
    "High": {"first_response_hours": 2, "resolution_hours": 24},
    "Critical": {"first_response_hours": 1, "resolution_hours": 8},
}
DEFAULT_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DEFAULT_ALLOWED_ATTACHMENT_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
]


def _settings_table() -> sa.TableClause:
    """A lightweight table for the seed insert, typed so values are serialised."""
    return sa.table(
        "system_settings",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("is_singleton", sa.Boolean),
        sa.column("sla_targets", postgresql.JSONB),
        sa.column("max_attachment_bytes", sa.BigInteger),
        sa.column("allowed_attachment_types", postgresql.ARRAY(sa.Text)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(message) <> ''", name=op.f("ck_notifications_message_not_blank")
        ),
        sa.CheckConstraint(
            "type IN ('assignment', 'comment', 'resolution', 'closure', 'sla_breach')",
            name=op.f("ck_notifications_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_notifications_recipient_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            ondelete="RESTRICT",
            name=op.f("fk_notifications_ticket_id_tickets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_singleton", sa.Boolean(), nullable=False),
        sa.Column("sla_targets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_attachment_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "allowed_attachment_types", postgresql.ARRAY(sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "is_singleton", name=op.f("ck_system_settings_is_singleton_true")
        ),
        sa.CheckConstraint(
            "sla_targets->>'Low' IS NOT NULL AND sla_targets->>'Medium' IS NOT NULL "
            "AND sla_targets->>'High' IS NOT NULL "
            "AND sla_targets->>'Critical' IS NOT NULL",
            name=op.f("ck_system_settings_sla_targets_priorities"),
        ),
        sa.CheckConstraint(
            "max_attachment_bytes > 0",
            name=op.f("ck_system_settings_max_attachment_bytes_positive"),
        ),
        sa.CheckConstraint(
            "cardinality(allowed_attachment_types) >= 1",
            name=op.f("ck_system_settings_allowed_attachment_types_not_empty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_settings")),
        sa.UniqueConstraint(
            "is_singleton", name=op.f("uq_system_settings_is_singleton")
        ),
    )
    op.create_index(
        op.f("ix_notifications_recipient_id_created_at"),
        "notifications",
        ["recipient_id", "created_at"],
    )
    op.execute(
        _settings_table()
        .insert()
        .values(
            id=SETTINGS_ROW_ID,
            is_singleton=True,
            sla_targets=DEFAULT_SLA_TARGETS,
            max_attachment_bytes=DEFAULT_MAX_ATTACHMENT_BYTES,
            allowed_attachment_types=DEFAULT_ALLOWED_ATTACHMENT_TYPES,
            created_at=sa.func.now(),
            updated_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_recipient_id_created_at"), table_name="notifications"
    )
    # Dropping the table drops the seeded row with it; no delete needed.
    op.drop_table("system_settings")
    op.drop_table("notifications")
