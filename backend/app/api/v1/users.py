"""Admin-only user management; users are deactivated, never deleted."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.schemas import CreateUserIn, RoleName, UpdateUserIn, UserOut, UserPage
from app.core.db import get_db
from app.core.passwords import hash_password
from app.core.security import require_roles
from app.models import AuditLog, Role, User
from app.models.role import utc_now


router = APIRouter(tags=["users"])
admin = require_roles("Admin")


def role_by_name(session: Session, name: str) -> Role:
    role = session.scalar(select(Role).where(Role.name == name))
    if role is None:
        raise HTTPException(status_code=400, detail="Role is not configured")
    return role


@router.get("/users", response_model=UserPage, summary="List users")
def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role: RoleName | None = None,
    is_active: bool | None = None,
    _: User = Depends(admin),
    session: Session = Depends(get_db),
) -> UserPage:
    where = []
    if role is not None:
        where.append(Role.name == role)
    if is_active is not None:
        where.append(User.is_active == is_active)
    total = session.scalar(
        select(func.count()).select_from(User).join(Role).where(*where)
    ) or 0
    users = session.scalars(
        select(User).join(Role).where(*where)
        .order_by(User.created_at.desc(), User.id).limit(limit).offset(offset)
    ).all()
    return UserPage(items=[UserOut.from_user(user) for user in users], total=total)


@router.post("/users", response_model=UserOut, status_code=201, summary="Create a user")
def create_user(
    data: CreateUserIn,
    actor: User = Depends(admin),
    session: Session = Depends(get_db),
) -> UserOut:
    if session.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise HTTPException(status_code=409, detail="Email already used")
    user = User(
        name=data.name, email=data.email, password_hash=hash_password(data.password),
        role=role_by_name(session, data.role), is_active=True,
    )
    try:
        session.add(user)
        session.flush()
        session.add(AuditLog(
            actor_id=actor.id, action="user_create", entity_type="user",
            entity_id=user.id,
            new_value={"name": user.name, "email": user.email, "role": user.role.name,
                       "is_active": True},
            created_at=utc_now(),
        ))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email already used") from None
    return UserOut.from_user(user)


@router.patch("/users/{user_id}", response_model=UserOut, summary="Edit a user")
def update_user(
    user_id: UUID,
    data: UpdateUserIn,
    actor: User = Depends(admin),
    session: Session = Depends(get_db),
) -> UserOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    old = {field: user.role.name if field == "role" else getattr(user, field)
           for field in data.model_fields_set}
    new = data.model_dump(exclude_unset=True)
    if user.is_active and user.role.name == "Admin" and (
        new.get("is_active") is False or new.get("role", "Admin") != "Admin"
    ):
        active_admins = session.scalar(
            select(func.count()).select_from(User).join(Role).where(
                Role.name == "Admin", User.is_active.is_(True)
            )
        ) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active admin")
    if "name" in new:
        user.name = new["name"]
    if "role" in new:
        user.role = role_by_name(session, new["role"])
    if "is_active" in new:
        user.is_active = new["is_active"]
    if old != new:
        user.updated_at = utc_now()
        session.add(AuditLog(
            actor_id=actor.id, action="user_update", entity_type="user",
            entity_id=user.id, old_value=old, new_value=new, created_at=utc_now(),
        ))
    session.commit()
    return UserOut.from_user(user)
