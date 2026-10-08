"""F03/F04 smoke test: the API boots and reaches the local PostgreSQL.

This is an integration test, not a unit test: it needs the database
running (`docker compose up -d`). That is deliberate - mocking the
database would prove the app starts, not that F04's database is reachable.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_api_and_database_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "database": "ok"}
