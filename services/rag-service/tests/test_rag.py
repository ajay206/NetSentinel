from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rag_service.api import app
from rag_service.chunking import chunk_runbook
from rag_service.embed import HashEmbedder
from rag_service.ingest import ingest
from rag_service.runbooks import load_runbooks, parse_runbook
from rag_service.search import Retriever
from rag_service.store import VectorStore

RUNBOOKS = {
    "RB-FIB-001": """---
id: RB-FIB-001
title: Fibre cut on aggregation ring
faultType: fibre_cut
tags: [LOS, transport, ring]
---
# Fibre cut on aggregation ring

## Symptoms
Loss of signal on fibre ring.

## Diagnosis
Check LOS alarms on aggregation nodes.

## Remediation
Dispatch field team to repair fibre.
""",
    "RB-PWR-002": """---
id: RB-PWR-002
title: Power failure at site
faultType: power_failure
tags: [power, site]
---
# Power failure at site

## Symptoms
Site offline, no power.

## Diagnosis
Check UPS and generator status.

## Remediation
Restore mains power or switch to generator.
""",
    "RB-CON-003": """---
id: RB-CON-003
title: Congestion on link
faultType: congestion
tags: [utilization, transport]
---
# Congestion on link

## Symptoms
High utilization on link.

## Diagnosis
Check interface counters for drops.

## Remediation
Apply QoS policies to reduce utilization.
""",
    "RB-BAD-004": """---
id: RB-BAD-004
title: Bad upgrade
faultType: bad_upgrade
tags: [upgrade, software]
---
# Bad upgrade

## Symptoms
Service degradation after upgrade.

## Diagnosis
Check version and rollback plan.

## Remediation
Rollback to previous stable version.
""",
}


@pytest.fixture
def runbooks_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runbooks"
    d.mkdir()
    for rid, content in RUNBOOKS.items():
        (d / f"{rid}.md").write_text(content)
    return d


def test_parse_runbook(runbooks_dir: Path):
    rb = parse_runbook(runbooks_dir / "RB-FIB-001.md")
    assert rb.id == "RB-FIB-001"
    assert rb.title == "Fibre cut on aggregation ring"
    assert rb.fault_type == "fibre_cut"
    assert rb.tags == ("LOS", "transport", "ring")


def test_load_runbooks_sorted(runbooks_dir: Path):
    runbooks = load_runbooks(runbooks_dir)
    assert [r.id for r in runbooks] == ["RB-BAD-004", "RB-CON-003", "RB-FIB-001", "RB-PWR-002"]


def test_chunk_ids_stable(runbooks_dir: Path):
    rb = parse_runbook(runbooks_dir / "RB-FIB-001.md")
    chunks1 = chunk_runbook(rb)
    chunks2 = chunk_runbook(rb)
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]
    assert chunks1[0].chunk_id == "RB-FIB-001#0"


def test_ingest_idempotent(runbooks_dir: Path):
    store = VectorStore()
    embedder = HashEmbedder()
    summary1 = ingest(str(runbooks_dir), store, embedder)
    assert summary1["chunks"] > 0
    count1 = store.count()
    summary2 = ingest(str(runbooks_dir), store, embedder)
    assert summary2["upserted"] == summary1["chunks"]
    assert store.count() == count1 == summary1["chunks"]
    assert summary2["deleted"] == 0


def test_ingest_delete_missing(runbooks_dir: Path):
    store = VectorStore()
    embedder = HashEmbedder()
    ingest(str(runbooks_dir), store, embedder)
    (runbooks_dir / "RB-FIB-001.md").unlink()
    summary = ingest(str(runbooks_dir), store, embedder)
    assert summary["deleted"] > 0


def test_bm25_finds_exact_id(runbooks_dir: Path):
    runbooks = load_runbooks(runbooks_dir)
    chunks = []
    for rb in runbooks:
        chunks.extend(chunk_runbook(rb))
    store = VectorStore()
    embedder = HashEmbedder()
    store.ensure_collection(embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]).tolist()
    store.upsert(chunks, vectors)
    retriever = Retriever(store, embedder, chunks)
    results = retriever.search("RB-FIB-001", top_k=5, mode="bm25")
    assert results[0].runbook_id == "RB-FIB-001"


