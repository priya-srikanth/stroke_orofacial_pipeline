"""Cross-session endpoint primitive (Phase 8a.5).

One endpoint: :func:`inter_session_persistence`. Q9 #2 — lag-k Pearson
autocorrelation of any per-session metric over the ordered session axis.

Input contract (plan decision D11): a plain ordered ``np.ndarray`` of
per-session metric values. The caller (Phase 8a.7 report writer) handles
the ``date → metric_value`` extraction so this primitive stays numerically
pure and trivially fixture-testable.

NaN handling: pairs ``(x[i], x[i+lag])`` where either element is NaN are
dropped before the correlation is computed. Surviving-pair count is
reported in provenance + in the aggregate so downstream stats can gate
on sample size.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult


def inter_session_persistence(
    metric_sequence: np.ndarray,
    *,
    endpoints_v2_params: dict[str, Any],
) -> EndpointResult:
    """Compute lag-k Pearson autocorrelation of an ordered per-session metric.

    Parameters
    ----------
    metric_sequence : np.ndarray
        1-D ordered array of per-session metric values. Session ordering is
        the caller's responsibility (typically by session date ascending);
        this function operates purely on array position.
    endpoints_v2_params : dict
        The ``spout_behavior.endpoints_v2`` block. Reads
        ``inter_session_persistence.lag`` (default config: 1).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"lag_k_autocorr": float,
          "n_pairs": int, "lag_k": int}``. Autocorrelation is NaN when
          ``n_pairs < 2`` or when either side of the pair has zero variance.
        - ``per_trial_array``: ``None`` (this is a session-axis metric).
        - ``per_trial_type_split``: ``None``.
    """
    lag = int(endpoints_v2_params["inter_session_persistence"]["lag"])
    if lag < 1:
        raise ValueError(f"inter_session_persistence.lag must be >= 1, got {lag}")

    seq = np.asarray(metric_sequence, dtype=float)
    if seq.ndim != 1:
        raise ValueError(f"metric_sequence must be 1-D, got shape {seq.shape}")

    n_input = seq.size
    if n_input <= lag:
        # No eligible pairs.
        return _result(float("nan"), 0, lag, n_input, endpoints_v2_params)

    x = seq[:-lag]
    y = seq[lag:]
    mask = ~np.isnan(x) & ~np.isnan(y)
    x_clean = x[mask]
    y_clean = y[mask]
    n_pairs = int(mask.sum())

    if n_pairs < 2:
        return _result(float("nan"), n_pairs, lag, n_input, endpoints_v2_params)

    # np.corrcoef returns a 2x2 matrix; off-diagonal is the Pearson r. It
    # emits an (unavoidable) RuntimeWarning when either input has zero
    # variance; we detect that case up-front to avoid the warning and to
    # return a clean NaN rather than whatever nan/inf np.corrcoef produces.
    if np.std(x_clean) == 0.0 or np.std(y_clean) == 0.0:
        return _result(float("nan"), n_pairs, lag, n_input, endpoints_v2_params)

    r = float(np.corrcoef(x_clean, y_clean)[0, 1])
    return _result(r, n_pairs, lag, n_input, endpoints_v2_params)


def _result(
    autocorr: float,
    n_pairs: int,
    lag: int,
    n_input: int,
    endpoints_v2_params: dict[str, Any],
) -> EndpointResult:
    return EndpointResult(
        per_session_aggregate={
            "lag_k_autocorr": autocorr,
            "n_pairs": n_pairs,
            "lag_k": lag,
        },
        per_trial_array=None,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "inter_session_persistence",
            "config_snapshot": copy.deepcopy(endpoints_v2_params),
            "n_trials_input": n_input,
            "n_trials_used": n_pairs,
        },
    )
