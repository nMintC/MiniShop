import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.cache import (
    CACHE_BYPASS,
    CACHE_ERROR,
    CACHE_HIT,
    CACHE_MISS,
    cache_get_json_with_status,
    cache_set_json,
    invalidate_product_cache,
    invalidate_product_list_cache,
    load_with_request_coalescing,
    product_cache_key,
    product_list_cache_key,
)
from app.config import REDIS_CACHE_TTL
from app.database import SessionLocal, get_db
from app.models.product import Product
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


def public_product_payload(product: Product) -> dict[str, object]:
    return ProductPublicResponse.model_validate(product, from_attributes=True).model_dump(mode="json")


def public_product_list_payload(data: dict[str, object]) -> dict[str, object]:
    products = data["items"]
    return {
        "items": [public_product_payload(product) for product in products],
        "total": data["total"],
        "page": data["page"],
        "page_size": data["page_size"],
        "total_pages": data["total_pages"],
    }


def load_product_detail_from_database(product_id: int) -> dict[str, object]:
    with SessionLocal() as db:
        product = get_product(db, product_id)
        return public_product_payload(product)


def load_product_list_from_database(q: str | None, page: int, page_size: int) -> dict[str, object]:
    with SessionLocal() as db:
        data = _list_products(db=db, q=q, page=page, page_size=page_size)
        return public_product_list_payload(data)


async def load_and_cache_product_detail(cache_key: str, product_id: int) -> dict[str, object]:
    payload = await asyncio.to_thread(load_product_detail_from_database, product_id)
    await asyncio.to_thread(cache_set_json, cache_key, payload, REDIS_CACHE_TTL)
    return payload


async def load_and_cache_product_list(cache_key: str, q: str | None, page: int, page_size: int) -> dict[str, object]:
    payload = await asyncio.to_thread(load_product_list_from_database, q, page, page_size)
    await asyncio.to_thread(cache_set_json, cache_key, payload, REDIS_CACHE_TTL)
    return payload


def validate_image_upload(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be a JPG, PNG, or WebP file")
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image content type")
    return extension


def set_cache_header(response: Response, cache_status: str) -> None:
    response.headers["X-Cache"] = cache_status


@public_router.get("", response_model=ProductPublicListResponse, summary="List public products")
async def read_products(
    response: Response,
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    cache_key = product_list_cache_key(q=q, page=page, page_size=page_size)
    cached, cache_status = cache_get_json_with_status(cache_key)
    if cached is not None:
        set_cache_header(response, CACHE_HIT)
        return cached

    if cache_status == CACHE_MISS:
        payload = await load_with_request_coalescing(
            cache_key,
            lambda: load_and_cache_product_list(cache_key, q, page, page_size),
        )
    else:
        payload = await asyncio.to_thread(load_product_list_from_database, q, page, page_size)

    set_cache_header(response, cache_status if cache_status in {CACHE_BYPASS, CACHE_ERROR} else CACHE_MISS)
    return payload


@public_router.get("/{product_id}", response_model=ProductPublicResponse, summary="Get public product detail")
async def read_product(product_id: int, response: Response):
    cache_key = product_cache_key(product_id)
    cached, cache_status = cache_get_json_with_status(cache_key)
    if cached is not None:
        set_cache_header(response, CACHE_HIT)
        return cached

    try:
        if cache_status == CACHE_MISS:
            payload = await load_with_request_coalescing(
                cache_key,
                lambda: load_and_cache_product_detail(cache_key, product_id),
            )
        else:
            payload = await asyncio.to_thread(load_product_detail_from_database, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc

    set_cache_header(response, cache_status if cache_status in {CACHE_BYPASS, CACHE_ERROR} else CACHE_MISS)
    return payload


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
        product = create_product(db, payload)
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc
    invalidate_product_list_cache()
    return product


@admin_router.put("/{product_id}", response_model=ProductAdminResponse, summary="Update product")
def edit_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        product = update_product(db, product_id, payload)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc
    except DuplicateSKUError as exc:
        raise duplicate_sku_error() from exc
    invalidate_product_cache(product_id)
    invalidate_product_list_cache()
    return product


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
    product = update_product_image(db, product_id, image_url)
    invalidate_product_cache(product_id)
    invalidate_product_list_cache()
    return product


@admin_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete product")
def remove_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        delete_product(db, product_id)
    except ProductNotFoundError as exc:
        raise product_not_found_error() from exc
    invalidate_product_cache(product_id)
    invalidate_product_list_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


legacy_admin_router.add_api_route("", add_product, methods=["POST"], response_model=ProductAdminResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", edit_product, methods=["PUT"], response_model=ProductAdminResponse, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", patch_product, methods=["PATCH"], response_model=ProductAdminResponse, include_in_schema=False)
legacy_admin_router.add_api_route("/{product_id}", remove_product, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
