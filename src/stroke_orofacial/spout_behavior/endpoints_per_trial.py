"""Per-trial endpoint primitives (Phase 8a.3).

Four pure-function endpoints consuming a ``list[TrialRecord]`` from
:mod:`stroke_orofacial.spout_behavior.trial_segmentation` and returning an
:class:`EndpointResult`. All functions are side-effect-free — no I/O, no
plotting, no config loading — so they are fully testable against synthetic
fixtures.

Endpoints implemented:

- :func:`first_lick_latency_per_trial` — Q9 #7, legacy A10 re-package.
- :func:`directional_lick_accuracy_per_session` — Q9 #6 extension of legacy A7/A9.
- :func:`switch_cost_per_session` — Q9 #5, distinct from legacy A12 lick-direction
  switch rate; contrasts trial N's performance based on trial (N-1)'s reward side.
- :func:`latency_variability_per_session` — Q9 #8, re-packaged from A10's
  by-product mean+std into std / CV / IQR / n per side.

The Phase 8a default "per-trial performance metric" for ``switch_cost`` is
first-lick latency (on the correct side). The original kickoff proposed
using ``criteria_34_pass`` as the performance metric, but C3/C4 recomputation
is deferred to Phase 8a.7 (the report writer), so latency is the primary
metric here and ``criteria_34_pass`` lands alongside once 8a.7 ports the
criteria logic. See the approved plan at
``C:\\Users\\sabatini\\.claude\\plans\\jaunty-foraging-scott.md`` (D7, D8).
"""
from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


# ---------------------------------------------------------------------------
# Shared helper — per-trial first-correct-lick latency
# ---------------------------------------------------------------------------


def _first_correct_lick_latency_s(trial: TrialRecord) -> float:
    """Return seconds from reward onset to first correct-side lick in window.

    "Correct side" = ``trial.reward_side``. ``NaN`` if no correct-side lick
    falls in the scoring window.
    """
    correct_licks = (
        trial.licks_L_indices_in_window
        if trial.reward_side == "L"
        else trial.licks_R_indices_in_window
    )
    if correct_licks.size == 0:
        return float("nan")
    return float((correct_licks[0] - trial.reward_idx) / trial.Fs)


def _per_trial_latencies(trials: Sequence[TrialRecord]) -> np.ndarray:
    """Vector of first-correct-lick latencies (NaN where absent)."""
    return np.array([_first_correct_lick_latency_s(t) for t in trials], dtype=float)


def _mean_std(values: np.ndarray) -> dict[str, float]:
    """Compute mean/std/n over non-NaN values; NaN/0 when no values."""
    mask = ~np.isnan(values)
    n = int(mask.sum())
    if n == 0:
        return {"mean": float("nan"), "std": float("nan"), "n": 0}
    vals = values[mask]
    return {
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals, ddof=0)),
        "n": n,
    }


# ---------------------------------------------------------------------------
# Endpoint 1: first-lick latency (per-trial, Q9 #7)
# ---------------------------------------------------------------------------


