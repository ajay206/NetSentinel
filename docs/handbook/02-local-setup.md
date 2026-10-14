# 02 - Local Development Setup (Mac M2 8 GB)

This guide walks you through setting up NetSentinel locally on a resource‑constrained development environment like a MacBook Air M2 with 8 GB RAM.

## Quick start (any OS: macOS, Linux, Windows via WSL2)

The demo needs only three things on the host. Python, uv, Node, compilers and libomp are **not** required: every service, the console and the CLI tools (simulator, smoke test, gateway helper) run in containers.

| Prerequisite | Notes |
|---|---|
| **Docker** | Docker Desktop (macOS/Windows) or Docker Engine + Compose v2 plugin (Linux). Images are multi-arch (linux/amd64 and linux/arm64, e.g. Apple Silicon). |
| **git** | To clone the repo. |
| **make** | Preinstalled on macOS (Xcode CLT prompt) and most Linux distros; `sudo apt install make` on Debian/Ubuntu/WSL. |

**Windows:** use WSL2 (Ubuntu) with Docker Desktop's WSL integration enabled, and clone the repo *inside* the WSL filesystem (e.g. `~/src`), not under `/mnt/c`.

**Memory (8 GB machines):** the full demo stack has ~3.5 GB of container memory limits (Kafka 1 GB, TimescaleDB 512 MB, the rest 64–384 MB each). Give Docker **at least 4 GB, ideally 5 GB** (Docker Desktop → Settings → Resources; on WSL2 set `memory=5GB` in `%UserProfile%\.wslconfig`), and close heavy apps while it runs. Optional: Ollama on the host for LLM answers (otherwise the copilot uses deterministic fallback answers).

```bash
git clone https://github.com/ajay206/NetSentinel.git
cd NetSentinel
make demo        # creates .env from env.example.txt if missing, builds, starts, seeds, smoke-tests
```

Then open **http://localhost:5173** and sign in as `operator` / `operator`.

