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
