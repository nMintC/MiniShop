from __future__ import annotations

import os
import random
from collections import Counter

from locust import HttpUser, between, events, task

DEFAULT_PRODUCT_IDS = "1,2,3,4,5"
DEFAULT_WEIGHTS = "40,25,15,10,10"
CACHE_STATUS_COUNTS: Counter[str] = Counter()
KEY_COUNTS: Counter[int] = Counter()


def parse_int_list(raw_value: str, fallback: list[int]) -> list[int]:
    values: list[int] = []
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values or fallback


PRODUCT_IDS = parse_int_list(os.getenv("BENCHMARK_PRODUCT_IDS", DEFAULT_PRODUCT_IDS), [1, 2, 3, 4, 5])
PRODUCT_WEIGHTS = parse_int_list(os.getenv("BENCHMARK_PRODUCT_WEIGHTS", DEFAULT_WEIGHTS), [40, 25, 15, 10, 10])
DISTRIBUTION = os.getenv("BENCHMARK_DISTRIBUTION", "weighted").strip().lower()

if len(PRODUCT_WEIGHTS) != len(PRODUCT_IDS):
    PRODUCT_WEIGHTS = [1] * len(PRODUCT_IDS)


def choose_product_id() -> int:
    if DISTRIBUTION == "uniform":
        return random.choice(PRODUCT_IDS)
    return random.choices(PRODUCT_IDS, weights=PRODUCT_WEIGHTS, k=1)[0]


def record_cache_status(product_id: int, response) -> None:
    CACHE_STATUS_COUNTS[response.headers.get("X-Cache", "UNKNOWN")] += 1
    KEY_COUNTS[product_id] += 1


@events.test_stop.add_listener
def print_cache_summary(environment, **kwargs) -> None:
    total = sum(CACHE_STATUS_COUNTS.values())
    if not total:
        return
    print("\nCache status summary for locust_redis_multi.py")
    print(f"Product ids: {PRODUCT_IDS}")
    print(f"Distribution: {DISTRIBUTION}")
    for status, count in sorted(CACHE_STATUS_COUNTS.items()):
        print(f"  X-Cache {status}: {count} ({count / total * 100:.1f}%)")
    print("Requests per product key:")
    for product_id, count in sorted(KEY_COUNTS.items()):
        print(f"  product:{product_id}: {count}")


class MultipleHotProductsUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def product_detail(self) -> None:
        product_id = choose_product_id()
        with self.client.get(
            f"/api/products/{product_id}",
            name="GET /api/products/[id] multi-hot-key",
            catch_response=True,
        ) as response:
            record_cache_status(product_id, response)

            if response.status_code != 200:
                response.failure(f"Product {product_id} failed: {response.status_code} {response.text[:120]}")
                return

            try:
                payload = response.json()
            except ValueError as exc:
                response.failure(f"Invalid product JSON: {exc}")
                return

            if payload.get("id") != product_id:
                response.failure(f"Expected product id {product_id}, got {payload.get('id')!r}")
