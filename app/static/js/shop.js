const PLACEHOLDER_IMAGE = "/static/images/product-placeholder.png";
const HOME_PRODUCT_LIMIT = 8;
const PRODUCT_PAGE_SIZE = 12;
const PRODUCT_SEARCH_DEBOUNCE_MS = 250;
const MAX_SEARCH_LENGTH = 150;
const IS_STORE_PREVIEW = new URLSearchParams(window.location.search).get("preview") === "store";

function byId(id) {
    return document.getElementById(id);
}

function readableError(data, fallback = "Request failed") {
    if (!data || !data.detail) {
        return fallback;
    }
    if (typeof data.detail === "string") {
        return data.detail;
    }
    if (Array.isArray(data.detail)) {
        return data.detail.map((item) => {
            const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "field";
            if ((field === "q" || field === "search") && (item.type === "string_too_long" || String(item.msg || "").includes("at most 150"))) {
                return `Search must be ${MAX_SEARCH_LENGTH} characters or fewer.`;
            }
            return `${field}: ${item.msg}`;
        }).join("; ");
    }
    return fallback;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(readableError(data));
    }
    return data;
}

async function currentUser() {
    const response = await fetch("/api/auth/me");
    if (response.status === 401) {
        return null;
    }
    if (!response.ok) {
        return null;
    }
    return response.json();
}

async function logout(scope = "customer") {
    await fetch(`/api/auth/logout?scope=${scope}`, { method: "POST" });
    window.location.href = "/login";
}

