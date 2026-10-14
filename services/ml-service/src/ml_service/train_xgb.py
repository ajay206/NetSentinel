"""Training script for the Week 7 fault-type classifier.

Uses xgboost >= 2.1 built-in API (xgb.train). No sklearn, no pandas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xgboost as xgb

from .features import FEATURE_NAMES, alarm_features
from .synth_faults import FAULT_TYPES, make_dataset

_NUM_CLASSES = len(FAULT_TYPES)


def time_split(ts: np.ndarray, train_frac: float = 0.7) -> tuple[np.ndarray, np.ndarray]:
    """Split indices by time: all test timestamps strictly after all train.

    Ties (equal timestamps) go to train.
    """
    ts = np.asarray(ts)
    n = len(ts)
    n_train = int(round(n * train_frac))
    # Sort by timestamp; ties broken by original index (stable).
    order = np.argsort(ts, kind="stable")
    train_idx = order[:n_train]
    test_idx = order[n_train:]
    # Ensure strict separation: if the first test ts equals the last train ts,
    # move the duplicate-timestamp test entries into train.
    if len(test_idx) > 0 and len(train_idx) > 0:
        last_train_ts = ts[train_idx[-1]]
        # Move any test entries with ts <= last_train_ts into train.
        mask = ts[test_idx] <= last_train_ts
        moved = test_idx[mask]
        if len(moved) > 0:
            train_idx = np.concatenate([train_idx, moved])
            test_idx = test_idx[~mask]
    return train_idx, test_idx


def _confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred, strict=True):
        cm[int(t), int(p)] += 1
    return cm


def _per_class_f1(cm: np.ndarray) -> np.ndarray:
    n = cm.shape[0]
    f1s = np.zeros(n, dtype=np.float64)
    for i in range(n):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        f1s[i] = f1
    return f1s


def _macro_f1(cm: np.ndarray) -> float:
    return float(np.mean(_per_class_f1(cm)))


def _accuracy(cm: np.ndarray) -> float:
    total = cm.sum()
    correct = np.trace(cm)
    return float(correct / total) if total > 0 else 0.0


def train(
    seed: int = 42,
    n: int = 3000,
    days: int = 60,
    out_dir: str = "models",
    register: bool = True,
) -> dict:
    """Train the fault classifier and persist artifacts.

    Args:
        seed: RNG seed.
        n: number of synthetic samples.
        days: timestamp span in days.
        out_dir: base output directory.
        register: if True, update registry.json.

    Returns:
        metrics dict.
    """
    alarms, contexts, labels, ts = make_dataset(seed=seed, n=n, days=days)

    X = np.stack([alarm_features(a, c) for a, c in zip(alarms, contexts, strict=True)])
    y = labels.astype(np.int64)

    train_idx, test_idx = time_split(ts, train_frac=0.7)
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(FEATURE_NAMES))
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=list(FEATURE_NAMES))

    params = {
        "objective": "multi:softprob",
        "num_class": _NUM_CLASSES,
        "max_depth": 4,
        "eta": 0.2,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "nthread": 2,
        "seed": seed,
        "eval_metric": "mlogloss",
    }

    evals = [(dtrain, "train"), (dtest, "eval")]
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=150,
        evals=evals,
        verbose_eval=False,
    )

    # Predictions
    proba_test = booster.predict(dtest)  # (n_test, n_classes)
    y_pred = np.argmax(proba_test, axis=1)

    cm = _confusion_matrix(y_test, y_pred, _NUM_CLASSES)
    acc = _accuracy(cm)
    macro_f1 = _macro_f1(cm)
    per_class_f1 = _per_class_f1(cm)

    metrics = {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "per_class_f1": {FAULT_TYPES[i]: float(per_class_f1[i]) for i in range(_NUM_CLASSES)},
        "confusion_matrix": cm.tolist(),
        "n_train": int(len(train_idx)),
        "n_test": int(len(test_idx)),
    }

    # Persist
    out_path = Path(out_dir)
    version = "v" + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    version_dir = out_path / "fault_classifier" / version
    version_dir.mkdir(parents=True, exist_ok=True)

    booster.save_model(str(version_dir / "model.json"))

    meta = {
        "feature_names": list(FEATURE_NAMES),
        "fault_types": list(FAULT_TYPES),
        "metrics": metrics,
        "trainedAt": datetime.now(UTC).isoformat(),
        "seed": seed,
        "n": n,
        "version": version,
    }
    (version_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    if register:
        registry_path = out_path / "registry.json"
        registry: dict = {}
        if registry_path.exists():
            try:
                registry = json.loads(registry_path.read_text())
            except json.JSONDecodeError:
                registry = {}
        fc = registry.get("fault_classifier", {})
        versions = fc.get("versions", [])
        if version not in versions:
            versions.append(version)
        fc["latest"] = version
        fc["versions"] = versions
        registry["fault_classifier"] = fc
        tmp = registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(registry, indent=2))
        tmp.replace(registry_path)  # atomic on POSIX

    # Optional MLflow logging
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        try:
            import mlflow  # type: ignore[import-not-found]

            mlflow.set_tracking_uri(mlflow_uri)
            with mlflow.start_run(run_name=f"fault_classifier_{version}"):
                mlflow.log_params(params)
                mlflow.log_metrics(
                    {
                        "accuracy": acc,
                        "macro_f1": macro_f1,
                    }
                )
                mlflow.log_artifact(str(version_dir / "model.json"))
                mlflow.log_artifact(str(version_dir / "meta.json"))
        except ImportError:
            pass

    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ml_service.train_xgb",
        description="Train the Week 7 fault-type classifier.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--out", type=str, default="models")
    parser.add_argument("--register", action="store_true", default=False)
    args = parser.parse_args(argv)

    metrics = train(
        seed=args.seed,
        n=args.n,
        days=60,
        out_dir=args.out,
        register=args.register,
    )
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
