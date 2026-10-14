"""Synthetic fault dataset generator for the Week 7 classifier.

Deterministic with np.random.default_rng(seed). No pandas, no sklearn.
"""

from __future__ import annotations

import numpy as np

from .features import FEATURE_NAMES  # noqa: F401  (re-exported for convenience)

FAULT_TYPES: tuple[str, ...] = (
    "fibre_cut",
    "power_failure",
    "cell_outage",
    "congestion",
    "bad_upgrade",
    "hw_drift",
    "core_packet_loss",
)

# Epoch for 2026-08-01T00:00:00Z
_EPOCH_START = 1785561600


def _pick(rng: np.random.Generator, options: list, p: np.ndarray | None = None) -> object:
    return rng.choice(options, p=p).item()


def _make_alarm(
    rng: np.random.Generator,
    fault_type: str,
    ts_epoch: int,
) -> tuple[dict, dict]:
    """Generate one (alarm, context) pair for the given fault class."""
    # Shared noise so classes overlap.
    noise = rng.normal(0, 0.25)

    alarm: dict = {
        "id": f"uuid-{ts_epoch}-{rng.integers(0, 1_000_000)}",
        "alarmType": "communicationsAlarm",
        "perceivedSeverity": "critical",
        "probableCause": "lossOfSignal",
        "specificProblem": "LOS",
        "siteId": f"SITE-{rng.integers(1, 999):03d}",
        "alarmRaisedTime": _epoch_to_iso(ts_epoch),
        "state": "raised",
        "enrichment": {
            "siteName": "site",
            "region": "Central",
            "siteKind": "hub",
            "nodeTypes": ["gNB", "router"],
            "parentSiteId": "SITE-001",
            "known": True,
        },
        "dedup": {"key": "k", "count": 1, "firstSeen": "f", "isDuplicate": False},
        "correlation": {
            "groupId": f"corr-{rng.integers(0, 1000)}",
            "rootSiteId": "SITE-002",
            "role": "root",
        },
    }
    context: dict = {
        "groupSize": 1,
        "kpiDropPct": 0.0,
        "anomalyScore": 0.0,
    }

    def _set_severity(rank: int) -> None:
        sev = {5: "critical", 4: "major", 3: "minor", 2: "warning", 1: "cleared"}
        alarm["perceivedSeverity"] = sev.get(rank, "critical")

    if fault_type == "fibre_cut":
        alarm["alarmType"] = _pick(rng, ["communicationsAlarm", "transportAlarm"])
        alarm["probableCause"] = _pick(rng, ["lossOfSignal", "underlyingResourceUnavailable"])
        alarm["enrichment"]["siteKind"] = _pick(rng, ["hub", "access"])
        alarm["enrichment"]["nodeTypes"] = ["gNB", "router", "fibre"]
        alarm["correlation"]["role"] = "root"
        context["groupSize"] = int(rng.integers(4, 16))
        context["kpiDropPct"] = float(rng.uniform(40, 90))
        context["anomalyScore"] = float(rng.uniform(2, 6))
        _set_severity(5)

    elif fault_type == "power_failure":
        alarm["alarmType"] = _pick(rng, ["environmentalAlarm", "equipmentAlarm"])
        alarm["probableCause"] = "powerProblem"
        alarm["enrichment"]["siteKind"] = _pick(rng, ["core", "hub", "access"])
        alarm["enrichment"]["nodeTypes"] = ["power", "router"]
        alarm["correlation"]["role"] = "root"
        context["groupSize"] = int(rng.integers(1, 7))
        context["kpiDropPct"] = float(rng.uniform(60, 100))
        context["anomalyScore"] = float(rng.uniform(3, 8))
        _set_severity(4)

    elif fault_type == "cell_outage":
        alarm["alarmType"] = "equipmentAlarm"
        alarm["probableCause"] = "underlyingResourceUnavailable"
        alarm["enrichment"]["siteKind"] = "access"
        alarm["enrichment"]["nodeTypes"] = ["gNB"]
        alarm["correlation"]["role"] = "root"
        context["groupSize"] = int(rng.integers(1, 3))
        context["kpiDropPct"] = float(rng.uniform(50, 100))
        context["anomalyScore"] = float(rng.uniform(4, 9))
        _set_severity(5)

    elif fault_type == "congestion":
        alarm["alarmType"] = "qualityOfServiceAlarm"
        alarm["probableCause"] = "thresholdCrossed"
        alarm["enrichment"]["siteKind"] = _pick(rng, ["access", "hub"])
        alarm["enrichment"]["nodeTypes"] = ["gNB", "router"]
        alarm["correlation"]["role"] = _pick(rng, ["root", "symptom"])
        context["groupSize"] = int(rng.integers(1, 4))
        context["kpiDropPct"] = float(rng.uniform(10, 40))
        context["anomalyScore"] = float(rng.uniform(3, 8))
        # evening hours more likely
        hour = int(rng.choice([17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]))
        alarm["alarmRaisedTime"] = _epoch_to_iso(_set_hour(ts_epoch, hour))
        _set_severity(3)

    elif fault_type == "bad_upgrade":
        alarm["alarmType"] = "processingErrorAlarm"
        alarm["probableCause"] = "softwareError"
        alarm["enrichment"]["siteKind"] = _pick(rng, ["core", "hub", "access"])
        alarm["enrichment"]["nodeTypes"] = ["gNB", "router", "server"]
        alarm["correlation"]["role"] = _pick(rng, ["root", "symptom"])
        context["groupSize"] = int(rng.integers(2, 9))
        context["kpiDropPct"] = float(rng.uniform(10, 60))
        context["anomalyScore"] = float(rng.uniform(2, 7))
        _set_severity(4)

    elif fault_type == "hw_drift":
        alarm["alarmType"] = _pick(rng, ["equipmentAlarm", "qualityOfServiceAlarm"])
        alarm["probableCause"] = "degradedSignal"
        alarm["enrichment"]["siteKind"] = _pick(rng, ["core", "hub", "access"])
        alarm["enrichment"]["nodeTypes"] = ["gNB", "router"]
        alarm["correlation"]["role"] = "symptom"
        context["groupSize"] = 1
        context["kpiDropPct"] = float(rng.uniform(0, 20))
        context["anomalyScore"] = float(rng.uniform(2, 5))
        _set_severity(int(rng.choice([2, 3])))  # minor/warning

    elif fault_type == "core_packet_loss":
        alarm["alarmType"] = _pick(rng, ["communicationsAlarm", "qualityOfServiceAlarm"])
        alarm["probableCause"] = _pick(rng, ["thresholdCrossed", "degradedSignal"])
        alarm["enrichment"]["siteKind"] = _pick(rng, ["core", "hub"])
        alarm["enrichment"]["nodeTypes"] = ["router", "server"]
        alarm["correlation"]["role"] = "root"
        context["groupSize"] = int(rng.integers(3, 13))
        context["kpiDropPct"] = float(rng.uniform(10, 50))
        context["anomalyScore"] = float(rng.uniform(3, 8))
        _set_severity(4)

    # Make the task realistic (macro-F1 well below 1.0):
    # 1. node types come from the real topology vocabulary, never from the fault class;
    kind = alarm["enrichment"]["siteKind"]
    alarm["enrichment"]["nodeTypes"] = (
        ["router"]
        if kind == "core"
        else (["gNB", "router"] if kind == "hub" else [str(_pick(rng, ["gNB", "eNB"]))])
    )
    # 2. in a storm most alarms an operator sees are sympathetic ones, so the alarm text
    #    often says little about the root cause;
    if rng.random() < 0.45:
        alarm["alarmType"] = _pick(
            rng, ["communicationsAlarm", "equipmentAlarm", "qualityOfServiceAlarm"]
        )
        alarm["probableCause"] = _pick(
            rng, ["underlyingResourceUnavailable", "thresholdCrossed", "degradedSignal"]
        )
        alarm["correlation"]["role"] = "symptom"
    # 3. severity and KPI context are noisy measurements.
    if rng.random() < 0.3:
        _set_severity(int(rng.integers(2, 6)))
    context["kpiDropPct"] = float(np.clip(context["kpiDropPct"] + noise * 60, 0.0, 100.0))
    context["anomalyScore"] = float(max(0.0, context["anomalyScore"] + rng.normal(0, 1.5)))
    context["groupSize"] = int(max(1, context["groupSize"] + rng.integers(-2, 3)))

    return alarm, context


