"""Lick-bout detector (Phase 8a.2).

Groups a sample-indexed lick event array into contiguous bouts separated by
inter-lick-interval (ILI) gaps exceeding ``max_ili_ms``. Pattern-ported from
``find_running_bouts`` in :mod:`stroke_orofacial.spout_behavior.bouts`,
but operating on an event-index array instead of a continuous signal —
the 3-step "threshold → fill gaps → drop short" conceptual structure maps
to "compute ILIs → split at gaps above threshold → drop runs below min-licks".

Phase 8a Q9 endpoint #3 (``lick_bout_structure``). Pure function: no I/O,
no config loading. Caller ``spout_behavior.session_processing`` (in a later
sub-phase) handles NPZ write-out; caller ``recovery_trajectories`` handles
plotting.

Gap-boundary semantics
----------------------
A gap is "within-bout" iff ``ili_samples <= max_ili_samples``; a gap strictly
greater splits the bout. Tested against the exact-threshold edge case in
:mod:`tests.test_lick_bouts`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class LickBout:
    """A single contiguous lick bout."""

    start_idx: int        # sample index of first lick in bout
    end_idx: int          # sample index of last lick in bout (inclusive)
    n_licks: int          # number of licks in bout (>= min_bout_licks)
    mean_ili_s: float     # mean inter-lick interval in seconds


def find_lick_bouts(
    lick_indices: np.ndarray,
    Fs: float,
    params: dict[str, Any],
) -> list[LickBout]:
    """Group sample-indexed lick events into bouts.

    Algorithm (3-step, mirrors ``find_running_bouts``):

      1. Convert ``max_ili_ms`` to samples via ``round(max_ili_ms * Fs / 1000)``.
      2. Split the lick sequence wherever consecutive ILI exceeds the gap
         threshold (strict ``>``; equality stays within the bout).
      3. Drop runs with fewer than ``min_bout_licks`` events.

    Parameters
    ----------
    lick_indices : np.ndarray
        Monotonically non-decreasing integer array of lick-event sample indices
        (as produced by :func:`stroke_orofacial.spout_behavior.lick_detection.find_licks_and_rewards`).
        Must be 1-D. Empty input is permitted.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``spout_behavior.endpoints_v2.lick_bouts`` block from defaults.yaml.
        Required keys:

        - ``max_ili_ms`` (float): Maximum inter-lick interval, in milliseconds,
          still considered within a single bout.
        - ``min_bout_licks`` (int): Minimum lick count to report as a bout.
          Runs below this are dropped.

    Returns
    -------
    list[LickBout]
        Bouts in the same chronological order as the input, each with
        populated ``start_idx``, ``end_idx``, ``n_licks``, ``mean_ili_s``.
        Mean ILI is computed as ``(end_idx - start_idx) / (n_licks - 1) / Fs``
        — the average gap length over the bout's ``n_licks - 1`` internal gaps.
    """
    lick_indices = np.asarray(lick_indices)
    if lick_indices.ndim != 1:
        raise ValueError(
            f"lick_indices must be 1-D, got shape {lick_indices.shape}"
        )

    max_ili_ms = float(params["max_ili_ms"])
    min_bout_licks = int(params["min_bout_licks"])
    max_ili_samples = int(round(max_ili_ms * Fs / 1000.0))

    # Short-circuit: not enough licks to form any bout at the configured minimum.
    if lick_indices.size < min_bout_licks:
        return []

    # Step 2: find split points — positions in ``lick_indices`` after which
    # the next ILI exceeds the threshold.
    ilis_samples = np.diff(lick_indices)
    split_after = np.where(ilis_samples > max_ili_samples)[0]

    # Bout extents: start at 0 or just after each split; end just before the
    # next split or at the array end.
    starts = np.concatenate(([0], split_after + 1))
    ends = np.concatenate((split_after + 1, [lick_indices.size]))

    bouts: list[LickBout] = []
    for s, e in zip(starts, ends):
        n = int(e - s)
        # Step 3: drop runs below the min-licks threshold.
        if n < min_bout_licks:
            continue
        start_idx = int(lick_indices[s])
        end_idx = int(lick_indices[e - 1])
        # Mean ILI: total span divided by number of intra-bout gaps. With
        # min_bout_licks >= 2 (the only sensible setting) n - 1 >= 1 so no
        # div-by-zero; we still guard for callers that set min_bout_licks=1.
        if n >= 2:
            mean_ili_s = (end_idx - start_idx) / (n - 1) / Fs
        else:
            mean_ili_s = float("nan")
        bouts.append(
            LickBout(
                start_idx=start_idx,
                end_idx=end_idx,
                n_licks=n,
                mean_ili_s=float(mean_ili_s),
            )
        )

    return bouts
