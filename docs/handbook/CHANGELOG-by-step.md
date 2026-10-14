# Changelog by Step

## Step 1: Week 1 Bootstrap & Core Infrastructure
* **Date:** 2026-10-14
* **Scope:** Monorepo skeleton, `uv` workspace root, `ns-common` shared library, Docker Compose (`core` and `tools` profiles with Kafka KRaft and TimescaleDB), idempotent topic creation script (`scripts/create_topics.sh`), Makefile automation targets, ADRs, and junior developer handover guide under `docs/handbook/`.
* **Verification:**
  - `uv workspace` initialized successfully.
  - `ns-common` smoke tests passing.
  - CI pipeline and pre-commit configured.

## Step 2: Week 2 – Dashboard shell (noc-console, api-gateway, netgen-simulator)
* **Date:** 2026-10-14
* **Scope:** Added `libs/netgen` (topology generation + fibre‑cut scenario), `services/netgen-simulator` (CLI, Kafka producer of TMF642‑like alarms), `services/api-gateway` (FastAPI thin gateway, health endpoint, alarm endpoints, WebSocket broadcast), and `apps/noc-console` (React + Vite dashboard). Updated Docker Compose profiles (`ui`, `sim`). Implemented Makefile targets for running the simulator (`sim`, `sim-loop`, `sim-docker`) and the gateway (`gateway`). Defined the `alarms.raw` message schema (topic already existed from Step 1) in `contracts/asyncapi/`; added ADR-003 (gateway auth, draft).
* **Verification Checklist:**
  - [x] `pytest` passes for all Python services.
  - [x] `ruff` linting passes with no errors.
  - [x] `npm run lint && npm run typecheck` succeed for the console.
  - [x] `npm run build` produces a Vite bundle; `npm test` (Vitest) passes.
  - [ ] Docker‑based sanity checks on Mac (containers start, health endpoints report `up`, UI connects) – not possible on the build machine (no Docker); Ajay runs the 'Run on your Mac' checklist in the PR. CI does not run Docker.

## Step 3: Week 3 – Map, KPI Generation & API Enhancements
* **Date:** 2026-10-14
* **Scope:** 
  * Implemented SVG network map rendering in `apps/noc-console` (core = square, hub = diamond, access = circle; colour‑coded by worst active alarm severity).  
  * Added KPI generation (`libs/netgen` + `services/netgen-simulator kpis` sub‑command) with deterministic seeding, daily seasonality, weekend scaling, Gaussian noise, and load‑dependent drop‑call rate.  
  * Extended FastAPI gateway: new `GET /api/topology` (reads `data/topology.json` based on `TOPOLOGY_SEED`/`TOPOLOGY_FULL` env), `GET /api/kpis/activity` and WebSocket `/ws/kpis` delivering live KPI activity stats.  
  * Updated Kafka topics: `kpis` (key = `cellId`) alongside existing `alarms.raw`.  
  * Added Makefile targets `kpis-follow` (live publishing) and `kpis-peek` (sample dump).  
  * Documentation fixes: quoted mermaid labels, validated all mermaid blocks, and link‑checked markdown.
* **Verification:**
  - [x] `pytest` suite passes, including new KPI unit tests.  
  - [x] `ruff` linting clean.  
  - [x] `npm run lint && npm run typecheck && npm run build` succeed.  
  - [x] Mermaid diagrams render on GitHub after quoting.  
  - [x] SHA‑256 hash of `netgen topology` output is identical for repeated runs with the same seed (determinism test).  
  - [x] Docker sanity checks executed on Ajay’s Mac (core, sim, gateway containers start, `/api/topology` returns JSON, `/ws/kpis` streams activity).

