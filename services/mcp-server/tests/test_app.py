from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from mcp_server.app import build_app
from starlette.testclient import TestClient


def test_healthz_without_token():
    """Test /healthz returns 200 without auth."""
    with patch.dict(os.environ, {"MCP_SERVICE_TOKEN": "t0k", "MCP_ALLOW_NO_TOKEN": "0"}):
        app = build_app()
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_mcp_requires_token():
    """Test /mcp requires valid Bearer token."""
    with patch.dict(os.environ, {"MCP_SERVICE_TOKEN": "t0k", "MCP_ALLOW_NO_TOKEN": "0"}):
        app = build_app()
        # Context manager runs the lifespan (FastMCP's session manager task group).
        with TestClient(app) as client:
            _check_auth(client)


def _check_auth(client: TestClient) -> None:
    """401 without or with a wrong token; the right token passes the middleware."""
    # No token
    response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
    assert response.status_code == 401
    assert response.json() == {"detail": "missing or invalid service token"}

    # Wrong token
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "missing or invalid service token"}

    # Correct token - we don't test full handshake, just that it passes middleware
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        headers={
            "Authorization": "Bearer t0k",
            "Accept": "application/json, text/event-stream",
        },
    )
    # Should not be 401 (may be 400 for invalid JSON-RPC, but not auth error)
    assert response.status_code != 401


def test_build_app_without_token_raises():
    """Test build_app raises RuntimeError when token missing and not allowed."""
    with patch.dict(os.environ, {"MCP_SERVICE_TOKEN": "", "MCP_ALLOW_NO_TOKEN": "0"}, clear=True):
        with pytest.raises(RuntimeError, match="MCP_SERVICE_TOKEN is required"):
            build_app()


def test_build_app_with_allow_no_token():
    """Test build_app succeeds with MCP_ALLOW_NO_TOKEN=1."""
    with patch.dict(os.environ, {"MCP_SERVICE_TOKEN": "", "MCP_ALLOW_NO_TOKEN": "1"}, clear=True):
        app = build_app()
        assert app is not None
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
