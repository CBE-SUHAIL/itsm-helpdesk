"""The migration chain reaches PostgreSQL, reverses, and matches the models.

Both tests run inside one connection, using the connection sharing supported by
alembic/env.py. Their outer transactions are always rolled back: a test
downgrade must never erase development data.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


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
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.downgrade(config, "base")
                command.upgrade(config, "head")
                revision = connection.execute(
                    text("select version_num from alembic_version")
                ).scalar()
                assert revision == expected_head

                # Upgrading an already-current database is repeatable.
                command.upgrade(config, "head")
                revision = connection.execute(
                    text("select version_num from alembic_version")
                ).scalar()
                assert revision == expected_head

                tables = set(
                    connection.execute(
                        text(
                            "select tablename from pg_tables "
                            "where schemaname = 'public'"
                        )
                    ).scalars()
                )
                assert {"alembic_version", "roles", "users"} <= tables
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_models_match_the_database() -> None:
    """Alembic's drift check catches a model without a matching migration."""
    engine = _engine()
    config = _alembic_config()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.upgrade(config, "head")
                command.check(config)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
