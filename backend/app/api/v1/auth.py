"""Login, refresh rotation, logout, and the current user's profile."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas import LoginIn, LoginOut, RefreshIn, TokenPair, UserOut
from app.core.db import get_db
from app.core.passwords import hash_password, verify_password
from app.core.security import (
    create_refresh_token, current_user, find_refresh_token, make_access_token,
)
from app.models import AuditLog, User
from app.models.role import utc_now


router = APIRouter()
# A constant valid hash makes an unknown address take the same expensive
# verification path as a known address, without looking up a real account.
_DUMMY_HASH = hash_password("not-an-account-password")


@router.post("/auth/login", response_model=LoginOut)
def login(data: LoginIn, session: Session = Depends(get_db)) -> LoginOut:
    email = data.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    valid = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not valid or user is None or not user.is_active:
        session.add(AuditLog(
            actor_id=None, action="login_failure", entity_type="auth",
            new_value={"attempted_email": email}, created_at=utc_now(),
        ))
        session.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = make_access_token(user)
    refresh = create_refresh_token(session, user)
    session.add(AuditLog(
        actor_id=user.id, action="login_success", entity_type="user",
        entity_id=user.id, created_at=utc_now(),
    ))
    session.commit()
    return LoginOut(
        access_token=access, refresh_token=refresh, user=UserOut.from_user(user)
    )


@router.post("/auth/refresh", response_model=TokenPair)
def refresh(data: RefreshIn, session: Session = Depends(get_db)) -> TokenPair:
    record = find_refresh_token(session, data.refresh_token, lock=True)
    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access = make_access_token(user)
    record.revoked_at = utc_now()
    replacement = create_refresh_token(session, user)
    session.commit()
    return TokenPair(access_token=access, refresh_token=replacement)


@router.post("/auth/logout", status_code=204)
def logout(
    data: RefreshIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> Response:
    record = find_refresh_token(session, data.refresh_token, lock=True)
    if record.user_id != user.id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    record.revoked_at = utc_now()
    session.commit()
    return Response(status_code=204)


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.from_user(user)
