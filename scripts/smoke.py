"""W12 Phase 1 smoke test: the fibre_cut demo path, checked through the gateway only.

health -> login -> alarms -> timeline -> KPI anomaly -> fault -> runbooks -> copilot (cited)
-> RBAC (no token = 401). Synthetic data only; the token and password are never printed.
Usage: bash scripts/smoke.sh [--base-url URL] [--user operator] [--wait 120] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    ms: int


class Smoke:
    def __init__(
        self,
        client: httpx.Client,
        user: str = "operator",
        password: str | None = None,
        wait_s: float = 120.0,
        poll_s: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        console_url: str | None = None,
    ) -> None:
        self.client = client
        self.console_url = console_url.rstrip("/") if console_url else None
        self.user = user
        self.password = password if password is not None else user
        self.wait_s = wait_s
        self.poll_s = poll_s
        self.sleep = sleep
        self.clock = clock
        self.checks: list[Check] = []
        self.token: str | None = None
        self.alarm: dict[str, Any] | None = None
        self.fault_type: str | None = None
        self.admin_token: str | None = None
        self._tokens: dict[str, str] = {}  # reuse one token per user (fewer logins)
        self.login_waits = 0

    def _run(self, name: str, fn: Callable[[], str]) -> None:
        start = self.clock()
        try:
            detail = fn()
            ok = True
        except Exception as e:
            ok = False
            first_line = (str(e).splitlines() or [""])[0]
            detail = f"{type(e).__name__}: {first_line}"
            if len(detail) > 200:
                detail = detail[:200]
        ms = int((self.clock() - start) * 1000)
        self.checks.append(Check(name=name, ok=ok, detail=detail, ms=ms))

    def _auth_headers(self) -> dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def _poll(self, fetch: Callable[[], list[Any]], what: str) -> list[Any]:
        """Call ``fetch`` until it returns a non-empty list; always tries at least once."""
        deadline = self.clock() + self.wait_s
        while True:
            items = fetch()
            if items:
                return items
            if self.clock() >= deadline:
                raise RuntimeError(f"no {what} within {self.wait_s:.0f}s")
            self.sleep(self.poll_s)

    def _get_json(self, path: str, **params: Any) -> Any:
        resp = self.client.get(path, params=params or None, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    def step_health(self) -> str:
        """Every service in /health is up; polls within --wait (services may still be starting)."""
        deadline = self.clock() + self.wait_s
        while True:
            resp = self.client.get("/health")
            resp.raise_for_status()
            services = resp.json().get("services", [])
            down = [s.get("name", "?") for s in services if s.get("status") != "up"]
            if not down:
                return f"{len(services)} services up"
            if self.clock() >= deadline:
                raise RuntimeError(f"services down: {', '.join(down)}")
            self.sleep(self.poll_s)

    # The gateway allows LOGIN_RATE_PER_MIN (10) logins per IP per minute. Smoke logs in a few
    # times (roles + password checks), so it reuses tokens and backs off on 429 (fix 2).
    LOGIN_MAX_WAIT_S = float(os.environ.get("SMOKE_LOGIN_MAX_WAIT", "75"))

    def _login(self, user: str, password: str) -> httpx.Response:
        """POST /api/auth/login; on 429 sleep Retry-After (1-65 s), bounded by LOGIN_MAX_WAIT_S."""
        waited = 0.0
        while True:
            resp = self.client.post(
                "/api/auth/login", json={"username": user, "password": password}
            )
            if resp.status_code != 429:
                return resp
            try:
                retry = float(resp.headers.get("Retry-After", "5"))
            except ValueError:
                retry = 5.0
            retry = min(max(retry, 1.0), 65.0)
            if waited + retry > self.LOGIN_MAX_WAIT_S:
                return resp
            self.sleep(retry)
            waited += retry
            self.login_waits += 1

    def step_login(self) -> str:
        resp = self._login(self.user, self.password)
        resp.raise_for_status()
        body = resp.json()
        self.token = body.get("accessToken")
        if not self.token:
            raise RuntimeError("no accessToken in response")
        self._tokens[self.user] = self.token
        return "logged in"

    def step_alarms(self) -> str:
        alarms = self._poll(lambda: list(self._get_json("/api/alarms/enriched/recent")), "alarms")
        roots = [a for a in alarms if (a.get("correlation") or {}).get("role") == "root"]
        self.alarm = roots[-1] if roots else alarms[-1]
        return f"{len(alarms)} alarms"

    def step_timeline(self) -> str:
        if not self.token:
            raise RuntimeError("no token")
        resp = self.client.get("/api/alarms/timeline", headers=self._auth_headers())
        resp.raise_for_status()
        body = resp.json()
        total = body.get("total", 0)
        peak = body.get("peak", 0)
        if total <= 0 or peak <= 0:
            raise RuntimeError(f"timeline total={total} peak={peak}")
        return f"total={total} peak={peak}"

    def step_kpi_anomaly(self) -> str:
        def fetch() -> list[Any]:
            body = self._get_json("/api/ml/anomalies", kpi="dlThroughputMbps", hours=24, limit=20)
            return list(body.get("items", []))

        items = self._poll(fetch, "KPI anomalies")
        return f"{len(items)} anomalies"

    def step_fault(self) -> str:
        if not self.token:
            raise RuntimeError("no token")
        if not self.alarm:
            raise RuntimeError("no alarm")
        resp = self.client.post(
            "/api/ml/predict",
            json={"alarm": self.alarm},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        fault_type = body.get("faultType")
        if not fault_type:
            raise RuntimeError("no faultType in response")
        self.fault_type = fault_type
        return f"faultType={fault_type}"

    def step_runbooks(self) -> str:
        if not self.token:
            raise RuntimeError("no token")
        if not self.alarm:
            raise RuntimeError("no alarm")
        if not self.fault_type:
            raise RuntimeError("no fault_type")
        query = (
            f"{self.alarm.get('specificProblem', '')} {self.alarm.get('probableCause', '')}".strip()
        )
        resp = self.client.post(
            "/api/rag/search",
            json={"query": query, "top_k": 3, "faultType": self.fault_type},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            raise RuntimeError("no runbook results")
        ids = []
        for r in results:
            rid = r.get("runbookId") or r.get("id")
            if rid:
                ids.append(str(rid))
        return f"ids={','.join(ids)}"

    def step_copilot(self) -> str:
        if not self.token:
            raise RuntimeError("no token")
        if not self.alarm:
            raise RuntimeError("no alarm")
        corr = self.alarm.get("correlation") or {}
        root_site_id = corr.get("rootSiteId") or self.alarm.get("siteId")
        if not root_site_id:
            raise RuntimeError("no root site id")
        resp = self.client.post(
            "/api/copilot/analyze",
            json={"siteId": root_site_id, "window": "120m"},
            headers=self._auth_headers(),
            timeout=120.0,
        )
        resp.raise_for_status()
        body = resp.json()
        source_ids = body.get("sourceIds", [])
        if not source_ids:
            raise RuntimeError("no sourceIds")
        answer = body.get("answer", {})
        steps = answer.get("steps", [])
        cited_ids: set[str] = set()
        for step in steps:
            rid = step.get("runbookId")
            if rid:
                cited_ids.add(str(rid))
        if not cited_ids:
            raise RuntimeError("no runbook citations in answer")
        if not cited_ids & {str(i) for i in source_ids}:
            raise RuntimeError("cited runbooks are not in sourceIds")
        generated_by = body.get("generatedBy", "unknown")
        return f"{generated_by}, {len(source_ids)} sources"

    def step_rbac(self) -> str:
        resp = self.client.get("/api/alarms/timeline")
        if resp.status_code != 401:
            raise RuntimeError(f"expected 401, got {resp.status_code}")
        return "401 as expected"

    # --- Step 13b: server-side RBAC per role and the password-change flow ------------------

    def _login_as(self, user: str, password: str, reuse: bool = True) -> str:
        if reuse and user in self._tokens:
            return self._tokens[user]
        resp = self._login(user, password)
        if resp.status_code != 200:
            raise RuntimeError(f"login as {user} returned {resp.status_code}")
        token = str(resp.json()["accessToken"])
        if reuse:
            self._tokens[user] = token
        return token

    @staticmethod
    def _bearer(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def step_roles(self) -> str:
        """Viewer cannot act on incidents, operator cannot manage users, admin can (all 403s)."""
        viewer = self._login_as("viewer", os.environ.get("SMOKE_VIEWER_PASSWORD", "viewer"))
        r = self.client.post(
            "/api/incidents/INC-0000000000/actions",
            json={"action": "ack"},
            headers=self._bearer(viewer),
        )
        if r.status_code != 403:
            raise RuntimeError(f"viewer incident action: expected 403, got {r.status_code}")
        operator = self._login_as("operator", os.environ.get("SMOKE_OPERATOR_PASSWORD", "operator"))
        r = self.client.get("/api/admin/users", headers=self._bearer(operator))
        if r.status_code != 403:
            raise RuntimeError(f"operator admin view: expected 403, got {r.status_code}")
        self.admin_token = self._login_as("admin", os.environ.get("SMOKE_ADMIN_PASSWORD", "admin"))
        r = self.client.get("/api/admin/users", headers=self._bearer(self.admin_token))
        if r.status_code != 200:
            raise RuntimeError(f"admin user list: expected 200, got {r.status_code}")
        return "viewer 403 on actions, operator 403 on admin, admin 200"

    def step_password(self) -> str:
        """A throwaway user changes its password: the old token is revoked, then it is disabled."""
        if not self.admin_token:
            raise RuntimeError("no admin token (roles check failed)")
        admin = self._bearer(self.admin_token)
        name = f"smoke.{secrets.token_hex(3)}"
        first, second = (f"Sm0ke-{secrets.token_urlsafe(12)}!" for _ in range(2))
        r = self.client.post(
            "/api/admin/users",
            json={"username": name, "role": "viewer", "password": first},
            headers=admin,
        )
        if r.status_code != 201:
            raise RuntimeError(f"create user returned {r.status_code}")
        try:
            old = self._login_as(name, first, reuse=False)
            r = self.client.post(
                "/api/auth/password",
                json={"currentPassword": first, "newPassword": second},
                headers=self._bearer(old),
            )
            if r.status_code != 200:
                raise RuntimeError(f"password change returned {r.status_code}")
            new = str(r.json()["accessToken"])
            if self.client.get("/api/auth/me", headers=self._bearer(old)).status_code != 401:
                raise RuntimeError("old token still works after the change")
            if self.client.get("/api/auth/me", headers=self._bearer(new)).status_code != 200:
                raise RuntimeError("new token rejected")
            r = self._login(name, first)
            if r.status_code != 401:
                raise RuntimeError(f"old password still accepted ({r.status_code})")
        finally:
            self.client.patch(f"/api/admin/users/{name}", json={"disabled": True}, headers=admin)
        return "changed; old token revoked; throwaway user disabled"

    def step_console(self) -> str:
        """The dashboard container serves the SPA and proxies /health to the gateway."""
        page = self.client.get(f"{self.console_url}/")
        if page.status_code != 200:
            raise RuntimeError(f"dashboard returned {page.status_code}")
        if 'id="root"' not in page.text:
            raise RuntimeError("dashboard page has no #root element")
        proxied = self.client.get(f"{self.console_url}/health")
        if proxied.status_code != 200:
            raise RuntimeError(f"dashboard /health proxy returned {proxied.status_code}")
        return f"200 at {self.console_url} (proxy ok)"

    def run(self) -> bool:
        self._run("health", self.step_health)
        if self.console_url:
            self._run("console", self.step_console)
        self._run("login", self.step_login)

        if not self.token:
            for name in ("alarms", "timeline", "kpi_anomaly", "fault", "runbooks", "copilot"):
                self.checks.append(Check(name=name, ok=False, detail="skipped: no token", ms=0))
        else:
            self._run("alarms", self.step_alarms)
            self._run("timeline", self.step_timeline)
            self._run("kpi_anomaly", self.step_kpi_anomaly)

            if not self.alarm:
                for name in ("fault", "runbooks", "copilot"):
                    self.checks.append(Check(name=name, ok=False, detail="skipped: no alarm", ms=0))
            else:
                self._run("fault", self.step_fault)

                if not self.fault_type:
                    for name in ("runbooks", "copilot"):
                        self.checks.append(
                            Check(name=name, ok=False, detail="skipped: no fault_type", ms=0)
                        )
                else:
                    self._run("runbooks", self.step_runbooks)
                    self._run("copilot", self.step_copilot)

        self._run("rbac", self.step_rbac)
        self._run("roles", self.step_roles)
        self._run("password", self.step_password)
        return all(c.ok for c in self.checks)

    @staticmethod
    def format_report(checks: list[Check]) -> str:
        lines: list[str] = []
        for c in checks:
            status = "PASS" if c.ok else "FAIL"
            lines.append(f"{status}  {c.name:<16} {c.ms:>4} ms  {c.detail}")
        passed = sum(1 for c in checks if c.ok)
        total = len(checks)
        lines.append(f"{passed}/{total} checks passed")
        return "\n".join(lines)


def make_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=30.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NetSentinel Phase 1 smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GATEWAY_URL", "http://localhost:8000"),
        help="Gateway base URL",
    )
    parser.add_argument(
        "--console-url",
        default=os.environ.get("CONSOLE_URL", ""),
        help="Dashboard URL to check (e.g. http://localhost:5173); empty = skip",
    )
    parser.add_argument("--user", default="operator", help="Username")
    parser.add_argument("--wait", type=float, default=120.0, help="Max wait seconds for polling")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text report")
    args = parser.parse_args(argv)

    client = make_client(args.base_url)
    try:
        smoke = Smoke(
            client, user=args.user, wait_s=args.wait, console_url=args.console_url or None
        )
        all_ok = smoke.run()
        if args.json:
            print(json.dumps([asdict(c) for c in smoke.checks]))
        else:
            print(Smoke.format_report(smoke.checks))
        return 0 if all_ok else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
