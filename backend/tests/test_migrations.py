"""F05: the migration chain reaches the database and is reversible.

The chain carries only the baseline revision so far, and that revision creates
no tables by design, so these tests cover the mechanism rather than the schema:
Alembic can reach PostgreSQL through the same settings the app uses, upgrade
from nothing to head, report head, and return to base. When D01-D06 add tables,
the same tests keep covering the same path without changes, and
test_models_match_the_database turns into the drift guard for D07's ORM models.

Both tests run the whole chain inside one connection, using the connection
sharing that alembic/env.py supports. That keeps the suite to one connection per
test, which matters on a laptop where the database sits behind the WSL2 port
forward.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "20261008_2150_baseline"


def _alembic_config() -> Config:
    """Absolute paths, so the config works whatever directory pytest runs from."""
    return Config(str(BACKEND_DIR / "alembic.ini"))


def _engine():
    # connect_timeout matches app.core.db: a stopped database must fail in
    # seconds rather than hang, because this test runs in the normal suite.
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def test_chain_reaches_head_and_returns_to_base() -> None:
    engine = _engine()
    config = _alembic_config()
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection

            # Start from nothing: the baseline's downgrade is a no-op, so this
            # only removes the version row, which proves the reverse path runs.
            command.downgrade(config, "base")

            command.upgrade(config, "head")
            revision = connection.execute(
                text("select version_num from alembic_version")
            ).scalar()
            assert revision == BASELINE_REVISION

            # Head again, to prove the command is repeatable and not just lucky.
            command.upgrade(config, "head")
            revision = connection.execute(
                text("select version_num from alembic_version")
            ).scalar()
            assert revision == BASELINE_REVISION

            tables = connection.execute(
                text(
                    "select tablename from pg_tables "
                    "where schemaname = 'public' order by tablename"
                )
            ).scalars().all()
            assert "alembic_version" in tables
    finally:
        engine.dispose()


def test_models_match_the_database() -> None:
    """Alembic's own drift check: the models and the database agree.

    An empty metadata against an empty schema passes today. The value is the
    day it stops passing, because that means a model and its migration disagree.
    """
    engine = _engine()
    config = _alembic_config()
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
    finally:
        engine.dispose()
