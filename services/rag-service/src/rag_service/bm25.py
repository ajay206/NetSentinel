from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from .chunking import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    """Lowercase tokens; hyphenated IDs (rb-fib-001) are kept whole *and* split into parts."""
    out: list[str] = []
    for tok in _TOKEN_RE.findall(text.lower()):
        out.append(tok)
        if "-" in tok or "_" in tok:
            out.extend(p for p in re.split(r"[-_]", tok) if p)
    return out


@dataclass
class BM25Index:
    chunks: list[Chunk]
    _bm25: BM25Okapi | None = None

    def __post_init__(self) -> None:
        corpus = [_tokenize(c.text) for c in self.chunks]
        # rank-bm25 divides by the corpus size, so an empty corpus gets no index.
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, limit: int = 10) -> list[tuple[Chunk, float]]:
        if self._bm25 is None:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        results = [(c, s) for c, s in zip(self.chunks, scores, strict=True) if s > 0]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
