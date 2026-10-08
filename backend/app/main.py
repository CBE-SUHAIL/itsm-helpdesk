"""FastAPI application entry point.

Only the health route exists at F03/F04. Request and response shapes for the
rest of the API are agreed in F06 before any other route is added; see
docs/API_CONTRACT.md for the contract those routes must satisfy.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health
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

app.include_router(health.router, prefix="/api/v1")
