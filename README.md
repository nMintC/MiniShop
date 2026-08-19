# Mini E-commerce Admin Dashboard

A compact admin dashboard for managing products in a small e-commerce system.

The project includes a FastAPI backend, SQLAlchemy 2.x database layer, SQLite development database, cookie-based admin authentication, product CRUD APIs, a protected admin UI, automated tests, and Locust performance testing.

## Features

- Admin login, logout, and current-user session check
- HTTP-only cookie authentication
- PBKDF2-SHA256 password hashing
- Protected dashboard page
- Product statistics from real database aggregate queries
- Product CRUD with SKU uniqueness validation
- Search and pagination handled by the backend
- Swagger/OpenAPI documentation
- Vietnam timezone timestamps, UTC+7
- Pytest test suite
- Locust scenario for 100 concurrent user testing

## Tech Stack

- Python
- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic
- Uvicorn
- Pytest
- Locust
- HTML, CSS, JavaScript

## Project Structure

```text
app/
  models/
    admin.py
    product.py
  routers/
    auth.py
    dashboard.py
    products.py
  schemas/
    auth.py
    product.py
  services/
    auth_service.py
    product_service.py
  static/
    css/admin.css
    js/dashboard.js
    js/login.js
  utils/
    datetime.py
  config.py
  database.py
  main.py
frontend/
  index.html
  login.html
scripts/
  seed_products.py
tests/
  conftest.py
  test_auth.py
  test_docs_pages.py
  test_performance.py
  test_products.py
locustfile.py
PERFORMANCE.md
requirements.txt
.env.example
```

## Getting Started

### 1. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Activate it on Windows CMD:

```bat
venv\Scripts\activate
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Create local environment file

```bash
copy .env.example .env
```

Default development admin:

```text
username: admin
password: admin123
```

Change `SECRET_KEY` and `ADMIN_PASSWORD` in `.env` before using this outside local development.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./app.db` | Database connection URL |
| `DATABASE_POOL_SIZE` | `40` | SQLAlchemy connection pool size |
| `DATABASE_MAX_OVERFLOW` | `80` | Extra temporary connections allowed by the pool |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait for a database connection |
| `SECRET_KEY` | `change-this-secret-key` | Signing key for session cookies |
| `SESSION_COOKIE_NAME` | `admin_session` | Auth cookie name |
| `SESSION_MAX_AGE_SECONDS` | `86400` | Session lifetime in seconds |
| `ADMIN_USERNAME` | `admin` | Default seeded admin username |
| `ADMIN_PASSWORD` | `admin123` | Default seeded admin password |

## Run The App

```bash
python -m uvicorn app.main:app --reload
```

Open these URLs:

```text
Login:     http://127.0.0.1:8000/login
Dashboard: http://127.0.0.1:8000/dashboard
Swagger:   http://127.0.0.1:8000/docs
OpenAPI:   http://127.0.0.1:8000/openapi.json
```

The root route `/` redirects to `/dashboard`. The old `/products` page is kept as a redirect to `/dashboard` because product management is now part of the main admin dashboard.

## API Overview

Authentication:

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Dashboard:

```http
GET /api/dashboard
```

Products:

```http
GET    /api/products?q=iphone&page=1&page_size=20
GET    /api/products/{product_id}
POST   /api/products
PUT    /api/products/{product_id}
PATCH  /api/products/{product_id}
DELETE /api/products/{product_id}
```

Product and dashboard APIs require a valid admin session cookie.

## Database

The default database is `app.db`, created automatically when the app starts.

On startup, the app creates the required tables and seeds the default admin account if it does not exist.

Product statistics are calculated in SQLite through SQLAlchemy aggregate queries:

```text
COUNT(products.id)
COALESCE(SUM(products.quantity), 0)
```

Product timestamps are generated and serialized in Vietnam time, UTC+7.

## Seed Product Data

Use the seed script when you need sample data for manual testing or performance testing:

```bash
python scripts/seed_products.py --count 1000
```

The script creates `SEED-*` products and skips SKUs that already exist.

## Tests

Run the full test suite:

```bash
python -m pytest
```

The tests cover:

- Database connection
- Login success and failure
- Logout
- Unauthorized API access
- Protected dashboard page
- Product CRUD
- Duplicate SKU validation
- Invalid price and quantity validation
- Product search
- Pagination
- Dashboard statistics updates
- Swagger/OpenAPI availability
- Basic CRUD latency checks on a seeded local dataset

## Performance Testing

Locust is included for local load testing.

For benchmark runs, use a seeded database and run Uvicorn without `--reload`:

```bash
python scripts/seed_products.py --count 1000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run Locust UI:

```bash
locust -f locustfile.py --host http://127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8089
```

Suggested UI settings:

```text
Users: 100
Spawn rate: 10
```

Headless run:

```bash
locust -f locustfile.py --headless -u 100 -r 10 -t 1m --host http://127.0.0.1:8000 --csv performance_locust --csv-full-history --only-summary
```

Aggressive login burst run:

```bash
locust -f locustfile.py --headless -u 100 -r 100 -t 1m --host http://127.0.0.1:8000 --csv performance_locust_r100 --csv-full-history --only-summary
```

See [PERFORMANCE.md](PERFORMANCE.md) for the latest measured results and analysis.

## Current Performance Summary

Latest local benchmark:

```text
Users: 100
Spawn rate: 100 users/second
Duration: 60 seconds
Seed data: 1000 products
Failures: 0
Aggregated p95: 290 ms
Aggregated p99: 560 ms
Average latency: 140.90 ms
Throughput: 236.11 requests/second
```

Most CRUD and read APIs stayed under 1 second at p95. The login endpoint can exceed 1 second during an aggressive 100-user login burst because PBKDF2 password verification is CPU-bound. This is documented separately from steady-state product and dashboard API performance.

## Notes For GitHub

- `.env` is ignored and should not be committed.
- SQLite runtime files such as `app.db`, `app.db-wal`, and `app.db-shm` should not be committed.
- Locust CSV output files should not be committed.
- This project uses SQLite for local development and testing. For production-level concurrency, use a server database such as PostgreSQL.
