"""Liveness and dependency health for the API."""

from fastapi import APIRouter, Response, status

from app.core.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict[str, str]:
    """Report whether the API and its database are reachable.

    Returns 503 when PostgreSQL cannot be reached, so a broken dependency is
    visible to the caller instead of hidden behind a 200.
    """
    if not check_database():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}
