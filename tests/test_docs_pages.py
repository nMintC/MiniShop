def test_swagger_docs_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_openapi_json_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/products" in paths
    assert "/api/admin/products" in paths
    assert "/api/admin/products/{product_id}/image" in paths
    assert "/api/admin/users" in paths
    assert "/api/admin/customers" in paths
    assert "/api/admin/orders" in paths
    assert "/api/health" in paths
    assert "/api/auth/register" in paths
    assert "/api/auth/login" in paths


def test_login_and_register_pages_are_available(client):
    login = client.get("/login")
    register = client.get("/register")
    assert login.status_code == 200
    assert "Login" in login.text
    assert register.status_code == 200
    assert "Register" in register.text


def test_storefront_pages_require_customer_login(client):
    home = client.get("/", follow_redirects=False)
    products = client.get("/products", follow_redirects=False)
    detail = client.get("/products/1", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"] == "/login"
    assert products.status_code == 303
    assert products.headers["location"] == "/login"
    assert detail.status_code == 303
    assert detail.headers["location"] == "/login"


def test_storefront_pages_available_to_customer(user_client):
    home = user_client.get("/")
    products = user_client.get("/products")
    assert home.status_code == 200
    assert "Mini Shop" in home.text
    assert products.status_code == 200
    assert "Products" in products.text


def test_storefront_pages_redirect_admin_to_admin_dashboard(admin_client):
    home = admin_client.get("/", follow_redirects=False)
    products = admin_client.get("/products", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"] == "/admin/dashboard"
    assert products.status_code == 303
    assert products.headers["location"] == "/admin/dashboard"


def test_admin_can_open_store_preview(admin_client):
    home = admin_client.get("/?preview=store")
    products = admin_client.get("/products?preview=store")
    assert home.status_code == 200
    assert "Welcome to Mini Shop" in home.text
    assert products.status_code == 200
    assert "Products" in products.text


def test_login_page_stays_available_when_logged_in(admin_client):
    response = admin_client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text


def test_profile_requires_login(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_profile_page_available_to_user(user_client):
    response = user_client.get("/profile")
    assert response.status_code == 200
    assert "Profile" in response.text
    assert "Account Information" in response.text
    assert "Security" in response.text
    assert "open-password-button" in response.text
    assert "password-dialog-backdrop" in response.text
    assert "Current Password" in response.text
    assert "Confirm New Password" in response.text


def test_profile_redirects_admin_to_admin_dashboard(admin_client):
    response = admin_client.get("/profile", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"


def test_admin_pages_redirect_when_not_logged_in(client):
    dashboard = client.get("/admin/dashboard", follow_redirects=False)
    products = client.get("/admin/products", follow_redirects=False)
    customers = client.get("/admin/customers", follow_redirects=False)
    users = client.get("/admin/users", follow_redirects=False)
    orders = client.get("/admin/orders", follow_redirects=False)
    assert dashboard.status_code == 303
    assert dashboard.headers["location"] == "/login"
    assert products.status_code == 303
    assert products.headers["location"] == "/login"
    assert customers.status_code == 303
    assert customers.headers["location"] == "/login"
    assert users.status_code == 303
    assert users.headers["location"] == "/login"
    assert orders.status_code == 303
    assert orders.headers["location"] == "/login"


def test_admin_pages_redirect_normal_user(user_client):
    response = user_client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/profile"


def test_admin_pages_available_to_admin(admin_client):
    dashboard = admin_client.get("/admin/dashboard")
    products = admin_client.get("/admin/products")
    customers = admin_client.get("/admin/customers")
    legacy_users = admin_client.get("/admin/users", follow_redirects=False)
    orders = admin_client.get("/admin/orders")
    assert dashboard.status_code == 200
    assert "Welcome back" in dashboard.text
    assert "Total Customers" in dashboard.text
    assert "Low Stock" not in dashboard.text
    assert products.status_code == 200
    assert "Add Product" in products.text
    assert "Product Image" in products.text
    assert "Image URL" not in products.text
    assert 'maxlength="1000"' in products.text
    assert "description-counter" in products.text
    assert customers.status_code == 200
    assert "Customers" in customers.text
    assert legacy_users.status_code == 303
    assert legacy_users.headers["location"] == "/admin/customers"
    assert orders.status_code == 200
    assert "No orders have been created yet" in orders.text


def test_legacy_dashboard_redirects_to_admin_dashboard(admin_client):
    response = admin_client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"


def test_login_success_redirect_target_uses_role(client):
    response = client.get("/static/js/login.js")
    assert response.status_code == 200
    assert '"/admin/dashboard"' in response.text
    assert '"/"' in response.text


def test_storefront_nav_is_role_aware_for_admin(client):
    response = client.get("/static/js/shop.js")
    assert response.status_code == 200
    assert "Admin Dashboard" in response.text
    assert "/admin/dashboard" in response.text
    assert 'user.role === "admin"' in response.text


def test_admin_js_uses_customers_and_readable_error_messages(client):
    response = client.get("/static/js/admin.js")
    assert response.status_code == 200
    assert "/admin/customers" in response.text
    assert "/api/admin/customers" in response.text
    assert "[object Object]" not in response.text
    assert "item.msg" in response.text
    assert "productValidationMessage" in response.text
    assert "Description must be ${MAX_DESCRIPTION_LENGTH} characters or fewer." in response.text




def test_storefront_layout_uses_even_product_grids(client):
    js = client.get("/static/js/shop.js")
    css = client.get("/static/css/admin.css")
    assert js.status_code == 200
    assert css.status_code == 200
    assert "const HOME_PRODUCT_LIMIT = 8" in js.text
    assert "const PRODUCT_PAGE_SIZE = 12" in js.text
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in css.text
    assert ".store-shell > .content" in css.text
    assert "margin-top: auto" in css.text


def test_profile_page_uses_change_password_modal(client):
    js = client.get("/static/js/shop.js")
    assert js.status_code == 200
    assert "openPasswordDialog" in js.text
    assert "closePasswordDialog" in js.text
    assert "changePassword" in js.text
    assert "/api/users/me/password" in js.text
    assert "New password and confirmation do not match." in js.text



def test_products_page_uses_live_search_with_clear(user_client):
    page = user_client.get("/products")
    js = user_client.get("/static/js/shop.js")
    css = user_client.get("/static/css/admin.css")
    assert page.status_code == 200
    assert js.status_code == 200
    assert css.status_code == 200
    assert "clear-search-button" in page.text
    assert "id=\"search-button\"" not in page.text
    assert "PRODUCT_SEARCH_DEBOUNCE_MS" in js.text
    assert "scheduleLiveProductSearch" in js.text
    assert "commitProductSearch" in js.text
    assert "clearProductSearch" in js.text
    assert "window.history.replaceState" in js.text
    assert "body[data-page=\"products\"] .store-search" in css.text
    assert "product-description" in js.text
    assert "white-space: pre-wrap" in css.text
    assert "overflow-wrap: anywhere" in css.text

def test_admin_orders_api_placeholder(admin_client):
    response = admin_client.get("/api/admin/orders")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []