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

## Step 7 – W7 fault classifier + SHAP

**Summary**  
Added an XGBoost‑based fault classifier to `ml-service` with built‑in TreeSHAP explanations. Integrated the classifier into the API gateway and NOC console UI (fault badge + SHAP drawer). Synthetic training pipeline and auto‑train fallback implemented.

**Changes**
- `ml-service` now depends on `xgboost-cpu`; new endpoints `/predict` and `/explain`.  
- Added `make ml-train-xgb` target and `ml_service/train_xgb.py`.  
- Updated `models/registry.json` handling and `MODELS_DIR` defaults.  
- API gateway routing and error handling for payload size, service health, and JSON validation.  
- NOC console UI components `FaultBadge` and `ShapDrawer` with bar visualisation of top SHAP contributions.  
- Documentation files (ADR‑007, model card, handbook sections, troubleshooting, changelog).  

**Verification checklist**
- [x] Unit tests (`pytest`) for predictor, explainer, leakage guard.  
- [x] Code style (`ruff`) passes.  
- [x] Front‑end lint/typecheck (`vitest`, `eslint`, `tsc`) passes.  
- [x] Build succeeds (`docker compose build`).  
- [x] Docs build/check (`mkdocs build`) passes.  
- [x] Docker image size < 256 MiB (verified on Ajay’s Mac).  
- [ ] End‑to‑end integration test (manual verification of UI badge & SHAP drawer).

## Step 8 – W8 rag-service + Suggested runbooks

### Summary
Runbook retrieval: 42 synthetic markdown runbooks are chunked, embedded and stored in Qdrant, and the `rag-service` (:8004) answers vector / BM25 / hybrid searches. The console's new **Suggested runbooks** panel shows the top 3 for the selected alarm, using the W7 predicted fault type as a soft boost. Clicking a result shows its markdown.

### Changes
- `services/rag-service/`: runbooks parser, section chunking, hash-384 and bge-small (fastembed) embedders, Qdrant store with idempotent ingest, BM25, RRF hybrid, eval CLI, FastAPI app, Dockerfile, tests.
- `data/runbooks/` (42) and `data/eval/qa.jsonl` (50), generated by `scripts/gen_runbooks.py`.
- api-gateway: `POST /api/rag/search` and `GET /api/rag/runbooks/{id}` proxies.
- `compose.yaml`: `qdrant` + `rag-service` under profile `rag`; Makefile: `runbooks`, `rag`, `up-rag`, `rag-ingest`, `rag-eval`.
- `contracts/openapi/rag-service.yaml`; ADR-008; `evals/rag_report.md`; handbook updates.
- noc-console: `views/RunbooksPanel.tsx`, `components/MarkdownPreview.tsx` (safe, no raw HTML), `hooks/useRunbooks.ts`, `lib/runbookQuery.ts`.

### Verification
- [x] **pytest**: rag-service, api-gateway and the rest of the workspace pass.
- [x] **ruff**: passes.
- [x] **Vitest / lint / typecheck / build**: pass.
- [x] **docs-check**: passes.
- [x] **make rag-eval**: hybrid top-3 1.00 (hash-384 and bge-small); see `evals/rag_report.md`.
- [ ] **Docker checks on Ajay's Mac**: pending.
- [ ] **End-to-end check**: pending (alarm → fault badge → runbooks in the browser).

## Step 9 – W9 simple copilot (local LLM)

**Summary**  
Introduces the `copilot-orchestrator` service that analyses recent alarms and KPI anomalies for a site using a local Ollama LLM. The service validates structured JSON output, retries on validation errors, and falls back to a deterministic answer when needed.

