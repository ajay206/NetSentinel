# 03 - Services Inventory

This document catalogs all services in the NetSentinel ecosystem, detailing their purpose, data flows, Kafka topics, databases, and implementation status.

---

## Infrastructure Services (Week 1 - BUILT)

### 1. Apache Kafka (KRaft)
* **Status:** **BUILT**
* **Purpose:** Single-node event streaming backbone.
* **Topics:** `alarms.raw`, `alarms.enriched`, `kpis`, `incidents`
* **Database:** N/A (Event log)

### 2. TimescaleDB
* **Status:** **BUILT**
* **Purpose:** Time-series storage for KPIs and metric telemetry.
* **Database:** PostgreSQL + TimescaleDB extension

---

## Planned Microservices (Phase 1 & 2 - PLANNED)

### 3. netgen-simulator
* **Status:** **PLANNED**
* **Purpose:** Generates synthetic telecom alarms, cell state changes, and KPI time-series.
* **Inputs:** Configuration profiles.
* **Outputs:** Produces to `alarms.raw` and `kpis`.
* **Database:** None.

### 4. alarm-ingest
* **Status:** **PLANNED**
* **Purpose:** Consumes raw alarms, enriches them with metadata, and republishes.
* **Inputs:** Consumes `alarms.raw`.
* **Outputs:** Produces to `alarms.enriched`.
* **Database:** Redis (deduplication cache).

### 5. kpi-service
* **Status:** **PLANNED**
* **Purpose:** Processes KPI streams and persists metric history.
* **Inputs:** Consumes `kpis`.
* **Outputs:** None (storage service).
* **Database:** TimescaleDB.

### 6. incident-service
* **Status:** **PLANNED**
* **Purpose:** Correlates enriched alarms and KPIs into distinct network incidents.
* **Inputs:** Consumes `alarms.enriched`, metrics from TimescaleDB.
* **Outputs:** Produces to `incidents`.
* **Database:** PostgreSQL.

### 7. topology-service
* **Status:** **PLANNED**
* **Purpose:** Maintains and queries network topology graphs (cell sites, fiber links, routers).
* **Inputs:** Topology seed data / API requests.
* **Outputs:** Graph query responses to MCP server.
* **Database:** Neo4j.

### 8. rag-service
* **Status:** **PLANNED**
* **Purpose:** Semantic search over historical incidents, runbooks, and vendor documentation.
* **Inputs:** Document ingestion / search queries.
* **Outputs:** Similar context snippets to MCP server.
* **Database:** Qdrant.

### 9. ml-service
* **Status:** **PLANNED**
* **Purpose:** Anomaly detection and predictive failure inference on telemetry.
* **Inputs:** Consumes `kpis`.
* **Outputs:** Anomaly alerts to Kafka.
* **Database:** SQLite / MLflow.

### 10. mcp-server (Internal)
* **Status:** **PLANNED**
* **Purpose:** Internal Model Context Protocol server exposing tools to query topology, RAG, and incidents.
* **Inputs:** Tool calls from `copilot-orchestrator`.
* **Outputs:** Structured tool results.
* **Database:** N/A (Aggregator layer).

### 11. copilot-orchestrator
* **Status:** **PLANNED**
* **Purpose:** LLM agent orchestrator answering engineer queries and guiding root-cause analysis.
* **Inputs:** User queries from API gateway.
* **Outputs:** Responses to UI; tool calls to internal `mcp-server`.
* **Database:** Redis (chat session state).

### 12. llm-gateway
* **Status:** **PLANNED**
* **Purpose:** Unified proxy/adapter for local Ollama or hosted LLM endpoints.
* **Inputs:** Prompts from orchestrator.
* **Outputs:** Completion tokens.
* **Database:** None.

### 13. ticket-service
* **Status:** **PLANNED**
* **Purpose:** Integrates incident summaries with external IT ticketing simulations (e.g., Jira/ServiceNow mocks).
* **Inputs:** Incident notifications.
* **Outputs:** Mock ticket IDs.
* **Database:** PostgreSQL.

### 14. api-gateway (Traefik)
* **Status:** **PLANNED**
* **Purpose:** Reverse proxy routing HTTP/WebSocket traffic to microservices.
* **Inputs:** External HTTP requests.
* **Outputs:** Routed internal requests.
* **Database:** None.

### 15. noc-console (React)
* **Status:** **PLANNED**
* **Purpose:** Frontend web application for NOC operators (topology map, live alarms, copilot chat).
* **Inputs:** User interactions.
* **Outputs:** API calls to gateway.
* **Database:** None (Client state).
