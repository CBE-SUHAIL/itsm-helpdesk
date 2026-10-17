"""S01: read your notifications, mark them read, and dismiss them.

The write side is `app/core/notify.py`, which runs **inside the transaction of
the ticket change that caused the notification**; this router only reads rows
and mutates the two state timestamps. Read and dismissed are independent, which
is the F02 review decision: a notification may be read and still listed, or
dismissed without ever being read, and dismissing is not a delete.

Neither action writes ticket history or an audit entry, because
`REQUIREMENTS.md` calls personal UI state rather than an administrative action.

Everything here is scoped to `recipient_id == current_user.id`, so another
person's notification is a 404 rather than a 403: the same "do not reveal that
the record exists" rule the ticket routes follow.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import NotificationOut, NotificationPage
from app.core.db import get_db
from app.core.security import current_user
from app.models import Notification, User
from app.models.role import utc_now


router = APIRouter(tags=["notifications"])


def own_notification_or_404(
    session: Session, notification_id: UUID, user: User
) -> Notification:
    notice = session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user.id,
        )
    )
    if notice is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notice


@router.get(
    "/notifications",
    response_model=NotificationPage,
    summary="List your notifications",
)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_dismissed: bool = Query(default=False),
    unread_only: bool = Query(default=False),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> NotificationPage:
    """Newest first. Dismissed notifications are hidden unless asked for.

    `unread_only` filters on `read_at`, which is independent of dismissal, so
    "unread and not dismissed" is the default inbox view.
    """
    where = [Notification.recipient_id == user.id]
    if not include_dismissed:
        where.append(Notification.dismissed_at.is_(None))
    if unread_only:
        where.append(Notification.read_at.is_(None))

    total = (
        session.scalar(
            select(func.count()).select_from(Notification).where(*where)
        )
        or 0
    )
    notices = session.scalars(
        select(Notification)
        .where(*where)
        # Several notifications can share a timestamp, so `id` breaks the tie
        # and keeps paging reproducible between reads.
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return NotificationPage(
        items=[NotificationOut.from_notification(notice) for notice in notices],
        total=total,
    )


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark your notification read",
)
def mark_read(
    notification_id: UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> NotificationOut:
    """Set `read_at` once and leave it set.

    Marking an already-read notification read again succeeds and keeps the
    original timestamp, so the record still says when it was first read.
    """
    notice = own_notification_or_404(session, notification_id, user)
    if notice.read_at is None:
        notice.read_at = utc_now()
        session.commit()
    return NotificationOut.from_notification(notice)


@router.patch(
    "/notifications/{notification_id}/dismiss",
    response_model=NotificationOut,
    summary="Dismiss your notification",
)
def dismiss_notification(
    notification_id: UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> NotificationOut:
    """Set `dismissed_at` once and leave it set; the row is never deleted.

    Dismissing does not touch `read_at`, so a dismissed-but-unread notification
    is still a legitimate state.
    """
    notice = own_notification_or_404(session, notification_id, user)
    if notice.dismissed_at is None:
        notice.dismissed_at = utc_now()
        session.commit()
    return NotificationOut.from_notification(notice)
