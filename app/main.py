from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME, SESSION_COOKIE_NAME
from app.database import SessionLocal, engine, init_db
from app.routers import auth, dashboard, products
from app.services.auth_service import get_admin_by_username, seed_default_admin, verify_session_token

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_default_admin(db, ADMIN_USERNAME, ADMIN_PASSWORD)
    yield


app = FastAPI(
    title="Mini Shop API",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(products.router, prefix="/api")


def has_valid_session(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False

    username = verify_session_token(token)
    if username is None:
        return False

    with SessionLocal() as db:
        return get_admin_by_username(db, username) is not None


@app.get("/", include_in_schema=False)
def home_page(request: Request):
    if not has_valid_session(request):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", include_in_schema=False)
def dashboard_page(request: Request):
    if not has_valid_session(request):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    if has_valid_session(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/products", include_in_schema=False)
def old_products_page(request: Request):
    if not has_valid_session(request):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/database-test", tags=["Health"], summary="Test database connection")
def database_test():
    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": value}