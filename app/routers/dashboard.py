from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth_service import require_admin
from app.services.product_service import count_products
from app.services.user_service import count_customers

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])
legacy_router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])


def dashboard_payload(db: Session, current_admin: User) -> dict[str, object]:
    return {
        "admin": UserResponse.model_validate(current_admin, from_attributes=True),
        "shop_status": "Online",
        "total_revenue": "0",
        "total_products": count_products(db),
        "total_orders": 0,
        "total_customers": count_customers(db),
        "recent_orders": [],
    }


@router.get("", summary="Get admin dashboard stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return dashboard_payload(db, current_admin)


@legacy_router.get("", summary="Get admin dashboard stats", include_in_schema=False)
def legacy_dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return dashboard_payload(db, current_admin)