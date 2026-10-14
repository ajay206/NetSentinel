# netgen-simulator

Kafka alarm simulator that streams synthetic telecom alarms.

## Purpose

Continuously generates alarm scenarios and publishes them to Kafka for downstream consumers.

## Inputs

- `--seed`: Random seed (default 42)
- `--scenario`: Scenario type (currently only `fibre_cut`)
- `--speed`: Simulation speed multiplier (e.g., `60x`)
- `--bootstrap`: Kafka bootstrap servers (default `localhost:9092` or `KAFKA_BOOTSTRAP` env)
- `--topic`: Kafka topic (default `alarms.raw`)
- `--dry-run`: Print JSON lines to stdout instead of Kafka
- `--loop`: Repeat scenario forever with incrementing seed

## Outputs

- Alarm messages to Kafka topic `alarms.raw` with key = `siteId`
- JSON lines to stdout in `--dry-run` mode

## Run

```bash
# From repo root
uv run --package netgen-simulator netgen-sim run --seed 42 --scenario fibre_cut --speed 60x --dry-run
```

## Test

```bash
uv run --package netgen-simulator pytest services/netgen-simulator/tests -v
```

## Environment Variables

- `KAFKA_BOOTSTRAP`: Kafka bootstrap servers (default `localhost:9092`)
