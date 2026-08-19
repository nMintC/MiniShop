def test_database_connection(client):
    response = client.get("/database-test")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_admin_login_success(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert "admin_session" in response.cookies


def test_admin_login_wrong_password(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_logout_removes_access(auth_client):
    logout = auth_client.post("/api/auth/logout")
    assert logout.status_code == 200
    response = auth_client.get("/api/products")
    assert response.status_code == 401


def test_unauthorized_access_is_rejected(client):
    response = client.get("/api/products")
    assert response.status_code == 401
