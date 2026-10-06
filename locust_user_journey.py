from __future__ import annotations

import os
import random
from collections import Counter

from locust import HttpUser, between, events, task

from app.config import DEV_USER_PASSWORD, DEV_USER_USERNAME

SEARCH_TERMS = [term.strip() for term in os.getenv("LOCUST_SEARCH_TERMS", "shirt,jacket,pants,dress,black,white").split(",") if term.strip()]
CACHE_STATUS_COUNTS: Counter[str] = Counter()


def record_cache_status(response) -> None:
    CACHE_STATUS_COUNTS[response.headers.get("X-Cache", "NO_HEADER")] += 1


@events.test_stop.add_listener
def print_cache_summary(environment, **kwargs) -> None:
    total = sum(CACHE_STATUS_COUNTS.values())
    if not total:
        return
    print("\nCache status summary for locust_user_journey.py")
    for status, count in sorted(CACHE_STATUS_COUNTS.items()):
        print(f"  {status}: {count} ({count / total * 100:.1f}%)")


class CustomerJourneyUser(HttpUser):
    wait_time = between(0.3, 1.2)

    def on_start(self) -> None:
        self.product_ids: list[int] = []
        self.logged_in = False
        username = os.getenv("LOCUST_USER_USERNAME", DEV_USER_USERNAME)
        password = os.getenv("LOCUST_USER_PASSWORD", DEV_USER_PASSWORD)

        with self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            name="POST /api/auth/login customer",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.logged_in = True
                return
            response.failure(
                f"Customer login failed: {response.status_code} {response.text[:120]}. "
                "Create the customer first or set LOCUST_USER_USERNAME/LOCUST_USER_PASSWORD."
            )

    def remember_product_ids(self, response) -> None:
        try:
            data = response.json()
        except ValueError:
            return
        ids = [item.get("id") for item in data.get("items", []) if isinstance(item.get("id"), int)]
        if ids:
            self.product_ids = ids

    @task(50)
    def browse_product_list(self) -> None:
        page = random.randint(1, 3)
        with self.client.get(
            f"/api/products?page={page}&page_size=20",
            name="GET /api/products list",
            catch_response=True,
        ) as response:
            record_cache_status(response)
            if response.status_code != 200:
                response.failure(f"Product list failed: {response.status_code} {response.text[:120]}")
                return
            self.remember_product_ids(response)

    @task(30)
    def open_product_detail(self) -> None:
        if not self.product_ids:
            self.browse_product_list()
            if not self.product_ids:
                return
        product_id = random.choice(self.product_ids)
        with self.client.get(
            f"/api/products/{product_id}",
            name="GET /api/products/[id] detail",
            catch_response=True,
        ) as response:
            record_cache_status(response)
            if response.status_code != 200:
                response.failure(f"Product detail failed: {response.status_code} {response.text[:120]}")

    @task(15)
    def search_products(self) -> None:
        term = random.choice(SEARCH_TERMS)
        with self.client.get(
            f"/api/products?q={term}&page=1&page_size=20",
            name="GET /api/products search",
            catch_response=True,
        ) as response:
            record_cache_status(response)
            if response.status_code != 200:
                response.failure(f"Search failed: {response.status_code} {response.text[:120]}")
                return
            self.remember_product_ids(response)

    @task(5)
    def profile(self) -> None:
        if not self.logged_in:
            return
        with self.client.get("/api/users/me", name="GET /api/users/me profile", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Profile failed: {response.status_code} {response.text[:120]}")
