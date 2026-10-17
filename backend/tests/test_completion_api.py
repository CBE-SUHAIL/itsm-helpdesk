"""Integration checks for articles, reporting, dashboard, and admin settings."""

import csv
from datetime import timedelta
from io import StringIO
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
from app.models import AuditLog, Category, Notification, Role, Ticket, User
from app.models.role import utc_now


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
        session = Session(bind=connection, join_transaction_mode="create_savepoint",
                          autoflush=False, expire_on_commit=False)
        try:
            marker = uuid4().hex[:10]
            roles = {}
            for name in ("Employee", "Support agent", "Admin"):
                role = session.scalar(select(Role).where(Role.name == name))
                if role is None:
                    role = Role(name=name)
                    session.add(role)
                    session.flush()
                roles[name] = role
            users = {}
            for key, role in (("employee", "Employee"), ("other", "Employee"),
                              ("agent", "Support agent"), ("admin", "Admin")):
                user = User(name=f"Test {key}", email=f"{marker}.{key}@example.test",
                            role=roles[role], password_hash=hash_password(PASSWORD))
                session.add(user)
                session.flush()
                users[key] = user
            category = Category(name=f"[{marker}] Support", description="Support")
            inactive = Category(name=f"[{marker}] Retired", description="Old", is_active=False)
            session.add_all([category, inactive])
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
                yield client, session, users, headers, category, inactive
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def test_article_draft_visibility_and_publish(api):
    client, _session, users, headers, category, inactive = api
    url = "/api/v1/articles"
    payload = {"title": "  Reset password  ", "body": "  Use the portal.  ",
               "category_id": str(category.id)}
    assert client.post(url, headers=headers["employee"], json=payload).status_code == 403
    assert client.post(url, headers=headers["agent"], json={
        **payload, "category_id": str(inactive.id),
    }).status_code == 400
    made = client.post(url, headers=headers["agent"], json=payload)
    assert made.status_code == 201, made.text
    article = made.json()
    assert article["title"] == "Reset password" and article["is_published"] is False
    assert article["author_id"] == str(users["agent"].id)
    assert client.get(f"{url}/{article['id']}", headers=headers["employee"]).status_code == 404
    assert client.get(url, headers=headers["employee"]).json()["total"] == 0
    assert client.get(url, headers=headers["agent"]).json()["total"] == 1
    assert client.patch(f"{url}/{article['id']}", headers=headers["employee"],
                        json={"title": "Wrong"}).status_code == 403
    changed = client.patch(f"{url}/{article['id']}", headers=headers["agent"],
                           json={"body": "Use your company account."})
    assert changed.status_code == 200, changed.text
    assert client.patch(f"{url}/{article['id']}", headers=headers["agent"],
                        json={}).status_code == 422
    assert client.post(f"{url}/{article['id']}/publish", headers=headers["agent"],
                       json={"published": True}).status_code == 403
    published = client.post(f"{url}/{article['id']}/publish", headers=headers["admin"],
                            json={"published": True})
    assert published.status_code == 200, published.text
    assert client.get(f"{url}?q=company", headers=headers["employee"]).json()["total"] == 1
    assert client.get(f"{url}/{article['id']}", headers=headers["employee"]).status_code == 200
    assert client.patch(f"{url}/{article['id']}", headers=headers["agent"],
                        json={"title": "Wrong"}).status_code == 404
    assert client.patch(f"{url}/{article['id']}", headers=headers["admin"],
                        json={"title": "Account help"}).status_code == 200
    assert client.post(f"{url}/{article['id']}/publish", headers=headers["admin"],
                       json={"published": False}).status_code == 200
    assert client.get(f"{url}/{article['id']}", headers=headers["employee"]).status_code == 404


