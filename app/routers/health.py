from fastapi import APIRouter
from sqlalchemy import text

from app.cache import is_redis_enabled, redis_ping
from app.database import engine

router = APIRouter(prefix="/health", tags=["Health"])


def database_ok() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar()
        return True
    except Exception:
        return False


@router.get("", summary="Check application dependencies")
def health_check():
    database_status = "ok" if database_ok() else "down"
    if is_redis_enabled():
        redis_status = "ok" if redis_ping() else "down"
    else:
        redis_status = "disabled"
    status = "ok" if database_status == "ok" and redis_status in {"ok", "disabled"} else "degraded"
    return {"status": status, "database": database_status, "redis": redis_status}