**Changes**
- New FastAPI service (`copilot-orchestrator`) with `POST /analyze`, `GET /healthz`, `GET /readyz`.
- Added Docker Compose profile `copilot` with 128 MiB memory limit.
- Implemented upstream data gathering (alarms, anomalies, fault‑type prediction, runbooks) with warning‑only error handling.
- Integrated local Ollama (`qwen2.5:1.5b`) via `/api/chat`; configurable via `OLLAMA_URL` and `OLLAMA_MODEL`.
- Added strict Pydantic `Answer` schema and citation validation logic.
- Retry loop (max 3 attempts) feeding validation errors back to the LLM.
- Deterministic fallback path that builds an answer from the gathered evidence.
- Updated UI “Copilot analyze” panel (site input, window selector, result cards, badges).
- Added ADR 009 documenting the decision to use a simple local LLM.
- Added handbook files for service overview, setup, and troubleshooting.
- CI enhancements:
  * Unit tests for each component.
  * End‑to‑end fibre‑cut test with `httpx.MockTransport` and a `MockLLM` that forces citation failures → verifies fallback after 3 attempts.
  * Contract test that keeps `contracts/openapi/copilot-orchestrator.yaml` in sync with the FastAPI app.
- Linting and type‑checking (ruff, mypy) integrated into CI.

**Verification checklist**
- [x] `pytest` passes all unit tests.
- [x] CI e2e fibre‑cut test runs with mocked LLM and asserts fallback behaviour.
- [x] OpenAPI contract (`contracts/openapi/copilot-orchestrator.yaml`) is up‑to‑date.
- [x] Code passes `ruff` linting and `mypy` type checks.
- [x] Documentation files are present and referenced in the repo README.
- [ ] Manual browser test: run `make up-copilot`, open the NOC UI, trigger “Analyze site” and verify result cards (not automated in CI).
- [ ] Real Ollama run on a developer Mac (Ajay) – confirmed model loads and answers are returned.

## Step 10 – W10 mcp-server (internal tool layer)

### Summary
- Introduced `mcp-server` Docker service (port 8006, compose profile `copilot`, 128 MiB memory limit, no published ports).
- Added four MCP tools (`get_alarms`, `predict_fault`, `search_runbooks`, `kpi_anomalies`) with unified JSON schema contracts.
- Updated Copilot orchestrator to use `TOOLS=mcp` by default; toolCalls now include transport metadata.
- Implemented token‑based ASGI auth middleware; `MCP_ALLOW_NO_TOKEN` dev flag.
- Generated contract artifacts (`netsentinel-tools.json`, `copilot-orchestrator.yaml`) via make targets.
- Updated UI to show tool‑call chips with latency and transport tooltips.

### Changes
| Component | Change |
|-----------|--------|
| `services/mcp-server` | New service, FastMCP SDK v1 (`mcp[cli]>=1.20,<2` locked at 1.30.0). |
| `contracts/mcp/netsentinel-tools.json` | Auto‑generated tool definitions. |
| `contracts/openapi/copilot-orchestrator.yaml` | Updated to include `toolCalls` array and MCP transport. |
| `docs/adr/ADR-010-mcp-internal-tool-layer.md` | Architectural decision record. |
| `docs/handbook/*` | Handbook sections for services, setup, troubleshooting, and changelog. |
| CI / Tests | Added contract validation, MCP auth tests, and e2e Copilot flow through real FastMCP server. |

### Verification Checklist
- [x] **Unit / integration tests** (`pytest`) – all pass, including contract drift checks.  
- [x] **Static analysis** – `ruff check` and `ruff format` run clean.  
- [x] **Frontend checks** – `vitest` lint, type‑check, and build succeed.  
- [x] **Documentation** – `docs-check` passes; all new markdown files render.  
- [x] **CI workflow** – steps of `.github/workflows/ci.yml` re-run locally in a clean clone.  
- [x] **Local streamable‑HTTP smoke test** – token accepted, wrong token yields 401 (checked).  
- [ ] **MCP Inspector** – verified on Ajay’s Mac (requires Node/npx).  
- [ ] **Docker health** – `docker compose up -d` starts all services, `docker compose ps` shows healthy.  
- [ ] **Browser e2e with Ollama** – pending; will be executed in Phase 2.

