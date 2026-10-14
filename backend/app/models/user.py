"""Users remain in the database when deactivated so ticket history survives."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.audit_log import AuditLog
    from app.models.comment import Comment
    from app.models.knowledge_article import KnowledgeArticle
    from app.models.notification import Notification
    from app.models.role import Role
    from app.models.ticket import Ticket
    from app.models.ticket_history import TicketHistory
from app.models.role import utc_now


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''", name="email_normalized"
        ),
        CheckConstraint("btrim(password_hash) <> ''", name="password_hash_not_blank"),
        UniqueConstraint("email"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # D07. Two of these point at tickets, so each side names its foreign key
    # explicitly; no other relationship in the model is ambiguous.
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    tickets_created: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="creator", foreign_keys="Ticket.creator_id"
    )
    tickets_assigned: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="assignee", foreign_keys="Ticket.assignee_id"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="author"
    )
    ticket_history_entries: Mapped[list["TicketHistory"]] = relationship(
        "TicketHistory", back_populates="actor"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="uploader"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="actor"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="recipient"
    )
    knowledge_articles: Mapped[list["KnowledgeArticle"]] = relationship(
        "KnowledgeArticle", back_populates="author"
    )
