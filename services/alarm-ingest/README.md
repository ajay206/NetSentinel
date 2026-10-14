# Alarm Ingest Service

This service consumes raw alarms from Kafka topic `alarms.raw`, normalizes, enriches with topology data, deduplicates, correlates, and produces enriched alarms to `alarms.enriched`.

## Configuration

Environment variables:
- `KAFKA_BOOTSTRAP` (default: `localhost:9092`)
- `RAW_TOPIC` (default: `alarms.raw`)
- `ENRICHED_TOPIC` (default: `alarms.enriched`)
- `TOPOLOGY_SEED` (default: `42`)
- `TOPOLOGY_FULL` (default: `0` - small topology)
- `DISABLE_KAFKA` (default: `0` - set to `1` to disable Kafka for testing)
- `PORT` (default: `8001`)

## Endpoints

- `GET /healthz` - Liveness probe
- `GET /readyz` - Readiness probe (checks Kafka connection)
- `GET /stats` - Pipeline statistics

## Running

```bash
uv run alarm-ingest
```

Or with Docker:
```bash
docker build -t alarm-ingest .
docker run -p 8001:8001 alarm-ingest
```