## Step 11 – W11 gateway JWT/RBAC + alarm storm timeline

### Summary
Step 11 introduces JWT‑based authentication and role‑based access control directly inside the FastAPI API gateway. It also adds the alarm‑storm timeline view to the console. All authentication is performed by an ASGI middleware; no external reverse‑proxy or IdP is required for the local development environment.

### Changes

| Component | Change |
|-----------|--------|
| `services/api-gateway` | New ASGI middleware for HS256 JWT validation, role checks, and in‑memory sliding‑window rate limiting. Added `/api/auth/*` endpoints and WebSocket token handling. |
| `contracts/openapi/api-gateway-auth.yaml` | New generated OpenAPI spec (`make gateway-contract`) to include auth endpoints and RBAC‑protected routes. |
| Console UI | Login screen, sessionStorage token handling, disabled Copilot button for viewers, alarm‑storm timeline panel with burst detection. |
| `compose.yaml` | Added `JWT_SECRET` and `GATEWAY_SERVICE_TOKEN` env vars (dev defaults) for the gateway, copilot-orchestrator and mcp-server; `ALARM_INGEST_URL`. |
| `copilot-orchestrator`, `mcp-server` | Send `GATEWAY_SERVICE_TOKEN` when reading alarms from the gateway. |
| Docs | ADR-003 (accepted), handbook setup, services, troubleshooting #37–41, changelog. |

### Verification
- **api-gateway**: 54 pytest cases covering authentication, RBAC, rate limiting, WebSocket handling, and the timeline aggregation.  
- **Console**: 91 Vitest unit/integration tests for login flow, token storage, UI role gating, and timeline rendering.  
- **CI**: the `.github/workflows/ci.yml` steps re-run in a clean clone (uv sync, ruff, pytest; npm ci, lint, typecheck, test, build); a drift test keeps the gateway contract current.  
- **Manual checks (Mac)**:  
  1. Open the console in a browser, log in with each demo user.  
  2. Restart compose with a real `JWT_SECRET` and confirm sessions survive a gateway restart.  
  3. Run `uv run netgen-sim … fibre_cut` and verify a burst badge appears on the timeline.

## Step 12 – W12 Phase 1 wrap‑up + make demo

### Summary
Finalised Phase 1, added a one‑command demo (`make demo`), a gateway‑only smoke test, and the console “Demo path (fibre_cut)” UI strip. Updated health endpoints, token handling for analysis commands, and Docker compose profiles.

### Changes
| Component | Change |
|-----------|--------|
| api‑gateway | Added `/healthz` and `/readyz`; `/health` now lists `mcp-server`. |
| mcp‑server | Added `/readyz`. |
| makefile | New targets: `demo`, `smoke` (renamed from `kafka-smoke`), `down` (stops rag & copilot profiles), `analyze`/`anomalies` now fetch token first. |
| scripts/demo.sh | Orchestrates compose up, topic creation, KPI back‑fill, fibre‑cut scenario, smoke verification, and console URL output. |
| scripts/smoke.sh & scripts/smoke.py | Nine gateway checks, polling with timeout, JSON output option, no token leakage. |
| console UI | Added “Demo path (fibre_cut)” strip showing the five‑stage flow and completion banner. |
| docs/adr/ADR‑011 | Recorded decision to use scripted demo + gateway smoke as release gate. |
| docs/handbook/w12‑setup.md | Documented one‑command demo and re‑run options. |
| docs/handbook/w12‑troubleshooting.md | Added troubleshooting entries 42‑46. |
| tests | Updated health endpoint tests; all existing pytest suites still pass (215 total). |

### Verification
- **Measured numbers** (see README): 215 pytest passes, 95 Vitest passes, lint clean.
- **Mac checks pending:** Run `make demo` on a fresh clone, verify all five demo stages turn green, smoke test reports 9/9 PASS, and memory usage stays within the configured limits.
- **Release gate:** ADR‑011 accepted; demo + smoke must pass before tagging `v0.1.0`.
