from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import ADMIN_SESSION_COOKIE_NAME, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from app.database import get_db
from app.models.user import ADMIN_ROLE, USER_ROLE, User
from app.schemas.auth import RegisterRequest

HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    email: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DuplicateUserError(Exception):
    pass


class InactiveUserError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return "$".join(
        [
            HASH_ALGORITHM,
            str(HASH_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_login(db: Session, login: str) -> User | None:
    normalized = login.strip()
    if "@" in normalized:
        return get_user_by_email(db, normalized)
    return get_user_by_username(db, normalized)


def get_user_auth_record(db: Session, login: str) -> AuthenticatedUser | None:
    normalized = login.strip()
    row = db.execute(
        select(
            User.id,
            User.username,
            User.email,
            User.password_hash,
            User.role,
            User.is_active,
            User.created_at,
            User.updated_at,
        ).where(or_(User.username == normalized, User.email == normalized.lower()))
    ).one_or_none()
    db.rollback()
    if row is None:
        return None

    user_id, username, email, password_hash, role, is_active, created_at, updated_at = row
    return AuthenticatedUser(
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
        created_at=created_at,
        updated_at=updated_at,
    )


def create_user(db: Session, payload: RegisterRequest, role: str = USER_ROLE) -> User:
    existing = db.scalar(
        select(User.id).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if existing is not None:
        raise DuplicateUserError

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def authenticate_user(db: Session, login: str, password: str) -> AuthenticatedUser | None:
    user = get_user_auth_record(db, login)
    if user is None or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        raise InactiveUserError
    return user


def _encode_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_json(encoded: str) -> dict[str, Any]:
    padding = "=" * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Invalid payload")
    return decoded


def create_session_token(user: User | AuthenticatedUser) -> str:
    payload = _encode_json(
        {
            "sub": str(user.id),
            "role": user.role,
            "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
        }
    )
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload}.{signature_text}"


def verify_session_token(token: str) -> int | None:
    try:
        payload, signature_text = token.split(".", 1)
        expected_signature = hmac.new(
            SECRET_KEY.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
        ).digest()
        padding = "=" * (-len(signature_text) % 4)
        actual_signature = base64.urlsafe_b64decode((signature_text + padding).encode("ascii"))
        if not hmac.compare_digest(actual_signature, expected_signature):
            return None
        data = _decode_json(payload)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return int(data.get("sub"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def session_cookie_name_for_role(role: str) -> str:
    return ADMIN_SESSION_COOKIE_NAME if role == ADMIN_ROLE else SESSION_COOKIE_NAME


def _user_from_cookie(request: Request, db: Session, cookie_name: str) -> User | None:
    token = request.cookies.get(cookie_name)
    user_id = verify_session_token(token) if token else None
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _user_from_cookie(request, db, SESSION_COOKIE_NAME) or _user_from_cookie(request, db, ADMIN_SESSION_COOKIE_NAME)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def get_current_customer(request: Request, db: Session = Depends(get_db)) -> User:
    user = _user_from_cookie(request, db, SESSION_COOKIE_NAME)
    if user is None:
        if _user_from_cookie(request, db, ADMIN_SESSION_COOKIE_NAME) is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access required")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if user.role != USER_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access required")
    return user


def get_current_admin_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = _user_from_cookie(request, db, ADMIN_SESSION_COOKIE_NAME)
    if user is None:
        if _user_from_cookie(request, db, SESSION_COOKIE_NAME) is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if user.role != ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_authenticated_user(current_user: User = Depends(get_current_customer)) -> User:
    return current_user


def require_admin(current_user: User = Depends(get_current_admin_user)) -> User:
    return current_user


get_current_admin = require_admin
get_admin_by_username = get_user_by_username


def seed_default_admin(db: Session, username: str, password: str, email: str | None = None) -> User:
    admin_email = (email or f"{username}@local.dev").lower()
    admin = db.scalar(select(User).where(or_(User.username == username, User.email == admin_email)))

    if admin is None:
        admin = User(
            username=username,
            email=admin_email,
            password_hash=hash_password(password),
            role=ADMIN_ROLE,
            is_active=True,
        )
        db.add(admin)
    else:
        admin.username = username
        admin.email = admin_email
        admin.role = ADMIN_ROLE
        admin.is_active = True
        admin.password_hash = hash_password(password)

    try:
        db.commit()
        db.refresh(admin)
        return admin
    except Exception:
        db.rollback()
        raise


def seed_default_user(db: Session, username: str, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is not None:
        changed = False
        if user.username != username:
            existing_username = get_user_by_username(db, username)
            if existing_username is None:
                user.username = username
                changed = True
        if user.role != USER_ROLE:
            user.role = USER_ROLE
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user

    existing_username = get_user_by_username(db, username)
    if existing_username is not None:
        return existing_username

    user = User(
        username=username,
        email=email.lower(),
        password_hash=hash_password(password),
        role=USER_ROLE,
        is_active=True,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise