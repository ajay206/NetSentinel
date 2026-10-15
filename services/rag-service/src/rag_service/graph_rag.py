"""Step 15: Graph RAG = entity linking -> neighbourhood expansion -> hybrid retrieval -> rerank.

1. ``EntityLinker`` finds sites / links / nodes / cells in the query (ids, aliases, names, and one
   "hub of X" hop).
2. Each entity's one-hop context comes from topology-service (or the local topology); it gives
   facets (e.g. *access, single-site* for an access link) and the node ids a citation may show.
3. Hybrid (vector + BM25, RRF) retrieves a candidate pool for the query expanded with the facets.
4. ``FeatureReranker`` re-scores candidates (first-stage score + facet agreement + term overlap).
5. The text-to-Cypher planner names the catalogue query that answers the topology part.

``mode="rerank"`` is the ablation: hybrid + reranker without the graph.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any

from .entities import EntityLinker
from .facets import facets as facets_of
from .facets import node_ids, summary, type_facets
from .rerank import FeatureReranker
from .runbooks import Runbook
from .search import Hit, Retriever
from .text2cypher import RulePlanner
from .topology import Topology

POOL = 12


@dataclass
class GraphHit:
    hit: Hit
    node_ids: list[str] = field(default_factory=list)
    matched_facets: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)


@dataclass
class GraphResult:
    hits: list[GraphHit]
    graph: dict[str, Any] | None


class GraphRetriever:
    def __init__(
        self,
        retriever: Retriever,
        runbooks: dict[str, Runbook],
        topology: Topology | None,
        planner: Any | None = None,
    ) -> None:
        self.retriever = retriever
        self.topology = topology
        self.linker = EntityLinker(topology)
        self.reranker = FeatureReranker(runbooks)
        self.planner = planner or RulePlanner()

    def _pool(self, query: str, fault_type: str | None) -> dict[str, Hit]:
        return {
            h.runbook_id: h
            for h in self.retriever.search(query, top_k=POOL, mode="hybrid", fault_type=fault_type)
        }

    def search(
        self, query: str, top_k: int = 3, mode: str = "graph", fault_type: str | None = None
    ) -> GraphResult:
        start = time.perf_counter()
        use_graph = mode == "graph" and self.topology is not None
        entities = self.linker.link(query) if use_graph else []
        contexts = (
            [c for c in (self.topology.context(e.id) for e in entities) if c] if use_graph else []
        )
        facets: set[str] = set().union(*(facets_of(c) for c in contexts)) if contexts else set()
        typed: set[str] = set().union(*(type_facets(c) for c in contexts)) if contexts else set()
        pool = self._pool(query, fault_type)
        floor = min((h.score for h in pool.values()), default=0.0)
        base = {rid: h.score for rid, h in pool.items()}
        if facets:  # neighbourhood expansion: also retrieve for the query + graph facets
            for rid, h in self._pool(f"{query} {' '.join(sorted(facets))}", fault_type).items():
                if rid not in pool:  # only found via the graph: enters at the pool's floor
                    pool[rid] = h
                    base[rid] = floor
        cands = [(rid, base[rid]) for rid in pool]
        ranked = self.reranker.rerank(query, cands, facets, typed)
        cite = [i for c in contexts for i in node_ids(c)]
        cite = list(dict.fromkeys(cite))
        hits = [
            GraphHit(
                hit=replace(pool[s.runbook_id], score=s.score),
                # graph-backed citation: the entities (and their uplink / parent) that support it
                node_ids=(cite if s.matched_facets else [c["id"] for c in contexts]),
                matched_facets=s.matched_facets,
                features=s.features,
            )
            for s in ranked[:top_k]
        ]
        graph = None
        if use_graph:
            plan = self.planner.plan(query, entities)
            graph = {
                "entities": [e.to_dict() for e in entities],
                "nodes": cite,
                "facets": sorted(facets | typed),
                "summary": [summary(c) for c in contexts],
                "source": getattr(self.topology, "source", "local"),
                "plan": plan.to_dict() if plan else None,
                "reranker": self.reranker.name,
                "elapsedMs": round((time.perf_counter() - start) * 1000, 2),
            }
        return GraphResult(hits, graph)
