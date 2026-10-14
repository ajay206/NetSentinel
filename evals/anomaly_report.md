# Anomaly baselines: evaluation report (draft, W6)

**Status:** draft. Synthetic data only.

## Method

The `ml-service` statistical baseline (ADR-006) works in three steps:

1. Decomposes a 15-minute KPI series into trend (a one-day rolling median), seasonal (the median per time of day) and residual.
2. Scores the residual with a robust z-score (median/MAD).
3. Flags points where |z| > 3.5, or where a two-sided CUSUM (k = 0.5, h = 5) alarms.

## Data

- Seven days of `dlThroughputMbps` from `netgen` (seed 42), for cells `SITE-001-N1-C1`, `SITE-002-N1-C1` and `SITE-003-N1-C1`.
- Ground truth: 6 non-overlapping blocks of 4 points (one hour each), scaled by ×(1 ± 0.35). None of them fall on the first day.
- A prediction counts as a hit if it is within 2 points (30 min) of a ground-truth point.

## Results (measured 2026-10-14)

| Metric | Average over the 3 cells |
|--------|--------------------------|
| Precision | 0.53 |
| Recall | 0.98 |
| F1 | 0.68 |

## Reproduce

```bash
make ml-train   # uv run python -m ml_service.train_baselines --experiment anomaly-baselines --seed 42 --days 7
```

Without `MLFLOW_TRACKING_URI`, the run is written to `evals/runs/anomaly-baselines-<UTC>.json`, which git ignores. To log to MLflow instead, install the optional `mlflow` extra and set the URI.

## Known limitations

- Precision is low. CUSUM keeps alarming for a few points after each injected block, and natural noise sometimes crosses the threshold.
- The decomposition needs at least 2 days of data to learn the daily profile. With less data, only a short rolling median is used.
- Detection runs on demand for each request. Nothing is stored yet, so the scores aren't tracked over time.

## Next steps

- Tune `ANOMALY_Z`, `k` and `h` per KPI, and add a short cool-down after each CUSUM alarm.
- Compare against the ML detector in W7 on the same seeds and ground truth.

## Note (Step 7): fault classifier
The W7 XGBoost fault classifier is evaluated separately: on synthetic labelled faults (n=3000, seed 42, 70/30 time-based split) it reaches accuracy ≈ 0.84 and macro-F1 ≈ 0.84. See `docs/model_card_fault_classifier.md` and ADR-007. Synthetic data only.
