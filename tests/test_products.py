from pathlib import Path

from tests.conftest import product_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_list_products(client, admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload())
    assert created.status_code == 201

    public = client.get("/api/products?page=1&page_size=20")
    assert public.status_code == 200
    assert public.json()["total"] == 1


def test_public_product_detail(client, admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload())
    product_id = created.json()["id"]

    detail = client.get(f"/api/products/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Keyboard"


def test_product_not_found(client):
    response = client.get("/api/products/999999")
    assert response.status_code == 404


def test_admin_create_get_update_delete_product(admin_client):
    create = admin_client.post("/api/admin/products", json=product_payload())
    assert create.status_code == 201
    product = create.json()
    assert product["sku"] == "SKU-001"

    detail = admin_client.get(f"/api/admin/products/{product['id']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Keyboard"

    update = admin_client.put(
        f"/api/admin/products/{product['id']}",
        json={"name": "Keyboard Pro", "price": "59.99", "quantity": 7},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Keyboard Pro"
    assert update.json()["quantity"] == 7

    delete = admin_client.delete(f"/api/admin/products/{product['id']}")
    assert delete.status_code == 204

    missing = admin_client.get(f"/api/admin/products/{product['id']}")
    assert missing.status_code == 404


def test_duplicate_sku_is_conflict(admin_client):
    first = admin_client.post("/api/admin/products", json=product_payload())
    assert first.status_code == 201
    duplicate = admin_client.post("/api/admin/products", json=product_payload(name="Mouse"))
    assert duplicate.status_code == 409


def test_invalid_price_and_quantity_are_rejected(admin_client):
    bad_price = product_payload(sku="BAD-PRICE")
    bad_price["price"] = "-1.00"
    assert admin_client.post("/api/admin/products", json=bad_price).status_code == 422

    huge_price = product_payload(sku="HUGE-PRICE")
    huge_price["price"] = "1000000000000000000000000000"
    assert admin_client.post("/api/admin/products", json=huge_price).status_code == 422

    bad_quantity = product_payload(sku="BAD-QTY")
    bad_quantity["quantity"] = -1
    assert admin_client.post("/api/admin/products", json=bad_quantity).status_code == 422

    huge_quantity = product_payload(sku="HUGE-QTY")
    huge_quantity["quantity"] = 1000000000000000000000000000
    assert admin_client.post("/api/admin/products", json=huge_quantity).status_code == 422


def test_description_length_is_limited_and_multiline_is_kept(admin_client):
    too_long = product_payload(sku="LONG-DESC")
    too_long["description"] = "a" * 1001
    assert admin_client.post("/api/admin/products", json=too_long).status_code == 422

    multiline = product_payload(sku="MULTI-DESC")
    multiline["description"] = "Line one\nLine two"
    created = admin_client.post("/api/admin/products", json=multiline)
    assert created.status_code == 201
    assert created.json()["description"] == "Line one\nLine two"

def test_admin_can_upload_product_image(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="IMG-001"))
    product_id = created.json()["id"]

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    response = admin_client.post(
        f"/api/admin/products/{product_id}/image",
        files={"file": ("keyboard.png", png_bytes, "image/png")},
    )

    assert response.status_code == 200
    image_url = response.json()["image_url"]
    assert image_url.startswith("/static/uploads/products/product_")

    uploaded_path = PROJECT_ROOT / "app" / image_url.lstrip("/")
    assert uploaded_path.exists()
    uploaded_path.unlink()


def test_invalid_image_upload_is_rejected(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="BAD-IMG"))
    product_id = created.json()["id"]

    response = admin_client.post(
        f"/api/admin/products/{product_id}/image",
        files={"file": ("keyboard.gif", b"GIF89a", "image/gif")},
    )
    assert response.status_code == 400


def test_admin_update_product(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="UPD-001"))
    product_id = created.json()["id"]
    updated = admin_client.patch(f"/api/admin/products/{product_id}", json={"quantity": 3})
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 3


