"""T07: attach files to a ticket, list them, and download them again.

Authorization follows the comment routes, because the contract gives both the
same rule: any agent or admin may **read** a ticket's attachments, but only the
ticket's creator, its assigned agent, or an admin may **add** one. Reading an
inaccessible ticket answers 404 rather than 403, so an employee cannot probe for
other people's ticket IDs.

`GET` on the ticket reuses `visible_ticket_or_404` from the ticket router, so the
visibility rule stays in one place. An `attachment_id` that belongs to a
different ticket is a 404 for the same reason.

Bytes never pass through PostgreSQL and the storage path is never serialised:
the download resolves the row's generated `storage_name` against the configured
upload root and returns the file with the client's original name in
`Content-Disposition`, which is what "never a storage path" in the contract
means.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import AttachmentOut, AttachmentPage
from app.api.v1.tickets import visible_ticket_or_404
from app.core.db import get_db
from app.core.security import current_user
from app.core.storage import (
    attachment_limits,
    discard,
    display_name,
    new_storage_name,
    read_within_limit,
    storage_path,
)
from app.models import Attachment, Ticket, User


router = APIRouter(tags=["attachments"])

ADMIN = "Admin"


def may_attach(ticket: Ticket, user: User) -> bool:
    """The ticket's creator, its assigned agent, or an admin may add a file."""
    return (
        user.role.name == ADMIN
        or ticket.creator_id == user.id
        or ticket.assignee_id == user.id
    )


@router.get(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentPage,
    summary="List a ticket's attachments",
)
def list_attachments(
    ticket_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> AttachmentPage:
    """Newest first. Metadata only; the bytes come from the download route."""
    ticket = visible_ticket_or_404(session, ticket_id, user)
    total = (
        session.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(Attachment.ticket_id == ticket.id)
        )
        or 0
    )
    attachments = session.scalars(
        select(Attachment)
        .where(Attachment.ticket_id == ticket.id)
        # Two uploads can share a timestamp, so `id` breaks the tie and keeps
        # paging reproducible between reads.
        .order_by(Attachment.created_at.desc(), Attachment.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AttachmentPage(
        items=[AttachmentOut.from_attachment(item) for item in attachments],
        total=total,
    )


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentOut,
    status_code=201,
    summary="Attach a file to a ticket",
)
def add_attachment(
    ticket_id: UUID,
    file: UploadFile = File(
        ..., description="PDF, PNG, JPEG, or TXT, at most the configured size limit"
    ),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> AttachmentOut:
    """Store the bytes under a generated name and the metadata in PostgreSQL.

    Permission is checked before type and size, so a caller who may not attach
    anything learns nothing about the configured limits.
    """
    ticket = visible_ticket_or_404(session, ticket_id, user)
    if not may_attach(ticket, user):
        raise HTTPException(
            status_code=403, detail="Only the ticket's people may attach files"
        )

    file_name = display_name(file.filename)
    if file_name is None:
        raise HTTPException(status_code=400, detail="A file name is required")

    # A multipart part may carry parameters, as in "text/plain; charset=utf-8".
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    max_bytes, allowed_types = attachment_limits(session)
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type is not allowed")

    data = read_within_limit(file, max_bytes)
    if data is None:
        raise HTTPException(
            status_code=400, detail="File is larger than the allowed limit"
        )

    storage_name = new_storage_name()
    target = storage_path(storage_name)
    target.write_bytes(data)

    attachment = Attachment(
        ticket_id=ticket.id,
        uploader_id=user.id,
        file_name=file_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_name=storage_name,
    )
    try:
        session.add(attachment)
        session.commit()
    except Exception:
        # The row and the bytes must agree, so a failed insert must not leave
        # the file behind.
        session.rollback()
        discard(target)
        raise
    return AttachmentOut.from_attachment(attachment)


@router.get(
    "/tickets/{ticket_id}/attachments/{attachment_id}",
    summary="Download an attachment",
    responses={
        200: {
            "description": "The stored bytes, as uploaded.",
            "content": {"application/octet-stream": {}},
        }
    },
)
def download_attachment(
    ticket_id: UUID,
    attachment_id: UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> FileResponse:
    """Return the file with its stored type and its original name.

    An attachment id that belongs to another ticket is a 404, and so is a row
    whose file is missing from disk: the caller learns that the file is not
    available, not where it lives.
    """
    ticket = visible_ticket_or_404(session, ticket_id, user)
    attachment = session.get(Attachment, attachment_id)
    if attachment is None or attachment.ticket_id != ticket.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = storage_path(attachment.storage_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(
        path, media_type=attachment.content_type, filename=attachment.file_name
    )
