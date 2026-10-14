# api-gateway

NetSentinel API Gateway with WebSocket alarm streaming.

## Purpose

Provides REST and WebSocket APIs for real-time alarm monitoring. Consumes alarms from Kafka and broadcasts to WebSocket clients.

## Inputs

- Kafka topic `alarms.raw` (configurable via `ALARM_TOPIC`)
- WebSocket connections at `/ws/alarms`

## Outputs

- `GET /health` - Service health with dependency checks
- `GET /api/alarms/recent` - Recent alarms buffer (max 200)
- `WS /ws/alarms` - Real-time alarm stream with initial snapshot

## Run

```bash
# From repo root
uv run --package api-gateway uvicorn api_gateway.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:
```bash
docker build -f services/api-gateway/Dockerfile -t api-gateway .
docker run -p 8000:8000 -e KAFKA_BOOTSTRAP=host.docker.internal:9092 api-gateway
```

## Test

```bash
uv run --package api-gateway pytest services/api-gateway/tests -v
```

## Environment Variables

- `KAFKA_BOOTSTRAP`: Kafka bootstrap servers (default `localhost:9092`)
- `ALARM_TOPIC`: Kafka topic to consume (default `alarms.raw`)
- `TIMESCALE_HOST`: TimescaleDB host (default `localhost`)
- `TIMESCALE_PORT`: TimescaleDB port (default `5432`)
- `CORS_ORIGINS`: Comma-separated allowed origins (default `http://localhost:5173`)
- `DISABLE_KAFKA`: Set to `1` to disable Kafka consumer (default `0`)

## ADR-003

Week 2 implementation: No authentication, local deployment only. Auth and multi-tenancy deferred.
