"""Engagement-extras endpoint primitives (Phase 8a.6).

Two small per-session endpoints surfaced by the Phase 8a archaeology (§3)
as cheap additions beyond the original Q9 list but scientifically useful
for recovery-trajectory analysis:

- :func:`tone_trial_count_per_session` — per-side trial-presented counts
  (number of tone cues fired on each spout side). Engagement / motivation
  proxy; stroke-recovering animals typically maintain or increase trial
  counts, non-recoverers plateau or decline. Q-C rename from the prior
  ``reward_trial_count_per_session`` (Phase 8a.10.1 audit lock
  2026-05-14): the metric counts EXPOSURES (trial cues presented), not
  REWARDS EARNED; under Case-2 universal the legacy ``Reward_*`` channel
  was the tone-cue channel, so the "rewarded trial count" name was a
  misnomer for "trials presented".
- :func:`inter_trial_interval_distribution` — mean / median / std / n of
  consecutive-tone gaps per side. Task-pace / motivation proxy. Raw
  per-ITI distribution is deferred (plan decision D13); only the summary
  lands in the per-session JSON. (Function name is event-class-agnostic
  and survives Q-C unchanged.)

Both operate directly on the Phase 2 ``licks_and_rewards`` NPZ's
tone-index arrays (Q-C: read ``Tone_L``/``Tone_R`` keys, not
``Reward_L``/``Reward_R``), with no dependence on the ``TrialRecord``
structure.

The ``engagement`` feature gates in ``defaults.yaml``
(``compute_tone_trial_count_per_session``,
``compute_inter_trial_interval_distribution``) are the *caller's*
responsibility; these primitives always compute when called. The gate
values are echoed into provenance for traceability.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult


# ---------------------------------------------------------------------------
# tone_trial_count_per_session
# ---------------------------------------------------------------------------


def tone_trial_count_per_session(
    tone_indices: dict[str, np.ndarray],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Report per-side + total trial-presented counts for a session.

    Q-C rename (2026-05-14): the function counts exposures (tones
    presented), not rewards earned. Under Case-2 universal the legacy
    ``Reward_*`` channel was the tone-cue channel, so the old name
    ``reward_trial_count_per_session`` was a misnomer; reads from
    ``Tone_L``/``Tone_R`` post-fix.

    Parameters
    ----------
    tone_indices : dict
        ``{"Tone_L": np.ndarray, "Tone_R": np.ndarray}`` — tone-onset
        sample indices, as produced by Phase 2's tone detection
        post-swap-fix.
    endpoints_params : dict
        ``spout_behavior.endpoints`` config block (snapshot for
        provenance).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"L": int, "R": int, "total": int}``.
        - ``per_trial_array``: ``None``.
        - ``per_trial_type_split``: ``None`` (the aggregate is already
          the split).
    """
    n_L = int(np.asarray(tone_indices.get("Tone_L", [])).size)
    n_R = int(np.asarray(tone_indices.get("Tone_R", [])).size)
    return EndpointResult(
        per_session_aggregate={"L": n_L, "R": n_R, "total": n_L + n_R},
        per_trial_array=None,
        per_trial_type_split=None,
        provenance={
            "endpoint_name": "tone_trial_count_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
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
    tone_indices: dict[str, np.ndarray],
    Fs: float,
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Summary stats of consecutive-tone gaps per side and overall.

    Q-C semantics (2026-05-14): an ITI is the gap (in seconds) between
    consecutive tone-cue events on the same side — i.e., the inter-trial
    interval as experienced by the animal. A side with fewer than 2
    tone events contributes 0 ITIs. (Function name survives Q-C
    unchanged because "inter-trial interval" is event-class-agnostic.)

    Parameters
    ----------
    tone_indices : dict
        ``{"Tone_L": np.ndarray, "Tone_R": np.ndarray}``.
    Fs : float
        Sampling rate in Hz (for samples → seconds).
    endpoints_params : dict
        ``spout_behavior.endpoints`` block (snapshot for provenance).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: combined-sides summary
          ``{"mean_s", "median_s", "std_s", "n"}`` over stacked L+R ITIs.
        - ``per_trial_array``: ``None`` (raw distribution not stored;
          deferred per plan decision D13).
        - ``per_trial_type_split``: per-side dicts of the same summary.
    """
    t_L = np.asarray(tone_indices.get("Tone_L", []), dtype=int)
    t_R = np.asarray(tone_indices.get("Tone_R", []), dtype=int)

    # Sort inputs defensively — ITI requires monotonic ordering. Phase 2
    # arrays are already sorted but the cost is trivial and the safety
    # margin is real.
    iti_L = np.diff(np.sort(t_L))
    iti_R = np.diff(np.sort(t_R))
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
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": int(t_L.size + t_R.size),
            "n_trials_used": int(iti_all.size),
            "Fs": float(Fs),
        },
    )
