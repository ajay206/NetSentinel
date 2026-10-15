# ADR-014 – Neo4j knowledge graph for topology impact and RCA
**Status:** Accepted (Step 14). Builds on ADR-001 (knowledge graph + RAG) and ADR-012 (incident clustering).

## Context
NOC engineers ask topology questions: "which cells lose service if link LNK-012 fails?", "what is the path from this site to the core?", "which sites are single-homed?". Until now topology lived only as JSON inside services (incident-service walks it in Python). The build plan (W14) calls for a network knowledge graph with ~20 queries, a REST API, an MCP tool and a console impact panel, with impact answers in under 100 ms, on laptops with 8 GB of RAM and only Docker installed.

## Decision
- **Store:** Neo4j 5 Community (`neo4j:5.26-community`, multi-arch) in a new compose profile `graph`, off by default. Memory is capped at 512 MB heap, 256 MB page cache and `mem_limit: 1g`. The 60-site graph is about 1k nodes, so this is generous. Ports are bound to 127.0.0.1 and the password comes from `.env`.
- **Model:**
  - nodes: `Site`, `Node`, `Cell`, `Alarm`, `Runbook`, `Ticket`;
  - relationships `HAS_NODE`, `HAS_CELL`, `LINK {linkId, kind, role}` between sites, the `PARENT_OF` homing tree, and `RAISED_ON` for alarms;
  - uniqueness constraints on every business id;
  - the loader rebuilds the topology in one write transaction on every start and keeps alarms.
- **Impact semantics:** a failed link or site isolates every non-core site that has no `LINK` path of ≤ 8 hops to a surviving core site avoiding the failure. A failed node only loses its own cells. The query is a single `NOT EXISTS { MATCH p = (s)-[:LINK*1..8]-(c:Site {kind:'core'}) WHERE none(...) }`, read-routed.
- **Query surface:** a fixed catalogue of 20 named, parameterised, read-only Cypher queries. There is no free-form Cypher over HTTP or MCP. `hops` and `limit` are clamped, and tests reject write clauses.
- **Fallback backend:** `GRAPH_BACKEND=memory` answers `/graph/impact` with a BFS over the same model, for tests, CI without Neo4j and low-RAM laptops. An opt-in integration test (`NEO4J_TEST_URI`) asserts that both backends agree on every link, site and node of both topologies.
- **Access:** through the gateway only. `/api/graph/*` needs viewer; `POST /api/graph/reload` needs admin and is audited (Step 13b RBAC). The MCP `query_topology` tool calls the gateway with the service token.

## Alternatives considered
- **Keep using NetworkX / Python graphs in each service:** no extra container, but it gives no query language, no shared model for RCA/RAG (ADR-001) and no Cypher catalogue for the copilot. Kept only as the memory fallback.
- **Memgraph:** fast and Cypher-compatible, but larger images and an in-memory footprint. Neo4j Community has better tooling (Browser) and is what the build plan names.
- **Postgres recursive CTEs / Apache AGE:** reuses TimescaleDB, but recursive "no path avoiding X" queries are awkward. AGE has no official multi-arch image.

## Consequences
- **Latency:** impact queries take about 5–6 ms p50 on Neo4j 5.26 (12 and 60 sites). The first query after start takes 150–600 ms while it is planned, so smoke warms it up before measuring.
- **Memory:** the `graph` profile adds about 1.2 GB. It stays opt-in, and 8 GB machines may need to stop `rag`/`copilot` while using it.
- **Password:** Neo4j keeps its password in its volume, so changing `NEO4J_PASSWORD` needs a volume reset (troubleshooting #69).
- **Deferred:** tickets (incidents) and alarm→runbook relationships are not mirrored yet; the constraints are in place for a later step.
