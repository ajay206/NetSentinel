# NetSentinel

NetSentinel is an AI‑assisted Network Operations Center (NOC) copilot for telecom networks built on **synthetic data only**. It consists of event‑driven micro‑services communicating via Apache Kafka, time‑series storage in TimescaleDB, graph analysis in Neo4j, vector search in Qdrant, and a Model Context Protocol (MCP) server for AI tool execution.

> **Note:** All network telemetry, alarms, KPIs, and customer data generated and processed by NetSentinel are entirely synthetic.

## Status
* **Current Phase:** **Week 3** – KPI generation, topology endpoint, and enhanced console panels.
* **Built Components:**  
  * `libs/netgen` – deterministic topology & fibre‑cut scenario (`seed=42`).  
  * `services/netgen-simulator` – KPI back‑fill & live stream (`kpis` topic) plus unchanged alarm generator.  
  * `services/api-gateway` – FastAPI gateway exposing `/api/topology`, `/api/kpis/activity` and WebSocket `/ws/kpis`.  
  * `apps/noc-console` – New Network‑Map panel (SVG topology) and KPI‑Activity panel; timestamps shown in IST.  
  * Core infra (Kafka KRaft, TimescaleDB, Neo4j, Qdrant), CI pipeline, pre‑commit hooks, and architecture handbook.  

* **Planned Services:** Remaining micro‑services (`alarm-ingest`, `kpi-service`, `incident-service`, `copilot-orchestrator`, `mcp-server`, `ml-service`, `topology‑service`, `rag‑service`, `ticket‑service`, `llm‑gateway`) will be added in later weeks.

## Quick Start

### 1. Prepare the repo
```bash
cp .env.example .env          # set POSTGRES_PASSWORD, etc.
uv sync --all-extras --dev    # install Python deps
```

### 2. Core infrastructure (Docker)
```bash
make up-core      # starts Kafka and TimescaleDB
make topics       # create required Kafka topics (alarms.raw, kpis, …)
```

### 3. Run the dashboard (Week 3)

#### Native processes (recommended on low‑memory Mac)
```bash
# start the FastAPI gateway (uvicorn)
make gateway

# install & start the React UI
make console-install
make console          # Vite dev server → http://localhost:5173
```

#### Containerised UI (api‑gateway runs in Docker)
```bash
make up-ui            # core + api‑gateway container (profile ui)
make topics
make console          # UI runs natively, talks to gateway container via proxy
```

### 4. Start the simulators
```bash
# Alarm generator (unchanged)
make sim

# KPI generator – back‑fill 7 days then follow live samples every 5 s
make kpis-follow      # runs: uv run netgen-sim kpis --seed 42 --days 7 --follow --interval 5
```

### 5. Verify the UI
Open **http://localhost:5173**. You should see:

* **Network Map** – SVG topology with sites coloured by the worst active alarm severity (critical sites pulse).  
* **KPI Activity** – live sample rate, total samples, per‑cell reporting, and network‑wide averages (updated every 2 s).  
* Alarm table, service‑health tiles, and timestamps displayed in **IST (Asia/Kolkata)**.

### 6. Run checks
```bash
make test          # pytest + vitest
make lint          # ruff + eslint
make fmt           # auto‑format code
make smoke         # simple Kafka produce/consume sanity check
```

## Repo Layout

```
netsentinel/
├── apps/
│   └── noc-console/        # React/Vite dashboard (Week 3)
├── libs/
│   ├── ns-common/          # Shared models, topic definitions, utils
│   └── netgen/             # Topology library + fibre_cut scenario
├── services/
│   ├── netgen-simulator/   # CLI that emits alarms & KPI samples to Kafka
│   └── api-gateway/        # FastAPI thin gateway (health, topology, KPI endpoints, WS)
├── contracts/
│   └── asyncapi/
│       └── netsentinel.asyncapi.yaml
├── docs/
│   ├── adr/
│   └── handbook/
├── compose.yaml            # Docker Compose with profiles (core, tools, ui, sim)
├── Makefile                # Automation targets (up‑core, up‑ui, sim, kpis-follow, …)
├── pyproject.toml          # uv workspace root
└── LEARNING_LOG.md
```

* `apps/` – Front‑end applications.  
* `libs/` – Re‑usable Python libraries.  
* `services/` – Backend micro‑services (each with its own Dockerfile).  
* `contracts/` – AsyncAPI / OpenAPI specifications.  

## License
MIT
