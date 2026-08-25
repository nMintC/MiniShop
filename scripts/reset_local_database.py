from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text  # noqa: E402

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME, DATABASE_URL  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services.auth_service import seed_default_admin  # noqa: E402

CLOTHING_PRODUCTS = [
    ("Classic White T-Shirt", "CLOTH-001", "Soft cotton crew neck t-shirt for daily wear.", "19.00", 45),
    ("Black Oversized Hoodie", "CLOTH-002", "Warm fleece hoodie with a relaxed streetwear fit.", "49.00", 24),
    ("Slim Fit Denim Jeans", "CLOTH-003", "Dark blue stretch denim jeans with slim fit cut.", "59.00", 32),
    ("Linen Summer Shirt", "CLOTH-004", "Breathable button-up linen shirt for warm weather.", "39.00", 28),
    ("Pleated Midi Skirt", "CLOTH-005", "Lightweight midi skirt with clean pleated details.", "42.00", 18),
    ("Cotton Chino Pants", "CLOTH-006", "Tapered chino pants suitable for smart casual outfits.", "46.00", 36),
    ("Cropped Denim Jacket", "CLOTH-007", "Classic cropped denim jacket with front pockets.", "69.00", 14),
    ("Ribbed Knit Sweater", "CLOTH-008", "Soft ribbed sweater for layering in cooler weather.", "55.00", 21),
    ("Athletic Jogger Pants", "CLOTH-009", "Comfortable joggers with elastic waist and cuffs.", "35.00", 40),
    ("Basic Polo Shirt", "CLOTH-010", "Minimal polo shirt with breathable pique fabric.", "29.00", 33),
    ("Floral Wrap Dress", "CLOTH-011", "Printed wrap dress with adjustable waist tie.", "64.00", 12),
    ("Tailored Blazer", "CLOTH-012", "Structured blazer for office and formal styling.", "89.00", 10),
    ("High Waist Shorts", "CLOTH-013", "Casual high waist shorts with practical pockets.", "31.00", 27),
    ("Graphic Street Tee", "CLOTH-014", "Statement t-shirt with durable front graphic print.", "24.00", 38),
    ("Puffer Vest", "CLOTH-015", "Light padded vest for transitional weather.", "72.00", 16),
    ("White Shirt", "CLOTH-016", "Clean white button-up shirt for casual and office outfits.", "32.00", 42),
    ("Black Shirt", "CLOTH-017", "Classic black shirt with a regular comfortable fit.", "34.00", 37),
    ("Blue Oxford Shirt", "CLOTH-018", "Blue oxford shirt with a structured collar.", "38.00", 31),
    ("Striped Shirt", "CLOTH-019", "Vertical striped shirt for an easy smart casual look.", "36.00", 26),
    ("Checked Shirt", "CLOTH-020", "Soft checked flannel shirt for everyday layering.", "41.00", 22),
    ("Oversized White Shirt", "CLOTH-021", "Oversized white shirt with a relaxed modern silhouette.", "40.00", 29),
    ("Slim Fit Black Shirt", "CLOTH-022", "Slim black shirt designed for sharper styling.", "43.00", 18),
    ("Linen Beige Shirt", "CLOTH-023", "Light beige linen shirt made for warm days.", "44.00", 25),
    ("Denim Shirt", "CLOTH-024", "Medium wash denim shirt with snap buttons.", "48.00", 20),
    ("Short Sleeve Camp Shirt", "CLOTH-025", "Relaxed camp collar shirt for summer outfits.", "35.00", 34),
    ("White T-Shirt", "CLOTH-026", "Essential white cotton t-shirt with a clean fit.", "18.00", 55),
    ("Black T-Shirt", "CLOTH-027", "Essential black cotton t-shirt for daily rotation.", "18.00", 52),
    ("Navy T-Shirt", "CLOTH-028", "Navy crew neck t-shirt with soft cotton fabric.", "20.00", 44),
    ("Relaxed Graphic T-Shirt", "CLOTH-029", "Relaxed t-shirt with a bold front graphic.", "27.00", 30),
    ("Premium Cotton T-Shirt", "CLOTH-030", "Premium heavyweight cotton t-shirt with smooth finish.", "29.00", 28),
    ("Oversized T-Shirt", "CLOTH-031", "Oversized t-shirt with drop shoulders.", "26.00", 36),
    ("V-Neck T-Shirt", "CLOTH-032", "Soft v-neck t-shirt for simple layering.", "22.00", 33),
    ("Long Sleeve T-Shirt", "CLOTH-033", "Long sleeve cotton t-shirt for cooler days.", "28.00", 24),
    ("Cropped T-Shirt", "CLOTH-034", "Cropped t-shirt with a fitted shape.", "23.00", 21),
    ("Basic Tank Top", "CLOTH-035", "Lightweight tank top for warm weather styling.", "16.00", 47),
    ("White Hoodie", "CLOTH-036", "White pullover hoodie with soft fleece lining.", "52.00", 19),
    ("Zip Up Hoodie", "CLOTH-037", "Everyday zip up hoodie with front pockets.", "54.00", 23),
    ("Cropped Hoodie", "CLOTH-038", "Cropped hoodie with a relaxed sporty fit.", "46.00", 17),
    ("Cargo Pants", "CLOTH-039", "Utility cargo pants with multiple pockets.", "58.00", 27),
    ("Wide Leg Jeans", "CLOTH-040", "Wide leg denim jeans with a vintage wash.", "62.00", 20),
    ("Straight Denim Jeans", "CLOTH-041", "Straight fit denim jeans for everyday wear.", "57.00", 31),
    ("Black Denim Jeans", "CLOTH-042", "Black denim jeans with slight stretch.", "60.00", 26),
    ("Mini Skirt", "CLOTH-043", "Simple mini skirt with a clean A-line shape.", "33.00", 18),
    ("A-Line Skirt", "CLOTH-044", "A-line skirt with an easy fitted waist.", "37.00", 23),
    ("Satin Midi Skirt", "CLOTH-045", "Smooth satin midi skirt for polished outfits.", "45.00", 15),
    ("Casual Shirt Dress", "CLOTH-046", "Button-up shirt dress with a relaxed waist tie.", "66.00", 12),
    ("Black Wrap Dress", "CLOTH-047", "Black wrap dress with a flattering adjustable fit.", "68.00", 14),
    ("Knit Cardigan", "CLOTH-048", "Soft knit cardigan for layered styling.", "50.00", 22),
    ("Trench Coat", "CLOTH-049", "Light trench coat with classic lapel details.", "95.00", 9),
    ("Bomber Jacket", "CLOTH-050", "Casual bomber jacket with ribbed cuffs.", "78.00", 13),
]


