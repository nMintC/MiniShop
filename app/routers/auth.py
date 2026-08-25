from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.config import ADMIN_SESSION_COOKIE_NAME, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from app.database import get_db
from app.models.user import ADMIN_ROLE, User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from app.schemas.user import UserResponse
from app.services.auth_service import (
    DuplicateUserError,
    InactiveUserError,
    authenticate_user,
    create_session_token,
    create_user,
    get_current_admin_user,
    get_current_user,
    session_cookie_name_for_role,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def set_session_cookie(response: Response, token: str, role: str) -> None:
    response.set_cookie(
        key=session_cookie_name_for_role(role),
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, cookie_name: str) -> None:
    response.delete_cookie(key=cookie_name)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, summary="Register user")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = create_user(db, payload)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists") from exc
    return RegisterResponse(message="Registration successful", user=user)


@router.post("/login", response_model=LoginResponse, summary="Login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, payload.username, payload.password)
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled") from exc
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_session_token(user)
    set_session_cookie(response, token, user.role)
    return LoginResponse(message="Login successful", user=user)


@router.post("/logout", summary="Logout")
def logout(
    response: Response,
    scope: str = Query(default="all", pattern="^(all|customer|admin)$"),
):
    if scope in {"all", "customer"}:
        clear_session_cookie(response, SESSION_COOKIE_NAME)
    if scope in {"all", "admin"}:
        clear_session_cookie(response, ADMIN_SESSION_COOKIE_NAME)
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserResponse, summary="Get current storefront user")
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/admin/me", response_model=UserResponse, summary="Get current admin user")
def admin_me(current_admin: User = Depends(get_current_admin_user)):
    return current_admin