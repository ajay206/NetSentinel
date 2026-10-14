# 03 - Services Inventory

This document catalogs all services in the NetSentinel ecosystem, detailing their purpose, data flows, Kafka topics, databases, and implementation status.  
The **Week 2** additions are highlighted as **BUILT** and include short hand‑over notes for junior developers.

---

## Infrastructure Services (Week 1 – BUILT)

### 1. Apache Kafka (KRaft)
* **Status:** **BUILT**
* **Purpose:** Single‑node event streaming backbone.
* **Topics:** `alarms.raw`, `alarms.enriched`, `kpis`, `incidents`
* **Database:** N/A (event log)

### 2. TimescaleDB
* **Status:** **BUILT**
* **Purpose:** Time‑series storage for KPIs and metric telemetry.
* **Database:** PostgreSQL + TimescaleDB extension

---

## Library Packages (Week 2 – BUILT)

### libs/netgen
* **Status:** **BUILT**
* **Purpose:** Provides a small Python library that models a synthetic telecom topology (sites, cells, fiber links) and a “fibre_cut” scenario generator.
* **Key Modules:**
  * `netgen.topology` – data classes for `Site`, `Cell`, `FiberLink` and helper to build a static graph.
  * `netgen.scenarios.fibre_cut` – function `run(seed: int, speed: float, loop: bool, dry_run: bool)` that yields alarm dictionaries matching the TMF642 shape.
* **Inputs:** None (hard‑coded demo topology). Parameters are passed via the CLI of the simulator.
* **Outputs:** Python objects that the simulator serialises to JSON and publishes to Kafka (`alarms.raw`).

---

## Core Micro‑services (Week 2 – BUILT)

### 3. netgen‑simulator
* **Status:** **BUILT**
* **Purpose:** CLI tool that drives the `libs/netgen` scenario engine and streams synthetic alarms to Kafka. Acts as the “source of truth” for the demo.
* **Command line:**  

  ```bash
  netgen-sim run \
      --seed 42 \
      --scenario fibre_cut \
      --speed 60x \
      [--loop] \
      [--dry-run]
  ```

* **Inputs:** Command‑line arguments (`seed`, `scenario`, `speed`, optional `--loop`, `--dry-run`).
* **Outputs:** Publishes JSON alarm messages to the Kafka topic **`alarms.raw`**, keyed by `siteId`. When `--loop` is used the simulator repeats the scenario until the process is stopped.
* **Environment Variables:**  
  * `KAFKA_BOOTSTRAP` – e.g. `kafka:29092` (or host:port when running natively).  
  * `ALARM_TOPIC` – defaults to `alarms.raw`.  
  * `DISABLE_KAFKA` – set to any non‑empty value to run in dry‑run mode (no Kafka connection).  

* **How to run locally:** `make sim` (native) or `make sim-docker` (container).  
* **How to test:** See `make test` target in the repo root; the simulator has a pytest suite that validates the JSON schema and key handling.

### 4. api‑gateway
* **Status:** **BUILT**
* **Purpose:** Thin FastAPI façade that aggregates health information, exposes a small public API for the UI, and forwards raw alarm events from Kafka to WebSocket clients.  
  *Future:* Will be replaced by a full Traefik reverse‑proxy in later weeks (see ADR‑003).*
* **Key Endpoints:**
  * `GET /health` – Returns a JSON payload with overall status (`ok`|`degraded`) and per‑service health (`api‑gateway`, `kafka`, `timescaledb`). Example:

    ```json
    {
      "status": "ok",
      "services": [
        {"name": "api-gateway", "status": "up", "detail": ""},
        {"name": "kafka", "status": "up", "detail": ""},
        {"name": "timescaledb", "status": "up", "detail": ""}
      ],
      "checkedAt": "2026-10-14T09:12:34Z"
    }
    ```

  * `GET /api/alarms/recent` – Returns the most recent 100 alarms from the `alarms.raw` topic (cached in‑memory for fast UI refresh).
  * `WebSocket /ws/alarms` – Sends an initial **snapshot** message (`type: "snapshot", alarms: [...]`) followed by incremental **alarm** messages (`type: "alarm", alarm: {...}`) as they arrive from Kafka.

