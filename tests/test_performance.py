from time import perf_counter

from tests.conftest import product_payload, seed_products


def assert_under_1000ms(call, expected_statuses={200, 201, 204}):
    start = perf_counter()
    response = call()
    elapsed_ms = (perf_counter() - start) * 1000
    assert response.status_code in expected_statuses
    assert elapsed_ms < 1000, f"Request took {elapsed_ms:.2f}ms"
    return response


def test_auth_and_read_latency_under_1000ms(client, admin_client):
    seed_products(1000)

    assert_under_1000ms(
        lambda: client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    )
    assert_under_1000ms(lambda: admin_client.get("/api/admin/dashboard"))
    assert_under_1000ms(lambda: client.get("/api/products?page=1&page_size=20"))
    assert_under_1000ms(lambda: client.get("/api/products?page=2&page_size=20"))
    assert_under_1000ms(lambda: client.get("/api/products?q=Product&page=1&page_size=20"))


def test_crud_latency_under_1000ms(admin_client):
    seed_products(1000)

    listing = assert_under_1000ms(lambda: admin_client.get("/api/admin/products?page=1&page_size=20"))
    first_id = listing.json()["items"][0]["id"]

    assert_under_1000ms(lambda: admin_client.get(f"/api/admin/products/{first_id}"))
    created = assert_under_1000ms(
        lambda: admin_client.post("/api/admin/products", json=product_payload(sku="PERF-001", name="Performance Test"))
    )
    created_id = created.json()["id"]
    assert_under_1000ms(lambda: admin_client.get("/api/admin/products?q=PERF&page=1&page_size=20"))
    assert_under_1000ms(lambda: admin_client.put(f"/api/admin/products/{created_id}", json={"quantity": 3}))
    assert_under_1000ms(lambda: admin_client.delete(f"/api/admin/products/{created_id}"))