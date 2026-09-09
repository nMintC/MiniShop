import asyncio
import json

import pytest
from fastapi import Response
from redis.exceptions import RedisError

import app.cache as cache
import app.routers.health as health_router
import app.routers.products as product_router
from tests.conftest import product_payload


class FakeRedis:
    def __init__(self, *, raise_get: bool = False, raise_set: bool = False, ping_ok: bool = True):
        self.store: dict[str, str] = {}
        self.raise_get = raise_get
        self.raise_set = raise_set
        self.ping_ok = ping_ok
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, int, str]] = []
        self.delete_calls: list[tuple[str, ...]] = []

    def ping(self):
        if not self.ping_ok:
            raise RedisError("redis down")
        return True

    def get(self, key: str):
        self.get_calls.append(key)
        if self.raise_get:
            raise RedisError("read failed")
        return self.store.get(key)

    def set(self, key: str, value: str, *, ex: int):
        if self.raise_set:
            raise RedisError("write failed")
        self.set_calls.append((key, ex, value))
        self.store[key] = value
        return True

    def delete(self, *keys: str):
        self.delete_calls.append(tuple(keys))
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    def scan_iter(self, match: str):
        prefix = match.removesuffix("*")
        for key in list(self.store):
            if key.startswith(prefix):
                yield key


class FailingRedisClient:
    def get(self, key: str):
        raise AssertionError("Redis client should not be used when REDIS_ENABLED=false")

    def set(self, key: str, value: str, *, ex: int):
        raise AssertionError("Redis client should not be used when REDIS_ENABLED=false")

    def delete(self, *keys: str):
        raise AssertionError("Redis client should not be used when REDIS_ENABLED=false")

    def scan_iter(self, match: str):
        raise AssertionError("Redis client should not be used when REDIS_ENABLED=false")


@pytest.fixture(autouse=True)
def clear_in_flight_tasks():
    cache._in_flight.clear()
    yield
    cache._in_flight.clear()


def test_product_detail_cache_miss_sets_cache(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="CACHE-MISS"))
    product_id = created.json()["id"]
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_client", fake)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = admin_client.get(f"/api/products/{product_id}")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["name"] == "Keyboard"
    assert fake.set_calls[0][0] == f"product:{product_id}"
    assert json.loads(fake.set_calls[0][2])["id"] == product_id


def test_product_detail_cache_hit_skips_database(client, monkeypatch):
    product_id = 123
    cached = {
        "id": product_id,
        "name": "Cached Shirt",
        "description": "From Redis",
        "price": "25.00",
        "image_url": "/static/images/product-placeholder.png",
        "in_stock": True,
    }
    fake = FakeRedis()
    fake.store[f"product:{product_id}"] = json.dumps(cached)
    monkeypatch.setattr(cache, "_client", fake)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    def fail_get_product(db, product_id):
        raise AssertionError("DB should not be queried on cache hit")

    monkeypatch.setattr(product_router, "get_product", fail_get_product)

    response = client.get(f"/api/products/{product_id}")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "HIT"
    assert response.json() == cached
    assert fake.set_calls == []


def test_product_detail_cache_bypass_when_redis_disabled(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="BYPASS-DETAIL"))
    product_id = created.json()["id"]
    monkeypatch.setattr(cache, "_client", FailingRedisClient())
    monkeypatch.setattr(cache, "REDIS_ENABLED", False)

    response = admin_client.get(f"/api/products/{product_id}")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json()["id"] == product_id


def test_product_list_cache_miss_sets_cache(admin_client, monkeypatch):
    admin_client.post("/api/admin/products", json=product_payload(sku="LIST-MISS", name="White Shirt"))
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_client", fake)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = admin_client.get("/api/products?page=1&page_size=10&q=shirt")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["total"] == 1
    assert fake.set_calls[0][0] == "products:list:page=1:size=10:q=shirt"
    assert json.loads(fake.set_calls[0][2])["items"][0]["name"] == "White Shirt"


