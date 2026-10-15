"""Strict request and response shapes for A01–A07."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import User


RoleName = Literal["Employee", "Support agent", "Admin"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserOut(StrictModel):
    id: UUID
    name: str
    email: str
    role: RoleName
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id, name=user.name, email=user.email,
            role=user.role.name, is_active=user.is_active,
            created_at=user.created_at, updated_at=user.updated_at,
        )


class LoginIn(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RefreshIn(StrictModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(StrictModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class LoginOut(TokenPair):
    user: UserOut


class CreateUserIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    role: RoleName

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or not all(value.split("@")) or " " in value:
            raise ValueError("Invalid email")
        return value

    @field_validator("password")
    @classmethod
    def clean_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class UpdateUserIn(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: RoleName | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("At least one non-null field is required")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class UserPage(StrictModel):
    items: list[UserOut]
    total: int
