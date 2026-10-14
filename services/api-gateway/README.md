# NetSentinel API Gateway

Real-time alarm streaming, KPI activity monitoring, and topology query API for the NetSentinel NOC demo.

## Features

- **WebSocket Alarm Streaming** (`/ws/alarms`): Real-time alarm push to connected clients.
- **Recent Alarms REST** (`/api/alarms/recent`): Retrieve the last 200 alarms.
- **KPI Activity WebSocket** (`/ws/kpis`): Real-time KPI activity snapshot every 2 seconds.
- **KPI Activity REST** (`/api/kpis/activity`): Current KPI statistics (rate, averages, cells reporting).
- **Topology REST** (`/api/topology`): Generated network topology (sites, cells, links) with geo-coordinates.
- **Health Check** (`/health`): Dependency status (Kafka, TimescaleDB).

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP` | `localhost:9092` | Kafka bootstrap servers (comma-separated). |
| `ALARM_TOPIC` | `alarms.raw` | Kafka topic for raw alarms. |
| `KPI_TOPIC` | `kpis` | Kafka topic for KPI samples. |
| `TIMESCALE_HOST` | `localhost` | TimescaleDB host. |
| `TIMESCALE_PORT` | `5432` | TimescaleDB port. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed CORS origins. |
| `DISABLE_KAFKA` | `0` | Set to `1` to disable Kafka consumers (for testing). |
| `TOPOLOGY_SEED` | `42` | Seed for deterministic topology generation. |
| `TOPOLOGY_FULL` | `0` | Set to `1` to generate full topology (more sites/cells). |

## Running Locally

```bash
# From repository root with uv workspace
uv run --service api-gateway uvicorn api_gateway.main:app --reload --port 8000
```

Or install dependencies and run directly:

```bash
cd services/api-gateway
uv sync
uv run uvicorn api_gateway.main:app --reload --port 8000
```

## API Endpoints

### `GET /health`
Returns overall status and dependency health.

### `GET /api/alarms/recent`
Returns the most recent alarms (max 200).

### `WS /ws/alarms`
WebSocket for real-time alarms. Sends a snapshot on connect, then pushes new alarms as they arrive.

### `GET /api/kpis/activity`
Returns current KPI activity snapshot:
- `totalSamples`: Total samples recorded since start.
- `ratePerMin`: Samples per minute over the last 60 seconds.
- `lastSampleTime`: ISO timestamp of last sample.
- `lastSample`: The last sample dict.
- `averages`: Per-KPI average over rolling window (max 500 samples per KPI).
- `cellsReporting`: Distinct cell IDs in rolling window.

### `WS /ws/kpis`
WebSocket for real-time KPI activity. Sends a `kpiActivity` message every 2 seconds.

### `GET /api/topology`
Returns the generated network topology:
- `sites`: List of sites with `id`, `name`, `lat`, `lon`.
- `cells`: List of cells with `id`, `siteId`, `tech`, `band`, `azimuth`, etc.
- `links`: List of links between sites.
- `counts`: Aggregated counts.

## Development

### Tests
```bash
uv run pytest services/api-gateway/tests -v
```

### Linting
```bash
uv run ruff check services/api-gateway
uv run ruff format services/api-gateway
```

## Architecture Notes

- **ADR-003**: No authentication, local-only deployment. Auth and multi-tenancy deferred.
- Topology is generated once at startup using the `netgen` library (workspace dependency).
- Kafka consumers run as background tasks with automatic retry on failure.
- In-memory buffers (alarms, KPI samples) — not persistent across restarts.
