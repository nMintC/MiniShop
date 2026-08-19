from tests.conftest import product_payload


def test_create_get_list_update_delete_product(auth_client):
    create = auth_client.post("/api/products", json=product_payload())
    assert create.status_code == 201
    product = create.json()
    assert product["sku"] == "SKU-001"

    detail = auth_client.get(f"/api/products/{product['id']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Keyboard"

    listing = auth_client.get("/api/products?page=1&page_size=20")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    update = auth_client.put(
        f"/api/products/{product['id']}",
        json={"name": "Keyboard Pro", "price": "59.99", "quantity": 7},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Keyboard Pro"
    assert update.json()["quantity"] == 7

    delete = auth_client.delete(f"/api/products/{product['id']}")
    assert delete.status_code == 204

    missing = auth_client.get(f"/api/products/{product['id']}")
    assert missing.status_code == 404


def test_product_not_found(auth_client):
    response = auth_client.get("/api/products/999999")
    assert response.status_code == 404


def test_duplicate_sku_is_conflict(auth_client):
    first = auth_client.post("/api/products", json=product_payload())
    assert first.status_code == 201
    duplicate = auth_client.post("/api/products", json=product_payload(name="Mouse"))
    assert duplicate.status_code == 409


def test_invalid_price_and_quantity_are_rejected(auth_client):
    bad_price = product_payload(sku="BAD-PRICE")
    bad_price["price"] = "-1.00"
    assert auth_client.post("/api/products", json=bad_price).status_code == 422

    bad_quantity = product_payload(sku="BAD-QTY")
    bad_quantity["quantity"] = -1
    assert auth_client.post("/api/products", json=bad_quantity).status_code == 422


def test_search_and_pagination(auth_client):
    for index in range(25):
        response = auth_client.post(
            "/api/products",
            json=product_payload(sku=f"ITEM-{index:03d}", name=f"Item {index}"),
        )
        assert response.status_code == 201

    page_two = auth_client.get("/api/products?page=2&page_size=10")
    assert page_two.status_code == 200
    assert page_two.json()["page"] == 2
    assert len(page_two.json()["items"]) == 10

    search = auth_client.get("/api/products?q=Item 2&page=1&page_size=10")
    assert search.status_code == 200
    assert search.json()["total"] >= 6


def test_dashboard_stats_update_after_product_crud(auth_client):
    initial = auth_client.get("/api/dashboard").json()

    created = auth_client.post("/api/products", json=product_payload(sku="STATS-001", name="Stats Product"))
    assert created.status_code == 201
    product_id = created.json()["id"]

    after_create = auth_client.get("/api/dashboard").json()
    assert after_create["total_products"] == initial["total_products"] + 1
    assert after_create["total_quantity"] == initial["total_quantity"] + 12

    updated = auth_client.put(f"/api/products/{product_id}", json={"quantity": 20})
    assert updated.status_code == 200

    after_update = auth_client.get("/api/dashboard").json()
    assert after_update["total_products"] == after_create["total_products"]
    assert after_update["total_quantity"] == initial["total_quantity"] + 20

    deleted = auth_client.delete(f"/api/products/{product_id}")
    assert deleted.status_code == 204

    after_delete = auth_client.get("/api/dashboard").json()
    assert after_delete["total_products"] == initial["total_products"]
    assert after_delete["total_quantity"] == initial["total_quantity"]


def test_product_timestamps_use_vietnam_timezone(auth_client):
    created = auth_client.post("/api/products", json=product_payload(sku="TZ-001", name="Timezone Product"))
    assert created.status_code == 201
    product = created.json()
    assert product["created_at"].endswith("+07:00")
    assert product["updated_at"].endswith("+07:00")