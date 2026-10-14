"""KPI generation with realistic seasonality and trends."""

from __future__ import annotations

import hashlib
import math
import random
import uuid
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from netgen.topology import Topology

KPI_BOUNDS: dict[str, tuple[float, float]] = {
    "dlThroughputMbps": (0.0, 1000.0),
    "prbUtilPct": (0.0, 100.0),
    "rrcSetupSuccessPct": (0.0, 100.0),
    "dropCallRatePct": (0.0, 100.0),
    "availabilityPct": (0.0, 100.0),
}

KPI_NAMES = tuple(KPI_BOUNDS.keys())


def _stable_rng(seed: int, *parts: str) -> random.Random:
    """Create a deterministic RNG from seed and string parts using CRC32."""
    key = f"{seed}:{':'.join(parts)}"
    crc = zlib.crc32(key.encode()) & 0xFFFFFFFF
    return random.Random(crc)


def _seasonality_factor(ts: datetime) -> float:
    """Compute daily seasonality factor (peak at 14:30 UTC, trough at 22:30 UTC)."""
    # Hour of day as float (0-24)
    hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0
    # Peak at 14.5 (14:30 UTC = 20:00 IST), trough at 22.5 (22:30 UTC = 04:00 IST)
    # Cosine wave: 1.0 at peak, 0.7 at trough (30% variation)
    phase = (hour - 14.5) * 2 * math.pi / 24.0
    return 0.85 + 0.15 * (1 + math.cos(phase)) / 2


def _weekly_factor(ts: datetime) -> float:
    """Weekend reduction factor (-15% on weekends)."""
    # Monday=0, Sunday=6
    if ts.weekday() >= 5:  # Saturday, Sunday
        return 0.85
    return 1.0


def _trend_factor(ts: datetime) -> float:
    """Small linear trend (0.1% per day) anchored to 2026-01-01."""
    epoch = datetime(2026, 1, 1, tzinfo=UTC)
    days = (ts - epoch).total_seconds() / 86400.0
    return 1.0 + 0.001 * days


def _base_value(kpi: str) -> float:
    """Base value for each KPI (mid-range typical)."""
    bases = {
        "dlThroughputMbps": 400.0,
        "prbUtilPct": 50.0,
        "rrcSetupSuccessPct": 98.5,
        "dropCallRatePct": 0.5,
        "availabilityPct": 99.5,
    }
    return bases.get(kpi, 50.0)


def _noise_factor(rng: random.Random, kpi: str) -> float:
    """Gaussian noise factor (multiplicative)."""
    noise_std = {
        "dlThroughputMbps": 0.15,
        "prbUtilPct": 0.10,
        "rrcSetupSuccessPct": 0.005,
        "dropCallRatePct": 0.30,
        "availabilityPct": 0.002,
    }
    std = noise_std.get(kpi, 0.1)
    return max(0.0, rng.gauss(1.0, std))


def kpi_value(seed: int, cell_id: str, kpi: str, ts: datetime, start: datetime) -> float:
    """
    Deterministic KPI value for a cell at timestamp.
    Note: 'start' parameter is kept for API compatibility but is unused;
    trends are anchored to a fixed epoch.
    """
    rng = _stable_rng(seed, cell_id, kpi, str(int(ts.timestamp())))
    base = _base_value(kpi)
    seasonality = _seasonality_factor(ts)
    weekly = _weekly_factor(ts)
    noise = _noise_factor(rng, kpi)

    if kpi in ("dlThroughputMbps", "prbUtilPct"):
        value = base * seasonality * weekly * _trend_factor(ts) * noise
    elif kpi == "dropCallRatePct":
        # Load normalized to ~0..1 (roughly 0.7 to 1.0 range)
        load = seasonality * weekly
        value = base * (0.7 + 0.6 * load) * noise
    else:
        # rrcSetupSuccessPct and availabilityPct
        value = base * noise

    lo, hi = KPI_BOUNDS[kpi]
    return max(lo, min(hi, value))


def _deterministic_uuid(seed: int, *parts: str) -> str:
    """Generate a deterministic UUID from seed and parts."""
    key = f"{seed}:{':'.join(parts)}"
    hash_bytes = hashlib.sha256(key.encode()).digest()[:16]
    # Set version 4 bits
    hash_bytes = bytearray(hash_bytes)
    hash_bytes[6] = (hash_bytes[6] & 0x0F) | 0x40
    hash_bytes[8] = (hash_bytes[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(hash_bytes)))


def generate_kpis(
    topology: Topology,
    seed: int,
    start: datetime,
    end: datetime,
    step_minutes: int = 15,
) -> Iterator[dict]:
    """Generate 15-minute KPI samples for all cells in topology."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    # Align start to step boundary
    start_minute = (start.minute // step_minutes) * step_minutes
    aligned_start = start.replace(minute=start_minute, second=0, microsecond=0)

    # Build cell -> (site, node, region) mapping
    cell_info: dict[str, tuple[str, str, str]] = {}
    for site in topology.sites:
        for node in site.nodes:
            for cell_id in node.cells:
                cell_info[cell_id] = (site.site_id, node.node_id, site.region)

    current = aligned_start
    step = timedelta(minutes=step_minutes)
    while current < end:
        for cell_id, (site_id, node_id, region) in cell_info.items():
            kpis = {}
            for kpi_name in KPI_NAMES:
                val = kpi_value(seed, cell_id, kpi_name, current, aligned_start)
                kpis[kpi_name] = round(val, 3)

            sample_id = _deterministic_uuid(seed, cell_id, str(int(current.timestamp())))
            yield {
                "@type": "KpiSample",
                "sampleId": sample_id,
                "siteId": site_id,
                "nodeId": node_id,
                "cellId": cell_id,
                "region": region,
                "timestamp": current.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "granularitySec": step_minutes * 60,
                "kpis": kpis,
            }
        current += step
