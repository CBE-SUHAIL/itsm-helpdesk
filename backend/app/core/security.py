"""Short-lived signed access tokens and server-side refresh-token sessions."""

from datetime import timedelta
import hashlib
import secrets

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import RefreshToken, User
from app.models.role import utc_now


ACCESS_MINUTES = 30
REFRESH_DAYS = 7
ISSUER = "itsm-helpdesk"
bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    secret = get_settings().jwt_secret
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    return secret


def make_access_token(user: User) -> str:
    now = utc_now()
    return jwt.encode(
        {
            "iss": ISSUER,
            "sub": str(user.id),
            "role": user.role.name,
            "typ": "access",
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_MINUTES),
        },
        _secret(),
        algorithm="HS256",
    )


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_refresh_token(session: Session, user: User) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=token_hash(raw),
        expires_at=utc_now() + timedelta(days=REFRESH_DAYS),
    ))
    return raw


def find_refresh_token(session: Session, raw: str, *, lock: bool = False) -> RefreshToken:
    query = select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw))
    if lock:
        query = query.with_for_update()
    record = session.scalar(query)
    if record is None or record.revoked_at is not None or record.expires_at <= utc_now():
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return record


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Login required")
    try:
        claims = jwt.decode(
            credentials.credentials,
            _secret(),
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "sub", "role", "typ"]},
        )
        if claims["typ"] != "access":
            raise jwt.InvalidTokenError("Wrong token type")
        from uuid import UUID
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired login") from None
    user = session.get(User, user_id)
    if user is None or not user.is_active or user.role.name != claims["role"]:
        raise HTTPException(status_code=401, detail="Invalid or expired login")
    return user


def require_roles(*names: str):
    def check(user: User = Depends(current_user)) -> User:
        if user.role.name not in names:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return check
