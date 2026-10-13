"""D03: create comments and ticket_history

Revision ID: 20261014_d03_comments_history
Revises: 20261014_d02_tickets_categories
Create Date: 2026-10-14

Both tables are append-only in practice: neither has `updated_at`, because a
comment is never edited (the contract has no comment update route) and history
rows are written once, in the same transaction as the change they describe.

`ticket_history.field` is limited to the four change kinds the contract names:
status, assignee, category, and priority. `reason` is where the resolution note
lands, since the contract's Ticket shape has no resolution-note field.

Each table carries one composite index on (ticket_id, created_at): the contract's
two read routes filter by ticket and order oldest first, so one index serves both
the filter and the ordering. The revision id is 29 characters, inside the
`varchar(32)` limit on `alembic_version.version_num` that D02 documented.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_d03_comments_history"
down_revision: Union[str, Sequence[str], None] = "20261014_d02_tickets_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(body) <> ''", name=op.f("ck_comments_body_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            ondelete="RESTRICT",
            name=op.f("fk_comments_ticket_id_tickets"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_comments_author_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_table(
        "ticket_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.String(length=64), nullable=True),
        sa.Column("new_value", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "field IN ('status', 'assignee_id', 'category_id', 'priority')",
            name=op.f("ck_ticket_history_field_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            ondelete="RESTRICT",
            name=op.f("fk_ticket_history_ticket_id_tickets"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_ticket_history_actor_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_history")),
    )
    op.create_index(
        op.f("ix_comments_ticket_id_created_at"),
        "comments",
        ["ticket_id", "created_at"],
    )
    op.create_index(
        op.f("ix_ticket_history_ticket_id_created_at"),
        "ticket_history",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ticket_history_ticket_id_created_at"), table_name="ticket_history"
    )
    op.drop_index(op.f("ix_comments_ticket_id_created_at"), table_name="comments")
    op.drop_table("ticket_history")
    op.drop_table("comments")
