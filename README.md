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

## API Overview

Auth:

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Customer APIs:

```http
GET   /api/products
GET   /api/products/{id}
GET   /api/users/me
PATCH /api/users/me
PATCH /api/users/me/password
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

The test suite covers auth, page access control, admin authorization, customer APIs, product CRUD, product upload validation, dashboard stats, public/admin product response visibility, Swagger/OpenAPI, and performance smoke tests.

## Current Limitations

Not implemented yet:

- shopping cart
- checkout
- payment
- real order creation
- real revenue calculation
- real customer order history

SQLite is good for local development. For production-style concurrency, use a server database such as PostgreSQL.