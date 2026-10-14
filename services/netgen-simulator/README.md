# NetSentinel Netgen Simulator

Simulator service that generates synthetic telecom alarms and KPIs, publishing to Kafka.

## Commands

- `uv run netgen-simulator` — Start the simulator (publishes to `alarms.raw` and `kpis` topics).
- `uv run netgen-simulator --help` — Show all options.

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP` | `localhost:9092` | Kafka bootstrap servers. |
| `ALARM_TOPIC` | `alarms.raw` | Topic for alarm events. |
| `KPI_TOPIC` | `kpis` | Topic for KPI samples. |
| `TOPOLOGY_SEED` | `42` | Seed for topology generation (must match API gateway). |
| `TOPOLOGY_FULL` | `0` | Generate full topology if `1`. |
| `SIMULATION_SPEED` | `1.0` | Speed multiplier for event generation. |

## New in Week 3

- Publishes KPI samples to `kpis` topic (configurable via `KPI_TOPIC`).
- Uses shared `netgen` library for topology generation.
- Aligns topology seed with API gateway via `TOPOLOGY_SEED`.

## Development

```bash
uv run pytest services/netgen-simulator/tests -v
uv run ruff check services/netgen-simulator
```
