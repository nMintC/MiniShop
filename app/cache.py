from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Awaitable
from threading import Lock
from typing import Any
from urllib.parse import quote

from redis import Redis
from redis.exceptions import RedisError

from app.config import REDIS_CACHE_TTL, REDIS_ENABLED, REDIS_URL

logger = logging.getLogger(__name__)
_client: Redis | None = None

CACHE_HIT = "HIT"
CACHE_MISS = "MISS"
CACHE_BYPASS = "BYPASS"
CACHE_ERROR = "ERROR"

# "In-flight" means one request is already loading a missing cache key.
# The dict is process-local, so it only coalesces requests handled by this one
# FastAPI process. Separate workers/servers would each have their own map.
_in_flight: dict[str, asyncio.Task[Any]] = {}
_in_flight_lock = Lock()


def is_redis_enabled() -> bool:
    return REDIS_ENABLED


def get_redis_client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    return _client


def redis_ping() -> bool:
    if not is_redis_enabled():
        return False
    try:
        return (get_redis_client().ping())
    except RedisError as exc:
        logger.warning("Redis connection failed: %s", exc)
        return False
    except OSError as exc:
        logger.warning("Redis connection failed: %s", exc)
        return False


async def load_with_request_coalescing(key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
    # asyncio.Task represents the shared load currently running for this cache key.
    # Multiple requests can await the same Task, so only the first request performs
    # the DB read and Redis SET while the others reuse the same success or failure.
    with _in_flight_lock:
        task = _in_flight.get(key)
        if task is None:
            task = asyncio.create_task(loader())
            _in_flight[key] = task
            logger.debug("Product cache load START key=%s", key)
        else:
            logger.debug("Product cache load JOIN key=%s", key)

    try:
        return await task
    finally:
        # Keep the task registered until the loader has fully finished, including
        # Redis cache writing. Then remove it so failed/completed tasks do not leak.
        if task.done():
            with _in_flight_lock:
                if _in_flight.get(key) is task:
                    _in_flight.pop(key, None)


def cache_get_json_with_status(key: str) -> tuple[Any | None, str]:
    if not is_redis_enabled():
        logger.debug("Product cache BYPASS key=%s", key)
        return None, CACHE_BYPASS

    try:
        raw_value = get_redis_client().get(key)
        if raw_value is None:
            logger.debug("Product cache MISS key=%s", key)
            return None, CACHE_MISS
        logger.debug("Product cache HIT key=%s", key)
        return json.loads(raw_value), CACHE_HIT
    except RedisError as exc:
        logger.warning("Redis cache read failed for %s: %s", key, exc)
        return None, CACHE_ERROR
    except (TypeError, ValueError) as exc:
        logger.warning("Redis cache decode failed for %s: %s", key, exc)
        return None, CACHE_ERROR
    except OSError as exc:
        logger.warning("Redis cache read failed for %s: %s", key, exc)
        return None, CACHE_ERROR


def cache_get_json(key: str) -> Any | None:
    value, _status = cache_get_json_with_status(key)
    return value


def cache_set_json(key: str, value: Any, ttl: int | None = None) -> bool:
    if not is_redis_enabled():
        return False

    try:
        get_redis_client().set(key, json.dumps(value, separators=(",", ":")), ex=ttl or REDIS_CACHE_TTL)
        return True
    except RedisError as exc:
        logger.warning("Redis cache write failed for %s: %s", key, exc)
        return False
    except (TypeError, ValueError) as exc:
        logger.warning("Redis cache encode failed for %s: %s", key, exc)
        return False
    except OSError as exc:
        logger.warning("Redis cache write failed for %s: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    if not is_redis_enabled():
        return False

    try:
        get_redis_client().delete(key)
        return True
    except RedisError as exc:
        logger.warning("Redis cache invalidation failed for %s: %s", key, exc)
        return False
    except OSError as exc:
        logger.warning("Redis cache invalidation failed for %s: %s", key, exc)
        return False


def cache_delete_prefix(prefix: str) -> int:
    if not is_redis_enabled():
        return 0

    deleted = 0
    try:
        client = get_redis_client()
        batch: list[str] = []
        for key in client.scan_iter(match=f"{prefix}*"):
            batch.append(key)
            if len(batch) >= 100:
                deleted += (client.delete(*batch))
                batch = []
        if batch:
            deleted += (client.delete(*batch))
        return deleted
    except RedisError as exc:
        logger.warning("Redis cache invalidation failed for prefix %s: %s", prefix, exc)
        return deleted
    except OSError as exc:
        logger.warning("Redis cache invalidation failed for prefix %s: %s", prefix, exc)
        return deleted


def product_cache_key(product_id: int) -> str:
    return f"product:{product_id}"


def product_list_cache_key(q: str | None, page: int, page_size: int) -> str:
    normalized_q = (q or "").strip().lower()
    safe_q = quote(normalized_q, safe="")
    return f"products:list:page={page}:size={page_size}:q={safe_q}"


def invalidate_product_cache(product_id: int) -> None:
    cache_delete(product_cache_key(product_id))


def invalidate_product_list_cache() -> None:
    cache_delete_prefix("products:list:")
