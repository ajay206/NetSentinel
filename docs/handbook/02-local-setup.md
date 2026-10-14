# 02 - Local Development Setup (Mac M2 8 GB)

This guide walks you through setting up NetSentinel locally on a resource‑constrained development environment like a MacBook Air M2 with 8 GB RAM.

## System Prerequisites
* **Python:** `>=3.12` (install via Homebrew or python.org)  
* **uv:** Fast Python package installer and workspace manager (`pip install uv`)  
* **Docker Desktop:** Allocate **at least 4 GB RAM** to Docker (Settings → Resources).  
* **Node:** **v22** (required for the React dashboard). Install with Homebrew: `brew install node@22`.  
* **Ollama (Optional for AI phases):** Running locally (`ollama serve`) with models like `llama3` or `mistral`.

## Step‑by‑Step Setup

1. **Clone the repository and copy the environment file**
   ```bash
   git clone https://github.com/ajay206/netsentinel.git
   cd netsentinel
   cp .env.example .env
   # Edit .env and set POSTGRES_PASSWORD=your_secure_password
   ```

2. **Install Python dependencies (uv)**
   ```bash
   uv sync --all-extras --dev
   ```

3. **Install Node dependencies for the UI**
   ```bash
   cd apps/noc-console
   npm ci   # installs exact versions from package-lock.json
   cd ../..
   ```

4. **Start Core Infrastructure (Kafka + TimescaleDB)**
   ```bash
   make up-core
   ```
   *This starts the `core` profile in `compose.yaml` – a single‑node KRaft Kafka broker (heap capped at 512 MiB) and a TimescaleDB instance (memory‑limited for an 8 GB laptop).*

5. **Create Kafka topics**
   ```bash
   make topics
   ```

6. **Run the test suite**
   ```bash
   make test
   ```

7. **Verify the event loop (smoke test)**
   ```bash
   make smoke
   ```

---

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
