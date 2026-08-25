from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.user import ADMIN_ROLE, USER_ROLE, VALID_ROLES
from app.utils.datetime import as_vietnam_time

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalize_username(value: str) -> str:
    username = value.strip()
    if not username:
        raise ValueError("username must not be empty")
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("username may contain only letters, numbers, dots, underscores, and hyphens")
    return username


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not email or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("email must be valid")
    return email


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    if len(value) > 128:
        raise ValueError("password must be at most 128 characters")
    return value


def validate_role(value: str) -> str:
    role = value.strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of: {ADMIN_ROLE}, {USER_ROLE}")
    return role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_vietnam_datetime(self, value: datetime) -> str:
        return as_vietnam_time(value).isoformat()


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserProfileUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=80)
    email: str | None = Field(default=None, min_length=3, max_length=255)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str | None) -> str | None:
        return normalize_username(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_enough_password(cls, value: str) -> str:
        return validate_password(value)


class AdminUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=80)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str | None) -> str | None:
        return normalize_username(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else None

    @field_validator("role")
    @classmethod
    def strip_role(cls, value: str | None) -> str | None:
        return validate_role(value) if value is not None else None