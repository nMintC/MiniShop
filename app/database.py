from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_MAX_OVERFLOW, DATABASE_POOL_SIZE, DATABASE_POOL_TIMEOUT, DATABASE_URL

DEFAULT_PRODUCT_IMAGE_URL = "/static/images/product-placeholder.png"
IS_SQLITE = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": DATABASE_POOL_TIMEOUT} if IS_SQLITE else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_timeout=DATABASE_POOL_TIMEOUT,
)


@event.listens_for(Engine, "connect")
def configure_sqlite(dbapi_connection, connection_record):
    if not IS_SQLITE:
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute(f"PRAGMA busy_timeout={DATABASE_POOL_TIMEOUT * 1000}")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_sqlite_schema() -> None:
    if not IS_SQLITE:
        return

    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "products" in tables:
            product_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(products)"))}
            if "image_url" not in product_columns:
                connection.execute(
                    text(
                        "ALTER TABLE products ADD COLUMN image_url VARCHAR(500) "
                        f"NOT NULL DEFAULT '{DEFAULT_PRODUCT_IMAGE_URL}'"
                    )
                )
        if "users" in tables:
            user_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(users)"))}
            if "email" in user_columns and "username" in user_columns:
                connection.execute(text("UPDATE users SET username = email WHERE username IS NULL"))


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema()