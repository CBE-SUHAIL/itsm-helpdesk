"""D01: create users and roles

Revision ID: 20261010_0001_d01_users_roles
Revises: 20261008_2150_baseline
Create Date: 2026-10-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261010_0001_d01_users_roles"
down_revision: Union[str, Sequence[str], None] = "20261008_2150_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "name IN ('Employee', 'Support agent', 'Admin')",
            name=op.f("ck_roles_name_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_users_name_not_blank")),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''",
            name=op.f("ck_users_email_normalized"),
        ),
        sa.CheckConstraint(
            "btrim(password_hash) <> ''",
            name=op.f("ck_users_password_hash_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="RESTRICT",
            name=op.f("fk_users_role_id_roles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_users_role_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
