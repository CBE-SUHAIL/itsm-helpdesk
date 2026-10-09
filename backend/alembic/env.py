"""Alembic environment.

The database URL is deliberately absent from alembic.ini. It is built here from
app.core.config, which reads the repository-root .env, so the migration target
is always the database compose.yaml started and the credentials live in exactly
one place. Run migrations from backend/:  alembic upgrade head
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# configparser interpolates on read, so an unescaped percent sign in a password
# would break the URL. Escape it before handing the URL to Alembic.
config.set_main_option(
    "sqlalchemy.url", get_settings().database_url.replace("%", "%%")
)

# Autogenerate diffs the database against this metadata. It stays empty until
# D01-D06 add models, which is why F05's baseline revision creates nothing.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of connecting, for reviewing a migration."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and apply migrations, the normal local path.

    connect_timeout matches app.core.db: when PostgreSQL is down, which happens
    whenever the WSL2 VM that hosts Docker has stopped, a migration must fail in
    seconds with a real error instead of sitting in TCP retries.

    A caller may pass an open connection in config.attributes["connection"] to run
    the whole chain inside it. That is the documented Alembic pattern for driving
    several commands from one script, and it is what tests/test_migrations.py uses
    to run the whole chain in a single connection.
    """
    supplied = config.attributes.get("connection", None)
    if supplied is not None:
        context.configure(
            connection=supplied,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
