"""W11 gateway auth (JWT, RBAC, rate limits) and alarm timeline tests."""

import time
from datetime import UTC, datetime, timedelta

import pytest
from api_gateway import auth
from api_gateway.timeline import build_timeline
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def app(monkeypatch):
    # monkeypatch settings
    monkeypatch.setattr(auth.settings, "disabled", False)
    monkeypatch.setattr(auth.settings, "secret", "test-secret-0123456789abcdef-0123456789")
    monkeypatch.setattr(auth.settings, "ttl_seconds", 3600)
    users = {
        "viewer": ("viewer", "viewer"),
        "operator": ("operator", "operator"),
        "admin": ("admin", "admin"),
    }
    monkeypatch.setattr(auth.settings, "users", users)
    monkeypatch.setattr(auth.settings, "rate_per_min", 1000)
    monkeypatch.setattr(auth.settings, "login_rate_per_min", 10)
    monkeypatch.setattr(auth.settings, "service_token", "svc-token")

    # reset limiters
    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())
    monkeypatch.setattr(auth, "login_limiter", auth.RateLimiter())

    app = FastAPI()

    # simple routes
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/thing")
    async def get_thing():
        return {"thing": "value"}

    @app.post("/api/copilot/analyze")
    async def analyze():
        return {"ok": True}

    @app.websocket("/ws/feed")
    async def ws_feed(ws: WebSocket):
        await ws.accept()
        await ws.send_text("hi")
        await ws.close()

    app.include_router(auth.router)
    app.add_middleware(auth.AuthMiddleware)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


