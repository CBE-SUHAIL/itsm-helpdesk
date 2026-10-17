"""Attachment bytes on local disk. T07.

`REQUIREMENTS.md` fixes the rules this module implements: uploads are PDF, PNG,
JPEG, or TXT up to the configured limit; the bytes live in a local directory
outside the web folder while PostgreSQL keeps the metadata; **storage names are
generated server-side**, and a client-supplied name is never turned into a path.

Three consequences shape the code:

- the stored name is a bare `uuid4` hex string, with no directory part and no
  extension taken from the client, so a crafted `filename` cannot escape the
  root. `storage_path` still re-checks that the resolved path lands directly
  inside the root, so a hand-edited row cannot either;
- the size limit is enforced while reading in chunks rather than after buffering
  the whole upload. Starlette has already spooled the request to a temporary
  file by the time a route runs, so this bounds API memory, not the temporary
  file the parser wrote;
- the file is written before the row is committed and unlinked again if the
  commit fails, so a rejected upload cannot leave a stray file behind.

The limit and the allowed types come from the singleton settings row — the same
row the SLA targets live in — so an admin change applies to the next upload
without a code change.
"""

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.sla import SlaNotConfigured, get_settings_row

# One megabyte keeps an oversized upload from being buffered whole just to be
# rejected, while staying large enough that a 10 MB file is a handful of reads.
CHUNK_BYTES = 1024 * 1024


def upload_root() -> Path:
    """The configured upload directory, created on first use."""
    root = get_settings().upload_root
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_storage_name() -> str:
    """A generated file name. The client never influences it."""
    return uuid4().hex


def storage_path(storage_name: str) -> Path:
    """Resolve a stored name against the upload root, refusing traversal."""
    root = upload_root().resolve()
    candidate = (root / storage_name).resolve()
    if candidate.parent != root:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return candidate


def attachment_settings_unavailable() -> HTTPException:
    """A missing or malformed settings row is a server problem, not a client one."""
    return HTTPException(
        status_code=503, detail="Attachment settings are not configured"
    )


def attachment_limits(session: Session) -> tuple[int, tuple[str, ...]]:
    """Return the (max bytes, allowed content types) in force right now.

    Read per request rather than cached, so `PATCH /settings` can lower a limit
    and have the next upload honour it.
    """
    try:
        settings = get_settings_row(session)
    except SlaNotConfigured:
        raise attachment_settings_unavailable() from None
    try:
        max_bytes = int(settings.max_attachment_bytes)
        allowed = tuple(
            str(item).strip().lower()
            for item in settings.allowed_attachment_types
            if str(item).strip()
        )
    except (TypeError, ValueError):
        raise attachment_settings_unavailable() from None
    if max_bytes <= 0 or not allowed:
        raise attachment_settings_unavailable()
    return max_bytes, allowed


def read_within_limit(upload: UploadFile, max_bytes: int) -> bytes | None:
    """Read the upload, returning None as soon as it exceeds `max_bytes`."""
    stream = upload.file
    stream.seek(0)
    data = bytearray()
    while True:
        chunk = stream.read(CHUNK_BYTES)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            return None
    return bytes(data)


def display_name(raw_name: str | None) -> str | None:
    """Reduce a client-supplied name to a display label, or None when blank.

    Browsers may send a full path, and some send Windows separators even to a
    Linux server, so both are stripped to the final component. The column holds
    255 characters, so anything longer is truncated rather than rejected: the
    name is only ever shown to a user.
    """
    if raw_name is None:
        return None
    name = Path(raw_name.replace("\\", "/")).name.strip()
    return name[:255] or None


def discard(path: Path) -> None:
    """Remove a written file after a failed commit. Safe to call twice."""
    path.unlink(missing_ok=True)
