# ML Service - Statistical Anomaly Baselines

Week 6 implementation for NetSentinel: lightweight statistical anomaly detection
using seasonal decomposition, robust z-scores, and CUSUM. No ML models yet.

## Features

- **Seasonal decomposition**: STL-lite with centred rolling median + per-phase medians
- **Robust z-score**: Median/MAD based, handles NaN
- **CUSUM**: Two-sided tabular CUSUM on robust z-scores
- **Synthetic evaluation**: Deterministic anomaly injection via netgen
- **Mann-Whitney U**: For before/after change significance
- **FastAPI endpoints**: Per-cell and aggregate anomaly queries

## Quick Start

```bash
# Install (from workspace root)
uv sync --package ml-service

# Run API
uv run --package ml-service uvicorn ml_service.api:app --port 8003

# Run evaluation
uv run --package ml-service python -m ml_service.train_baselines --seed 42 --days 7
```

## API Endpoints

- `GET /healthz` - Liveness
- `GET /readyz` - Readiness (checks kpi-service)
- `GET /anomalies/cells/{cell_id}?kpi=dlThroughputMbps&hours=168` - Cell anomalies
- `GET /anomalies?kpi=dlThroughputMbps&hours=24&limit=50` - Top anomalies across cells

## Environment Variables

- `KPI_SERVICE_URL` (default: http://localhost:8002)
- `ANOMALY_Z` (default: 3.5)
- `PORT` (default: 8003)
- `MLFLOW_TRACKING_URI` - Enable MLflow logging

## Testing

```bash
uv run --package ml-service pytest tests/test_ml_service.py -v
```
