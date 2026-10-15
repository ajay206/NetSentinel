"""Unit tests for scripts/smoke.py against a fake gateway (httpx.MockTransport)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest


def load_smoke_module():
    smoke_path = Path(__file__).parent.parent / "scripts" / "smoke.py"
    spec = importlib.util.spec_from_file_location("smoke", smoke_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load smoke module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke"] = module
    spec.loader.exec_module(module)
    return module


smoke_module = load_smoke_module()
Smoke = smoke_module.Smoke
Check = smoke_module.Check
make_client = smoke_module.make_client
main = smoke_module.main


class FakeGateway:
    def __init__(self):
        self.token = "secret-token-xyz"
        self.alarms_data = [
            {
                "id": "alarm-1",
                "specificProblem": "High latency",
                "probableCause": "Congestion",
                "siteId": "site-1",
                "correlation": {"role": "root", "rootSiteId": "site-1"},
            },
            {
                "id": "alarm-2",
                "specificProblem": "Packet loss",
                "probableCause": "Faulty cable",
                "siteId": "site-2",
                "correlation": {"role": "child", "rootSiteId": "site-1"},
            },
        ]
        self.anomalies_data = {
            "kpi": "dlThroughputMbps",
            "hours": 24,
            "items": [{"cellId": "CELL-001-1", "score": 4.2}],
        }
        self.fault_response = {"faultType": "congestion", "confidence": 0.95}
        self.runbooks_data = {
            "results": [
                {"runbookId": "rb-1", "title": "Congestion mitigation"},
                {"runbookId": "rb-2", "title": "Capacity planning"},
            ]
        }
        self.copilot_response = {
            "sourceIds": ["alarm-1", "rb-1", "rb-2"],
            "answer": {
                "steps": [
                    {"runbookId": "rb-1", "description": "Check bandwidth"},
                    {"runbookId": "rb-2", "description": "Plan upgrade"},
                ]
            },
            "generatedBy": "llm",
        }
        self.health_response = {
            "status": "ok",
            "services": [
                {"name": n, "status": "up"}
                for n in ("api-gateway", "kafka", "alarm-ingest", "ml-service", "rag-service")
            ],
        }
        self.timeline_response = {"total": 42, "peak": 10}
        # Step 13b: tokens per user, password store and revocation for the roles/password checks
        self.passwords = {"operator": "operator", "viewer": "viewer", "admin": "admin"}
        self.roles = {"operator": "operator", "viewer": "viewer", "admin": "admin"}
        self.tokens: dict[str, str] = {self.token: "operator"}
        self.disabled: set[str] = set()
        self.issued = 0
        # Step 14: graph profile up? (False -> 503 like the gateway when topology-service is down)
        self.graph_up = True
        self.impact_ms = 4.2

    def _user(self, request: httpx.Request) -> str | None:
        return self.tokens.get(request.headers.get("Authorization", "").removeprefix("Bearer "))

    def _issue(self, user: str) -> str:
        self.issued += 1
        token = self.token if user == "operator" else f"tok-{user}-{self.issued}"
        self.tokens[token] = user
        return token

    def _check_auth(self, request: httpx.Request) -> bool:
        auth = request.headers.get("Authorization", "")
        return auth == f"Bearer {self.token}"

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if path == "/health" and method == "GET":
            return httpx.Response(200, json=self.health_response)

        if path == "/api/auth/login" and method == "POST":
            body = json.loads(request.content)
            user = body.get("username")
            if user in self.passwords and self.passwords[user] == body.get("password"):
                if user in self.disabled:
                    return httpx.Response(403, json={"detail": "Account disabled"})
                return httpx.Response(200, json={"accessToken": self._issue(user)})
            return httpx.Response(401, json={"detail": "Invalid credentials"})

        if path == "/api/auth/me" and method == "GET":
            user = self._user(request)
            return httpx.Response(200 if user else 401, json={"username": user})

        if path == "/api/auth/password" and method == "POST":
            user = self._user(request)
            body = json.loads(request.content)
            if not user or self.passwords[user] != body["currentPassword"]:
                return httpx.Response(401, json={"detail": "no"})
            self.passwords[user] = body["newPassword"]
            self.tokens = {t: u for t, u in self.tokens.items() if u != user}
            return httpx.Response(200, json={"accessToken": self._issue(user)})

        if path.startswith("/api/incidents/") and path.endswith("/actions"):
            user = self._user(request)
            if self.roles.get(user or "") not in ("operator", "admin"):
                return httpx.Response(403, json={"detail": "Requires role operator"})
            return httpx.Response(404, json={"detail": "Incident not found"})

        if path.startswith("/api/admin/users"):
            if self.roles.get(self._user(request) or "") != "admin":
                return httpx.Response(403, json={"detail": "Requires role admin"})
            if method == "GET":
                return httpx.Response(200, json={"items": []})
            if method == "POST":
                body = json.loads(request.content)
                self.passwords[body["username"]] = body["password"]
                self.roles[body["username"]] = body["role"]
                return httpx.Response(201, json={"username": body["username"]})
            if method == "PATCH":
                self.disabled.add(path.rsplit("/", 1)[-1])
                return httpx.Response(200, json={})

        if path.startswith("/api/graph/"):
            if not self._user(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            if not self.graph_up:
                return httpx.Response(503, json={"detail": "topology-service unreachable"})
            if path == "/api/graph/summary":
                return httpx.Response(200, json={"counts": {"sites": 12}})
            if path == "/api/graph/impact" and request.url.params.get("linkId") == "LNK-012":
                cells = ["SITE-010-N1-C1", "SITE-010-N1-C2", "SITE-010-N1-C3"]
                return httpx.Response(
                    200,
                    json={
                        "impactedSites": [{"siteId": "SITE-010", "cells": cells}],
                        "cellsLost": 3,
                        "elapsedMs": self.impact_ms,
                        "backend": "neo4j",
                    },
                )

        if path == "/api/alarms/enriched/recent" and method == "GET":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            return httpx.Response(200, json=self.alarms_data)

        if path == "/api/alarms/timeline" and method == "GET":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            return httpx.Response(200, json=self.timeline_response)

        if path == "/api/ml/anomalies" and method == "GET":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            return httpx.Response(200, json=self.anomalies_data)

        if path == "/api/ml/predict" and method == "POST":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            return httpx.Response(200, json=self.fault_response)

        if path == "/api/rag/search" and method == "POST":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            body = json.loads(request.content or b"{}")
            if body.get("mode") == "graph":
                hits = [
                    dict(r, nodeIds=["SITE-010", "LNK-012"]) for r in self.runbooks_data["results"]
                ]
                return httpx.Response(
                    200,
                    json={
                        **self.runbooks_data,
                        "mode": "graph",
                        "results": hits,
                        "graph": {"source": "local", "nodes": ["SITE-010"]},
                    },
                )
            return httpx.Response(200, json=self.runbooks_data)

        if path == "/api/copilot/analyze" and method == "POST":
            if not self._check_auth(request):
                return httpx.Response(401, json={"detail": "Unauthorized"})
            return httpx.Response(200, json=self.copilot_response)

        if request.url.host == "console" and method == "GET":
            if path == "/":
                return httpx.Response(200, text='<html><div id="root"></div></html>')
            if path == "/health":
                return httpx.Response(200, json={"services": []})

        if path.startswith("/api/copilot/runs"):
            return self._runs(request)
        if path.startswith("/api/tickets"):
            return self._tickets(request)
        return httpx.Response(404, json={"detail": "Not found"})


@pytest.fixture
def fake_gateway():
    return FakeGateway()


@pytest.fixture
def mock_transport(fake_gateway):
    return httpx.MockTransport(fake_gateway.handle_request)


@pytest.fixture
def client(mock_transport):
    return httpx.Client(transport=mock_transport, base_url="http://test")


def test_smoke_all_pass(client, monkeypatch):
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: client)
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0)
    result = smoke.run()
    assert result is True
    assert len(smoke.checks) == 15
    assert all(c.ok for c in smoke.checks)


def test_smoke_down_service(client, monkeypatch):
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: client)
    fake = FakeGateway()
    fake.health_response = {
        "services": [
            {"name": "api-gateway", "status": "up"},
            {"name": "alarm-ingest", "status": "down"},
        ]
    }
    transport = httpx.MockTransport(fake.handle_request)
    test_client = httpx.Client(transport=transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    smoke = Smoke(test_client, user="operator", wait_s=0, poll_s=0)
    result = smoke.run()
    assert result is False
    health_check = next(c for c in smoke.checks if c.name == "health")
    assert health_check.ok is False
    assert "alarm-ingest" in health_check.detail


def test_smoke_empty_alarms_skips_dependants(client, monkeypatch):
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: client)
    fake = FakeGateway()
    fake.alarms_data = []
    transport = httpx.MockTransport(fake.handle_request)
    test_client = httpx.Client(transport=transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    smoke = Smoke(test_client, user="operator", wait_s=0, poll_s=0)
    result = smoke.run()
    assert result is False
    alarms_check = next(c for c in smoke.checks if c.name == "alarms")
    assert alarms_check.ok is False
    for name in ("fault", "runbooks", "copilot"):
        check = next(c for c in smoke.checks if c.name == name)
        assert check.ok is False
        assert check.detail.startswith("skipped:")


def test_smoke_copilot_no_citation_fails(client, monkeypatch):
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: client)
    fake = FakeGateway()
    fake.copilot_response = {
        "sourceIds": ["src-1"],
        "answer": {"steps": [{"description": "No citation"}]},
        "generatedBy": "llm",
    }
    transport = httpx.MockTransport(fake.handle_request)
    test_client = httpx.Client(transport=transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    smoke = Smoke(test_client, user="operator", wait_s=0, poll_s=0)
    result = smoke.run()
    assert result is False
    copilot_check = next(c for c in smoke.checks if c.name == "copilot")
    assert copilot_check.ok is False
    assert "citation" in copilot_check.detail.lower()


def test_format_report():
    checks = [
        Check(name="health", ok=True, detail="5 services up", ms=12),
        Check(name="login", ok=True, detail="logged in", ms=45),
        Check(name="alarms", ok=False, detail="skipped: no token", ms=0),
    ]
    report = Smoke.format_report(checks)
    lines = report.splitlines()
    assert lines[0].startswith("PASS  health") and lines[0].endswith("12 ms  5 services up")
    assert lines[2].startswith("FAIL  alarms") and lines[2].endswith("skipped: no token")
    assert "2/3 checks passed" in report


def test_main_json_output(monkeypatch, mock_transport, capsys):
    test_client = httpx.Client(transport=mock_transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    exit_code = main(["--base-url", "http://test", "--json", "--wait", "0"])
    assert exit_code == 0
    checks = json.loads(capsys.readouterr().out)
    assert [c["name"] for c in checks][-6:] == [
        "rbac",
        "roles",
        "password",
        "graph_impact",
        "tickets",
        "agents",
    ] and all(c["ok"] for c in checks)


def test_main_text_output(monkeypatch, mock_transport, capsys):
    test_client = httpx.Client(transport=mock_transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    exit_code = main(["--base-url", "http://test", "--wait", "0"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "15/15 checks passed" in captured.out
    assert "secret-token-xyz" not in captured.out


def test_token_never_in_report(monkeypatch, mock_transport, capsys):
    test_client = httpx.Client(transport=mock_transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    main(["--base-url", "http://test", "--wait", "0"])
    captured = capsys.readouterr()
    assert "secret-token-xyz" not in captured.out


def test_rbac_requires_auth(monkeypatch, mock_transport):
    test_client = httpx.Client(transport=mock_transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    smoke = Smoke(test_client, user="operator", wait_s=0, poll_s=0)
    smoke.run()
    rbac_check = next(c for c in smoke.checks if c.name == "rbac")
    assert rbac_check.ok is True
    assert "401" in rbac_check.detail


def test_polls_until_alarms_arrive() -> None:
    """Alarms show up on the third poll; the fake clock/sleep means no real waiting."""
    fake = FakeGateway()
    calls = {"n": 0}
    real = fake.handle_request

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/alarms/enriched/recent":
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(200, json=[])
        return real(request)

    now = {"t": 0.0}

    def sleep(s: float) -> None:
        now["t"] += s

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    smoke = Smoke(client, wait_s=30, poll_s=3, sleep=sleep, clock=lambda: now["t"])
    assert smoke.run() is True
    assert calls["n"] == 3


def test_smoke_console_check(client):
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0, console_url="http://console/")
    assert smoke.run() is True
    assert [c.name for c in smoke.checks][:2] == ["health", "console"]
    assert len(smoke.checks) == 16


def test_smoke_console_down(client):
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0, console_url="http://nope")
    assert smoke.run() is False
    failed = [c for c in smoke.checks if not c.ok]
    assert [c.name for c in failed] == ["console"]


def test_roles_and_password_checks_against_real_gateway(monkeypatch):
    """Step 13b: the new smoke checks pass against the real gateway (memory user store)."""
    import asyncio
    import os

    os.environ.setdefault("DISABLE_KAFKA", "1")
    import api_gateway.main as gw
    from api_gateway import auth
    from api_gateway.users import MemoryUserStore, seed
    from fastapi.testclient import TestClient

    users = {r: (r, r) for r in ("viewer", "operator", "admin")}
    store = MemoryUserStore()
    asyncio.run(seed(store, users))
    monkeypatch.setattr(auth.settings, "disabled", False)
    monkeypatch.setattr(auth.settings, "secret", "test-secret-0123456789abcdef-0123456789")
    monkeypatch.setattr(auth.settings, "login_rate_per_min", 1000)
    monkeypatch.setattr(auth, "store", store)
    monkeypatch.setattr(auth, "store_state", {"ready": True, "seeded": 3, "error": None})
    monkeypatch.setattr(auth, "_cache", {})
    monkeypatch.setattr(
        gw,
        "incident_transport",
        httpx.MockTransport(lambda r: httpx.Response(404, json={"detail": "Incident not found"})),
    )
    smoke = Smoke(TestClient(gw.app), user="operator", wait_s=0, poll_s=0)
    smoke._run("roles", smoke.step_roles)
    smoke._run("password", smoke.step_password)
    assert [c.ok for c in smoke.checks] == [True, True], smoke.checks
    created = [u for u in asyncio.run(store.list()) if u.username.startswith("smoke.")]
    assert len(created) == 1 and created[0].disabled
    report = Smoke.format_report(smoke.checks)
    assert "Sm0ke-" not in report  # generated passwords never printed


def test_password_check_fails_if_old_token_survives(client, fake_gateway):
    fake_gateway.handle_request  # noqa: B018 - fixture in use
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0)
    smoke._run("roles", smoke.step_roles)
    original = fake_gateway.handle_request

    def keep_tokens(request):
        if request.url.path == "/api/auth/password":
            before = dict(fake_gateway.tokens)
            resp = original(request)
            fake_gateway.tokens.update(before)  # simulate a gateway that forgets to revoke
            return resp
        return original(request)

    client._transport = httpx.MockTransport(keep_tokens)
    smoke._run("password", smoke.step_password)
    assert smoke.checks[-1].ok is False
    assert "old token still works" in smoke.checks[-1].detail


# --- fix 2: login rate limit (429) during smoke --------------------------------------------


class LimitedGateway(FakeGateway):
    """FakeGateway whose login allows `limit` calls per window (like LOGIN_RATE_PER_MIN)."""

    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit
        self.window_logins = 0
        self.login_calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            self.login_calls += 1
            if self.window_logins >= self.limit:
                return httpx.Response(429, headers={"Retry-After": "7"}, json={"detail": "slow"})
            self.window_logins += 1
        return super().handle_request(request)


def test_smoke_backs_off_on_login_429_and_reuses_tokens():
    gw = LimitedGateway(limit=3)
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        gw.window_logins = 0  # the minute window rolls over while we wait

    client = httpx.Client(transport=httpx.MockTransport(gw.handle_request), base_url="http://t")
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0, sleep=sleep)
    assert smoke.run() is True, [c for c in smoke.checks if not c.ok]
    assert 7.0 in sleeps and smoke.login_waits >= 1  # honoured Retry-After
    # operator, viewer, admin, throwaway, old-password check: the operator token is reused
    assert gw.login_calls - smoke.login_waits == 5


def test_smoke_login_backoff_is_bounded(monkeypatch):
    gw = LimitedGateway(limit=0)  # every login is 429
    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(gw.handle_request), base_url="http://t")
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0, sleep=sleeps.append)
    monkeypatch.setattr(smoke, "LOGIN_MAX_WAIT_S", 20.0)
    smoke._run("login", smoke.step_login)
    assert smoke.checks[-1].ok is False and "429" in smoke.checks[-1].detail
    assert sum(sleeps) <= 20.0 and sleeps == [7.0, 7.0]


@pytest.mark.parametrize(
    "mode,graph_up,ms,ok,needle",
    [
        ("auto", True, 4.2, True, "LNK-012 -> 3 cells lost"),
        ("auto", False, 4.2, True, "skipped: graph profile not running"),
        ("1", False, 4.2, False, "503"),
        ("1", True, 250.0, False, "target < 100"),
    ],
)
def test_graph_impact_check(monkeypatch, mode, graph_up, ms, ok, needle):
    fake = FakeGateway()
    fake.graph_up, fake.impact_ms = graph_up, ms
    c = httpx.Client(transport=httpx.MockTransport(fake.handle_request), base_url="http://test")
    monkeypatch.setattr(Smoke, "GRAPH_MODE", mode)
    smoke = Smoke(c, user="operator", wait_s=0, poll_s=0)
    smoke.run()
    check = next(x for x in smoke.checks if x.name == "graph_impact")
    assert check.ok is ok and needle in check.detail, check.detail


def test_graph_check_off(client, monkeypatch):
    monkeypatch.setattr(Smoke, "GRAPH_MODE", "0")
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0)
    smoke.run()
    assert "graph_impact" not in {c.name for c in smoke.checks}


def _tickets(self, request):  # noqa: ANN001 - test double for the W16 endpoints
    if not getattr(self, "tickets_up", False):
        return httpx.Response(503, json={"detail": "ticket-service unreachable"})
    auth = request.headers.get("authorization", "")
    path = request.url.path
    if path == "/api/tickets/drafts":
        return httpx.Response(201, json={"id": "TKT-0000000001", "status": "draft"})
    if path.endswith("/approve"):
        if "viewer" in auth:
            return httpx.Response(403, json={"detail": "Requires role operator"})
        return httpx.Response(200, json={"id": "TKT-0000000001", "status": "approved"})
    if path.endswith("/verify"):
        return httpx.Response(200, json={"ok": True, "entries": 2})
    return httpx.Response(200, json={"entries": [{"action": "created"}, {"action": "approved"}]})


FakeGateway._tickets = _tickets  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "mode,up,ok,needle",
    [
        ("auto", False, True, "skipped: ops profile not running"),
        ("1", False, False, "503"),
        ("auto", True, True, "draft -> approved, audit chain ok"),
    ],
)
def test_tickets_check(monkeypatch, mode, up, ok, needle):
    fake = FakeGateway()
    fake.tickets_up = up
    c = httpx.Client(transport=httpx.MockTransport(fake.handle_request), base_url="http://test")
    monkeypatch.setattr(Smoke, "TICKETS_MODE", mode)
    smoke = Smoke(c, user="operator", wait_s=0, poll_s=0)
    smoke.run()
    check = next(x for x in smoke.checks if x.name == "tickets")
    assert check.ok is ok and needle in check.detail, check.detail


def _runs(self, request):  # noqa: ANN001 - test double for the W17 endpoints
    if not getattr(self, "agents_up", False):
        return httpx.Response(503, json={"detail": "copilot-orchestrator unreachable"})
    run = {"runId": "RUN-00000000AA", "status": "awaiting_approval", "agentPath": ["supervisor"]}
    if request.url.path.endswith("/approval"):
        path = ["supervisor", "triage", "rca", "remediation", "approval", "report"]
        run |= {"status": "completed", "agentPath": path, "ticketId": "TKT-00000000AA"}
    return httpx.Response(200, json=run)


FakeGateway._runs = _runs  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "mode,up,ok,needle",
    [
        ("auto", False, True, "skipped: copilot profile not running"),
        ("1", False, False, "503"),
        ("auto", True, True, "approval→report ticket=TKT-00000000AA"),
    ],
)
def test_agents_check(monkeypatch, mode, up, ok, needle):
    fake = FakeGateway()
    fake.agents_up = up
    c = httpx.Client(transport=httpx.MockTransport(fake.handle_request), base_url="http://test")
    monkeypatch.setattr(Smoke, "AGENTS_MODE", mode)
    smoke = Smoke(c, user="operator", wait_s=0, poll_s=0)
    smoke.run()
    check = next(x for x in smoke.checks if x.name == "agents")
    assert check.ok is ok and needle in check.detail, check.detail
