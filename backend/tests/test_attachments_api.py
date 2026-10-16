"""T07: attachment upload, listing, download, and the limits that guard them.

Real PostgreSQL plus a real (temporary) upload directory, both isolated: the
fixture opens one outer transaction around the database and points `UPLOAD_DIR`
at pytest's `tmp_path`, so the development database keeps no rows and no test
file is ever written near the repository.
"""

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
from app.models import Attachment, Category, Role, SystemSetting, User


BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "test-password-2026"
SECRET = "test-only-secret-long-enough-for-hs256-2026"


def settings_row(session: Session) -> SystemSetting:
    row = session.scalar(
        select(SystemSetting).where(SystemSetting.is_singleton.is_(True))
    )
    assert row is not None, "the D05 seed row must exist"
    return row


@pytest.fixture()
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
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
                yield client, session, users, headers, category, tmp_path
        finally:
            app.dependency_overrides.clear()
            session.close()
            transaction.rollback()
            engine.dispose()
            get_settings.cache_clear()


def make_ticket(client, headers, users, category, *, assign_to=None) -> str:
    """Create a ticket as the employee; optionally assign it through the API."""
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


def upload(client, headers, role, ticket_id, *, name="notes.txt", data=b"hello world",
           content_type="text/plain"):
    return client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        headers=headers[role],
        files={"file": (name, data, content_type)},
    )


