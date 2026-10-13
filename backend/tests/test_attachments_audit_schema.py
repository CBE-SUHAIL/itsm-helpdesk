"""D04 database checks for the attachments and audit_logs tables.

Same shape as the other schema tests: the real PostgreSQL constraints inside one
transaction that is always rolled back, so running the suite cannot touch
development rows.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, insert, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Attachment, AuditLog, Category, Role, Ticket, User

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _engine():
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def test_attachments_and_audit_logs_link_to_real_records() -> None:
    engine = _engine()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    user_id = uuid4()
    category_id = uuid4()
    ticket_id = uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.upgrade(config, "head")
                connection.execute(
                    insert(Role).values(
                        id=role_id, name="Employee", created_at=now, updated_at=now
                    )
                )
                connection.execute(
                    insert(User).values(
                        id=user_id,
                        role_id=role_id,
                        name="Demo Employee",
                        email="employee@example.com",
                        password_hash="hashed-placeholder",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(
                    insert(Category).values(
                        id=category_id,
                        name="Hardware",
                        description="Laptops, monitors, and peripherals.",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(
                    insert(Ticket).values(
                        id=ticket_id,
                        title="Monitor flickers",
                        description="It flickers when the laptop is docked.",
                        category_id=category_id,
                        creator_id=user_id,
                        assignee_id=None,
                        status="Open",
                        priority="Medium",
                        response_due_at=now + timedelta(hours=8),
                        resolution_due_at=now + timedelta(hours=48),
                        first_response_at=None,
                        resolved_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )

                attachment = dict(
                    id=uuid4(),
                    ticket_id=ticket_id,
                    uploader_id=user_id,
                    file_name="screen-recording.pdf",
                    content_type="application/pdf",
                    size_bytes=2048,
                    storage_name="6f1c2a9b8e4d47f0a1b2c3d4e5f60718.pdf",
                    created_at=now,
                )
                connection.execute(insert(Attachment).values(**attachment))
                stored = connection.execute(
                    select(Attachment.file_name, Attachment.storage_name).where(
                        Attachment.id == attachment["id"]
                    )
                ).one()
                assert stored.file_name == "screen-recording.pdf"
                # The storage name is kept in the table and hidden from routes.
                assert stored.storage_name == attachment["storage_name"]

                invalid_attachments = [
                    {**attachment, "id": uuid4(), "ticket_id": None},
                    {**attachment, "id": uuid4(), "ticket_id": uuid4()},
                    {**attachment, "id": uuid4(), "uploader_id": None},
                    {**attachment, "id": uuid4(), "uploader_id": uuid4()},
                    {**attachment, "id": uuid4(), "file_name": ""},
                    {**attachment, "id": uuid4(), "file_name": "   "},
                    {**attachment, "id": uuid4(), "file_name": None},
                    {**attachment, "id": uuid4(), "content_type": None},
                    {**attachment, "id": uuid4(), "size_bytes": None},
                    {**attachment, "id": uuid4(), "size_bytes": -1},
                    {**attachment, "id": uuid4(), "storage_name": None},
                    {**attachment, "id": uuid4(), "storage_name": ""},
                    # storage_name is unique: the same name twice is rejected.
                    {**attachment, "id": uuid4()},
                    {**attachment, "id": uuid4(), "created_at": None},
                ]
                for invalid in invalid_attachments:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                insert(Attachment).values(**invalid)
                            )

                audit = dict(
                    id=uuid4(),
                    actor_id=user_id,
                    action="ticket.status_changed",
                    entity_type="ticket",
                    entity_id=ticket_id,
                    old_value={"status": "Assigned"},
                    new_value={"status": "In Progress"},
                    created_at=now,
                )
                connection.execute(insert(AuditLog).values(**audit))
                # A failed sign-in has no actor and no entity, and stores only
                # the attempted email.
                failed_login = {
                    **audit,
                    "id": uuid4(),
                    "actor_id": None,
                    "action": "auth.sign_in_failed",
                    "entity_type": "user",
                    "entity_id": None,
                    "old_value": None,
                    "new_value": {"attempted_email": "nobody@example.com"},
                }
                connection.execute(insert(AuditLog).values(**failed_login))

                invalid_audit = [
                    {**audit, "id": uuid4(), "actor_id": uuid4()},
                    {**audit, "id": uuid4(), "action": ""},
                    {**audit, "id": uuid4(), "action": "   "},
                    {**audit, "id": uuid4(), "action": None},
                    {**audit, "id": uuid4(), "entity_type": ""},
                    {**audit, "id": uuid4(), "entity_type": None},
                    {**audit, "id": uuid4(), "created_at": None},
                ]
                for invalid in invalid_audit:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(AuditLog).values(**invalid))

                # No hard delete: neither table lets its ticket or user go.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(Ticket).where(Ticket.id == ticket_id))
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(User).where(User.id == user_id))

                audit_indexes = set(
                    connection.execute(
                        text(
                            "select indexname from pg_indexes "
                            "where tablename = 'audit_logs'"
                        )
                    ).scalars()
                )
                assert "ix_audit_logs_created_at" in audit_indexes
                assert "ix_audit_logs_entity_type_entity_id" in audit_indexes
                attachment_indexes = set(
                    connection.execute(
                        text(
                            "select indexname from pg_indexes "
                            "where tablename = 'attachments'"
                        )
                    ).scalars()
                )
                assert "ix_attachments_ticket_id" in attachment_indexes
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_attachments_and_audit_logs_are_write_once() -> None:
    """No `updated_at`: no route updates an attachment or an audit entry."""
    for model in (Attachment, AuditLog):
        assert "created_at" in model.__table__.columns
        assert "updated_at" not in model.__table__.columns
    # The one column the contract hides from responses, kept for the bytes.
    assert "storage_name" in Attachment.__table__.columns
