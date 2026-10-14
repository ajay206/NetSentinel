from __future__ import annotations

from dataclasses import dataclass

from .bm25 import BM25Index
from .chunking import Chunk
from .embed import Embedder
from .store import VectorStore


@dataclass(frozen=True)
class Hit:
    runbook_id: str
    title: str
    section: str
    snippet: str
    score: float
    fault_type: str
    chunk_id: str


def _snippet(text: str) -> str:
    lines = text.split("\n", 1)
    content = lines[1] if len(lines) > 1 else text
    collapsed = " ".join(content.split())
    return collapsed[:240]


def _rrf(ranks: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal rank fusion with 1-based ranks."""
    scores: dict[str, float] = {}
    for rank_list in ranks:
        for position, key in enumerate(rank_list, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + position)
    return scores


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        chunks: list[Chunk],
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.chunks = chunks
        self.bm25 = BM25Index(chunks)
        self._by_id = {c.chunk_id: c for c in chunks}

    def _ranked(self, query: str, mode: str, pool: int = 20) -> dict[str, float]:
        """Chunk-id -> score for the requested mode (higher is better)."""
        if mode == "bm25":
            return {c.chunk_id: float(s) for c, s in self.bm25.search(query, limit=pool)}
        vector = self.embedder.embed([query])[0].tolist()
        vec_hits = [(p["chunk_id"], float(s)) for p, s in self.store.search(vector, limit=pool)]
        if mode == "vector":
            return dict(vec_hits)
        bm25_ids = [c.chunk_id for c, _ in self.bm25.search(query, limit=pool)]
        return _rrf([[cid for cid, _ in vec_hits], bm25_ids])

    def search(
        self,
        query: str,
        top_k: int = 3,
        mode: str = "hybrid",
        fault_type: str | None = None,
    ) -> list[Hit]:
        if mode not in ("vector", "bm25", "hybrid"):
            raise ValueError(f"Invalid mode: {mode}")
        best: dict[str, tuple[Chunk, float]] = {}
        for chunk_id, raw in self._ranked(query, mode).items():
            chunk = self._by_id.get(chunk_id)
            if chunk is None:  # stale point from an older ingest
                continue
            score = raw
            if fault_type and chunk.fault_type == fault_type:
                score = raw + abs(raw) * 0.2  # +20%, still a boost when cosine is negative
            if chunk.runbook_id not in best or score > best[chunk.runbook_id][1]:
                best[chunk.runbook_id] = (chunk, score)
        hits = [
            Hit(
                runbook_id=chunk.runbook_id,
                title=chunk.title,
                section=chunk.section,
                snippet=_snippet(chunk.text),
                score=round(score, 6),
                fault_type=chunk.fault_type,
                chunk_id=chunk.chunk_id,
            )
            for chunk, score in best.values()
        ]
        hits.sort(key=lambda h: (-h.score, h.runbook_id))
        return hits[:top_k]
