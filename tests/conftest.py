import os
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).resolve().parent / "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services.auth_service import seed_default_admin  # noqa: E402


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_admin(db, "admin", "admin123")


@pytest.fixture()
def client():
    reset_database()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return client


def product_payload(sku: str = "SKU-001", name: str = "Keyboard") -> dict[str, object]:
    return {
        "name": name,
        "description": "Mechanical keyboard",
        "sku": sku,
        "price": "49.99",
        "quantity": 12,
    }


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
