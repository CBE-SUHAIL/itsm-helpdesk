"""Knowledge-base articles: published reading and role-scoped drafts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    ArticleOut, ArticlePage, CreateArticleIn, PublishArticleIn, UpdateArticleIn,
)
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Category, KnowledgeArticle, User
from app.models.role import utc_now


router = APIRouter(tags=["articles"])


def _active_category(session: Session, category_id: UUID) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Category is inactive")
    return category


def _visible(article: KnowledgeArticle | None, user: User) -> KnowledgeArticle:
    if article is None or not (
        article.is_published or user.role.name == "Admin" or
        (user.role.name == "Support agent" and article.author_id == user.id)
    ):
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/articles", response_model=ArticlePage, summary="List knowledge articles")
def list_articles(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = None,
    category_id: UUID | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> ArticlePage:
    where = []
    if user.role.name == "Employee":
        where.append(KnowledgeArticle.is_published.is_(True))
    elif user.role.name == "Support agent":
        where.append(or_(
            KnowledgeArticle.is_published.is_(True),
            KnowledgeArticle.author_id == user.id,
        ))
    if q:
        term = f"%{q.strip()}%"
        where.append(or_(KnowledgeArticle.title.ilike(term), KnowledgeArticle.body.ilike(term)))
    if category_id is not None:
        where.append(KnowledgeArticle.category_id == category_id)
    total = session.scalar(
        select(func.count()).select_from(KnowledgeArticle).where(*where)
    ) or 0
    articles = session.scalars(
        select(KnowledgeArticle).where(*where)
        .order_by(KnowledgeArticle.updated_at.desc(), KnowledgeArticle.id)
        .limit(limit).offset(offset)
    ).all()
    return ArticlePage(items=[ArticleOut.from_article(a) for a in articles], total=total)


@router.get("/articles/{article_id}", response_model=ArticleOut, summary="Read an article")
def get_article(
    article_id: UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> ArticleOut:
    return ArticleOut.from_article(_visible(session.get(KnowledgeArticle, article_id), user))


@router.post("/articles", response_model=ArticleOut, status_code=201, summary="Create a draft article")
def create_article(
    data: CreateArticleIn,
    user: User = Depends(require_roles("Support agent", "Admin")),
    session: Session = Depends(get_db),
) -> ArticleOut:
    _active_category(session, data.category_id)
    article = KnowledgeArticle(
        title=data.title, body=data.body, category_id=data.category_id,
        author_id=user.id, is_published=False,
    )
    session.add(article)
    session.commit()
    return ArticleOut.from_article(article)


@router.patch("/articles/{article_id}", response_model=ArticleOut, summary="Edit an article")
def update_article(
    article_id: UUID,
    data: UpdateArticleIn,
    user: User = Depends(require_roles("Support agent", "Admin")),
    session: Session = Depends(get_db),
) -> ArticleOut:
    article = session.get(KnowledgeArticle, article_id)
    if article is None or (user.role.name != "Admin" and (
        article.author_id != user.id or article.is_published
    )):
        raise HTTPException(status_code=404, detail="Article not found")
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes and changes["category_id"] != article.category_id:
        _active_category(session, changes["category_id"])
    if any(getattr(article, key) != value for key, value in changes.items()):
        for key, value in changes.items():
            setattr(article, key, value)
        article.updated_at = utc_now()
    session.commit()
    return ArticleOut.from_article(article)


@router.post("/articles/{article_id}/publish", response_model=ArticleOut, summary="Publish or unpublish an article")
def publish_article(
    article_id: UUID,
    data: PublishArticleIn,
    _: User = Depends(require_roles("Admin")),
    session: Session = Depends(get_db),
) -> ArticleOut:
    article = session.get(KnowledgeArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.is_published != data.published:
        article.is_published = data.published
        article.updated_at = utc_now()
    session.commit()
    return ArticleOut.from_article(article)
