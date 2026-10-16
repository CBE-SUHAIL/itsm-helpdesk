"""S01: notification listing, read, and dismiss, plus the write side's wiring.

Real PostgreSQL, rollback-isolated HTTP tests matching the pattern the ticket
suite established. Two kinds of check live here: the routes' own behaviour, and
that the ticket events `app/core/notify.py` documents really do produce the rows
those routes then read.
"""

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.passwords import hash_password
from app.main import app
from app.models import Category, Notification, Role, User
from app.models.role import utc_now


BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "test-password-2026"
SECRET = "test-only-secret-long-enough-for-hs256-2026"


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_settings.cache_clear()
    engine = create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )
        try:
            roles = {}
            for name in ("Employee", "Support agent", "Admin"):
                role = session.scalar(select(Role).where(Role.name == name))
                if role is None:
                    role = Role(name=name)
                    session.add(role)
                    session.flush()
                roles[name] = role
            marker = uuid4().hex[:10]
            users = {}
            for key, role_name in (
                ("employee", "Employee"),
                ("other_employee", "Employee"),
                ("agent", "Support agent"),
                ("other_agent", "Support agent"),
                ("admin", "Admin"),
            ):
                user = User(
                    name=f"Test {key}",
                    email=f"{marker}.{key}@example.test",
                    role=roles[role_name],
                    password_hash=hash_password(PASSWORD),
                )
                session.add(user)
                session.flush()
                users[key] = user
            category = Category(
                name=f"[{marker}] Hardware", description="Test", is_active=True
            )
            session.add(category)
            session.commit()

            def override_db():
                yield session

            app.dependency_overrides[get_db] = override_db
            with TestClient(app) as client:
                headers = {}
                for key, user in users.items():
                    response = client.post(
                        "/api/v1/auth/login",
                        json={"email": user.email, "password": PASSWORD},
                    )
                    assert response.status_code == 200, response.text
                    headers[key] = {
                        "Authorization": f"Bearer {response.json()['access_token']}"
                    }
                yield client, session, users, headers, category
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def make_ticket(client, headers, category, *, assign_to=None, users=None) -> str:
    created = client.post(
        "/api/v1/tickets",
        headers=headers["employee"],
        json={
            "title": "Printer jams",
            "description": "Paper feed is broken",
            "category_id": str(category.id),
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    if assign_to is not None:
        assigned = client.post(
            f"/api/v1/tickets/{ticket_id}/assignment",
            headers=headers["admin"],
            json={"assignee_id": str(users[assign_to].id)},
        )
        assert assigned.status_code == 200, assigned.text
    return ticket_id


def seed_notice(session, user, *, message, minutes_ago, read=False, dismissed=False):
    """Insert a notification directly, for the states the routes cannot create."""
    now = utc_now() - timedelta(minutes=minutes_ago)
    notice = Notification(
        recipient_id=user.id,
        ticket_id=None,
        type="assignment",
        message=message,
        read_at=now if read else None,
        dismissed_at=now if dismissed else None,
        created_at=now,
    )
    session.add(notice)
    session.flush()
    return notice


def test_ticket_events_create_the_notifications_the_routes_read(api) -> None:
    """The write side wired into T02/T03/T06 feeds this router."""
    client, _session, users, headers, category = api
    ticket_id = make_ticket(client, headers, category, assign_to="agent", users=users)

    agent_inbox = client.get("/api/v1/notifications", headers=headers["agent"]).json()
    assert agent_inbox["total"] == 1
    assignment = agent_inbox["items"][0]
    assert assignment["type"] == "assignment"
    assert assignment["ticket_id"] == ticket_id
    assert assignment["read_at"] is None and assignment["dismissed_at"] is None
    assert "assigned" in assignment["message"]

    commented = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        headers=headers["agent"],
        json={"body": "Looking at it now."},
    )
    assert commented.status_code == 201, commented.text
    employee_inbox = client.get(
        "/api/v1/notifications", headers=headers["employee"]
    ).json()
    assert [item["type"] for item in employee_inbox["items"]] == ["comment"]
    # Nobody else is told about either event.
    assert client.get(
        "/api/v1/notifications", headers=headers["other_employee"]
    ).json() == {"items": [], "total": 0}


def test_default_list_hides_dismissed_and_can_filter_unread(api) -> None:
    client, session, users, headers, _category = api
    employee = users["employee"]
    seed_notice(session, employee, message="oldest", minutes_ago=30, read=True)
    seed_notice(session, employee, message="middle", minutes_ago=20, dismissed=True)
    seed_notice(session, employee, message="newest", minutes_ago=10)
    session.commit()

    default = client.get("/api/v1/notifications", headers=headers["employee"]).json()
    assert [item["message"] for item in default["items"]] == ["newest", "oldest"]
    assert default["total"] == 2

    unread = client.get(
        "/api/v1/notifications?unread_only=true", headers=headers["employee"]
    ).json()
    assert [item["message"] for item in unread["items"]] == ["newest"]

    everything = client.get(
        "/api/v1/notifications?include_dismissed=true", headers=headers["employee"]
    ).json()
    assert [item["message"] for item in everything["items"]] == [
        "newest", "middle", "oldest",
    ]
    assert everything["total"] == 3

    # The inbox is per user, so one person's filter cannot widen another's.
    assert client.get(
        "/api/v1/notifications?include_dismissed=true", headers=headers["other_agent"]
    ).json() == {"items": [], "total": 0}


def test_read_marks_read_and_keeps_the_notification_listed(api) -> None:
    client, session, users, headers, _category = api
    notice = seed_notice(session, users["employee"], message="read me", minutes_ago=5)
    session.commit()
    path = f"/api/v1/notifications/{notice.id}/read"

    assert client.patch(path).status_code == 401
    assert client.patch(path, headers=headers["employee"]).status_code == 200
    first = client.patch(path, headers=headers["employee"]).json()
    assert first["read_at"] is not None and first["dismissed_at"] is None

    # Still listed, and still listed as read rather than removed.
    listed = client.get("/api/v1/notifications", headers=headers["employee"]).json()
    assert listed["total"] == 1 and listed["items"][0]["read_at"] is not None
    assert client.get(
        "/api/v1/notifications?unread_only=true", headers=headers["employee"]
    ).json()["total"] == 0

    # Marking read twice keeps the original timestamp instead of moving it.
    again = client.patch(path, headers=headers["employee"]).json()
    assert again["read_at"] == first["read_at"]
    session.expire_all()
    stored = session.get(Notification, notice.id)
    assert stored.read_at == datetime.fromisoformat(first["read_at"])


def test_dismiss_hides_from_the_default_list_without_deleting(api) -> None:
    client, session, users, headers, _category = api
    notice = seed_notice(session, users["employee"], message="dismiss me", minutes_ago=5)
    session.commit()
    path = f"/api/v1/notifications/{notice.id}/dismiss"

    assert client.patch(path, headers=headers["employee"]).status_code == 200
    body = client.patch(path, headers=headers["employee"]).json()
    assert body["dismissed_at"] is not None
    # Dismiss is independent of read: it never sets read_at.
    assert body["read_at"] is None

    assert client.get(
        "/api/v1/notifications", headers=headers["employee"]
    ).json() == {"items": [], "total": 0}
    assert client.get(
        "/api/v1/notifications?include_dismissed=true", headers=headers["employee"]
    ).json()["total"] == 1
    # Not a delete: the row is still there.
    assert session.get(Notification, notice.id) is not None


def test_another_persons_notification_is_hidden(api) -> None:
    client, session, users, headers, _category = api
    notice = seed_notice(session, users["employee"], message="private", minutes_ago=5)
    session.commit()
    for role in ("other_employee", "agent", "admin"):
        assert client.patch(
            f"/api/v1/notifications/{notice.id}/read", headers=headers[role]
        ).status_code == 404, role
        assert client.patch(
            f"/api/v1/notifications/{notice.id}/dismiss", headers=headers[role]
        ).status_code == 404, role
    assert client.patch(
        f"/api/v1/notifications/{uuid4()}/read", headers=headers["employee"]
    ).status_code == 404
    assert client.patch(
        "/api/v1/notifications/not-a-uuid/read", headers=headers["employee"]
    ).status_code == 422
    # An admin's powers do not extend to another person's inbox.
    assert client.get(
        "/api/v1/notifications", headers=headers["admin"]
    ).json() == {"items": [], "total": 0}


def test_notification_list_is_paginated_and_validated(api) -> None:
    client, session, users, headers, _category = api
    for index in range(3):
        seed_notice(
            session, users["employee"], message=f"n{index}", minutes_ago=10 - index
        )
    session.commit()

    page = client.get(
        "/api/v1/notifications?limit=2&offset=0", headers=headers["employee"]
    ).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    rest = client.get(
        "/api/v1/notifications?limit=2&offset=2", headers=headers["employee"]
    ).json()
    assert [item["message"] for item in page["items"] + rest["items"]] == [
        "n2", "n1", "n0",
    ]
    for query in ("limit=0", "limit=101", "offset=-1", "limit=oops"):
        assert client.get(
            f"/api/v1/notifications?{query}", headers=headers["employee"]
        ).status_code == 422, query
    assert client.get("/api/v1/notifications").status_code == 401
