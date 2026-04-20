"""Engagement-extras endpoint primitives (Phase 8a.6).

Two small per-session endpoints surfaced by the Phase 8a archaeology (§3)
as cheap additions beyond the original Q9 list but scientifically useful
for recovery-trajectory analysis:

- :func:`reward_trial_count_per_session` — per-side rewarded-trial counts.
  Engagement/motivation proxy; stroke-recovering animals typically maintain
  or increase trial counts, non-recoverers plateau or decline.
- :func:`inter_trial_interval_distribution` — mean / median / std / n of
  consecutive-reward gaps per side. Task-pace / motivation proxy. Raw
  per-ITI distribution is deferred (plan decision D13); only the summary
  lands in the per-session JSON.

Both operate directly on the Phase 2 ``licks_and_rewards`` NPZ's reward-
index arrays, with no dependence on the ``TrialRecord`` structure.

The ``engagement`` feature gates in ``defaults.yaml``
(``compute_reward_trial_count_per_session``, ``compute_inter_trial_interval_distribution``)
are the *caller's* responsibility; these primitives always compute when
called. The gate values are echoed into provenance for traceability.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult


# ---------------------------------------------------------------------------
# reward_trial_count_per_session
# ---------------------------------------------------------------------------


def reward_trial_count_per_session(
    reward_indices: dict[str, np.ndarray],
    *,
    endpoints_v2_params: dict[str, Any],
) -> EndpointResult:
    """Report per-side + total rewarded-trial counts for a session.

    Parameters
    ----------
    reward_indices : dict
        ``{"Reward_L": np.ndarray, "Reward_R": np.ndarray}`` — reward-onset
        sample indices, as produced by Phase 2's lick-and-reward detection.
    endpoints_v2_params : dict
        ``spout_behavior.endpoints_v2`` config block (snapshot for provenance).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"L": int, "R": int, "total": int}``.
        - ``per_trial_array``: ``None``.
        - ``per_trial_type_split``: ``None`` (the aggregate is already the split).
    """
    n_L = int(np.asarray(reward_indices.get("Reward_L", [])).size)
    n_R = int(np.asarray(reward_indices.get("Reward_R", [])).size)
    return EndpointResult(
        per_session_aggregate={"L": n_L, "R": n_R, "total": n_L + n_R},
        per_trial_array=None,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "reward_trial_count_per_session",
            "config_snapshot": copy.deepcopy(endpoints_v2_params),
            "n_trials_input": n_L + n_R,
            "n_trials_used": n_L + n_R,
        },
    )


# ---------------------------------------------------------------------------
# inter_trial_interval_distribution
# ---------------------------------------------------------------------------


def _iti_stats(iti_samples: np.ndarray, Fs: float) -> dict[str, float]:
    """Mean/median/std/n of an ITI array. NaN stats when n<1 (mean/median) or n<2 (std)."""
    n = int(iti_samples.size)
    if n == 0:
        return {
            "mean_s": float("nan"), "median_s": float("nan"),
            "std_s": float("nan"), "n": 0,
        }
    iti_s = iti_samples.astype(float) / Fs
    return {
        "mean_s": float(np.mean(iti_s)),
        "median_s": float(np.median(iti_s)),
        "std_s": float(np.std(iti_s, ddof=0)) if n >= 2 else float("nan"),
        "n": n,
    }


def inter_trial_interval_distribution(
    reward_indices: dict[str, np.ndarray],
    Fs: float,
    *,
    endpoints_v2_params: dict[str, Any],
) -> EndpointResult:
    """Summary stats of consecutive-reward gaps per side and overall.

    An ITI is the gap (in seconds) between consecutive reward events on the
    same side. A side with fewer than 2 reward events contributes 0 ITIs.

    Parameters
    ----------
    reward_indices : dict
        ``{"Reward_L": np.ndarray, "Reward_R": np.ndarray}``.
    Fs : float
        Sampling rate in Hz (for samples → seconds).
    endpoints_v2_params : dict
        ``spout_behavior.endpoints_v2`` block (snapshot for provenance).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: combined-sides summary
          ``{"mean_s", "median_s", "std_s", "n"}`` over stacked L+R ITIs.
        - ``per_trial_array``: ``None`` (raw distribution not stored;
          deferred per plan decision D13).
        - ``per_trial_type_split``: per-side dicts of the same summary.
    """
    r_L = np.asarray(reward_indices.get("Reward_L", []), dtype=int)
    r_R = np.asarray(reward_indices.get("Reward_R", []), dtype=int)

    # Sort inputs defensively — ITI requires monotonic ordering. Phase 2
    # arrays are already sorted but the cost is trivial and the safety
    # margin is real.
    iti_L = np.diff(np.sort(r_L))
    iti_R = np.diff(np.sort(r_R))
    iti_all = np.concatenate([iti_L, iti_R])

    return EndpointResult(
        per_session_aggregate=_iti_stats(iti_all, Fs),
        per_trial_array=None,
        per_trial_type_split={
            "L": _iti_stats(iti_L, Fs),
            "R": _iti_stats(iti_R, Fs),
        },
        provenance={
            "endpoint_name": "inter_trial_interval_distribution",
            "config_snapshot": copy.deepcopy(endpoints_v2_params),
            "n_trials_input": int(r_L.size + r_R.size),
            "n_trials_used": int(iti_all.size),
            "Fs": float(Fs),
        },
    )
