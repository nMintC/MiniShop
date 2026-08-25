from __future__ import annotations

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import ADMIN_ROLE, USER_ROLE, User
from app.schemas.user import AdminUserUpdate, PasswordChangeRequest, UserProfileUpdate
from app.services.auth_service import hash_password, verify_password


class DuplicateUserError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class LastAdminError(Exception):
    pass


class InvalidPasswordError(Exception):
    pass


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def list_users(db: Session, q: str | None, page: int, page_size: int) -> dict[str, object]:
    filters = []
    if q:
        keyword = f"%{q.strip()}%"
        filters.append(or_(User.username.ilike(keyword), User.email.ilike(keyword)))

    count_statement = select(func.count(User.id))
    list_statement = select(User).order_by(User.id.desc())
    if filters:
        count_statement = count_statement.where(*filters)
        list_statement = list_statement.where(*filters)

    total = db.scalar(count_statement) or 0
    users = db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "items": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if total else 0,
    }


def count_active_admins(db: Session) -> int:
    return db.scalar(
        select(func.count(User.id)).where(User.role == ADMIN_ROLE, User.is_active.is_(True))
    ) or 0


def update_profile(db: Session, current_user: User, payload: UserProfileUpdate) -> User:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(current_user, field, value)

    try:
        db.commit()
        db.refresh(current_user)
        return current_user
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateUserError from exc
    except Exception:
        db.rollback()
        raise


def change_password(db: Session, current_user: User, payload: PasswordChangeRequest) -> None:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise InvalidPasswordError
    current_user.password_hash = hash_password(payload.new_password)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _would_remove_active_admin(user: User, data: dict[str, object]) -> bool:
    if user.role != ADMIN_ROLE or not user.is_active:
        return False
    next_role = data.get("role", user.role)
    next_active = data.get("is_active", user.is_active)
    return next_role != ADMIN_ROLE or next_active is False


def admin_update_user(db: Session, target_user_id: int, payload: AdminUserUpdate, current_admin: User) -> User:
    target = get_user(db, target_user_id)
    data = payload.model_dump(exclude_unset=True)

    if target.id == current_admin.id and data.get("is_active") is False:
        raise LastAdminError
    if _would_remove_active_admin(target, data) and count_active_admins(db) <= 1:
        raise LastAdminError

    for field, value in data.items():
        setattr(target, field, value)

    try:
        db.commit()
        db.refresh(target)
        return target
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateUserError from exc
    except Exception:
        db.rollback()
        raise

def list_customers(db: Session, q: str | None, page: int, page_size: int) -> dict[str, object]:
    filters = [User.role == USER_ROLE]
    if q:
        keyword = f"%{q.strip()}%"
        filters.append(or_(User.username.ilike(keyword), User.email.ilike(keyword)))

    count_statement = select(func.count(User.id)).where(*filters)
    list_statement = select(User).where(*filters).order_by(User.id.desc())
    total = db.scalar(count_statement) or 0
    customers = db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "items": customers,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if total else 0,
    }


def count_customers(db: Session) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == USER_ROLE)) or 0


def get_customer(db: Session, user_id: int) -> User:
    user = get_user(db, user_id)
    if user.role != USER_ROLE:
        raise UserNotFoundError
    return user