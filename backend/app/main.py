"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    attachments,
    audit_logs,
    auth,
    categories,
    health,
    notifications,
    tickets,
    users,
)
from app.core.config import get_settings

settings = get_settings()

# G03: what /docs shows. Each tag groups the routes the contract lists together,
# so a reviewer can find a route by the thing it acts on.
TAGS = [
    {"name": "health", "description": "Liveness and database reachability."},
    {"name": "auth", "description": "Sign in, refresh, sign out, and read the current user."},
    {"name": "users", "description": "Admin user administration (A06)."},
    {
        "name": "categories",
        "description": "Active category list for everyone; management for admins (T05).",
    },
    {
        "name": "tickets",
        "description": (
            "Create and read tickets, and move them through the lifecycle: "
            "assignment (T03), status (T02), priority (T04), comments and "
            "history (T06)."
        ),
    },
    {
        "name": "attachments",
        "description": "Attach PDF, PNG, JPEG, or TXT files to a ticket and download them (T07).",
    },
    {
        "name": "notifications",
        "description": "Read, mark read, and dismiss your own notifications (S01).",
    },
    {"name": "audit", "description": "Admin-only read of the append-only audit log (G01)."},
]

DESCRIPTION = """
Local IT service management backend. The shapes below are the agreed contract in
`docs/API_CONTRACT.md`; a route that is not here has not been implemented yet.

**Authentication.** Every route needs a bearer access token except
`POST /auth/login`, `POST /auth/refresh`, and `GET /health`. Click *Authorize*,
paste the `access_token` from `POST /auth/login`, and the padlock on each route
applies it. Access tokens last 30 minutes; a role change invalidates them
immediately, because the API compares the token's role with the stored one.

**Permissions are enforced here, never by the React app.** An employee sees only
their own tickets and notifications. An agent sees every ticket but may act only
on the one they are assigned. Admin-only routes answer `403` for the other roles.
A record that exists but is not yours answers `404`, so IDs cannot be probed.

**Errors.** Every failure returns `{"detail": "..."}`: `400` the request is well
formed but the domain refuses it, `401` missing or expired login, `403`
forbidden, `404` missing or inaccessible, `409` conflicting state, `422` the
request itself does not validate, `503` the server's own configuration is
missing (for example the seeded SLA or attachment settings).

**Lists.** Paginated routes take `limit` (default 20, maximum 100) and `offset`
(default 0) and answer `{"items": [...], "total": n}`.
"""

app = FastAPI(
    title="ITSM Helpdesk API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
)

# The Vite dev server proxies /api, so this is a fallback for a built
# frontend served from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 payload can echo an invalid password or token in
    # an `input` field. Contract errors are one safe string instead.
    return JSONResponse(status_code=422, content={"detail": "Invalid request fields"})

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(attachments.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
