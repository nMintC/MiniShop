let state = {
    page: 1,
    pageSize: 10,
    q: "",
    editingId: null,
};

function byId(id) {
    return document.getElementById(id);
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required");
    }
    return response;
}

async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
}

function formatMoney(value) {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function productPayload() {
    return {
        name: byId("name").value.trim(),
        sku: byId("sku").value.trim(),
        price: byId("price").value,
        quantity: Number(byId("quantity").value),
        description: byId("description").value.trim() || null,
    };
}

async function loadStats() {
    const response = await apiFetch("/api/dashboard");
    const data = await response.json();
    byId("admin-name").textContent = `Signed in as ${data.admin.username}`;
    byId("total-products").textContent = data.total_products;
    byId("total-quantity").textContent = data.total_quantity;
}

function openDialog(product = null) {
    state.editingId = product ? product.id : null;
    byId("dialog-title").textContent = product ? "Edit Product" : "Add Product";
    byId("name").value = product?.name || "";
    byId("sku").value = product?.sku || "";
    byId("price").value = product?.price || "";
    byId("quantity").value = product?.quantity ?? 0;
    byId("description").value = product?.description || "";
    byId("form-message").textContent = "";
    byId("dialog-backdrop").classList.add("open");
    byId("name").focus();
}

function closeDialog() {
    byId("dialog-backdrop").classList.remove("open");
    state.editingId = null;
}

async function loadProducts() {
    const params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
    if (state.q) {
        params.set("q", state.q);
    }

    const response = await apiFetch(`/api/products?${params.toString()}`);
    const data = await response.json();
    const rows = byId("product-rows");
    rows.innerHTML = "";

    for (const product of data.items) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${product.id}</td>
            <td>${product.name}</td>
            <td>${product.sku}</td>
            <td>${formatMoney(product.price)}</td>
            <td>${product.quantity}</td>
            <td>
                <div class="actions">
                    <button class="secondary" type="button" data-action="edit" data-id="${product.id}">Edit</button>
                    <button class="danger" type="button" data-action="delete" data-id="${product.id}">Delete</button>
                </div>
            </td>
        `;
        rows.appendChild(row);
    }

    if (data.items.length === 0) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="6" class="muted">No products found</td>`;
        rows.appendChild(row);
    }

    byId("summary").textContent = `${data.total} product(s) shown for current filter`;
    byId("page-info").textContent = `Page ${data.page} of ${Math.max(data.total_pages, 1)}`;
    byId("prev-page").disabled = data.page <= 1;
    byId("next-page").disabled = data.total_pages === 0 || data.page >= data.total_pages;
}

async function refreshDashboard() {
    await Promise.all([loadStats(), loadProducts()]);
}

async function saveProduct(event) {
    event.preventDefault();
    const button = byId("save-button");
    const message = byId("form-message");
    button.disabled = true;
    message.textContent = "";

    const url = state.editingId ? `/api/products/${state.editingId}` : "/api/products";
    const method = state.editingId ? "PUT" : "POST";

    try {
        const response = await apiFetch(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(productPayload()),
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "Save failed");
        }

        closeDialog();
        await refreshDashboard();
    } catch (error) {
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

async function editProduct(id) {
    const response = await apiFetch(`/api/products/${id}`);
    if (!response.ok) {
        return;
    }
    openDialog(await response.json());
}

async function deleteProduct(id) {
    if (!confirm("Are you sure you want to delete this product?")) {
        return;
    }

    const response = await apiFetch(`/api/products/${id}`, { method: "DELETE" });
    if (response.ok) {
        await refreshDashboard();
    }
}

byId("logout-button").addEventListener("click", logout);
byId("add-button").addEventListener("click", () => openDialog());
byId("cancel-button").addEventListener("click", closeDialog);
byId("product-form").addEventListener("submit", saveProduct);
byId("search-button").addEventListener("click", () => {
    state.q = byId("search-input").value.trim();
    state.page = 1;
    loadProducts();
});
byId("search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        state.q = byId("search-input").value.trim();
        state.page = 1;
        loadProducts();
    }
});
byId("prev-page").addEventListener("click", () => {
    state.page -= 1;
    loadProducts();
});
byId("next-page").addEventListener("click", () => {
    state.page += 1;
    loadProducts();
});
byId("product-rows").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) {
        return;
    }
    const id = Number(button.dataset.id);
    if (button.dataset.action === "edit") {
        editProduct(id);
    }
    if (button.dataset.action === "delete") {
        deleteProduct(id);
    }
});

refreshDashboard().catch(() => {});