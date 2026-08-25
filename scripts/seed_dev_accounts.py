from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.services.auth_service import seed_default_admin  # noqa: E402


def main() -> None:
    init_db()
    with SessionLocal() as db:
        admin = seed_default_admin(db, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
    print(f"Admin account: {admin.email} ({admin.role})")


if __name__ == "__main__":
    main()