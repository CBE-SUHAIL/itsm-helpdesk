"""Ticket routes: create, read, lifecycle, assignment, priority, comments, history.

Covers checklist rows T01 (create/read/update), T02 (lifecycle transitions),
T03 (assign and reassign), T04 (priority and SLA), and T06 (comments and
history). Every change writes ticket history, an audit entry, and any
notifications **in the same transaction**, so a rejected change leaves none of
them behind; `docs/API_CONTRACT.md` requires exactly that.

Authorization is enforced here, never by the React app:

- an employee sees only tickets they created;
- an agent and an admin see every ticket, but an agent may only act on the
  ticket they are assigned;
- role checks reuse the A03 `current_user` and `require_roles` dependencies.
"""

from typing import Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    AssignmentIn,
    CategoryChangeIn,
    CommentIn,
    CommentOut,
    CommentPage,
    CreateTicketIn,
    Priority,
    PriorityIn,
    StatusIn,
    TicketHistoryOut,
    TicketHistoryPage,
    TicketOut,
    TicketPage,
    TicketStatus,
)
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.notify import notify
from app.core.security import current_user, require_roles
from app.core.sla import (
    SlaNotConfigured,
    deadlines_for,
    get_settings_row,
    sla_unavailable,
)
from app.models import Category, Comment, Ticket, TicketHistory, User
from app.models.role import utc_now


router = APIRouter(tags=["tickets"])

EMPLOYEE = "Employee"
AGENT = "Support agent"
ADMIN = "Admin"

OPEN = "Open"
ASSIGNED = "Assigned"
IN_PROGRESS = "In Progress"
RESOLVED = "Resolved"
CLOSED = "Closed"

# `REQUIREMENTS.md`: no role chooses priority at creation, so a new ticket is
# always Medium and its deadlines come from Medium's targets.
DEFAULT_PRIORITY = "Medium"

# A ticket may be assigned only while it is in one of these states.
ASSIGNABLE_STATES = (OPEN, ASSIGNED, IN_PROGRESS)


def _text(value: Any) -> str | None:
    """History stores labels and the string form of a UUID, never an object."""
    return None if value is None else str(value)


def sees_every_ticket(user: User) -> bool:
    return user.role.name in (AGENT, ADMIN)


