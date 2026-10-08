"""Database connectivity helper.

Deliberately minimal: no ORM models and no session factory live here. The
schema and session handling belong to checklist rows F05 and D07.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

# connect_timeout keeps a stopped database from hanging the request for
# minutes: the failure surfaces in seconds instead of blocking a test run.
engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)


def check_database() -> bool:
    """Return True when a trivial query round-trips to PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
