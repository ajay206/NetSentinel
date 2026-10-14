# KPI Service

Ingests KPI samples from Kafka topic `kpis`, stores them in TimescaleDB (or memory for tests), and exposes a REST API for querying aggregated KPIs per cell.

## Endpoints

- `GET /healthz` – liveness probe
- `GET /readyz` – readiness probe (checks DB and Kafka)
- `GET /stats` – ingestion statistics
- `GET /kpis/cells` – list cells with metadata
- `GET /kpis/cells/{cell_id}` – query KPIs for a cell

## Query Parameters

- `from` – start time (ISO 8601, default: 24h before `to`)
- `to` – end time (ISO 8601, default: latest sample or now)
- `agg` – aggregation: `raw`, `15m`, `1h`, `1d` (default: `1h`)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP` | `localhost:9092` | Kafka bootstrap servers |
| `KPI_TOPIC` | `kpis` | Kafka topic to consume |
| `DISABLE_KAFKA` | `false` | Disable Kafka consumer |
| `KPI_STORE` | `postgres` | Store backend: `postgres` or `memory` |
| `DATABASE_URL` | built from parts | PostgreSQL connection string |
| `TIMESCALE_HOST` | `localhost` | TimescaleDB host |
| `TIMESCALE_PORT` | `5432` | TimescaleDB port |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_DB` | `postgres` | Database name |
| `PORT` | `8002` | HTTP server port |

## Development

```bash
uv sync --package kpi-service
uv run pytest services/kpi-service/tests/
uv run uvicorn kpi_service.main:app --reload --port 8002
```
