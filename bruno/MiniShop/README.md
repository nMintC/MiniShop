# MiniShop API Bruno Collection

## How to Open

1. Open Bruno.
2. Choose **Open Collection**.
3. Select this folder: `bruno/MiniShop`.
4. Choose the `local` environment.
5. Make sure the FastAPI server is running at `http://127.0.0.1:8000`.

## Recommended Test Flow

1. Run `06 Health / Database Test`.
2. Run `01 Auth / Login Admin`.
3. Run admin requests such as Dashboard, Products, Customers.
4. To test customers, run `01 Auth / Register Customer`, then log back in as admin before using admin customer routes.

Bruno should keep the `shop_session` cookie after login. If an admin route returns `401`, run `Login Admin` again.

## Useful Local Admin

```text
username: admin
email: admin@minishop.local
password: Admin123!
```

## Variables

Edit `environments/local.bru` if your server port or test IDs are different.
## Redis Cache Checks

Use `02 Public Products / Get Public Product Detail` and check the response headers:

```text
X-Cache: MISS
X-Cache: HIT
X-Cache: BYPASS
X-Cache: ERROR
```

Use `06 Health / Redis Health` to confirm whether Redis is `ok`, `down`, or `disabled`.