| Command | What it does |
|---|---|
| `make demo` | Build + start all profiles, create topics, back-fill KPIs, play fibre_cut, run the smoke test |
| `make smoke` | Smoke test inside the tools container: 9 gateway checks + the dashboard (`noc-console` returns 200 and proxies `/health`) |
| `make logs S=kpi-service` | Logs for one service (`F=1` to follow). Plain `docker compose logs <svc>` fails with "no such service" because of profiles |
| `make ps` | Status of every container across profiles |
| `make sim`, `make kpis`, `make analyze`, `make anomalies`, `make incidents`, `make token AS=viewer` | Run in the tools container (`docker compose --profile cli run --rm tools …`) |
| `make reset-db` | Delete the TimescaleDB volume (see troubleshooting #53) |
| `make down` | Stop everything |

## Developer setup (optional: only to run tests or services natively)

* **Python** `>=3.12` and **uv** (`uv sync --all-extras --dev`).
* **Node 20+** for console development (`make console-install && make console`, Vite on :5173; stop the `noc-console` container first, or it holds the port).
* Makefile targets marked `(dev)` use these host tools. On macOS, importing xgboost natively needs `brew install libomp` (the containers don't).
* The sections below are the original week-by-week developer walkthroughs.

## Week 2: Run the Dashboard

You now have two ways to run the full Week 2 stack (simulator, API gateway, and React console). Choose the one that best fits your workflow and memory budget.

### A. All‑Native (recommended for low memory)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `make up-core` | Starts Kafka & TimescaleDB containers |
| 2 | `make topics` | Creates `alarms.raw` topic |
| 3 | `make gateway` | Launches the FastAPI gateway with `uvicorn` on **localhost:8000** |
| 4 | `make console-install && make console` | Installs UI dependencies and starts Vite dev server on **localhost:5173** (proxying `/api`, `/health`, `/ws` to the gateway) |
| 5 | `make sim` | Runs the `netgen-simulator` CLI natively, publishing alarms to Kafka |

Open your browser at **http://localhost:5173**. The dashboard will connect via WebSocket to `/ws/alarms` and start showing live alarms. The fibre‑cut scenario at `--speed 60x` runs for ~2 minutes and ends with cleared alarms.

### B. Containerised UI (useful if you prefer Docker for the UI)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `make up-ui` | Starts core services **and** builds & runs the `api-gateway` container (≈192 MiB) |
| 2 | `make topics` | Creates `alarms.raw` topic |
| 3 | `make console` | Starts the Vite dev server (still native) – it proxies to the gateway container at `http://localhost:8000` |
| 4 | `make sim` **or** `make sim-docker` | Run the simulator natively (`sim`) or inside its own container (`sim-docker`) |

The UI is still served by Vite on your host, but all backend services run in Docker.

---

### Memory Tips for an M2 8 GB Machine

* **Kafka:** Heap limited to 512 MiB (see `compose.yaml` → `KAFKA_HEAP_OPTS`).  
* **TimescaleDB:** `shared_buffers=128MB`, `work_mem=16MB`.  
* **api‑gateway container:** ~192 MiB RAM (FastAPI + aiokafka).  
* **netgen‑simulator container:** ~128 MiB RAM (pure Python).  
* **React dev server:** ~150 MiB (Node 22).  

If you hit memory pressure, stop the UI (`Ctrl‑C` in the Vite terminal) or the simulator, and keep only the core services running.

---

## Week 3: Map and KPI Stack

The Week 3 sprint adds the SVG network map, KPI generation, and new API endpoints.

### Run the Full Stack (native)

```bash
# 1️⃣ Generate topology (once) – deterministic seed 42
uv run netgen topology --seed 42 --out data/topology.json   # small (default) set
#   or add --full for the large topology

# 2️⃣ Back‑fill a week of KPI data
uv run netgen-sim kpis --seed 42 --days 7 --out - | \
  uv run kafka-console-producer --broker-list localhost:9092 --topic kpis

# 3️⃣ Start core services (Kafka + TimescaleDB)
make up-core

# 4️⃣ Create required topics (kpis + alarms)
make topics   # now creates `alarms.raw` and `kpis`

# 5️⃣ Launch the FastAPI gateway
make gateway

# 6️⃣ Start the React console
make console-install && make console

# 7️⃣ Run the live KPI publisher (follow mode)
make kpis-follow   # publishes one sample per cell every 5 s (default)
```

### Run the Full Stack (Docker‑compose profile)

```bash
# Build and start core + simulator + API gateway containers
make up-ui && docker compose --profile core --profile sim up -d --build
# Then start the UI (Vite) natively
make console
# Follow live KPI stream
make kpis-follow
```

**Memory note:** The KPI simulator adds roughly another 100 MiB when running in follow mode. Keep an eye on Docker memory; you may need to raise the allocation to **5 GB** if you run the full (`--full`) topology.

## Week 4: alarm-ingest and the enriched alarm feed

alarm-ingest reads `alarms.raw`, adds site/region/node types from the topology, counts repeats
(dedup) and groups symptoms under a root alarm (correlation), then writes `alarms.enriched`.
The gateway forwards it on `/ws/enriched` to the **Enriched alarm feed** panel.

### Run it natively (lowest memory)

```bash
make up-core && make topics      # Kafka (+ TimescaleDB); topics include alarms.enriched
make gateway                     # terminal 1, :8000
make ingest                      # terminal 2, alarm-ingest on :8001
make console                     # terminal 3, http://localhost:5173
make sim                         # terminal 4, fibre-cut scenario
make ingest-stats                # received / published / invalid / duplicates
```

### Or run alarm-ingest in Docker

```bash
make up-pipeline                 # core + alarm-ingest container (~160 MB)
make enriched-peek               # print 5 enriched alarms from Kafka
```

Expected: during `make sim` the panel fills within a few seconds; the LOS rows at both ends of
the cut show **root**, the access-site rows show **↳ <root site>**, and every time ends in IST.

## Week 5: kpi-service and KPI charts

kpi-service stores every KPI sample from the `kpis` topic in a TimescaleDB hypertable and
serves time-series queries; the gateway forwards `/api/kpi/*` to it and the **KPI charts**
panel draws them.

```bash
make up-core && make topics      # Kafka + TimescaleDB (needs POSTGRES_PASSWORD in .env)
make kpi-service                 # terminal 1, :8002 (applies SQL migrations on start)
make gateway                     # terminal 2, :8000
make console                     # terminal 3, http://localhost:5173
make kpis                        # backfill 1 day of 15-min samples, then make kpis-follow
make kpi-stats                   # received / written / invalid
make kpi-query                   # first cells via the gateway
```

Docker route: `make up-pipeline` now starts alarm-ingest **and** kpi-service (~350 MB).

### Documentation sanity‑check

After the changes, run the documentation validation target:

```bash
make docs-check
```

It runs `@mermaid-js/mermaid-cli` on all mermaid blocks and verifies relative markdown links and images.

## Week 6: ml-service and the Anomalies panel

```bash
make up-core && make topics      # Kafka + TimescaleDB
make kpi-service                 # terminal 1, :8002 (stores KPIs)
make kpis                        # backfill 1 day of KPIs (more days = better baseline)
make ml                          # terminal 2, ml-service on :8003
make gateway                     # terminal 3, :8000 (proxies /api/ml/*)
make console                     # terminal 4, http://localhost:5173
make anomalies                   # top 5 anomalies via the gateway
make ml-train                    # offline precision/recall/F1 on synthetic ground truth
```

Expected: the **Anomalies** panel lists cells with a `z` score badge, and the KPI chart shows
red dots plus an "N anomalies" badge on anomalous points. Times are shown in IST.

## Fault classifier (W7) – Local setup

```bash
# 1. Build and start the demo stack (docker-compose)
docker compose up -d

# 2. Train the XGBoost model (optional – AUTO_TRAIN will handle missing model)
make ml-train-xgb   # runs: python -m ml_service.train_xgb --register

# 3. Verify the model is registered
cat models/registry.json

# 4. Call the classifier via the API gateway
curl -X POST http://localhost:8000/api/ml/predict \
     -H "Content-Type: application/json" \
     -d '{"alarm": {"severity": 3, "node_type": "router", "blast_radius": 2, "dedup_cnt": 1, "kpi": 0.78, "group_sz": 4}}'

# 5. Get an explanation (top‑5 features)
curl -X POST "http://localhost:8000/api/ml/explain?top_k=5" \
     -H "Content-Type: application/json" \
     -d '{"alarm": {"severity": 3, "node_type": "router", "blast_radius": 2, "dedup_cnt": 1, "kpi": 0.78, "group_sz": 4}}'
```

**Notes**
- The gateway enforces a 64 KB request‑body limit (returns **413 Payload Too Large** if exceeded).  
- If `ml-service` is down, the gateway returns **503 Service Unavailable**.  
- Non‑JSON payloads result in **502 Bad Gateway** from the gateway.

## Runbook search (W8) – Local setup

The W8 demo can be run entirely locally; Docker is only needed for Qdrant when you want persistence.

### 1. Prepare the runbook corpus
```bash
make runbooks          # runs scripts/gen_runbooks.py; files are committed, so this is optional
```

### 2. Start the rag service (in‑memory Qdrant)
```bash
make rag               # builds and runs rag-service with an in‑memory Qdrant instance
```

### 3. Or start with Docker‑backed Qdrant
```bash
make up-rag            # brings up qdrant/qdrant:v1.12.4 on :6333 with volume qdrant-data
```

### 4. Ingest the runbooks
```bash
# If you have a remote Qdrant instance set QDRANT_URL, otherwise the in‑memory store is used
make rag-ingest        # reads data/runbooks, chunks, embeds, and upserts into Qdrant
```

### 5. Run the evaluation
```bash
make rag-eval          # executes the QA evaluation and prints the result table
```

### 6. Query via the NOC gateway
```bash
curl -s -XPOST localhost:8000/api/rag/search \
     -H 'content-type: application/json' \
     -d '{"query":"LOS on aggregation ring"}'
```

The response contains the top‑3 runbook suggestions with titles, sections, snippets, scores, and predicted fault types.

## Copilot with a local LLM (W9) – Setup

### Prerequisites
1. **Homebrew** (macOS) – for installing Ollama.  
2. **Docker & Docker Compose** – to run the demo stack.  
3. **Python 3.11+** – for local development (`uvicorn`, `httpx`, `pydantic`, etc.).

### Install and start Ollama
```bash
brew install ollama          # installs the Ollama binary
ollama serve                 # starts the Ollama server (listens on 127.0.0.1:11434)
make ollama-pull            # pulls qwen2.5:1.5b (≈1 GB)
```

### Docker Compose integration
`compose.yaml` includes an extra host entry so containers can reach the host‑side Ollama:

```yaml
services:
  copilot-orchestrator:
    build: {context: ., dockerfile: services/copilot-orchestrator/Dockerfile}
    profiles: [copilot]
    ports:
      - "8005:8005"
    mem_limit: 192m
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OLLAMA_URL=http://host.docker.internal:11434
      - OLLAMA_MODEL=qwen2.5:1.5b
```

### Make targets
| Target | Description |
|--------|-------------|
| `make copilot` | Runs the orchestrator locally with `uvicorn` (useful for debugging). |
| `make up-copilot` | Starts the full demo stack (gateway, ml‑service, rag‑service, and copilot‑orchestrator) via Docker Compose. |
| `make analyze SITE=SITE-012 WINDOW=30m` | Sends a `POST /api/copilot/analyze` request through the gateway (curl wrapper). |

### Example analysis call
```bash
make analyze SITE=SITE-012 WINDOW=30m
```
The gateway proxies the request to `http://localhost:8005/analyze` with a 90 s timeout.

## MCP tool layer (W10)

This guide walks you through building, running, and configuring the new **mcp-server** service.

### 1. Run locally (no Docker)

```bash
make mcp          # uvicorn --factory mcp_server.app:build_app --port 8006
                  # sets MCP_ALLOW_NO_TOKEN=1 so a token is not required
curl -s localhost:8006/healthz
```

For Docker, `make up-copilot` starts both `mcp-server` and `copilot-orchestrator` on the compose network. mcp-server publishes no host ports; only other containers can reach it. Set `MCP_SERVICE_TOKEN` in `.env` (do not use the compose default).

### 2. Development Mode (Inspector)

```bash
make mcp-dev      # → uv run mcp dev services/mcp-server/src/mcp_server/server.py
```

*Requires Node & npx for the MCP Inspector UI.*  

### 3. Environment Variables

| Variable | Required? | Description |
|----------|-----------|-------------|
| `MCP_SERVICE_TOKEN` | Yes (unless `MCP_ALLOW_NO_TOKEN=1`) | Bearer token used by the ASGI auth middleware. |
| `MCP_ALLOW_NO_TOKEN` | No | Set to `1` for local dev to bypass token requirement. |
| `TOOLS` | No (default `mcp`) | `mcp` = evidence via mcp-server; `http` = W9 direct calls. |
| `MCP_URL` | No | Defaults to `http://localhost:8006/mcp` (compose: `http://mcp-server:8006/mcp`). |
| `MCP_SERVICE_TOKEN` (copilot) | Same as mcp-server | Bearer token the copilot sends. |

**Tip:** Add the token to `.env` (used by `docker compose`) and **do not** rely on the dev default.

### 4. Regenerate Contracts

Whenever a tool signature changes:

```bash
make mcp-contract        # generates contracts/mcp/netsentinel-tools.json
make copilot-contract    # generates contracts/openapi/copilot-orchestrator.yaml
```

Both contracts are validated by CI; mismatches cause test failures.

### 5. Run Copilot with MCP

```bash
export MCP_SERVICE_TOKEN=your-secret-token   # for local uvicorn
make mcp &                                  # or: make up-copilot (Docker)
TOOLS=mcp MCP_URL=http://localhost:8006/mcp MCP_SERVICE_TOKEN=$MCP_SERVICE_TOKEN make copilot
make analyze SITE=SITE-012
```

## Gateway login and RBAC (W11)

### Console login screen
The web console shows a simple login form. In the demo build the following users exist:

| User | Password | Role |
|------|----------|------|
| `viewer` | `viewer` | viewer |
| `operator` | `operator` | operator |
| `admin` | `admin` | admin |

### Generating a token locally
```bash
make token AS=operator
# prints a JWT signed with the current JWT_SECRET
```

### Example API calls

```bash
TOKEN=$(make -s token AS=viewer)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/alarms/timeline
```

```bash
http :8000/api/kpi/healthz "Authorization:Bearer $TOKEN"
```

### Docker‑compose environment
Add the following to `.env` (do **not** commit real secrets):

```dotenv
JWT_SECRET=<random, 32+ characters>
GATEWAY_SERVICE_TOKEN=<random>
```

The compose file provides dev defaults for all other variables.

### UI behaviour
- A viewer sees the **Copilot “Analyze site”** button disabled, with the note *“Read-only: analyze needs the operator role.”*.
- The **Alarm storm timeline** panel shows one bar per minute, stacked by severity. A scrub‑slider lets you move through the last 5 000 enriched alarms. When a bucket’s count ≥ max(5, peak/2) a **Burst** badge appears.

### Generating a burst scenario
```bash
uv run netgen-sim run --seed 42 --scenario fibre_cut --speed 60x
```
The simulation injects a rapid series of alarms, causing the timeline to display a burst badge.

## One‑command demo (W12)

The `make demo` target builds and runs the complete Phase 1 demo scenario.

### Steps performed by `make demo`
1. `docker compose up` with the profiles **core**, **ui**, **pipeline**, **rag**, **copilot**.
2. Creates the required Kafka topics.
3. Waits for the API gateway `/readyz` (environment variable `DEMO_WAIT_S`, default 240 s).
4. Back‑fills one day of KPI data (seed 42) into TimescaleDB.
5. Starts the `netgen‑simulator` with the fibre‑cut scenario accelerated 60×.
6. Executes a quick smoke check against the gateway.
7. Prints the URL to open the console.

### Environment variables
- `DEMO_WAIT_S` – seconds to wait for `/readyz` before timing out (default 240).
- `GATEWAY_URL` – base URL of the API gateway (default `http://localhost:8000`).

### Re‑run only parts
- **Scenario only:** `make sim` – runs the `netgen‑simulator` against an already‑running stack.
- **Smoke only:** `make smoke` or `bash scripts/smoke.sh --json --wait 60`.

### Example smoke output

Example output (timings vary; `--json` prints the same checks as a JSON list):

```text
PASS  health             95 ms  9 services up
PASS  login               4 ms  logged in
PASS  alarms             12 ms  200 alarms
PASS  timeline            3 ms  total=214 peak=61
PASS  kpi_anomaly        40 ms  20 anomalies
PASS  fault              35 ms  faultType=fibre_cut
PASS  runbooks           60 ms  ids=RB-FIB-001,RB-FIB-002,RB-TRN-003
PASS  copilot          9500 ms  llm, 6 sources
PASS  rbac                2 ms  401 as expected
10/10 checks passed
```
