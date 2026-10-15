# ADR-015 – Graph RAG: entity linking, catalogue text-to-Cypher, neighbourhood expansion, rerank
**Status:** Accepted (Step 15). Builds on ADR-001 (knowledge graph + RAG), ADR-008 (runbook retrieval) and ADR-014 (Neo4j topology graph).

## Context
Hybrid retrieval (ADR-008) matches words, but the right runbook often depends on a topology fact the query does not state. A LOS on SITE-010 (an access site on a single link) needs the last-mile fibre runbook, not the ring one. "High utilisation on LNK-005" is a core link, not a cell. "The hub of SITE-010" means SITE-004. The build plan (W15) asks for entity linking, text-to-Cypher with schema prompting, neighbourhood expansion and a reranker. It also asks for a measured vector vs hybrid vs Graph RAG benchmark and node-ID citations in the console. Constraints: no paid APIs, laptops with 8 GB of RAM, the `graph` profile optional.

## Decision
- **Entity linking:** deterministic regexes and dictionaries (ids, aliases, site names, "hub/parent/upstream of X" relations). It is not an NER model: the ids are structured, and this is exact, fast (< 1 ms) and testable.
- **Text-to-Cypher:** the planner chooses a **named catalogue query** (10 of the 20 from ADR-014) and its parameters from a schema prompt. It never emits free-form Cypher. The output is validated against the allow-list; an LLM planner is optional and falls back to the rule planner.
- **Expansion:** `GET /graph/context/{id}` (topology-service, both backends) returns the site, parent, children, links and alarms. rag-service can compute the same shape in-process from netgen (`GRAPH_CONTEXT=local`, default and fallback), so Graph RAG works without Neo4j. A test asserts that the Neo4j and memory shapes are identical.
- **Rerank:** a transparent feature reranker (`features-v1`). Score = normalised hybrid score × (1 + 0.6·facet match + 0.25·type match) + 0.2·term overlap over a pool of 12; candidates found only through the graph enter at the pool floor. No cross-encoder: it would be a ~100 MB+ model, slow on CPU, and it cannot see topology facts.
- **Citations:** each hit carries `nodeIds`. The copilot puts them in `context.graphNodes`, which makes them valid `sourceIds` (the W9 citation guard still applies). The console shows node chips and a "retrieval mode: graph" badge.
- **Topology vector index:** deferred. Node embeddings would duplicate the embedder in a second service and add nothing for id/name lookups, which linking already handles exactly.

## Alternatives considered
- **LLM-generated Cypher:** flexible, but unsafe (writes, expensive scans) and non-deterministic on small local models. The catalogue keeps ADR-014's read-only guarantee.
- **Graph embeddings / GNN retrieval:** needs training data we do not have; the topology is small and explicit.
- **Neo4j vector index:** couples retrieval to the optional `graph` profile.

## Consequences
- Benchmark (`evals/retrieval_report.md`, hash embedder): on graph questions hit@1 goes from 0.26 (hybrid) to 0.80 (graph), and overall hit@1 from 0.73 to 0.90. Text questions drop slightly (0.94 → 0.90) from the term-overlap feature. p95 is about 2.5 ms in-process.
- **Caveats:** graph questions are template-made over one synthetic topology, weights were tuned on the same set, and paraphrases are too easy (1.0 everywhere). A held-out set and a real cross-encoder comparison are future work.
- Facet tables (`facets.py`) must be updated when new site kinds or runbook families are added.
