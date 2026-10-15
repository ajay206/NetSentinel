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
- [ ] **Docker health** – `docker compose up -d` starts all services, `make ps` shows healthy.  
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

## Step 13 – W13 incident-service + incident board

**Summary**  
Introduces the topology‑aware incident clustering service, its API, and the new Incident board UI component.

### Changes
| Component | Change |
|-----------|--------|
| `services/incident-service` | New service (port 8007, `ops` profile, 128 MiB). Consumes `alarms.enriched`, publishes to `incidents`. |
| AsyncAPI | Added `incidents` channel and Incident message schema (v0.3.0). |
| Gateway | Proxy endpoints `/api/incidents` and `/api/incidents/{id}`; health list includes incident-service. |
| Console | New “Incident board” card with severity chip, status, root site, alarm/site counts, duration, and stats line “N alarms → M incidents (R×)”. Click filters feeds; polls every 5 s. |
| Makefile | Targets `incident`, `up-incident`, `incidents-peek`, `incident-eval`. Demo scripts now include `ops` profile. |
| Tests | 21 pytest tests for incident-service, 2 gateway proxy tests, 121 vitest console tests (including IncidentBoard). |

### Verification
- **Synthetic evaluation** (`uv run incident-eval`):  
  * Sequential faults – 397 alarms → 79 incidents, compression 5.03×, root match 100 %, purity 95 %, completeness 100 %, deterministic True.  
  * Concurrent pairs – 48 incidents, compression 8.27×, root match 65 %, merged 9, deterministic True.  
  * Concurrent with 60 s gap – 90 incidents, compression 4.41×, root match 65 %, split 1, merged 9.  
- **Operational checks**: `/readyz` returns 200, Incident board displays cards, filters work, and restart yields identical incident sets.  
- **Mac checks pending** – verify UI rendering on macOS browsers.

## Fix 1 – demo portability (`fix-demo-portability`)

### Summary
`make demo` now works on any machine with only Docker, git and make (macOS, Linux, Windows/WSL2). Fixes the bugs Ajay hit running the demo on a Mac against main `58a9b6c`.

### Changes
| Area | Change |
|---|---|
| compose.yaml | Every `depends_on` has a `condition`; kafka/timescaledb also in dependent profiles (all 512 profile combinations validate); fixed project `name: netsentinel`; new `noc-console` (nginx, `ui`) and `tools` (`cli`) services |
| Dockerfiles | Run `uvicorn`/`netgen-sim` from the venv instead of `uv run`; `UV_NO_CACHE`/`UV_CACHE_DIR`; home dir for appuser; libgomp1 for ml-service; multi-arch base images |
| kpi-service | No more `PoolClosed` crash: fresh pool per attempt, background retry with backoff, `/readyz` 503 until migrated |
| rag-service | Retries ingest in the background when Qdrant isn't ready |
| ml-service | `xgboost-cpu` → `xgboost` (prebuilt wheels everywhere); NCCL excluded; `uv.lock` updated |
| demo/smoke/Makefile | Host steps moved into the tools container; `scripts/gw.py` (wait/token/call); `make logs S=`, `ps`, `reset-db`, `incidents`, `tools-build`; `(dev)` markers on host targets |
| copilot | `AnalyzeRequest` accepts `siteId` (alias) and `site_id`; console sends `siteId`; contract regenerated |
| mcp-server / copilot | FastMCP `transport_security` allows the `mcp-server` host (`MCP_ALLOWED_HOSTS`), fixing 421; copilot maps failed evidence tools to 503/502 instead of 404 |
| dashboard | `noc-console` container (node build → nginx, proxies /api, /health, /ws to the gateway) on :5173 in the `ui` profile; smoke adds a `console` check (10 checks in the tools container) |
| docs | Docker-only prerequisites (+ memory note, WSL2), services section for noc-console, troubleshooting #51–60 |
| console auth | `login()` persists the session (`saveSession`), so /api calls carry the Bearer token and WebSockets carry `?token=`; Vitest regression test |

### Verification
- ruff, pytest, vitest, console lint/typecheck/build green in a clean clone; `docker compose config` passes for all 512 profile combinations (compose v2.32 binary, no daemon); shellcheck clean.
- Each service's `uv sync --frozen --no-dev --package …` venv imports its app and has `uvicorn` on PATH.
- **Mac checks pending:** images not built on the box (no Docker daemon); run `make demo` on Mac (arm64) and on Linux/WSL.

### Fix 1 — (13) NOC console redesign, (14) alarm drawer runbooks
- One 12-column layout grid with equal-height rows, a design-token theme (`theme.ts`) and severity chips.
- New header (live status, user/role, IST clock) and KPI summary row. Every card has a title, a subtitle and an ⓘ tooltip.
- Storm timeline rebuilt: labelled axes in IST, severity-stacked bars, legend, highlighted peak with a "Storm: N alarms at HH:MM IST, root SITE-xxx" annotation, and empty/loading/error states.
- Incident board is now a table. Enriched feed columns renamed (Repeats, Root / symptom). Stale "Week 5" text removed.
- Clicking an enriched alarm opens a detail drawer with alarm details, suggested runbooks (clickable, markdown preview) and SHAP. Esc closes it.
- The auth fetch wrapper is installed before App mounts, so the first API calls carry the token.
- Tests: timeline annotation/helpers, drawer runbooks; 127 Vitest tests pass.

