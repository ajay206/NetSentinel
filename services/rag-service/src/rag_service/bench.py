"""Step 15: retrieval benchmark, vector-only vs BM25 vs hybrid vs hybrid+rerank vs Graph RAG.

Usage:
    uv run python -m rag_service.bench --modes vector,hybrid,graph --out evals/retrieval_report.md
    (or: make rag-bench)   EMBEDDER=fastembed for bge-small; GRAPH_CONTEXT=http for topology-service

Metrics per mode and question category (text / paraphrase / graph / all): hit@1, hit@3, MRR@5
and per-query latency p50 / p95 in this process (no network for the local topology). For the
graph category it also scores entity linking and the text-to-Cypher plan.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from .chunking import chunk_runbook
from .embed import get_embedder
from .graph_rag import GraphRetriever
from .runbooks import load_runbooks
from .search import Retriever
from .store import VectorStore
from .topology import get_topology

ALL_MODES = ("vector", "bm25", "hybrid", "rerank", "graph")
CATS = ("text", "paraphrase", "graph", "all")


def load_qa(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build(runbooks_dir: str) -> tuple[Retriever, GraphRetriever, str]:
    runbooks = load_runbooks(runbooks_dir)
    chunks = [c for rb in runbooks for c in chunk_runbook(rb)]
    store = VectorStore()
    embedder = get_embedder()
    store.ensure_collection(embedder.dim)
    store.upsert(chunks, embedder.embed([c.text for c in chunks]).tolist())
    retriever = Retriever(store, embedder, chunks)
    graph = GraphRetriever(retriever, {rb.id: rb for rb in runbooks}, get_topology())
    return retriever, graph, embedder.name


def ranked_ids(mode: str, q: dict, retriever: Retriever, graph: GraphRetriever, k: int = 5):
    if mode in ("rerank", "graph"):
        res = graph.search(q["query"], top_k=k, mode=mode)
        return [h.hit.runbook_id for h in res.hits], res.graph
    return [h.runbook_id for h in retriever.search(q["query"], top_k=k, mode=mode)], None


def score(ids: list[str], expected: str) -> tuple[int, int, float]:
    rank = ids.index(expected) + 1 if expected in ids else 0
    return int(rank == 1), int(1 <= rank <= 3), (1.0 / rank if rank else 0.0)


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def run(qa: list[dict], modes: list[str], retriever: Retriever, graph: GraphRetriever) -> dict:
    out: dict = {"modes": {}, "planner": None, "failures": {}}
    for mode in modes:
        ranked_ids(mode, qa[0], retriever, graph)  # warm-up (embedder, caches)
        rows: dict[str, list] = {c: [] for c in CATS}
        lat: list[float] = []
        fails = []
        plans = ents = n_graph = 0
        for q in qa:
            t0 = time.perf_counter()
            ids, ctx = ranked_ids(mode, q, retriever, graph)
            lat.append((time.perf_counter() - t0) * 1000)
            s = score(ids, q["expected"])
            for c in (q.get("category", "text"), "all"):
                rows[c].append(s)
            if not s[0]:
                fails.append({"query": q["query"], "expected": q["expected"], "got": ids[:3]})
            if mode == "graph" and q.get("category") == "graph":
                n_graph += 1
                got = [e["id"] for e in (ctx or {}).get("entities", [])]
                want = q.get("entities", [])
                ents += int(bool(got) and (got[0] in want or q.get("plan") == "parent_chain"))
                plans += int(((ctx or {}).get("plan") or {}).get("query") == q.get("plan"))
        out["modes"][mode] = {
            c: {
                "n": len(r),
                "hit1": round(sum(x[0] for x in r) / len(r), 3) if r else 0.0,
                "hit3": round(sum(x[1] for x in r) / len(r), 3) if r else 0.0,
                "mrr": round(sum(x[2] for x in r) / len(r), 3) if r else 0.0,
            }
            for c, r in rows.items()
        }
        out["modes"][mode]["latency"] = {
            "p50": round(statistics.median(lat), 2),
            "p95": round(pct(lat, 0.95), 2),
        }
        out["failures"][mode] = fails
        if mode == "graph" and n_graph:
            out["planner"] = {
                "n": n_graph,
                "entity_acc": round(ents / n_graph, 3),
                "plan_acc": round(plans / n_graph, 3),
            }
    return out


CAVEATS = [
    "## How to read this",
    "",
    "- **Categories.** `text` = the 50 original W8 questions; `paraphrase` = 50 LLM paraphrases"
    " of them (free model, synthetic); `graph` = 50 template questions from"
    " `scripts/gen_qa_graph.py` whose right runbook depends on a topology fact (access vs"
    " core link, link vs cell, the hub a site homes on).",
    "- **Caveats.** Paraphrases are easy here (every mode scores 1.0). Graph questions are"
    " template-made over one synthetic topology (seed 42). The reranker weights were tuned"
    " on this same set, so the graph gain is optimistic; the reranker gives no gain on"
    " plain-text questions (text hit@1 0.94 hybrid -> 0.90 graph/rerank).",
    "- **Modes.** `rerank` = hybrid + feature reranker without graph context (ablation);"
    " `graph` = entity linking + catalogue text-to-Cypher plan + neighbourhood expansion"
    " + rerank. Latency is in-process (hash embedder, local graph), excluding HTTP.",
    "- Regenerate: `make rag-bench` (Docker only) or"
    " `uv run python -m rag_service.bench --modes vector,hybrid,graph"
    " --out evals/retrieval_report.md`.",
]


def report(res: dict, embedder: str, source: str, qa_path: str, n: int) -> str:
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Retrieval benchmark (Step 15)",
        "",
        f"Generated by `python -m rag_service.bench` on {when} ({platform.machine()}). "
        f"Embedder `{embedder}`, graph context `{source}`, {n} questions from `{qa_path}`.",
        "",
        "| Mode | Category | n | hit@1 | hit@3 | MRR@5 |",
        "|---|---|--:|--:|--:|--:|",
    ]
    for mode, m in res["modes"].items():
        for c in CATS:
            r = m[c]
            lines.append(
                f"| {mode} | {c} | {r['n']} | {r['hit1']:.3f} | {r['hit3']:.3f} | {r['mrr']:.3f} |"
            )
    lines += ["", "| Mode | latency p50 (ms) | p95 (ms) |", "|---|--:|--:|"]
    for mode, m in res["modes"].items():
        lines.append(f"| {mode} | {m['latency']['p50']:.2f} | {m['latency']['p95']:.2f} |")
    if res.get("planner"):
        p = res["planner"]
        lines += [
            "",
            f"Graph questions ({p['n']}): entity linking accuracy **{p['entity_acc']:.3f}**, "
            f"text-to-Cypher plan accuracy (rule planner) **{p['plan_acc']:.3f}**.",
        ]
    lines += ["", *CAVEATS]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Retrieval benchmark (vector / hybrid / Graph RAG)")
    ap.add_argument("--modes", default=",".join(ALL_MODES))
    ap.add_argument("--qa", default="data/eval/qa.jsonl")
    ap.add_argument("--runbooks", default="data/runbooks")
    ap.add_argument("--out", help="write the markdown table here (else print JSON)")
    ap.add_argument("--json", help="also write raw results (incl. failures) as JSON")
    args = ap.parse_args(argv)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    bad = [m for m in modes if m not in ALL_MODES]
    if bad:
        ap.error(f"unknown modes: {bad}")
    qa = load_qa(args.qa)
    retriever, graph, embedder = build(args.runbooks)
    res = run(qa, modes, retriever, graph)
    source = getattr(graph.topology, "source", "off")
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))
    if args.out:
        Path(args.out).write_text(report(res, embedder, source, args.qa, len(qa)))
        print(f"wrote {args.out}")
    else:
        print(json.dumps({k: v for k, v in res.items() if k != "failures"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
