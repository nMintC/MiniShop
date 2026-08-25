from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.product import DEFAULT_PRODUCT_IMAGE_URL
from app.utils.datetime import as_vietnam_time

MIN_PRICE: Decimal = Decimal("0")
MAX_PRICE: Decimal = Decimal("999999999")
MAX_QUANTITY = 1_000_000
MAX_DESCRIPTION_LENGTH = 1000


def normalize_image_url(value: str | None) -> str:
    if value is None:
        return DEFAULT_PRODUCT_IMAGE_URL
    stripped = value.strip()
    return stripped or DEFAULT_PRODUCT_IMAGE_URL


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    sku: str = Field(min_length=1, max_length=50)
    price: Decimal = Field(ge=MIN_PRICE, le=MAX_PRICE, max_digits=12, decimal_places=2)
    quantity: int = Field(ge=0, le=MAX_QUANTITY)
    image_url: str | None = Field(default=DEFAULT_PRODUCT_IMAGE_URL, max_length=500)

    @field_validator("name", "sku")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("image_url")
    @classmethod
    def strip_image_url(cls, value: str | None) -> str:
        return normalize_image_url(value)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    price: Decimal | None = Field(default=None, ge=MIN_PRICE, le=MAX_PRICE, max_digits=12, decimal_places=2)
    quantity: int | None = Field(default=None, ge=0, le=MAX_QUANTITY)
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("name", "sku")
    @classmethod
    def strip_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("image_url")
    @classmethod
    def strip_optional_image_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_image_url(value)


class ProductPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    image_url: str
    in_stock: bool


class ProductAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    sku: str
    price: Decimal
    quantity: int
    image_url: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_vietnam_datetime(self, value: datetime) -> str:
        return as_vietnam_time(value).isoformat()


class ProductPublicListResponse(BaseModel):
    items: list[ProductPublicResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductAdminListResponse(BaseModel):
    items: list[ProductAdminResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


ProductResponse = ProductAdminResponse
ProductListResponse = ProductAdminListResponse