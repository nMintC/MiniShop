const PLACEHOLDER_IMAGE = "/static/images/product-placeholder.png";
const MAX_PRICE = 999999999;
const MAX_QUANTITY = 1000000;
const MAX_DESCRIPTION_LENGTH = 1000;
const MAX_SEARCH_LENGTH = 150;
let currentAdmin = null;
let productState = { page: 1, pageSize: 10, q: "", editingId: null, imageFile: null };
let customerState = { page: 1, pageSize: 10, q: "", selected: null };

function byId(id) {
    return document.getElementById(id);
}

function normalizeSearchQuery(value) {
    return String(value || "").trim().slice(0, MAX_SEARCH_LENGTH);
}


function productValidationMessage(field, item) {
    if (field === "description" && (item.type === "string_too_long" || String(item.msg || "").includes("at most 1000"))) {
        return `Description must be ${MAX_DESCRIPTION_LENGTH} characters or fewer.`;
    }
    if ((field === "q" || field === "search") && (item.type === "string_too_long" || String(item.msg || "").includes("at most 150"))) {
        return `Search must be ${MAX_SEARCH_LENGTH} characters or fewer.`;
    }
    return null;
}

function errorMessage(data, fallback = "Request failed") {
    if (!data || !data.detail) {
        return fallback;
    }
    if (typeof data.detail === "string") {
        return data.detail;
    }
    if (Array.isArray(data.detail)) {
        return data.detail.map((item) => {
            const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "field";
            return productValidationMessage(field, item) || `${field}: ${item.msg}`;
        }).join("; ");
    }
    return fallback;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required");
    }
    if (response.status === 403) {
        window.location.href = "/profile";
        throw new Error("Admin access required");
    }
    if (response.status === 204) {
        return null;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(errorMessage(data));
    }
    return data;
}

async function uploadImage(productId) {
    if (!productState.imageFile) {
        return null;
    }
    const formData = new FormData();
    formData.append("file", productState.imageFile);
    return fetchJson(`/api/admin/products/${productId}/image`, { method: "POST", body: formData });
}

async function ensureAdmin() {
    const user = await fetchJson("/api/auth/admin/me");
    if (user.role !== "admin") {
        window.location.href = "/profile";
        throw new Error("Admin access required");
    }
    currentAdmin = user;
    const adminName = byId("admin-name");
    if (adminName) {
        adminName.textContent = `${user.email} (${user.role})`;
    }
    renderAdminNav(document.body.dataset.adminPage);
    return user;
}

function renderAdminNav(active) {
    const nav = byId("admin-nav");
    if (!nav) {
        return;
    }
    const link = (href, text, key) => `<a class="${active === key ? "active" : ""}" href="${href}">${text}</a>`;
    nav.innerHTML =
        link("/admin/dashboard", "Dashboard", "dashboard") +
        link("/admin/orders", "Orders", "orders") +
        link("/admin/products", "Products", "products") +
        link("/admin/customers", "Customers", "customers") +
        '<div class="sidebar-spacer"></div>' +
        link("/?preview=store", "View Store", "shop") +
        '<button id="logout-button" class="secondary" type="button">Logout</button>';
    byId("logout-button").addEventListener("click", logout);
}

async function logout() {
    await fetch("/api/auth/logout?scope=admin", { method: "POST" });
    window.location.href = "/login";
}

