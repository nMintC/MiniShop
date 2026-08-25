from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import AdminUserUpdate, PasswordChangeRequest, UserListResponse, UserProfileUpdate, UserResponse
from app.services.auth_service import require_admin, require_authenticated_user
from app.services.user_service import (
    DuplicateUserError,
    InvalidPasswordError,
    LastAdminError,
    UserNotFoundError,
    admin_update_user,
    change_password,
    get_customer,
    get_user,
    list_customers,
    list_users,
    update_profile,
)

user_router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(prefix="/admin/users", tags=["Admin Users"])
customer_router = APIRouter(prefix="/admin/customers", tags=["Admin Customers"])


def duplicate_user_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")


def user_not_found_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def customer_not_found_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")


def last_admin_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable or demote the last active admin")


@user_router.get("/me", response_model=UserResponse, summary="Get my profile")
def read_my_profile(current_user: User = Depends(require_authenticated_user)):
    return current_user


@user_router.patch("/me", response_model=UserResponse, summary="Update my profile")
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    try:
        return update_profile(db, current_user, payload)
    except DuplicateUserError as exc:
        raise duplicate_user_error() from exc


@user_router.patch("/me/password", summary="Change my password")
def update_my_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    try:
        change_password(db, current_user, payload)
    except InvalidPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect") from exc
    return {"message": "Password updated"}


@admin_router.get("", response_model=UserListResponse, summary="List users")
def admin_list_users(
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_users(db=db, q=q, page=page, page_size=page_size)


@admin_router.get("/{user_id}", response_model=UserResponse, summary="Get user detail")
def admin_get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        return get_user(db, user_id)
    except UserNotFoundError as exc:
        raise user_not_found_error() from exc


@admin_router.patch("/{user_id}", response_model=UserResponse, summary="Update user")
def admin_patch_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        return admin_update_user(db, user_id, payload, current_admin)
    except UserNotFoundError as exc:
        raise user_not_found_error() from exc
    except DuplicateUserError as exc:
        raise duplicate_user_error() from exc
    except LastAdminError as exc:
        raise last_admin_error() from exc


@customer_router.get("", response_model=UserListResponse, summary="List customers")
def admin_list_customers(
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_customers(db=db, q=q, page=page, page_size=page_size)


@customer_router.get("/{customer_id}", summary="Get customer detail")
def admin_get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        customer = get_customer(db, customer_id)
    except UserNotFoundError as exc:
        raise customer_not_found_error() from exc
    return {"customer": UserResponse.model_validate(customer, from_attributes=True), "orders_count": 0, "orders": []}


@customer_router.patch("/{customer_id}", response_model=UserResponse, summary="Update customer status")
def admin_patch_customer(
    customer_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        get_customer(db, customer_id)
        return admin_update_user(db, customer_id, payload, current_admin)
    except UserNotFoundError as exc:
        raise customer_not_found_error() from exc
    except DuplicateUserError as exc:
        raise duplicate_user_error() from exc
    except LastAdminError as exc:
        raise last_admin_error() from exc