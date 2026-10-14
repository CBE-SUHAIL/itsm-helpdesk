"""Ticket categories. Admin-managed, deactivated rather than deleted.

D02. The contract's Category shape fixes these columns: id, name, description,
is_active, created_at, updated_at. A ticket always points at one category, so
the foreign key on tickets is restrictive: a category in use cannot be removed.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.knowledge_article import KnowledgeArticle
    from app.models.ticket import Ticket
from app.models.role import utc_now


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        UniqueConstraint("name"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Required by the contract: the Category shape always carries a description
    # and never marks it nullable. An empty string is allowed, a null is not.
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # D07. Articles reuse this table, so a category that is deactivated rather
    # than deleted keeps both its tickets and its articles attributable.
    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="category")
    knowledge_articles: Mapped[list["KnowledgeArticle"]] = relationship(
        "KnowledgeArticle", back_populates="category"
    )
