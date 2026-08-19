from __future__ import annotations

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


class DuplicateSKUError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError
    return product


def list_products(db: Session, q: str | None, page: int, page_size: int) -> dict[str, object]:
    filters = []
    if q:
        keyword = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(keyword), Product.sku.ilike(keyword)))

    count_statement = select(func.count(Product.id))
    list_statement = select(Product).order_by(Product.id.desc())
    if filters:
        count_statement = count_statement.where(*filters)
        list_statement = list_statement.where(*filters)

    total = db.scalar(count_statement) or 0
    products = db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "items": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if total else 0,
    }


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    try:
        db.add(product)
        db.commit()
        db.refresh(product)
        return product
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateSKUError from exc
    except Exception:
        db.rollback()
        raise


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> Product:
    product = get_product(db, product_id)
    data = payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        setattr(product, field, value)

    try:
        db.commit()
        db.refresh(product)
        return product
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateSKUError from exc
    except Exception:
        db.rollback()
        raise


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    try:
        db.delete(product)
        db.commit()
    except Exception:
        db.rollback()
        raise


def count_products(db: Session) -> int:
    return db.scalar(select(func.count(Product.id))) or 0


def count_total_quantity(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(Product.quantity), 0))) or 0
