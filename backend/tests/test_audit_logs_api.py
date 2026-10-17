"""G01: the admin-only audit read, and the entries the write side produces.

Real PostgreSQL, rollback-isolated HTTP tests. G01's "done when" is that login,
user, ticket, and settings changes record actor and time, so the tests here drive
real actions through the API and then read them back rather than inserting audit
rows by hand.
"""

from datetime import datetime, timedelta, timezone
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
from app.models import Category, Role, User


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
                ("agent", "Support agent"),
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
                yield client, session, users, headers, category, marker
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def read(client, headers, query="") -> dict:
    response = client.get(f"/api/v1/audit-logs{query}", headers=headers["admin"])
    assert response.status_code == 200, response.text
    return response.json()


def test_only_an_admin_may_read_the_audit_log(api) -> None:
    client, _session, _users, headers, _category, _marker = api
    assert client.get("/api/v1/audit-logs").status_code == 401
    for role in ("employee", "agent"):
        assert client.get(
            "/api/v1/audit-logs", headers=headers[role]
        ).status_code == 403, role
    body = read(client, headers)
    assert body["total"] >= 1
    assert set(body["items"][0]) == {
        "id", "actor_id", "action", "entity_type",
        "entity_id", "old_value", "new_value", "created_at",
    }


def test_login_success_and_failure_are_recorded(api) -> None:
    client, _session, users, headers, _category, _marker = api
    employee = users["employee"]

    failed = client.post(
        "/api/v1/auth/login",
        json={"email": employee.email, "password": "definitely-not-the-password"},
    )
    assert failed.status_code == 401
    assert "password" not in failed.text

    failures = read(client, headers, "?action=login_failure")["items"]
    mine = [entry for entry in failures
            if entry["new_value"] == {"attempted_email": employee.email}]
    assert len(mine) == 1
    # A failed sign-in has no actor: only the attempted address is stored.
    assert mine[0]["actor_id"] is None
    assert mine[0]["entity_type"] == "auth"
    assert mine[0]["created_at"].endswith("Z")

    successes = read(
        client, headers, f"?action=login_success&actor_id={employee.id}"
    )["items"]
    assert successes and all(e["actor_id"] == str(employee.id) for e in successes)
    assert successes[0]["entity_id"] == str(employee.id)


def test_user_changes_are_audited_with_old_and_new_values(api) -> None:
    client, _session, _users, headers, _category, marker = api
    created = client.post(
        "/api/v1/users",
        headers=headers["admin"],
        json={
            "name": "Audited Person",
            "email": f"{marker}.audited@example.test",
            "password": "another-password-2026",
            "role": "Employee",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    edited = client.patch(
        f"/api/v1/users/{user_id}", headers=headers["admin"], json={"role": "Support agent"}
    )
    assert edited.status_code == 200, edited.text

    creates = read(
        client, headers, f"?action=user_create&entity_id={user_id}"
    )["items"]
    assert len(creates) == 1 and creates[0]["entity_type"] == "user"

    updates = read(
        client, headers, f"?action=user_update&entity_id={user_id}"
    )["items"]
    assert len(updates) == 1
    assert updates[0]["old_value"]["role"] == "Employee"
    assert updates[0]["new_value"]["role"] == "Support agent"

    # A no-op edit writes nothing, so the audit log stays a record of changes.
    client.patch(
        f"/api/v1/users/{user_id}", headers=headers["admin"], json={"role": "Support agent"}
    )
    assert read(client, headers, f"?action=user_update&entity_id={user_id}")["total"] == 1


def test_ticket_changes_are_audited(api) -> None:
    client, _session, users, headers, category, _marker = api
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
    assert client.post(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=headers["admin"],
        json={"assignee_id": str(users["agent"].id)},
    ).status_code == 200

    creates = read(client, headers, f"?action=ticket_create&entity_id={ticket_id}")["items"]
    assert len(creates) == 1
    assert creates[0]["actor_id"] == str(users["employee"].id)
    assert creates[0]["new_value"]["status"] == "Open"
    assert creates[0]["new_value"]["priority"] == "Medium"

    updates = read(client, headers, f"?action=ticket_update&entity_id={ticket_id}")["items"]
    assert len(updates) == 1
    assert updates[0]["actor_id"] == str(users["admin"].id)
    assert updates[0]["old_value"]["assignee_id"] is None
    assert updates[0]["new_value"]["assignee_id"] == str(users["agent"].id)
    assert updates[0]["new_value"]["status"] == "Assigned"


def test_filters_paging_and_ordering(api) -> None:
    client, _session, users, headers, category, _marker = api
    created = client.post(
        "/api/v1/tickets",
        headers=headers["employee"],
        json={
            "title": "Filter me",
            "description": "One ticket",
            "category_id": str(category.id),
        },
    )
    ticket_id = created.json()["id"]

    everything = read(client, headers, "?limit=100")
    stamps = [entry["created_at"] for entry in everything["items"]]
    assert stamps == sorted(stamps, reverse=True)

    page = read(client, headers, "?limit=2&offset=0")
    assert len(page["items"]) == 2 and page["total"] == everything["total"]
    rest = read(client, headers, "?limit=2&offset=2")
    assert [e["id"] for e in page["items"] + rest["items"]] == [
        e["id"] for e in everything["items"][:4]
    ]

    by_entity = read(client, headers, f"?entity_type=ticket&entity_id={ticket_id}")
    assert by_entity["total"] == 1
    assert all(e["entity_type"] == "ticket" for e in by_entity["items"])

    # An unknown vocabulary value is a valid query that matches nothing.
    assert read(client, headers, "?action=not_a_real_action") == {"items": [], "total": 0}
    assert read(client, headers, f"?actor_id={uuid4()}")["total"] == 0

    # The contract writes timestamps ending in `Z`. That form also avoids the
    # `+` in `+00:00`, which a query string would decode as a space unless the
    # client percent-encodes it.
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert read(client, headers, f"?created_from={future}")["total"] == 0
    assert read(client, headers, f"?created_to={past}")["total"] == 0
    assert read(client, headers, f"?created_from={past}")["total"] == everything["total"]


def test_query_validation(api) -> None:
    client, _session, _users, headers, _category, _marker = api
    for query in (
        "?limit=0", "?limit=101", "?offset=-1", "?limit=oops",
        "?actor_id=not-a-uuid", "?entity_id=not-a-uuid", "?created_from=not-a-date",
    ):
        assert client.get(
            f"/api/v1/audit-logs{query}", headers=headers["admin"]
        ).status_code == 422, query
