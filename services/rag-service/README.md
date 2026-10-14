# rag-service

Runbook retrieval service for NOC alarms. Retrieves the correct runbook for a given alarm using hybrid vector + BM25 search.

## Usage

```bash
# Ingest runbooks
rag-ingest data/runbooks

# Run API
uvicorn rag_service.api:app --host 0.0.0.0 --port 8004
```

## Environment

- `RUNBOOKS_DIR` — directory with `data/runbooks/*.md` (default: `data/runbooks`)
- `QDRANT_URL` — Qdrant server URL (default: in-memory)
- `EMBEDDER` — `hash` (default) or `fastembed`
- `PORT` — API port (default: 8004)
