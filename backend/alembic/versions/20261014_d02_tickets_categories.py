"""D02: create categories and tickets

Revision ID: 20261014_d02_tickets_categories
Revises: 20261010_0001_d01_users_roles
Create Date: 2026-10-14

The revision id carries no counter, unlike D01's: Alembic stores it in
`alembic_version.version_num`, which is `varchar(32)`, and
`20261014_0001_d02_tickets_categories` is 36 characters. Any later row must
keep its id to 32 characters or fewer.

Status and priority are text columns with check constraints, not PostgreSQL
enum types, following the F05 convention for closed sets. The allowed values
match REQUIREMENTS.md; the legal transitions between statuses are T02 business
rules and are deliberately not encoded here.

`tickets.response_due_at` and `tickets.resolution_due_at` are required: the API
copies the SLA targets in force at creation onto the row. The contract's
`response_overdue` and `resolution_overdue` fields are derived from these
deadlines and are not columns.

Indexes cover the three foreign keys only. `status` and `priority` are not
indexed: they hold 5 and 4 distinct values, so PostgreSQL prefers a sequential
scan at demo size. The model and this migration must declare the same indexes,
which is what `alembic check` enforces in tests/test_migrations.py.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_d02_tickets_categories"
down_revision: Union[str, Sequence[str], None] = "20261010_0001_d01_users_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_categories_name_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(title) <> ''", name=op.f("ck_tickets_title_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(description) <> ''", name=op.f("ck_tickets_description_not_blank")
        ),
        sa.CheckConstraint(
            "status IN ('Open', 'Assigned', 'In Progress', 'Resolved', 'Closed')",
            name=op.f("ck_tickets_status_allowed"),
        ),
        sa.CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name=op.f("ck_tickets_priority_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="RESTRICT",
            name=op.f("fk_tickets_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_tickets_creator_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_tickets_assignee_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index(op.f("ix_tickets_category_id"), "tickets", ["category_id"])
    op.create_index(op.f("ix_tickets_creator_id"), "tickets", ["creator_id"])
    op.create_index(op.f("ix_tickets_assignee_id"), "tickets", ["assignee_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_assignee_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_creator_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_category_id"), table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("categories")
