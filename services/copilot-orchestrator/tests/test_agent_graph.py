"""W17 CI graph test: the full supervisor path with a mocked LLM and mocked services."""

from __future__ import annotations

import json

import httpx
import pytest
from copilot_orchestrator import api
from copilot_orchestrator.clients.llm import MockLLM
from copilot_orchestrator.clients.upstream import Upstream
from copilot_orchestrator.graph import tracing
from copilot_orchestrator.graph.actions import GatewayActions
from copilot_orchestrator.graph.runs import RunService
from copilot_orchestrator.graph.trigger import Seen, created
from fastapi.testclient import TestClient

from .conftest import ROOT_ID, good_answer, make_transport

INC = "INC-0123456789"


class FakeGateway:
    def __init__(self, ticket_up: bool = True) -> None:
        self.ticket_up = ticket_up
        self.posts: list[tuple[str, dict]] = []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        p = r.url.path
        if p == f"/api/incidents/{INC}":
            return httpx.Response(200, json={"id": INC, "rootSiteId": "SITE-010"})
        if p == "/api/graph/impact":
            return httpx.Response(200, json={"cellsLost": 3, "sitesIsolated": 1})
        body = json.loads(r.content or b"{}")
        self.posts.append((p, body))
        if p == "/api/tickets/drafts":
            if not self.ticket_up:
                return httpx.Response(503, json={"detail": "down"})
            return httpx.Response(201, json={"id": "TKT-00000000AA", "status": "draft"})
        if p == "/api/graph/rca":
            return httpx.Response(200, json={"finding": body, "backend": "memory"})
        return httpx.Response(404, json={})


def service(llm_answers, gw: FakeGateway) -> RunService:
    async def deps():
        return {
            "upstream": Upstream(
                "http://gw", "http://ml", "http://rag", transport=make_transport()
            ),
            "llm": MockLLM(llm_answers),
            "actions": GatewayActions("http://gw", transport=httpx.MockTransport(gw)),
        }

    return RunService(deps)


async def test_incident_runs_full_path_to_ticket_draft_after_approval():
    gw = FakeGateway()
    svc = service([good_answer()], gw)
    run = await svc.start("SITE-000", INC)
    assert run["status"] == "awaiting_approval" and run["siteId"] == "SITE-010"
    assert run["agentPath"] == ["supervisor", "triage", "rca", "remediation"]
    assert run["plan"]["steps"][0]["runbookId"] == "RB-FIB-001"
    assert gw.posts == []  # nothing written before a human decides
    names = [c["name"] for s in run["trace"] for c in s["toolCalls"]]
    assert {
        "get_incident",
        "get_alarms",
        "predict_fault",
        "search_runbooks",
        "query_topology",
    } <= set(names)
    assert "llm:mock" in names

    done = await svc.decide(run["runId"], True, "operator", "go")
    assert done["status"] == "completed" and done["ticketId"] == "TKT-00000000AA"
    assert done["agentPath"] == ["supervisor", "triage", "rca", "remediation", "approval", "report"]
    assert [s["agent"] for s in done["trace"]] == [
        "triage",
        "rca",
        "remediation",
        "approval",
        "report",
    ]
    draft = dict(gw.posts)["/api/tickets/drafts"]
    assert (
        draft["incidentId"] == INC
        and draft["siteId"] == "SITE-010"
        and ROOT_ID in draft["sourceIds"]
    )
    finding = dict(gw.posts)["/api/graph/rca"]
    assert finding["runId"] == run["runId"] and finding["ticketId"] == "TKT-00000000AA"
    assert done["kgWriteBack"]["ok"] is True and "Ticket draft: TKT-00000000AA" in done["report"]
    assert [m["agent"] for m in done["messages"]][-2:] == ["human", "report"]