function formatMoney(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "$0";
    }
    return Number.isInteger(number) ? `$${number.toLocaleString()}` : `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(value) {
    return value ? new Date(value).toLocaleString() : "";
}

function updateDescriptionCounter() {
    const counter = byId("description-counter");
    const description = byId("description");
    if (!counter || !description) {
        return;
    }
    counter.textContent = `${description.value.length} / ${MAX_DESCRIPTION_LENGTH}`;
    counter.classList.toggle("danger-text", description.value.length >= MAX_DESCRIPTION_LENGTH);
}

function validateProductForm() {
    const price = Number(byId("price").value);
    const quantity = Number(byId("quantity").value);
    const descriptionLength = byId("description").value.length;
    if (!Number.isFinite(price) || price < 0 || price > MAX_PRICE) {
        throw new Error("Price must be between $0 and $999,999,999.");
    }
    if (!Number.isInteger(quantity) || quantity < 0 || quantity > MAX_QUANTITY) {
        throw new Error("Quantity must be a whole number from 0 to 1,000,000.");
    }
    if (descriptionLength > MAX_DESCRIPTION_LENGTH) {
        throw new Error(`Description must be ${MAX_DESCRIPTION_LENGTH} characters or fewer.`);
    }
}

function productPayload() {
    validateProductForm();
    return {
        name: byId("name").value.trim(),
        sku: byId("sku").value.trim(),
        price: byId("price").value,
        quantity: Number(byId("quantity").value),
        description: byId("description").value.trim() || null,
    };
}

async function loadDashboard() {
    await ensureAdmin();
    const message = byId("page-message");
    try {
        const data = await fetchJson("/api/admin/dashboard");
        byId("welcome-name").textContent = data.admin.username || "Admin";
        byId("shop-status").textContent = data.shop_status || "Online";
        byId("total-revenue").textContent = formatMoney(data.total_revenue || 0);
        byId("total-products").textContent = data.total_products;
        byId("total-orders").textContent = data.total_orders;
        byId("total-customers").textContent = data.total_customers;
        byId("recent-orders").textContent = data.recent_orders.length ? "" : "No orders yet.";
    } catch (error) {
        message.textContent = error.message;
    }
}

function openDialog(product = null) {
    productState.editingId = product ? product.id : null;
    productState.imageFile = null;
    byId("dialog-title").textContent = product ? "Edit Product" : "Add Product";
    byId("name").value = product?.name || "";
    byId("sku").value = product?.sku || "";
    byId("price").value = product?.price || "";
    byId("quantity").value = product?.quantity ?? 0;
    byId("description").value = product?.description || "";
    updateDescriptionCounter();
    byId("image-file").value = "";
    byId("image-preview").src = product?.image_url || PLACEHOLDER_IMAGE;
    byId("form-message").textContent = "";
    byId("dialog-backdrop").classList.add("open");
    byId("name").focus();
}

function closeDialog() {
    byId("dialog-backdrop").classList.remove("open");
    productState.editingId = null;
    productState.imageFile = null;
}

async function loadAdminProducts() {
    await ensureAdmin();
    const params = new URLSearchParams({ page: productState.page, page_size: productState.pageSize });
    if (productState.q) {
        params.set("q", productState.q);
    }
    const data = await fetchJson(`/api/admin/products?${params.toString()}`);
    const rows = byId("product-rows");
    rows.innerHTML = "";

    for (const product of data.items) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><img class="admin-thumb" src="${product.image_url || PLACEHOLDER_IMAGE}" alt="${product.name}" onerror="this.src='${PLACEHOLDER_IMAGE}'"></td>
            <td>${product.sku}</td>
            <td>${product.name}</td>
            <td>${formatMoney(product.price)}</td>
            <td>${product.quantity}</td>
            <td>${product.quantity > 0 ? "In stock" : "Out of stock"}</td>
            <td>${formatDate(product.updated_at)}</td>
            <td><div class="actions">
                <button class="secondary" type="button" data-action="edit" data-id="${product.id}">Edit</button>
                <button class="danger" type="button" data-action="delete" data-id="${product.id}">Delete</button>
            </div></td>
        `;
        rows.appendChild(row);
    }

    if (data.items.length === 0) {
        rows.innerHTML = '<tr><td colspan="8" class="muted">No products found</td></tr>';
    }

    byId("summary").textContent = `${data.total} product(s)`;
    byId("page-info").textContent = `Page ${data.page} of ${Math.max(data.total_pages, 1)}`;
    byId("prev-page").disabled = data.page <= 1;
    byId("next-page").disabled = data.total_pages === 0 || data.page >= data.total_pages;
}

async function saveProduct(event) {
    event.preventDefault();
    const button = byId("save-button");
    const message = byId("form-message");
    button.disabled = true;
    message.textContent = "";
    const url = productState.editingId ? `/api/admin/products/${productState.editingId}` : "/api/admin/products";
    const method = productState.editingId ? "PUT" : "POST";
    try {
        const product = await fetchJson(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(productPayload()),
        });
        await uploadImage(product.id);
        closeDialog();
        await loadAdminProducts();
    } catch (error) {
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

async function editProduct(id) {
    const product = await fetchJson(`/api/admin/products/${id}`);
    openDialog(product);
}

async function deleteProduct(id) {
    if (!confirm("Are you sure you want to delete this product?")) {
        return;
    }
    await fetchJson(`/api/admin/products/${id}`, { method: "DELETE" });
    await loadAdminProducts();
}

function bindProductAdmin() {
    byId("add-button").addEventListener("click", () => openDialog());
    byId("cancel-button").addEventListener("click", closeDialog);
    byId("product-form").addEventListener("submit", saveProduct);
    byId("description").addEventListener("input", updateDescriptionCounter);
    byId("image-file").addEventListener("change", (event) => {
        const file = event.target.files[0];
        productState.imageFile = file || null;
        if (file) {
            byId("image-preview").src = URL.createObjectURL(file);
        }
    });
    byId("search-button").addEventListener("click", () => {
        productState.q = normalizeSearchQuery(byId("search-input").value);
        productState.page = 1;
        loadAdminProducts();
    });
    byId("search-input").addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            productState.q = normalizeSearchQuery(byId("search-input").value);
            productState.page = 1;
            loadAdminProducts();
        }
    });
    byId("prev-page").addEventListener("click", () => { productState.page -= 1; loadAdminProducts(); });
    byId("next-page").addEventListener("click", () => { productState.page += 1; loadAdminProducts(); });
    byId("product-rows").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const id = Number(button.dataset.id);
        if (button.dataset.action === "edit") editProduct(id);
        if (button.dataset.action === "delete") deleteProduct(id);
    });
}

