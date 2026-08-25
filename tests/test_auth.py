from tests.conftest import create_inactive_user, register_payload


def test_database_connection(client):
    response = client.get("/database-test")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_register_success(client):
    response = client.post("/api/auth/register", json=register_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "user"
    assert "password_hash" not in data["user"]


def test_register_duplicate_username(client):
    assert client.post("/api/auth/register", json=register_payload()).status_code == 201
    response = client.post("/api/auth/register", json=register_payload(email="alice2@example.com"))
    assert response.status_code == 409


def test_register_duplicate_email(client):
    assert client.post("/api/auth/register", json=register_payload()).status_code == 201
    response = client.post("/api/auth/register", json=register_payload(username="alice2"))
    assert response.status_code == 409


def test_admin_login_success(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
    assert response.json()["user"]["role"] == "admin"
    assert "admin_session" in response.cookies
    assert "shop_session" not in response.cookies


def test_login_wrong_password(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post("/api/auth/login", json={"username": "missing", "password": "password123"})
    assert response.status_code == 401


def test_inactive_user_cannot_login(client):
    create_inactive_user()
    response = client.post("/api/auth/login", json={"username": "inactive", "password": "password123"})
    assert response.status_code == 403


def test_get_me_authenticated(admin_client):
    response = admin_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_get_me_unauthenticated(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout_invalidates_session(admin_client):
    logout = admin_client.post("/api/auth/logout")
    assert logout.status_code == 200
    response = admin_client.get("/api/auth/me")
    assert response.status_code == 401


def test_anonymous_cannot_access_protected_endpoint(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_user_cannot_access_admin_endpoint(user_client):
    response = user_client.get("/api/admin/users")
    assert response.status_code == 403


def test_admin_can_access_admin_endpoint(admin_client):
    response = admin_client.get("/api/admin/users")
    assert response.status_code == 200

def test_default_admin_can_login_by_email(client):
    admin_login = client.post("/api/auth/login", json={"username": "admin@minishop.local", "password": "Admin123!"})
    assert admin_login.status_code == 200
    assert admin_login.json()["user"]["role"] == "admin"

def test_customer_login_uses_customer_session_cookie(client):
    assert client.post("/api/auth/register", json=register_payload()).status_code == 201
    response = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "user"
    assert "shop_session" in response.cookies
    assert "admin_session" not in response.cookies


def test_admin_and_customer_sessions_can_coexist(client):
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert admin_login.status_code == 200
    assert "admin_session" in client.cookies

    assert client.post("/api/auth/register", json=register_payload(username="shopper", email="shopper@example.com")).status_code == 201
    customer_login = client.post("/api/auth/login", json={"username": "shopper", "password": "password123"})
    assert customer_login.status_code == 200
    assert "shop_session" in client.cookies
    assert "admin_session" in client.cookies

    storefront_me = client.get("/api/auth/me")
    assert storefront_me.status_code == 200
    assert storefront_me.json()["username"] == "shopper"
    assert storefront_me.json()["role"] == "user"

    admin_me = client.get("/api/auth/admin/me")
    assert admin_me.status_code == 200
    assert admin_me.json()["username"] == "admin"
    assert admin_me.json()["role"] == "admin"

    assert client.get("/profile", follow_redirects=False).status_code == 200
    assert client.get("/admin/dashboard", follow_redirects=False).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 200


def test_scoped_logout_keeps_the_other_role_session(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).status_code == 200
    assert client.post("/api/auth/register", json=register_payload(username="shopper", email="shopper@example.com")).status_code == 201
    assert client.post("/api/auth/login", json={"username": "shopper", "password": "password123"}).status_code == 200

    customer_logout = client.post("/api/auth/logout?scope=customer")
    assert customer_logout.status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "admin"
    assert client.get("/api/auth/admin/me").status_code == 200

    admin_logout = client.post("/api/auth/logout?scope=admin")
    assert admin_logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/admin/me").status_code == 401