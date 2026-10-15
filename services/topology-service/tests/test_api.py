"""W14: topology-service REST API on the in-memory backend."""

from __future__ import annotations

import os

os.environ.setdefault("GRAPH_BACKEND", "memory")
os.environ.setdefault("DISABLE_KAFKA", "1")
os.environ.pop("TOPOLOGY_FILE", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from topology_service import main  # noqa: E402


@pytest.fixture
def client():
    with TestClient(main.app) as c:  # lifespan loads the graph
        yield c


def test_ready_and_summary(client):
    assert client.get("/readyz").json() == {"status": "ready", "backend": "memory"}
    counts = client.get("/graph/summary").json()["counts"]
    assert counts["sites"] == 12 and counts["links"] == 14 and counts["runbooks"] >= 40


def test_impact_link(client):
    body = client.get("/graph/impact", params={"linkId": "LNK-012"}).json()
    assert body["target"] == {"type": "link", "id": "LNK-012"}
    assert [s["siteId"] for s in body["impactedSites"]] == ["SITE-010"]
    assert body["backend"] == "memory" and body["elapsedMs"] >= 0


@pytest.mark.parametrize(
    "params,status",
    [
        ({}, 400),
        ({"linkId": "LNK-012", "siteId": "SITE-004"}, 400),
        ({"linkId": "DROP"}, 400),
        ({"linkId": "LNK-999"}, 404),
        ({"siteId": "SITE-004"}, 200),
        ({"nodeId": "SITE-004-N1"}, 200),
    ],
)
def test_impact_validation(client, params, status):
    assert client.get("/graph/impact", params=params).status_code == status


def test_queries_listing_and_memory_backend(client):
    assert len(client.get("/graph/queries").json()["items"]) == 20
    assert client.post("/graph/queries/site_by_id", json={"siteId": "SITE-001"}).status_code == 501
    assert client.post("/graph/queries/nope", json={}).status_code == 404


def test_reload_is_idempotent(client):
    assert client.post("/graph/reload").json()["loaded"]["sites"] == 12


def test_not_ready_is_503(monkeypatch):
    monkeypatch.setitem(main.state, "ready", False)
    c = TestClient(main.app)  # no lifespan
    assert c.get("/graph/impact", params={"linkId": "LNK-012"}).status_code == 503
    assert c.get("/readyz").status_code == 503


def test_runbook_front_matter():
    from topology_service.load import read_runbooks

    rbs = read_runbooks("data/runbooks")
    assert len(rbs) == 42 and rbs[0] == {
        "runbookId": "RB-CEL-001",
        "title": "Cell out of service after radio fault",
        "faultType": "cell_outage",
    }
