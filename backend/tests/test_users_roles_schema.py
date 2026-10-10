"""D01 database checks for the users and roles tables."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Role, User

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_users_reference_roles_and_database_rejects_invalid_rows() -> None:
    """Exercise the actual PostgreSQL constraints, then roll everything back."""
    engine = create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    role_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.upgrade(config, "head")
                connection.execute(
                    insert(Role).values(
                        id=role_id, name="Employee", created_at=now, updated_at=now
                    )
                )
                user = dict(
                    id=user_id,
                    role_id=role_id,
                    name="Demo User",
                    email="demo@example.com",
                    password_hash="hashed-placeholder",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(insert(User).values(**user))
                assert connection.execute(
                    select(User.role_id).where(User.id == user_id)
                ).scalar_one() == role_id

                invalid_users = [
                    {**user, "id": uuid4()},  # duplicate email
                    {**user, "id": uuid4(), "email": "DEMO@example.com"},
                    {**user, "id": uuid4(), "email": ""},
                    {**user, "id": uuid4(), "email": None},
                    {**user, "id": uuid4(), "name": "  ", "email": "other@example.com"},
                    {**user, "id": uuid4(), "name": None, "email": "other@example.com"},
                    {**user, "id": uuid4(), "password_hash": "", "email": "other@example.com"},
                    {**user, "id": uuid4(), "password_hash": None, "email": "other@example.com"},
                    {**user, "id": uuid4(), "role_id": None, "email": "other@example.com"},
                    {**user, "id": uuid4(), "role_id": uuid4(), "email": "other@example.com"},
                ]
                for invalid in invalid_users:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(User).values(**invalid))

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(
                            insert(Role).values(
                                id=uuid4(), name="Superuser",
                                created_at=now, updated_at=now
                            )
                        )
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(
                            insert(Role).values(
                                id=uuid4(), name="Employee",
                                created_at=now, updated_at=now
                            )
                        )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