def sqlite_db_files() -> list[Path]:
    if not DATABASE_URL.startswith("sqlite"):
        return []
    raw_path = DATABASE_URL.removeprefix("sqlite:///")
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    return [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]


def remove_sqlite_files() -> None:
    engine.dispose()
    for path in sqlite_db_files():
        if path.exists():
            path.unlink()


def seed_clothing_products() -> None:
    with SessionLocal() as db:
        seed_default_admin(db, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
        for name, sku, description, price, quantity in CLOTHING_PRODUCTS:
            db.add(
                Product(
                    name=name,
                    sku=sku,
                    description=description,
                    price=Decimal(price),
                    quantity=quantity,
                )
            )
        db.commit()


def main() -> None:
    remove_sqlite_files()
    init_db()
    with engine.begin() as connection:
        connection.execute(text("PRAGMA journal_mode=DELETE"))
    Base.metadata.create_all(bind=engine)
    seed_clothing_products()

    with SessionLocal() as db:
        users = db.execute(text("SELECT id, username, email, role FROM users ORDER BY id")).fetchall()
        products = db.execute(text("SELECT id, name, sku, price, quantity FROM products ORDER BY id")).fetchall()

    print("Database reset complete.")
    print(f"Users: {len(users)}")
    for row in users:
        print(dict(row._mapping))
    print(f"Products: {len(products)}")


if __name__ == "__main__":
    main()