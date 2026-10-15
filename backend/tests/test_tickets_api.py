"""T01-T06: tickets, lifecycle, assignment, priority, comments, and history.

Real PostgreSQL, rollback-isolated HTTP tests, matching the pattern A01-A03
established: the fixture opens one outer transaction, points `get_db` at it, and
rolls everything back, so the development database keeps no test rows.
"""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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
from app.models import (
    AuditLog,
    Category,
    Comment,
    Notification,
    Role,
    Ticket,
    TicketHistory,
    User,
)
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
    config = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(config, "head")
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
            actors = {}
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
                actors[key] = user
            category = Category(
                name=f"[{marker}] Hardware", description="Test", is_active=True
            )
            inactive = Category(
                name=f"[{marker}] Retired", description="Inactive", is_active=False
            )
            session.add_all([category, inactive])
            session.flush()
            session.commit()

            def override_db():
                yield session

            app.dependency_overrides[get_db] = override_db
            with TestClient(app) as client:
                yield SimpleNamespace(
                    client=client,
                    session=session,
                    actors=actors,
                    category=category,
                    inactive=inactive,
                    marker=marker,
                )
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def auth(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create(api, headers, *, title="Laptop will not boot", category=None) -> dict:
    response = api.client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": title,
            "description": "Black screen on power.",
            "category_id": str((category or api.category).id),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def assign(api, headers, ticket, assignee) -> dict:
    response = api.client.post(
        f"/api/v1/tickets/{ticket['id']}/assignment",
        headers=headers,
        json={"assignee_id": str(assignee.id) if assignee else None},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_ticket_starts_open_medium_unassigned_with_sla_deadlines(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    ticket = create(api, employee)

    assert ticket["status"] == "Open"
    assert ticket["priority"] == "Medium"
    assert ticket["assignee_id"] is None
    assert ticket["first_response_at"] is None and ticket["resolved_at"] is None
    assert ticket["response_overdue"] is False and ticket["resolution_overdue"] is False
    # REQUIREMENTS: Medium is 8 hours to respond and 48 to resolve, in calendar hours.
    assert parse(ticket["response_due_at"]) - parse(ticket["created_at"]) == timedelta(hours=8)
    assert parse(ticket["resolution_due_at"]) - parse(ticket["created_at"]) == timedelta(hours=48)

    # Creation is audited but is not a change, so it writes no history row.
    audits = api.session.scalars(
        select(AuditLog).where(AuditLog.entity_id == UUID(ticket["id"]))
    ).all()
    assert [entry.action for entry in audits] == ["ticket_create"]
    assert api.session.scalars(
        select(TicketHistory).where(TicketHistory.ticket_id == UUID(ticket["id"]))
    ).all() == []


def test_create_ticket_rejects_priority_non_employee_and_bad_category(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    admin = auth(api.client, api.actors["admin"])

    rejected = api.client.post(
        "/api/v1/tickets",
        headers=employee,
        json={
            "title": "Needs a priority",
            "description": "Body",
            "category_id": str(api.category.id),
            "priority": "Critical",
        },
    )
    assert rejected.status_code == 422

    body = {
        "title": "Agent attempt",
        "description": "Body",
        "category_id": str(api.category.id),
    }
    assert api.client.post("/api/v1/tickets", headers=agent, json=body).status_code == 403
    assert api.client.post("/api/v1/tickets", headers=admin, json=body).status_code == 403

    inactive = api.client.post(
        "/api/v1/tickets",
        headers=employee,
        json={**body, "category_id": str(api.inactive.id)},
    )
    assert inactive.status_code == 400

    missing = api.client.post(
        "/api/v1/tickets",
        headers=employee,
        json={**body, "category_id": str(uuid4())},
    )
    assert missing.status_code == 404


def test_employees_see_own_tickets_only_and_other_ids_are_404(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    other = auth(api.client, api.actors["other_employee"])
    agent = auth(api.client, api.actors["agent"])
    admin = auth(api.client, api.actors["admin"])

    ticket = create(api, employee)

    assert api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=other).status_code == 404
    assert api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=agent).status_code == 200
    assert api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=admin).status_code == 200

    own = api.client.get("/api/v1/tickets", headers=employee).json()
    assert own["total"] == 1 and own["items"][0]["id"] == ticket["id"]
    assert api.client.get("/api/v1/tickets", headers=other).json()["total"] == 0
    assert api.client.get("/api/v1/tickets", headers=agent).json()["total"] == 1

    filtered = api.client.get(
        "/api/v1/tickets?status=Open&priority=Medium&category_id=" + str(api.category.id),
        headers=employee,
    ).json()
    assert filtered["total"] == 1
    assert api.client.get("/api/v1/tickets?status=Resolved", headers=employee).json()["total"] == 0
    assert api.client.get("/api/v1/tickets?status=Nonsense", headers=employee).status_code == 422


def test_agent_self_assigns_and_writes_history_audit_and_notification(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    other_agent = auth(api.client, api.actors["other_agent"])
    ticket = create(api, employee)

    result = assign(api, agent, ticket, api.actors["agent"])
    assert result["status"] == "Assigned"
    assert result["assignee_id"] == str(api.actors["agent"].id)

    # An agent may only self-assign, and only while the ticket is open.
    assert api.client.post(
        f"/api/v1/tickets/{ticket['id']}/assignment",
        headers=agent,
        json={"assignee_id": str(api.actors["other_agent"].id)},
    ).status_code == 403
    assert api.client.post(
        f"/api/v1/tickets/{ticket['id']}/assignment",
        headers=other_agent,
        json={"assignee_id": str(api.actors["other_agent"].id)},
    ).status_code == 409

    history = api.session.scalars(
        select(TicketHistory).where(TicketHistory.ticket_id == UUID(ticket["id"]))
    ).all()
    assert {entry.field for entry in history} == {"status", "assignee_id"}
    assert all(entry.actor_id == api.actors["agent"].id for entry in history)

    audits = api.session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == UUID(ticket["id"]), AuditLog.action == "ticket_update"
        )
    ).all()
    assert [entry.actor_id for entry in audits] == [api.actors["agent"].id]

    notices = api.session.scalars(
        select(Notification).where(Notification.ticket_id == UUID(ticket["id"]))
    ).all()
    assert [notice.type for notice in notices] == ["assignment"]
    assert notices[0].recipient_id == api.actors["agent"].id


def test_admin_reassigns_and_unassigns_but_agent_cannot(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    admin = auth(api.client, api.actors["admin"])
    ticket = create(api, employee)

    first = assign(api, admin, ticket, api.actors["agent"])
    assert first["status"] == "Assigned"
    second = assign(api, admin, first, api.actors["other_agent"])
    assert second["assignee_id"] == str(api.actors["other_agent"].id)
    assert second["status"] == "Assigned"

    assert api.client.post(
        f"/api/v1/tickets/{ticket['id']}/assignment",
        headers=agent,
        json={"assignee_id": None},
    ).status_code == 403

    unassigned = assign(api, admin, second, None)
    assert unassigned["assignee_id"] is None and unassigned["status"] == "Open"

    history = api.session.scalars(
        select(TicketHistory).where(TicketHistory.ticket_id == UUID(ticket["id"]))
    ).all()
    # Reassigning changes only the assignee; assigning and unassigning also move status.
    assert [entry.field for entry in history].count("assignee_id") == 3
    assert [entry.field for entry in history].count("status") == 2


def test_lifecycle_transitions_enforce_actor_and_order(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    other_agent = auth(api.client, api.actors["other_agent"])
    ticket = create(api, employee)
    assigned = assign(api, agent, ticket, api.actors["agent"])

    def move(headers, status, **extra):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            headers=headers,
            json={"status": status, **extra},
        )

    # No skipping: Open cannot jump to Resolved, and Open is not reachable here.
    assert move(agent, "Resolved", resolution_note="done").status_code == 409
    assert move(agent, "Open").status_code == 409

    # Only the assigned agent may start work.
    assert move(other_agent, "In Progress").status_code == 403
    assert move(employee, "In Progress").status_code == 403
    started = move(agent, "In Progress")
    assert started.status_code == 200 and started.json()["status"] == "In Progress"

    # Resolving requires a non-blank note.
    assert move(agent, "Resolved").status_code == 422
    assert move(agent, "Resolved", resolution_note="   ").status_code == 422
    assert move(employee, "Resolved", resolution_note="done").status_code == 403
    resolved = move(agent, "Resolved", resolution_note="Replaced the power supply.")
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "Resolved" and body["resolved_at"] is not None

    # The resolution note is kept on the history row for the status change.
    note = api.session.scalars(
        select(TicketHistory).where(
            TicketHistory.ticket_id == UUID(ticket["id"]),
            TicketHistory.field == "status",
            TicketHistory.new_value == "Resolved",
        )
    ).one()
    assert note.reason == "Replaced the power supply."

    # Only the creator or an admin may close, and only from Resolved.
    assert move(agent, "Closed").status_code == 403
    closed = move(employee, "Closed")
    assert closed.status_code == 200 and closed.json()["status"] == "Closed"
    assert move(agent, "In Progress").status_code == 409

    assert assigned["status"] == "Assigned"


def test_returning_a_resolved_ticket_clears_its_resolution(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    ticket = create(api, employee)
    assign(api, agent, ticket, api.actors["agent"])

    def move(status, **extra):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/status",
            headers=agent,
            json={"status": status, **extra},
        )

    move("In Progress")
    assert move("Resolved", resolution_note="Fixed.").json()["resolved_at"] is not None
    # REQUIREMENTS: a returned ticket's previous resolution no longer counts.
    reopened = move("In Progress")
    assert reopened.status_code == 200
    assert reopened.json()["resolved_at"] is None


def test_priority_change_requires_reason_and_recomputes_deadlines(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    other_agent = auth(api.client, api.actors["other_agent"])
    admin = auth(api.client, api.actors["admin"])
    ticket = create(api, employee)
    assign(api, agent, ticket, api.actors["agent"])

    def reprioritise(headers, payload):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/priority", headers=headers, json=payload
        )

    assert reprioritise(agent, {"priority": "High"}).status_code == 422
    assert reprioritise(agent, {"priority": "High", "reason": "  "}).status_code == 422
    assert reprioritise(other_agent, {"priority": "High", "reason": "Urgent"}).status_code == 403
    assert reprioritise(employee, {"priority": "High", "reason": "Urgent"}).status_code == 403

    changed = reprioritise(agent, {"priority": "High", "reason": "Customer escalation"})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["priority"] == "High"
    # Priority determines the deadlines, measured from the ticket's creation.
    assert parse(body["response_due_at"]) - parse(body["created_at"]) == timedelta(hours=2)
    assert parse(body["resolution_due_at"]) - parse(body["created_at"]) == timedelta(hours=24)

    entry = api.session.scalars(
        select(TicketHistory).where(
            TicketHistory.ticket_id == UUID(ticket["id"]),
            TicketHistory.field == "priority",
        )
    ).one()
    assert (entry.old_value, entry.new_value) == ("Medium", "High")
    assert entry.reason == "Customer escalation"
    assert entry.actor_id == api.actors["agent"].id

    assert reprioritise(admin, {"priority": "Critical", "reason": "Admin override"}).status_code == 200


def test_comments_record_the_first_response_and_notify_the_other_side(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    other_agent = auth(api.client, api.actors["other_agent"])
    ticket = create(api, employee)
    assign(api, agent, ticket, api.actors["agent"])

    def comment(headers, body):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/comments", headers=headers, json={"body": body}
        )

    assert comment(other_agent, "Not mine").status_code == 403
    assert comment(employee, "   ").status_code == 422
    assert comment(employee, "Any update?").status_code == 201

    # Assignment alone is not a response; the assigned agent's comment is.
    assert api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=employee).json()[
        "first_response_at"
    ] is None
    first = comment(agent, "Looking into it now.")
    assert first.status_code == 201
    assert api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=employee).json()[
        "first_response_at"
    ] is not None

    # Each side of the conversation is told about the other's comment.
    notices = api.session.scalars(
        select(Notification).where(
            Notification.ticket_id == UUID(ticket["id"]), Notification.type == "comment"
        )
    ).all()
    assert {notice.recipient_id for notice in notices} == {
        api.actors["employee"].id,
        api.actors["agent"].id,
    }
    assert len(notices) == 2

    listed = api.client.get(f"/api/v1/tickets/{ticket['id']}/comments", headers=employee)
    assert listed.status_code == 200
    bodies = [item["body"] for item in listed.json()["items"]]
    assert bodies == ["Any update?", "Looking into it now."]

    assert api.session.scalars(
        select(Comment).where(Comment.ticket_id == UUID(ticket["id"]))
    ).all()


