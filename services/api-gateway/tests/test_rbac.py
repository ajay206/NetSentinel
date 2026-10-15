"""Step 13b: server-side RBAC per role, password change, lockout, admin user management, audit."""

from __future__ import annotations

import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_KAFKA", "1")

import api_gateway.main as main  # noqa: E402
from api_gateway import auth  # noqa: E402

STRONG = "N3w-Synthetic-pass!"
INC = "INC-0123456789"


@pytest.fixture
def client(monkeypatch, memory_store_factory):
    monkeypatch.setattr(auth.settings, "disabled", False)
    monkeypatch.setattr(auth.settings, "secret", "test-secret-0123456789abcdef-0123456789")
    monkeypatch.setattr(auth.settings, "ttl_seconds", 3600)
    monkeypatch.setattr(auth.settings, "rate_per_min", 10_000)
    monkeypatch.setattr(auth.settings, "login_rate_per_min", 10_000)
    monkeypatch.setattr(auth.settings, "lockout_threshold", 3)
    monkeypatch.setattr(auth.settings, "lockout_seconds", 600)
    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())
    monkeypatch.setattr(auth, "login_limiter", auth.RateLimiter())
    users = {r: (r, r) for r in ("viewer", "operator", "admin")}
    monkeypatch.setattr(auth.settings, "users", users)
    store = memory_store_factory(users)

    seen: list[httpx.Request] = []

    def incident_service(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/actions"):
            if request.headers.get("x-ns-role") not in ("operator", "admin"):
                return httpx.Response(403, json={"detail": "Requires role operator"})
            return httpx.Response(200, json={"id": INC, "workflow": {"state": "acknowledged"}})
        return httpx.Response(200, json={"items": [], "total": 0, "stats": {}})

    monkeypatch.setattr(main, "incident_transport", httpx.MockTransport(incident_service))
    monkeypatch.setattr(
        main,
        "copilot_transport",
        httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True})),
        raising=False,
    )
    monkeypatch.setattr(
        main,
        "topology_transport",
        httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True, "loaded": {}})),
    )
    c = TestClient(main.app)
    c.store = store  # type: ignore[attr-defined]
    c.seen = seen  # type: ignore[attr-defined]
    return c


def login(c: TestClient, user: str, password: str | None = None) -> httpx.Response:
    return c.post("/api/auth/login", json={"username": user, "password": password or user})