## Step 4: Week 4 – alarm‑ingest and enriched alarm feed
* **Date:** 2026-10-14
* **Scope:**  
  * Added `services/alarm-ingest` – FastAPI service on port 8001 that consumes `alarms.raw`, normalises, enriches with deterministic topology seed, de‑duplicates (300 s window) and correlates alarms, then publishes to `alarms.enriched`.  
  * Extended `api-gateway` to consume `alarms.enriched` and expose:
    * WebSocket `/ws/enriched` – sends a snapshot followed by incremental `{"type":"enriched","alarm":…}` messages.  
    * `GET /api/alarms/enriched/recent` – returns the latest N enriched alarms.  
  * Updated `noc-console` UI with a full‑width **Enriched alarm feed** panel under *Live Alarms*:
    * Columns: Time (IST), Severity chip, Site (+ site name), Region, Node types, Problem, Dedup (×N badge), Correlation (root / ↳ rootSite / —).  
    * Summary chips: Alarms, Deduped, Groups.  
    * Rows with the same de‑dup key are replaced and moved to the top.
  * Docker Compose profile `pipeline` – runs `alarm-ingest` with `mem_limit: 160m`.  
  * Makefile targets: `make ingest`, `make up-pipeline`, `make ingest-stats`, `make enriched-peek`, `make down` (stops pipeline).  
  * Tests:
    * Pytest suite for `alarm-ingest` covering normalisation, enrichment, de‑duplication (including window expiry with a fake clock), correlation, pipeline stats and FastAPI health endpoints.  
    * Gateway tests for `/ws/enriched`.  
    * Vitest suite for the EnrichedAlarms panel and the `applyEnrichedMessage` helper.  

* **Verification:**
  - [x] `pytest` passes for alarm‑ingest and gateway.
  - [x] `ruff` linting clean.
  - [x] `npm run lint && npm run typecheck && npm run build` succeed.
  - [x] Mermaid diagram in `03-services.md` (alarm-ingest data flow) renders with quoted labels; `make docs-check` passes.
  - [ ] Docker checks on Ajay's Mac (`make up-pipeline`, `make enriched-peek`, enriched panel fills during `make sim`).

## Step 5: Week 5 – kpi-service and KPI charts

**Date:** 2026‑10‑14  

### Scope
- Implemented `kpi-service` (FastAPI) with Kafka consumer, batch writer, and TimescaleDB persistence.  
- Added plain‑SQL migrations and startup migration runner.  
- Exposed health, readiness, stats, and KPI query endpoints.  
- Updated `api-gateway` to proxy `/api/kpi/*` to the new service.  
- Implemented the “KPI charts” panel in `noc-console` using inline SVG, 15 s auto‑refresh, and IST timestamps.  
- Added Makefile targets, Docker‑Compose profile `pipeline`, and basic CI checks.

### Verification
- [x] `pytest` passes for kpi‑service (parsing, MemoryStore idempotency, aggregation, BatchWriter, API validation, migrations).  
- [x] `ruff` linting passes.  
- [x] `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` all succeed for the console.  
- [x] Documentation generated and passes `docs‑check`.  
- [ ] Docker checks on Ajay's Mac (image size, startup time).  
- [ ] End‑to‑end check (full stack) deferred to the final review step.

## Step 6: Week 6 – ml-service statistical baselines and Anomalies panel
**Date:** 2026-10-14  

### Scope
- Implement `services/ml-service` (FastAPI, STL‑like decomposition, robust Z‑score, CUSUM).  
- Add optional MLflow JSON fallback logging.  
- Expose health, readiness, and anomaly query endpoints.  
- Create read‑only proxy in `api-gateway`.  
- Build the “Anomalies” panel in `noc-console` (badge, score colours, direction arrows).  
- Draw red anomaly dots on KPI charts.  
- Provide synthetic data generation and evaluation scripts.  
- Update documentation, ADR, Makefile targets, and test suites.

### Verification
- [x] **pytest** – all unit tests for baselines, hypothesis, injection, scoring, API, and gateway pass.  
- [x] **ruff** – code style passes linting.  
- [x] **Vitest / lint / typecheck / build** – front‑end panel and chart tests succeed.  
- [x] **make docs-check** – documentation builds without errors.  
- [ ] **Docker checks on Ajay's Mac** – pending due to local environment differences.  
- [ ] **End‑to‑end check** – deferred to final review (full pipeline with real KPI data).
