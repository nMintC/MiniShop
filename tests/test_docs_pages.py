def test_swagger_docs_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_openapi_json_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/products" in paths
    assert "/api/auth/login" in paths


def test_admin_pages_redirect_when_not_logged_in(client):
    home = client.get("/", follow_redirects=False)
    dashboard = client.get("/dashboard", follow_redirects=False)
    products = client.get("/products", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"] == "/login"
    assert dashboard.status_code == 303
    assert dashboard.headers["location"] == "/login"
    assert products.status_code == 303
    assert products.headers["location"] == "/login"


def test_dashboard_page_contains_product_management(auth_client):
    response = auth_client.get("/dashboard")
    assert response.status_code == 200
    assert "Total Products" in response.text
    assert "Total Quantity" in response.text
    assert "Products" in response.text
    assert "Add Product" in response.text
    assert "product-rows" in response.text
    assert 'href="/products"' not in response.text


def test_old_products_page_redirects_to_dashboard(auth_client):
    response = auth_client.get("/products", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_login_success_redirect_target_is_dashboard(client):
    response = client.get("/static/js/login.js")
    assert response.status_code == 200
    assert 'window.location.href = "/dashboard"' in response.text