from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import stats


def mann_whitney(
    before: NDArray[np.float64], after: NDArray[np.float64], alpha: float = 0.05
) -> dict:
    """
    Two-sided Mann-Whitney U test using scipy.stats.mannwhitneyu.

    Returns dict with u, pValue, significant, medianBefore, medianAfter, n_before, n_after.
    Raises ValueError if either sample has < 3 non-NaN values.
    """
    before_clean = before[~np.isnan(before)]
    after_clean = after[~np.isnan(after)]

    if len(before_clean) < 3 or len(after_clean) < 3:
        raise ValueError("Each sample must have at least 3 non-NaN values")

    u_stat, p_value = stats.mannwhitneyu(before_clean, after_clean, alternative="two-sided")

    return {
        "u": float(u_stat),
        "pValue": float(p_value),
        "significant": bool(p_value < alpha),
        "medianBefore": float(np.median(before_clean)),
        "medianAfter": float(np.median(after_clean)),
        "n_before": int(len(before_clean)),
        "n_after": int(len(after_clean)),
    }