def test_missing_token(client):
    resp = client.get("/api/thing")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_garbage_token(client):
    resp = client.get("/api/thing", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_expired_token(client, monkeypatch):
    token = auth.issue_token("viewer", "viewer", now=time.time() - 7200)
    resp = client.get("/api/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_wrong_secret_token(client, monkeypatch):
    # issue with a different secret
    other_secret = "other-secret-0123456789abcdef-0123456789"
    payload = {
        "sub": "viewer",
        "role": "viewer",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "iss": "netsentinel-gateway",
    }
    token = auth.jwt.encode(payload, other_secret, algorithm="HS256")
    resp = client.get("/api/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.parametrize(
    "username,method,expected_status",
    [
        ("viewer", "GET", 200),
        ("viewer", "POST", 403),
        ("operator", "GET", 200),
        ("operator", "POST", 200),
        ("admin", "GET", 200),
        ("admin", "POST", 200),
    ],
)
def test_role_access(client, username, method, expected_status):
    token = _login(client, username, username)
    headers = {"Authorization": f"Bearer {token}"}
    if method == "GET":
        resp = client.get("/api/thing", headers=headers)
    else:
        resp = client.post("/api/copilot/analyze", headers=headers)
    assert resp.status_code == expected_status


def test_admin_user_listing(client):
    token = _login(client, "admin", "admin")
    resp = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert {"username": "admin", "role": "admin"} in users
    assert {"username": "viewer", "role": "viewer"} in users
    assert {"username": "operator", "role": "operator"} in users
    # passwords must not be present
    for u in users:
        assert "password" not in u


def test_viewer_cannot_list_users(client):
    token = _login(client, "viewer", "viewer")
    resp = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_health_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_and_me(client):
    token = _login(client, "operator", "operator")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "operator"
    assert data["role"] == "operator"


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "viewer", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_rate_limit(client, monkeypatch):
    # set low limit
    monkeypatch.setattr(auth.settings, "login_rate_per_min", 2)
    for _ in range(2):
        resp = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer"})
        assert resp.status_code == 200
    resp = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_general_rate_limit(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "rate_per_min", 3)
    token = _login(client, "viewer", "viewer")
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(3):
        resp = client.get("/api/thing", headers=headers)
        assert resp.status_code == 200
    resp = client.get("/api/thing", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_service_token_access(client):
    token = "svc-token"
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/thing", headers=headers)
    assert resp.status_code == 200
    resp = client.post("/api/copilot/analyze", headers=headers)
    assert resp.status_code == 403


def test_websocket_with_token(client):
    token = _login(client, "viewer", "viewer")
    with client.websocket_connect(f"/ws/feed?token={token}") as ws:
        msg = ws.receive_text()
        assert msg == "hi"


def test_websocket_missing_token(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/feed") as ws:
            ws.receive_text()
    assert exc.value.code == 4401  # 4000 + 401


@pytest.mark.parametrize(
    "disabled,expected_status",
    [(True, 200), (False, 401)],
)
def test_disabled_bypass(monkeypatch, client, disabled, expected_status):
    monkeypatch.setattr(auth.settings, "disabled", disabled)
    resp = client.get("/api/thing")
    assert resp.status_code == expected_status


# ---------- Timeline tests ----------
def test_build_timeline_empty():
    result = build_timeline([])
    assert result["buckets"] == []


def test_build_timeline_gap_and_severity():
    alarms = [
        {"alarmRaisedTime": "2023-01-01T00:00:10Z", "perceivedSeverity": "critical"},
        {"alarmRaisedTime": "2023-01-01T00:01:10Z", "perceivedSeverity": "major"},
        {"alarmRaisedTime": "2023-01-01T00:02:05Z", "perceivedSeverity": "warning"},
    ]
    res = build_timeline(alarms, bucket_seconds=60, max_buckets=5)
    # buckets aligned to epoch multiples: 0-60,60-120,120-180
    assert len(res["buckets"]) == 3
    # first bucket total 1 critical
    b0 = res["buckets"][0]
    assert b0["total"] == 1
    assert b0["bySeverity"]["critical"] == 1
    # second bucket total 1 major
    b1 = res["buckets"][1]
    assert b1["total"] == 1
    assert b1["bySeverity"]["major"] == 1
    # third bucket total 1 warning
    b2 = res["buckets"][2]
    assert b2["total"] == 1
    assert b2["bySeverity"]["warning"] == 1
    # total and peak
    assert res["total"] == 3
    assert res["peak"] == 1


def test_build_timeline_max_buckets():
    # generate 10 minutes of alarms, bucket 60s, max 5 buckets -> keep last 5
    alarms = []
    base = datetime(2023, 1, 1, tzinfo=UTC)
    for i in range(10):
        ts = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        alarms.append({"alarmRaisedTime": ts, "perceivedSeverity": "minor"})
    res = build_timeline(alarms, bucket_seconds=60, max_buckets=5)
    assert len(res["buckets"]) == 5
    # earliest kept bucket corresponds to minute 5
    first_start = datetime.fromisoformat(res["buckets"][0]["start"].replace("Z", "+00:00"))
    assert first_start == base + timedelta(minutes=5)


def test_build_timeline_unparsable_times():
    alarms = [
        {"alarmRaisedTime": "invalid", "perceivedSeverity": "critical"},
        {"alarmRaisedTime": "2023-01-01T00:00:30Z", "perceivedSeverity": "major"},
    ]
    res = build_timeline(alarms, bucket_seconds=60, max_buckets=10)
    # only one valid alarm counted
    assert res["total"] == 1
    assert res["buckets"][0]["bySeverity"]["major"] == 1


@pytest.mark.parametrize(
    "method,path,needed",
    [
        ("GET", "/health", None),
        ("GET", "/healthz", None),
        ("GET", "/readyz", None),
        ("OPTIONS", "/api/thing", None),
        ("POST", "/api/auth/login", None),
        ("GET", "/api/alarms/timeline", "viewer"),
        ("GET", "/ws/enriched", "viewer"),
        ("POST", "/api/ml/predict", "viewer"),
        ("POST", "/api/copilot/analyze", "operator"),
        ("GET", "/api/auth/users", "admin"),
        ("GET", "/", None),
    ],
)
def test_required_role_table(method: str, path: str, needed: str | None) -> None:
    assert auth.required_role(method, path) == needed


def test_settings_from_env_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_USERS", "ann:pw1:operator,bad-entry,bob:pw2:root")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    s = auth.AuthSettings.from_env()
    assert s.users == {"ann": ("pw1", "operator")}
