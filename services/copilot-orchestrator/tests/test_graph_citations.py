"""Step 15: copilot uses Graph RAG; graph node ids become citable sources (real rag-service)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from copilot_orchestrator.api import app, get_llm, get_upstream
from copilot_orchestrator.clients.llm import MockLLM
from copilot_orchestrator.clients.upstream import Upstream
from fastapi.testclient import TestClient

from .conftest import ROOT_ID, good_answer, make_transport

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setenv("RUNBOOKS_DIR", str(ROOT / "data/runbooks"))
    monkeypatch.setenv("EMBEDDER", "hash")
    monkeypatch.setenv("GRAPH_CONTEXT", "local")
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_PATH", raising=False)
    from rag_service.api import app as rag_app

    with TestClient(rag_app) as c:
        yield c


def _client(rag_client, llm, seen):
    base = make_transport()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "rag":
            seen.append(json.loads(req.content))
            r = rag_client.post(
                req.url.path, content=req.content, headers={"Content-Type": "application/json"}
            )
            return httpx.Response(r.status_code, content=r.content, headers=r.headers)
        return base.handle_request(req)

    app.dependency_overrides[get_upstream] = lambda: Upstream(
        "http://gw", "http://ml", "http://rag", transport=httpx.MockTransport(handler)
    )
    app.dependency_overrides[get_llm] = lambda: llm
    return TestClient(app)


def test_fallback_answer_cites_graph_nodes(rag, monkeypatch):
    monkeypatch.setenv("RAG_MODE", "graph")
    seen: list = []
    try:
        c = _client(rag, MockLLM([{"bad": 1}]), seen)
        data = c.post("/analyze", json={"siteId": "SITE-010"}).json()
    finally:
        app.dependency_overrides.clear()
    assert seen[0]["mode"] == "graph" and seen[0]["query"].startswith("SITE-010 ")
    ctx = data["context"]
    assert ctx["retrievalMode"] == "graph"
    assert {"SITE-010", "LNK-012", "SITE-004"} <= set(ctx["graphNodes"])
    assert set(ctx["graphNodes"]) <= set(data["sourceIds"])
    claims = data["answer"]["evidence"]
    topo = [c for c in claims if c["text"].startswith("Topology context (Graph RAG)")]
    assert topo and set(topo[0]["sources"]) <= set(ctx["graphNodes"])
    assert claims[0]["sources"] == [ROOT_ID]
    assert any(r["nodeIds"] for r in ctx["runbooks"])


def test_llm_may_cite_graph_nodes_and_hybrid_mode_has_none(rag, monkeypatch):
    monkeypatch.setenv("RAG_MODE", "graph")
    ans = good_answer()
    ans["evidence"].append(
        {"text": "SITE-010 hangs off SITE-004 via LNK-012", "sources": ["LNK-012"]}
    )
    seen: list = []
    try:
        data = (
            _client(rag, MockLLM([ans]), seen).post("/analyze", json={"siteId": "SITE-010"}).json()
        )
        assert data["generatedBy"] == "llm", data["errors"]
        monkeypatch.setenv("RAG_MODE", "hybrid")
        plain = (
            _client(rag, MockLLM([good_answer()]), seen)
            .post("/analyze", json={"siteId": "SITE-010"})
            .json()
        )
    finally:
        app.dependency_overrides.clear()
    assert plain["context"]["retrievalMode"] == "hybrid" and plain["context"]["graphNodes"] == []
    assert seen[-1]["mode"] == "hybrid"
