from __future__ import annotations

import os
from collections import Counter

from locust import HttpUser, between, events, task

# Scenario A: one hot product key. Use this when you want many users to hit the
# exact same Redis key, for example product:3, to observe hot-key behavior.
BENCHMARK_PRODUCT_ID = int(os.getenv("BENCHMARK_PRODUCT_ID", "3"))
CACHE_STATUS_COUNTS: Counter[str] = Counter()


def record_cache_status(response) -> str:
    status = response.headers.get("X-Cache", "UNKNOWN")
    CACHE_STATUS_COUNTS[status] += 1
    return status


@events.test_stop.add_listener
def print_cache_summary(environment, **kwargs) -> None:
    if not CACHE_STATUS_COUNTS:
        return
    total = sum(CACHE_STATUS_COUNTS.values())
    print("\nCache status summary for locust_redis.py")
    print(f"Total product responses: {total}")
    for status, count in sorted(CACHE_STATUS_COUNTS.items()):
        ratio = (count / total) * 100 if total else 0
        print(f"  {status}: {count} ({ratio:.1f}%)")


class ProductReadUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def product_detail(self) -> None:
        with self.client.get(
            f"/api/products/{BENCHMARK_PRODUCT_ID}",
            name="GET /api/products/[id] hot-key",
            catch_response=True,
        ) as response:
            cache_status = record_cache_status(response)

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
                return

            if cache_status == "ERROR":
                response.failure("Redis returned X-Cache=ERROR; check Redis health for this benchmark")
