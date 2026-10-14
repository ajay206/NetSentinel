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

### 9. Enriched panel shows no data
**Symptom**  
The Enriched alarm feed in the NOC console is empty even though raw alarms are being produced.

**Cause**  
`api-gateway` is not subscribed to the `alarms.enriched` topic (environment variable `ENRICHED_TOPIC` missing or wrong) or the Kafka consumer failed to join the group.

**Fix**  
1. Verify `ENRICHED_TOPIC` is set to `alarms.enriched` in the gateway container env.  
2. Check `make ingest-stats` (is `published` growing?) and the gateway log line `Kafka consumer started on topic alarms.enriched`.  
3. Make sure alarm-ingest is running (`make ingest` or `make up-pipeline`) and that `make topics` created `alarms.enriched`. The gateway reads from `latest`, so start it before `make sim`.

### 10. readyz returns 503
**Symptom**  
`GET /readyz` on `alarm-ingest` returns HTTP 503.

**Cause**  
The service cannot connect to the Kafka broker (network issue, broker down, or wrong `KAFKA_BOOTSTRAP`).

**Fix**  
* Ensure the Kafka container is running: `docker ps | grep kafka`.  
* Verify the bootstrap address matches the compose network (`kafka:29092` inside compose, `localhost:9092` on the host).  
* If you are running locally without Kafka, set `DISABLE_KAFKA=1` and restart the service.

### 11. Duplicate alarms appear after restart
**Symptom**  
After restarting `alarm-ingest`, the console shows duplicate enriched alarms for the same event.

**Cause**  
In‑memory de‑duplication windows are cleared on restart, so the service re‑reads raw messages whose offsets were not yet committed (at-least-once, ADR-004).

**Fix**  
* Accept that duplicates are possible; downstream consumers are idempotent.  
* For a production‑grade fix, persist the de‑dup state (e.g., Redis) in a future sprint.  
* In the meantime, reduce the restart window or increase the de‑dup window size if duplicates are problematic.

### 12. Unknown region displayed
**Symptom**  
Enriched alarms show `region: "Unknown"` even though the site exists in the topology.

**Cause**  
The topology seed does not contain the site ID, or the site ID in the raw alarm is malformed (e.g., extra whitespace).

**Fix**  
* Check the raw alarm `siteId` / `alarmedObject.id` for correct formatting.  
* Make sure `TOPOLOGY_SEED` / `TOPOLOGY_FULL` are the same for the simulator, alarm-ingest and the gateway (default 42 / 0).
