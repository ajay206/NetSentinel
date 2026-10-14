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

### 13. KPI charts empty
**Symptom**: The KPI panel shows no lines or data points.  
**Cause**: The console queried the KPI service with a time range that contains no samples (e.g., wrong IST conversion) or the service returned an empty `points` array.  
**Fix**: Verify the request parameters in the network tab. Ensure `from`/`to` are in IST and fall within the last 62 days. Use `GET /kpis/cells` to confirm that the cell has recent samples.  

### 14. kpi-service unreachable (503)
**Symptom**: The API‑gateway returns `503 Service Unavailable` with message *“kpi-service unreachable”*.  
**Cause**: The KPI service container is not running, crashed, or the `KPI_SERVICE_URL` env var points to the wrong host/port.  
**Fix**: `docker compose ps` → restart the service (`docker compose up -d kpi-service`). Check logs (`docker compose logs kpi-service`). Ensure the port matches `PORT` env var.  

### 15. readyz 503 (DB)
**Symptom**: `GET /readyz` returns `503 Service Unavailable`.  
**Cause**: TimescaleDB is not reachable, credentials are wrong, or migrations have not been applied.  
**Fix**: Confirm the TimescaleDB container is up (`docker compose ps`). Test connectivity: `docker compose exec timescaledb psql -U $POSTGRES_USER -c "\dt"`. Apply migrations manually if needed (`make kpi-service` will run them at startup).  

### 16. Duplicate‑key / no new rows after replay
**Symptom**: After replaying a Kafka partition, the row count in `kpi_samples` does not increase.  
**Cause**: The `INSERT … ON CONFLICT (cell_id, ts) DO NOTHING` clause intentionally discards duplicates; the replayed messages have timestamps identical to existing rows.  
**Fix**: This is expected behavior. If you need to reprocess data, adjust the consumer offset or change the primary key strategy (e.g., include a version column).

### 17. ml-service unreachable (panel shows error)
**Symptom**: The Anomalies panel displays *“ml-service unreachable — run make ml”*.  
**Cause**: `api-gateway` cannot reach `ml-service` (service not started or wrong `ML_SERVICE_URL`).  
**Fix**:  
```bash
make ml            # start the FastAPI server
# or, if the URL changed:
export ML_SERVICE_URL=http://<host>:8003
```
Then refresh the console.

### 18. No anomalies shown (panel empty)
**Symptom**: Panel shows *“No anomalies in the last 24 h”* even though synthetic data contains injected blocks.  
**Cause**:  
* Less than one full day of KPI history is available – the first day is excluded from anomaly injection, so the evaluation data set contains no detectable anomalies.  
* Or the KPI fetch failed and returned empty series.  
**Fix**:  
1. Populate KPI data: `make kpis` or `make kpis-follow` to ingest at least 2 days of 15‑min points.  
2. Verify the fetch endpoint with `curl $KPI_SERVICE_URL/kpis/SITE-001-N1-C1?kpi=dlThroughputMbps&hours=48`.  

### 19. Too many anomalies on short history
**Symptom**: When requesting only a few hours of data, the CUSUM detector flags many points (often the points adjacent to an injected block).  
**Cause**: CUSUM is sensitive to short windows; the rolling‑median trend is poorly estimated with < 2 days, leading to larger residuals.  
**Fix**:  
* Request at least 168 h (7 days) for stable baselines, or  
* Adjust `ANOMALY_Z` upward for short queries, or  
* Tune CUSUM parameters (`k`, `h`) in `baselines.py` for the specific KPI.

### 20. MLflow not installed – runs not logged to server
**Symptom**: After `make ml-train` the console prints *“MLflow not available, writing JSON run log”* and no entry appears in the MLflow UI.  
**Cause**: The optional `mlflow-skinny` package is missing or `MLFLOW_TRACKING_URI` is unset.  
**Fix**:  
* Install the optional dependency: `uv add mlflow-skinny`.  
* Or set an environment variable pointing to a running MLflow server:  
  ```bash
  export MLFLOW_TRACKING_URI=http://mlflow:5000
  ```
  The service will automatically switch to server logging.
