from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime import vietnam_now

USER_ROLE = "user"
ADMIN_ROLE = "admin"
VALID_ROLES = {USER_ROLE, ADMIN_ROLE}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=USER_ROLE, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=vietnam_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=vietnam_now,
        onupdate=vietnam_now,
    )