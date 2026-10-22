"""W23: Locust load test against the k3d ingress (synthetic demo users only).

    make k3d-load                       # headless: 20 users, 3 min, writes loadtest/report.md
    uvx locust -f loadtest/locustfile.py --host http://localhost:8080   # web UI on :8089

Viewers poll the console's read APIs; operators also press Analyze site, which is the
CPU-heavy path that should make the copilot HPA scale from 1 to up to 3 replicas.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

SITES = [f"SITE-{i:03d}" for i in range(1, 15)]


class _Base(HttpUser):
    abstract = True
    username = "viewer"

    def on_start(self) -> None:
        password = os.getenv(f"LOAD_{self.username.upper()}_PASSWORD", self.username)
        r = self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": password},
            name="/api/auth/login",
        )
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['accessToken']}"


class Viewer(_Base):
    weight = 3
    wait_time = between(1, 3)
    username = "viewer"

    @task(4)
    def health(self) -> None:
        self.client.get("/health")

    @task(3)
    def alarms(self) -> None:
        self.client.get("/api/alarms/enriched/recent")

    @task(2)
    def incidents(self) -> None:
        self.client.get("/api/incidents")

    @task(1)
    def topology(self) -> None:
        self.client.get("/api/topology")


class Operator(_Base):
    weight = 1
    wait_time = between(0.5, 1.5)
    username = "operator"

    @task
    def analyze(self) -> None:
        self.client.post(
            "/api/copilot/analyze",
            json={"siteId": random.choice(SITES), "window": "30m"},
            name="/api/copilot/analyze",
        )
