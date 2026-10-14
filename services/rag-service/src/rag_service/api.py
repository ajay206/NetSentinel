from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .chunking import chunk_runbook
from .embed import get_embedder
from .ingest import ingest
from .runbooks import load_runbooks
from .search import Retriever
from .store import VectorStore

logger = logging.getLogger("rag-service")

_RUNBOOK_ID_RE = re.compile(r"^RB-[A-Z]{3}-\d{3}$")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)
    mode: Literal["vector", "bm25", "hybrid"] = "hybrid"
    faultType: str | None = None


class SearchResult(BaseModel):
    runbookId: str
    title: str
    section: str
    snippet: str
    score: float
    faultType: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    embedder: str
    results: list[SearchResult]


def build_state(app: FastAPI) -> None:
    """Ingest runbooks (idempotent) and build the retriever. Sets app.state.ready."""
    runbooks_dir = os.environ.get("RUNBOOKS_DIR", "data/runbooks")
    app.state.ready = False
    try:
        store = VectorStore(url=os.environ.get("QDRANT_URL"), path=os.environ.get("QDRANT_PATH"))
        embedder = get_embedder()
        summary = ingest(runbooks_dir, store, embedder)
        runbooks = load_runbooks(runbooks_dir)
        chunks = [c for rb in runbooks for c in chunk_runbook(rb)]
        app.state.retriever = Retriever(store, embedder, chunks)
        app.state.embedder = embedder
        app.state.chunks = chunks
        app.state.runbooks = {rb.id: rb for rb in runbooks}
        app.state.ready = True
        logger.info("rag-service ready: %s", summary)
    except Exception:
        logger.exception("rag-service ingest failed; /readyz will report 503")


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_state(app)
    yield


app = FastAPI(title="rag-service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    if not getattr(app.state, "ready", False):
        raise HTTPException(status_code=503, detail="not ready")
    return {
        "status": "ready",
        "chunks": len(app.state.chunks),
        "embedder": app.state.embedder.name,
    }


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Sync on purpose: embedding is CPU-bound, so FastAPI runs it in the threadpool."""
    if not getattr(app.state, "ready", False):
        raise HTTPException(status_code=503, detail="not ready")
    results = app.state.retriever.search(
        request.query,
        top_k=request.top_k,
        mode=request.mode,
        fault_type=request.faultType,
    )
    return SearchResponse(
        query=request.query,
        mode=request.mode,
        embedder=app.state.embedder.name,
        results=[
            SearchResult(
                runbookId=h.runbook_id,
                title=h.title,
                section=h.section,
                snippet=h.snippet,
                score=round(h.score, 4),
                faultType=h.fault_type,
            )
            for h in results
        ],
    )


@app.get("/runbooks/{runbook_id}")
async def get_runbook(runbook_id: str):
    if not _RUNBOOK_ID_RE.match(runbook_id):
        raise HTTPException(status_code=404, detail="Invalid runbook id")
    rb = getattr(app.state, "runbooks", {}).get(runbook_id)
    if rb is None:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return {
        "id": rb.id,
        "title": rb.title,
        "faultType": rb.fault_type,
        "tags": list(rb.tags),
        "markdown": rb.body,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