def visible_ticket_or_404(session: Session, ticket_id: UUID, user: User) -> Ticket:
    """Load a ticket the caller may read, hiding other people's tickets as 404.

    The contract asks for 404 rather than 403 on an inaccessible ticket, so an
    employee cannot probe for the existence of someone else's ticket IDs.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or not (
        sees_every_ticket(user) or ticket.creator_id == user.id
    ):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def add_history(
    session: Session,
    ticket: Ticket,
    actor_id: UUID,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str | None,
    now: datetime,
) -> TicketHistory:
    entry = TicketHistory(
        ticket_id=ticket.id,
        actor_id=actor_id,
        field=field,
        old_value=_text(old_value),
        new_value=_text(new_value),
        reason=reason,
        created_at=now,
    )
    session.add(entry)
    return entry


def apply_changes(
    session: Session,
    ticket: Ticket,
    actor: User,
    changes: dict[str, tuple[Any, Any]],
    *,
    reason: str | None = None,
    now: datetime,
) -> bool:
    """Record one history row per changed field and one audit entry.

    Returns False when nothing actually changed, so a no-op request writes
    neither history nor audit. `ticket_history` is one row per changed field;
    the audit log records that the change happened and who made it.
    """
    if not changes:
        return False
    for changed_field, (old_value, new_value) in changes.items():
        add_history(
            session, ticket, actor.id, changed_field, old_value, new_value, reason, now
        )
    record_audit(
        session,
        actor_id=actor.id,
        action="ticket_update",
        entity_type="ticket",
        entity_id=ticket.id,
        old_value={key: _text(pair[0]) for key, pair in changes.items()},
        new_value={key: _text(pair[1]) for key, pair in changes.items()},
    )
    ticket.updated_at = now
    return True


@router.get("/tickets", response_model=TicketPage, summary="List tickets")
def list_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: TicketStatus | None = Query(default=None),
    priority: Priority | None = Query(default=None),
    category_id: UUID | None = None,
    assignee_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> TicketPage:
    """Newest first. An employee is scoped to their own tickets before filters."""
    where: list[Any] = []
    if not sees_every_ticket(user):
        where.append(Ticket.creator_id == user.id)
    if status is not None:
        where.append(Ticket.status == status)
    if priority is not None:
        where.append(Ticket.priority == priority)
    if category_id is not None:
        where.append(Ticket.category_id == category_id)
    if assignee_id is not None:
        where.append(Ticket.assignee_id == assignee_id)
    if created_from is not None:
        where.append(Ticket.created_at >= created_from)
    if created_to is not None:
        where.append(Ticket.created_at <= created_to)

    total = (
        session.scalar(select(func.count()).select_from(Ticket).where(*where)) or 0
    )
    tickets = session.scalars(
        select(Ticket)
        .where(*where)
        .order_by(Ticket.created_at.desc(), Ticket.id)
        .limit(limit)
        .offset(offset)
    ).all()
    now = utc_now()
    return TicketPage(
        items=[TicketOut.from_ticket(ticket, now) for ticket in tickets], total=total
    )


@router.post("/tickets", response_model=TicketOut, status_code=201, summary="Create a ticket")
def create_ticket(
    data: CreateTicketIn,
    user: User = Depends(require_roles(EMPLOYEE)),
    session: Session = Depends(get_db),
) -> TicketOut:
    """Employees create tickets. Priority is never accepted and starts Medium."""
    category = session.get(Category, data.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Category is inactive")
    # One clock reading: the deadlines must be exactly relative to created_at.
    now = utc_now()
    try:
        settings = get_settings_row(session)
        response_due, resolution_due = deadlines_for(settings, DEFAULT_PRIORITY, now)
    except SlaNotConfigured:
        raise sla_unavailable() from None
    ticket = Ticket(
        title=data.title,
        description=data.description,
        category_id=category.id,
        creator_id=user.id,
        assignee_id=None,
        status=OPEN,
        priority=DEFAULT_PRIORITY,
        response_due_at=response_due,
        resolution_due_at=resolution_due,
        created_at=now,
        updated_at=now,
    )
    session.add(ticket)
    session.flush()
    record_audit(
        session,
        actor_id=user.id,
        action="ticket_create",
        entity_type="ticket",
        entity_id=ticket.id,
        new_value={
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "category_id": _text(category.id),
        },
    )
    session.commit()
    return TicketOut.from_ticket(ticket, now)


@router.get("/tickets/{ticket_id}", response_model=TicketOut, summary="Read one ticket")
def get_ticket(
    ticket_id: UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> TicketOut:
    return TicketOut.from_ticket(visible_ticket_or_404(session, ticket_id, user))


@router.post(
    "/tickets/{ticket_id}/assignment",
    response_model=TicketOut,
    summary="Assign, reassign, or unassign a ticket",
)
def set_assignment(
    ticket_id: UUID,
    data: AssignmentIn,
    user: User = Depends(require_roles(AGENT, ADMIN)),
    session: Session = Depends(get_db),
) -> TicketOut:
    """T03. An agent self-assigns an unassigned Open ticket; an admin may
    reassign Open/Assigned/In Progress. A null assignee is admin-only and
    returns the ticket to Open."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    is_admin = user.role.name == ADMIN
    now = utc_now()
    changes: dict[str, tuple[Any, Any]] = {}

    if data.assignee_id is None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only an admin may unassign")
        if ticket.status not in (ASSIGNED, IN_PROGRESS):
            raise HTTPException(
                status_code=409, detail="Ticket cannot return to Open from its state"
            )
        previous = ticket.assignee_id
        if previous is not None:
            changes["assignee_id"] = (previous, None)
            notify(
                session,
                recipient_id=previous,
                ticket_id=ticket.id,
                type="assignment",
                message=f'You were unassigned from ticket "{ticket.title}".',
            )
        ticket.assignee_id = None
        if ticket.status != OPEN:
            changes["status"] = (ticket.status, OPEN)
            ticket.status = OPEN
    else:
        assignee = session.get(User, data.assignee_id)
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=400, detail="Invalid assignee")
        if assignee.role.name not in (AGENT, ADMIN):
            raise HTTPException(status_code=400, detail="Invalid assignee")
        if not is_admin:
            if assignee.id != user.id:
                raise HTTPException(
                    status_code=403, detail="An agent may only self-assign"
                )
            if ticket.status != OPEN or ticket.assignee_id is not None:
                raise HTTPException(
                    status_code=409, detail="Ticket is not open and unassigned"
                )
        if ticket.status not in ASSIGNABLE_STATES:
            raise HTTPException(
                status_code=409, detail="Ticket cannot be assigned in its state"
            )
        if ticket.assignee_id != assignee.id:
            changes["assignee_id"] = (ticket.assignee_id, assignee.id)
            notify(
                session,
                recipient_id=assignee.id,
                ticket_id=ticket.id,
                type="assignment",
                message=f'You were assigned ticket "{ticket.title}".',
            )
        if ticket.status == OPEN:
            changes["status"] = (OPEN, ASSIGNED)
            ticket.status = ASSIGNED
        ticket.assignee_id = assignee.id

    apply_changes(session, ticket, user, changes, now=now)
    session.commit()
    return TicketOut.from_ticket(ticket, now)


