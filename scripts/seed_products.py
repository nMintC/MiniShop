from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func, select

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME
from app.database import SessionLocal, init_db
from app.models.product import Product
from app.services.auth_service import seed_default_admin

DEFAULT_PREFIX = "SEED"


def existing_seed_count(prefix: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count(Product.id)).where(Product.sku.like(f"{prefix}-%"))) or 0


def seed_products(count: int, prefix: str, batch_size: int) -> int:
    init_db()
    created = 0

    with SessionLocal() as db:
        seed_default_admin(db, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)

        index = 1
        while created < count:
            sku = f"{prefix}-{index:06d}"
            exists = db.scalar(select(Product.id).where(Product.sku == sku))
            if exists is None:
                product = Product(
                    name=f"Seed Product {index}",
                    description=f"Generated benchmark product {index}",
                    sku=sku,
                    price=Decimal(f"{(index % 500) + 1}.99"),
                    quantity=index % 100,
                )
                db.add(product)
                created += 1

                if created % batch_size == 0:
                    db.commit()
            index += 1

        db.commit()

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed products for local performance testing.")
    parser.add_argument("--count", type=int, default=1000, help="Number of new products to add.")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="SKU prefix for generated products.")
    parser.add_argument("--batch-size", type=int, default=250, help="Commit batch size.")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    before = existing_seed_count(args.prefix)
    created = seed_products(args.count, args.prefix, args.batch_size)
    after = existing_seed_count(args.prefix)

    print(f"Existing {args.prefix} products before: {before}")
    print(f"Created products: {created}")
    print(f"Existing {args.prefix} products after: {after}")


if __name__ == "__main__":
    main()