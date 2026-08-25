from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserResponse, normalize_email, normalize_username, validate_password


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def strip_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def strong_enough_password(cls, value: str) -> str:
        return validate_password(value)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def strip_login(cls, value: str) -> str:
        return value.strip()


class LoginResponse(BaseModel):
    message: str
    user: UserResponse


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


AdminResponse = UserResponse