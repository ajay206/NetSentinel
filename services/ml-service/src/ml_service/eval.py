from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


def score(
    pred_mask: NDArray[np.bool_], truth_mask: NDArray[np.bool_], tolerance: int = 2
) -> dict[str, float]:
    """
    Compute precision, recall, F1 with tolerance.

    A truth block is detected if any predicted index within tolerance of a truth index.
    Precision: predicted indices within tolerance of truth / total predicted.
    """
    n = len(pred_mask)
    if n != len(truth_mask):
        raise ValueError("Masks must have same length")

    pred_indices = np.where(pred_mask)[0]
    truth_indices = np.where(truth_mask)[0]

    if len(pred_indices) == 0 and len(truth_indices) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if len(pred_indices) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if len(truth_indices) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Recall: fraction of truth indices with a prediction within tolerance
    truth_detected = 0
    for t_idx in truth_indices:
        if np.any(np.abs(pred_indices - t_idx) <= tolerance):
            truth_detected += 1
    recall = truth_detected / len(truth_indices)

    # Precision: fraction of predicted indices within tolerance of any truth
    pred_correct = 0
    for p_idx in pred_indices:
        if np.any(np.abs(truth_indices - p_idx) <= tolerance):
            pred_correct += 1
    precision = pred_correct / len(pred_indices)

    f1 = 0.0
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate(
    seed: int = 42,
    cells: tuple[str, ...] = (
        "SITE-001-N1-C1",
        "SITE-002-N1-C1",
        "SITE-003-N1-C1",
    ),
    kpi: str = "dlThroughputMbps",
    days: int = 7,
) -> dict[str, Any]:
    """
    Run evaluation on multiple cells, return per-run metrics and averages.
    """
    from ml_service.baselines import detect
    from ml_service.synth import inject_anomalies, make_series

    results = []
    for cell_id in cells:
        timestamps, values = make_series(seed, cell_id, kpi, days)
        values_anom, truth_mask = inject_anomalies(values, seed)
        anomalies = detect(values_anom)
        pred_mask = np.zeros(len(values_anom), dtype=bool)
        for a in anomalies:
            pred_mask[a["index"]] = True
        metrics = score(pred_mask, truth_mask)
        metrics["cellId"] = cell_id
        metrics["n_anomalies_true"] = int(np.sum(truth_mask))
        metrics["n_anomalies_pred"] = int(np.sum(pred_mask))
        results.append(metrics)

    # Averages
    avg_precision = np.mean([r["precision"] for r in results])
    avg_recall = np.mean([r["recall"] for r in results])
    avg_f1 = np.mean([r["f1"] for r in results])

    return {
        "per_cell": results,
        "average": {
            "precision": float(avg_precision),
            "recall": float(avg_recall),
            "f1": float(avg_f1),
        },
        "params": {
            "seed": seed,
            "cells": list(cells),
            "kpi": kpi,
            "days": days,
        },
    }


def log_to_mlflow(
    metrics: dict[str, Any],
    params: dict[str, Any],
    experiment: str,
    out_dir: str | None = None,
) -> str:
    """
    Log metrics to MLflow if available and MLFLOW_TRACKING_URI set.
    Otherwise write JSON to evals/runs/<experiment>-<UTC timestamp>.json.
    Returns path or MLflow run ID.
    """
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment)
            with mlflow.start_run() as run:
                mlflow.log_params(params)
                # Log average metrics
                for k, v in metrics.get("average", {}).items():
                    mlflow.log_metric(k, v)
                # Log per-cell as tags or nested
                for i, cell_metrics in enumerate(metrics.get("per_cell", [])):
                    for k, v in cell_metrics.items():
                        if isinstance(v, (int, float)):
                            mlflow.log_metric(f"{k}_cell_{i}", v)
                return run.info.run_id
        except ImportError:
            pass

    # Fallback to JSON file
    if out_dir is None:
        out_dir = "evals/runs"
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{experiment}-{timestamp}.json"
    filepath = Path(out_dir) / filename
    with open(filepath, "w") as f:
        json.dump(metrics, f, indent=2)
    return str(filepath)