async def test_rejected_plan_writes_nothing_and_second_decision_conflicts():
    from copilot_orchestrator.graph.runs import NotAwaitingApproval, RunNotFound

    gw = FakeGateway()
    svc = service([{"bad": 1}] * 3, gw)  # invalid LLM output -> deterministic fallback answer
    run = await svc.start("SITE-010", None)
    assert run["generatedBy"] == "fallback" and run["status"] == "awaiting_approval"
    out = await svc.decide(run["runId"], False, "operator", "wrong site")
    assert out["status"] == "rejected" and out["ticketId"] is None and gw.posts == []
    with pytest.raises(NotAwaitingApproval):
        await svc.decide(run["runId"], True, "operator", "")
    with pytest.raises(RunNotFound):
        svc.get("RUN-FFFFFFFFFF")


async def test_no_alarms_fails_and_ticket_outage_is_reported():
    svc = service([good_answer()], FakeGateway())
    run = await svc.start("SITE-777", None, window="15m")
    assert run["status"] == "failed" and run["agentPath"] == ["supervisor", "triage", "report"]
    svc2 = service([good_answer()], FakeGateway(ticket_up=False))
    r = await svc2.start("SITE-010", None)
    done = await svc2.decide(r["runId"], True, "admin", "")
    assert done["status"] == "completed" and done["ticketId"] is None
    assert "FAILED" in done["report"]


def test_incident_created_trigger_only_first_sighting():
    seen = Seen(cap=2)
    inc = {"id": INC, "rootSiteId": "SITE-010", "version": 1}
    assert created(inc, seen) == (INC, "SITE-010")
    assert created({**inc, "version": 2}, seen) is None  # update, already seen
    assert created({"id": "INC-AAAAAAAAAA", "rootSiteId": "SITE-010", "version": 3}, seen) is None
    assert created({"id": "bad", "rootSiteId": "SITE-010"}, seen) is None
    assert created("junk", seen) is None


async def test_langfuse_export_when_configured(monkeypatch):
    sent = []
    monkeypatch.setattr(
        tracing,
        "transport",
        httpx.MockTransport(lambda r: sent.append(json.loads(r.content)) or httpx.Response(207)),
    )
    for k, v in {
        "LANGFUSE_HOST": "http://lf",
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
    }.items():
        monkeypatch.setenv(k, v)
    svc = service([good_answer()], FakeGateway())
    run = await svc.start("SITE-010", None)
    assert run["tracing"]["langfuse"] is True
    batch = sent[0]["batch"]
    assert batch[0]["type"] == "trace-create" and batch[0]["body"]["id"] == run["runId"]
    assert [e["body"]["name"].split(":")[0] for e in batch[1:]] == ["triage", "rca", "remediation"]
    await svc.decide(run["runId"], True, "operator", "")
    assert [e["body"]["name"].split(":")[0] for e in sent[1]["batch"][1:]] == ["approval", "report"]


def test_http_api_runs_and_approval(monkeypatch):
    gw = FakeGateway()

    async def deps():
        return {
            "upstream": Upstream(
                "http://gw", "http://ml", "http://rag", transport=make_transport()
            ),
            "llm": MockLLM([good_answer()]),
            "actions": GatewayActions("http://gw", transport=httpx.MockTransport(gw)),
        }

    with TestClient(api.app) as c:
        api.app.state.runs = RunService(deps)
        assert c.post("/v2/runs", json={}).status_code == 422
        assert c.post("/v2/runs", json={"siteId": "S-1"}).status_code == 422
        run = c.post("/v2/runs", json={"siteId": "SITE-010"}).json()
        assert run["status"] == "awaiting_approval"
        assert c.get("/v2/runs").json()["items"][0]["runId"] == run["runId"]
        r = c.post(
            f"/v2/runs/{run['runId']}/approval",
            json={"approved": True},
            headers={"X-NS-User": "op1"},
        )
        assert r.json()["decision"]["by"] == "op1" and r.json()["status"] == "completed"
        assert (
            c.post(f"/v2/runs/{run['runId']}/approval", json={"approved": True}).status_code == 409
        )
        assert c.get("/v2/runs/RUN-0000000000").status_code == 404
