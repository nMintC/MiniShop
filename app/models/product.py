from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime import vietnam_now

DEFAULT_PRODUCT_IMAGE_URL = "/static/images/product-placeholder.png"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False, default=DEFAULT_PRODUCT_IMAGE_URL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=vietnam_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=vietnam_now,
        onupdate=vietnam_now,
    )

    @property
    def in_stock(self) -> bool:
        return self.quantity > 0