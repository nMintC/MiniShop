from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from app.database import get_db
from app.models.admin import Admin
from app.schemas.auth import AdminResponse, LoginRequest, LoginResponse
from app.services.auth_service import authenticate_admin, create_session_token, get_current_admin

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, summary="Admin login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    admin = authenticate_admin(db, payload.username, payload.password)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_session_token(admin)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return LoginResponse(message="Login successful", username=admin.username)


@router.post("/logout", summary="Admin logout")
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"message": "Logout successful"}


@router.get("/me", response_model=AdminResponse, summary="Get current admin")
def me(current_admin: Admin = Depends(get_current_admin)):
    return current_admin