def _epoch_to_iso(epoch: int) -> str:
    """Convert epoch seconds to ISO-8601 UTC string."""
    import datetime as dt

    return dt.datetime.fromtimestamp(epoch, tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _set_hour(epoch: int, hour: int) -> int:
    """Return epoch with the hour component set to `hour` (UTC)."""
    import datetime as dt

    d = dt.datetime.fromtimestamp(epoch, tz=dt.UTC)
    d = d.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def make_dataset(
    seed: int = 42, n: int = 3000, days: int = 60
) -> tuple[list[dict], list[dict], np.ndarray, np.ndarray]:
    """Generate a deterministic synthetic fault dataset.

    Args:
        seed: RNG seed.
        n: number of samples.
        days: span of timestamps in days from 2026-08-01.

    Returns:
        alarms: list of alarm dicts.
        contexts: list of context dicts.
        labels: int array of class indices (0..6).
        ts: epoch-second timestamps, sorted ascending.
    """
    rng = np.random.default_rng(seed)
    span_seconds = days * 24 * 3600
    end_epoch = _EPOCH_START + span_seconds

    # Roughly balanced class assignment.
    class_indices = rng.integers(0, len(FAULT_TYPES), size=n)

    # Uniform timestamps in [start, end).
    raw_ts = rng.integers(_EPOCH_START, end_epoch, size=n)
    # Sort ascending overall.
    order = np.argsort(raw_ts, kind="stable")
    sorted_ts = raw_ts[order]
    sorted_classes = class_indices[order]

    alarms: list[dict] = []
    contexts: list[dict] = []
    labels: list[int] = []

    for i in range(n):
        ft = FAULT_TYPES[int(sorted_classes[i])]
        alarm, ctx = _make_alarm(rng, ft, int(sorted_ts[i]))
        alarms.append(alarm)
        contexts.append(ctx)
        labels.append(int(sorted_classes[i]))

    labels_arr = np.asarray(labels, dtype=np.int64)
    ts_arr = np.asarray(sorted_ts, dtype=np.int64)
    return alarms, contexts, labels_arr, ts_arr
