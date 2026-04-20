"""Per-trial record construction from Phase 2 lick + reward outputs (Phase 8a.3).

The ``TrialRecord`` dataclass defined here is the per-trial data unit consumed
by all Phase 8a endpoint primitives under
:mod:`stroke_orofacial.spout_behavior.endpoints_per_trial`,
:mod:`stroke_orofacial.spout_behavior.endpoints_within_session`, and later
sub-phases. Reward-anchored (matches legacy A10 semantics per archaeology §2);
tone-anchoring deferred to a later phase.

Phase 8a populates only the ``"rewarded"`` trial type. The ``trial_type``
field is present up-front so later phases that add unrewarded trials don't
need to retrofit the four downstream endpoint consumers.

Pure function — no pandas, no I/O. Matches the numpy/dict house style of
:mod:`stroke_orofacial.spout_behavior.bouts` and
:mod:`stroke_orofacial.spout_behavior.lick_detection`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """A single per-trial record.

    Attributes
    ----------
    trial_idx : int
        0-based ordinal position within the session.
    reward_side : {"L", "R"}
        Spout on which reward was delivered this trial.
    reward_idx : int
        Wavesurfer sample index of reward onset (the trial's anchor).
    tone_idx : int | None
        Sample index of paired tone, or None if not matched. Phase 8a emits
        None for all trials — tone-matching is deferred.
    trial_type : {"rewarded", "unrewarded"}
        Phase 8a populates ``"rewarded"`` only.
    licks_L_indices_in_window : np.ndarray
        Sample indices of left-spout licks falling in the trial-scoring
        window ``[reward_idx + window_seconds[0]*Fs, reward_idx + window_seconds[1]*Fs)``.
        Half-open: left-inclusive, right-exclusive.
    licks_R_indices_in_window : np.ndarray
        Sample indices of right-spout licks in the same window.
    window_seconds : tuple[float, float]
        Scoring-window bounds in seconds, relative to ``reward_idx``.
    Fs : float
        Sampling rate in Hz.
    """

    trial_idx: int
    reward_side: Literal["L", "R"]
    reward_idx: int
    tone_idx: int | None
    trial_type: Literal["rewarded", "unrewarded"]
    licks_L_indices_in_window: np.ndarray
    licks_R_indices_in_window: np.ndarray
    window_seconds: tuple[float, float]
    Fs: float


def build_per_trial_records(
    licks_and_rewards: dict[str, np.ndarray],
    *,
    window_seconds: tuple[float, float],
) -> list[TrialRecord]:
    """Construct one reward-anchored ``TrialRecord`` per reward event.

    Walks the concatenation of ``Reward_L`` and ``Reward_R`` in sample order
    (stable sort preserves acquisition ordering when a simultaneous-index
    collision occurs, though that does not happen in practice). For each
    reward event, slices ``Lick_L`` and ``Lick_R`` to the half-open window
    ``[reward_idx + window_seconds[0]*Fs, reward_idx + window_seconds[1]*Fs)``.

    Parameters
    ----------
    licks_and_rewards : dict
        The Phase 2 ``find_licks_and_rewards`` output: ``Lick_L``, ``Lick_R``,
        ``Reward_L``, ``Reward_R``, ``Fs`` (keys sufficient for this builder;
        ``Tone_L/R`` and ``n_samples`` are ignored here).
    window_seconds : tuple[float, float]
        Scoring-window bounds relative to each reward onset, in seconds.
        Typically driven by the widest of the ``criteria.C3`` / ``criteria.C4``
        windows (legacy defaults 2.0 / 2.5 s post-reward).

    Returns
    -------
    list[TrialRecord]
        One record per reward event, ordered by ``reward_idx``. Empty list
        when no reward events exist.
    """
    reward_L = np.asarray(licks_and_rewards["Reward_L"], dtype=int)
    reward_R = np.asarray(licks_and_rewards["Reward_R"], dtype=int)
    lick_L = np.asarray(licks_and_rewards["Lick_L"], dtype=int)
    lick_R = np.asarray(licks_and_rewards["Lick_R"], dtype=int)
    Fs = float(licks_and_rewards["Fs"])

    # Combine reward events with per-event side labels, then sort by sample idx.
    all_rewards = np.concatenate([reward_L, reward_R])
    all_sides = np.array(
        ["L"] * reward_L.size + ["R"] * reward_R.size, dtype=object
    )
    if all_rewards.size == 0:
        return []
    order = np.argsort(all_rewards, kind="stable")
    sorted_rewards = all_rewards[order]
    sorted_sides = all_sides[order]

    window_start_samples = int(round(window_seconds[0] * Fs))
    window_end_samples = int(round(window_seconds[1] * Fs))

    records: list[TrialRecord] = []
    for trial_idx, (reward_idx, side) in enumerate(zip(sorted_rewards, sorted_sides)):
        start = int(reward_idx) + window_start_samples
        end = int(reward_idx) + window_end_samples
        licks_L_in_window = lick_L[(lick_L >= start) & (lick_L < end)]
        licks_R_in_window = lick_R[(lick_R >= start) & (lick_R < end)]
        records.append(
            TrialRecord(
                trial_idx=trial_idx,
                reward_side=side,
                reward_idx=int(reward_idx),
                tone_idx=None,
                trial_type="rewarded",
                licks_L_indices_in_window=licks_L_in_window,
                licks_R_indices_in_window=licks_R_in_window,
                window_seconds=tuple(float(w) for w in window_seconds),
                Fs=Fs,
            )
        )
    return records
