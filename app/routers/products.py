from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.services.auth_service import get_current_admin
from app.services.product_service import (
    DuplicateSKUError,
    ProductNotFoundError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
)

router = APIRouter(prefix="/products", tags=["Products"])


def duplicate_sku_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")


def product_not_found_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


@router.get("", response_model=ProductListResponse, summary="List products")
def read_products(
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return list_products(db=db, q=q, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductResponse, summary="Get product detail")
def read_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        return get_product(db, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Create product")
def add_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        return create_product(db, payload)
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc


@router.put("/{product_id}", response_model=ProductResponse, summary="Update product")
def edit_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        return update_product(db, product_id, payload)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc


@router.patch("/{product_id}", response_model=ProductResponse, summary="Partially update product")
def patch_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return edit_product(product_id=product_id, payload=payload, db=db, current_admin=current_admin)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete product")
def remove_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        delete_product(db, product_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc
