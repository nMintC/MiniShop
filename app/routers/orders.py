from fastapi import APIRouter, Depends

from app.models.user import User
from app.services.auth_service import require_admin

router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"])


@router.get("", summary="List orders placeholder")
def admin_orders(current_admin: User = Depends(require_admin)):
    return {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "message": "No orders have been created yet. Order management will become available when checkout is implemented.",
    }