def test_dashboard_and_report_scoping_filters_and_downloads(api):
    client, session, users, headers, category, _inactive = api
    def create(owner: str, title: str):
        response = client.post("/api/v1/tickets", headers=headers[owner], json={
            "title": title, "description": "Please help", "category_id": str(category.id),
        })
        assert response.status_code == 201, response.text
        return response.json()

    first = create("employee", "Laptop issue")
    second = create("other", "=HYPERLINK(\"https://example.test\")")
    mine = client.get("/api/v1/dashboard/summary", headers=headers["employee"])
    assert mine.status_code == 200, mine.text
    assert mine.json()["counts_by_status"]["Open"] == 1
    assert mine.json()["agent_workload"] is None
    all_tickets = client.get("/api/v1/dashboard/summary", headers=headers["admin"])
    assert all_tickets.json()["counts_by_status"]["Open"] >= 2
    assert isinstance(all_tickets.json()["agent_workload"], dict)
    assert client.get("/api/v1/reports/tickets?format=csv",
                      headers=headers["employee"]).status_code == 403
    response = client.get(f"/api/v1/reports/tickets?format=csv&category_id={category.id}",
                          headers=headers["agent"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(response.text)))
    assert {row["id"] for row in rows} == {first["id"], second["id"]}
    assert any(row["title"].startswith("'=HYPERLINK") for row in rows)
    assert rows[0]["response_overdue"] in ("true", "false")
    pdf = client.get(f"/api/v1/reports/tickets?format=pdf&category_id={category.id}",
                     headers=headers["admin"])
    assert pdf.status_code == 200, pdf.text if pdf.status_code != 200 else ""
    assert pdf.content.startswith(b"%PDF-")
    assert len(pdf.content) > 1000
    assert client.get("/api/v1/reports/tickets?format=xls",
                      headers=headers["admin"]).status_code == 422
    assert session.get(Ticket, first["id"]).creator_id == users["employee"].id


