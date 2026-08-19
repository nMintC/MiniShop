from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from app.database import get_db
from app.models.admin import Admin

HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000


@dataclass(frozen=True)
class AuthenticatedAdmin:
    id: int
    username: str
    password_hash: str


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


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    return db.scalar(select(Admin).where(Admin.username == username))


def get_admin_auth_record(db: Session, username: str) -> AuthenticatedAdmin | None:
    row = db.execute(
        select(Admin.id, Admin.username, Admin.password_hash).where(Admin.username == username)
    ).one_or_none()
    db.rollback()
    if row is None:
        return None
    admin_id, admin_username, password_hash = row
    return AuthenticatedAdmin(id=admin_id, username=admin_username, password_hash=password_hash)


def authenticate_admin(db: Session, username: str, password: str) -> AuthenticatedAdmin | None:
    admin = get_admin_auth_record(db, username)
    if admin is None or not verify_password(password, admin.password_hash):
        return None
    return admin


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


def create_session_token(admin: Admin | AuthenticatedAdmin) -> str:
    payload = _encode_json({"sub": admin.username, "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS})
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload}.{signature_text}"


def verify_session_token(token: str) -> str | None:
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
        username = data.get("sub")
        return username if isinstance(username, str) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    username = verify_session_token(token) if token else None
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    admin = get_admin_by_username(db, username)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return admin


def seed_default_admin(db: Session, username: str, password: str) -> Admin:
    admin = get_admin_by_username(db, username)
    if admin is not None:
        return admin

    admin = Admin(username=username, password_hash=hash_password(password))
    try:
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    except Exception:
        db.rollback()
        raise