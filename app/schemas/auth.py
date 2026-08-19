from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    message: str
    username: str


class AdminResponse(BaseModel):
    id: int
    username: str
