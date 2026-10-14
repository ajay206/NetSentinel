# NetSentinel – Phase 1 (Weeks 1-12)

NetSentinel is an AI-assisted NOC copilot for telecom operators. It runs locally on a Mac M2 (8 GB) using Docker and native processes and works only with synthetic data. Phase 1 delivers the core data-pipeline, a set of analysis services, and a web console.

## Status
**Phase 1 complete, v0.1.0 pending tag**

**Built services (Docker + tests)**
- api-gateway (FastAPI, port 8000)
- alarm-ingest (port 8001)
- kpi-service (port 8002)
- ml-service (port 8003)
- rag-service (port 8004)
- copilot-orchestrator (port 8005)
- mcp-server (port 8006, internal)
- netgen-simulator (CLI batch publisher)

**Infrastructure (built)**
- Kafka (KRaft)
- TimescaleDB
- Qdrant

**Not yet built (Phase 2+)**
- Neo4j / graph RAG
- LangGraph agents
- Ticket/incident services
- llm-gateway
- Kubernetes deployment

## Quick start
**Prerequisites**
- Docker Desktop
- `uv` (Python package manager)
- Node 20 (for the console)
- Optional: Ollama with `make ollama-pull` to pull the local LLM

**Setup**
```bash
cp env.example.txt .env
# Edit .env and set:
#   JWT_SECRET (≥32 characters)
#   GATEWAY_SERVICE_TOKEN
#   MCP_SERVICE_TOKEN
uv sync --all-extras --dev
make console-install
make demo          # stack up, topics, KPI back-fill, fibre_cut, smoke test
make console       # starts the React console
```
Open http://localhost:5173 and sign in with the demo user **operator** (password = `operator`).

## Demo walkthrough
`make demo` plays the seeded fibre_cut scenario. In the console, the **Demo path (fibre_cut)** strip at the top
ticks off five stages and shows a hint for the next one:

1. **Alarms stream** – enriched alarms arrive in *Enriched alarms* (and the *Alarm storm timeline* shows the burst).
2. **KPI anomaly** – after the 1-day KPI back-fill, the *Anomalies* panel lists anomalous cells.
3. **Fault badge** – click a root alarm in *Enriched alarms*: ml-service classifies it (XGBoost) and the SHAP drawer explains it.
4. **Runbooks** – *Suggested runbooks* lists the best matches for the selected alarm.
5. **Copilot answer** – as `operator`, press **Analyze site** in *Copilot analyze*; the answer must cite runbooks from its sources.

When all five are done the strip shows **Phase 1 demo complete**. Viewers can follow stages 1–4; analyze needs the operator role.

## Smoke test
Run the gateway-only smoke test:

```bash
make smoke               # runs scripts/smoke.sh with defaults
# or
bash scripts/smoke.sh --json --wait 60
```

The script (`scripts/smoke.py`) performs nine checks (health, login, alarms, timeline, KPI anomaly, fault, runbooks, copilot citation, RBAC) through the API gateway and exits with status 0 on success.

## Numbers (measured only)

Measured on 2026-10-14 on the build box (Linux), not on the Mac.

| Metric                              | Value |
|-------------------------------------|-------|
| Pytest total passed                 | 215 |
| pytest breakdown (by service)       | api-gateway 57, ml-service 37, netgen 25, rag-service 18, copilot-orchestrator 17, alarm-ingest 14, kpi-service 14, mcp-server 12, netgen-simulator 10, root smoke 10, ns-common 1 |
| Vitest (console) passed             | 95 |
| Lint/format (ruff, ESLint, tsc)     | clean |

### Configured memory limits (Docker compose)

| Service               | Limit |
|-----------------------|-------|
| kafka                 | 1 GiB |
| timescaledb           | 512 MiB |
| qdrant                | 384 MiB |
| ml-service            | 256 MiB |
| rag-service           | 256 MiB |
| api-gateway           | 192 MiB |
| kpi-service           | 192 MiB |
| copilot-orchestrator  | 192 MiB |
| alarm-ingest          | 160 MiB |
| mcp-server            | 128 MiB |

### Not yet measured
- End-to-end `make demo` execution time and memory usage on the Mac (Docker not available on the build box).

## Architecture
| Service                | Port | Role |
|------------------------|------|------|
| api-gateway            | 8000 | HTTP entry point, JWT/RBAC, rate limiting, WebSocket proxy |
| alarm-ingest           | 8001 | Raw alarm deduplication & enrichment |
| kpi-service            | 8002 | KPI ingestion, TimescaleDB storage, query API |
| ml-service             | 8003 | Statistical baselines, XGBoost fault classifier, SHAP |
| rag-service            | 8004 | Hybrid runbook search (Qdrant or in-memory) |
| copilot-orchestrator   | 8005 | Orchestrates tool calls, local Ollama LLM, JSON response validation |
| mcp-server             | 8006 | Internal MCP API for tool access |
| netgen-simulator       | —    | Batch/stream CLI publisher for synthetic topology, KPIs, fault scenarios |

## Repo layout
```
apps/
services/
libs/
contracts/
docs/
scripts/
evals/
data/
```

## Docs
- `docs/handbook/README.md`
- `docs/adr/` (ADR-001 … ADR-011)
- `LEARNING_LOG.md`

## License
MIT
