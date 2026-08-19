# Performance Report

## Environment

- Date: 2026-08-18
- OS: Windows
- Python: 3.14.3
- Backend: FastAPI + Uvicorn
- Database: SQLite `app.db`
- SQLite settings for benchmark/dev: WAL journal mode, 30s busy timeout
- SQLAlchemy pool: `pool_size=40`, `max_overflow=80`, `pool_timeout=30`
- Dataset size for latest benchmark: 1000 seeded products
- Existing database was not reset during the benchmark run. The seed script added benchmark rows with `SEED-*` SKUs.

## Current Locust Scenario

Each virtual admin user does real authentication and real API/database work.

Startup flow:

```text
on_start()
  -> POST /api/auth/login
```

Steady workload:

```text
GET    /api/dashboard
GET    /api/products?page=...
GET    /api/products?q=...
GET    /api/products/{id}
POST   /api/products
PATCH  /api/products/{id}
DELETE /api/products/{id}
```

Important details:

- There is no separate `GET /api/products seed ids` helper request anymore.
- Product IDs are collected from normal `GET /api/products?page` and `GET /api/products?q` responses.
- Temporary write-flow records use `LOAD-*` SKUs and are not saved as detail-read IDs, so detail reads avoid artificial 404 races.
- The write flow creates one unique product, patches that same product's quantity, then deletes that same product.
- `PATCH` is used for the quantity-only update because it is a partial update.
- `wait_time = between(0.1, 0.5)`, so this is an aggressive load scenario.

## Commands

Server command, without `--reload`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Seed command used:

```bash
python scripts/seed_products.py --count 1000
```

Headless benchmark command:

```bash
locust -f locustfile.py --headless -u 100 -r 100 -t 1m --host http://127.0.0.1:8000 --csv performance_locust_refactor --csv-full-history --only-summary
```

## Before vs After Locust Refactor

Before:

- `on_start()` did login and then a helper request named `GET /api/products seed ids`.
- Startup burst was effectively `100 login requests + 100 seed-id list requests`.
- Update used `PUT` for a quantity-only payload.

After:

- `on_start()` only logs in.
- Normal list/search product responses populate `self.product_ids`.
- No helper endpoint label appears in Locust statistics.
- Update uses `PATCH` for quantity-only changes.
- Create/update/delete status codes are explicitly validated.

## Latest Benchmark Result (`100 users`, `100 users/s`, `60s`)

Evaluation rule used: report p95/p99 and failures; do not rely only on average latency.

- Total requests: 14014
- Failures: 0
- Failure rate: 0.00%
- Average response time: 140.90ms
- Median response time: 110ms
- Aggregated p95: 290ms
- Aggregated p99: 560ms
- Maximum: 2155.78ms
- Requests/second: 236.11
- Result: The application no longer has the seed-id helper request and has 0 failures. Steady CRUD/read APIs are under 1s p95. Login burst still exceeds 1s.

## Endpoint Metrics

| Method | Endpoint | Requests | Failures | Avg ms | Median ms | p95 ms | p99 ms | Max ms | RPS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| POST | `/api/auth/login` | 100 | 0 | 1682.93 | 1800 | 2100 | 2200 | 2155.78 | 1.68 |
| GET | `/api/dashboard` | 3235 | 0 | 100.47 | 84 | 230 | 370 | 1410.98 | 54.50 |
| GET | `/api/products?page` | 4946 | 0 | 152.00 | 130 | 310 | 530 | 1609.49 | 83.33 |
| GET | `/api/products?q` | 2474 | 0 | 138.03 | 120 | 290 | 470 | 1543.24 | 41.68 |
| GET | `/api/products/{id}` | 2020 | 0 | 117.84 | 100 | 260 | 430 | 539.38 | 34.03 |
| POST | `/api/products` | 413 | 0 | 129.44 | 110 | 280 | 460 | 515.83 | 6.96 |
| PATCH | `/api/products/{id}` | 413 | 0 | 131.62 | 110 | 270 | 400 | 485.30 | 6.96 |
| DELETE | `/api/products/{id}` | 413 | 0 | 101.85 | 89 | 220 | 290 | 381.28 | 6.96 |

## Bottleneck

`POST /api/auth/login` still exceeds 1 second under the `100 users/s` login burst:

- Login p95: 2100ms
- Login p99: 2200ms
- Login max: 2155.78ms

This is not hidden by the refactor. It is a real CPU-bound bottleneck from PBKDF2 password verification when 100 logins start almost simultaneously. The CRUD/read workload after login remains below 1 second at p95.

## Notes

SQLite and the app handle the current aggressive 100-user workload without request failures after the connection-pool fix. SQLite is still not a production high-concurrency database. If production-grade concurrent writes or login storms are required, PostgreSQL/MySQL and a more production auth/session strategy should be considered.