def test_product_list_cache_hit_skips_database(client, monkeypatch):
    cached = {
        "items": [
            {
                "id": 99,
                "name": "Cached Product",
                "description": None,
                "price": "10.00",
                "image_url": "/static/images/product-placeholder.png",
                "in_stock": True,
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
    }
    fake = FakeRedis()
    fake.store["products:list:page=1:size=10:q="] = json.dumps(cached)
    monkeypatch.setattr(cache, "_client", fake)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    def fail_list_products(db, q, page, page_size):
        raise AssertionError("DB should not be queried on cache hit")

    monkeypatch.setattr(product_router, "_list_products", fail_list_products)

    response = client.get("/api/products?page=1&page_size=10")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "HIT"
    assert response.json() == cached
    assert fake.set_calls == []


def test_product_list_cache_bypass_when_redis_disabled(admin_client, monkeypatch):
    admin_client.post("/api/admin/products", json=product_payload(sku="BYPASS-LIST", name="Black Shirt"))
    monkeypatch.setattr(cache, "_client", FailingRedisClient())
    monkeypatch.setattr(cache, "REDIS_ENABLED", False)

    response = admin_client.get("/api/products?page=1&page_size=10&q=shirt")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json()["total"] == 1


def test_request_coalescing_same_key_runs_one_loader():
    async def run():
        calls = 0

        async def loader():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"value": "shared"}

        results = await asyncio.gather(
            *(cache.load_with_request_coalescing("product:1", loader) for _ in range(50))
        )
        assert results == [{"value": "shared"}] * 50
        assert calls == 1
        assert "product:1" not in cache._in_flight

    asyncio.run(run())


def test_request_coalescing_different_keys_load_independently():
    async def run():
        calls: list[str] = []

        async def loader_for(value: str):
            calls.append(value)
            await asyncio.sleep(0.01)
            return {"value": value}

        results = await asyncio.gather(
            cache.load_with_request_coalescing("product:1", lambda: loader_for("one")),
            cache.load_with_request_coalescing("product:2", lambda: loader_for("two")),
        )
        assert results == [{"value": "one"}, {"value": "two"}]
        assert sorted(calls) == ["one", "two"]
        assert cache._in_flight == {}

    asyncio.run(run())


def test_request_coalescing_failed_load_cleans_up_task():
    async def run():
        calls = 0

        async def loader():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            raise RuntimeError("database failed")

        results = await asyncio.gather(
            *(cache.load_with_request_coalescing("product:fail", loader) for _ in range(5)),
            return_exceptions=True,
        )
        assert calls == 1
        assert all(isinstance(result, RuntimeError) for result in results)
        assert "product:fail" not in cache._in_flight

    asyncio.run(run())


def test_product_detail_concurrent_miss_coalesces_loader(monkeypatch):
    async def run():
        calls = 0
        payload = {
            "id": 1,
            "name": "Coalesced Shirt",
            "description": None,
            "price": "19.00",
            "image_url": "/static/images/product-placeholder.png",
            "in_stock": True,
        }

        def miss(cache_key):
            return None, cache.CACHE_MISS

        async def load_once(cache_key: str, product_id: int):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return payload

        monkeypatch.setattr(product_router, "cache_get_json_with_status", miss)
        monkeypatch.setattr(product_router, "load_and_cache_product_detail", load_once)

        responses = [Response() for _ in range(25)]
        results = await asyncio.gather(*(product_router.read_product(1, response) for response in responses))

        assert results == [payload] * 25
        assert calls == 1
        assert {response.headers["X-Cache"] for response in responses} == {"MISS"}

    asyncio.run(run())


def test_create_product_invalidates_list_cache(admin_client, monkeypatch):
    calls = []
    monkeypatch.setattr(product_router, "invalidate_product_list_cache", lambda: calls.append("list"))

    response = admin_client.post("/api/admin/products", json=product_payload(sku="CREATE-INV"))

    assert response.status_code == 201
    assert calls == ["list"]


def test_update_product_invalidates_detail_and_list_cache(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="UPDATE-INV"))
    product_id = created.json()["id"]
    calls = []
    monkeypatch.setattr(product_router, "invalidate_product_cache", lambda value: calls.append(("detail", value)))
    monkeypatch.setattr(product_router, "invalidate_product_list_cache", lambda: calls.append(("list", None)))

    response = admin_client.patch(f"/api/admin/products/{product_id}", json={"name": "Updated"})

    assert response.status_code == 200
    assert calls == [("detail", product_id), ("list", None)]


def test_delete_product_invalidates_detail_and_list_cache(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="DELETE-INV"))
    product_id = created.json()["id"]
    calls = []
    monkeypatch.setattr(product_router, "invalidate_product_cache", lambda value: calls.append(("detail", value)))
    monkeypatch.setattr(product_router, "invalidate_product_list_cache", lambda: calls.append(("list", None)))

    response = admin_client.delete(f"/api/admin/products/{product_id}")

    assert response.status_code == 204
    assert calls == [("detail", product_id), ("list", None)]


def test_redis_get_error_falls_back_to_database(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="GET-FAIL"))
    product_id = created.json()["id"]
    monkeypatch.setattr(cache, "_client", FakeRedis(raise_get=True))
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = admin_client.get(f"/api/products/{product_id}")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "ERROR"
    assert response.json()["id"] == product_id


def test_redis_set_error_still_returns_response(admin_client, monkeypatch):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="SET-FAIL"))
    product_id = created.json()["id"]
    monkeypatch.setattr(cache, "_client", FakeRedis(raise_set=True))
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = admin_client.get(f"/api/products/{product_id}")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["id"] == product_id


def test_health_reports_redis_ok(client, monkeypatch):
    monkeypatch.setattr(health_router, "database_ok", lambda: True)
    monkeypatch.setattr(health_router, "redis_ping", lambda: True)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_health_reports_redis_down_as_degraded(client, monkeypatch):
    monkeypatch.setattr(health_router, "database_ok", lambda: True)
    monkeypatch.setattr(health_router, "redis_ping", lambda: False)
    monkeypatch.setattr(cache, "REDIS_ENABLED", True)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "ok", "redis": "down"}


def test_health_reports_redis_disabled_without_ping(client, monkeypatch):
    monkeypatch.setattr(health_router, "database_ok", lambda: True)
    monkeypatch.setattr(cache, "REDIS_ENABLED", False)

    def fail_ping():
        raise AssertionError("Redis ping should not run when REDIS_ENABLED=false")

    monkeypatch.setattr(health_router, "redis_ping", fail_ping)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "disabled"}
