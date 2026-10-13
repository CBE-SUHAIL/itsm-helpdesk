"""D02 database checks for the categories and tickets tables.

Same shape as test_users_roles_schema.py: exercise the real PostgreSQL
constraints inside one transaction that is always rolled back, so running the
suite can never touch development rows.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Category, Role, Ticket, User

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _engine():
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def test_tickets_reference_categories_and_users_and_reject_invalid_rows() -> None:
    engine = _engine()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    creator_id = uuid4()
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
                        id=creator_id,
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

                # A ticket that omits status and priority must take the contract
                # defaults: Open and Medium.
                ticket = dict(
                    id=ticket_id,
                    title="Laptop will not charge",
                    description="The charger light stays off on any outlet.",
                    category_id=category_id,
                    creator_id=creator_id,
                    assignee_id=None,
                    response_due_at=now + timedelta(hours=8),
                    resolution_due_at=now + timedelta(hours=48),
                    first_response_at=None,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(insert(Ticket).values(**ticket))
                row = connection.execute(
                    select(Ticket.status, Ticket.priority, Ticket.assignee_id).where(
                        Ticket.id == ticket_id
                    )
                ).one()
                assert row.status == "Open"
                assert row.priority == "Medium"
                assert row.assignee_id is None

                # Same ticket, plus an explicit assignee, is also valid.
                connection.execute(
                    insert(Ticket).values(
                        **{**ticket, "id": uuid4(), "assignee_id": creator_id}
                    )
                )

                invalid_tickets = [
                    {**ticket, "id": uuid4(), "status": "Pending"},
                    {**ticket, "id": uuid4(), "status": "open"},
                    {**ticket, "id": uuid4(), "status": None},
                    {**ticket, "id": uuid4(), "priority": "Urgent"},
                    {**ticket, "id": uuid4(), "priority": "medium"},
                    {**ticket, "id": uuid4(), "priority": None},
                    {**ticket, "id": uuid4(), "title": "   "},
                    {**ticket, "id": uuid4(), "title": None},
                    {**ticket, "id": uuid4(), "description": ""},
                    {**ticket, "id": uuid4(), "description": None},
                    {**ticket, "id": uuid4(), "category_id": None},
                    {**ticket, "id": uuid4(), "category_id": uuid4()},
                    {**ticket, "id": uuid4(), "creator_id": None},
                    {**ticket, "id": uuid4(), "creator_id": uuid4()},
                    {**ticket, "id": uuid4(), "assignee_id": uuid4()},
                    {**ticket, "id": uuid4(), "response_due_at": None},
                    {**ticket, "id": uuid4(), "resolution_due_at": None},
                ]
                for invalid in invalid_tickets:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(Ticket).values(**invalid))

                invalid_categories = [
                    {
                        "id": uuid4(),
                        "name": "Hardware",
                        "description": "Duplicate name.",
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "id": uuid4(),
                        "name": "  ",
                        "description": "Blank name.",
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "id": uuid4(),
                        "name": "Software",
                        "description": None,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                ]
                for invalid in invalid_categories:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(Category).values(**invalid))

                # Nothing is hard-deleted in v1: a category or user that a
                # ticket still references cannot be removed.
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(
                            delete(Category).where(Category.id == category_id)
                        )
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(delete(User).where(User.id == creator_id))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
