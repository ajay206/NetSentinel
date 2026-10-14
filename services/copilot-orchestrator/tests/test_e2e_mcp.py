"""W9 fibre-cut e2e again, but evidence now flows copilot -> MCP -> mcp-server -> services (W10).

Uses the real FastMCP server over an in-memory MCP session; backends and the LLM are mocked.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import mcp_server.backends as backends
import pytest
from copilot_orchestrator.api import app, get_llm, get_upstream
from copilot_orchestrator.clients.llm import MockLLM
from copilot_orchestrator.clients.mcp_client import McpUpstream
from fastapi.testclient import TestClient
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_server.server import mcp

from .conftest import ANOM_ID, ROOT_ID, good_answer, make_transport


@asynccontextmanager
async def in_memory_session():
    async with create_connected_server_and_client_session(mcp) as session:
        yield session


@pytest.fixture
def client(monkeypatch):
    backends.TRANSPORT = make_transport()
    upstreams: list[McpUpstream] = []

    async def mcp_upstream():
        up = McpUpstream(in_memory_session)
        upstreams.append(up)
        try:
            yield up
        finally:
            await up.aclose()

    app.dependency_overrides[get_upstream] = mcp_upstream
    app.dependency_overrides[get_llm] = lambda: MockLLM([good_answer()])
    yield TestClient(app), upstreams
    app.dependency_overrides.clear()
    backends.TRANSPORT = None


def test_fibre_cut_through_mcp(client):
    c, upstreams = client
    resp = c.post("/analyze", json={"site_id": "SITE-010", "window": "30m"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["generatedBy"] == "llm" and data["warnings"] == []
    assert {ROOT_ID, ANOM_ID, "RB-FIB-001"} <= set(data["sourceIds"])
    calls = data["toolCalls"]
    assert [t["name"] for t in calls] == [
        "get_alarms",
        "predict_fault",
        "search_runbooks",
        "kpi_anomalies",
    ]
    assert all(t["ok"] and t["transport"] == "mcp" for t in calls)
    assert upstreams[0]._session is None  # session closed after the request


def test_mcp_server_down_is_503_not_404(client, monkeypatch):
    c, _ = client

    async def broken():
        up = McpUpstream(lambda: _raise())
        yield up

    @asynccontextmanager
    async def _raise():
        raise httpx.ConnectError("mcp down")
        yield  # pragma: no cover

    app.dependency_overrides[get_upstream] = broken
    # The alarm tool failed (not "no alarms"): surface 503, not a misleading 404
    resp = c.post("/analyze", json={"siteId": "SITE-010"})
    assert resp.status_code == 503
    assert "mcp-server unavailable" in resp.json()["detail"]


def test_mcp_tool_error_is_502(client, monkeypatch):
    c, _ = client
    backends.TRANSPORT = make_transport({"/api/alarms/enriched/recent"})
    try:
        resp = c.post("/analyze", json={"siteId": "SITE-010"})
    finally:
        backends.TRANSPORT = None
    assert resp.status_code == 502, resp.text
    assert "get_alarms" in resp.json()["detail"]


async def test_tool_error_becomes_warning():
    backends.TRANSPORT = make_transport({"/predict"})
    try:
        up = McpUpstream(in_memory_session)
        assert await up.predict({"id": ROOT_ID}) is None
        alarms = await up.alarms_for_site("SITE-010", 30)
        await up.aclose()
    finally:
        backends.TRANSPORT = None
    assert alarms[0]["id"] == ROOT_ID
    assert up.warnings == ["predict_fault returned an error"]
    assert [t["ok"] for t in up.tool_calls] == [False, True]
