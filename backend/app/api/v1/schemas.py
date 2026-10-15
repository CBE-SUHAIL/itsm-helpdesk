"""Strict request and response shapes for A01–A07, T01–T07, S01, and G01."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.sla import resolution_overdue, response_overdue
from app.models import (
    AuditLog,
    Comment,
    Notification,
    Ticket,
    TicketHistory,
    User,
)


RoleName = Literal["Employee", "Support agent", "Admin"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserOut(StrictModel):
    id: UUID
    name: str
    email: str
    role: RoleName
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id, name=user.name, email=user.email,
            role=user.role.name, is_active=user.is_active,
            created_at=user.created_at, updated_at=user.updated_at,
        )


class LoginIn(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RefreshIn(StrictModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(StrictModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class LoginOut(TokenPair):
    user: UserOut


class CreateUserIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    role: RoleName

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or not all(value.split("@")) or " " in value:
            raise ValueError("Invalid email")
        return value

    @field_validator("password")
    @classmethod
    def clean_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class UpdateUserIn(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: RoleName | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("At least one non-null field is required")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class UserPage(StrictModel):
    items: list[UserOut]
    total: int


# --- T01–T04: tickets -------------------------------------------------------

TicketStatus = Literal["Open", "Assigned", "In Progress", "Resolved", "Closed"]
Priority = Literal["Low", "Medium", "High", "Critical"]
HistoryField = Literal["status", "assignee_id", "category_id", "priority"]
NotificationType = Literal[
    "assignment", "comment", "resolution", "closure", "sla_breach"
]


def _strip_not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Must not be blank")
    return value


class TicketOut(StrictModel):
    id: UUID
    title: str
    description: str
    category_id: UUID
    creator_id: UUID
    assignee_id: UUID | None
    status: TicketStatus
    priority: Priority
    response_due_at: datetime
    resolution_due_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    response_overdue: bool
    resolution_overdue: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_ticket(cls, ticket: Ticket, now: datetime | None = None) -> "TicketOut":
        return cls(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            category_id=ticket.category_id,
            creator_id=ticket.creator_id,
            assignee_id=ticket.assignee_id,
            status=ticket.status,
            priority=ticket.priority,
            response_due_at=ticket.response_due_at,
            resolution_due_at=ticket.resolution_due_at,
            first_response_at=ticket.first_response_at,
            resolved_at=ticket.resolved_at,
            response_overdue=response_overdue(ticket, now),
            resolution_overdue=resolution_overdue(ticket, now),
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )


class TicketPage(StrictModel):
    items: list[TicketOut]
    total: int


class CreateTicketIn(StrictModel):
    """`extra="forbid"` is what rejects a `priority` field for every role."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    category_id: UUID

    @field_validator("title", "description")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _strip_not_blank(value)


class AssignmentIn(StrictModel):
    """A required key that may be null: null unassigns and is admin-only."""

    assignee_id: UUID | None


class StatusIn(StrictModel):
    status: TicketStatus
    resolution_note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def note_when_resolving(self):
        if self.status == "Resolved" and not (self.resolution_note or "").strip():
            raise ValueError("resolution_note is required when moving to Resolved")
        return self


class PriorityIn(StrictModel):
    priority: Priority
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _strip_not_blank(value)


class CategoryChangeIn(StrictModel):
    category_id: UUID
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _strip_not_blank(value)


# --- T06: comments and history ---------------------------------------------


class CommentIn(StrictModel):
    body: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        return _strip_not_blank(value)


class CommentOut(StrictModel):
    id: UUID
    ticket_id: UUID
    author_id: UUID
    body: str
    created_at: datetime

    @classmethod
    def from_comment(cls, comment: Comment) -> "CommentOut":
        return cls(
            id=comment.id,
            ticket_id=comment.ticket_id,
            author_id=comment.author_id,
            body=comment.body,
            created_at=comment.created_at,
        )


class CommentPage(StrictModel):
    items: list[CommentOut]
    total: int


class TicketHistoryOut(StrictModel):
    id: UUID
    ticket_id: UUID
    actor_id: UUID
    field: HistoryField
    old_value: str | None
    new_value: str | None
    reason: str | None
    created_at: datetime

    @classmethod
    def from_history(cls, entry: TicketHistory) -> "TicketHistoryOut":
        return cls(
            id=entry.id,
            ticket_id=entry.ticket_id,
            actor_id=entry.actor_id,
            field=entry.field,
            old_value=entry.old_value,
            new_value=entry.new_value,
            reason=entry.reason,
            created_at=entry.created_at,
        )


class TicketHistoryPage(StrictModel):
    items: list[TicketHistoryOut]
    total: int


# --- S01 and G01: notifications and audit reads -----------------------------


class NotificationOut(StrictModel):
    id: UUID
    recipient_id: UUID
    ticket_id: UUID | None
    type: NotificationType
    message: str
    read_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_notification(cls, notice: Notification) -> "NotificationOut":
        return cls(
            id=notice.id,
            recipient_id=notice.recipient_id,
            ticket_id=notice.ticket_id,
            type=notice.type,
            message=notice.message,
            read_at=notice.read_at,
            dismissed_at=notice.dismissed_at,
            created_at=notice.created_at,
        )


class NotificationPage(StrictModel):
    items: list[NotificationOut]
    total: int


class AuditLogOut(StrictModel):
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime

    @classmethod
    def from_audit(cls, entry: AuditLog) -> "AuditLogOut":
        return cls(
            id=entry.id,
            actor_id=entry.actor_id,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            old_value=entry.old_value,
            new_value=entry.new_value,
            created_at=entry.created_at,
        )


class AuditLogPage(StrictModel):
    items: list[AuditLogOut]
    total: int