@router.post(
    "/tickets/{ticket_id}/status",
    response_model=TicketOut,
    summary="Move a ticket through its lifecycle",
)
def set_status(
    ticket_id: UUID,
    data: StatusIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> TicketOut:
    """T02. Only the assigned agent may start or resolve work; only the ticket's
    creator or an admin may close a Resolved ticket."""
    ticket = visible_ticket_or_404(session, ticket_id, user)
    is_admin = user.role.name == ADMIN
    is_assignee = ticket.assignee_id == user.id
    is_creator = ticket.creator_id == user.id
    now = utc_now()
    reason = (data.resolution_note or "").strip() or None
    previous = ticket.status

    if data.status == IN_PROGRESS:
        if ticket.status not in (ASSIGNED, RESOLVED):
            raise HTTPException(status_code=409, detail="Invalid status transition")
        if not is_assignee:
            raise HTTPException(
                status_code=403, detail="Only the assigned agent may start work"
            )
        if ticket.status == RESOLVED:
            # REQUIREMENTS: a returned ticket's previous resolution no longer counts.
            ticket.resolved_at = None
        ticket.status = IN_PROGRESS
    elif data.status == RESOLVED:
        if ticket.status != IN_PROGRESS:
            raise HTTPException(status_code=409, detail="Invalid status transition")
        if not is_assignee:
            raise HTTPException(
                status_code=403, detail="Only the assigned agent may resolve"
            )
        ticket.status = RESOLVED
        ticket.resolved_at = now
    elif data.status == CLOSED:
        if ticket.status != RESOLVED:
            raise HTTPException(status_code=409, detail="Invalid status transition")
        if not (is_creator or is_admin):
            raise HTTPException(
                status_code=403, detail="Only the creator or an admin may close"
            )
        ticket.status = CLOSED
    else:
        # Open and Assigned are reached through the assignment route, never here.
        raise HTTPException(status_code=409, detail="Invalid status transition")

    apply_changes(
        session,
        ticket,
        user,
        {"status": (previous, ticket.status)},
        reason=reason,
        now=now,
    )
    # Tell the creator their ticket moved on, unless they made the change.
    # `resolution` and `closure` are the types the database allows; the message
    # carries the past-tense wording instead.
    if ticket.creator_id != user.id and data.status in (RESOLVED, CLOSED):
        kind = "resolution" if data.status == RESOLVED else "closure"
        moved = "resolved" if data.status == RESOLVED else "closed"
        notify(
            session,
            recipient_id=ticket.creator_id,
            ticket_id=ticket.id,
            type=kind,
            message=f'Your ticket "{ticket.title}" was {moved}.',
        )

    session.commit()
    return TicketOut.from_ticket(ticket, now)


@router.post(
    "/tickets/{ticket_id}/priority",
    response_model=TicketOut,
    summary="Change priority with a reason",
)
def set_priority(
    ticket_id: UUID,
    data: PriorityIn,
    user: User = Depends(require_roles(AGENT, ADMIN)),
    session: Session = Depends(get_db),
) -> TicketOut:
    """T04. The assigned agent or an admin may reprioritise. Both deadlines are
    recomputed from the ticket's original `created_at` with the new priority's
    targets, because priority is what determines the deadlines."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if user.role.name != ADMIN and ticket.assignee_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the assigned agent or an admin may reprioritise"
        )
    if ticket.status == CLOSED:
        raise HTTPException(
            status_code=409, detail="A closed ticket cannot be reprioritised"
        )
    now = utc_now()
    if data.priority != ticket.priority:
        previous = ticket.priority
        ticket.priority = data.priority
        try:
            settings = get_settings_row(session)
            ticket.response_due_at, ticket.resolution_due_at = deadlines_for(
                settings, data.priority, ticket.created_at
            )
        except SlaNotConfigured:
            raise sla_unavailable() from None
        apply_changes(
            session,
            ticket,
            user,
            {"priority": (previous, data.priority)},
            reason=data.reason,
            now=now,
        )
    session.commit()
    return TicketOut.from_ticket(ticket, now)


@router.post(
    "/tickets/{ticket_id}/category",
    response_model=TicketOut,
    summary="Recategorise a ticket with a reason",
)
def set_category(
    ticket_id: UUID,
    data: CategoryChangeIn,
    user: User = Depends(require_roles(AGENT, ADMIN)),
    session: Session = Depends(get_db),
) -> TicketOut:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if user.role.name != ADMIN and ticket.assignee_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the assigned agent or an admin may recategorise"
        )
    category = session.get(Category, data.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Category is inactive")
    if ticket.status == CLOSED:
        raise HTTPException(
            status_code=409, detail="A closed ticket cannot be recategorised"
        )
    now = utc_now()
    if category.id != ticket.category_id:
        previous = ticket.category_id
        ticket.category_id = category.id
        apply_changes(
            session,
            ticket,
            user,
            {"category_id": (previous, category.id)},
            reason=data.reason,
            now=now,
        )
    session.commit()
    return TicketOut.from_ticket(ticket, now)


@router.get(
    "/tickets/{ticket_id}/comments",
    response_model=CommentPage,
    summary="List a ticket's comments",
)
def list_comments(
    ticket_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> CommentPage:
    ticket = visible_ticket_or_404(session, ticket_id, user)
    total = (
        session.scalar(
            select(func.count()).select_from(Comment).where(Comment.ticket_id == ticket.id)
        )
        or 0
    )
    comments = session.scalars(
        select(Comment)
        .where(Comment.ticket_id == ticket.id)
        .order_by(Comment.created_at, Comment.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return CommentPage(
        items=[CommentOut.from_comment(comment) for comment in comments], total=total
    )


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=CommentOut,
    status_code=201,
    summary="Comment on a ticket",
)
def add_comment(
    ticket_id: UUID,
    data: CommentIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> CommentOut:
    """T06. The ticket creator, its assigned agent, or an admin may comment.
    The first comment from the assigned agent is what counts as the first
    response for SLA purposes."""
    ticket = visible_ticket_or_404(session, ticket_id, user)
    is_admin = user.role.name == ADMIN
    is_creator = ticket.creator_id == user.id
    is_assignee = ticket.assignee_id == user.id
    if not (is_creator or is_assignee or is_admin):
        raise HTTPException(
            status_code=403, detail="Only the ticket's people may comment"
        )

    now = utc_now()
    comment = Comment(
        ticket_id=ticket.id, author_id=user.id, body=data.body, created_at=now
    )
    session.add(comment)
    session.flush()

    if is_assignee and ticket.first_response_at is None:
        ticket.first_response_at = now
        ticket.updated_at = now

    recipients = set()
    if not is_creator:
        recipients.add(ticket.creator_id)
    if ticket.assignee_id is not None and not is_assignee:
        recipients.add(ticket.assignee_id)
    for recipient_id in recipients:
        notify(
            session,
            recipient_id=recipient_id,
            ticket_id=ticket.id,
            type="comment",
            message=f'New comment on ticket "{ticket.title}".',
        )

    session.commit()
    return CommentOut.from_comment(comment)


@router.get(
    "/tickets/{ticket_id}/history",
    response_model=TicketHistoryPage,
    summary="List a ticket's change history",
)
def list_history(
    ticket_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> TicketHistoryPage:
    ticket = visible_ticket_or_404(session, ticket_id, user)
    total = (
        session.scalar(
            select(func.count())
            .select_from(TicketHistory)
            .where(TicketHistory.ticket_id == ticket.id)
        )
        or 0
    )
    entries = session.scalars(
        select(TicketHistory)
        .where(TicketHistory.ticket_id == ticket.id)
        # One action can change several fields at the same instant, so `field`
        # breaks the tie and keeps the timeline reproducible between reads.
        .order_by(TicketHistory.created_at, TicketHistory.field)
        .limit(limit)
        .offset(offset)
    ).all()
    return TicketHistoryPage(
        items=[TicketHistoryOut.from_history(entry) for entry in entries], total=total
    )