def test_upload_list_and_download_round_trip(api) -> None:
    client, _session, users, headers, category, tmp_path = api
    ticket_id = make_ticket(client, headers, users, category, assign_to="agent")
    body = b"the printer is jammed\n"

    created = upload(client, headers, "employee", ticket_id, data=body)
    assert created.status_code == 201, created.text
    item = created.json()
    assert set(item) == {
        "id", "ticket_id", "uploader_id", "file_name",
        "content_type", "size_bytes", "created_at",
    }
    assert item["ticket_id"] == ticket_id
    assert item["uploader_id"] == str(users["employee"].id)
    assert item["file_name"] == "notes.txt"
    assert item["content_type"] == "text/plain"
    assert item["size_bytes"] == len(body)
    # The storage path is never serialised, and never the client's name.
    assert "storage" not in created.text

    root = tmp_path / "uploads"
    stored = sorted(path.name for path in root.iterdir())
    assert len(stored) == 1
    assert len(stored[0]) == 32 and stored[0].isalnum()
    assert (root / stored[0]).read_bytes() == body
    assert stored[0] not in created.text

    listed = client.get(
        f"/api/v1/tickets/{ticket_id}/attachments", headers=headers["employee"]
    )
    assert listed.status_code == 200, listed.text
    assert listed.json() == {"items": [item], "total": 1}

    downloaded = client.get(
        f"/api/v1/tickets/{ticket_id}/attachments/{item['id']}",
        headers=headers["employee"],
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == body
    # Starlette appends a charset to text types, which is correct HTTP rather
    # than a change of the stored type; the base type is what the row holds.
    assert downloaded.headers["content-type"].startswith("text/plain")
    assert 'filename="notes.txt"' in downloaded.headers["content-disposition"]
    assert stored[0] not in downloaded.headers["content-disposition"]

    # A binary type is returned exactly as stored, with no charset added.
    png = upload(
        client, headers, "employee", ticket_id,
        name="shot.png", data=b"\x89PNG\r\n\x1a\n", content_type="image/png",
    )
    assert png.status_code == 201, png.text
    image = client.get(
        f"/api/v1/tickets/{ticket_id}/attachments/{png.json()['id']}",
        headers=headers["employee"],
    )
    assert image.status_code == 200, image.text
    assert image.headers["content-type"] == "image/png"
    assert image.content == b"\x89PNG\r\n\x1a\n"


def test_upload_permissions(api) -> None:
    client, _session, users, headers, category, _tmp = api
    ticket_id = make_ticket(client, headers, users, category, assign_to="agent")

    assert client.post(f"/api/v1/tickets/{ticket_id}/attachments").status_code == 401
    # An employee who is neither creator nor assignee cannot see the ticket at all.
    assert upload(client, headers, "other_employee", ticket_id).status_code == 404
    # An agent may read every ticket, but may attach only to their own.
    assert upload(client, headers, "other_agent", ticket_id).status_code == 403
    # The contract's "Ticket owner, assigned agent, admin" rule.
    assert upload(client, headers, "agent", ticket_id).status_code == 201
    assert upload(client, headers, "admin", ticket_id).status_code == 201
    assert upload(client, headers, "employee", ticket_id).status_code == 201


def test_upload_rejects_bad_type_size_and_name(api) -> None:
    client, session, users, headers, category, tmp_path = api
    ticket_id = make_ticket(client, headers, users, category)

    disallowed = upload(
        client, headers, "employee", ticket_id,
        name="payload.zip", data=b"PK\x03\x04", content_type="application/zip",
    )
    assert disallowed.status_code == 400, disallowed.text

    blank = upload(client, headers, "employee", ticket_id, name="   ")
    assert blank.status_code == 400, blank.text

    # A missing part never reaches the route; the shared 422 shape answers.
    assert client.post(
        f"/api/v1/tickets/{ticket_id}/attachments", headers=headers["employee"]
    ).status_code == 422

    # Shrink the limit rather than uploading ten megabytes to prove the check.
    settings_row(session).max_attachment_bytes = 1024
    session.commit()
    too_big = upload(client, headers, "employee", ticket_id, data=b"x" * 1025)
    assert too_big.status_code == 400, too_big.text
    exactly_at_limit = upload(client, headers, "employee", ticket_id, data=b"x" * 1024)
    assert exactly_at_limit.status_code == 201, exactly_at_limit.text

    # Nothing was written for a rejected upload, and a rejected name is not a path.
    root = tmp_path / "uploads"
    assert len(list(root.iterdir())) == 1
    assert not (tmp_path / "payload.zip").exists()


def test_limits_and_types_come_from_settings(api) -> None:
    client, session, users, headers, category, _tmp = api
    ticket_id = make_ticket(client, headers, users, category)

    assert upload(
        client, headers, "employee", ticket_id,
        name="archive.zip", data=b"PK\x03\x04", content_type="application/zip",
    ).status_code == 400

    row = settings_row(session)
    row.allowed_attachment_types = [*row.allowed_attachment_types, "application/zip"]
    session.commit()
    allowed = upload(
        client, headers, "employee", ticket_id,
        name="archive.zip", data=b"PK\x03\x04", content_type="application/zip",
    )
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["content_type"] == "application/zip"


def test_content_type_parameters_are_accepted(api) -> None:
    """A multipart part may carry parameters, as real browsers send for text."""
    client, _session, users, headers, category, _tmp = api
    ticket_id = make_ticket(client, headers, users, category)
    response = upload(
        client, headers, "employee", ticket_id,
        data=b"plain", content_type="text/plain; charset=utf-8",
    )
    assert response.status_code == 201, response.text
    assert response.json()["content_type"] == "text/plain"


def test_uploaded_file_name_is_never_a_path(api) -> None:
    client, _session, users, headers, category, tmp_path = api
    ticket_id = make_ticket(client, headers, users, category)
    response = upload(
        client, headers, "employee", ticket_id,
        name="C:\\Windows\\..\\..\\etc\\passwd.txt", data=b"x",
    )
    assert response.status_code == 201, response.text
    assert response.json()["file_name"] == "passwd.txt"
    # Only the generated file exists, and nothing escaped the upload root.
    assert [path.name for path in (tmp_path / "uploads").iterdir()] != []
    assert not (tmp_path / "etc").exists()
    assert not (tmp_path / "passwd.txt").exists()


def test_long_file_name_is_truncated_not_rejected(api) -> None:
    client, _session, users, headers, category, _tmp = api
    ticket_id = make_ticket(client, headers, users, category)
    response = upload(
        client, headers, "employee", ticket_id, name=f"{'a' * 400}.txt", data=b"x"
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["file_name"]) == 255


def test_download_isolation_and_missing_file(api) -> None:
    client, session, users, headers, category, _tmp = api
    first = make_ticket(client, headers, users, category, assign_to="agent")
    second = make_ticket(client, headers, users, category, assign_to="agent")
    attachment_id = upload(client, headers, "employee", first).json()["id"]

    # An attachment id belongs to its ticket, so another ticket's id is a 404.
    assert client.get(
        f"/api/v1/tickets/{second}/attachments/{attachment_id}",
        headers=headers["employee"],
    ).status_code == 404
    # Another employee cannot read the ticket, so the download hides behind 404.
    assert client.get(
        f"/api/v1/tickets/{first}/attachments/{attachment_id}",
        headers=headers["other_employee"],
    ).status_code == 404
    assert client.get(
        f"/api/v1/tickets/{first}/attachments/{uuid4()}", headers=headers["employee"]
    ).status_code == 404
    assert client.get(
        f"/api/v1/tickets/{first}/attachments/not-a-uuid", headers=headers["employee"]
    ).status_code == 422
    # Any agent may read, matching the ticket visibility rule.
    assert client.get(
        f"/api/v1/tickets/{first}/attachments/{attachment_id}",
        headers=headers["other_agent"],
    ).status_code == 200

    # A row whose bytes are gone answers 404 rather than a server error.
    row = session.get(Attachment, UUID(attachment_id))
    stored = get_settings().upload_root / row.storage_name
    stored.unlink()
    assert client.get(
        f"/api/v1/tickets/{first}/attachments/{attachment_id}",
        headers=headers["employee"],
    ).status_code == 404


def test_list_is_paginated_and_validated(api) -> None:
    client, _session, users, headers, category, _tmp = api
    ticket_id = make_ticket(client, headers, users, category)
    ids = []
    for index in range(3):
        ids.append(
            upload(client, headers, "employee", ticket_id, data=f"v{index}".encode()).json()["id"]
        )

    first_page = client.get(
        f"/api/v1/tickets/{ticket_id}/attachments?limit=2&offset=0",
        headers=headers["employee"],
    ).json()
    assert first_page["total"] == 3 and len(first_page["items"]) == 2
    rest = client.get(
        f"/api/v1/tickets/{ticket_id}/attachments?limit=2&offset=2",
        headers=headers["employee"],
    ).json()
    assert [item["id"] for item in first_page["items"] + rest["items"]] == list(
        reversed(ids)
    )

    for query in ("limit=0", "limit=101", "offset=-1", "limit=oops"):
        response = client.get(
            f"/api/v1/tickets/{ticket_id}/attachments?{query}",
            headers=headers["employee"],
        )
        assert response.status_code == 422, query
    assert client.get(
        f"/api/v1/tickets/{uuid4()}/attachments", headers=headers["employee"]
    ).status_code == 404
    assert client.get(
        "/api/v1/tickets/not-a-uuid/attachments", headers=headers["employee"]
    ).status_code == 422


def test_ticket_attachment_count_is_scoped_to_the_ticket(api) -> None:
    """A second ticket's list never shows the first ticket's attachments."""
    client, _session, users, headers, category, _tmp = api
    first = make_ticket(client, headers, users, category)
    second = make_ticket(client, headers, users, category)
    upload(client, headers, "employee", first)
    assert client.get(
        f"/api/v1/tickets/{second}/attachments", headers=headers["employee"]
    ).json() == {"items": [], "total": 0}