async function loadCustomers() {
    await ensureAdmin();
    const params = new URLSearchParams({ page: customerState.page, page_size: customerState.pageSize });
    if (customerState.q) params.set("q", customerState.q);
    const data = await fetchJson(`/api/admin/customers?${params.toString()}`);
    const rows = byId("customer-rows");
    rows.innerHTML = "";
    for (const customer of data.items) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${customer.id}</td>
            <td>${customer.username || ""}</td>
            <td>${customer.email}</td>
            <td>${customer.is_active ? "Active" : "Disabled"}</td>
            <td>${formatDate(customer.created_at)}</td>
            <td>0</td>
            <td><div class="actions">
                <button class="secondary" type="button" data-action="view" data-id="${customer.id}">View</button>
                <button class="${customer.is_active ? "danger" : "secondary"}" type="button" data-action="toggle" data-id="${customer.id}" data-active="${customer.is_active}">${customer.is_active ? "Disable" : "Enable"}</button>
            </div></td>
        `;
        rows.appendChild(row);
    }
    if (data.items.length === 0) {
        rows.innerHTML = '<tr><td colspan="7" class="muted">No customers found</td></tr>';
    }
    byId("summary").textContent = `${data.total} customer(s)`;
    byId("page-info").textContent = `Page ${data.page} of ${Math.max(data.total_pages, 1)}`;
    byId("prev-page").disabled = data.page <= 1;
    byId("next-page").disabled = data.total_pages === 0 || data.page >= data.total_pages;
}

async function viewCustomer(id) {
    const data = await fetchJson(`/api/admin/customers/${id}`);
    const customer = data.customer;
    customerState.selected = customer;
    byId("customer-dialog-title").textContent = `Customer #${customer.id}`;
    byId("customer-detail").innerHTML = `
        <div><strong>Username</strong><div>${customer.username || ""}</div></div>
        <div><strong>Email</strong><div>${customer.email}</div></div>
        <div><strong>Status</strong><div>${customer.is_active ? "Active" : "Disabled"}</div></div>
        <div><strong>Registered</strong><div>${formatDate(customer.created_at)}</div></div>
        <div><strong>Orders</strong><div>${data.orders_count}</div><p class="muted">Order history will appear after checkout is implemented.</p></div>
    `;
    byId("customer-status-button").textContent = customer.is_active ? "Disable Account" : "Enable Account";
    byId("customer-status-button").className = customer.is_active ? "danger" : "secondary";
    byId("customer-message").textContent = "";
    byId("customer-dialog-backdrop").classList.add("open");
}

function closeCustomerDialog() {
    byId("customer-dialog-backdrop").classList.remove("open");
    customerState.selected = null;
}

async function toggleCustomer(id, isActive) {
    const message = byId("page-message") || byId("customer-message");
    try {
        await fetchJson(`/api/admin/customers/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !isActive }),
        });
        if (message) message.textContent = "";
        await loadCustomers();
        if (customerState.selected?.id === id) {
            closeCustomerDialog();
        }
    } catch (error) {
        if (message) message.textContent = error.message;
    }
}

function bindCustomers() {
    byId("search-button").addEventListener("click", () => {
        customerState.q = normalizeSearchQuery(byId("search-input").value);
        customerState.page = 1;
        loadCustomers();
    });
    byId("search-input").addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            customerState.q = normalizeSearchQuery(byId("search-input").value);
            customerState.page = 1;
            loadCustomers();
        }
    });
    byId("prev-page").addEventListener("click", () => { customerState.page -= 1; loadCustomers(); });
    byId("next-page").addEventListener("click", () => { customerState.page += 1; loadCustomers(); });
    byId("customer-close-button").addEventListener("click", closeCustomerDialog);
    byId("customer-status-button").addEventListener("click", () => {
        if (customerState.selected) toggleCustomer(customerState.selected.id, customerState.selected.is_active);
    });
    byId("customer-rows").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const id = Number(button.dataset.id);
        if (button.dataset.action === "view") viewCustomer(id);
        if (button.dataset.action === "toggle") toggleCustomer(id, button.dataset.active === "true");
    });
}

async function loadAdminOrders() {
    await ensureAdmin();
    const message = byId("page-message");
    try {
        await fetchJson("/api/admin/orders");
        message.textContent = "";
    } catch (error) {
        message.textContent = error.message;
    }
}

const page = document.body.dataset.adminPage;
if (page === "dashboard") loadDashboard();
if (page === "products") { bindProductAdmin(); loadAdminProducts(); }
if (page === "customers") { bindCustomers(); loadCustomers(); }
if (page === "orders") loadAdminOrders();