"""Contract tests: tools/resources/prompts of the FastMCP server, over an in-memory MCP session."""

from __future__ import annotations

import json

import httpx
import mcp_server.backends as backends
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_server.server import mcp

TS = "2026-10-14T10:00:00Z"


def _alarm(aid: str, site: str, role: str, root: str | None, sev: str = "major") -> dict:
    return {
        "id": aid,
        "siteId": site,
        "specificProblem": "LOS",
        "probableCause": "lossOfSignal",
        "perceivedSeverity": sev,
        "alarmRaisedTime": TS,
        "enrichment": {"parentSiteId": "SITE-001"},
        "correlation": {"rootSiteId": root, "role": role},
    }


def handler(req: httpx.Request) -> httpx.Response:
    path = req.url.path
    if path == "/api/alarms/enriched/recent":
        return httpx.Response(
            200,
            json=[
                _alarm("sym-1", "SITE-011", "symptom", "SITE-010"),
                _alarm("root-1", "SITE-010", "root", "SITE-010", "critical"),
                _alarm("other", "SITE-099", "none", None),
            ],
        )
    if path == "/anomalies":
        items = []
        if req.url.params["kpi"] == "availabilityPct":
            items = [
                {"cellId": "SITE-010-N1-C1", "ts": TS, "score": 8.0, "direction": "low"},
                {"cellId": "SITE-0100-N1-C1", "ts": TS, "score": 99.0, "direction": "low"},
            ]
        return httpx.Response(200, json={"kpi": req.url.params["kpi"], "items": items})
    if path == "/predict":
        assert json.loads(req.content)["alarm"]["id"] == "root-1"
        return httpx.Response(200, json={"faultType": "fibre_cut", "confidence": 0.9})
    if path == "/search":
        body = json.loads(req.content)
        assert body["faultType"] == "fibre_cut" and body["top_k"] == 2
        return httpx.Response(200, json={"results": [{"runbookId": "RB-FIB-001"}]})
    if path == "/runbooks/RB-FIB-001":
        return httpx.Response(200, json={"id": "RB-FIB-001", "markdown": "# Fibre cut"})
    if path == "/api/graph/impact":
        assert dict(req.url.params) == {"linkId": "LNK-012"}
        return httpx.Response(
            200,
            json={
                "target": {"type": "link", "id": "LNK-012"},
                "impactedSites": [{"siteId": "SITE-010", "reason": "isolated", "cells": ["c1"]}],
                "cellsLost": 1,
                "sitesIsolated": 1,
            },
        )
    if path == "/api/graph/queries/path_to_core":
        assert json.loads(req.content) == {"siteId": "SITE-010"}
        return httpx.Response(200, json={"query": "path_to_core", "rows": [{"hops": 2}]})
    return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture(autouse=True)
def fake_backends():
    backends.TRANSPORT = httpx.MockTransport(handler)
    yield
    backends.TRANSPORT = None


async def test_lists_exactly_the_phase1_tools():
    async with create_connected_server_and_client_session(mcp) as s:
        tools = {t.name: t for t in (await s.list_tools()).tools}
    assert set(tools) == {
        "get_alarms",
        "kpi_anomalies",
        "search_runbooks",
        "predict_fault",
        "query_topology",
    }
    assert "required" not in tools["query_topology"].inputSchema
    assert tools["get_alarms"].inputSchema["required"] == ["site_id"]
    assert tools["search_runbooks"].inputSchema["required"] == ["query"]
    assert tools["predict_fault"].inputSchema["required"] == ["alarm"]
    assert all(t.description for t in tools.values())


async def test_get_alarms_root_first_and_site_filtered():
    async with create_connected_server_and_client_session(mcp) as s:
        res = await s.call_tool("get_alarms", {"site_id": "SITE-010"})
    assert not res.isError
    ids = [a["id"] for a in res.structuredContent["alarms"]]
    assert ids == ["root-1", "sym-1"]


