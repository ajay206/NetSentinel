"""E2E (CI): POST /analyze for a fibre-cut scenario with mocked upstreams and a mocked LLM."""

from __future__ import annotations

import pytest
from copilot_orchestrator.api import app, get_llm, get_upstream
from copilot_orchestrator.clients.llm import MockLLM
from copilot_orchestrator.clients.upstream import Upstream
from fastapi.testclient import TestClient

from .conftest import ANOM_ID, ROOT_ID, good_answer, make_transport


@pytest.fixture
def client_with():
    def _make(llm):
        app.dependency_overrides[get_upstream] = lambda: Upstream(
            "http://gw", "http://ml", "http://rag", transport=make_transport()
        )
        app.dependency_overrides[get_llm] = lambda: llm
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


def test_fibre_cut_answer_is_cited(client_with):
    resp = client_with(MockLLM([good_answer()])).post(
        "/analyze", json={"site_id": "SITE-010", "window": "30m"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["generatedBy"] == "llm" and data["model"] == "mock"
    assert data["answer"]["faultType"] == "fibre_cut"
    allowed = set(data["sourceIds"])
    assert {ROOT_ID, ANOM_ID, "RB-FIB-001"} <= allowed
    for claim in data["answer"]["evidence"]:
        assert set(claim["sources"]) <= allowed
    assert [s["runbookId"] for s in data["answer"]["steps"]] == ["RB-FIB-001"]


def test_hallucinated_runbook_falls_back(client_with):
    bad = good_answer()
    bad["steps"][0]["runbookId"] = "RB-XYZ-999"
    data = client_with(MockLLM([bad])).post("/analyze", json={"site_id": "SITE-010"}).json()
    assert data["generatedBy"] == "fallback" and data["attempts"] == 3
    assert {s["runbookId"] for s in data["answer"]["steps"]} <= {"RB-FIB-001", "RB-FIB-004"}


def test_no_alarms_404_and_bad_site_422(client_with):
    c = client_with(MockLLM([good_answer()]))
    assert c.post("/analyze", json={"site_id": "SITE-777"}).status_code == 404
    assert c.post("/analyze", json={"site_id": "S-12"}).status_code == 422
    assert c.get("/healthz").json() == {"status": "ok"}
