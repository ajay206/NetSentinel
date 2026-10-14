"""Feature engineering for the Week 7 fault-type classifier.

No pandas, no sklearn. Only numpy.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

# Fixed, stable feature order. Do NOT reorder without re-training.
FEATURE_NAMES: tuple[str, ...] = (
    "severity_rank",
    # one-hot alarmType
    "alarmType_communicationsAlarm",
    "alarmType_equipmentAlarm",
    "alarmType_qualityOfServiceAlarm",
    "alarmType_transportAlarm",
    "alarmType_processingErrorAlarm",
    "alarmType_environmentalAlarm",
    "alarmType_other",
    # one-hot probableCause
    "probableCause_lossOfSignal",
    "probableCause_powerProblem",
    "probableCause_underlyingResourceUnavailable",
    "probableCause_thresholdCrossed",
    "probableCause_softwareError",
    "probableCause_degradedSignal",
    "probableCause_other",
    # one-hot siteKind
    "siteKind_core",
    "siteKind_hub",
    "siteKind_access",
    "siteKind_unknown",
    # scalar / contextual
    "n_node_types",
    "has_router",
    "dedup_count",
    "is_root",
    "is_symptom",
    "group_size",
    "kpi_drop_pct",
    "anomaly_score",
    "hour_of_day_sin",
    "hour_of_day_cos",
)

# Fields that must never be used as features (leakage guard).
LEAKY_FIELDS: tuple[str, ...] = (
    "specificProblem",
    "id",
    "siteId",
    "faultType",
)

_ALARM_TYPES = (
    "communicationsAlarm",
    "equipmentAlarm",
    "qualityOfServiceAlarm",
    "transportAlarm",
    "processingErrorAlarm",
    "environmentalAlarm",
)

_PROBABLE_CAUSES = (
    "lossOfSignal",
    "powerProblem",
    "underlyingResourceUnavailable",
    "thresholdCrossed",
    "softwareError",
    "degradedSignal",
)

_SITE_KINDS = ("core", "hub", "access")

_SEVERITY_RANK = {
    "critical": 5,
    "major": 4,
    "minor": 3,
    "warning": 2,
    "cleared": 1,
}


def _one_hot(value: str | None, categories: tuple[str, ...]) -> list[int]:
    """Return a one-hot list with a trailing 'other' bucket."""
    if value in categories:
        return [1 if value == c else 0 for c in categories] + [0]
    return [0 for _ in categories] + [1]


def _hour_from_iso(ts: str | None) -> int:
    """Extract UTC hour (0-23) from an ISO-8601 timestamp string."""
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC)
        return dt.hour
    except (TypeError, ValueError):
        return 0


def alarm_features(alarm: dict, context: dict | None = None) -> np.ndarray:
    """Build a float32 feature vector for an enriched alarm.

    Args:
        alarm: enriched alarm dict (output of alarm-ingest).
        context: optional per-alarm context dict.

    Returns:
        np.ndarray of shape (len(FEATURE_NAMES),) and dtype float32.
    """
    ctx = context or {}
    enrichment = alarm.get("enrichment") or {}
    dedup = alarm.get("dedup") or {}
    correlation = alarm.get("correlation") or {}

    # severity_rank
    severity = alarm.get("perceivedSeverity")
    severity_rank = float(_SEVERITY_RANK.get(severity, 0))

    # alarmType one-hot
    alarm_type = alarm.get("alarmType")
    at_oh = _one_hot(alarm_type, _ALARM_TYPES)

    # probableCause one-hot
    probable_cause = alarm.get("probableCause")
    pc_oh = _one_hot(probable_cause, _PROBABLE_CAUSES)

    # siteKind one-hot
    site_kind = enrichment.get("siteKind")
    sk_oh = _one_hot(site_kind, _SITE_KINDS)

    # node types
    node_types = enrichment.get("nodeTypes") or []
    n_node_types = float(len(node_types))
    has_router = float(1 if "router" in node_types else 0)

    # dedup
    dedup_count = float(dedup.get("count", 0) or 0)

    # correlation role
    role = correlation.get("role")
    is_root = float(1 if role == "root" else 0)
    is_symptom = float(1 if role == "symptom" else 0)

    # context
    group_size = float(ctx.get("groupSize", 0) or 0)
    kpi_drop_pct = float(ctx.get("kpiDropPct", 0) or 0)
    anomaly_score = float(ctx.get("anomalyScore", 0) or 0)

    # hour of day (cyclical)
    hour = _hour_from_iso(alarm.get("alarmRaisedTime"))
    hour_norm = hour / 24.0
    hour_sin = float(np.sin(2 * np.pi * hour_norm))
    hour_cos = float(np.cos(2 * np.pi * hour_norm))

    vec = [
        severity_rank,
        *at_oh,
        *pc_oh,
        *sk_oh,
        n_node_types,
        has_router,
        dedup_count,
        is_root,
        is_symptom,
        group_size,
        kpi_drop_pct,
        anomaly_score,
        hour_sin,
        hour_cos,
    ]

    arr = np.asarray(vec, dtype=np.float32)
    if arr.shape != (len(FEATURE_NAMES),):
        raise ValueError(f"feature vector has {arr.shape[0]} values, expected {len(FEATURE_NAMES)}")
    return arr
