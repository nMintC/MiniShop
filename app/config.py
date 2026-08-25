from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


load_env_file()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
DATABASE_POOL_SIZE = env_int("DATABASE_POOL_SIZE", 40)
DATABASE_MAX_OVERFLOW = env_int("DATABASE_MAX_OVERFLOW", 80)
DATABASE_POOL_TIMEOUT = env_int("DATABASE_POOL_TIMEOUT", 30)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-this-secret-key")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "shop_session")
ADMIN_SESSION_COOKIE_NAME = os.getenv("ADMIN_SESSION_COOKIE_NAME", "admin_session")
SESSION_MAX_AGE_SECONDS = env_int("SESSION_MAX_AGE_SECONDS", 86400)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@minishop.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
DEV_USER_USERNAME = os.getenv("DEV_USER_USERNAME", "user")
DEV_USER_EMAIL = os.getenv("DEV_USER_EMAIL", "user@minishop.local")
DEV_USER_PASSWORD = os.getenv("DEV_USER_PASSWORD", "User123!")