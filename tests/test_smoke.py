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
            if body.get("username") == "operator" and body.get("password") == "operator":
                return httpx.Response(200, json={"accessToken": self.token})
            return httpx.Response(401, json={"detail": "Invalid credentials"})

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
    assert len(smoke.checks) == 9
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
    assert [c["name"] for c in checks][-1] == "rbac" and all(c["ok"] for c in checks)


def test_main_text_output(monkeypatch, mock_transport, capsys):
    test_client = httpx.Client(transport=mock_transport, base_url="http://test")
    monkeypatch.setattr(smoke_module, "make_client", lambda base_url: test_client)
    exit_code = main(["--base-url", "http://test", "--wait", "0"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "9/9 checks passed" in captured.out
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
    assert len(smoke.checks) == 10


def test_smoke_console_down(client):
    smoke = Smoke(client, user="operator", wait_s=0, poll_s=0, console_url="http://nope")
    assert smoke.run() is False
    failed = [c for c in smoke.checks if not c.ok]
    assert [c.name for c in failed] == ["console"]
