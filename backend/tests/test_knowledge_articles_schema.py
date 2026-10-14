"""D06 constraints against real PostgreSQL, rolled back after each run."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models import Category, KnowledgeArticle, Role, User


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_articles_have_category_author_and_publication_state() -> None:
    engine = create_engine(
        get_settings().database_url, connect_args={"connect_timeout": 5}
    )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    now = datetime.now(timezone.utc)
    role_id, author_id, category_id, article_id = (uuid4() for _ in range(4))
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            config.attributes["connection"] = connection
            try:
                command.upgrade(config, "head")
                connection.execute(
                    insert(Role).values(
                        id=role_id, name="Support agent", created_at=now, updated_at=now
                    )
                )
                connection.execute(
                    insert(User).values(
                        id=author_id,
                        role_id=role_id,
                        name="Article Author",
                        email="article-author@example.com",
                        password_hash="hashed-placeholder",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                connection.execute(
                    insert(Category).values(
                        id=category_id,
                        name="Knowledge",
                        description="Help articles",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                article = dict(
                    id=article_id,
                    title="Reset your password",
                    body="Ask the helpdesk for a reset.",
                    category_id=category_id,
                    author_id=author_id,
                    is_published=False,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(insert(KnowledgeArticle).values(**article))
                default_draft_id = uuid4()
                connection.execute(insert(KnowledgeArticle).values(
                    **{key: value for key, value in article.items()
                       if key not in {"id", "is_published"}},
                    id=default_draft_id,
                ))
                assert connection.execute(
                    select(KnowledgeArticle.is_published).where(
                        KnowledgeArticle.id == default_draft_id
                    )
                ).scalar_one() is False
                row = connection.execute(
                    select(KnowledgeArticle.category_id, KnowledgeArticle.author_id,
                           KnowledgeArticle.is_published).where(KnowledgeArticle.id == article_id)
                ).one()
                assert (row.category_id, row.author_id, row.is_published) == (
                    category_id, author_id, False
                )

                connection.execute(
                    update(KnowledgeArticle)
                    .where(KnowledgeArticle.id == article_id)
                    .values(is_published=True, updated_at=now)
                )
                assert connection.execute(
                    select(KnowledgeArticle.is_published).where(KnowledgeArticle.id == article_id)
                ).scalar_one() is True

                # An inactive category does not invalidate an existing article.
                connection.execute(
                    update(Category).where(Category.id == category_id).values(is_active=False)
                )
                assert connection.execute(
                    select(KnowledgeArticle.category_id).where(KnowledgeArticle.id == article_id)
                ).scalar_one() == category_id

                invalid_articles = [
                    {**article, "id": uuid4(), "title": ""},
                    {**article, "id": uuid4(), "title": "   "},
                    {**article, "id": uuid4(), "title": None},
                    {**article, "id": uuid4(), "body": ""},
                    {**article, "id": uuid4(), "body": "   "},
                    {**article, "id": uuid4(), "body": None},
                    {**article, "id": uuid4(), "category_id": None},
                    {**article, "id": uuid4(), "category_id": uuid4()},
                    {**article, "id": uuid4(), "author_id": None},
                    {**article, "id": uuid4(), "author_id": uuid4()},
                    {**article, "id": uuid4(), "is_published": None},
                ]
                for invalid in invalid_articles:
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(insert(KnowledgeArticle).values(**invalid))

                for target in (delete(Category).where(Category.id == category_id),
                               delete(User).where(User.id == author_id)):
                    with pytest.raises(IntegrityError):
                        with connection.begin_nested():
                            connection.execute(target)

                indexes = set(connection.execute(text(
                    "select indexname from pg_indexes where tablename = 'knowledge_articles'"
                )).scalars())
                assert "ix_knowledge_articles_category_id" in indexes
                assert "ix_knowledge_articles_author_id" in indexes
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
