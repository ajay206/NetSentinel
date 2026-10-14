from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from netgen.kpis import kpi_value
from numpy.typing import NDArray

KPI_NAMES = (
    "dlThroughputMbps",
    "prbUtilPct",
    "rrcSetupSuccessPct",
    "dropCallRatePct",
    "availabilityPct",
)


def make_series(
    seed: int,
    cell_id: str,
    kpi: str,
    days: int = 7,
    start: datetime | None = None,
) -> tuple[list[datetime], NDArray[np.float64]]:
    """
    Generate 15-min KPI series using netgen.kpi_value.

    Returns (timestamps, values) where values is float64 array.
    """
    if kpi not in KPI_NAMES:
        raise ValueError(f"Unknown KPI: {kpi}. Valid: {KPI_NAMES}")

    if start is None:
        start = datetime(2026, 10, 1, tzinfo=UTC)
    elif start.tzinfo is None:
        start = start.replace(tzinfo=UTC)

    n_points = days * 96  # 96 periods per day at 15-min
    timestamps = [start + timedelta(minutes=15 * i) for i in range(n_points)]
    values = np.array(
        [kpi_value(seed, cell_id, kpi, ts, start) for ts in timestamps],
        dtype=np.float64,
    )
    return timestamps, values


def inject_anomalies(
    values: NDArray[np.float64],
    seed: int,
    n: int = 6,
    width: int = 4,
    magnitude: float = 0.35,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """
    Inject deterministic block anomalies into series.

    Each anomaly: block of `width` points multiplied by (1 ± magnitude).
    Non-overlapping, not in first day (first 96 points).
    Returns (values_copy, truth_mask).
    """
    rng = np.random.default_rng(seed)
    n_points = len(values)
    first_day_end = 96  # 15-min periods in a day

    if n_points <= first_day_end + width:
        return values.copy(), np.zeros(n_points, dtype=bool)

    available_starts = list(range(first_day_end, n_points - width + 1))
    if len(available_starts) < n:
        n = len(available_starts)

    chosen_starts = rng.choice(available_starts, size=n, replace=False)
    chosen_starts.sort()

    # Ensure non-overlapping by filtering
    filtered_starts = []
    last_end = -1
    for s in chosen_starts:
        if s >= last_end:
            filtered_starts.append(s)
            last_end = s + width

    values_copy = values.copy()
    truth_mask = np.zeros(n_points, dtype=bool)

    for start_idx in filtered_starts:
        end_idx = start_idx + width
        sign = 1 if rng.random() < 0.5 else -1
        factor = 1.0 + sign * magnitude
        values_copy[start_idx:end_idx] *= factor
        truth_mask[start_idx:end_idx] = True

    return values_copy, truth_mask
