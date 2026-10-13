"""D05 database checks for the notifications and system_settings tables.

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
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Category, Notification, Role, SystemSetting, Ticket, User

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024


def _engine():
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def test_notifications_read_state_and_settings_values_persist() -> None:
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

                notification = dict(
                    id=uuid4(),
                    recipient_id=user_id,
                    ticket_id=ticket_id,
                    type="assignment",
                    message="You were assigned ticket 'Monitor flickers'.",
                    read_at=None,
                    dismissed_at=None,
                    created_at=now,
                )
                connection.execute(insert(Notification).values(**notification))

                # Read and dismissed are independent: marking read must not
                # dismiss, and the row must survive both.
                connection.execute(
                    update(Notification)
                    .where(Notification.id == notification["id"])
                    .values(read_at=now)
                )
                row = connection.execute(
                    select(Notification.read_at, Notification.dismissed_at).where(
                        Notification.id == notification["id"]
                    )
                ).one()
                assert row.read_at is not None
                assert row.dismissed_at is None

                connection.execute(
                    update(Notification)
                    .where(Notification.id == notification["id"])
                    .values(dismissed_at=now)
                )
                row = connection.execute(
                    select(Notification.read_at, Notification.dismissed_at).where(
                        Notification.id == notification["id"]
                    )
                ).one()
                assert row.read_at is not None
                assert row.dismissed_at is not None

                # A notification needs no ticket: the column is nullable.
                connection.execute(
                    insert(Notification).values(
                        **{**notification, "id": uuid4(), "ticket_id": None}
                    )
                )

                invalid_notifications = [
                    {**notification, "id": uuid4(), "type": "Assignment"},
                    {**notification, "id": uuid4(), "type": "mention"},
                    {**notification, "id": uuid4(), "type": None},
                    {**notification, "id": uuid4(), "message": ""},
                    {**notification, "id": uuid4(), "message": "   "},
                    {**notification, "id": uuid4(), "message": None},
                    {**notification, "id": uuid4(), "recipient_id": None},
                    {**notification, "id": uuid4(), "recipient_id": uuid4()},
                    {**notification, "id": uuid4(), "ticket_id": uuid4()},
                    {**notification, "id": uuid4(), "created_at": None},
                ]
                for invalid in invalid_notifications:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                insert(Notification).values(**invalid)
                            )

                # The seeded singleton row is the defaults REQUIREMENTS.md
                # documents, and it is editable in place.
                seeded = connection.execute(
                    select(
                        SystemSetting.sla_targets,
                        SystemSetting.max_attachment_bytes,
                        SystemSetting.allowed_attachment_types,
                    ).where(SystemSetting.is_singleton.is_(True))
                ).one()
                assert seeded.sla_targets["Low"] == {
                    "first_response_hours": 24,
                    "resolution_hours": 72,
                }
                assert seeded.sla_targets["Critical"] == {
                    "first_response_hours": 1,
                    "resolution_hours": 8,
                }
                assert seeded.max_attachment_bytes == 10 * MIB
                assert set(seeded.allowed_attachment_types) == {
                    "application/pdf",
                    "image/png",
                    "image/jpeg",
                    "text/plain",
                }

                connection.execute(
                    update(SystemSetting)
                    .where(SystemSetting.is_singleton.is_(True))
                    .values(max_attachment_bytes=5 * MIB, updated_at=now)
                )
                assert connection.execute(
                    select(SystemSetting.max_attachment_bytes).where(
                        SystemSetting.is_singleton.is_(True)
                    )
                ).scalar_one() == 5 * MIB

                settings_row = dict(
                    id=uuid4(),
                    is_singleton=True,
                    sla_targets={
                        "Low": {"first_response_hours": 1, "resolution_hours": 1},
                        "Medium": {"first_response_hours": 1, "resolution_hours": 1},
                        "High": {"first_response_hours": 1, "resolution_hours": 1},
                        "Critical": {"first_response_hours": 1, "resolution_hours": 1},
                    },
                    max_attachment_bytes=1 * MIB,
                    allowed_attachment_types=["application/pdf"],
                    created_at=now,
                    updated_at=now,
                )
                invalid_settings = [
                    # A second row: is_singleton is unique, so one is all there is.
                    settings_row,
                    {**settings_row, "id": uuid4(), "is_singleton": False},
                    {
                        **settings_row,
                        "id": uuid4(),
                        "sla_targets": {
                            "Low": {"first_response_hours": 1, "resolution_hours": 1}
                        },
                    },
                    {**settings_row, "id": uuid4(), "sla_targets": None},
                    {**settings_row, "id": uuid4(), "max_attachment_bytes": 0},
                    {**settings_row, "id": uuid4(), "max_attachment_bytes": -1},
                    {**settings_row, "id": uuid4(), "max_attachment_bytes": None},
                    {**settings_row, "id": uuid4(), "allowed_attachment_types": []},
                    {**settings_row, "id": uuid4(), "allowed_attachment_types": None},
                ]
                for invalid in invalid_settings:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                insert(SystemSetting).values(**invalid)
                            )

                # No hard delete: a notification holds its ticket and recipient.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(Ticket).where(Ticket.id == ticket_id))
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(User).where(User.id == user_id))

                indexes = set(
                    connection.execute(
                        text(
                            "select indexname from pg_indexes "
                            "where tablename = 'notifications'"
                        )
                    ).scalars()
                )
                assert "ix_notifications_recipient_id_created_at" in indexes
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_settings_is_the_only_editable_table_of_the_two() -> None:
    """`PATCH /settings` exists, so settings carries `updated_at`; notifications
    are edited only through the read/dismiss routes, which already have their own
    timestamps."""
    assert "updated_at" in SystemSetting.__table__.columns
    assert "created_at" in SystemSetting.__table__.columns
    assert "updated_at" not in Notification.__table__.columns
