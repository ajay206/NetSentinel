# NetSentinel

NetSentinel is an AI‑assisted Network Operations Center (NOC) copilot for telecom networks built on **synthetic data only**. It features event‑driven microservices communicating via Apache Kafka, time‑series metrics storage in TimescaleDB, topological root‑cause analysis via Neo4j, vector RAG via Qdrant, and an internal Model Context Protocol (MCP) server for AI tool execution.

> **Note:** All network telemetry, alarms, KPIs, and customer data generated and processed by NetSentinel are entirely synthetic.

## Status
* **Current Phase:** Week 2 – Core services built, API gateway thin FastAPI layer, and live NOC dashboard.
* **Built Components:** Monorepo workspace (`uv`), shared library (`ns-common`), Kafka KRaft, TimescaleDB, Kafka UI, `netgen-simulator` (topology & fibre‑cut scenario), `api‑gateway` (FastAPI thin gateway), `noc-console` (React/Vite dashboard), CI pipeline, pre‑commit hooks, and architecture handbook.
* **Planned Services:** Remaining services (`alarm-ingest`, `kpi-service`, `incident-service`, `copilot-orchestrator`, `mcp-server`, `ml-service`, `topology‑service`, `rag‑service`, `ticket‑service`, `llm‑gateway`) will be added in later weeks.

## Quick Start

### 1. Prepare the repo
```bash
cp .env.example .env          # set POSTGRES_PASSWORD, etc.
uv sync --all-extras --dev    # install Python deps
```

### 2. Core infrastructure (Docker)
```bash
make up-core      # starts Kafka and TimescaleDB
make topics       # create required Kafka topics (alarms.raw, …)
```

### 3. Run the dashboard (Week 2)

You have two equivalent ways to get the UI up and see live alarms.

#### A) All native processes (recommended on low‑memory Mac)
```bash
# start the gateway (native uvicorn)
make gateway

# install & start the React UI
make console-install
make console          # Vite dev server → http://localhost:5173
```

#### B) Containerised UI (api‑gateway runs in Docker)
```bash
make up-ui            # core + api‑gateway container (profile ui)
make topics
make console          # UI runs natively, talks to gateway container via proxy
```

In both cases, start the simulator to generate alarms:

```bash
# native simulator (single run)
make sim

# or run continuously in a container
make sim-docker
```

Open **http://localhost:5173** in a browser. You should see:

* A table of recent alarms (colour‑coded by severity).  
* Service‑health tiles for the gateway, Kafka, and TimescaleDB.  
* Live updates via WebSocket as the `netgen‑simulator` publishes to `alarms.raw`.

### 4. Verify everything works
```bash
make test          # pytest + ruff
make lint          # ruff + black
make fmt           # auto‑format code
make smoke         # simple Kafka produce/consume sanity check
```

## Repo Layout

```
netsentinel/
├── apps/
│   └── noc-console/        # React/Vite dashboard (Week 2)
├── libs/
│   ├── ns-common/          # Shared models, topic definitions, utils
│   └── netgen/             # Topology library + fibre_cut scenario (Week 2)
├── services/
│   ├── netgen-simulator/   # CLI that emits TMF642‑like alarm JSON to Kafka
│   └── api-gateway/        # FastAPI thin gateway (health, alarm endpoints, WS)
├── contracts/
│   └── asyncapi/
│       └── netsentinel.asyncapi.yaml
├── scripts/
│   └── create_topics.sh    # Idempotent Kafka topic creation script
├── docs/
│   ├── adr/                # Architecture Decision Records
│   └── handbook/           # Junior developer hand‑over guide
├── compose.yaml            # Docker Compose with profiles (core, tools, ui, sim)
├── Makefile                # Automation targets (up‑core, up‑ui, sim, etc.)
├── pyproject.toml          # uv workspace root
└── LEARNING_LOG.md         # Learning and reflection log
```

* `apps/` – Front‑end applications.  
* `libs/` – Re‑usable Python libraries.  
* `services/` – Backend micro‑services (each with its own Dockerfile).  
* `contracts/` – AsyncAPI / OpenAPI specifications.  

## License
MIT
