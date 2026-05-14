"""Per-trial record construction from Phase 2 lick + tone + reward outputs.

Phase 8a.3 originated this module reward-anchored; Phase 8a.10.1 (Q-A.β
+ Q-B.α locked 2026-05-14) rewrites the anchor to tone-onset to reflect
the cohort-wide WS channel-label inversion fix at Commit A. Every trial
has a tone (the auditory cue) — that's the always-present anchor.
Reward delivery is optional (``reward_idx: int | None``); on withhold
trials it's ``None``.

Side field renamed ``reward_side → tone_side`` (Q-B.α). The side
identity is set at tone-onset and is well-defined even on no-reward
trials; the legacy ``reward_side`` name became misleading on withhold
trials where there is no reward.

Window math (criteria C3 / C4 windows, lick-counting windows) is
relative to ``tone_idx`` post-Q-A.β — i.e., relative to the auditory
cue, which is what every legacy "post-reward window" was actually
measuring under the pre-fix swap. Scientific intent is preserved
exactly.

The ``TrialRecord`` dataclass defined here is consumed by Phase 8a
endpoint primitives under
:mod:`stroke_orofacial.spout_behavior.endpoints_per_trial`,
:mod:`stroke_orofacial.spout_behavior.endpoints_within_session`, and
the Phase 8a.10 visual-gate renderers
(:mod:`stroke_orofacial.spout_behavior.visual_gate`,
:mod:`stroke_orofacial.spout_behavior.spout_close_vs_std`).

Pure function — no pandas, no I/O. Matches the numpy/dict house style
of :mod:`stroke_orofacial.spout_behavior.bouts` and
:mod:`stroke_orofacial.spout_behavior.lick_detection`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

# Defensive ε-window for tone→reward pairing inside
# :func:`build_per_trial_records`. Per the prior diagnostic
# (.scratch_phase_8a_10/reward_tone_swap_extended_diagnostic.md §C) tone
# and reward TTLs fire synchronously — all sample-delta values across
# the cohort verified at 0. The 50 ms window is defensive against
# hypothetical future acquisition jitter; in the current cohort every
# pairing hits at delta = 0 samples.
_TONE_REWARD_PAIRING_WINDOW_MS = 50.0


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """A single per-trial record.

    Phase 8a.10.1 Q-A.β two-anchor model (locked 2026-05-14): ``tone_idx``
    is the always-present trial anchor (the auditory cue onset);
    ``reward_idx`` is the optional actual reward-delivery sample, or
    ``None`` when reward was withheld on this trial.

    Attributes
    ----------
    trial_idx : int
        0-based ordinal position within the session, sorted chronologically
        across both sides by ``tone_idx``.
    tone_side : {"L", "R"}
        Spout-side identity of the trial, set at tone-onset. Q-B.α
        renamed from ``reward_side`` (2026-05-14) — the side is
        well-defined even on no-reward trials, so the new name avoids
        the on-withhold-trial misnomer.
    tone_idx : int
        Wavesurfer sample index of tone-onset (the trial's anchor).
        Always present.
    reward_idx : int or None
        Wavesurfer sample index of paired reward-delivery, or ``None``
        when reward was withheld on this trial. Pairing is
        nearest-after-tone within :data:`_TONE_REWARD_PAIRING_WINDOW_MS`
        on the same side (one-to-one greedy match).
    trial_type : {"rewarded", "unrewarded"}
        Derived: ``"rewarded"`` iff ``reward_idx is not None``.
    licks_L_indices_in_window : np.ndarray
        Sample indices of left-spout licks falling in the trial-scoring
        window ``[tone_idx + window_seconds[0]*Fs,
        tone_idx + window_seconds[1]*Fs)``. Half-open: left-inclusive,
        right-exclusive. Window is now tone-anchored (Q-A.β).
    licks_R_indices_in_window : np.ndarray
        Sample indices of right-spout licks in the same window.
    window_seconds : tuple[float, float]
        Scoring-window bounds in seconds, relative to ``tone_idx``.
    Fs : float
        Sampling rate in Hz.
    """

    trial_idx: int
    tone_side: Literal["L", "R"]
    tone_idx: int
    reward_idx: int | None
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
    """Construct one tone-anchored :class:`TrialRecord` per tone event.

    Q-A.β tone-anchored algorithm (2026-05-14): walk the concatenation
    of ``Tone_L`` and ``Tone_R`` in sample order (stable sort preserves
    acquisition ordering on simultaneous-index ties — which do not occur
    in practice within one side). For each tone event, slice ``Lick_L``
    and ``Lick_R`` to the half-open window
    ``[tone_idx + window_seconds[0]*Fs, tone_idx + window_seconds[1]*Fs)``.
    Pair each tone with the nearest unclaimed same-side reward event
    within :data:`_TONE_REWARD_PAIRING_WINDOW_MS` (one-to-one greedy);
    when no such reward exists, ``reward_idx`` is ``None`` and
    ``trial_type`` is ``"unrewarded"``.

    Parameters
    ----------
    licks_and_rewards : dict
        The Phase 2 ``find_licks_and_rewards`` output: ``Lick_L``,
        ``Lick_R``, ``Tone_L``, ``Tone_R``, ``Reward_L``, ``Reward_R``,
        ``Fs`` (post-Phase-8a.10.1 swap-fix the labels match content
        semantically — ``Tone_*`` holds tone-onset, ``Reward_*`` holds
        actual reward-delivery).
    window_seconds : tuple[float, float]
        Scoring-window bounds relative to each tone onset, in seconds.
        Typically driven by the widest of the ``criteria.C3`` /
        ``criteria.C4`` windows (legacy defaults 2.0 / 2.5 s
        post-tone — pre-fix labeled "post-reward" but the underlying
        anchor was tone-onset all along under Case-2 universal).

    Returns
    -------
    list[TrialRecord]
        One record per tone event, ordered by ``tone_idx``. Empty list
        when no tone events exist.
    """
    tone_L = np.asarray(licks_and_rewards["Tone_L"], dtype=int)
    tone_R = np.asarray(licks_and_rewards["Tone_R"], dtype=int)
    reward_L = np.asarray(licks_and_rewards["Reward_L"], dtype=int)
    reward_R = np.asarray(licks_and_rewards["Reward_R"], dtype=int)
    lick_L = np.asarray(licks_and_rewards["Lick_L"], dtype=int)
    lick_R = np.asarray(licks_and_rewards["Lick_R"], dtype=int)
    Fs = float(licks_and_rewards["Fs"])

    eps_samples = int(round(_TONE_REWARD_PAIRING_WINDOW_MS / 1000.0 * Fs))

    # Combine tone events with per-event side labels, then sort by sample idx.
    all_tones = np.concatenate([tone_L, tone_R])
    all_sides = np.array(
        ["L"] * tone_L.size + ["R"] * tone_R.size, dtype=object
    )
    if all_tones.size == 0:
        return []
    order = np.argsort(all_tones, kind="stable")
    sorted_tones = all_tones[order]
    sorted_sides = all_sides[order]

    window_start_samples = int(round(window_seconds[0] * Fs))
    window_end_samples = int(round(window_seconds[1] * Fs))

    # One-to-one greedy pairing trackers (per side).
    reward_by_side = {"L": reward_L, "R": reward_R}
    consumed_by_side = {
        "L": np.zeros(reward_L.size, dtype=bool),
        "R": np.zeros(reward_R.size, dtype=bool),
    }

    records: list[TrialRecord] = []
    for trial_idx, (tone_idx, side) in enumerate(zip(sorted_tones, sorted_sides)):
        # Pair this tone with the nearest unclaimed same-side reward
        # within eps_samples after tone-onset.
        rew_arr = reward_by_side[side]
        consumed = consumed_by_side[side]
        candidate_mask = (
            (rew_arr >= tone_idx)
            & (rew_arr <= tone_idx + eps_samples)
            & ~consumed
        )
        candidate_indices = np.where(candidate_mask)[0]
        if candidate_indices.size > 0:
            pair_idx = candidate_indices[0]
            consumed[pair_idx] = True
            paired_reward: int | None = int(rew_arr[pair_idx])
            trial_type: Literal["rewarded", "unrewarded"] = "rewarded"
        else:
            paired_reward = None
            trial_type = "unrewarded"

        # Window math relative to tone_idx (the Q-A.β anchor).
        start = int(tone_idx) + window_start_samples
        end = int(tone_idx) + window_end_samples
        licks_L_in_window = lick_L[(lick_L >= start) & (lick_L < end)]
        licks_R_in_window = lick_R[(lick_R >= start) & (lick_R < end)]
        records.append(
            TrialRecord(
                trial_idx=trial_idx,
                tone_side=side,
                tone_idx=int(tone_idx),
                reward_idx=paired_reward,
                trial_type=trial_type,
                licks_L_indices_in_window=licks_L_in_window,
                licks_R_indices_in_window=licks_R_in_window,
                window_seconds=tuple(float(w) for w in window_seconds),
                Fs=Fs,
            )
        )
    return records