def bearer(c: TestClient, user: str, password: str | None = None) -> dict[str, str]:
    r = login(c, user, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


# --- permission matrix -------------------------------------------------------------------

MATRIX = [
    # (method, path, body, minimum role)
    ("GET", "/api/incidents", None, "viewer"),
    ("GET", "/api/alarms/workflow", None, "viewer"),
    ("POST", f"/api/incidents/{INC}/actions", {"action": "ack"}, "operator"),
    ("POST", "/api/alarms/actions", {"key": "SITE-001|x|y|z", "action": "ack"}, "operator"),
    ("GET", "/api/admin/users", None, "admin"),
    ("GET", "/api/admin/audit", None, "admin"),
    ("GET", "/api/admin/settings", None, "admin"),
    ("POST", "/api/admin/users/viewer/unlock", None, "admin"),
    # Step 14 knowledge graph
    ("GET", "/api/graph/impact?linkId=LNK-012", None, "viewer"),
    ("GET", "/api/graph/summary", None, "viewer"),
    ("GET", "/api/graph/queries", None, "viewer"),
    ("POST", "/api/graph/queries/site_by_id", {"siteId": "SITE-001"}, "viewer"),
    ("POST", "/api/graph/reload", None, "admin"),
]
ROLES = ("viewer", "operator", "admin")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("method,path,body,needed", MATRIX)
def test_permission_matrix(client, role, method, path, body, needed):
    r = client.request(method, path, json=body, headers=bearer(client, role))
    allowed = ROLES.index(role) >= ROLES.index(needed)
    if allowed:
        assert r.status_code == 200, (role, path, r.text)
    else:
        assert r.status_code == 403, (role, path, r.text)
        assert r.json()["detail"] == f"Requires role {needed}"


def test_copilot_needs_operator(client):
    r = client.post("/api/copilot/analyze", json={}, headers=bearer(client, "viewer"))
    assert r.status_code == 403


def test_actions_forward_user_and_are_audited(client):
    h = bearer(client, "operator")
    body = {"action": "assign", "assignee": "operator", "note": "taking it"}
    r = client.post(f"/api/incidents/{INC}/actions", json=body, headers=h)
    assert r.status_code == 200
    fwd = client.seen[-1]
    assert fwd.headers["x-ns-user"] == "operator" and fwd.headers["x-ns-role"] == "operator"
    entries = client.store.entries
    assert entries[-1]["action"] == "incident.assign" and entries[-1]["target"] == INC
    assert entries[-1]["detail"] == {"assignee": "operator", "note": "taking it"}


def test_unauthenticated_is_401(client):
    assert client.get("/api/admin/users").status_code == 401
    assert client.post("/api/auth/password", json={}).status_code == 401


# --- password change ----------------------------------------------------------------------


def test_password_change_revokes_old_tokens(client):
    old = bearer(client, "viewer")
    r = client.post(
        "/api/auth/password",
        json={"currentPassword": "viewer", "newPassword": STRONG},
        headers=old,
    )
    assert r.status_code == 200, r.text
    new = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=old).json()["detail"].startswith("Token revoked")
    assert client.get("/api/auth/me", headers=new).json()["username"] == "viewer"
    assert login(client, "viewer").status_code == 401
    assert login(client, "viewer", STRONG).status_code == 200
    assert any(e["action"] == "password.changed" for e in client.store.entries)


@pytest.mark.parametrize(
    "current,new,status,needle",
    [
        ("wrong", STRONG, 401, "Current password is wrong"),
        ("viewer", "viewer", 400, "must differ"),
        ("viewer", "short1!A", 400, "at least 10 characters"),
        ("viewer", "alllowercase123!", 400, "an uppercase letter"),
        ("viewer", "Viewer-is-me-123!", 400, "must not contain the username"),
        ("viewer", "Aa1!" + "x" * 69, 400, "at most 72 bytes"),
    ],
)
def test_password_change_policy(client, current, new, status, needle):
    r = client.post(
        "/api/auth/password",
        json={"currentPassword": current, "newPassword": new},
        headers=bearer(client, "viewer"),
    )
    assert r.status_code == status
    assert needle in r.json()["detail"]


def test_password_change_wrong_current_locks_out(client):
    h = bearer(client, "viewer")
    body = {"currentPassword": "wrong", "newPassword": STRONG}
    for _ in range(2):
        r = client.post("/api/auth/password", json=body, headers=h)
        assert r.status_code == 401
    r = client.post("/api/auth/password", json=body, headers=h)
    assert r.status_code == 423
    assert login(client, "viewer").status_code == 423


# --- lockout ------------------------------------------------------------------------------


def test_lockout_after_failures_and_admin_unlock(client):
    for _ in range(2):
        assert login(client, "operator", "bad").status_code == 401
    r = login(client, "operator", "bad")
    assert r.status_code == 423
    # even the right password is refused while locked
    assert login(client, "operator").status_code == 423
    admin = bearer(client, "admin")
    users = {
        u["username"]: u for u in client.get("/api/admin/users", headers=admin).json()["items"]
    }
    assert users["operator"]["locked"] is True
    assert client.post("/api/admin/users/operator/unlock", headers=admin).status_code == 200
    assert login(client, "operator").status_code == 200
    actions = [e["action"] for e in client.store.entries]
    assert "user.locked" in actions and "user.unlocked" in actions


def test_unknown_user_is_plain_401(client):
    assert login(client, "nobody", "x").status_code == 401


# --- admin user management ----------------------------------------------------------------


