from __future__ import annotations

import argparse
import json
import os

from .chunking import chunk_runbook
from .embed import get_embedder
from .runbooks import load_runbooks
from .store import VectorStore


def ingest(
    runbooks_dir: str,
    store: VectorStore,
    embedder,
) -> dict:
    runbooks = load_runbooks(runbooks_dir)
    all_chunks = []
    for rb in runbooks:
        all_chunks.extend(chunk_runbook(rb))
    if not all_chunks:
        raise ValueError(f"No runbooks found in {runbooks_dir}")
    store.ensure_collection(embedder.dim)
    vectors = []
    for i in range(0, len(all_chunks), 64):
        batch = all_chunks[i : i + 64]
        vectors.extend(embedder.embed([c.text for c in batch]).tolist())
    upserted = store.upsert(all_chunks, vectors)
    keep_ids = {c.chunk_id for c in all_chunks}
    deleted = store.delete_missing(keep_ids)
    return {
        "runbooks": len(runbooks),
        "chunks": len(all_chunks),
        "upserted": upserted,
        "deleted": deleted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest runbooks into the vector store.")
    parser.add_argument("dir", nargs="?", default="data/runbooks")
    parser.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL"))
    parser.add_argument("--qdrant-path", default=os.environ.get("QDRANT_PATH"))
    args = parser.parse_args()
    store = VectorStore(url=args.qdrant_url, path=args.qdrant_path)
    embedder = get_embedder()
    summary = ingest(args.dir, store, embedder)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
