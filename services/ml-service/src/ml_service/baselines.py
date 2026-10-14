from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def _centred_rolling_median(values: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Centred rolling median with nearest-edge handling."""
    n = len(values)
    half = window // 2
    result = np.full(n, np.nan, dtype=np.float64)

    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        window_vals = values[start:end]
        valid = window_vals[~np.isnan(window_vals)]
        if len(valid) > 0:
            result[i] = np.median(valid)
        else:
            result[i] = np.nan
    return result


def _phase_medians(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Compute per-phase median, centred to mean 0."""
    phase_medians = np.zeros(period, dtype=np.float64)
    for p in range(period):
        phase_vals = values[p::period]
        valid = phase_vals[~np.isnan(phase_vals)]
        if len(valid) > 0:
            phase_medians[p] = np.median(valid)
        else:
            phase_medians[p] = 0.0
    phase_medians -= np.mean(phase_medians)
    return phase_medians


def seasonal_decompose(
    values: NDArray[np.float64], period: int = 96
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """
    Lightweight STL-like decomposition.

    Returns (trend, seasonal, resid) where:
    - trend: centred rolling median (window=period)
    - seasonal: per-phase median of (values - trend), centred to mean 0
    - resid: values - trend - seasonal
    NaN positions preserved in resid.
    """
    n = len(values)
    if n < 2 * period:
        # Too short to learn a daily profile: a short rolling median (about 3 h at 15 min)
        # follows the daily curve so normal peaks are not flagged.
        trend = _centred_rolling_median(values, max(5, period // 8))
        seasonal = np.zeros(n, dtype=np.float64)
        resid = values - trend
        return trend, seasonal, resid

    trend = _centred_rolling_median(values, period)
    detrended = values - trend
    phase_meds = _phase_medians(detrended, period)
    seasonal = np.tile(phase_meds, (n // period) + 1)[:n]
    resid = values - trend - seasonal
    return trend, seasonal, resid


def robust_zscore(x: NDArray[np.float64]) -> NDArray[np.float64]:
    """
    Robust z-score: (x - median) / (1.4826 * MAD).
    MAD == 0 -> zeros. NaN preserved.
    """
    mask = ~np.isnan(x)
    if not np.any(mask):
        return np.full_like(x, np.nan)

    median = np.median(x[mask])
    mad = np.median(np.abs(x[mask] - median))
    # MAD is 0 when over half the points are identical; fall back to the mean absolute
    # deviation (scaled to sigma) so a lone outlier on a flat series is still scored.
    scale = 1.4826 * mad if mad > 0 else 1.2533 * float(np.mean(np.abs(x[mask] - median)))
    if scale == 0:
        result = np.zeros_like(x)
        result[~mask] = np.nan
        return result

    result = (x - median) / scale
    result[~mask] = np.nan
    return result


def cusum(x: NDArray[np.float64], k: float = 0.5, h: float = 5.0) -> NDArray[np.bool_]:
    """
    Two-sided tabular CUSUM on robust z-scores.
    Flags index where S+ or S- exceeds h, then resets that side to 0.
    """
    n = len(x)
    flags = np.zeros(n, dtype=bool)
    s_pos = 0.0
    s_neg = 0.0

    for i in range(n):
        if np.isnan(x[i]):
            flags[i] = False
            continue
        s_pos = max(0.0, s_pos + x[i] - k)
        s_neg = min(0.0, s_neg + x[i] + k)
        if s_pos > h or s_neg < -h:
            flags[i] = True
            if s_pos > h:
                s_pos = 0.0
            if s_neg < -h:
                s_neg = 0.0
    return flags


def detect(
    values: NDArray[np.float64],
    period: int = 96,
    z_threshold: float = 3.5,
    k: float = 0.5,
    h: float = 5.0,
) -> list[dict]:
    """
    Detect anomalies using seasonal decomposition + robust z-score + CUSUM.

    Returns list of dicts for each anomalous index:
    {index, score, method (zscore, cusum or both), direction (high or low)}
    """
    _, _, resid = seasonal_decompose(values, period)
    z = robust_zscore(resid)
    cusum_flags = cusum(z, k=k, h=h)

    anomalies = []
    for i in range(len(values)):
        if np.isnan(z[i]):
            continue
        z_flag = abs(z[i]) > z_threshold
        c_flag = cusum_flags[i]
        if z_flag or c_flag:
            methods = []
            if z_flag:
                methods.append("zscore")
            if c_flag:
                methods.append("cusum")
            direction = "high" if z[i] > 0 else "low"
            anomalies.append(
                {
                    "index": i,
                    "score": round(float(abs(z[i])), 2),
                    "method": "both" if len(methods) == 2 else methods[0],
                    "direction": direction,
                }
            )
    return anomalies
