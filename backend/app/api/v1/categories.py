"""T05: list active categories and let admins manage them without deletion."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    CategoryOut,
    CategoryPage,
    CreateCategoryIn,
    UpdateCategoryIn,
)
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Category, User
from app.models.role import utc_now


router = APIRouter()
admin = require_roles("Admin")


@router.get("/categories", response_model=CategoryPage)
def list_categories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> CategoryPage:
    active = Category.is_active.is_(True)
    total = session.scalar(select(func.count()).select_from(Category).where(active)) or 0
    categories = session.scalars(
        select(Category).where(active)
        .order_by(Category.name, Category.id).limit(limit).offset(offset)
    ).all()
    return CategoryPage(
        items=[CategoryOut.from_category(category) for category in categories],
        total=total,
    )


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    data: CreateCategoryIn,
    _: User = Depends(admin),
    session: Session = Depends(get_db),
) -> CategoryOut:
    if session.scalar(select(Category.id).where(Category.name == data.name)) is not None:
        raise HTTPException(status_code=409, detail="Category name already used")
    category = Category(name=data.name, description=data.description, is_active=True)
    try:
        session.add(category)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name already used") from None
    return CategoryOut.from_category(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: UUID,
    data: UpdateCategoryIn,
    _: User = Depends(admin),
    session: Session = Depends(get_db),
) -> CategoryOut:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != category.name:
        existing = session.scalar(select(Category.id).where(Category.name == changes["name"]))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Category name already used")
    if any(getattr(category, key) != value for key, value in changes.items()):
        for key, value in changes.items():
            setattr(category, key, value)
        category.updated_at = utc_now()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name already used") from None
    return CategoryOut.from_category(category)
