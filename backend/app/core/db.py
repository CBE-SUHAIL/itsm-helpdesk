"""Database connectivity, the session factory, and transaction handling. D07.

F05 left this module deliberately minimal. D07 adds the rest of the data access
layer the architecture picture names: models and their relationships live in
`app/models`, and the session factory, the request dependency, and the
transaction boundary live here.

Two session defaults are chosen on purpose:

`autoflush=False`
    A query never writes a partially built object as a side effect. Code flushes
    or commits when it means to, which keeps a failed request from leaving a
    half-inserted row behind.

`expire_on_commit=False`
    After a commit the object keeps its loaded values, so a route can commit and
    then serialise the object it just wrote without a refresh round trip. Nothing
    here mutates a committed object afterwards, so the usual staleness risk does
    not apply.

**Transaction policy.** `API_CONTRACT.md` requires that a ticket change updates
the ticket and appends its history, audit, and notification rows "together or
roll back together", so a request is one unit of work: the caller decides where
it ends and calls `commit()` once. This module owns the failure path and the
cleanup, never the commit:

- `get_db` is the FastAPI dependency. It rolls the transaction back if the
  request raises, and always closes the session.
- `session_scope` is the same contract for code outside a request, such as a
  script or a test, where success should commit and any exception should not.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# connect_timeout keeps a stopped database from hanging the request for
# minutes: the failure surfaces in seconds instead of blocking a test run.
engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

# One factory for the process. Sessions are short-lived and never shared across
# requests: a Session is not thread-safe, and FastAPI runs sync dependencies in a
# worker thread.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def check_database() -> bool:
    """Return True when a trivial query round-trips to PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session whose transaction is not committed.

    The route commits the unit of work. If the route raises instead, the
    transaction is rolled back here so a partially applied multi-table change
    cannot survive, and the session is closed either way.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Run a unit of work outside a request: commit on success, roll back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