async def test_kpi_anomalies_prefix_filter_and_kpi_tag():
    async with create_connected_server_and_client_session(mcp) as s:
        res = await s.call_tool("kpi_anomalies", {"site_id": "SITE-010"})
    items = res.structuredContent["anomalies"]
    assert [(i["cellId"], i["kpi"]) for i in items] == [("SITE-010-N1-C1", "availabilityPct")]


async def test_predict_and_search():
    async with create_connected_server_and_client_session(mcp) as s:
        pred = await s.call_tool("predict_fault", {"alarm": {"id": "root-1"}})
        rb = await s.call_tool(
            "search_runbooks", {"query": "LOS", "fault_type": "fibre_cut", "top_k": 2}
        )
    assert pred.structuredContent["faultType"] == "fibre_cut"
    assert rb.structuredContent["results"][0]["runbookId"] == "RB-FIB-001"


async def test_invalid_input_and_backend_down_are_tool_errors():
    async with create_connected_server_and_client_session(mcp) as s:
        assert (await s.call_tool("get_alarms", {"site_id": "S-1"})).isError
        assert (await s.call_tool("search_runbooks", {"query": "x", "top_k": 99})).isError
        backends.TRANSPORT = httpx.MockTransport(
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("down"))
        )
        res = await s.call_tool("kpi_anomalies", {"site_id": "SITE-010"})
    assert res.isError
    assert "http://" not in res.content[0].text  # no internal URLs leak


async def test_resource_and_prompt():
    async with create_connected_server_and_client_session(mcp) as s:
        res = await s.read_resource("runbook://RB-FIB-001")
        prompts = {p.name for p in (await s.list_prompts()).prompts}
        prompt = await s.get_prompt("analyze_site", {"site_id": "SITE-010"})
    assert res.contents[0].text == "# Fibre cut"
    assert prompts == {"analyze_site"}
    assert "SITE-010" in prompt.messages[0].content.text


async def test_query_topology_impact_and_named_query():
    async with create_connected_server_and_client_session(mcp) as s:
        imp = await s.call_tool("query_topology", {"link_id": "LNK-012"})
        named = await s.call_tool(
            "query_topology", {"query": "path_to_core", "params": {"siteId": "SITE-010"}}
        )
    assert imp.structuredContent["impactedSites"][0]["siteId"] == "SITE-010"
    assert named.structuredContent["rows"] == [{"hops": 2}]


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"link_id": "LNK-012", "site_id": "SITE-010"},
        {"link_id": "LNK-012", "query": "path_to_core"},
        {"link_id": "L12"},
        {"query": "MATCH (n) DETACH DELETE n"},
        {"query": "path_to_core", "params": {str(i): i for i in range(6)}},
    ],
)
async def test_query_topology_rejects_bad_input(args):
    async with create_connected_server_and_client_session(mcp) as s:
        assert (await s.call_tool("query_topology", args)).isError


async def test_query_topology_graph_profile_down():
    backends.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(503, json={}))
    async with create_connected_server_and_client_session(mcp) as s:
        res = await s.call_tool("query_topology", {"site_id": "SITE-004"})
    assert res.isError and "topology error: HTTP 503" in res.content[0].text


async def test_search_mode_graph_is_forwarded_and_bad_mode_rejected():
    seen = []
    orig = backends.TRANSPORT

    def h(r: httpx.Request) -> httpx.Response:
        seen.append(json.loads(r.content))
        res = [{"runbookId": "RB-FIB-001", "nodeIds": ["SITE-010", "LNK-012"]}]
        return httpx.Response(200, json={"results": res})

    backends.TRANSPORT = httpx.MockTransport(h)
    try:
        async with create_connected_server_and_client_session(mcp) as s:
            rb = await s.call_tool("search_runbooks", {"query": "SITE-010 LOS", "mode": "graph"})
            bad = await s.call_tool("search_runbooks", {"query": "x", "mode": "cypher"})
    finally:
        backends.TRANSPORT = orig
    assert seen[0]["mode"] == "graph" and rb.structuredContent["mode"] == "graph"
    assert rb.structuredContent["results"][0]["nodeIds"] == ["SITE-010", "LNK-012"]
    assert bad.isError and len(seen) == 1