def first_lick_latency_per_trial(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Compute per-trial first-correct-lick latency.

    Legacy A10 re-package (archaeology §2). Preserves per-trial granularity
    (required downstream by :func:`latency_variability_per_session` and
    within-session trend endpoints).

    Returns
    -------
    EndpointResult
        - ``per_trial_array``: per-trial latency in seconds (NaN where no
          correct-side lick in window).
        - ``per_session_aggregate``: ``{"mean": ..., "std": ..., "n": ...}``
          over the non-NaN latencies.
        - ``per_trial_type_split``: per-side dict of the same summary.
    """
    latencies = _per_trial_latencies(trials)
    sides = np.array([t.reward_side for t in trials], dtype=object)

    per_side = {
        side: _mean_std(latencies[sides == side] if latencies.size else latencies)
        for side in ("L", "R")
    }
    # n_trials_used counts trials with a correct-side lick in window.
    n_used = int(np.count_nonzero(~np.isnan(latencies)))

    return EndpointResult(
        per_session_aggregate=_mean_std(latencies),
        per_trial_array=latencies,
        per_trial_type_split=per_side,
        provenance={
            "endpoint_name": "first_lick_latency_per_trial",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": len(trials),
            "n_trials_used": n_used,
        },
    )


# ---------------------------------------------------------------------------
# Endpoint 2: directional lick accuracy (Q9 #6, extends A7/A9)
# ---------------------------------------------------------------------------


def directional_lick_accuracy_per_session(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Per-reward-side fraction of trials where correct-side licks dominate.

    For each trial, counts licks on the correct (rewarded) side and on the
    incorrect side within the scoring window. A trial is classified as
    "correct" iff ``correct_count >= incorrect_count AND correct_count >= 1``
    — a simple directional-dominance rule chosen here because the stricter
    legacy C3/C4 criteria port doesn't land until Phase 8a.7. Once that
    lands, the report writer can swap in C3∩C4 as the per-trial pass rule.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"fraction_correct_on_L_trials": float,
          "fraction_correct_on_R_trials": float}``. Either fraction is NaN
          when there are no trials on that side.
        - ``per_trial_array``: ``None`` (counts live in ``per_trial_type_split``).
        - ``per_trial_type_split``: per-side dict with ``counts_correct`` (list),
          ``counts_incorrect`` (list), ``n_trials`` (int).
    """
    sides = np.array([t.reward_side for t in trials], dtype=object)

    def _pair_counts(t: TrialRecord) -> tuple[int, int]:
        if t.reward_side == "L":
            return int(t.licks_L_indices_in_window.size), int(t.licks_R_indices_in_window.size)
        return int(t.licks_R_indices_in_window.size), int(t.licks_L_indices_in_window.size)

    pair_counts = np.array([_pair_counts(t) for t in trials], dtype=int) if trials else np.zeros((0, 2), dtype=int)

    per_side: dict[str, dict[str, Any]] = {}
    fractions: dict[str, float] = {}
    for side in ("L", "R"):
        mask = sides == side if sides.size else np.zeros(0, dtype=bool)
        side_counts = pair_counts[mask] if pair_counts.size else pair_counts
        n_trials = int(mask.sum())
        if n_trials == 0:
            fractions[f"fraction_correct_on_{side}_trials"] = float("nan")
            per_side[side] = {
                "counts_correct": [], "counts_incorrect": [], "n_trials": 0
            }
            continue
        correct = side_counts[:, 0]
        incorrect = side_counts[:, 1]
        trial_correct = (correct >= incorrect) & (correct >= 1)
        fractions[f"fraction_correct_on_{side}_trials"] = float(np.mean(trial_correct))
        per_side[side] = {
            "counts_correct": correct.tolist(),
            "counts_incorrect": incorrect.tolist(),
            "n_trials": n_trials,
        }

    return EndpointResult(
        per_session_aggregate=fractions,
        per_trial_array=None,
        per_trial_type_split=per_side,
        provenance={
            "endpoint_name": "directional_lick_accuracy_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": len(trials),
            "n_trials_used": len(trials),
        },
    )


# ---------------------------------------------------------------------------
# Endpoint 3: switch cost (Q9 #5)
# ---------------------------------------------------------------------------


def switch_cost_per_session(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Contrast of trial-N performance on "switch" vs "same-side-continuation" trials.

    Classifies each trial N ≥ 1 by whether its reward side matches trial
    N-1's reward side (same-side-continuation) or not (switch). The first
    trial has no prior-trial context and is excluded from both classes.

    Performance metric (Phase 8a default): first-correct-lick latency. Per
    plan decision D8 — ``criteria_34_pass`` as alternative will be wired in
    Phase 8a.7 once C3/C4 computation ports.

    Config requirement: ``switch_cost.same_side_baseline_definition`` must be
    ``"immediately_prior_trial"``. Other values raise ``NotImplementedError``
    — space is reserved for N-back averaging but unused in this sub-phase.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"switch_cost_s": float,
          "mean_latency_same_side_s": float, "mean_latency_switch_s": float,
          "n_same_side_trials": int, "n_switch_trials": int}``. ``switch_cost_s``
          = ``mean_latency_switch_s - mean_latency_same_side_s``; NaN when
          either class is empty.
        - ``per_trial_array``: ``None`` (classification + latencies
          recoverable from ``first_lick_latency_per_trial`` + trial ordering).
        - ``per_trial_type_split``: ``None`` (the decomposition is temporal,
          not side-wise).
    """
    baseline = endpoints_params.get("switch_cost", {}).get(
        "same_side_baseline_definition", "immediately_prior_trial"
    )
    if baseline != "immediately_prior_trial":
        raise NotImplementedError(
            f"switch_cost.same_side_baseline_definition={baseline!r} is reserved "
            "for a future phase; only 'immediately_prior_trial' is supported."
        )

    latencies = _per_trial_latencies(trials)
    sides = [t.reward_side for t in trials]
    n_trials = len(trials)

    same_latencies: list[float] = []
    switch_latencies: list[float] = []
    for n in range(1, n_trials):
        prev, curr = sides[n - 1], sides[n]
        if np.isnan(latencies[n]):
            continue
        (same_latencies if prev == curr else switch_latencies).append(latencies[n])

    def _safe_mean(xs: list[float]) -> float:
        return float(np.mean(xs)) if xs else float("nan")

    mean_same = _safe_mean(same_latencies)
    mean_switch = _safe_mean(switch_latencies)
    cost = mean_switch - mean_same  # NaN if either is NaN — documented above

    return EndpointResult(
        per_session_aggregate={
            "switch_cost_s": float(cost),
            "mean_latency_same_side_s": mean_same,
            "mean_latency_switch_s": mean_switch,
            "n_same_side_trials": len(same_latencies),
            "n_switch_trials": len(switch_latencies),
        },
        per_trial_array=None,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "switch_cost_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": n_trials,
            "n_trials_used": len(same_latencies) + len(switch_latencies),
            "performance_metric": "first_correct_lick_latency_s",
        },
    )


# ---------------------------------------------------------------------------
# Endpoint 4: latency variability (Q9 #8, re-package of A10 by-product)
# ---------------------------------------------------------------------------


def latency_variability_per_session(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Dispersion statistics (std, CV, IQR, n) on per-trial first-lick latency.

    Consumes the same per-trial latency array as :func:`first_lick_latency_per_trial`.
    Per plan decision D9 reports std + CV + IQR + n, with a per-side split.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"std_s": float, "cv": float,
          "iqr_s": float, "n": int}``. CV and IQR/std are NaN when n < 2 or
          mean is zero.
        - ``per_trial_array``: ``None`` (retrieve per-trial latencies from
          :func:`first_lick_latency_per_trial`).
        - ``per_trial_type_split``: per-side dict of the same fields.
    """
    latencies = _per_trial_latencies(trials)
    sides = np.array([t.reward_side for t in trials], dtype=object)

    def _dispersion(vals: np.ndarray) -> dict[str, Any]:
        mask = ~np.isnan(vals)
        n = int(mask.sum())
        if n == 0:
            return {"std_s": float("nan"), "cv": float("nan"),
                    "iqr_s": float("nan"), "n": 0}
        clean = vals[mask]
        std = float(np.std(clean, ddof=0))
        mean = float(np.mean(clean))
        cv = float(std / mean) if mean != 0.0 else float("nan")
        if n >= 2:
            q75, q25 = np.percentile(clean, [75, 25])
            iqr = float(q75 - q25)
        else:
            iqr = float("nan")
        return {"std_s": std, "cv": cv, "iqr_s": iqr, "n": n}

    per_side = {
        side: _dispersion(latencies[sides == side] if latencies.size else latencies)
        for side in ("L", "R")
    }

    return EndpointResult(
        per_session_aggregate=_dispersion(latencies),
        per_trial_array=None,
        per_trial_type_split=per_side,
        provenance={
            "endpoint_name": "latency_variability_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": len(trials),
            "n_trials_used": int(np.count_nonzero(~np.isnan(latencies))),
        },
    )
