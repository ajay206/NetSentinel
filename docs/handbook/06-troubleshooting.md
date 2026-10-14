# 06 - Troubleshooting

## Common Issues & Solutions

### 1. Docker Compose fails to start TimescaleDB (`POSTGRES_PASSWORD` error)
* **Cause:** The `.env` file is missing or `POSTGRES_PASSWORD` is not set.
* **Solution:** Run `cp .env.example .env` and populate `POSTGRES_PASSWORD=your_password`.

### 2. Kafka container exits or unhealthy
* **Cause:** Insufficient Docker memory allocation or port conflict on 9092.
* **Solution:** Ensure Docker Desktop has at least 4 GB RAM allocated. Check port availability (`lsof -i :9092`).

### 3. `uv sync` or workspace package resolution issues
* **Cause:** Outdated `uv` version or uninitialized workspace members.
* **Solution:** Upgrade `uv` (`pip install --upgrade uv`) and re-run `uv sync --all-extras --dev`.

### 4. Ruff or pre-commit hook failures
* **Cause:** Code formatting or linting rules violated.
* **Solution:** Run `make fmt` (`uv run ruff format .`) and `make lint` (`uv run ruff check .`) to automatically fix and check issues.

### 5. Map panel shows empty (no SVG)  
* **Cause:** The FastAPI gateway is down or `/api/topology` endpoint is unreachable.  
* **Solution:** Verify the gateway container is running (`docker ps`), check logs for errors, and ensure the environment variables `TOPOLOGY_SEED` and `TOPOLOGY_FULL` are set correctly. Restart the gateway if needed.

### 6. KPI activity panel shows “no data”  
* **Cause:** KPI simulator not publishing samples or the consumer has not received any messages yet.  
* **Solution:** Run the back‑fill/follow command: `make kpis-follow` (which executes `uv run netgen-sim kpis --seed 42 --days 7 --follow`). You can also peek at the latest samples with `make kpis-peek` to confirm messages are on the `kpis` topic.

### 7. “Stale” badge appears on KPI panel  
* **Cause:** No live KPI samples have been received for more than 60 seconds, indicating a break in the simulator or consumer.  
* **Solution:** Check that `netgen-sim kpis` is running in follow mode, verify the Kafka consumer group health, and ensure the system clock is synchronized (UTC). Restart the simulator if necessary.

### 8. Mermaid diagram fails to render on GitHub  
* **Cause:** Labels containing parentheses or other special characters are not quoted, causing the Mermaid parser to error.  
* **Solution:** Quote any label with special characters, e.g., `UI["noc-console (React)"]`. After fixing, run `make docs-check` which invokes `@mermaid-js/mermaid-cli` to validate all Mermaid blocks. Ensure all relative markdown links and images resolve correctly.
