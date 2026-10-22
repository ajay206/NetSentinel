# NetSentinel – AI copilot for telecom NOC operations

NetSentinel is an AI-assisted NOC copilot for telecom operators. It runs locally on a Mac M2 (8 GB) using Docker and native processes and works only with synthetic data. Phase 1 (Weeks 1-12) delivered the core data pipeline, analysis services and web console; Phase 2 added graph RAG, multi-agent workflows, ticketing, an LLM gateway and post-quantum crypto.

## Status
**Phase 1 and Phase 2 complete (v0.1.0 = Phase 1, v0.2.0 = Phase 2). Phase 3 (TelcoGPT-mini) is planned.**

**Built services (Docker + tests)**
- api-gateway (FastAPI, port 8000): JWT auth, role-based access (viewer / operator / admin)
- alarm-ingest (port 8001)
- kpi-service (port 8002)
- ml-service (port 8003): anomaly detection, XGBoost fault classifier with SHAP
- rag-service (port 8004): hybrid runbook search in Qdrant
- copilot-orchestrator (port 8005): LangGraph multi-agent copilot with a human approval node (Step 17)
- mcp-server (port 8006, internal)
- incident-service (port 8007): alarm correlation, incident board, operator workflow
- topology-service (port 8008): Neo4j topology, impact/RCA graph and Graph RAG (Steps 14-15)
- ticket-service (port 8009): ticket drafts with human approval and an audit trail (Step 16)
- llm-gateway (port 8010, internal): model router, prompt-injection guard, PII redaction (Step 18)
- netgen-simulator (CLI batch publisher)
- Post-quantum: hybrid ML-KEM TLS, ML-DSA model signing and a PQC panel (Step 21)

**Infrastructure (built)**
- Kafka (KRaft)
- TimescaleDB
- Qdrant
- Neo4j

**Observability (opt-in, `make up-obs`):** OTel collector, Prometheus, Grafana dashboards, Langfuse and MLflow under compose profile `obs` (W22); Service health shows latency/error sparklines and Grafana/Langfuse links when it's running.

**Kubernetes (opt-in, W23):** k3d cluster + Helm umbrella chart (`deploy/helm/netsentinel`) for a reduced service set, HPA on the copilot, Locust load test (`make k3d-up k3d-images k3d-install k3d-load`).

**Console:** React/TypeScript/Tailwind NOC console with a responsive bento theme (375–1920 px), checked in CI by a Playwright layout audit.

**Planned**
- Phase 3: TelcoGPT-mini (Steps 19-20), a small telecom-tuned model behind the llm-gateway (its route is reserved but not used yet)
- Managed Kubernetes / cloud deployment (W25+)

## Quick start
**Prerequisites:** Docker (Desktop or Engine with Compose v2), git and make. That's all: Python, uv and Node are only needed for development. Windows: use WSL2. On 8 GB machines, give Docker 4–5 GB (see `docs/handbook/02-local-setup.md`).
Optional: Ollama on the host (`ollama pull qwen2.5:1.5b`) for LLM answers.

```bash
git clone https://github.com/ajay206/NetSentinel.git && cd NetSentinel
make demo          # .env from env.example.txt if missing; build, start, topics, KPIs, fibre_cut, smoke
```
Open http://localhost:5173 and sign in with the demo user **operator** (password = `operator`).
For real secrets, edit `.env` (JWT_SECRET ≥32 chars, GATEWAY_SERVICE_TOKEN, MCP_SERVICE_TOKEN, TICKET_SERVICE_TOKEN, INCIDENT_SERVICE_TOKEN, POSTGRES_PASSWORD) before the first run.
Logs: `make logs S=<service>`; stop: `make down`.

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
- `docs/adr/` (ADR-001 … ADR-014)
- `LEARNING_LOG.md`

## License
MIT
