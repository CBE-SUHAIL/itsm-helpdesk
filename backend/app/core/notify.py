"""In-app notification rows. S01.

A notification is created in the **same transaction** as the event that caused
it, so a failed ticket change cannot leave a stray notice behind. Recipients are
chosen by this rule, which the ticket routes follow:

=================  ==========================================================
event              recipient
=================  ==========================================================
assignment         the newly assigned agent or admin
comment            the ticket's other participant: the creator unless the
                   commenter is the creator, plus the assignee unless the
                   commenter is the assignee
resolution         the ticket creator
closure            the ticket creator
sla_breach         the assignee when there is one, otherwise every admin
=================  ==========================================================

`REQUIREMENTS.md` fixes the five `type` values and the database enforces them.
Read and dismissed are independent states, so this module only ever writes the
row; the read and dismiss routes live in the notifications router.
"""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Notification, Role, Ticket, User
from app.models.role import utc_now
from app.core.sla import resolution_overdue, response_overdue


def notify(
    session: Session,
    *,
    recipient_id: UUID,
    message: str,
    type: str,
    ticket_id: UUID | None = None,
) -> Notification:
    """Add one notification to the caller's transaction; never commit here."""
    notice = Notification(
        recipient_id=recipient_id,
        ticket_id=ticket_id,
        type=type,
        message=message,
        created_at=utc_now(),
    )
    session.add(notice)
    return notice


def notify_admins(
    session: Session, *, message: str, type: str, ticket_id: UUID | None = None
) -> list[Notification]:
    """Notify every active admin, used when a breach has no assignee to tell."""
    admins = session.scalars(
        select(User).join(Role).where(Role.name == "Admin", User.is_active.is_(True))
    ).all()
    return [
        notify(
            session,
            recipient_id=admin.id,
            message=message,
            type=type,
            ticket_id=ticket_id,
        )
        for admin in admins
    ]


def scan_sla_breaches(session: Session) -> int:
    """Create one alert per breached ticket/recipient when an inbox is polled.

    The local-only app has no queue or external scheduler. A transaction-level
    PostgreSQL lock keeps simultaneous polls from creating duplicate notices.
    """
    session.execute(text("SELECT pg_advisory_xact_lock(1758667291)"))
    now = utc_now()
    candidates = session.scalars(
        select(Ticket).where(
            (Ticket.response_due_at < now) | (Ticket.resolution_due_at < now)
        )
    ).all()
    count = 0
    for ticket in candidates:
        if not (response_overdue(ticket, now) or resolution_overdue(ticket, now)):
            continue
        if ticket.assignee_id is not None:
            recipients = [ticket.assignee_id]
        else:
            recipients = session.scalars(
                select(User.id).join(Role).where(
                    Role.name == "Admin", User.is_active.is_(True)
                )
            ).all()
        for recipient_id in recipients:
            exists = session.scalar(
                select(Notification.id).where(
                    Notification.ticket_id == ticket.id,
                    Notification.recipient_id == recipient_id,
                    Notification.type == "sla_breach",
                ).limit(1)
            )
            if exists is None:
                notify(session, recipient_id=recipient_id, ticket_id=ticket.id,
                       type="sla_breach", message=f"SLA deadline missed for ticket: {ticket.title}")
                count += 1
    if count:
        session.commit()
    return count
