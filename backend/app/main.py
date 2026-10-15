"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, health, tickets, users
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ITSM Helpdesk API",
    version="0.1.0",
    description="Local IT service management backend.",
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
app.include_router(tickets.router, prefix="/api/v1")