* **Environment Variables:**  
  * `KAFKA_BOOTSTRAP` – Kafka broker address.  
  * `ALARM_TOPIC` – Topic to consume (`alarms.raw`).  
  * `TIMESCALE_HOST` / `TIMESCALE_PORT` – Used by health‑check only.  
  * `CORS_ORIGINS` – Comma‑separated list for FastAPI CORS middleware.  
  * `DISABLE_KAFKA` – If set, the gateway runs in “offline” mode (no Kafka consumer).  

* **How to run locally:** `make gateway` (starts uvicorn on `0.0.0.0:8000`).  
* **How to test:** `make test` runs FastAPI test client checks for health, recent alarms, and WebSocket handshake.

### 5. noc‑console
* **Status:** **BUILT**
* **Purpose:** Front‑end dashboard (Vite + React + TypeScript + Tailwind) that visualises live alarms, service health tiles, and placeholder panels for future features.  
* **Running:** `npm run dev` serves the UI on `http://localhost:5173`. Vite proxy forwards `/api/*`, `/health`, and `/ws/*` to the locally running `api‑gateway` (`http://localhost:8000`).  
* **Key UI Elements (Week 2):**
  * **Alarm Table** – colour‑coded rows based on `perceivedSeverity` (critical = red, major = orange, …, cleared = gray). Updates in real‑time via the WebSocket stream.
  * **Service‑Health Tiles** – small cards showing the health status of `api‑gateway`, `kafka`, and `timescaledb`. Tiles turn red within ~5 s of a service becoming unavailable.
  * **Placeholder Panels** – empty cards labelled “Topology”, “Incidents”, “Copilot Chat” for later weeks.
* **How to add a new panel:** Create a new React component under `src/components/`, import it in `src/App.tsx`, and add a `<Panel>` wrapper with a title. No code changes are required in the backend for static panels.

---

## Planned Micro‑services (Phase 1 & 2 – PLANNED)

*(The entries below remain unchanged from Week 1; they are kept for roadmap visibility.)*

### 6. alarm‑ingest
* **Status:** PLANNED
* **Purpose:** Consumes `alarms.raw`, enriches with topology metadata, republishes to `alarms.enriched`.

### 7. kpi‑service
* **Status:** PLANNED
* **Purpose:** Processes KPI streams and persists metric history to TimescaleDB.

### 8. incident‑service
* **Status:** PLANNED
* **Purpose:** Correlates enriched alarms and KPIs into incidents.

### 9. topology‑service
* **Status:** PLANNED
* **Purpose:** Maintains network topology graph (Neo4j).

### 10. rag‑service
* **Status:** PLANNED
* **Purpose:** Semantic search over historical incidents and runbooks.

### 11. ml‑service
* **Status:** PLANNED
* **Purpose:** Anomaly detection on telemetry.

### 12. mcp‑server (Internal)
* **Status:** PLANNED
* **Purpose:** Internal Model Context Protocol server.

### 13. copilot‑orchestrator
* **Status:** PLANNED
* **Purpose:** LLM‑driven query handling for operators.

### 14. llm‑gateway
* **Status:** PLANNED
* **Purpose:** Proxy for local Ollama or hosted LLM endpoints.

### 15. ticket‑service
* **Status:** PLANNED
* **Purpose:** Mock integration with external ticketing systems.

### 16. api‑gateway – Traefik edge (planned, Week 11)
* **Status:** PLANNED
* **Purpose:** Full‑featured reverse‑proxy for HTTP/WebSocket traffic (will replace the thin FastAPI gateway).

### 17. noc‑console – full UI (later weeks)
* **Status:** PLANNED
* **Purpose:** Full NOC UI with topology map, incident view, and copilot chat.

--- 

*All Week 2 items are marked **BUILT** and ready for junior developers to explore, run, and extend.*
