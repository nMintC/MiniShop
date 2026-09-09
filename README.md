# Mini Shop

Mini Shop is a FastAPI e-commerce practice project with a customer storefront and a protected admin panel. The app uses SQLite for local development, SQLAlchemy for persistence, Pydantic for validation, and vanilla HTML/CSS/JavaScript for the frontend.

## Tech Stack

- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic v2
- Vanilla HTML/CSS/JavaScript
- Pytest
- Locust
- Redis optional cache

## Roles

Accounts live in the `users` table:

```text
role=user  -> customer
role=admin -> administrator
```

Backend authorization is enforced with role checks. The frontend only controls navigation and UX.

> Note: older local databases may contain an `admins` table from a previous version. Current login/auth uses `users` with `role=admin`. The reset script below recreates a clean database without the legacy `admins` table.

## Development Accounts

Seeded automatically on startup:

```text
Admin email:    admin@minishop.local
Admin username: admin
Admin password: Admin123!

User email:     user@minishop.local
User username:  user
User password:  User123!
```

You can override these in `.env`.

## Routes

Customer pages:

```text
/              Customer home, requires customer login
/products      Product catalog, requires customer login
/products/{id} Product detail, requires customer login
/profile       Customer profile
/login         Login
/register      Register
```

Admin pages:

```text
/admin/dashboard
/admin/orders
/admin/products
/admin/customers
```

`/admin/users` is kept as a legacy redirect to `/admin/customers`.

## Admin Dashboard

The dashboard shows:

- Welcome back panel
- Shop status
- Total Revenue
- Total Products
- Total Orders
- Total Customers
- Recent Orders placeholder

Orders and revenue are placeholders until checkout/order creation is implemented.

## Product Management

Admins can create, edit, search, paginate, delete, and upload product images.

Product validation:

```text
price    >= 0 and <= 999,999,999
quantity >= 0 and <= 1,000,000
```

Product image upload:

```http
POST /api/admin/products/{product_id}/image
```

Allowed image types:

```text
.jpg, .jpeg, .png, .webp
max size: 5 MB
```

Uploaded files are stored under `/static/uploads/products/`. Runtime uploads are ignored by Git.

## Redis Cache

Redis is used as an optional cache layer for public product reads and as a health dependency check. It is not used for authentication or sessions in this phase.

Purpose:

- cache public product detail responses
- cache public product list/search/pagination responses
- expose Redis status in `/api/health`
- fall back to SQLite when Redis is unavailable
- allow A/B benchmarks between Redis enabled and direct database reads

Run Redis locally with Docker:

```powershell
docker run --name mini-shop-redis -p 6379:6379 -d redis:7
```

Verify Redis:

```powershell
docker exec -it mini-shop-redis redis-cli PING
```

Expected:

```text
PONG
```

Environment variables:

```text
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
REDIS_CACHE_TTL=120
```

`REDIS_ENABLED=true` enables the cache layer. Public product APIs check Redis first, return cached data on hit, and fall back to SQLite on miss or Redis failure.

`REDIS_ENABLED=false` bypasses Redis completely. Product reads query SQLite directly, do not call Redis, and do not log Redis connection errors for those requests.

Cache keys:

```text
product:{id}
products:list:page={page}:size={page_size}:q={query}
```

Cache invalidation:

- create product: invalidates product list cache
- update product: invalidates `product:{id}` and product list cache
- delete product: invalidates `product:{id}` and product list cache
- upload product image: invalidates `product:{id}` and product list cache

## Cache Stampede Protection

Public product cache misses use simple request coalescing, also called SingleFlight, for this one FastAPI process.

Problem solved:

```text
Cache expires
many concurrent requests ask for the same key
without protection, every request queries SQLite
```

Implementation:

```text
app/cache.py -> _in_flight: dict[str, asyncio.Task]
```

Flow on Redis MISS:

```text
1. Check _in_flight for the cache key.
2. If a task already exists, await that task.
3. If no task exists, create one asyncio.Task.
4. The task loads from SQLite, writes Redis, then returns the payload.
5. Waiting requests receive the same payload or the same error.
6. The completed or failed task is removed from _in_flight.
```

Different cache keys still load independently. This is intentionally process-local and does not coordinate across multiple Uvicorn workers, multiple servers, or multiple containers. Distributed Redis locks are intentionally not implemented in this lab.
Public product responses include an `X-Cache` response header:

```text
HIT     response came from Redis
MISS    Redis was enabled, no cached value existed, SQLite was queried
BYPASS  Redis was disabled with REDIS_ENABLED=false
ERROR   Redis was enabled but unavailable or returned an error, SQLite was queried
```

Health endpoint behavior:

```http
GET /api/health
```

Possible Redis values:

```text
redis=ok
redis=down
redis=disabled
```

Redis is optional. If Redis is down while enabled, public product APIs continue reading from SQLite and `/api/health` reports `status=degraded` with `redis=down`.

## Redis Performance Benchmark

This benchmark compares public product reads with Redis disabled versus Redis enabled. It exists to show the difference between repeated database reads and warm Redis cache reads under concurrent traffic.

Because SQLite, Redis, FastAPI, and Locust are all running locally, the results are educational local benchmark results, not production capacity numbers.

The benchmark file is:

```text
locust_redis.py
```

Target endpoint:

```http
GET /api/products/{BENCHMARK_PRODUCT_ID}
```

Default product ID:

```text
BENCHMARK_PRODUCT_ID=3
```

You can override it when the product does not exist in your local database.

Run FastAPI without reload for benchmark measurements:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use `--reload` only for development. Reload mode adds development overhead and can distort benchmark results.

Mode A, Redis OFF:

```powershell
$env:REDIS_ENABLED='false'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then run Locust in another terminal:

```powershell
locust -f locust_redis.py --host http://127.0.0.1:8000
```

Expected API check:

```text
GET /api/products/3
X-Cache: BYPASS
```

Mode B, Redis ON:

```powershell
$env:REDIS_ENABLED='true'
$env:REDIS_CACHE_TTL='300'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Warm the cache before starting the benchmark:

```text
1. DEL product:3
2. GET /api/products/3 -> X-Cache: MISS
3. GET /api/products/3 -> X-Cache: HIT
```

Then run Locust with the same settings used in Redis OFF mode:

```powershell
locust -f locust_redis.py --host http://127.0.0.1:8000
```

The two benchmark modes should keep these conditions identical:

- same machine
- same product ID
- same API endpoint
- same number of users
- same spawn rate
- same run duration
- same FastAPI worker count
- same Locust file and configuration

Only change:

```text
REDIS_ENABLED=false
REDIS_ENABLED=true
```

Recommended load stages:

```text
10 users, spawn rate 2
50 users, spawn rate 5
100 users, spawn rate 10
250 users, spawn rate 20, optional
500 users, spawn rate 25, optional
```

Recommended duration:

```text
30-60 seconds per run
```

For warm-cache benchmarks, set `REDIS_CACHE_TTL` longer than the run duration, for example `REDIS_CACHE_TTL=300`. The normal default remains `120` seconds.

Metrics table template:

| Users | Redis | Requests | Failures | Avg ms | Median ms | p95 ms | p99 ms | RPS |
|------:|-------|---------:|---------:|-------:|----------:|-------:|-------:|----:|
| 10 | OFF | | | | | | | |
| 10 | ON | | | | | | | |
| 50 | OFF | | | | | | | |
| 50 | ON | | | | | | | |
| 100 | OFF | | | | | | | |
| 100 | ON | | | | | | | |

Cache stampede manual scenario:

```powershell
# Terminal 1: run Redis ON with a TTL longer than the test
$env:REDIS_ENABLED='true'
$env:REDIS_CACHE_TTL='300'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: clear one hot product key before starting Locust
docker exec -it mini-shop-redis redis-cli DEL product:3

# Terminal 3: send many users to the same product detail endpoint
$env:BENCHMARK_PRODUCT_ID='3'
locust -f locust_redis.py --host http://127.0.0.1:8000
```

Start Locust with a burst such as `100 users` and `spawn rate 100` to make many requests arrive while the key is cold. With request coalescing, the first cold-key request creates one in-flight task and the rest await it instead of duplicating the same DB load.
Manual Redis CLI checks:

```powershell
docker exec -it mini-shop-redis redis-cli
GET product:3
TTL product:3
SCAN 0 MATCH product:*
DEL product:3
```

Redis failure test, separate from the A/B benchmark:

```powershell
$env:REDIS_ENABLED='true'
docker stop mini-shop-redis
```

Expected:

```text
GET /api/products/3 -> 200 from SQLite fallback, X-Cache: ERROR
GET /api/health -> status=degraded, redis=down
```

Restart Redis afterward:

```powershell
docker start mini-shop-redis
```

Targeted Redis tests:

```powershell
python -m pytest tests/test_redis_cache.py -v
```

Full regression test:

```powershell
python -m pytest -v
```
## API Overview

Auth:

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/auth/admin/me
```

Customer APIs:

```http
GET   /api/products
GET   /api/products/{id}
GET   /api/users/me
PATCH /api/users/me
PATCH /api/users/me/password
```

Health:

```http
GET /api/health
GET /database-test
```

Admin APIs:

```http
GET    /api/admin/dashboard
GET    /api/admin/orders
GET    /api/admin/products
GET    /api/admin/products/{id}
POST   /api/admin/products
PUT    /api/admin/products/{id}
PATCH  /api/admin/products/{id}
POST   /api/admin/products/{id}/image
DELETE /api/admin/products/{id}
GET    /api/admin/customers
GET    /api/admin/customers/{id}
PATCH  /api/admin/customers/{id}
```

Legacy admin user APIs are still available for compatibility:

```http
GET    /api/admin/users
GET    /api/admin/users/{id}
PATCH  /api/admin/users/{id}
```

## Product Data Visibility

Public product responses hide admin-only fields:

- SKU
- exact quantity
- created/updated timestamps

Public product responses include:

- image URL
- name
- description
- price
- simple stock status

Admin product responses include:

- SKU
- exact quantity
- image URL
- created/updated timestamps

Default product image:

```text
/static/images/product-placeholder.png
```

## Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```

## Initialize Database

The app creates tables automatically on startup and seeds one admin account.

To reset the local SQLite database from scratch with one admin and 50 clothing products:

```powershell
python scripts/reset_local_database.py
```

To seed only the admin account manually:

```powershell
python scripts/seed_dev_accounts.py
```

SQLite WAL mode is disabled in this project (`journal_mode=DELETE`), so changes are written to `app.db` directly instead of being kept in `app.db-wal`.

Redis is optional for local development. Product APIs still work when Redis is not running, but `/api/health` will report `status=degraded` and `redis=down`.

Optional benchmark seed data:

```powershell
python scripts/seed_products.py --count 1000
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/admin/dashboard
http://127.0.0.1:8000/docs
```

## Testing

```powershell
python -m pytest
```

The test suite covers auth, page access control, admin authorization, customer APIs, product CRUD, product upload validation, Redis cache hit/miss/failover/invalidation, health checks, dashboard stats, public/admin product response visibility, Swagger/OpenAPI, and performance smoke tests.

## Current Limitations

Not implemented yet:

- shopping cart
- checkout
- payment
- real order creation
- real revenue calculation
- real customer order history

SQLite is good for local development. For production-style concurrency, use a server database such as PostgreSQL.

