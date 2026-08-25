from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.product import (
    ProductAdminListResponse,
    ProductAdminResponse,
    ProductCreate,
    ProductPublicListResponse,
    ProductPublicResponse,
    ProductUpdate,
)
from app.services.auth_service import require_admin
from app.services.product_service import (
    DuplicateSKUError,
    ProductNotFoundError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
    update_product_image,
)

public_router = APIRouter(prefix="/products", tags=["Products"])
admin_router = APIRouter(prefix="/admin/products", tags=["Admin Products"])
legacy_admin_router = APIRouter(prefix="/products", tags=["Admin Products"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "products"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def duplicate_sku_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")


def product_not_found_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


def _list_products(db: Session, q: str | None, page: int, page_size: int):
    return list_products(db=db, q=q, page=page, page_size=page_size)


def validate_image_upload(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be a JPG, PNG, or WebP file")
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image content type")
    return extension


@public_router.get("", response_model=ProductPublicListResponse, summary="List public products")
def read_products(
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return _list_products(db=db, q=q, page=page, page_size=page_size)


@public_router.get("/{product_id}", response_model=ProductPublicResponse, summary="Get public product detail")
def read_product(product_id: int, db: Session = Depends(get_db)):
    try:
        return get_product(db, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc


@admin_router.get("", response_model=ProductAdminListResponse, summary="List products for admin")
def admin_read_products(
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return _list_products(db=db, q=q, page=page, page_size=page_size)


@admin_router.get("/{product_id}", response_model=ProductAdminResponse, summary="Get product detail for admin")
def admin_read_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        return get_product(db, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc


@admin_router.post("", response_model=ProductAdminResponse, status_code=status.HTTP_201_CREATED, summary="Create product")
def add_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        return create_product(db, payload)
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc


@admin_router.put("/{product_id}", response_model=ProductAdminResponse, summary="Update product")
def edit_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        return update_product(db, product_id, payload)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc


@admin_router.patch("/{product_id}", response_model=ProductAdminResponse, summary="Partially update product")
def patch_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return edit_product(product_id=product_id, payload=payload, db=db, current_admin=current_admin)


@admin_router.post("/{product_id}/image", response_model=ProductAdminResponse, summary="Upload product image")
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    extension = validate_image_upload(file)
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be 5 MB or smaller")

    try:
        get_product(db, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"product_{product_id}_{uuid4().hex}{extension}"
    target = UPLOAD_DIR / filename
    target.write_bytes(data)
    image_url = f"/static/uploads/products/{filename}"
    return update_product_image(db, product_id, image_url)


@admin_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete product")
def remove_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        delete_product(db, product_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc


legacy_admin_router.add_api_route("", add_product, methods=["POST"], response_model=ProductAdminResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", edit_product, methods=["PUT"], response_model=ProductAdminResponse, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", patch_product, methods=["PATCH"], response_model=ProductAdminResponse, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", remove_product, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)