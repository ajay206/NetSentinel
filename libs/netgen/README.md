# netgen

Synthetic telecom topology and alarm generator library.

## Purpose

Generates deterministic network topologies and alarm scenarios for testing and development.

## Inputs

- `seed`: Integer seed for reproducible generation
- `n_sites`: Number of sites in topology (default 12)

## Outputs

- `Topology` with `Site` and `Link` dataclasses
- Alarm sequences following TMF642/X.733 format

## Run

```bash
# From repo root
uv run --package netgen python -c "from netgen import build_topology; print(build_topology(42))"
```

## Test

```bash
uv run --package netgen pytest libs/netgen/tests -v
```

## Environment Variables

None required.
