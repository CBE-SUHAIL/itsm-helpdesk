"""D06: create knowledge_articles

Revision ID: 20261014_d06_knowledge_articles
Revises: 20261014_d05_notify_settings
Create Date: 2026-10-14

Articles reuse the existing categories table. Category and author references
are restrictive so published content never loses its attribution or category.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261014_d06_knowledge_articles"
down_revision: Union[str, Sequence[str], None] = "20261014_d05_notify_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(title) <> ''", name=op.f("ck_knowledge_articles_title_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(body) <> ''", name=op.f("ck_knowledge_articles_body_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT",
            name=op.f("fk_knowledge_articles_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], ondelete="RESTRICT",
            name=op.f("fk_knowledge_articles_author_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_articles")),
    )
    op.create_index(op.f("ix_knowledge_articles_category_id"), "knowledge_articles", ["category_id"])
    op.create_index(op.f("ix_knowledge_articles_author_id"), "knowledge_articles", ["author_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_articles_author_id"), table_name="knowledge_articles")
    op.drop_index(op.f("ix_knowledge_articles_category_id"), table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
