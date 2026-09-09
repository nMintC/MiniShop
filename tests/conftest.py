import os
from decimal import Decimal
from pathlib import Path

import pytest
from redis.exceptions import RedisError
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).resolve().parent / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SESSION_COOKIE_NAME"] = "shop_session"
os.environ["ADMIN_SESSION_COOKIE_NAME"] = "admin_session"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_EMAIL"] = "admin@minishop.local"
os.environ["ADMIN_PASSWORD"] = "Admin123!"
os.environ["DEV_USER_USERNAME"] = "user"
os.environ["DEV_USER_EMAIL"] = "user@minishop.local"
os.environ["DEV_USER_PASSWORD"] = "User123!"
os.environ["REDIS_ENABLED"] = "true"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import hash_password, seed_default_admin  # noqa: E402


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_admin(db, "admin", "Admin123!", "admin@minishop.local")


@pytest.fixture()
def client():
    reset_database()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_client(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert response.status_code == 200
    return client


@pytest.fixture()
def auth_client(admin_client):
    return admin_client


@pytest.fixture()
def user_client(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "customer", "email": "customer@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": "customer", "password": "password123"})
    assert login.status_code == 200
    return client


def product_payload(sku: str = "SKU-001", name: str = "Keyboard") -> dict[str, object]:
    return {
        "name": name,
        "description": "Mechanical keyboard",
        "sku": sku,
        "price": "49.99",
        "quantity": 12,
    }


def register_payload(username: str = "alice", email: str = "alice@example.com") -> dict[str, object]:
    return {"username": username, "email": email, "password": "password123"}


def seed_products(count: int) -> None:
    with SessionLocal() as db:
        products = [
            Product(
                name=f"Product {index}",
                description=f"Seed product {index}",
                sku=f"SKU-{index:05d}",
                price=Decimal("10.00"),
                quantity=index % 100,
            )
            for index in range(count)
        ]
        db.add_all(products)
        db.commit()


def create_inactive_user(username: str = "inactive", email: str = "inactive@example.com") -> None:
    with SessionLocal() as db:
        db.add(
            User(
                username=username,
                email=email,
                password_hash=hash_password("password123"),
                role="user",
                is_active=False,
            )
        )
        db.commit()
class OfflineRedis:
    def ping(self):
        raise RedisError("Redis disabled during tests")

    def get(self, key: str):
        raise RedisError("Redis disabled during tests")

    def set(self, key: str, value: str, *, ex: int):
        raise RedisError("Redis disabled during tests")

    def delete(self, *keys: str):
        return 0

    def scan_iter(self, match: str):
        return iter(())


@pytest.fixture(autouse=True)
def disable_real_redis(monkeypatch):
    import app.cache as cache

    monkeypatch.setattr(cache, "_client", OfflineRedis())

