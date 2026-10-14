# ADR 008 – Runbook Retrieval Service (RAG) for W8

**Status:** Accepted  
**Date:** 2026-10-14  

## Context
W8 adds the retrieval half of RAG (generation arrives with the W9 copilot) to the NetSentinel NOC AIOps platform.  A new FastAPI service (`rag-service`) must expose search over a synthetic corpus of 42 markdown runbooks.  The service must be lightweight, deterministic for CI, and avoid large model downloads.

## Decision
* **Service** – FastAPI listening on port **8004**, composed with profile `rag`.  
* **Vector store** – Qdrant (`qdrant/qdrant:v1.12.4`) on port **6333**, persisted in volume `qdrant-data`.  
* **Embedding** – Default deterministic `hash-384` embedder (hash‑based token + 3‑gram blake2b).  Optional `EMBEDDER=fastembed` to use BAAI/bge‑small‑en‑v1.5 via the `embed` extra (ONNX, no torch).  
* **Chunking** – One chunk per markdown `##` section (preamble = Overview).  Long sections are split by paragraph and then hard‑split to ≤800 chars with 100‑char overlap.  Chunk header format:  
  ```
  <title> — <section> (id; tags)
  ```  
  Chunk IDs are `<runbookId>#<n>`; Qdrant point IDs are `uuid5(chunk_id)` for idempotent re‑ingest.  
* **Search modes** – Vector (cosine), BM25 (rank‑bm25 BM25Okapi), Hybrid (Reciprocal Rank Fusion, k=60, top‑20 each).  Results are collapsed to a single hit per runbook.  An optional `faultType` hint multiplies matching runbooks’ scores by **1.2** (boost, not filter).  
* **API** –  
  * `GET /healthz` – always 200.  
  * `GET /readyz` – 503 until ingest succeeds.  
  * `POST /search` – body `{query:string (1‑500), top_k?:1‑10 (default 3), mode?: "vector"|"bm25"|"hybrid" (default "hybrid"), faultType?:string}` → results array with `{runbookId,title,section,snippet,score,faultType}`.  
  * `GET /runbooks/{id}` – returns full markdown and metadata.  

## Consequences
* **Determinism** – `hash-384` guarantees identical vectors across CI runs, enabling reproducible tests without model downloads.  
* **Container size** – The default embedder keeps the container < 256 MiB.  Switching to `fastembed` adds ~130 MiB for the ONNX model and requires internet on first run.  
* **Re‑ingest** – Changing embedder dimension triggers collection recreation; same‑dim swaps need manual collection deletion to avoid stale vectors.  
* **Fault‑type boost** – Simple multiplicative boost improves top‑1 accuracy when the W7 classifier is available, but does not filter out unrelated runbooks.  

## Alternatives considered
| Alternative | Reason for rejection |
|-------------|----------------------|
| `sentence-transformers` + PyTorch | Pulls several GBs of torch libraries, exceeding the 256 MiB container budget. |
| pgvector in TimescaleDB | Added operational complexity; Qdrant already provides vector search with built‑in cosine distance. |
| Vector‑only search | BM25 gave perfect top‑3 on the synthetic set; hybrid provides a safety net for lexical matches. |
| Cross-encoder / local-LLM reranker | Not needed to hit the target on this set and adds latency/memory; deferred. |
