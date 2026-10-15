"""T05 category API checks against rollback-isolated PostgreSQL."""

from pathlib import Path
from uuid import UUID, uuid4

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
from app.models import Category, Role, Ticket, User


BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "test-password-2026"


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-long-enough-for-hs256-2026")
    get_settings.cache_clear()
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 5})
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint",
            autoflush=False, expire_on_commit=False,
        )
        try:
            marker = uuid4().hex[:10]
            users = {}
            for key, role_name in (
                ("employee", "Employee"), ("agent", "Support agent"),
                ("admin", "Admin"),
            ):
                role = session.scalar(select(Role).where(Role.name == role_name))
                if role is None:
                    role = Role(name=role_name)
                    session.add(role)
                    session.flush()
                user = User(
                    name=f"Test {key}", email=f"{marker}.{key}@example.test",
                    role=role, password_hash=hash_password(PASSWORD),
                )
                session.add(user)
                session.flush()
                users[key] = user
            active = Category(name=f"[{marker}] Hardware", description="Devices")
            inactive = Category(
                name=f"[{marker}] Retired", description="Old devices", is_active=False
            )
            session.add_all([active, inactive])
            session.commit()

            def override_db():
                yield session

            app.dependency_overrides[get_db] = override_db
            with TestClient(app) as client:
                headers = {}
                for key, user in users.items():
                    response = client.post("/api/v1/auth/login", json={
                        "email": user.email, "password": PASSWORD,
                    })
                    assert response.status_code == 200, response.text
                    headers[key] = {"Authorization": f"Bearer {response.json()['access_token']}"}
                yield client, session, users, headers, active, inactive, marker
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def test_list_active_categories_for_all_roles_with_pagination(api) -> None:
    client, _session, _users, headers, active, inactive, _marker = api
    assert client.get("/api/v1/categories").status_code == 401
    for role in ("employee", "agent", "admin"):
        response = client.get("/api/v1/categories?limit=100&offset=0", headers=headers[role])
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert response.json()["total"] >= 1
        own = next(item for item in items if item["id"] == str(active.id))
        assert set(own) == {"id", "name", "description", "is_active", "created_at", "updated_at"}
        assert own["name"] == active.name and own["description"] == active.description
        assert own["is_active"] is True
        assert all(item["is_active"] is True for item in items)
        assert str(inactive.id) not in response.text
        past_end = client.get(f"/api/v1/categories?offset={response.json()['total']}",
                              headers=headers[role])
        assert past_end.json() == {"items": [], "total": response.json()["total"]}
    for query in ("limit=0", "limit=101", "offset=-1", "limit=oops"):
        assert client.get(f"/api/v1/categories?{query}", headers=headers["employee"]).status_code == 422


def test_admin_create_update_duplicate_and_validation(api) -> None:
    client, session, _users, headers, active, inactive, marker = api
    path = "/api/v1/categories"
    payload = {"name": f"  [{marker}] Software  ", "description": "Licenses"}
    for role in ("employee", "agent"):
        assert client.post(path, json=payload, headers=headers[role]).status_code == 403
        assert client.patch(f"{path}/{active.id}", json={"name": "Other"},
                            headers=headers[role]).status_code == 403
    assert client.post(path, json=payload).status_code == 401
    made = client.post(path, json=payload, headers=headers["admin"])
    assert made.status_code == 201, made.text
    item = made.json()
    assert set(item) == {"id", "name", "description", "is_active", "created_at", "updated_at"}
    assert item["name"] == f"[{marker}] Software" and item["is_active"] is True
    assert client.post(path, json={"name": item["name"], "description": "again"},
                       headers=headers["admin"]).status_code == 409
    assert client.patch(f"{path}/{item['id']}", json={"name": active.name},
                        headers=headers["admin"]).status_code == 409
    assert client.post(path, json={"name": inactive.name, "description": "again"},
                       headers=headers["admin"]).status_code == 409
    for bad in (
        {"name": "   ", "description": "x"},
        {"name": "x"},
        {"name": "x", "description": "x", "extra": True},
        {"name": "x" * 81, "description": "x"},
    ):
        assert client.post(path, json=bad, headers=headers["admin"]).status_code == 422
    for bad in ({}, {"name": "   "}, {"is_active": None}, {"description": None},
                {"unexpected": True}):
        assert client.patch(f"{path}/{item['id']}", json=bad,
                            headers=headers["admin"]).status_code == 422
    assert client.patch(f"{path}/{uuid4()}", json={"description": "x"},
                        headers=headers["admin"]).status_code == 404
    assert client.patch(f"{path}/not-a-uuid", json={"description": "x"},
                        headers=headers["admin"]).status_code == 422

    unchanged = client.patch(f"{path}/{item['id']}", json={"description": "Licenses"},
                             headers=headers["admin"])
    assert unchanged.status_code == 200
    assert unchanged.json()["updated_at"] == item["updated_at"]

    updated = client.patch(f"{path}/{item['id']}", json={
        "name": f"  [{marker}] Apps  ", "description": "", "is_active": False,
    }, headers=headers["admin"])
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == f"[{marker}] Apps"
    assert updated.json()["description"] == "" and updated.json()["is_active"] is False
    assert session.get(Category, active.id).is_active is True
    assert session.get(Category, inactive.id).is_active is False
    assert str(item["id"]) not in client.get(path, headers=headers["employee"]).text
    assert session.get(Category, UUID(item["id"])) is not None


def test_deactivation_keeps_existing_ticket_but_blocks_new_ones(api) -> None:
    client, session, _users, headers, active, _inactive, _marker = api
    created = client.post("/api/v1/tickets", headers=headers["employee"], json={
        "title": "Printer broken", "description": "It jams", "category_id": str(active.id),
    })
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    disabled = client.patch(f"/api/v1/categories/{active.id}",
                            headers=headers["admin"], json={"is_active": False})
    assert disabled.status_code == 200, disabled.text
    assert session.get(Ticket, UUID(ticket_id)).category_id == active.id
    assert client.get(f"/api/v1/tickets/{ticket_id}",
                      headers=headers["employee"]).status_code == 200
    assert client.post("/api/v1/tickets", headers=headers["employee"], json={
        "title": "Another issue", "description": "Again", "category_id": str(active.id),
    }).status_code == 400
    assert str(active.id) not in client.get(
        "/api/v1/categories", headers=headers["employee"]
    ).text
    restored = client.patch(f"/api/v1/categories/{active.id}",
                            headers=headers["admin"], json={"is_active": True})
    assert restored.status_code == 200
    assert str(active.id) in client.get(
        "/api/v1/categories", headers=headers["employee"]
    ).text
