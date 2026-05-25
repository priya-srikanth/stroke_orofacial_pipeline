"""Multiple-comparisons correction helpers for Phase 9 stats results.

Two scalar corrections:

- :func:`benjamini_hochberg_fdr` — Benjamini-Hochberg false discovery rate
  (1995). Returns adjusted p-values + a boolean reject array at the
  specified ``alpha``. Less conservative than Bonferroni; controls
  expected proportion of false discoveries among rejections.
- :func:`bonferroni_correct` — family-wise error rate control via
  ``p_adj = min(1, p * n)``. More conservative.

Plus a DataFrame-level wrapper :func:`apply_correction_to_results_df`
that applies one of the above within "families" (e.g. one correction
per (axis, granularity) per the Phase 9 kickoff convention).

Convention for "family" in Phase 9: a family is the set of related tests
that share a hypothesis structure and a single FDR budget. Per the
kickoff Task 4 plan, families are partitioned by (axis, granularity)
unless otherwise specified — e.g. all ``per_session`` spatial-axis tests
share one BH budget, separately from all ``per_bin`` spatial-axis tests.

NaN p-values are treated as not-rejected and propagate as NaN through
``p_adj``. The reject array is False at NaN positions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control


CorrectionMethod = Literal["bh_fdr", "bonferroni"]


def _validate_p_values(p_values: np.ndarray) -> np.ndarray:
    """Cast to float ndarray + validate range."""
    arr = np.asarray(p_values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if len(finite) > 0 and (finite.min() < 0 or finite.max() > 1):
        raise ValueError(
            f"p_values must be in [0, 1]; got min={finite.min():.4g}, "
            f"max={finite.max():.4g}.",
        )
    return arr


def benjamini_hochberg_fdr(
    p_values: Sequence[float] | np.ndarray,
    *,
    alpha: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """Benjamini-Hochberg FDR adjustment.

    Parameters
    ----------
    p_values : Sequence[float] or ndarray
        Raw p-values from individual tests in one family.
    alpha : float, default 0.05
        FDR level — expected proportion of false discoveries among
        rejections.

    Returns
    -------
    p_adj : np.ndarray
        BH-adjusted p-values (monotone-increasing, clipped at 1).
        NaN inputs propagate as NaN.
    reject : np.ndarray (bool)
        ``p_adj <= alpha``. False for NaN positions.

    Notes
    -----
    Backed by :func:`scipy.stats.false_discovery_control` (requires
    scipy >= 1.11). NaN p-values are excluded from the rank-based
    adjustment and re-inserted as NaN at their original positions.

    For an empty input ``returns (np.array([]), np.array([]))``.
    """
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}.")
    arr = _validate_p_values(p_values)
    if arr.size == 0:
        return np.array([]), np.array([], dtype=bool)

    mask = ~np.isnan(arr)
    if mask.sum() == 0:
        p_adj = np.full_like(arr, np.nan)
        reject = np.zeros_like(arr, dtype=bool)
        return p_adj, reject

    adj_known = false_discovery_control(arr[mask], method="bh")
    p_adj = np.full_like(arr, np.nan)
    p_adj[mask] = adj_known
    reject = np.where(np.isnan(p_adj), False, p_adj <= alpha)
    return p_adj, reject


def bonferroni_correct(
    p_values: Sequence[float] | np.ndarray,
    *,
    alpha: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """Bonferroni FWER correction.

    ``p_adj = min(1, p * n)`` where ``n`` is the count of non-NaN
    p-values in the input. NaN inputs propagate as NaN; reject is False
    at NaN positions.

    Parameters
    ----------
    p_values : Sequence[float] or ndarray
    alpha : float, default 0.05
        Family-wise error rate.

    Returns
    -------
    p_adj : np.ndarray
        Bonferroni-adjusted p-values, clipped at 1.
    reject : np.ndarray (bool)
        ``p_adj <= alpha``. False for NaN positions.
    """
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1); got {alpha}.")
    arr = _validate_p_values(p_values)
    if arr.size == 0:
        return np.array([]), np.array([], dtype=bool)
    n = int(np.sum(~np.isnan(arr)))
    if n == 0:
        p_adj = np.full_like(arr, np.nan)
        reject = np.zeros_like(arr, dtype=bool)
        return p_adj, reject
    p_adj = np.minimum(arr * n, 1.0)
    reject = np.where(np.isnan(p_adj), False, p_adj <= alpha)
    return p_adj, reject


def apply_correction_to_results_df(
    results_df: pd.DataFrame,
    *,
    method: CorrectionMethod = "bh_fdr",
    group_cols: Sequence[str] = ("axis", "granularity"),
    p_value_col: str = "p_value",
    alpha: float = 0.05,
    p_adj_col: str = "p_adj",
    reject_col: str = "reject",
) -> pd.DataFrame:
    """Apply per-family multiple-comparisons correction to a results table.

    Each unique combination of ``group_cols`` values defines one
    "family". The correction is applied INDEPENDENTLY within each
    family — distinct families share no FDR/FWER budget.

    Per the Phase 9 kickoff Task 4 plan, the default family partition
    is ``("axis", "granularity")``: each (axis, granularity) pair is its
    own family. Adjust ``group_cols`` for analyses that want a different
    family structure (e.g. just ``("axis",)`` for an axis-wide budget).

    Parameters
    ----------
    results_df : pd.DataFrame
        Long-format results table from Task 4 fit_* model functions.
        Must contain ``p_value_col`` and all ``group_cols``.
    method : {"bh_fdr", "bonferroni"}, default "bh_fdr"
        Correction strategy.
    group_cols : Sequence[str], default ("axis", "granularity")
        Family partition. Pass ``()`` for a single global correction.
    p_value_col : str, default "p_value"
    alpha : float, default 0.05
    p_adj_col : str, default "p_adj"
        Output column name for adjusted p-values.
    reject_col : str, default "reject"
        Output column name for the boolean reject array.

    Returns
    -------
    pd.DataFrame
        Copy of ``results_df`` with two added columns (``p_adj_col`` and
        ``reject_col``). Original row order is preserved.

    Raises
    ------
    KeyError
        If ``p_value_col`` or any ``group_cols`` are missing from
        ``results_df``.
    ValueError
        If ``method`` is unsupported.
    """
    if method not in ("bh_fdr", "bonferroni"):
        raise ValueError(
            f"method must be 'bh_fdr' or 'bonferroni'; got {method!r}.",
        )
    required = {p_value_col, *group_cols}
    missing = required - set(results_df.columns)
    if missing:
        raise KeyError(
            f"results_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(results_df.columns)}.",
        )

    correct_fn = {
        "bh_fdr": benjamini_hochberg_fdr,
        "bonferroni": bonferroni_correct,
    }[method]

    out = results_df.copy()
    out[p_adj_col] = np.nan
    out[reject_col] = False

    if not group_cols:
        # Single global family.
        p_adj, reject = correct_fn(out[p_value_col].to_numpy(), alpha=alpha)
        out[p_adj_col] = p_adj
        out[reject_col] = reject
        return out

    # Per-family correction. groupby preserves row order within each
    # group via .indices (positional indexing).
    for _key, idx in out.groupby(list(group_cols), dropna=False).indices.items():
        family_p = out.iloc[idx][p_value_col].to_numpy()
        p_adj, reject = correct_fn(family_p, alpha=alpha)
        out.iloc[idx, out.columns.get_loc(p_adj_col)] = p_adj
        out.iloc[idx, out.columns.get_loc(reject_col)] = reject
    return out
