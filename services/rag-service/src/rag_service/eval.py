from __future__ import annotations

import argparse
import json

from .chunking import chunk_runbook
from .embed import get_embedder
from .runbooks import load_runbooks
from .search import Retriever
from .store import VectorStore


def evaluate(
    qa_path: str,
    retriever: Retriever,
    k: int = 3,
    mode: str = "hybrid",
    use_fault_type: bool = False,
) -> dict:
    """Top-1 / top-k accuracy. ``use_fault_type`` passes the gold faultType as the boost hint
    (an upper bound for when the W7 classifier is right); off by default so the headline
    number is pure retrieval."""
    with open(qa_path, encoding="utf-8") as f:
        queries = [json.loads(line) for line in f if line.strip()]
    hits = 0
    top1 = 0
    topk = 0
    for q in queries:
        results = retriever.search(
            q["query"],
            top_k=k,
            mode=mode,
            fault_type=q.get("faultType") if use_fault_type else None,
        )
        if not results:
            continue
        if results[0].runbook_id == q["expected"]:
            top1 += 1
        if any(r.runbook_id == q["expected"] for r in results):
            topk += 1
            hits += 1
    return {
        "n": len(queries),
        "hits": hits,
        "top1": top1,
        "topk": topk,
        "top1_acc": round(top1 / len(queries), 3) if queries else 0.0,
        "topk_acc": round(topk / len(queries), 3) if queries else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate runbook retrieval.")
    parser.add_argument("--qa", default="data/eval/qa.jsonl")
    parser.add_argument("--runbooks", default="data/runbooks")
    parser.add_argument("--mode", default="all")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--use-fault-type", action="store_true", help="boost gold faultType")
    args = parser.parse_args()
    runbooks = load_runbooks(args.runbooks)
    chunks = []
    for rb in runbooks:
        chunks.extend(chunk_runbook(rb))
    store = VectorStore()
    embedder = get_embedder()
    store.ensure_collection(embedder.dim)
    vectors = embedder.embed([c.text for c in chunks]).tolist()
    store.upsert(chunks, vectors)
    retriever = Retriever(store, embedder, chunks)
    if args.mode == "all":
        for mode in ("vector", "bm25", "hybrid"):
            result = evaluate(args.qa, retriever, args.k, mode, args.use_fault_type)
            print(json.dumps({"mode": mode, "embedder": embedder.name, **result}))
    else:
        result = evaluate(args.qa, retriever, args.k, args.mode, args.use_fault_type)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
