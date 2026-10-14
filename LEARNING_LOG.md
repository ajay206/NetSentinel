# Learning Log - NetSentinel

This log is maintained by Ajay to track learnings, insights, and key concepts encountered during the development of NetSentinel.

---

## Week 1: Setup, Repo Skeleton & Core Infrastructure (Oct 17–18, 2026)

### Focus Areas
- Monorepo bootstrapping with `uv` workspace and shared library (`ns-common`).
- Containerized core infrastructure (`Kafka KRaft` single-node, `TimescaleDB`, `Kafka UI`).
- Event streaming fundamentals: topics, partitions, keys, and consumer groups.
- Telecom standards overview: Fault Management vs. Performance Management, alarm severities (X.733), TMF642 alarm shape, and 3GPP KPI names (TS 28.552).

### Key Learnings & Notes
*(To be filled by Ajay)*

- **Why Kafka auto-create topics is disabled:**
- **Kafka KRaft vs ZooKeeper:**
- **TMF642 alarm structure takeaways:**

---

## Week 2: Simulator, Gateway & React Dashboard (Oct 14, 2026)

### Focus Areas
- Generating synthetic topology and fault scenarios (`libs/netgen`).
- Publishing TMF642‑like alarm JSON to Kafka (`netgen‑simulator`).
- Thin FastAPI gateway that aggregates health, serves recent alarms, and pushes live updates via WebSocket.
- React + Vite UI consuming the WebSocket stream, displaying severity‑coloured tables, and showing service health tiles.

### Learning Prompts for Ajay
- **WebSockets vs. polling:**  
  *What are the latency, bandwidth, and back‑pressure differences? How does the gateway handle reconnects?*  

- **aiokafka consumer groups & offset reset:**  
  *When the gateway restarts, which offset does it start from? How would you configure “latest” vs. “earliest”?*  

- **React Query (or SWR) polling strategy:**  
  *If you switched from WebSocket to periodic polling for recent alarms, what cache‑invalidation rules would you use?*  

- **Tailwind utility classes:**  
  *List the classes you used for severity colour‑coding. How would you extend the palette for a new “info” severity?*  

- **Why a thin gateway now:**  
  *Explain the trade‑off between a thin FastAPI façade and a richer microservice. How does this decision simplify testing and deployment in Week 2?*  

*(Leave space for answers as you work through the next sprint.)*

---

## Week 3: Synthetic KPI Engine, Kafka Publishing, Time‑zone Handling & SVG Map (Oct 14–20, 2026)

### Focus Areas
- **Synthetic KPI generation** (`libs/netgen`): deterministic seeding, small vs full topology, 15‑minute samples per cell, daily load seasonality (peak ~20:00 IST, trough ~04:00 IST), weekend‑offset, Gaussian noise, load‑dependent drop‑call rate.
- **Kafka publishing** (`services/netgen-simulator`): `netgen-sim kpis` sub‑command, back‑fill of historic samples, live follow mode (`--follow --interval 5`), deterministic `sampleId` UUIDs, key = `cellId` for partition ordering.
- **FastAPI gateway enhancements**: new `/api/topology` endpoint (seed & full flags via `TOPOLOGY_SEED` / `TOPOLOGY_FULL`), KPI activity endpoint `/api/kpis/activity`, WebSocket `/ws/kpis` emitting activity snapshots every 2 s.
- **NOC console UI updates**: SVG map rendering (core = square, hub = diamond, access = circle), colour‑coding by worst active alarm severity, pulsing for critical sites, hover tooltip with site details, IST timestamp display throughout UI, “stale” badge when no sample received for >60 s.
- **Documentation hygiene**: mermaid diagram label quoting, validation with `@mermaid-js/mermaid-cli`, link/image path checks.

### Learning Prompts for Ajay
- **Seasonality and noise modeling:**  
  *Explain how the sinusoidal load curve and weekend scaling are combined with Gaussian noise. Why avoid external libraries like NumPy?*  

- **Deterministic seeding & hash tests:**  
  *Describe the process that guarantees byte‑identical topology/KPI output for a given seed (e.g., SHA‑256 checksum verification).*  

- **Kafka keys (cellId) and partition ordering:**  
  *How does using `cellId` as the message key affect ordering guarantees and load balancing across partitions?*  

- **SVG map drawing logic:**  
  *Outline how the gateway translates topology JSON into SVG primitives (square, diamond, circle) and applies severity‑based fill colours.*  

- **Time‑zone handling (store UTC, display IST):**  
  *Why store all timestamps in UTC in the database and Kafka payloads, and convert to IST only at the presentation layer?*  

*(Leave space for answers as you work through the next sprint.)*

---

## Week 12: Phase 1 wrap-up and demo (Oct 2026)

### Focus Areas
- Review of all Phase 1 services and their Docker configurations.
- Execution of `make demo` to run the end‑to‑end demo path (fibre_cut scenario).
- Running the smoke test suite via `make smoke` and interpreting results.
- Understanding the new demo UI strip and its step‑by‑step flow.
- Preparing a concise 2‑minute explanation of the Phase 1 architecture.
- Discussing key trade‑offs made in each service implementation.

### Learning Prompts for Ajay
1. **Architecture Rehearsal**  
   - How would you describe the overall Phase 1 architecture, including the roles of Kafka, TimescaleDB, Qdrant, and each microservice, in roughly two minutes?

2. **Service Trade‑offs**  
   - **api‑gateway**: What are the implications of handling JWT/RBAC authentication in‑process versus delegating to an external proxy such as Traefik?  
   - **alarm‑ingest**: How does the at‑least‑once delivery guarantee interact with the deduplication and enrichment pipeline?  
   - **kpi‑service**: Why was a TimescaleDB hypertable chosen for KPI storage, and what trade‑offs does it introduce?  
   - **ml‑service**: What are the benefits and limitations of using statistical baseline models versus deeper machine‑learning models for anomaly detection?  
   - **rag‑service**: How does the hybrid BM25 + vector search approach affect relevance and performance compared to a pure vector‑only solution?  
   - **copilot‑orchestrator**: What are the trade‑offs of using a small local LLM (Ollama qwen2.5:1.5b) with Pydantic‑validated JSON and a deterministic fallback versus a larger hosted model?  
   - **mcp‑server**: In what ways does the tool‑layer abstraction add cost or benefit when exposing internal functions like `get_alarms` and `predict_fault`?

3. **Smoke Test Design**  
   - Why does the smoke test poll the gateway endpoints until they become ready instead of using a fixed sleep interval?

*(Leave space for answers.)*
