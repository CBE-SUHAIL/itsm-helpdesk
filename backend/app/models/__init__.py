"""SQLAlchemy declarative base and the metadata every model shares.

F05 owns the schema decisions and the migration mechanism; tables and their
minimal models arrive with D01-D06, while D07 completes shared relationships
and session handling. This module exists for two reasons:
Alembic needs one Base to autogenerate against, and every later model must
inherit the same naming convention from its first table. Constraint names are
compared by name during autogenerate, so renaming them after tables exist costs
a migration each time.

See docs/DATA_MODEL.md for the schema itself.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Predictable, greppable constraint names. Derived from the SQLAlchemy
# documented convention, so a reviewer can read a migration and know what the
# index or foreign key on the database is called without opening the database.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for every ITSM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Import each model so Alembic sees its table in Base.metadata. Later D-rows
# add their models here before generating or checking a migration.
from app.models.role import Role  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
