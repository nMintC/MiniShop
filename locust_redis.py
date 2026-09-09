from __future__ import annotations

import os

from locust import HttpUser, between, task

# For the cache-stampede lab, clear this product key first and then send many users here.
# Keeping all users on one product makes it easy to observe request coalescing.
BENCHMARK_PRODUCT_ID = int(os.getenv("BENCHMARK_PRODUCT_ID", "3"))


class ProductReadUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def product_detail(self) -> None:
        with self.client.get(
            f"/api/products/{BENCHMARK_PRODUCT_ID}",
            name="GET /api/products/{id}",
            catch_response=True,
        ) as response:
            cache_status = response.headers.get("X-Cache", "UNKNOWN")
            response.request_meta["name"] = f"GET /api/products/{{id}} X-Cache={cache_status}"

            if response.status_code != 200:
                response.failure(
                    f"Product {BENCHMARK_PRODUCT_ID} failed: {response.status_code} {response.text[:120]}"
                )
                return

            try:
                payload = response.json()
            except ValueError as exc:
                response.failure(f"Invalid product JSON: {exc}")
                return

            if payload.get("id") != BENCHMARK_PRODUCT_ID:
                response.failure(
                    f"Expected product id {BENCHMARK_PRODUCT_ID}, got {payload.get('id')!r}. "
                    "Check BENCHMARK_PRODUCT_ID exists in the database."
                )
                return

            if not isinstance(payload.get("name"), str) or not payload["name"]:
                response.failure("Product response is missing a valid name")


