"""Step 15: lightweight reranker (CPU, deterministic, no model download).

Score = base * (1 + facet agreement + element-type agreement) + title/tag term overlap, where base
is the min-max normalised first-stage (hybrid) score for the *original* query.
Features stay readable so the console / benchmark can explain a ranking. ``RERANKER=off``
disables it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .runbooks import Runbook

_TOK = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOP = {"a", "an", "the", "on", "of", "to", "and", "or", "in", "at", "is", "with", "after", "no"}

W_BASE, W_FACET, W_TYPE, W_TERMS = 1.0, 0.6, 0.25, 0.2


def terms(text: str) -> set[str]:
    words = set(_TOK.findall(text.lower()))
    parts = {p for w in words if "-" in w for p in w.split("-")}
    return (words | parts) - STOP


@dataclass
class Scored:
    runbook_id: str
    score: float
    features: dict[str, float] = field(default_factory=dict)
    matched_facets: list[str] = field(default_factory=list)


class FeatureReranker:
    name = "features-v1"

    def __init__(self, runbooks: dict[str, Runbook]) -> None:
        self.terms = {rid: terms(f"{rb.title} {' '.join(rb.tags)}") for rid, rb in runbooks.items()}

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, float]],
        facets: set[str] | None = None,
        type_facets: set[str] | None = None,
    ) -> list[Scored]:
        if not candidates:
            return []
        facets = facets or set()
        type_facets = type_facets or set()
        scores = [s for _, s in candidates]
        lo, hi = min(scores), max(scores)
        q = terms(query)
        out = []
        for rid, raw in candidates:
            rb_terms = self.terms.get(rid, set())
            base = 1.0 if hi == lo else (raw - lo) / (hi - lo)
            matched = sorted(facets & rb_terms)
            facet = min(len(matched), 2) / 2 if facets else 0.0
            typed = sorted(type_facets & rb_terms)
            tfacet = 1.0 if typed else 0.0
            overlap = len(q & rb_terms) / max(len(rb_terms), 1)
            feats = {
                "base": round(base, 4),
                "facet": facet,
                "type": tfacet,
                "terms": round(overlap, 4),
            }
            # the graph only reorders what the text already finds plausible: facet boosts scale
            # with the first-stage score, so a topology match cannot drag in another fault family
            score = W_BASE * base * (1 + W_FACET * facet + W_TYPE * tfacet) + W_TERMS * overlap
            matched = matched + [t for t in typed if t not in matched]
            out.append(Scored(rid, round(score, 6), feats, matched))
        out.sort(key=lambda s: (-s.score, s.runbook_id))
        return out
