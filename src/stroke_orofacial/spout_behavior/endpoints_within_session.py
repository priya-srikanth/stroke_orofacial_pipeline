"""Within-session trend endpoint primitives (Phase 8a.4).

Both endpoints are *metric-agnostic* — they accept a caller-supplied
``metric_extractor: Callable[[TrialRecord], float]`` and operate on the
extracted per-trial scalar series. Testable against synthetic fixtures
with any arbitrary metric (e.g., ``lambda t: t.trial_idx`` for monotonic
inputs). The Phase 8a default per-trial metric wired by the 8a.7 report
writer is first-correct-lick latency (plan decision D7).

Endpoints:

- :func:`within_session_learning_curve` — Q9 #1. Bins trials into ``n_bins``
  equal-size ordinal-position bins, reports per-bin means + early-vs-late
  difference + within-session linear slope. All three views live in
  ``per_session_aggregate`` so Phase 9 consumers pick whichever shape they want
  without having to recompute.
- :func:`within_session_change` — Q9 #4. Single-number linear-trend slope of
  metric vs trial-ordinal. ``detrend_method`` config key supports
  ``"linear"`` in Phase 8a; ``"theil_sen"`` / ``"loess"`` raise
  ``NotImplementedError`` (reserved for Phase 9 polish).

NaN handling: per-trial NaN metric values are dropped before aggregation in
both endpoints. Per-bin means are computed over non-NaN values; if a bin is
all-NaN (or empty), its mean is NaN.
"""
from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


def _extract_metric_values(
    trials: Sequence[TrialRecord],
    metric_extractor: Callable[[TrialRecord], float],
) -> np.ndarray:
    """Apply metric_extractor to every trial, returning a float array."""
    if not trials:
        return np.array([], dtype=float)
    return np.array([float(metric_extractor(t)) for t in trials], dtype=float)


def _linear_slope(metric_values: np.ndarray) -> float:
    """Least-squares slope of metric vs trial-ordinal; NaN when under-determined."""
    mask = ~np.isnan(metric_values)
    if int(mask.sum()) < 2:
        return float("nan")
    x = np.arange(metric_values.size, dtype=float)[mask]
    y = metric_values[mask]
    # Fully-collinear x-variance guard: if only one unique x-value remains,
    # polyfit is undefined. (Impossible unless fewer than 2 trials survive,
    # which the mask.sum() < 2 check above already catches.)
    slope, _ = np.polyfit(x, y, deg=1)
    return float(slope)


# ---------------------------------------------------------------------------
# within_session_learning_curve (Q9 #1)
# ---------------------------------------------------------------------------


def within_session_learning_curve(
    trials: Sequence[TrialRecord],
    *,
    metric_extractor: Callable[[TrialRecord], float],
    endpoints_params: dict[str, Any],
    metric_name: str = "unspecified",
) -> EndpointResult:
    """Bin trials by ordinal position, report per-bin mean + early-vs-late + slope.

    Bins are built via ``numpy.array_split`` — for N trials and B bins each
    bin holds either ``ceil(N/B)`` or ``floor(N/B)`` trials; leftover-size
    differences land in the earlier bins. When ``n_bins > n_trials``, excess
    bins are empty and report NaN means.

    Parameters
    ----------
    trials : Sequence[TrialRecord]
    metric_extractor : Callable[[TrialRecord], float]
        Per-trial scalar extractor. May return NaN; such trials drop out of
        the per-bin means and linear slope.
    endpoints_params : dict
        The ``spout_behavior.endpoints`` config block. Reads
        ``within_session_learning_curve.n_bins``.
    metric_name : str
        Human-readable metric label, stored in provenance for later traceability.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"per_bin_means": list[float],
          "early_vs_late_diff": float, "linear_slope_per_trial": float,
          "n_bins": int, "n_trials_valid": int}``.
        - ``per_trial_array``: the extracted per-trial metric values (NaN
          where ``metric_extractor`` returned NaN).
        - ``per_trial_type_split``: ``None`` (grouping is temporal, not side-wise).
    """
    n_bins = int(endpoints_params["within_session_learning_curve"]["n_bins"])
    metric_values = _extract_metric_values(trials, metric_extractor)

    n_trials = metric_values.size
    n_valid = int(np.count_nonzero(~np.isnan(metric_values)))

    if n_trials == 0:
        per_bin_means = [float("nan")] * n_bins
    else:
        # array_split returns n_bins chunks even when n_trials < n_bins (excess
        # chunks are empty arrays — their mean is NaN by convention below).
        bin_values = np.array_split(metric_values, n_bins)
        per_bin_means = []
        for bv in bin_values:
            if bv.size == 0:
                per_bin_means.append(float("nan"))
                continue
            mask = ~np.isnan(bv)
            if not mask.any():
                per_bin_means.append(float("nan"))
            else:
                per_bin_means.append(float(np.mean(bv[mask])))

    # early-vs-late: last bin minus first bin (NaN-propagating).
    early_vs_late = per_bin_means[-1] - per_bin_means[0] if n_bins >= 1 else float("nan")
    slope = _linear_slope(metric_values)

    return EndpointResult(
        per_session_aggregate={
            "per_bin_means": per_bin_means,
            "early_vs_late_diff": float(early_vs_late),
            "linear_slope_per_trial": float(slope),
            "n_bins": n_bins,
            "n_trials_valid": n_valid,
        },
        per_trial_array=metric_values,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "within_session_learning_curve",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": n_trials,
            "n_trials_used": n_valid,
            "metric_name": metric_name,
        },
    )


# ---------------------------------------------------------------------------
# within_session_change (Q9 #4)
# ---------------------------------------------------------------------------


def within_session_change(
    trials: Sequence[TrialRecord],
    *,
    metric_extractor: Callable[[TrialRecord], float],
    endpoints_params: dict[str, Any],
    metric_name: str = "unspecified",
) -> EndpointResult:
    """Single-number within-session linear-trend slope of metric vs trial ordinal.

    Supports ``detrend_method="linear"`` (least-squares) in Phase 8a. Other
    values raise ``NotImplementedError`` — space reserved for Theil-Sen /
    LOESS alternatives in Phase 9.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"slope_per_trial": float,
          "detrend_method": str, "n_trials_valid": int}``.
        - ``per_trial_array``: the extracted per-trial metric values.
        - ``per_trial_type_split``: ``None``.
    """
    method = endpoints_params["within_session_change"]["detrend_method"]
    if method != "linear":
        raise NotImplementedError(
            f"within_session_change.detrend_method={method!r} reserved for "
            "Phase 9 polish; only 'linear' is supported."
        )

    metric_values = _extract_metric_values(trials, metric_extractor)
    n_valid = int(np.count_nonzero(~np.isnan(metric_values)))
    slope = _linear_slope(metric_values)

    return EndpointResult(
        per_session_aggregate={
            "slope_per_trial": float(slope),
            "detrend_method": method,
            "n_trials_valid": n_valid,
        },
        per_trial_array=metric_values,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "within_session_change",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": metric_values.size,
            "n_trials_used": n_valid,
            "metric_name": metric_name,
        },
    )