### Step 13b — Enterprise RBAC, role-specific dashboards, change password
- **Users:** users and `audit_log` are persisted in TimescaleDB with bcrypt hashes. Demo users are seeded on first run only. Accounts lock after N failed logins (423), with admin unlock. A token-version claim revokes old tokens on a password change, reset, role change or disable.
- **New endpoints:** password change for every user; admin user management, audit log and settings under `/api/admin/*`; operator workflow (`POST /api/incidents/{id}/actions`, `POST /api/alarms/actions`) with notes. incident-service checks the forwarded role again.
- **Console:**
  - role badge and profile menu (Change password with strength meter and confirmation);
  - viewer is read-only with no copilot;
  - operator gets acknowledge / assign / resolve controls on incidents and alarms;
  - admin gets an Admin tab with users, audit log and system settings;
  - the UI hides what a role lacks, and the server returns 403 regardless.
- **Docs:** role-permission matrix and API table in `03-services.md`, ADR-013, troubleshooting #61–65. The gateway contract is regenerated.
- **Tests:**
  - pytest: permission matrix per role, password change and revocation, lockout and unlock, admin guards, audit, workflow rules;
  - Vitest: role-based dashboards, change-password form, RBAC matrix;
  - smoke: `roles` and `password` checks (12 checks with `CONSOLE_URL`).

### Fix 2 — smoke vs the login rate limiter
- `scripts/smoke.py` reuses one token per user and backs off on login 429s, honouring `Retry-After` within a bounded total wait (`SMOKE_LOGIN_MAX_WAIT`, default 75 s). Production limiter defaults are unchanged.
- Tests cover the back-off and token reuse (5 logins per run) and the wait bound. Troubleshooting #66 explains it.

### Step 14 — topology-service on Neo4j + impact / RCA graph panel (W14)
- **topology-service** (new, port 8008, profile `graph`):
  - Neo4j knowledge graph Site→Node→Cell, `LINK` between sites, a `PARENT_OF` homing tree, `Alarm`, `Runbook`, and `Ticket` (constraint reserved);
  - the loader rebuilds it in one transaction on start (`make topo-load`);
  - `/graph/impact` for link, site or node failure, plus a catalogue of 20 named read-only Cypher queries;
  - an in-memory backend for tests and low-RAM machines.
- **compose:** `neo4j:5.26-community` (multi-arch) with 512 MB heap, 256 MB page cache and `mem_limit: 1g`, ports bound to localhost; `topology-service` at 192 MB. New targets `make up-graph`, `make impact`, `make topo-load`. `NEO4J_PASSWORD` is in `env.example.txt`.
- **Gateway:** `/api/graph/impact|summary|queries` and `POST /api/graph/queries/{name}` need viewer; `POST /api/graph/reload` needs admin and is audited. The contract is regenerated.
- **MCP:** new `query_topology` tool; the contract is regenerated.
- **Console:** **Impact / RCA graph** panel (`views/RcaGraph.tsx`). NetworkMap highlights the impact radius and the failed link or site.
- **Results:**
  - "which cells lose service if LNK-012 fails?" returns SITE-010's 3 cells;
  - Neo4j matches the in-memory graph for every link, site and node on both topologies (27 + 138 targets);
  - impact latency on Neo4j 5.26 is about 5–6 ms p50, against a target of < 100 ms.
- **Docs:** `03-services.md` (service, API, RBAC rows, console panel), `02-local-setup.md`, troubleshooting #67–70, ADR-014, `contracts/openapi/topology-service.yaml`.
- **Tests:**
  - pytest: impact against a brute-force check for every link and site on both topologies; the LNK-012 answer and latency; API validation; the catalogue (read-only, params match); fake-driver loading; gateway RBAC matrix, proxy and audit; MCP tool;
  - an opt-in Neo4j integration test (`NEO4J_TEST_URI`);
  - Vitest: RcaGraph panel and map highlight;
  - smoke: `graph_impact` check.

### Step 15 — Graph RAG with entity linking, reranker, retrieval benchmark and console graph citations (W15)
- **rag-service:**
  - `mode: "graph"` = entity linking (`entities.py`) + catalogue text-to-Cypher with a schema prompt (`text2cypher.py`) + neighbourhood expansion (`graph_rag.py`, `topology.py`) + feature reranker (`rerank.py`); `mode: "rerank"` is the ablation;
  - results carry `nodeIds`/`matchedFacets` and the response a `graph` block;
  - `python -m rag_service.bench` + `make rag-bench` (Docker) write `evals/retrieval_report.md`.
- **Data:** `data/eval/qa.jsonl` grows to 150 questions (50 text, 50 paraphrases from a free model, 50 graph questions from `scripts/gen_qa_graph.py`).
- **topology-service:** `GET /graph/context/{id}` on Neo4j and memory (identical shapes); gateway `/api/graph/context/{id}` needs viewer. Contracts regenerated.
- **Copilot / MCP:** `RAG_MODE=graph` (default); the site id goes in the runbook query; graph nodes become citable sources, and the fallback answer cites them. MCP `search_runbooks` takes `mode`. Contracts regenerated.
- **Console:** node-ID chips on suggested runbooks and copilot citations, plus a "retrieval mode: graph" badge (`components/NodeChips.tsx`).
- **Compose:** rag-service `GRAPH_CONTEXT=http` + `TOPOLOGY_SERVICE_URL` (falls back to local); copilot `RAG_MODE: graph`. All 1024 profile combinations validate.
- **Results (hash embedder):** graph-question hit@1 0.26 (hybrid) → 0.80 (graph); all-questions hit@1 0.733 → 0.900, MRR@5 0.815 → 0.921; p95 about 2.5 ms. Caveats are in the report and ADR-015.
- **Docs:** ADR-015, `03-services.md`, `02-local-setup.md`, troubleshooting #71–73.
- **Tests:** rag graph pipeline (linking, planner, rerank, API, bench), context endpoint (memory + opt-in Neo4j equality), gateway RBAC row, MCP mode, copilot end-to-end against the real rag-service, Vitest chips/badge; smoke: `graph_rag` check (works without the `graph` profile).