def test_overdue_flags_compare_deadlines_with_actuals_and_the_clock(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    ticket = create(api, employee)

    row = api.session.get(Ticket, UUID(ticket["id"]))
    row.response_due_at = utc_now() - timedelta(hours=2)
    row.resolution_due_at = utc_now() - timedelta(hours=2)
    api.session.commit()

    late = api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=employee).json()
    assert late["response_overdue"] is True and late["resolution_overdue"] is True

    # A breach stays visible once the work finally happens.
    row.first_response_at = utc_now()
    row.resolved_at = utc_now()
    api.session.commit()
    still = api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=employee).json()
    assert still["response_overdue"] is True and still["resolution_overdue"] is True


def test_history_is_oldest_first_and_paginated(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    ticket = create(api, employee)
    assign(api, agent, ticket, api.actors["agent"])
    api.client.post(
        f"/api/v1/tickets/{ticket['id']}/status",
        headers=agent,
        json={"status": "In Progress"},
    )

    page = api.client.get(f"/api/v1/tickets/{ticket['id']}/history?limit=1", headers=employee)
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3 and len(body["items"]) == 1
    # The assignment action writes both of its rows at one instant; `field`
    # breaks that tie, so the first page is stable rather than uuid-dependent.
    assert body["items"][0]["field"] == "assignee_id"

    everything = api.client.get(f"/api/v1/tickets/{ticket['id']}/history", headers=employee).json()
    stamps = [parse(item["created_at"]) for item in everything["items"]]
    assert stamps == sorted(stamps)
    statuses = [item["new_value"] for item in everything["items"] if item["field"] == "status"]
    assert statuses == ["Assigned", "In Progress"]


def test_assignment_rejects_an_assignee_who_cannot_work_tickets(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    admin = auth(api.client, api.actors["admin"])
    ticket = create(api, employee)

    retired = User(
        name="Retired agent",
        email=f"{api.marker}.retired@example.test",
        role=api.actors["agent"].role,
        password_hash=hash_password(PASSWORD),
        is_active=False,
    )
    api.session.add(retired)
    api.session.flush()

    def assign_to(value):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/assignment",
            headers=admin,
            json={"assignee_id": value},
        )

    # The contract's 400 for an invalid assignee: unknown, not an agent, or inactive.
    assert assign_to(str(uuid4())).status_code == 400
    assert assign_to(str(api.actors["other_employee"].id)).status_code == 400
    assert assign_to(str(retired.id)).status_code == 400
    unchanged = api.client.get(f"/api/v1/tickets/{ticket['id']}", headers=admin).json()
    assert unchanged["status"] == "Open" and unchanged["assignee_id"] is None

    # An employee may not reach the route at all.
    assert api.client.post(
        f"/api/v1/tickets/{ticket['id']}/assignment",
        headers=employee,
        json={"assignee_id": str(api.actors["agent"].id)},
    ).status_code == 403


def test_a_reassignment_that_changes_nothing_writes_nothing(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    admin = auth(api.client, api.actors["admin"])
    ticket = create(api, employee)

    first = assign(api, admin, ticket, api.actors["agent"])
    assert assign(api, admin, first, api.actors["agent"])["assignee_id"] == str(
        api.actors["agent"].id
    )

    # Assigning the same agent twice is a no-op: one history pair, one notice.
    notices = api.session.scalars(
        select(Notification).where(Notification.ticket_id == UUID(ticket["id"]))
    ).all()
    assert len(notices) == 1
    history = api.session.scalars(
        select(TicketHistory).where(TicketHistory.ticket_id == UUID(ticket["id"]))
    ).all()
    assert {entry.field for entry in history} == {"assignee_id", "status"}


def test_recategorising_needs_an_active_category_and_a_reason(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    other_agent = auth(api.client, api.actors["other_agent"])
    ticket = create(api, employee)
    assign(api, agent, ticket, api.actors["agent"])
    target = Category(name=f"[{api.marker}] Software", description="Test", is_active=True)
    api.session.add(target)
    api.session.flush()

    def recategorise(headers, payload):
        return api.client.post(
            f"/api/v1/tickets/{ticket['id']}/category", headers=headers, json=payload
        )

    assert recategorise(agent, {"category_id": str(target.id)}).status_code == 422
    assert recategorise(agent, {"category_id": str(target.id), "reason": "   "}).status_code == 422
    assert recategorise(other_agent, {"category_id": str(target.id), "reason": "Wrong queue"}).status_code == 403
    assert recategorise(employee, {"category_id": str(target.id), "reason": "Wrong queue"}).status_code == 403
    assert recategorise(agent, {"category_id": str(uuid4()), "reason": "Wrong queue"}).status_code == 404
    assert recategorise(agent, {"category_id": str(api.inactive.id), "reason": "Wrong queue"}).status_code == 400

    moved = recategorise(agent, {"category_id": str(target.id), "reason": "Wrong queue"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["category_id"] == str(target.id)

    entry = api.session.scalars(
        select(TicketHistory).where(
            TicketHistory.ticket_id == UUID(ticket["id"]),
            TicketHistory.field == "category_id",
        )
    ).one()
    assert entry.reason == "Wrong queue"
    assert (entry.old_value, entry.new_value) == (str(api.category.id), str(target.id))

    # A closed ticket is no longer recategorisable.
    api.client.post(
        f"/api/v1/tickets/{ticket['id']}/status",
        headers=agent,
        json={"status": "In Progress"},
    )
    api.client.post(
        f"/api/v1/tickets/{ticket['id']}/status",
        headers=agent,
        json={"status": "Resolved", "resolution_note": "Done."},
    )
    api.client.post(
        f"/api/v1/tickets/{ticket['id']}/status", headers=employee, json={"status": "Closed"}
    )
    assert recategorise(agent, {"category_id": str(target.id), "reason": "Tidy up"}).status_code == 409


def test_ticket_list_filters_by_assignee_and_creation_window(api) -> None:
    employee = auth(api.client, api.actors["employee"])
    agent = auth(api.client, api.actors["agent"])
    first = create(api, employee, title="First")
    second = create(api, employee, title="Second")
    assign(api, agent, second, api.actors["agent"])

    def titles(query=""):
        body = api.client.get(f"/api/v1/tickets{query}", headers=employee).json()
        return [item["title"] for item in body["items"]]

    assert titles(f"?assignee_id={api.actors['agent'].id}") == ["Second"]
    assert titles(f"?assignee_id={uuid4()}") == []
    assert titles("?limit=1&offset=0") == ["Second"]  # newest first
    assert titles("?limit=1&offset=1") == ["First"]
    assert api.client.get("/api/v1/tickets?limit=0", headers=employee).status_code == 422
    assert api.client.get("/api/v1/tickets?offset=-1", headers=employee).status_code == 422

    # The contract lists created_from and created_to among the ticket filters.
    cutoff = first["created_at"]
    assert titles(f"?created_from={cutoff}") == ["Second", "First"]
    assert titles(f"?created_to={cutoff}") == ["First"]
