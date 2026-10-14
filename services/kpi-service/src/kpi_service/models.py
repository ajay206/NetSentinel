from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

KPI_NAMES = (
    "dlThroughputMbps",
    "prbUtilPct",
    "rrcSetupSuccessPct",
    "dropCallRatePct",
    "availabilityPct",
)


@dataclass(frozen=True, slots=True)
class KpiRow:
    sample_id: UUID
    ts: datetime
    site_id: str | None
    node_id: str | None
    cell_id: str
    region: str | None
    dl_throughput_mbps: float | None
    prb_util_pct: float | None
    rrc_setup_success_pct: float | None
    drop_call_rate_pct: float | None
    availability_pct: float | None


AGG_INTERVALS = {
    "raw": None,
    "15m": "15 minutes",
    "1h": "1 hour",
    "1d": "1 day",
}


def _parse_iso_timestamp(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
        return dt
    except Exception:
        return None


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except Exception:
        return None


def _get_float(kpis: dict[str, Any], key: str) -> float | None:
    val = kpis.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def parse_sample(raw: dict[str, Any]) -> KpiRow | None:
    sample_id_str = raw.get("sampleId")
    cell_id = raw.get("cellId")
    timestamp_str = raw.get("timestamp")

    if not sample_id_str or not cell_id or not timestamp_str:
        return None

    sample_id = _parse_uuid(sample_id_str)
    ts = _parse_iso_timestamp(timestamp_str)
    if sample_id is None or ts is None:
        return None

    kpis = raw.get("kpis", {})
    if not isinstance(kpis, dict):
        kpis = {}

    return KpiRow(
        sample_id=sample_id,
        ts=ts,
        site_id=raw.get("siteId"),
        node_id=raw.get("nodeId"),
        cell_id=cell_id,
        region=raw.get("region"),
        dl_throughput_mbps=_get_float(kpis, "dlThroughputMbps"),
        prb_util_pct=_get_float(kpis, "prbUtilPct"),
        rrc_setup_success_pct=_get_float(kpis, "rrcSetupSuccessPct"),
        drop_call_rate_pct=_get_float(kpis, "dropCallRatePct"),
        availability_pct=_get_float(kpis, "availabilityPct"),
    )
