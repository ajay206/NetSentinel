# NetSentinel

NetSentinel is an AI-assisted Network Operations Center (NOC) copilot for telecom networks built on **synthetic data only**. It features event-driven microservices communicating via Apache Kafka, time-series metrics storage in TimescaleDB, topological root-cause analysis via Neo4j, vector RAG via Qdrant, and an internal Model Context Protocol (MCP) server for AI tool execution.

> **Note:** All network telemetry, alarms, KPIs, and customer data generated and processed by NetSentinel are entirely synthetic.

## Status
* **Current Phase:** Week 1 Bootstrap (Skeleton and Core Infrastructure).
* **Built Components:** Monorepo workspace (`uv`), shared library (`ns-common`), Kafka KRaft, TimescaleDB, Kafka UI, CI pipeline, pre-commit hooks, and architecture handbook.
* **Planned Services:** Services (`netgen-simulator`, `alarm-ingest`, `kpi-service`, `incident-service`, `copilot-orchestrator`, `mcp-server`, `ml-service`, `topology-service`, `rag-service`, `ticket-service`, `llm-gateway`, `api-gateway`, and React `noc-console`) are not built yet.

## Quick Start

1. Copy environment file:
   ```bash
   cp .env.example .env
   # Set POSTGRES_PASSWORD in .env
   ```

2. Install python dependencies:
   ```bash
   uv sync --all-extras --dev
   ```

3. Start core infrastructure:
   ```bash
   make up-core
   ```

4. Create Kafka topics:
   ```bash
   make topics
   ```

5. Run test suite:
   ```bash
   make test
   ```

6. Run Kafka smoke test (produce & consume):
   ```bash
   make smoke
   ```

## Repo Layout

```text
netsentinel/
├── libs/
│   └── ns-common/          # Shared common library (models, topics, utilities)
├── services/               # Microservices (coming in later weeks)
├── scripts/
│   └── create_topics.sh    # Idempotent Kafka topic creation script
├── docs/
│   ├── adr/                # Architecture Decision Records
│   └── handbook/           # Junior developer handover guide
├── compose.yaml            # Docker Compose profiles (core, tools, etc.)
├── Makefile                # Automation targets
├── pyproject.toml          # uv workspace root
└── LEARNING_LOG.md         # Learning and reflection log
```

## License
MIT
