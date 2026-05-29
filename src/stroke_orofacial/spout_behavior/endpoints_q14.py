"""Q-lock 14 per-session spout-behavior endpoints (net-new metrics #6, #7).

Two pure-function per-session endpoints introduced by Phase 9.1 Q-lock 14 that
did not already exist in the Phase 8a substrate (see kickoff Addendum #1 §3):

- :func:`accuracy_difference_index_per_session` — Q14 #6. A within-cue-side
  accuracy contrast, distinct from the Signal-Detection-Theory pair (#8 d',
  #9 c in :mod:`stroke_orofacial.spout_behavior.sdt`).
- :func:`licks_per_bout_per_session` — Q14 #7. Median bout size from the
  Phase 8a.2 lick-bout detector, scoped to trials of each cue side.

Both consume ``list[TrialRecord]`` and return :class:`EndpointResult`, matching
the Phase 8a.3 per-trial endpoint contract so they materialize through the same
Phase 9 inputs pipeline (and pick up the ``ipsi_contra`` column for free).

Stratification is by raw cue side (``tone_side`` ∈ {L, R}); the L/R → ipsi/contra
recoding happens downstream in the materializer, identically to every other
side-stratified endpoint. Keeping these on the L/R frame keeps one recoding
site in the codebase.
"""
from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

import numpy as np

from stroke_orofacial.spout_behavior.endpoint_result import EndpointResult
from stroke_orofacial.spout_behavior.lick_bouts import find_lick_bouts
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


def accuracy_difference_index_per_session(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Per-cue-side accuracy difference index (Q14 #6).

    For each cue side, pool licks across that side's trials into correct-side
    (= cued spout) and incorrect-side (= opposite spout) counts, then::

        ADI = (n_correct - n_incorrect) / (n_correct + n_incorrect)

    Bounded [-1, +1]: +1 = all licks on the cued side, -1 = all on the opposite
    side, 0 = balanced. ``NaN`` when a cue side has zero licks (empty
    denominator) — distinct from 0.0 (balanced licking).

    This is NOT a Signal-Detection-Theory metric: it measures within-side lick
    purity per cue side, not cross-side discrimination/bias (that is #8 d' / #9
    c). ``correct`` uses ``tone_side`` as the cued/correct side (Q-B.α
    convention, matching :func:`directional_lick_accuracy_per_session`).

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"accuracy_difference_index_on_L_trials":
          float, "accuracy_difference_index_on_R_trials": float}``.
        - ``per_trial_array``: ``None`` (counts live in ``per_trial_type_split``).
        - ``per_trial_type_split``: per-side ``{"n_correct", "n_incorrect",
          "n_trials"}``.
    """
    per_side: dict[str, dict[str, Any]] = {}
    aggregate: dict[str, float] = {}
    for side in ("L", "R"):
        side_trials = [t for t in trials if t.tone_side == side]
        n_correct = 0
        n_incorrect = 0
        for t in side_trials:
            n_on_L = int(t.licks_L_indices_in_window.size)
            n_on_R = int(t.licks_R_indices_in_window.size)
            if side == "L":
                n_correct += n_on_L
                n_incorrect += n_on_R
            else:
                n_correct += n_on_R
                n_incorrect += n_on_L
        denom = n_correct + n_incorrect
        aggregate[f"accuracy_difference_index_on_{side}_trials"] = (
            (n_correct - n_incorrect) / denom if denom > 0 else float("nan")
        )
        per_side[side] = {
            "n_correct": n_correct,
            "n_incorrect": n_incorrect,
            "n_trials": len(side_trials),
        }

    return EndpointResult(
        per_session_aggregate=aggregate,
        per_trial_array=None,
        per_trial_type_split=per_side,
        provenance={
            "endpoint_name": "accuracy_difference_index_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": len(trials),
            "n_trials_used": len(trials),
        },
    )


def licks_per_bout_per_session(
    trials: Sequence[TrialRecord],
    *,
    endpoints_params: dict[str, Any],
) -> EndpointResult:
    """Per-cue-side median licks-per-bout (Q14 #7).

    For each cue side, detect lick bouts WITHIN each of that side's trials
    (Priya-locked scoping, kickoff Addendum #1 §9 / §7-fork) and pool the bout
    sizes across trials; the per-session value is the median bout size. Bouts
    are detected per-trial (not across the concatenated session stream) so a
    bout never spans a trial boundary — consistent with "all bouts within
    cue-side trials".

    Each trial's lick stream merges both-spout licks in the scoring window
    (sorted by sample index) before bout detection, so a bout is a contiguous
    licking run regardless of which spout each lick landed on (matches the
    "all bouts" wording in the metric definition).

    Parameters
    ----------
    endpoints_params : dict
        The ``spout_behavior.endpoints.lick_bouts`` block: requires
        ``max_ili_ms`` (≤ this ILI stays within a bout; strict ``>`` splits) and
        ``min_bout_licks`` (runs below this are dropped). Passed straight to
        :func:`stroke_orofacial.spout_behavior.lick_bouts.find_lick_bouts`.

    Returns
    -------
    EndpointResult
        - ``per_session_aggregate``: ``{"median_licks_per_bout_on_L_trials":
          float, "median_licks_per_bout_on_R_trials": float}``. ``NaN`` when a
          cue side has no qualifying bouts.
        - ``per_trial_array``: ``None``.
        - ``per_trial_type_split``: per-side ``{"n_bouts", "n_trials",
          "bout_sizes"}``.
    """
    per_side: dict[str, dict[str, Any]] = {}
    aggregate: dict[str, float] = {}
    for side in ("L", "R"):
        side_trials = [t for t in trials if t.tone_side == side]
        bout_sizes: list[int] = []
        for t in side_trials:
            merged = np.sort(
                np.concatenate(
                    [t.licks_L_indices_in_window, t.licks_R_indices_in_window]
                )
            ).astype(np.int64)
            if merged.size == 0:
                continue
            bouts = find_lick_bouts(merged, t.Fs, endpoints_params)
            bout_sizes.extend(b.n_licks for b in bouts)
        aggregate[f"median_licks_per_bout_on_{side}_trials"] = (
            float(np.median(bout_sizes)) if bout_sizes else float("nan")
        )
        per_side[side] = {
            "n_bouts": len(bout_sizes),
            "n_trials": len(side_trials),
            "bout_sizes": bout_sizes,
        }

    return EndpointResult(
        per_session_aggregate=aggregate,
        per_trial_array=None,
        per_trial_type_split=per_side,
        provenance={
            "endpoint_name": "licks_per_bout_per_session",
            "config_snapshot": copy.deepcopy(endpoints_params),
            "n_trials_input": len(trials),
            "n_trials_used": len(trials),
        },
    )
