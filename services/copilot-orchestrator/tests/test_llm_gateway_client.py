"""W18: the copilot reaches models only via llm-gateway; route/latency/redactions surface."""

from __future__ import annotations

import json

import httpx
from copilot_orchestrator.analyze import analyze
from copilot_orchestrator.clients.llm import GatewayLLM
from copilot_orchestrator.models import AnalyzeRequest

from .conftest import good_answer


def gateway(status: int, body: dict, seen: dict | None = None) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen["auth"] = req.headers.get("authorization")
            seen["path"] = req.url.path
            seen["body"] = json.loads(req.read())
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


async def test_answer_via_gateway_reports_model_route(upstream):
    seen: dict = {}
    ok = {
        "content": json.dumps(good_answer()),
        "route": "ollama:qwen2.5:1.5b",
        "latencyMs": 812.5,
        "redactions": {"total": 2, "types": {"EMAIL": 2}},
    }
    llm = GatewayLLM("http://llm-gateway:8010", token="tok", transport=gateway(200, ok, seen))
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, llm)
    assert res.generatedBy == "llm" and res.model == "ollama:qwen2.5:1.5b"
    assert res.llm and res.llm.route == "ollama:qwen2.5:1.5b" and res.llm.redactions == 2
    assert res.llm.latencyMs == 812.5
    assert seen["path"] == "/v1/complete" and seen["auth"] == "Bearer tok"
    assert seen["body"]["schema"]["title"] == "Answer"


async def test_guard_block_falls_back_and_says_why(upstream):
    blocked = {"detail": {"error": "prompt_injection", "reasons": ["override"]}}
    llm = GatewayLLM("http://g", transport=gateway(400, blocked))
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, llm)
    assert res.generatedBy == "fallback" and res.model is None and res.attempts == 1
    assert res.llm and res.llm.blocked == ["override"] and res.llm.route is None
    assert "blocked by llm-gateway guard" in res.errors[0]


async def test_gateway_down_or_no_route_falls_back(upstream):
    llm = GatewayLLM("http://g", transport=gateway(503, {"detail": "no route available"}))
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, llm)
    assert res.generatedBy == "fallback" and "llm-gateway 503" in res.errors[0]
