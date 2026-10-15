"""SLA deadlines and the derived overdue flags. T04.

`REQUIREMENTS.md` fixes the rule: SLA time is **calendar hours from ticket
creation**, the first public comment from the assigned agent counts as the
response, and resolution time is when the status first becomes Resolved.

Two consequences shape this module:

- Deadlines are **copied onto the ticket** rather than looked up while
  serialising it. `POST /tickets` writes them from the targets in force at that
  moment, so a later settings change cannot rewrite an existing deadline.
- `POST /tickets/{id}/priority` is the one route that moves them, because
  "priority determines deadlines" would otherwise stop being true the moment a
  priority changed. It recomputes both deadlines from the ticket's original
  `created_at` with the new priority's targets, in the same transaction as the
  change.

`response_overdue` and `resolution_overdue` are never stored. They compare the
deadline with the actual timestamp when one exists and with the current clock
when it does not, so a late response stays visible as a breach.
"""

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting, Ticket
from app.models.role import utc_now


class SlaNotConfigured(RuntimeError):
    """The seeded settings row is missing, so no deadline can be computed."""


def get_settings_row(session: Session) -> SystemSetting:
    """Read the singleton settings row, or refuse rather than guess a target."""
    settings = session.scalar(
        select(SystemSetting).where(SystemSetting.is_singleton.is_(True))
    )
    if settings is None:
        raise SlaNotConfigured("system_settings row is missing")
    return settings


def deadlines_for(
    settings: SystemSetting, priority: str, created_at: datetime
) -> tuple[datetime, datetime]:
    """Return the (first response, resolution) deadlines for a new priority."""
    target = settings.sla_targets.get(priority)
    if not isinstance(target, dict):
        raise SlaNotConfigured(f"no SLA targets for priority {priority!r}")
    try:
        response_hours = int(target["first_response_hours"])
        resolution_hours = int(target["resolution_hours"])
    except (KeyError, TypeError, ValueError) as error:
        raise SlaNotConfigured(
            f"SLA targets for {priority!r} are malformed"
        ) from error
    return (
        created_at + timedelta(hours=response_hours),
        created_at + timedelta(hours=resolution_hours),
    )


def response_overdue(ticket: Ticket, now: datetime | None = None) -> bool:
    """True when the first response is late, or was never given in time."""
    actual = ticket.first_response_at or (now or utc_now())
    return actual > ticket.response_due_at


def resolution_overdue(ticket: Ticket, now: datetime | None = None) -> bool:
    """True when the resolution is late, or has not happened in time."""
    actual = ticket.resolved_at or (now or utc_now())
    return actual > ticket.resolution_due_at


def sla_unavailable() -> HTTPException:
    """A missing or malformed settings row is a server problem, not a client one."""
    return HTTPException(status_code=503, detail="SLA settings are not configured")
