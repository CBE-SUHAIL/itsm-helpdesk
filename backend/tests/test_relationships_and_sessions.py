"""D07: relationships load related rows, and transactions commit or roll back.

Two kinds of check live here.

The first needs no database: it compares the ORM's configured relationships with
the foreign keys in the metadata, so a foreign key added without a matching
relationship fails immediately rather than at the point some route tries to
navigate it.

The rest run against real PostgreSQL. Every one of them opens an outer
transaction, binds its sessions to that connection with
`join_transaction_mode="create_savepoint"`, and rolls the outer transaction back
at the end. That matters: these tests are about `commit()` and `rollback()`, so a
session really does commit, while the surrounding transaction still discards the
result. A test failure can never leave a row in the development database.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, configure_mappers

from app.core import db
from app.core.config import get_settings
from app.models import Base, Category, Comment, Role, Ticket, User


def _engine():
    return create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )


def _session_factory(connection):
    """A session that commits into the caller's transaction as a savepoint."""
    return lambda: Session(bind=connection, join_transaction_mode="create_savepoint")


def _seed(session: Session) -> dict[str, UUID]:
    """One role, one agent, one employee, and one category. Flushed, not committed."""
    ids = {key: uuid4() for key in ("role", "agent", "employee", "category")}
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Role(id=ids["role"], name="Support agent", created_at=now, updated_at=now),
            User(
                id=ids["agent"],
                role_id=ids["role"],
                name="Agent",
                email=f"agent-{ids['agent']}@example.com",
                password_hash="hashed-placeholder",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            User(
                id=ids["employee"],
                role_id=ids["role"],
                name="Employee",
                email=f"employee-{ids['employee']}@example.com",
                password_hash="hashed-placeholder",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            Category(
                id=ids["category"],
                name=f"Hardware {ids['category']}",
                description="Hardware",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    session.flush()
    return ids


def test_every_foreign_key_has_a_relationship_on_both_sides() -> None:
    """All models map correctly, without needing a database."""
    configure_mappers()
    mappers = {mapper.class_.__tablename__: mapper for mapper in Base.registry.mappers}
    assert set(mappers) == set(Base.metadata.tables), "every table needs a mapper"

    foreign_keys = 0
    endpoints = 0
    for table in Base.metadata.sorted_tables:
        child = mappers[table.name]
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                foreign_keys += 1
                parent = mappers[foreign_key.column.table.name]
                matches = [
                    relationship
                    for relationship in child.relationships
                    if relationship.mapper is parent
                    and column in relationship.local_columns
                ]
                assert matches, (
                    f"{table.name}.{column.name} -> {foreign_key.column.table.name} "
                    "has no relationship, so no route can navigate it"
                )
                for relationship in matches:
                    endpoints += 1
                    assert relationship.back_populates, (
                        f"{child.class_.__name__}.{relationship.key} has no "
                        "back_populates, so the reverse side cannot navigate back"
                    )
                    partners = [
                        other
                        for other in parent.relationships
                        if other.key == relationship.back_populates
                    ]
                    assert partners, (
                        f"{child.class_.__name__}.{relationship.key} names "
                        f"back_populates={relationship.back_populates!r}, which does "
                        f"not exist on {parent.class_.__name__}"
                    )
                    assert partners[0].back_populates == relationship.key

    # One relationship per foreign key on the child side, and the parent side
    # each one back_populates. Counting the whole registry catches a relationship
    # that no foreign key justifies, which nothing above would notice.
    assert endpoints == foreign_keys
    total = sum(len(mapper.relationships) for mapper in mappers.values())
    assert total == foreign_keys * 2, (
        f"{total} relationship endpoints for {foreign_keys} foreign keys"
    )


def test_related_rows_load_through_the_relationships() -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                session = Session(
                    bind=connection, join_transaction_mode="create_savepoint"
                )
                ids = _seed(session)
                ticket = Ticket(
                    id=uuid4(),
                    title="Printer is offline",
                    description="The floor printer stopped responding.",
                    category_id=ids["category"],
                    creator_id=ids["employee"],
                    assignee_id=ids["agent"],
                    status="Open",
                    priority="Medium",
                    response_due_at=now,
                    resolution_due_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(ticket)
                session.flush()
                session.add(
                    Comment(
                        id=uuid4(),
                        ticket_id=ticket.id,
                        author_id=ids["agent"],
                        body="Looking into it.",
                        created_at=now,
                    )
                )
                session.flush()

                # Drop everything loaded so far. Each assertion below then has to
                # fetch through the relationship rather than read the identity map.
                session.expunge_all()

                loaded = session.get(Ticket, ticket.id)
                assert loaded.category.id == ids["category"]
                assert loaded.creator.id == ids["employee"]
                assert loaded.assignee.id == ids["agent"]
                assert [comment.body for comment in loaded.comments] == [
                    "Looking into it."
                ]
                assert loaded.comments[0].author.id == ids["agent"]

                agent = session.get(User, ids["agent"])
                assert agent.role.name == "Support agent"
                assert [row.id for row in agent.tickets_assigned] == [ticket.id]
                assert agent.tickets_created == []
                assert [comment.ticket_id for comment in agent.comments] == [ticket.id]
                assert session.get(User, ids["employee"]).tickets_created[0].id == (
                    ticket.id
                )
                assert session.get(Category, ids["category"]).tickets[0].id == ticket.id
                session.close()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_a_commit_is_visible_to_a_later_session() -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                factory = _session_factory(connection)
                writer = factory()
                writer.add(
                    Role(
                        id=role_id,
                        name="Admin",
                        created_at=now,
                        updated_at=now,
                    )
                )
                writer.commit()
                writer.close()

                reader = factory()
                assert reader.get(Role, role_id) is not None
                reader.close()
            finally:
                # A session really committed above; the outer transaction still
                # discards it, which is what keeps this test safe to run anywhere.
                transaction.rollback()
    finally:
        engine.dispose()


def test_a_rollback_leaves_no_trace() -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                session = Session(
                    bind=connection, join_transaction_mode="create_savepoint"
                )
                session.add(
                    Role(id=role_id, name="Admin", created_at=now, updated_at=now)
                )
                session.flush()
                assert session.get(Role, role_id) is not None

                session.rollback()

                assert session.get(Role, role_id) is None
                session.close()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_get_db_rolls_back_and_closes_when_the_request_raises(monkeypatch) -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    role_id = uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                monkeypatch.setattr(db, "SessionLocal", _session_factory(connection))
                dependency = db.get_db()
                session = next(dependency)
                session.add(
                    Role(id=role_id, name="Admin", created_at=now, updated_at=now)
                )
                session.flush()
                assert session.get(Role, role_id) is not None

                # The route blows up before committing. The dependency must not
                # let the flushed row survive, or a half-applied multi-table
                # change would reach the database.
                with pytest.raises(RuntimeError):
                    dependency.throw(RuntimeError("the route failed"))

                assert session.in_transaction() is False
                assert session.get(Role, role_id) is None
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_session_scope_commits_on_success_and_rolls_back_on_error(monkeypatch) -> None:
    engine = _engine()
    now = datetime.now(timezone.utc)
    kept_id, discarded_id = uuid4(), uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                factory = _session_factory(connection)
                monkeypatch.setattr(db, "SessionLocal", factory)

                with db.session_scope() as session:
                    session.add(
                        Role(id=kept_id, name="Admin", created_at=now, updated_at=now)
                    )
                with pytest.raises(ValueError):
                    with db.session_scope() as session:
                        session.add(
                            Role(
                                id=discarded_id,
                                name="Employee",
                                created_at=now,
                                updated_at=now,
                            )
                        )
                        raise ValueError("something went wrong mid-unit-of-work")

                reader = factory()
                assert reader.get(Role, kept_id) is not None
                assert reader.get(Role, discarded_id) is None
                reader.close()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
