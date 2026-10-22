"""W24 eval gate: re-score a model on an independent synthetic hold-out, compare to thresholds.

The gate never trusts the model's own ``meta.json``: it loads ``model.json`` and scores it on
a hold-out generated with a different seed, so a degraded or tampered model cannot pass by
claiming good numbers. Thresholds and the champion baseline live in
``evals/gate_thresholds.json`` (reviewed like code: changing them is a visible diff).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

from .features import FEATURE_NAMES, alarm_features
from .synth_faults import FAULT_TYPES, make_dataset
from .train_xgb import _accuracy, _confusion_matrix, _macro_f1, _per_class_f1

HOLDOUT_SEED = 9001  # never used for training


def holdout(n: int = 1500, seed: int = HOLDOUT_SEED) -> tuple[np.ndarray, np.ndarray]:
    alarms, contexts, labels, _ = make_dataset(seed=seed, n=n, days=20)
    X = np.stack([alarm_features(a, c) for a, c in zip(alarms, contexts, strict=True)])
    return X, labels.astype(np.int64)


def score_model(model_dir: Path, n: int = 1500) -> dict[str, Any]:
    booster = xgb.Booster()
    booster.load_model(str(Path(model_dir) / "model.json"))
    X, y = holdout(n)
    proba = booster.predict(xgb.DMatrix(X, feature_names=list(FEATURE_NAMES)))
    cm = _confusion_matrix(y, np.argmax(proba, axis=1), len(FAULT_TYPES))
    per = _per_class_f1(cm)
    return {
        "accuracy": round(_accuracy(cm), 4),
        "macro_f1": round(_macro_f1(cm), 4),
        "per_class_f1": {FAULT_TYPES[i]: round(float(per[i]), 4) for i in range(len(FAULT_TYPES))},
        "n_holdout": int(len(y)),
    }


def decide(metrics: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Return {passed, reasons[]} for metrics against thresholds + champion baseline."""
    reasons: list[str] = []
    th = cfg["thresholds"]
    if metrics["accuracy"] < th["accuracy"]:
        reasons.append(f"accuracy {metrics['accuracy']:.3f} < {th['accuracy']}")
    if metrics["macro_f1"] < th["macro_f1"]:
        reasons.append(f"macro_f1 {metrics['macro_f1']:.3f} < {th['macro_f1']}")
    for cls, f1 in metrics["per_class_f1"].items():
        if f1 < th["per_class_f1_min"]:
            reasons.append(f"{cls} f1 {f1:.3f} < {th['per_class_f1_min']}")
    champ = cfg.get("champion") or {}
    if "macro_f1" in champ:
        drop = champ["macro_f1"] - metrics["macro_f1"]
        if drop > th["max_regression"]:
            reasons.append(
                f"macro_f1 regressed {drop:.3f} vs champion {champ['macro_f1']} "
                f"(max {th['max_regression']})"
            )
    return {"passed": not reasons, "reasons": reasons}


def gate_path(model_dir: Path) -> Path:
    """Sidecar next to (not inside) the version dir, so the ML-DSA file set stays unchanged."""
    model_dir = Path(model_dir)
    return model_dir.parent / f"{model_dir.name}.gate.json"


def run_gate(model_dir: Path, cfg_path: Path, n: int = 1500) -> dict[str, Any]:
    cfg = json.loads(Path(cfg_path).read_text())
    metrics = score_model(model_dir, n=n)
    result = {"model": Path(model_dir).name, "metrics": metrics, **decide(metrics, cfg)}
    gate_path(model_dir).write_text(json.dumps(result, indent=2))
    return result
