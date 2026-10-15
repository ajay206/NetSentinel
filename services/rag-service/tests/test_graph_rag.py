"""Step 15: entity linking, facets, reranker, text-to-Cypher planner, Graph RAG and the API."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from rag_service import bench
from rag_service.api import app
from rag_service.entities import EntityLinker
from rag_service.facets import facets, node_ids, summary, type_facets
from rag_service.rerank import FeatureReranker
from rag_service.runbooks import load_runbooks
from rag_service.text2cypher import ALLOWED, LlmPlanner, PlanError, RulePlanner, validate
from rag_service.topology import HttpTopology, LocalTopology

ROOT = Path(__file__).resolve().parents[3]
RUNBOOKS = str(ROOT / "data/runbooks")


@pytest.fixture(scope="module")
def topo() -> LocalTopology:
    return LocalTopology(seed=42, small=True)


@pytest.fixture(scope="module")
def linker(topo) -> EntityLinker:
    return EntityLinker(topo)


@pytest.fixture(scope="module")
def graph_retriever():
    retriever, graph, _ = bench.build(RUNBOOKS)
    return graph


# --- entity linking ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("LOS on L-12", [("LNK-012", "link", "alias")]),
        ("LNK-012 down", [("LNK-012", "link", "id")]),
        ("link 4 and site 9", [("LNK-004", "link", "alias"), ("SITE-009", "site", "alias")]),
        ("no light at Central-Access-5", [("SITE-010", "site", "name")]),
        ("central access 5 is dark", [("SITE-010", "site", "name")]),
        ("the hub of SITE-010 is dark", [("SITE-004", "site", "relation")]),
        ("SITE-010-N1-C2 off air", [("SITE-010-N1-C2", "cell", "id")]),
        ("SITE010-N1 reboot loop", [("SITE-010-N1", "node", "alias")]),
        ("fibre cut on the ring", []),
    ],
)
def test_entity_linking(linker, text, expected):
    assert [(e.id, e.type, e.via) for e in linker.link(text)] == expected


def test_entity_linking_dedupes_and_limits(linker):
    got = linker.link("SITE-001 SITE-001 SITE-002 SITE-003 SITE-004 SITE-005")
    assert [e.id for e in got] == ["SITE-001", "SITE-002", "SITE-003"]


# --- topology context, facets, citations -------------------------------------------------


def test_local_context_matches_topology_service_shape(topo):
    import asyncio

    from topology_service.graph import MemoryGraph
    from topology_service.model import from_netgen

    g = MemoryGraph()
    asyncio.run(g.load(from_netgen(seed=42, small=True)))
    for eid in ("SITE-010", "SITE-004", "SITE-001", "LNK-012", "LNK-005", "SITE-006-N1-C1"):
        assert topo.context(eid) == asyncio.run(g.context(eid)), eid
    assert topo.context("SITE-099") is None and topo.context("LNK-099") is None


def test_facets_reflect_graph_facts(topo):
    assert facets(topo.context("LNK-012")) == {"access", "single-site", "last-mile"}
    assert facets(topo.context("LNK-005")) == {"ring", "aggregation", "transport"}
    assert facets(topo.context("LNK-001")) == {"core", "router", "transport"}
    assert facets(topo.context("SITE-004")) == {"ring", "aggregation", "transport"}
    assert facets(topo.context("LNK-010")) >= {"microwave", "access"}
    assert type_facets(topo.context("LNK-012")) == {"link", "backhaul"}
    assert type_facets(topo.context("SITE-006-N1-C1")) == {"cell", "sector"}


def test_citation_nodes_and_summary(topo):
    assert node_ids(topo.context("SITE-010")) == ["SITE-010", "LNK-012", "SITE-004"]
    assert node_ids(topo.context("LNK-012")) == ["LNK-012", "SITE-004", "SITE-010"]
    assert node_ids(topo.context("SITE-010-N1-C1")) == [
        "SITE-010-N1-C1",
        "SITE-010",
        "LNK-012",
        "SITE-004",
    ]
    assert summary(topo.context("LNK-012")) == (
        "LNK-012 is a fibre access link SITE-004 (hub) - SITE-010 (access)"
    )
    assert "homed on SITE-004" in summary(topo.context("SITE-010"))


def test_http_topology_and_fallback(topo):
    h = HttpTopology("http://topology", local=topo)
    h.transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={**topo.context("SITE-010"), "backend": "neo4j"})
    )
    assert h.context("SITE-010") == topo.context("SITE-010") and h.source == "topology-service"
    h.transport = httpx.MockTransport(lambda r: httpx.Response(404, json={}))
    assert h.context("SITE-099") is None

    def down(r):
        raise httpx.ConnectError("refused", request=r)

    h.transport = httpx.MockTransport(down)
    assert h.context("LNK-012") == topo.context("LNK-012")
    assert h.source.startswith("local")


# --- reranker ------------------------------------------------------------------------------


def test_reranker_facets_reorder_within_plausible_candidates():
    rr = FeatureReranker({rb.id: rb for rb in load_runbooks(RUNBOOKS)})
    cands = [("RB-FIB-001", 1.0), ("RB-FIB-002", 0.95), ("RB-PWR-001", 0.1)]
    plain = rr.rerank("LOS alarm", cands)
    assert plain[0].runbook_id == "RB-FIB-001"
    graph = rr.rerank("LOS alarm", cands, {"access", "single-site", "last-mile"})
    assert graph[0].runbook_id == "RB-FIB-002"
    assert graph[0].matched_facets == ["access", "last-mile", "single-site"]
    # a topology match cannot rescue a candidate the text finds implausible (gated by base)
    weak = rr.rerank("LOS alarm", [("RB-FIB-001", 1.0), ("RB-FIB-002", 0.0)], {"access"})
    assert weak[0].runbook_id == "RB-FIB-001"
    assert rr.rerank("x", []) == []


# --- text-to-Cypher planner ----------------------------------------------------------------


def test_planner_catalogue_matches_topology_service():
    from topology_service.queries import CATALOGUE

    for name, (_, params) in ALLOWED.items():
        assert CATALOGUE[name].params == params, name


@pytest.mark.parametrize(
    "q,plan",
    [
        ("LOS on L-12", ("link_by_id", {"linkId": "LNK-012"})),
        ("which sites are downstream of SITE-004", ("downstream_sites", {"siteId": "SITE-004"})),
        ("path from SITE-010 to the core", ("path_to_core", {"siteId": "SITE-010"})),
        ("neighbours of site 4", ("neighbours", {"siteId": "SITE-004", "hops": 2})),
        ("the hub of SITE-010 is dark", ("parent_chain", {"siteId": "SITE-010"})),
        ("SITE-010-N1-C2 off air", ("site_of_cell", {"cellId": "SITE-010-N1-C2"})),
        ("SITE-010 is dark", ("site_by_id", {"siteId": "SITE-010"})),
    ],
)
def test_rule_planner(linker, q, plan):
    p = RulePlanner().plan(q, linker.link(q))
    assert (p.query, p.params, p.planner) == (*plan, "rules")


def test_rule_planner_needs_an_entity(linker):
    assert RulePlanner().plan("fibre cut on the ring", []) is None


@pytest.mark.parametrize(
    "name,params",
    [
        ("drop_all", {}),
        ("site_by_id", {"siteId": "SITE-010' DETACH DELETE n //"}),
        ("site_by_id", {"siteId": "SITE-010", "extra": 1}),
        ("neighbours", {"siteId": "SITE-010", "hops": 99}),
        ("link_by_id", {"linkId": "L-12"}),
    ],
)
def test_validate_rejects(name, params):
    with pytest.raises(PlanError):
        validate(name, params)


def test_llm_planner_schema_prompt_and_fallback(linker):
    seen = []

    def good(prompt: str) -> str:
        seen.append(prompt)
        return 'Sure: {"query": "path_to_core", "params": {"siteId": "SITE-010"}}'

    ents = linker.link("how does SITE-010 reach the core")
    p = LlmPlanner(good).plan("how does SITE-010 reach the core", ents)
    assert (p.query, p.planner) == ("path_to_core", "llm")
    assert (
        "PARENT_OF" in seen[0]
        and "path_to_core(siteId)" in seen[0]
        and "SITE-010 (site)" in seen[0]
    )
    evil = LlmPlanner(lambda _: '{"query": "x", "params": {}} MATCH (n) DETACH DELETE n')
    p = evil.plan("SITE-010 is dark", linker.link("SITE-010 is dark"))
    assert (p.query, p.planner) == (
        "site_by_id",
        "rules",
    ) and "not in the catalogue" in evil.last_error


# --- Graph RAG end to end --------------------------------------------------------------------


@pytest.mark.parametrize(
    "q,expected",
    [
        ("LOS alarm raised on LNK-012, what do I do", "RB-FIB-002"),
        ("LOS alarm raised on LNK-005, what do I do", "RB-FIB-001"),
        ("the hub of SITE-010 reports LOS on its transmission", "RB-FIB-001"),
    ],
)
def test_graph_mode_uses_topology(graph_retriever, q, expected):
    res = graph_retriever.search(q, top_k=3, mode="graph")
    assert res.hits[0].hit.runbook_id == expected
    assert res.hits[0].node_ids and res.graph["entities"] and res.graph["plan"]
    assert res.graph["source"] == "local" and res.graph["summary"]


def test_rerank_mode_has_no_graph(graph_retriever):
    res = graph_retriever.search("LOS alarm raised on LNK-012", mode="rerank")
    assert res.graph is None and all(h.node_ids == [] for h in res.hits)


def test_graph_mode_without_entities_is_plain_hybrid(graph_retriever):
    res = graph_retriever.search("fan tray stopped, chassis temperature rising", mode="graph")
    assert res.hits[0].hit.runbook_id == "RB-HWD-002" and res.graph["entities"] == []


# --- benchmark + dataset -------------------------------------------------------------------


def test_qa_dataset_shape():
    qa = bench.load_qa(str(ROOT / "data/eval/qa.jsonl"))
    ids = {rb.id for rb in load_runbooks(RUNBOOKS)}
    assert len(qa) == 150 and len({q["query"] for q in qa}) == 150
    assert {q["category"] for q in qa} == {"text", "paraphrase", "graph"}
    assert all(q["expected"] in ids for q in qa)
    assert all(q.get("plan") in ALLOWED for q in qa if q["category"] == "graph")


def test_qa_graph_lines_are_generated():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_qa_graph.py"), "--check"], capture_output=True
    )
    assert r.returncode == 0, r.stdout


def test_bench_graph_beats_hybrid_on_graph_questions(tmp_path, graph_retriever):
    qa = bench.load_qa(str(ROOT / "data/eval/qa.jsonl"))
    res = bench.run(qa, ["hybrid", "graph"], graph_retriever.retriever, graph_retriever)
    g, h = res["modes"]["graph"]["graph"], res["modes"]["hybrid"]["graph"]
    assert g["hit1"] >= h["hit1"] + 0.3
    assert res["modes"]["graph"]["text"]["hit3"] >= 0.95  # no regression beyond top-1 noise
    assert res["planner"]["entity_acc"] == 1.0 and res["planner"]["plan_acc"] == 1.0
    md = bench.report(res, "hash-384", "local", "qa.jsonl", len(qa))
    assert "| graph | graph | 50 |" in md and "latency p50" in md


def test_bench_cli(tmp_path):
    out = tmp_path / "r.md"
    raw = tmp_path / "r.json"
    assert (
        bench.main(
            [
                "--modes",
                "bm25,graph",
                "--out",
                str(out),
                "--json",
                str(raw),
                "--qa",
                str(ROOT / "data/eval/qa.jsonl"),
                "--runbooks",
                RUNBOOKS,
            ]
        )
        == 0
    )
    assert "| bm25 | all | 150 |" in out.read_text()
    assert set(json.loads(raw.read_text())["modes"]) == {"bm25", "graph"}
    with pytest.raises(SystemExit):
        bench.main(["--modes", "magic"])


# --- API -------------------------------------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("RUNBOOKS_DIR", RUNBOOKS)
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_PATH", raising=False)
    monkeypatch.setenv("EMBEDDER", "hash")
    monkeypatch.setenv("GRAPH_CONTEXT", "local")
    with TestClient(app) as c:
        yield c


def test_api_graph_mode(api):
    body = api.post(
        "/search", json={"query": "LOS alarm on L-12, what now", "mode": "graph", "top_k": 3}
    ).json()
    assert body["mode"] == "graph" and body["results"][0]["runbookId"] == "RB-FIB-002"
    top = body["results"][0]
    assert top["nodeIds"] == ["LNK-012", "SITE-004", "SITE-010"]
    assert "access" in top["matchedFacets"]
    g = body["graph"]
    assert g["entities"] == [{"id": "LNK-012", "type": "link", "mention": "L-12", "via": "alias"}]
    assert g["plan"] == {"query": "link_by_id", "params": {"linkId": "LNK-012"}, "planner": "rules"}
    assert g["source"] == "local" and g["elapsedMs"] >= 0


def test_api_hybrid_mode_unchanged(api):
    body = api.post("/search", json={"query": "fibre cut", "mode": "hybrid"}).json()
    assert body["graph"] is None and body["results"][0]["nodeIds"] == []


def test_api_graph_context_off(api, monkeypatch):
    monkeypatch.setattr(app.state.graph_retriever, "topology", None)
    body = api.post("/search", json={"query": "LOS on L-12", "mode": "graph"}).json()
    assert body["graph"] is None and body["results"]
