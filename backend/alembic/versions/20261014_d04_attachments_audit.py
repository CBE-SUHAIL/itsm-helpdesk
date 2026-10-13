"""D04: create attachments and audit_logs

Revision ID: 20261014_d04_attachments_audit
Revises: 20261014_d03_comments_history
Create Date: 2026-10-14

`attachments` stores metadata only; the bytes live on disk under the configured
upload root (`uploads/`, which .gitignore already excludes) and the table keeps a
server-generated `storage_name` that no route returns. There is no `updated_at`
on either table: no attachment update or delete route exists, and audit entries
are append-only.

`audit_logs.actor_id` is nullable for a failed sign-in, which has no actor.
`entity_id` deliberately has no foreign key: it identifies whatever
`entity_type` names, so it cannot point at one table. `action` and `entity_type`
are unconstrained vocabularies owned by G01.

The audit-log index strategy, left open by the F05 draft, is one index on
`created_at` for the newest-first listing route and one on
`(entity_type, entity_id)` for a record's own history.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_d04_attachments_audit"
down_revision: Union[str, Sequence[str], None] = "20261014_d03_comments_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(file_name) <> ''", name=op.f("ck_attachments_file_name_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(storage_name) <> ''",
            name=op.f("ck_attachments_storage_name_not_blank"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0", name=op.f("ck_attachments_size_bytes_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attachments_ticket_id_tickets"),
        ),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attachments_uploader_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
        sa.UniqueConstraint(
            "storage_name", name=op.f("uq_attachments_storage_name")
        ),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(action) <> ''", name=op.f("ck_audit_logs_action_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(entity_type) <> ''", name=op.f("ck_audit_logs_entity_type_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_audit_logs_actor_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_attachments_ticket_id"), "attachments", ["ticket_id"])
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"])
    op.create_index(
        op.f("ix_audit_logs_entity_type_entity_id"),
        "audit_logs",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_entity_type_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_attachments_ticket_id"), table_name="attachments")
    op.drop_table("audit_logs")
    op.drop_table("attachments")
