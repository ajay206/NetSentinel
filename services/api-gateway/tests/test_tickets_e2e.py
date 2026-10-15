"""Step 16 end to end: gateway RBAC + the real ticket-service (SQLite) + both audit logs."""

from __future__ import annotations

import os

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_KAFKA", "1")

import api_gateway.main as main  # noqa: E402
from api_gateway import auth  # noqa: E402

SVC_TOKEN = "svc-test-token-0123456789"
DRAFT = {"title": "Fibre cut isolates SITE-010", "siteId": "SITE-010", "runbookIds": ["RB-FIB-001"]}


@pytest.fixture
def gw(monkeypatch, memory_store_factory, tmp_path):
    from ticket_service.db import TicketStore, make_engine, upgrade
    from ticket_service.main import app as ticket_app

    monkeypatch.delenv("TICKET_SERVICE_TOKEN", raising=False)
    engine = make_engine(f"sqlite:///{tmp_path}/t.db")
    upgrade(engine)
    ticket_app.state.store = TicketStore(engine)
    monkeypatch.setattr(main, "ticket_transport", httpx.ASGITransport(app=ticket_app))
    monkeypatch.setattr(auth.settings, "disabled", False)
    monkeypatch.setattr(auth.settings, "secret", "test-secret-0123456789abcdef-0123456789")
    monkeypatch.setattr(auth.settings, "service_token", SVC_TOKEN)
    monkeypatch.setattr(auth.settings, "rate_per_min", 10_000)
    monkeypatch.setattr(auth.settings, "login_rate_per_min", 10_000)
    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())
    monkeypatch.setattr(auth, "login_limiter", auth.RateLimiter())
    users = {r: (r, r) for r in ("viewer", "operator", "admin")}
    monkeypatch.setattr(auth.settings, "users", users)
    store = memory_store_factory(users)
    c = TestClient(main.app)
    c.store = store  # type: ignore[attr-defined]
    return c


def h(c, user):
    tok = c.post("/api/auth/login", json={"username": user, "password": user}).json()
    return {"Authorization": f"Bearer {tok['accessToken']}"}


def test_mcp_drafts_viewer_cannot_operator_approves(gw):
    svc = {"Authorization": f"Bearer {SVC_TOKEN}"}
    r = gw.post("/api/tickets/drafts", json=DRAFT, headers=svc)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["createdVia"] == "mcp" and t["createdBy"] == "service:mcp"
    tid = t["id"]
    # the service token can draft but never decide
    assert gw.post(f"/api/tickets/{tid}/approve", json={}, headers=svc).status_code == 403
    viewer = h(gw, "viewer")
    assert gw.post("/api/tickets/drafts", json=DRAFT, headers=viewer).status_code == 403
    assert gw.post(f"/api/tickets/{tid}/approve", json={}, headers=viewer).status_code == 403
    assert gw.get("/api/tickets", headers=viewer).json()["counts"]["draft"] == 1
    op = h(gw, "operator")
    r = gw.post(f"/api/tickets/{tid}/approve", json={"note": "go"}, headers=op)
    assert r.status_code == 200 and r.json()["decidedBy"] == "operator"
    assert gw.post(f"/api/tickets/{tid}/reject", json={"note": "x"}, headers=op).status_code == 409
    trail = gw.get(f"/api/tickets/{tid}/audit", headers=viewer).json()["entries"]
    assert [(e["actor"], e["action"]) for e in trail] == [
        ("service:mcp", "created"),
        ("operator", "approved"),
    ]
    assert gw.get("/api/tickets/audit/verify", headers=viewer).json()["ok"] is True
    assert len(gw.get("/api/tickets/audit", headers=viewer).json()["entries"]) == 2
    gw_audit = [
        (e["actor"], e["action"]) for e in gw.store.entries if e["action"].startswith("ticket.")
    ]
    assert gw_audit == [("service", "ticket.draft"), ("operator", "ticket.approve")]


def test_bad_ids_and_down_service(gw, monkeypatch):
    op = h(gw, "operator")
    assert gw.get("/api/tickets/TKT-1", headers=op).status_code == 404
    assert gw.post("/api/tickets/TKT-0123456789/close", json={}, headers=op).status_code in (
        403,
        404,
    )

    def down(_r):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(main, "ticket_transport", httpx.MockTransport(down))
    assert gw.get("/api/tickets", headers=op).status_code == 503
