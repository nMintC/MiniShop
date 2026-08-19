from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.schemas.auth import AdminResponse
from app.services.auth_service import get_current_admin
from app.services.product_service import count_products, count_total_quantity

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", summary="Get admin dashboard stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return {
        "admin": AdminResponse.model_validate(current_admin, from_attributes=True),
        "total_products": count_products(db),
        "total_quantity": count_total_quantity(db),
    }
