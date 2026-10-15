"""Step 15: entity context (one-hop neighbourhood) used by Graph RAG."""

from __future__ import annotations

import os

os.environ.setdefault("GRAPH_BACKEND", "memory")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from topology_service import main  # noqa: E402
from topology_service.graph import MemoryGraph, UnknownTarget, entity_type  # noqa: E402
from topology_service.model import from_netgen  # noqa: E402


@pytest.fixture
async def g() -> MemoryGraph:
    m = MemoryGraph()
    await m.load(from_netgen(seed=42, small=True))
    return m


@pytest.mark.parametrize(
    "eid,kind",
    [
        ("SITE-010", "site"),
        ("LNK-012", "link"),
        ("SITE-010-N1", "node"),
        ("SITE-010-N1-C2", "cell"),
        ("L-12", None),
        ("SITE-1", None),
    ],
)
def test_entity_type(eid, kind):
    assert entity_type(eid) == kind


async def test_access_site_context(g):
    c = await g.context("SITE-010")
    assert c["site"] == {
        "siteId": "SITE-010",
        "name": "Central-Access-5",
        "kind": "access",
        "region": "Central",
    }
    assert c["parent"] == "SITE-004" and c["children"] == []
    assert c["links"] == [
        {"linkId": "LNK-012", "peer": "SITE-004", "kind": "fibre", "role": "access"}
    ]


async def test_hub_link_node_and_cell_context(g):
    hub = await g.context("SITE-004")
    assert hub["site"]["kind"] == "hub" and hub["children"] == ["SITE-009", "SITE-010"]
    assert {x["linkId"] for x in hub["links"]} == {"LNK-004", "LNK-005", "LNK-011", "LNK-012"}
    link = await g.context("LNK-012")
    assert link["link"] == {
        "linkId": "LNK-012",
        "a": "SITE-004",
        "b": "SITE-010",
        "kind": "fibre",
        "role": "access",
        "aKind": "hub",
        "bKind": "access",
    }
    cell = await g.context("SITE-010-N1-C2")
    assert cell["node"] == {"nodeId": "SITE-010-N1", "kind": "router"}
    assert cell["site"]["siteId"] == "SITE-010" and cell["type"] == "cell"


@pytest.mark.parametrize("eid", ["SITE-099", "LNK-099", "SITE-010-N9", "SITE-010-N1-C9"])
async def test_unknown(g, eid):
    with pytest.raises(UnknownTarget):
        await g.context(eid)


def test_context_api():
    with TestClient(main.app) as c:
        assert c.get("/graph/context/LNK-012").json()["link"]["role"] == "access"
        assert c.get("/graph/context/SITE-004").json()["backend"] == "memory"
        assert c.get("/graph/context/DROP").status_code == 400
        assert c.get("/graph/context/SITE-099").status_code == 404


@pytest.fixture
def client_memory_rca():
    with TestClient(main.app) as c:
        yield c


def test_rca_write_back_memory(client_memory_rca):
    c = client_memory_rca
    body = {
        "runId": "RUN-0123456789",
        "siteId": "SITE-010",
        "incidentId": "INC-0123456789",
        "faultType": "fibre_cut",
        "confidence": 0.8,
        "summary": "Fibre cut on LNK-012",
        "approvedBy": "operator",
        "runbookIds": ["RB-FIB-001", "RB-NOPE-999"],
        "ticketId": "TKT-0123456789",
    }
    r = c.post("/graph/rca", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["finding"]["runbookIds"] == ["RB-FIB-001"]
    assert c.post("/graph/rca", json=body).status_code == 200  # idempotent per runId
    items = c.get("/graph/rca/SITE-010").json()["items"]
    assert len(items) == 1 and items[0]["ticketId"] == "TKT-0123456789"
    assert c.post("/graph/rca", json={**body, "siteId": "SITE-999"}).status_code == 404
    assert c.post("/graph/rca", json={**body, "bogus": 1}).status_code == 422
    assert c.get("/graph/rca/S-1").status_code == 400
