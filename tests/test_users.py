from tests.conftest import register_payload


def test_user_profile(user_client):
    response = user_client.get("/api/users/me")
    assert response.status_code == 200
    assert response.json()["username"] == "customer"
    assert response.json()["role"] == "user"
    assert "password_hash" not in response.json()


def test_update_allowed_profile_fields(user_client):
    response = user_client.patch(
        "/api/users/me",
        json={"username": "customer2", "email": "customer2@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "customer2"
    assert response.json()["email"] == "customer2@example.com"


def test_user_cannot_change_role(user_client):
    response = user_client.patch("/api/users/me", json={"role": "admin", "is_active": False})
    assert response.status_code == 200
    assert response.json()["role"] == "user"
    assert response.json()["is_active"] is True


def test_user_change_password(user_client):
    response = user_client.patch(
        "/api/users/me/password",
        json={"current_password": "password123", "new_password": "newpassword123"},
    )
    assert response.status_code == 200

    user_client.post("/api/auth/logout")
    old_login = user_client.post("/api/auth/login", json={"username": "customer", "password": "password123"})
    assert old_login.status_code == 401
    new_login = user_client.post("/api/auth/login", json={"username": "customer", "password": "newpassword123"})
    assert new_login.status_code == 200


def test_admin_list_users(admin_client, client):
    client.post("/api/auth/register", json=register_payload(username="bob", email="bob@example.com"))
    response = admin_client.get("/api/admin/users?page=1&page_size=20")
    assert response.status_code == 200
    assert response.json()["total"] >= 2


def test_admin_user_detail(admin_client, client):
    created = client.post("/api/auth/register", json=register_payload(username="bob", email="bob@example.com"))
    user_id = created.json()["user"]["id"]
    response = admin_client.get(f"/api/admin/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "bob"


def test_admin_disable_user(admin_client, client):
    created = client.post("/api/auth/register", json=register_payload(username="bob", email="bob@example.com"))
    user_id = created.json()["user"]["id"]

    disabled = admin_client.patch(f"/api/admin/users/{user_id}", json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    login = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    assert login.status_code == 403


def test_admin_customer_routes_exclude_admins(admin_client, client):
    created = client.post("/api/auth/register", json=register_payload(username="bob", email="bob@example.com"))
    customer_id = created.json()["user"]["id"]

    listing = admin_client.get("/api/admin/customers?page=1&page_size=20")
    assert listing.status_code == 200
    data = listing.json()
    assert data["total"] == 1
    assert all(item["role"] == "user" for item in data["items"])
    assert "bob" in {item["username"] for item in data["items"]}

    detail = admin_client.get(f"/api/admin/customers/{customer_id}")
    assert detail.status_code == 200
    assert detail.json()["customer"]["username"] == "bob"
    assert detail.json()["orders_count"] == 0
    assert detail.json()["orders"] == []

    admin_user = admin_client.get("/api/auth/me").json()
    assert admin_client.get(f"/api/admin/customers/{admin_user['id']}").status_code == 404


def test_admin_can_toggle_customer_status(admin_client, client):
    created = client.post("/api/auth/register", json=register_payload(username="bob", email="bob@example.com"))
    customer_id = created.json()["user"]["id"]

    disabled = admin_client.patch(f"/api/admin/customers/{customer_id}", json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    enabled = admin_client.patch(f"/api/admin/customers/{customer_id}", json={"is_active": True})
    assert enabled.status_code == 200
    assert enabled.json()["is_active"] is True


def test_admin_user_pagination_and_search(admin_client, client):
    for index in range(15):
        response = client.post(
            "/api/auth/register",
            json=register_payload(username=f"search{index}", email=f"search{index}@example.com"),
        )
        assert response.status_code == 201

    page_two = admin_client.get("/api/admin/users?page=2&page_size=10")
    assert page_two.status_code == 200
    assert page_two.json()["page"] == 2
    assert len(page_two.json()["items"]) >= 1

    search = admin_client.get("/api/admin/users?q=search1&page=1&page_size=20")
    assert search.status_code == 200
    assert search.json()["total"] >= 6


def test_admin_cannot_disable_self(admin_client):
    me = admin_client.get("/api/auth/me").json()
    response = admin_client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False})
    assert response.status_code == 400


def test_duplicate_username_rejected_on_profile_update(user_client, client):
    created = client.post(
        "/api/auth/register",
        json={"username": "taken", "email": "taken@example.com", "password": "password123"},
    )
    assert created.status_code == 201

    response = user_client.patch("/api/users/me", json={"username": "taken"})
    assert response.status_code == 409