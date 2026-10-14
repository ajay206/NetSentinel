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
