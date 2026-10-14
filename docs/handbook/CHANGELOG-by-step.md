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
