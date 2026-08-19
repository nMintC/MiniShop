from __future__ import annotations

import os
import random
from uuid import uuid4

from locust import HttpUser, between, task
from requests import Response

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME

READ_PAGES = [1, 2, 3, 4, 5]
SEARCH_TERMS = ["SEED", "Product", "Demo", "Smoke", "Load"]


class AdminUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.product_ids: list[int] = []
        username = os.getenv("LOCUST_ADMIN_USERNAME", ADMIN_USERNAME)
        password = os.getenv("LOCUST_ADMIN_PASSWORD", ADMIN_PASSWORD)

        with self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            name="POST /api/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Login failed: {response.status_code} {response.text[:120]}")

    def remember_product_ids(self, response: Response) -> None:
        try:
            data = response.json()
        except ValueError as exc:
            response.failure(f"Invalid product list JSON: {exc}")
            return

        items = data.get("items", [])
        ids = [
            item.get("id")
            for item in items
            if isinstance(item.get("id"), int) and not str(item.get("sku", "")).startswith("LOAD-")
        ]
        if ids:
            self.product_ids = ids

    def load_product_page(self, page: int | None = None) -> Response:
        selected_page = page or random.choice(READ_PAGES)
        with self.client.get(
            f"/api/products?page={selected_page}&page_size=20",
            name="GET /api/products?page",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"List products failed: {response.status_code} {response.text[:120]}")
            else:
                self.remember_product_ids(response)
            return response

    @task(8)
    def dashboard_stats(self) -> None:
        with self.client.get("/api/dashboard", name="GET /api/dashboard", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Dashboard failed: {response.status_code} {response.text[:120]}")

    @task(12)
    def list_products(self) -> None:
        self.load_product_page()

    @task(6)
    def search_products(self) -> None:
        term = random.choice(SEARCH_TERMS)
        with self.client.get(
            f"/api/products?q={term}&page=1&page_size=20",
            name="GET /api/products?q",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Search failed: {response.status_code} {response.text[:120]}")
            else:
                self.remember_product_ids(response)

    @task(5)
    def product_detail(self) -> None:
        if not self.product_ids:
            self.load_product_page(page=1)
            if not self.product_ids:
                return

        product_id = random.choice(self.product_ids)
        with self.client.get(
            f"/api/products/{product_id}",
            name="GET /api/products/{id}",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Product detail failed: {response.status_code} {response.text[:120]}")

    @task(1)
    def create_update_delete_product(self) -> None:
        unique = uuid4().hex[:12].upper()
        payload = {
            "name": f"Load Test Product {unique}",
            "description": "Created and deleted by Locust write flow",
            "sku": f"LOAD-{unique}",
            "price": "9.99",
            "quantity": random.randint(1, 50),
        }

        with self.client.post(
            "/api/products",
            json=payload,
            name="POST /api/products",
            catch_response=True,
        ) as create_response:
            if create_response.status_code != 201:
                create_response.failure(
                    f"Create failed: {create_response.status_code} {create_response.text[:120]}"
                )
                return
            try:
                product_id = create_response.json()["id"]
            except (KeyError, ValueError, TypeError) as exc:
                create_response.failure(f"Create returned invalid product JSON: {exc}")
                return

        update_payload = {"quantity": random.randint(1, 50)}
        with self.client.patch(
            f"/api/products/{product_id}",
            json=update_payload,
            name="PATCH /api/products/{id}",
            catch_response=True,
        ) as update_response:
            if update_response.status_code != 200:
                update_response.failure(
                    f"Patch failed: {update_response.status_code} {update_response.text[:120]}"
                )

        with self.client.delete(
            f"/api/products/{product_id}",
            name="DELETE /api/products/{id}",
            catch_response=True,
        ) as delete_response:
            if delete_response.status_code != 204:
                delete_response.failure(
                    f"Delete failed: {delete_response.status_code} {delete_response.text[:120]}"
                )