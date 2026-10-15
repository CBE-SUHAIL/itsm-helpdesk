"""A01–A03 and A06: real Postgres, rollback-isolated HTTP integration tests."""

from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.passwords import hash_password
from app.core.security import ISSUER, token_hash
from app.main import app
from app.models import AuditLog, RefreshToken, Role, User
from app.models.role import utc_now


BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "test-password-2026"
SECRET = "test-only-secret-long-enough-for-hs256-2026"


@pytest.fixture()
def client_db(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    get_settings.cache_clear()
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 5})
    config = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint",
            autoflush=False, expire_on_commit=False,
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
            for key, role in (("employee", "Employee"), ("agent", "Support agent"),
                              ("admin", "Admin")):
                user = User(
                    name=f"Test {key}", email=f"{marker}.{key}@example.test",
                    role=roles[role], password_hash=hash_password(PASSWORD),
                )
                session.add(user)
                session.flush()
                users[key] = user
            session.commit()

            def override_db():
                yield session

            app.dependency_overrides[get_db] = override_db
            with TestClient(app) as client:
                yield client, session, users
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def sign_in(client: TestClient, user: User) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(pair: dict) -> dict:
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_login_audit_tokens_and_invalid_input(client_db) -> None:
    client, session, users = client_db
    admin = users["admin"]
    bad = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "wrong"})
    missing = client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "wrong"})
    assert bad.status_code == missing.status_code == 401
    assert bad.json() == missing.json()
    invalid = client.post("/api/v1/auth/login", json={"email": admin.email,
        "password": "SECRET-MUST-NOT-ECHO", "extra": True})
    assert invalid.status_code == 422
    assert "SECRET-MUST-NOT-ECHO" not in invalid.text

    pair = sign_in(client, admin)
    assert pair["user"]["role"] == "Admin"
    assert "password_hash" not in pair["user"]
    assert client.get("/api/v1/users/me", headers=bearer(pair)).status_code == 200
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers={"Authorization": "Bearer wrong"}).status_code == 401
    stored = session.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == token_hash(pair["refresh_token"])))
    assert stored is not None
    assert pair["refresh_token"] != stored.token_hash
    logs = session.scalars(select(AuditLog).where(AuditLog.entity_type == "auth")).all()
    assert any(log.new_value == {"attempted_email": admin.email} for log in logs)
    assert all("wrong" not in str(log.new_value) for log in logs)


def test_refresh_rotation_logout_expiry_and_role_checks(client_db) -> None:
    client, session, users = client_db
    employee = sign_in(client, users["employee"])
    agent = sign_in(client, users["agent"])
    assert client.get("/api/v1/users", headers=bearer(employee)).status_code == 403
    assert client.get("/api/v1/users", headers=bearer(agent)).status_code == 403
    assert client.post("/api/v1/users", headers=bearer(employee), json={}).status_code == 403

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": employee["refresh_token"]})
    assert rotated.status_code == 200
    newer = rotated.json()
    assert newer["refresh_token"] != employee["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": employee["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=bearer(newer),
        json={"refresh_token": newer["refresh_token"]}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": newer["refresh_token"]}).status_code == 401

    expired = jwt.encode({"iss": ISSUER, "sub": str(users["employee"].id),
        "role": "Employee", "typ": "access", "iat": utc_now() - timedelta(hours=2),
        "exp": utc_now() - timedelta(hours=1)}, SECRET, algorithm="HS256")
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    assert session.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == token_hash(newer["refresh_token"]))).revoked_at is not None


def test_admin_can_manage_users_without_exposing_hash_or_losing_last_admin(client_db) -> None:
    client, session, users = client_db
    admin = sign_in(client, users["admin"])
    assert client.patch(f"/api/v1/users/{users['admin'].id}", headers=bearer(admin),
        json={"is_active": False}).status_code == 400
    email = f"new-{uuid4().hex[:8]}@example.test"
    made = client.post("/api/v1/users", headers=bearer(admin), json={
        "name": "  New Person  ", "email": email.upper(),
        "password": PASSWORD, "role": "Employee",
    })
    assert made.status_code == 201, made.text
    item = made.json()
    assert item["name"] == "New Person" and item["email"] == email
    assert "password" not in item and "password_hash" not in item
    assert client.post("/api/v1/users", headers=bearer(admin), json={
        "name": "Duplicate", "email": email, "password": PASSWORD,
        "role": "Employee"}).status_code == 409
    page = client.get("/api/v1/users?role=Employee&is_active=true&limit=1", headers=bearer(admin))
    assert page.status_code == 200
    assert page.json()["total"] >= 2 and len(page.json()["items"]) == 1
    assert client.patch(f"/api/v1/users/{item['id']}", headers=bearer(admin), json={}).status_code == 422
    updated = client.patch(f"/api/v1/users/{item['id']}", headers=bearer(admin),
        json={"role": "Support agent", "name": "Updated Person"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "Support agent"
    assert client.patch(f"/api/v1/users/{item['id']}", headers=bearer(admin),
        json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert session.scalar(select(User).where(User.email == email)).is_active is False
    changes = session.scalars(select(AuditLog).where(
        AuditLog.entity_id == UUID(item["id"]))).all()
    assert [entry.action for entry in changes].count("user_create") == 1
    assert [entry.action for entry in changes].count("user_update") == 2
    assert all("password" not in str(entry.new_value) for entry in changes)


def test_changed_role_invalidates_old_access_token(client_db) -> None:
    client, _session, users = client_db
    admin = sign_in(client, users["admin"])
    employee = sign_in(client, users["employee"])
    changed = client.patch(f"/api/v1/users/{users['employee'].id}", headers=bearer(admin),
        json={"role": "Support agent"})
    assert changed.status_code == 200
    assert client.get("/api/v1/users/me", headers=bearer(employee)).status_code == 401
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": employee["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.get("/api/v1/users/me", headers=bearer(refreshed.json())).json()["role"] == "Support agent"