def test_settings_validation_and_audit(api):
    client, session, _users, headers, _category, _inactive = api
    url = "/api/v1/settings"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers["agent"]).status_code == 403
    original = client.get(url, headers=headers["admin"])
    assert original.status_code == 200, original.text
    shape = original.json()
    assert set(shape) == {"sla_targets", "max_attachment_bytes", "allowed_attachment_types"}
    for bad in ({}, {"max_attachment_bytes": 0}, {"allowed_attachment_types": []},
                {"allowed_attachment_types": ["application/zip"]},
                {"sla_targets": {k: {"first_response_hours": 10, "resolution_hours": 2}
                                 for k in ("Low", "Medium", "High", "Critical")}}):
        response = client.patch(url, headers=headers["admin"], json=bad)
        assert response.status_code in (400, 422), response.text
    updated = client.patch(url, headers=headers["admin"], json={
        "max_attachment_bytes": shape["max_attachment_bytes"] + 1,
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["max_attachment_bytes"] == shape["max_attachment_bytes"] + 1
    logs = session.scalars(select(AuditLog).where(AuditLog.action == "settings_update")).all()
    assert len(logs) == 1
    assert logs[0].old_value["max_attachment_bytes"] == shape["max_attachment_bytes"]
    assert logs[0].new_value["max_attachment_bytes"] == shape["max_attachment_bytes"] + 1
    assert client.patch(url, headers=headers["admin"], json={
        "max_attachment_bytes": shape["max_attachment_bytes"] + 1,
    }).status_code == 200
    assert len(session.scalars(select(AuditLog).where(AuditLog.action == "settings_update")).all()) == 1


def test_ticket_search_and_admin_inactive_categories(api):
    client, _session, _users, headers, category, inactive = api
    assert client.get("/api/v1/categories?include_inactive=true",
                      headers=headers["agent"]).status_code == 403
    categories = client.get("/api/v1/categories?include_inactive=true",
                            headers=headers["admin"])
    assert categories.status_code == 200
    assert str(inactive.id) in {row["id"] for row in categories.json()["items"]}
    created = client.post("/api/v1/tickets", headers=headers["employee"], json={
        "title": "Distinct network issue", "description": "WiFi drops at desk",
        "category_id": str(category.id),
    })
    assert created.status_code == 201, created.text
    assert client.get("/api/v1/tickets?q=network", headers=headers["employee"]).json()["total"] == 1
    assert client.get("/api/v1/tickets?q=WiFi", headers=headers["employee"]).json()["total"] == 1
    assert client.get("/api/v1/tickets?q=nonexistent", headers=headers["employee"]).json()["total"] == 0


def test_sla_breach_notification_is_created_once_and_scoped(api):
    client, session, users, headers, category, _inactive = api
    created = client.post("/api/v1/tickets", headers=headers["employee"], json={
        "title": "Overdue issue", "description": "Needs help", "category_id": str(category.id),
    })
    assert created.status_code == 201, created.text
    ticket = session.get(Ticket, created.json()["id"])
    ticket.response_due_at = utc_now() - timedelta(hours=1)
    session.commit()
    inbox = client.get("/api/v1/notifications", headers=headers["admin"])
    assert inbox.status_code == 200, inbox.text
    assert sum(row["type"] == "sla_breach" and row["ticket_id"] == str(ticket.id)
               for row in inbox.json()["items"]) == 1
    assert client.get("/api/v1/notifications", headers=headers["admin"]).status_code == 200
    assert session.scalar(select(Notification).where(
        Notification.ticket_id == ticket.id, Notification.type == "sla_breach",
        Notification.recipient_id == users["employee"].id,
    )) is None
    notices = session.scalars(select(Notification).where(
        Notification.ticket_id == ticket.id, Notification.type == "sla_breach",
        Notification.recipient_id == users["admin"].id,
    )).all()
    assert len(notices) == 1


def test_employee_agent_admin_end_to_end_journey(api):
    client, _session, users, headers, category, _inactive = api
    base = "/api/v1"
    title = f"VPN access {uuid4().hex[:10]}"
    created = client.post(f"{base}/tickets", headers=headers["employee"], json={
        "title": title, "description": "Cannot connect",
        "category_id": str(category.id),
    })
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    assert created.json()["status"] == "Open"
    assert client.get(f"{base}/tickets?q={title}", headers=headers["agent"]).json()["total"] == 1
    assigned = client.post(f"{base}/tickets/{ticket_id}/assignment", headers=headers["agent"],
                           json={"assignee_id": str(users["agent"].id)})
    assert assigned.status_code == 200 and assigned.json()["status"] == "Assigned"
    assert client.post(f"{base}/tickets/{ticket_id}/status", headers=headers["agent"],
                       json={"status": "In Progress"}).status_code == 200
    assert client.post(f"{base}/tickets/{ticket_id}/comments", headers=headers["agent"],
                       json={"body": "Checking the VPN profile."}).status_code == 201
    resolved = client.post(f"{base}/tickets/{ticket_id}/status", headers=headers["agent"],
                           json={"status": "Resolved", "resolution_note": "Profile repaired."})
    assert resolved.status_code == 200, resolved.text
    inbox = client.get(f"{base}/notifications", headers=headers["employee"])
    assert any(row["type"] == "resolution" and row["ticket_id"] == ticket_id
               for row in inbox.json()["items"])
    closed = client.post(f"{base}/tickets/{ticket_id}/status", headers=headers["employee"],
                         json={"status": "Closed"})
    assert closed.status_code == 200 and closed.json()["status"] == "Closed"
    history = client.get(f"{base}/tickets/{ticket_id}/history", headers=headers["admin"])
    assert history.status_code == 200 and history.json()["total"] >= 4
    report = client.get(f"{base}/reports/tickets?format=csv&status=Closed",
                        headers=headers["admin"])
    assert report.status_code == 200 and ticket_id in report.text
    audit = client.get(f"{base}/audit-logs?action=ticket_update", headers=headers["admin"])
    assert audit.status_code == 200 and audit.json()["total"] >= 4
