"""W24 drift check: Population Stability Index (PSI) per feature, training vs recent data.

PSI = sum((a - e) * ln(a / e)) over quantile bins of the *expected* (training) sample.
Rule of thumb: < 0.1 stable, 0.1-0.2 watch, > 0.2 drifted (retrain / investigate).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .features import FEATURE_NAMES, alarm_features
from .synth_faults import make_dataset

EPS = 1e-4


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:  # constant feature: drift = any change in that value
        same = np.mean(np.isclose(actual, expected[0])) if len(expected) else 1.0
        e, a = np.array([1.0, EPS]), np.array([max(same, EPS), max(1 - same, EPS)])
        return float(np.sum((a - e) * np.log(a / e)))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / max(len(expected), 1)
    a = np.histogram(actual, edges)[0] / max(len(actual), 1)
    e, a = np.clip(e, EPS, None), np.clip(a, EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def features(seed: int, n: int) -> np.ndarray:
    alarms, contexts, _, _ = make_dataset(seed=seed, n=n, days=20)
    return np.stack([alarm_features(a, c) for a, c in zip(alarms, contexts, strict=True)])


def report(
    train: np.ndarray,
    recent: np.ndarray,
    threshold: float = 0.2,
    warn: float = 0.1,
    names: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    cols = names or (FEATURE_NAMES if train.shape[1] == len(FEATURE_NAMES) else None)
    cols = cols or tuple(f"f{i}" for i in range(train.shape[1]))
    per = {name: round(psi(train[:, i], recent[:, i]), 4) for i, name in enumerate(cols)}
    drifted = sorted(k for k, v in per.items() if v > threshold)
    watch = sorted(k for k, v in per.items() if warn < v <= threshold)
    return {
        "threshold": threshold,
        "maxPsi": max(per.values()) if per else 0.0,
        "drifted": drifted,
        "watch": watch,
        "psi": per,
        "status": "drift" if drifted else ("watch" if watch else "stable"),
    }