def test_admin_creates_user_changes_role_and_disables(client):
    admin = bearer(client, "admin")
    r = client.post(
        "/api/admin/users",
        json={"username": "noc.alice", "role": "viewer", "password": STRONG},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    assert (
        client.post(
            "/api/admin/users",
            json={"username": "noc.alice", "role": "viewer", "password": STRONG},
            headers=admin,
        ).status_code
        == 409
    )
    alice = bearer(client, "noc.alice", STRONG)
    assert (
        client.post(
            f"/api/incidents/{INC}/actions", json={"action": "ack"}, headers=alice
        ).status_code
        == 403
    )

    r = client.patch("/api/admin/users/noc.alice", json={"role": "operator"}, headers=admin)
    assert r.json()["role"] == "operator"
    # role change revokes the old token; a fresh login carries the new role
    assert client.get("/api/auth/me", headers=alice).status_code == 401
    alice = bearer(client, "noc.alice", STRONG)
    assert (
        client.post(
            f"/api/incidents/{INC}/actions", json={"action": "ack"}, headers=alice
        ).status_code
        == 200
    )

    client.patch("/api/admin/users/noc.alice", json={"disabled": True}, headers=admin)
    assert client.get("/api/auth/me", headers=alice).status_code == 401
    assert login(client, "noc.alice", STRONG).status_code == 403
    role_change = [e for e in client.store.entries if e["action"] == "user.role_changed"][0]
    assert role_change["detail"] == {"from": "viewer", "to": "operator"}


def test_admin_reset_password_and_guards(client):
    admin = bearer(client, "admin")
    viewer = bearer(client, "viewer")
    weak = client.post(
        "/api/admin/users/viewer/reset-password", json={"newPassword": "x"}, headers=admin
    )
    assert weak.status_code == 400
    r = client.post(
        "/api/admin/users/viewer/reset-password", json={"newPassword": STRONG}, headers=admin
    )
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=viewer).status_code == 401
    assert login(client, "viewer", STRONG).status_code == 200
    # an admin cannot demote or disable themselves, and the last admin is protected
    assert (
        client.patch("/api/admin/users/admin", json={"role": "viewer"}, headers=admin).status_code
        == 400
    )
    assert (
        client.patch("/api/admin/users/admin", json={"disabled": True}, headers=admin).status_code
        == 400
    )
    assert (
        client.patch("/api/admin/users/ghost", json={"role": "viewer"}, headers=admin).status_code
        == 404
    )
    bad = client.post(
        "/api/admin/users",
        json={"username": "X!", "role": "viewer", "password": STRONG},
        headers=admin,
    )
    assert bad.status_code == 400


def test_audit_and_settings_views(client):
    admin = bearer(client, "admin")
    items = client.get("/api/admin/audit", headers=admin).json()["items"]
    assert items[0]["action"] == "auth.login"  # newest first
    s = client.get("/api/admin/settings", headers=admin).json()
    assert s["userStore"] == "memory" and s["lockoutThreshold"] == 3
    assert "secret" not in json.dumps(s).lower()


def test_store_not_ready_is_503(client, monkeypatch):
    monkeypatch.setattr(auth, "store_state", {"ready": False, "seeded": 0, "error": "OSError"})
    assert login(client, "viewer").status_code == 503


def test_store_outage_fails_closed_with_503(client, monkeypatch):
    h = bearer(client, "viewer")

    async def boom(username):
        raise OSError("db down")

    monkeypatch.setattr(auth, "_cache", {})
    monkeypatch.setattr(auth.store, "get", boom)
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 503 and "db down" not in r.text


def test_pre_13b_tokens_without_tv_are_revoked(client):
    old = auth.jwt.encode(
        {
            "sub": "viewer",
            "role": "viewer",
            "iat": int(auth.time.time()),
            "exp": int(auth.time.time()) + 600,
            "iss": "netsentinel-gateway",
        },
        auth.settings.secret,
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_graph_reload_is_audited(client):
    r = client.post("/api/graph/reload", headers=bearer(client, "admin"))
    assert r.status_code == 200
    audit = client.get("/api/admin/audit", headers=bearer(client, "admin")).json()
    assert any(e["action"] == "graph.reload" and e["actor"] == "admin" for e in audit["items"])
