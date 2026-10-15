"""D08: demo data is usable, repeatable, and never overwrites existing rows."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.passwords import hash_password, verify_password
from app.models import Category, Ticket, User
from app.seed_demo import seed_demo


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_password_hash_uses_salt_and_can_be_verified() -> None:
    first = hash_password("test-only-password")
    second = hash_password("test-only-password")
    assert first != second
    assert "test-only-password" not in first
    assert verify_password("test-only-password", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("test-only-password", "malformed")


def test_seed_rejects_invalid_keys_before_accessing_database() -> None:
    with pytest.raises(ValueError, match="seed_key"):
        seed_demo(None, "test-only-password", seed_key="UPPER")
    with pytest.raises(ValueError, match="seed_key"):
        seed_demo(None, "test-only-password", seed_key="x" * 33)


def test_demo_seed_can_run_twice_without_duplicates_or_resets() -> None:
    engine = create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    seed_key = f"test-{uuid4().hex[:10]}"
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.upgrade(config, "head")
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    autoflush=False,
                    expire_on_commit=False,
                ) as session:
                    first = seed_demo(session, "test-only-password", seed_key=seed_key)
                    session.commit()
                    assert first["users"] == 3
                    assert first["categories"] == 3
                    assert first["tickets"] == 5

                    users = session.scalars(
                        select(User).where(User.email.like(f"{seed_key}.%@example.test"))
                    ).all()
                    assert len(users) == 3
                    assert {user.role.name for user in users} == {
                        "Employee", "Support agent", "Admin"
                    }
                    assert all(
                        verify_password("test-only-password", user.password_hash)
                        for user in users
                    )

                    employee = next(user for user in users if user.role.name == "Employee")
                    tickets = session.scalars(
                        select(Ticket).where(Ticket.creator_id == employee.id)
                    ).all()
                    assert len(tickets) == 5
                    assert {ticket.status for ticket in tickets} == {
                        "Open", "Assigned", "In Progress", "Resolved", "Closed"
                    }
                    assert all(ticket.response_due_at < ticket.resolution_due_at
                               for ticket in tickets)
                    assert next(t for t in tickets if t.status == "Open").assignee_id is None
                    assert all(t.assignee_id is not None for t in tickets if t.status != "Open")
                    assert all(t.resolved_at is not None for t in tickets
                               if t.status in {"Resolved", "Closed"})

                    changed = next(t for t in tickets if t.status == "Open")
                    changed.title = "Changed during local testing"
                    session.commit()
                    second = seed_demo(session, "different-password", seed_key=seed_key)
                    session.commit()
                    assert second == {"roles": 0, "users": 0, "categories": 0, "tickets": 0}
                    assert session.get(Ticket, changed.id).title == "Changed during local testing"
                    assert all(
                        verify_password("test-only-password", user.password_hash)
                        for user in users
                    )
                    assert len(session.scalars(select(Category).where(
                        Category.name.like(f"[{seed_key}] %")
                    )).all()) == 3
            finally:
                outer.rollback()
    finally:
        engine.dispose()
