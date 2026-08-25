from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ADMIN_SESSION_COOKIE_NAME,
    SESSION_COOKIE_NAME,
)
from app.database import SessionLocal, engine, init_db
from app.models.user import ADMIN_ROLE, USER_ROLE, User
from app.routers import auth, dashboard, orders, products, users
from app.services.auth_service import seed_default_admin, verify_session_token

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_default_admin(db, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
    yield


app = FastAPI(
    title="Mini Shop API",
    version="2.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth.router, prefix="/api")
app.include_router(users.user_router, prefix="/api")
app.include_router(users.admin_router, prefix="/api")
app.include_router(users.customer_router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(dashboard.legacy_router, prefix="/api")
app.include_router(products.public_router, prefix="/api")
app.include_router(products.admin_router, prefix="/api")
app.include_router(products.legacy_admin_router, prefix="/api")


def request_user_from_cookie(request: Request, cookie_name: str) -> User | None:
    token = request.cookies.get(cookie_name)
    user_id = verify_session_token(token) if token else None
    if user_id is None:
        return None

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        db.expunge(user)
        return user


def request_user(request: Request) -> User | None:
    return request_user_from_cookie(request, SESSION_COOKIE_NAME) or request_user_from_cookie(
        request,
        ADMIN_SESSION_COOKIE_NAME,
    )


def redirect_for_user(user: User) -> RedirectResponse:
    if user.role == ADMIN_ROLE:
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return RedirectResponse(url="/", status_code=303)


def require_page_user(request: Request) -> User | RedirectResponse:
    user = request_user_from_cookie(request, SESSION_COOKIE_NAME)
    admin = request_user_from_cookie(request, ADMIN_SESSION_COOKIE_NAME)
    if user is None:
        if admin is not None:
            if request.query_params.get("preview") == "store":
                return admin
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/login", status_code=303)
    if user.role != USER_ROLE:
        return RedirectResponse(url="/login", status_code=303)
    return user


def require_page_admin(request: Request) -> User | RedirectResponse:
    user = request_user_from_cookie(request, ADMIN_SESSION_COOKIE_NAME)
    if user is None:
        if request_user_from_cookie(request, SESSION_COOKIE_NAME) is not None:
            return RedirectResponse(url="/profile", status_code=303)
        return RedirectResponse(url="/login", status_code=303)
    if user.role != ADMIN_ROLE:
        return RedirectResponse(url="/profile", status_code=303)
    return user


@app.get("/", include_in_schema=False)
def home_page(request: Request):
    user = require_page_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/products", include_in_schema=False)
def products_page(request: Request):
    user = require_page_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "products.html")


@app.get("/products/{product_id}", include_in_schema=False)
def product_detail_page(product_id: int, request: Request):
    user = require_page_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "product-detail.html")


@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/register", include_in_schema=False)
def register_page(request: Request):
    return FileResponse(FRONTEND_DIR / "register.html")


@app.get("/profile", include_in_schema=False)
def profile_page(request: Request):
    user = require_page_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "profile.html")


@app.get("/dashboard", include_in_schema=False)
def legacy_dashboard_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@app.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "admin-dashboard.html")


@app.get("/admin/products", include_in_schema=False)
def admin_products_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "admin-products.html")


@app.get("/admin/customers", include_in_schema=False)
def admin_customers_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "admin-users.html")


@app.get("/admin/users", include_in_schema=False)
def admin_users_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return RedirectResponse(url="/admin/customers", status_code=303)


@app.get("/admin/orders", include_in_schema=False)
def admin_orders_page(request: Request):
    user = require_page_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return FileResponse(FRONTEND_DIR / "admin-orders.html")


@app.get("/database-test", tags=["Health"], summary="Test database connection")
def database_test():
    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": value}