# Runbook retrieval evaluation (W8)

## Setup
```bash
# Generate the synthetic runbook corpus (already committed)
make runbooks

# Run rag-service locally (in-memory Qdrant, no Docker)
make rag

# Ingest the runbooks into Qdrant
QDRANT_URL=http://localhost:6333 make rag-ingest   # only needed for the Docker Qdrant

# Run the evaluation (builds its own in-memory index; add EMBEDDER=fastembed for bge-small)
make rag-eval
```

The evaluation uses `data/eval/qa.jsonl`, a hand‑written set of 50 paraphrased queries with the expected runbook ID.

## Results

| Embedder | Mode   | Top‑3 Accuracy | Top‑1 Accuracy |
|----------|--------|----------------|----------------|
| **hash‑384** | Vector | 0.98 | 0.88 |
| **hash‑384** | BM25   | 1.00 | 0.98 |
| **hash‑384** | Hybrid | 1.00 | 0.94 |
| **bge‑small‑en‑v1.5** | Vector | 0.96 | 0.90 |
| **bge‑small‑en‑v1.5** | BM25   | 1.00 | 0.98 |
| **bge‑small‑en‑v1.5** | Hybrid | 1.00 | 0.96 |

*All scores meet the ≥ 0.80 top‑3 target.*

### Fault‑type hint
When the `faultType` field is supplied (derived from the W7 classifier), the hybrid mode reaches **Top‑1 = 1.00** on this dataset, representing an upper bound.

## Caveats
* The queries were authored by the same person who generated the runbooks, sharing vocabulary and phrasing.  This makes the set optimistic; real NOC queries are expected to be more diverse and will likely score lower.
* The evaluation does not include any LLM‑based reranking; future work may add a lightweight reranker to improve robustness.

## Next steps
1. **Harder held‑out queries** – collect a second set written by a different author to better gauge generalisation.  
2. **Reranker experiment** – evaluate a lightweight cross‑encoder reranker on the hybrid shortlist.  
3. **Fault‑type filtering** – explore stricter filtering (instead of a simple boost) to reduce false positives when the classifier is uncertain.
