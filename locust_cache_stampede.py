from __future__ import annotations

import os
import random
from collections import Counter

import requests
from locust import HttpUser, constant, events, task
from redis import Redis
from redis.exceptions import RedisError

from app.config import REDIS_URL

DEFAULT_PRODUCT_IDS = "1,2,3,4,5"
VALID_CACHE_STATUSES = ("HIT", "MISS", "BYPASS", "ERROR")

HTTP_COUNTS: Counter[str] = Counter()
CACHE_COUNTS: Counter[str] = Counter()
FAILURE_COUNTS: Counter[str] = Counter()
KEY_COUNTS: Counter[int] = Counter()


def parse_product_ids() -> list[int]:
    values: list[int] = []
    for part in os.getenv("BENCHMARK_PRODUCT_IDS", DEFAULT_PRODUCT_IDS).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values or [1, 2, 3, 4, 5]


PRODUCT_IDS = parse_product_ids()
CLEAR_CACHE_ON_START = os.getenv("BENCHMARK_CLEAR_CACHE_ON_START", "false").strip().lower() in {"1", "true", "yes", "on"}


def product_cache_keys() -> list[str]:
    return [f"product:{product_id}" for product_id in PRODUCT_IDS]


def classify_request_error(error: Exception | None) -> str:
    if isinstance(error, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(error, requests.exceptions.ConnectionError):
        return "connection error"
    if isinstance(error, requests.exceptions.RequestException):
        return f"request error: {type(error).__name__}"
    if error is not None:
        return f"unexpected client error: {type(error).__name__}"
    return "request failed before HTTP response"


def classify_bad_status(response) -> str:
    status_code = response.status_code
    if status_code == 0:
        # Locust uses status 0 when the request raised before an HTTP response
        # existed. The real cause is kept in response.error.
        return classify_request_error(getattr(response, "error", None))
    if 400 <= status_code < 500:
        return "HTTP 4xx"
    if 500 <= status_code < 600:
        return "HTTP 5xx"
    return f"unexpected HTTP {status_code}"


def failure_detail(response) -> str:
    error = getattr(response, "error", None)
    if error is not None:
        return str(error)[:200]
    return response.text[:200]


def record_cache_status(response) -> None:
    cache_status = response.headers.get("X-Cache")
    if cache_status is None:
        CACHE_COUNTS["missing X-Cache"] += 1
        return
    if cache_status in VALID_CACHE_STATUSES:
        CACHE_COUNTS[cache_status] += 1
        return
    CACHE_COUNTS[f"invalid X-Cache: {cache_status}"] += 1


def record_failure(response, product_id: int, reason: str) -> None:
    HTTP_COUNTS["failed"] += 1
    FAILURE_COUNTS[reason] += 1
    detail = failure_detail(response)
    message = f"Product {product_id} failed: {reason}"
    if detail:
        message = f"{message} - {detail}"
    response.failure(message)


@events.test_start.add_listener
def clear_cache_keys(environment, **kwargs) -> None:
    keys = product_cache_keys()
    print("\nCache stampede benchmark keys:")
    for key in keys:
        print(f"  {key}")
    if not CLEAR_CACHE_ON_START:
        print("Set BENCHMARK_CLEAR_CACHE_ON_START=true to let Locust delete these Redis keys at test start.")
        return

    try:
        deleted = Redis.from_url(REDIS_URL, decode_responses=True).delete(*keys)
        print(f"Deleted {deleted} Redis key(s) before starting the stampede run.")
    except (RedisError, OSError) as exc:
        print(f"Could not clear Redis keys from Locust: {exc}")


@events.test_stop.add_listener
def print_cache_summary(environment, **kwargs) -> None:
    total = HTTP_COUNTS["total"]
    success = HTTP_COUNTS["success"]
    failed = HTTP_COUNTS["failed"]
    failure_rate = (failed / total) * 100 if total else 0

    print("\nCache stampede benchmark summary")
    print("Locust latency shows external performance. DB loader/coalesced counts still need app-side instrumentation.")

    print("\nHTTP")
    print(f"  total: {total}")
    print(f"  success: {success}")
    print(f"  failed: {failed}")
    print(f"  failure rate: {failure_rate:.1f}%")

    if FAILURE_COUNTS:
        print("  failure breakdown:")
        for reason, count in sorted(FAILURE_COUNTS.items()):
            print(f"    {reason}: {count}")

    print("\nCache")
    for status in VALID_CACHE_STATUSES:
        print(f"  {status}: {CACHE_COUNTS[status]}")
    print(f"  missing X-Cache: {CACHE_COUNTS['missing X-Cache']}")

    unexpected_cache = {key: value for key, value in CACHE_COUNTS.items() if key not in VALID_CACHE_STATUSES and key != "missing X-Cache"}
    for status, count in sorted(unexpected_cache.items()):
        print(f"  {status}: {count}")

    valid_cache_total = sum(CACHE_COUNTS[status] for status in VALID_CACHE_STATUSES)
    hit_ratio = (CACHE_COUNTS["HIT"] / valid_cache_total) * 100 if valid_cache_total else 0
    print(f"  valid X-Cache responses: {valid_cache_total}")
    print(f"  cache hit ratio: {hit_ratio:.1f}%")

    if KEY_COUNTS:
        print("\nRequests per product key:")
        for product_id, count in sorted(KEY_COUNTS.items()):
            print(f"  product:{product_id}: {count}")


class CacheStampedeUser(HttpUser):
    # Very small wait time helps many users arrive while the keys are cold.
    wait_time = constant(0)

    @task
    def product_detail_cold_burst(self) -> None:
        product_id = random.choice(PRODUCT_IDS)
        with self.client.get(
            f"/api/products/{product_id}",
            name="GET /api/products/[id] cache-stampede",
            catch_response=True,
        ) as response:
            HTTP_COUNTS["total"] += 1
            KEY_COUNTS[product_id] += 1

            if response.status_code != 200:
                record_failure(response, product_id, classify_bad_status(response))
                return

            try:
                payload = response.json()
            except ValueError:
                record_failure(response, product_id, "response invalid")
                return

            if payload.get("id") != product_id:
                record_failure(response, product_id, "response invalid")
                return

            HTTP_COUNTS["success"] += 1
            record_cache_status(response)