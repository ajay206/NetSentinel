# NetSentinel Netgen Library

Shared library for deterministic synthetic telecom topology generation.

## Usage

```python
from netgen import generate_topology

topology = generate_topology(seed=42, full=False)
topology_dict = topology.to_dict()
```

## Topology Structure

The generated topology includes:
- **Sites**: Physical locations with latitude/longitude.
- **Cells**: Radio cells attached to sites (technology, band, azimuth, etc.).
- **Links**: Transport links between sites.

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seed` | `int` | `42` | Random seed for reproducibility. |
| `full` | `bool` | `False` | If `True`, generates a larger topology (more sites/cells). |

## Output

`to_dict()` returns a dictionary with keys: `sites`, `cells`, `links`, `counts`.

## Development

```bash
uv run pytest libs/netgen/tests -v
uv run ruff check libs/netgen
```

## Integration

Used by:
- `api-gateway` (topology endpoint)
- `netgen-simulator` (event generation context)

Both services share the same `TOPOLOGY_SEED` and `TOPOLOGY_FULL` environment variables for consistency.