function formatMoney(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "$0";
    }
    return Number.isInteger(number) ? `$${number.toLocaleString()}` : `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    })[char]);
}

function productDescription(value) {
    const text = value && String(value).trim() ? value : "No description available.";
    return escapeHtml(text);
}

function normalizeSearchQuery(value) {
    return String(value || "").trim().slice(0, MAX_SEARCH_LENGTH);
}

function storeHref(path = "/") {
    return IS_STORE_PREVIEW ? `${path}${path.includes("?") ? "&" : "?"}preview=store` : path;
}

function productsHref(q = "") {
    const params = new URLSearchParams();
    if (IS_STORE_PREVIEW) {
        params.set("preview", "store");
    }
    if (q) {
        params.set("q", q);
    }
    const query = params.toString();
    return query ? `/products?${query}` : "/products";
}

function imageUrl(product) {
    return product.image_url || PLACEHOLDER_IMAGE;
}

function stockText(product) {
    return product.in_stock ? "In stock" : "Out of stock";
}

function productCard(product) {
    const name = escapeHtml(product.name);
    const src = escapeHtml(imageUrl(product));
    return `
        <article class="product-card">
            <div class="product-image-wrap">
                <img src="${src}" alt="${name}" loading="lazy" onerror="this.src='${PLACEHOLDER_IMAGE}'">
            </div>
            <div class="product-card-body">
                <h2>${name}</h2>
                <strong>${formatMoney(product.price)}</strong>
                <div class="stock ${product.in_stock ? "in-stock" : "out-stock"}">${stockText(product)}</div>
                <a class="button-link secondary-link" href="${storeHref(`/products/${product.id}`)}">View Product</a>
            </div>
        </article>
    `;
}

async function renderNav(active) {
    const nav = byId("main-nav");
    if (!nav) {
        return null;
    }
    const user = await currentUser();
    const link = (href, text, key) => `<a class="${active === key ? "active" : ""}" href="${href}">${text}</a>`;
    let html = link(storeHref("/"), "Home", "home") + link(productsHref(), "Products", "products");
    if (user) {
        if (user.role === "admin") {
            html += link("/admin/dashboard", "Admin Dashboard", "admin");
        } else {
            html += link("/profile", "Profile", "profile");
        }
        html += `<button id="logout-button" class="secondary" type="button" data-scope="${user.role === "admin" ? "admin" : "customer"}">Logout</button>`;
    } else {
        html += link("/login", "Login", "login") + link("/register", "Register", "register");
    }
    nav.innerHTML = html;
    const logoutButton = byId("logout-button");
    if (logoutButton) {
        logoutButton.addEventListener("click", () => logout(logoutButton.dataset.scope || "customer"));
    }
    return user;
}

function bindGlobalSearch() {
    const form = byId("global-search");
    const input = byId("global-search-input");
    if (!form || !input) {
        return;
    }
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const q = normalizeSearchQuery(input.value);
        window.location.href = productsHref(q);
    });
}

async function loadHome() {
    await renderNav("home");
    bindGlobalSearch();
    const container = byId("home-products");
    const message = byId("page-message");
    try {
        message.textContent = "Loading products...";
        const data = await fetchJson(`/api/products?page=1&page_size=${HOME_PRODUCT_LIMIT}`);
        message.textContent = "";
        container.innerHTML = data.items.length ? data.items.map(productCard).join("") : '<div class="muted">No products yet.</div>';
    } catch (error) {
        message.textContent = error.message;
    }
}

let productState = { page: 1, pageSize: PRODUCT_PAGE_SIZE, q: normalizeSearchQuery(new URLSearchParams(window.location.search).get("q") || "") };
let productSearchTimer = null;
let productRequestId = 0;

function setProductsUrl(q) {
    window.history.replaceState({}, "", productsHref(normalizeSearchQuery(q)));
}

function updateClearSearchButton() {
    const button = byId("clear-search-button");
    if (button) {
        const input = byId("search-input");
        button.disabled = !productState.q && !(input && input.value.trim());
    }
}

async function loadProducts() {
    const requestId = ++productRequestId;
    const params = new URLSearchParams({ page: productState.page, page_size: productState.pageSize });
    if (productState.q) {
        params.set("q", productState.q);
    }
    const container = byId("product-list");
    const message = byId("page-message");
    try {
        message.textContent = "Loading products...";
        const data = await fetchJson(`/api/products?${params.toString()}`);
        if (requestId !== productRequestId) {
            return;
        }
        message.textContent = "";
        container.innerHTML = data.items.length ? data.items.map(productCard).join("") : '<div class="muted padded-panel">No products found.</div>';
        byId("summary").textContent = productState.q ? `${data.total} product(s) found for "${productState.q}"` : `${data.total} product(s) found`;
        byId("page-info").textContent = `Page ${data.page} of ${Math.max(data.total_pages, 1)}`;
        byId("prev-page").disabled = data.page <= 1;
        byId("next-page").disabled = data.total_pages === 0 || data.page >= data.total_pages;
        byId("search-input").value = productState.q;
        updateClearSearchButton();
    } catch (error) {
        if (requestId === productRequestId) {
            message.textContent = error.message;
        }
    }
}

async function loadProductDetail() {
    await renderNav("products");
    bindGlobalSearch();
    const id = window.location.pathname.split("/").filter(Boolean).pop();
    const panel = byId("product-detail");
    const message = byId("page-message");
    try {
        message.textContent = "Loading product...";
        const product = await fetchJson(`/api/products/${id}`);
        message.textContent = "";
        const name = escapeHtml(product.name);
        const src = escapeHtml(imageUrl(product));
        panel.innerHTML = `
            <div class="detail-image-wrap">
                <img src="${src}" alt="${name}" onerror="this.src='${PLACEHOLDER_IMAGE}'">
            </div>
            <div class="detail-copy">
                <h1>${name}</h1>
                <div class="detail-price">${formatMoney(product.price)}</div>
                <div class="stock ${product.in_stock ? "in-stock" : "out-stock"}">${stockText(product)}</div>
                <p class="product-description">${productDescription(product.description)}</p>
                <a class="button-link secondary-link" href="${productsHref()}">Back to Products</a>
            </div>
        `;
    } catch (error) {
        panel.innerHTML = "";
        message.textContent = error.message || "Product not found";
    }
}

async function register(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = byId("register-button");
    const message = byId("message");
    button.disabled = true;
    message.textContent = "";
    try {
        await fetchJson("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: form.username.value.trim(),
                email: form.email.value.trim(),
                password: form.password.value,
            }),
        });
        message.classList.add("success");
        message.textContent = "Registration successful. Redirecting to login...";
        setTimeout(() => { window.location.href = "/login"; }, 500);
    } catch (error) {
        message.classList.remove("success");
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

async function loadProfile() {
    const user = await renderNav("profile");
    bindGlobalSearch();
    if (!user) {
        window.location.href = "/login";
        return;
    }
    if (user.role === "admin") {
        window.location.href = "/admin/dashboard";
        return;
    }
    byId("username").value = user.username || "";
    byId("email").value = user.email;
}

async function saveProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = byId("message");
    try {
        await fetchJson("/api/users/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: form.username.value.trim() }),
        });
        message.classList.add("success");
        message.textContent = "Profile updated.";
        await renderNav("profile");
    } catch (error) {
        message.classList.remove("success");
        message.textContent = error.message;
    }
}

function openPasswordDialog() {
    byId("password-form").reset();
    byId("password-message").textContent = "";
    byId("password-message").classList.remove("success");
    byId("password-dialog-backdrop").classList.add("open");
    byId("current-password").focus();
}

function closePasswordDialog() {
    byId("password-dialog-backdrop").classList.remove("open");
    byId("password-form").reset();
    byId("password-message").textContent = "";
}

async function changePassword(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = byId("change-password-button");
    const message = byId("password-message");
    const securityMessage = byId("security-message");
    const newPassword = form.new_password.value;
    const confirmPassword = form.confirm_password.value;

    message.classList.remove("success");
    message.textContent = "";
    if (newPassword !== confirmPassword) {
        message.textContent = "New password and confirmation do not match.";
        return;
    }

    button.disabled = true;
    try {
        await fetchJson("/api/users/me/password", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                current_password: form.current_password.value,
                new_password: newPassword,
            }),
        });
        closePasswordDialog();
        securityMessage.classList.add("success");
        securityMessage.textContent = "Password changed successfully.";
    } catch (error) {
        message.classList.remove("success");
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

function bindProfileControls() {
    byId("profile-form").addEventListener("submit", saveProfile);
    byId("open-password-button").addEventListener("click", openPasswordDialog);
    byId("cancel-password-button").addEventListener("click", closePasswordDialog);
    byId("password-form").addEventListener("submit", changePassword);
}

function scheduleLiveProductSearch() {
    window.clearTimeout(productSearchTimer);
    productSearchTimer = window.setTimeout(() => {
        const nextQuery = normalizeSearchQuery(byId("search-input").value);
        productState.q = nextQuery;
        productState.page = 1;
        if (!nextQuery) {
            setProductsUrl("");
        }
        loadProducts();
    }, PRODUCT_SEARCH_DEBOUNCE_MS);
}

function commitProductSearch() {
    window.clearTimeout(productSearchTimer);
    productState.q = normalizeSearchQuery(byId("search-input").value);
    productState.page = 1;
    setProductsUrl(productState.q);
    loadProducts();
}

function clearProductSearch() {
    window.clearTimeout(productSearchTimer);
    productState.q = "";
    productState.page = 1;
    byId("search-input").value = "";
    setProductsUrl("");
    loadProducts();
    byId("search-input").focus();
}

function bindProductListControls() {
    const input = byId("search-input");
    input.value = productState.q;
    input.addEventListener("input", scheduleLiveProductSearch);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            commitProductSearch();
        }
    });
    byId("clear-search-button").addEventListener("click", clearProductSearch);
    byId("prev-page").addEventListener("click", () => {
        productState.page -= 1;
        loadProducts();
    });
    byId("next-page").addEventListener("click", () => {
        productState.page += 1;
        loadProducts();
    });
    updateClearSearchButton();
}

async function initProductsPage() {
    await renderNav("products");
    bindGlobalSearch();
    bindProductListControls();
    loadProducts();
}

const page = document.body.dataset.page;
if (page === "home") {
    loadHome();
}
if (page === "products") {
    initProductsPage();
}
if (page === "product-detail") {
    loadProductDetail();
}
if (page === "register") {
    byId("register-form").addEventListener("submit", register);
}
if (page === "profile") {
    bindProfileControls();
    loadProfile();
}