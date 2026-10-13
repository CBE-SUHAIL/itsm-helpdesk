"""D03 database checks for the comments and ticket_history tables.

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
from app.models import Category, Comment, Role, Ticket, TicketHistory, User

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _engine():
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def test_comments_and_history_require_an_author_and_a_real_ticket() -> None:
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

                comment = dict(
                    id=uuid4(),
                    ticket_id=ticket_id,
                    author_id=user_id,
                    body="Tried a second cable, same flicker.",
                    created_at=now,
                )
                connection.execute(insert(Comment).values(**comment))
                assert connection.execute(
                    select(Comment.body).where(Comment.id == comment["id"])
                ).scalar_one() == "Tried a second cable, same flicker."

                history = dict(
                    id=uuid4(),
                    ticket_id=ticket_id,
                    actor_id=user_id,
                    field="status",
                    old_value="Assigned",
                    new_value="In Progress",
                    reason=None,
                    created_at=now,
                )
                connection.execute(insert(TicketHistory).values(**history))
                # Every field the contract names is accepted.
                for field, old, new in (
                    ("assignee_id", None, str(user_id)),
                    ("category_id", str(category_id), str(category_id)),
                    ("priority", "Medium", "High"),
                ):
                    connection.execute(
                        insert(TicketHistory).values(
                            **{**history, "id": uuid4(), "field": field,
                               "old_value": old, "new_value": new}
                        )
                    )

                invalid_comments = [
                    {**comment, "id": uuid4(), "body": ""},
                    {**comment, "id": uuid4(), "body": "   "},
                    {**comment, "id": uuid4(), "body": None},
                    {**comment, "id": uuid4(), "ticket_id": None},
                    {**comment, "id": uuid4(), "ticket_id": uuid4()},
                    {**comment, "id": uuid4(), "author_id": None},
                    {**comment, "id": uuid4(), "author_id": uuid4()},
                    {**comment, "id": uuid4(), "created_at": None},
                ]
                for invalid in invalid_comments:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(Comment).values(**invalid))

                invalid_history = [
                    {**history, "id": uuid4(), "field": "title"},
                    {**history, "id": uuid4(), "field": "Status"},
                    {**history, "id": uuid4(), "field": "resolution_note"},
                    {**history, "id": uuid4(), "field": None},
                    {**history, "id": uuid4(), "ticket_id": None},
                    {**history, "id": uuid4(), "ticket_id": uuid4()},
                    {**history, "id": uuid4(), "actor_id": None},
                    {**history, "id": uuid4(), "actor_id": uuid4()},
                    {**history, "id": uuid4(), "created_at": None},
                ]
                for invalid in invalid_history:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(
                                insert(TicketHistory).values(**invalid)
                            )

                # Nothing is hard-deleted in v1: history and comments block the
                # delete of the ticket they belong to.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(Ticket).where(Ticket.id == ticket_id))
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(User).where(User.id == user_id))

                # One composite index per table serves the contract's read
                # pattern: filter by ticket, order oldest first.
                comments_indexes = set(
                    connection.execute(
                        text(
                            "select indexname from pg_indexes "
                            "where tablename = 'comments'"
                        )
                    ).scalars()
                )
                history_indexes = set(
                    connection.execute(
                        text(
                            "select indexname from pg_indexes "
                            "where tablename = 'ticket_history'"
                        )
                    ).scalars()
                )
                assert "ix_comments_ticket_id_created_at" in comments_indexes
                assert "ix_ticket_history_ticket_id_created_at" in history_indexes
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_history_and_comments_are_append_only() -> None:
    """No `updated_at`: neither table has an update route in the contract."""
    for model in (Comment, TicketHistory):
        assert "created_at" in model.__table__.columns
        assert "updated_at" not in model.__table__.columns
