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

### 21. 503 Service Unavailable – No model registered
**Symptom:** `/predict` or `/explain` returns HTTP 503.  
**Cause:** `AUTO_TRAIN=0` and the registry does not contain a model entry.  
**Fix:**  
1. Run `make ml-train-xgb` to generate and register a synthetic model.  
2. Or set `AUTO_TRAIN=1` and restart `ml-service` so it can auto‑train on first request.  

### 22. 503 Service Unavailable – Drawer shows error
**Symptom:** In the NOC console, clicking an alarm row opens the `ShapDrawer` side panel, but it displays “Error loading explanation (503)”.  
**Cause:** The gateway could not reach `ml-service` (service down or network partition).  
**Fix:**  
1. Verify `ml-service` container is running: `docker ps | grep ml-service`.  
2. Check logs: `docker logs ml-service`.  
3. Restart the stack: `docker compose restart ml-service api-gateway`.  

### 23. Slow first request after startup
**Symptom:** The first `/predict` or `/explain` call after container start takes ~5‑10 seconds. Subsequent calls are fast.  
**Cause:** With `AUTO_TRAIN=1` and no pre‑registered model, the service trains a minimal synthetic XGBoost model on‑the‑fly.  
**Fix:**  
- Pre‑train and register a model (`make ml-train-xgb`) before starting the demo.  
- Or accept the warm‑up latency as expected behaviour for the auto‑train path.

### 24. rag-service unavailable (panel shows “rag-service unavailable”)
* **Symptom**: The “Suggested runbooks” panel in the console shows a red warning and no results.
* **Cause**: `rag-service` process is not running or cannot be reached on port 8004.
* **Fix**:  
  1. Verify the service is up: `curl -s http://localhost:8004/healthz`.  
  2. If it returns an error, start it: `make rag` (or `make up-rag`). Also check the gateway has `RAG_SERVICE_URL` pointing at it (default `http://localhost:8004`).  
  3. Check logs for port conflicts or missing environment variables.

### 25. /readyz returns 503 because a runbook has bad front‑matter
* **Symptom**: `GET http://localhost:8004/readyz` returns **503** even after ingest appears to finish.
* **Cause**: One of the markdown files is missing the required front‑matter fields `id` or `title` (or has no front matter), so the startup ingest raises and the service stays not‑ready.
* **Fix**:  
  1. Look at the ingest logs – they will point to the offending file.  
  2. Edit the file to include all required keys in the YAML front‑matter.  
  3. Restart rag-service (it ingests on startup); `/readyz` should now return **200**.

### 26. Switching EMBEDDER
* **Symptom**: After changing `EMBEDDER`, search results look odd or ingest fails with a vector-size error.
* **Cause**: Vectors from different embedders are not comparable. If the dimension changes, the `runbooks` collection is dropped and recreated automatically. `hash-384` and bge-small are both 384‑dim, so in that case nothing is recreated; the old vectors stay until the next ingest overwrites them.
* **Fix**: Restart rag-service, or run `make rag-ingest` with the same `EMBEDDER`. Every ingest re-upserts all chunks under the same point ids, which replaces every vector. To start clean: `curl -XDELETE http://localhost:6333/collections/runbooks`, then restart.

### 27. fastembed first run downloads ~130 MB model and needs internet
* **Symptom**: On the first start with `EMBEDDER=fastembed`, the service hangs for several minutes and then fails with a network‑related error.
* **Cause**: The FastEmbed library attempts to download the ONNX model for BAAI/bge‑small‑en‑v1.5.  Without internet access the download fails.
* **Fix**:  
  1. Ensure the host has outbound internet access for the initial download.  
  2. Alternatively, stay on the default `hash-384` embedder for offline CI.  
  3. After the model is cached (`~/.cache/fastembed`), subsequent runs work offline.

### 28. Panel always shows “fallback (no LLM)”

**Symptoms**: The UI displays the badge *fallback (no LLM)* and no LLM‑generated answer.

**Possible causes & fixes**
| Cause | Check | Remedy |
|-------|-------|--------|
| Ollama not running | `ps aux | grep ollama` or `curl http://localhost:11434/api/version` | Start Ollama: `ollama serve`. |
| Model not pulled | `ollama list` – model `qwen2.5:1.5b` missing | Run `make ollama-pull`. |
| `LLM=off` environment variable set | `docker exec copilot-orchestrator env | grep LLM` | Unset or set `LLM=on`. |
| Wrong `OLLAMA_URL` / network issue | Verify container can reach `host.docker.internal:11434` | Ensure `extra_hosts` entry is present; test with `curl http://host.docker.internal:11434/api/version` from inside the container. |

### 29. 404 No alarms for this site

**Symptoms**: API returns 404 with message `No alarms for site in window` (the panel shows “No alarms for this site in the window”).

**Possible causes & fixes**
| Cause | Check | Remedy |
|-------|-------|--------|
| Wrong `site_id` | Confirm pattern `^SITE-\d{3}$`. | Use a valid site ID (e.g., `SITE-012`). |
| Window too short | Verify alarms exist in the synthetic recent buffer. | Increase window (e.g., 30 m → 60 m). |
| Gateway recent buffer empty | Inspect `/api/alarms/enriched/recent` mock data. | Ensure the CI or demo seed populates recent alarms for the site. |

### 30. Slow first answer (approaching 90 s)

**Symptoms**: The first `Analyze site` request takes close to the 90 s timeout.

**Explanation**: The model is lazily loaded on first inference; subsequent calls are fast.

**Mitigation**
* Warm‑up the model after Ollama start: `curl -X POST http://localhost:11434/api/chat -d '{"model":"qwen2.5:1.5b","messages":[{"role":"user","content":"ping"}]}'`.
* Increase the timeout in the gateway if needed (not recommended for the demo).

### 31. Errors list shows citation failures

**Symptoms**: Validation reports “sourceId XYZ not found in context” or “runbookId not among retrieved runbooks”.

**Root cause**: The small model sometimes hallucinates IDs. After three retries the orchestrator falls back to the deterministic answer.

**Actions**
1. Review the cited IDs in the response – they should match alarm IDs (`ALM-…`), anomaly IDs (`ANOM-<cellId>-<kpi>-<ts>`), or runbook IDs (`RB-…`).  
2. If hallucinations persist, try a larger model by setting `OLLAMA_MODEL` to a higher‑capacity model (e.g., `qwen2.5:7b`).  
3. Ensure the prompt includes the full list of retrieved context IDs to reduce hallucination risk.