def test_admin_delete_product(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="DEL-001"))
    product_id = created.json()["id"]
    deleted = admin_client.delete(f"/api/admin/products/{product_id}")
    assert deleted.status_code == 204


def test_user_cannot_create_update_delete(client, admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="AUTHZ-001"))
    product_id = created.json()["id"]
    admin_client.post("/api/auth/logout")

    assert client.post(
        "/api/auth/register",
        json={"username": "customer", "email": "customer@example.com", "password": "password123"},
    ).status_code == 201
    assert client.post("/api/auth/login", json={"username": "customer", "password": "password123"}).status_code == 200

    assert client.post("/api/admin/products", json=product_payload(sku="NOPE-001")).status_code == 403
    assert client.patch(f"/api/admin/products/{product_id}", json={"quantity": 1}).status_code == 403
    assert client.delete(f"/api/admin/products/{product_id}").status_code == 403


def test_anonymous_cannot_create_update_delete(client, admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="ANON-001"))
    product_id = created.json()["id"]
    admin_client.post("/api/auth/logout")

    assert client.post("/api/admin/products", json=product_payload(sku="ANON-002")).status_code == 401
    assert client.patch(f"/api/admin/products/{product_id}", json={"quantity": 1}).status_code == 401
    assert client.delete(f"/api/admin/products/{product_id}").status_code == 401


def test_search_and_pagination(client, admin_client):
    for index in range(25):
        response = admin_client.post(
            "/api/admin/products",
            json=product_payload(sku=f"ITEM-{index:03d}", name=f"Item {index}"),
        )
        assert response.status_code == 201

    page_two = client.get("/api/products?page=2&page_size=10")
    assert page_two.status_code == 200
    assert page_two.json()["page"] == 2
    assert len(page_two.json()["items"]) == 10

    search = client.get("/api/products?q=Item 2&page=1&page_size=10")
    assert search.status_code == 200
    assert search.json()["total"] >= 6


def test_dashboard_stats_update_after_product_crud(admin_client):
    initial = admin_client.get("/api/admin/dashboard").json()

    created = admin_client.post("/api/admin/products", json=product_payload(sku="STATS-001", name="Stats Product"))
    assert created.status_code == 201
    product_id = created.json()["id"]

    after_create = admin_client.get("/api/admin/dashboard").json()
    assert after_create["total_products"] == initial["total_products"] + 1
    assert after_create["total_revenue"] == "0"
    assert after_create["total_orders"] == 0
    assert "total_customers" in after_create
    assert "low_stock_products" not in after_create
    assert "total_quantity" not in after_create

    deleted = admin_client.delete(f"/api/admin/products/{product_id}")
    assert deleted.status_code == 204

    after_delete = admin_client.get("/api/admin/dashboard").json()
    assert after_delete["total_products"] == initial["total_products"]


def test_product_timestamps_use_vietnam_timezone(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="TZ-001", name="Timezone Product"))
    assert created.status_code == 201
    product = created.json()
    assert product["created_at"].endswith("+07:00")
    assert product["updated_at"].endswith("+07:00")


def test_public_product_schema_hides_internal_fields(client, admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="PUBLIC-001"))
    product_id = created.json()["id"]

    public_detail = client.get(f"/api/products/{product_id}")
    assert public_detail.status_code == 200
    public_data = public_detail.json()
    assert "sku" not in public_data
    assert "quantity" not in public_data
    assert "created_at" not in public_data
    assert "updated_at" not in public_data
    assert "image_url" in public_data
    assert "in_stock" in public_data

    public_list_item = client.get("/api/products?page=1&page_size=20").json()["items"][0]
    assert "sku" not in public_list_item


def test_admin_product_schema_includes_internal_fields(admin_client):
    created = admin_client.post("/api/admin/products", json=product_payload(sku="ADMIN-001"))
    assert created.status_code == 201
    data = created.json()
    assert data["sku"] == "ADMIN-001"
    assert "quantity" in data
    assert "image_url" in data
    assert "updated_at" in data