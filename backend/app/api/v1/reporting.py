"""Role-scoped dashboard and downloadable ticket reports."""

import csv
from datetime import datetime
from io import BytesIO, StringIO
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas import DashboardOut, Priority, TicketStatus
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.core.sla import resolution_overdue, response_overdue
from app.models import Ticket, User
from app.models.role import utc_now


router = APIRouter(tags=["reporting"])
STATUSES = ("Open", "Assigned", "In Progress", "Resolved", "Closed")
PRIORITIES = ("Low", "Medium", "High", "Critical")
COLUMNS = (
    "id", "title", "status", "priority", "category_id", "creator_id",
    "assignee_id", "created_at", "response_due_at", "resolution_due_at",
    "response_overdue", "resolution_overdue",
)


def _report_values(ticket: Ticket, now: datetime) -> list[str]:
    return [
        str(ticket.id), ticket.title, ticket.status, ticket.priority,
        str(ticket.category_id), str(ticket.creator_id),
        str(ticket.assignee_id) if ticket.assignee_id else "",
        ticket.created_at.isoformat(), ticket.response_due_at.isoformat(),
        ticket.resolution_due_at.isoformat(),
        str(response_overdue(ticket, now)).lower(),
        str(resolution_overdue(ticket, now)).lower(),
    ]


def _safe_csv_cell(value: str) -> str:
    """Prevent spreadsheet programs treating user-entered text as a formula."""
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/dashboard/summary", response_model=DashboardOut, summary="View ticket summary")
def dashboard_summary(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> DashboardOut:
    query = select(Ticket)
    if user.role.name == "Employee":
        query = query.where(Ticket.creator_id == user.id)
    tickets = session.scalars(query).all()
    now = utc_now()
    by_status = {status: 0 for status in STATUSES}
    by_priority = {priority: 0 for priority in PRIORITIES}
    workload: dict[str, int] | None = None if user.role.name == "Employee" else {}
    for ticket in tickets:
        by_status[ticket.status] += 1
        by_priority[ticket.priority] += 1
        if workload is not None and ticket.assignee_id and ticket.status in ("Assigned", "In Progress"):
            key = str(ticket.assignee_id)
            workload[key] = workload.get(key, 0) + 1
    return DashboardOut(
        counts_by_status=by_status,
        counts_by_priority=by_priority,
        response_overdue_count=sum(response_overdue(t, now) for t in tickets),
        resolution_overdue_count=sum(resolution_overdue(t, now) for t in tickets),
        agent_workload=workload,
    )


@router.get("/reports/tickets", summary="Export filtered tickets")
def export_tickets(
    format: Literal["csv", "pdf"] = Query(),
    status: TicketStatus | None = None,
    priority: Priority | None = None,
    category_id: UUID | None = None,
    assignee_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    _: User = Depends(require_roles("Support agent", "Admin")),
    session: Session = Depends(get_db),
) -> Response:
    if created_from and created_to and created_from > created_to:
        raise HTTPException(status_code=422, detail="created_from must not exceed created_to")
    query = select(Ticket)
    if status is not None:
        query = query.where(Ticket.status == status)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if category_id is not None:
        query = query.where(Ticket.category_id == category_id)
    if assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)
    if created_from is not None:
        query = query.where(Ticket.created_at >= created_from)
    if created_to is not None:
        query = query.where(Ticket.created_at <= created_to)
    tickets = session.scalars(query.order_by(Ticket.created_at.desc(), Ticket.id)).all()
    now = utc_now()
    rows = [_report_values(ticket, now) for ticket in tickets]
    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        writer.writerows([[_safe_csv_cell(cell) for cell in row] for row in rows])
        return Response(
            content=output.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="itsm-tickets.csv"'},
        )
    output_bytes = BytesIO()
    document = SimpleDocTemplate(output_bytes, pagesize=landscape(A3),
                                 leftMargin=20, rightMargin=20)
    styles = getSampleStyleSheet()
    # The report keeps every contract column while wrapping long IDs and titles.
    data = [[Paragraph(str(cell), styles["BodyText"]) for cell in COLUMNS]]
    data.extend([Paragraph(cell.replace("&", "&amp;").replace("<", "&lt;"), styles["BodyText"])
                 for cell in row] for row in rows)
    widths = [68, 140, 52, 48, 68, 68, 68, 72, 72, 72, 54, 54]
    table = LongTable(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))
    document.build([
        Paragraph("ITSM ticket report", styles["Heading1"]),
        Paragraph(f"Generated {now.isoformat()} · {len(rows)} ticket(s)", styles["Normal"]),
        Spacer(1, 12), table,
    ])
    return Response(
        content=output_bytes.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="itsm-tickets.pdf"'},
    )