def test_hybrid_one_hit_per_runbook(runbooks_dir: Path):
    runbooks = load_runbooks(runbooks_dir)
    chunks = []
    for rb in runbooks:
        chunks.extend(chunk_runbook(rb))
    store = VectorStore()
    embedder = HashEmbedder()
    store.ensure_collection(embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]).tolist()
    store.upsert(chunks, vectors)
    retriever = Retriever(store, embedder, chunks)
    results = retriever.search("loss of signal on fibre ring LOS", top_k=10, mode="hybrid")
    runbook_ids = [h.runbook_id for h in results]
    assert len(runbook_ids) == len(set(runbook_ids))
    assert results[0].runbook_id == "RB-FIB-001"


def test_invalid_mode_raises(runbooks_dir: Path):
    runbooks = load_runbooks(runbooks_dir)
    chunks = []
    for rb in runbooks:
        chunks.extend(chunk_runbook(rb))
    store = VectorStore()
    embedder = HashEmbedder()
    store.ensure_collection(embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]).tolist()
    store.upsert(chunks, vectors)
    retriever = Retriever(store, embedder, chunks)
    with pytest.raises(ValueError):
        retriever.search("test", mode="invalid")


def test_eval_topk(runbooks_dir: Path, tmp_path: Path):
    qa_path = tmp_path / "qa.jsonl"
    qa_path.write_text(
        json.dumps({"query": "loss of signal on fibre ring", "expected": "RB-FIB-001"}) + "\n"
    )
    runbooks = load_runbooks(runbooks_dir)
    chunks = []
    for rb in runbooks:
        chunks.extend(chunk_runbook(rb))
    store = VectorStore()
    embedder = HashEmbedder()
    store.ensure_collection(embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]).tolist()
    store.upsert(chunks, vectors)
    retriever = Retriever(store, embedder, chunks)
    from rag_service.eval import evaluate

    result = evaluate(str(qa_path), retriever, k=3, mode="hybrid")
    assert result["n"] == 1
    assert result["topk"] == 1


@pytest.fixture
def client(runbooks_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RUNBOOKS_DIR", str(runbooks_dir))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_PATH", raising=False)
    monkeypatch.setenv("EMBEDDER", "hash")
    with TestClient(app) as c:  # context manager runs the lifespan (ingest)
        yield c


def test_api_health(client: TestClient):
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["chunks"] > 0


def test_api_not_ready_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RUNBOOKS_DIR", str(tmp_path / "missing"))
    (tmp_path / "missing").mkdir()
    (tmp_path / "missing" / "bad.md").write_text("no front matter")
    with TestClient(app) as c:
        assert c.get("/readyz").status_code == 503
        assert c.post("/search", json={"query": "x"}).status_code == 503


def test_api_search(client: TestClient):
    response = client.post("/search", json={"query": "loss of signal on fibre ring", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "hybrid"
    assert len(data["results"]) > 0


def test_api_invalid_top_k(client: TestClient):
    response = client.post("/search", json={"query": "test", "top_k": 42})
    assert response.status_code == 422


def test_api_runbook(client: TestClient):
    response = client.get("/runbooks/RB-FIB-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "RB-FIB-001"
    assert "Fibre cut" in data["markdown"]


def test_api_bad_runbook_id(client: TestClient):
    response = client.get("/runbooks/invalid-id")
    assert response.status_code == 404


def test_api_healthz_readyz(client: TestClient):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_empty_corpus_is_safe(tmp_path: Path):
    from rag_service.bm25 import BM25Index

    assert BM25Index([]).search("LOS") == []
    store = VectorStore()
    with pytest.raises(ValueError):
        ingest(str(tmp_path), store, HashEmbedder())


def test_fault_type_boost_never_lowers_score(runbooks_dir: Path):
    chunks = [c for rb in load_runbooks(runbooks_dir) for c in chunk_runbook(rb)]
    store = VectorStore()
    embedder = HashEmbedder()
    ingest(str(runbooks_dir), store, embedder)
    retriever = Retriever(store, embedder, chunks)
    plain = {h.runbook_id: h.score for h in retriever.search("upgrade", top_k=10, mode="vector")}
    boosted = retriever.search("upgrade", top_k=10, mode="vector", fault_type="bad_upgrade")
    for h in boosted:
        if h.fault_type == "bad_upgrade":
            assert h.score >= plain[h.runbook_id]
