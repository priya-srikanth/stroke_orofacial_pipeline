"""Bout detection: running, grooming, quiet, and peri-reward periods.

Ported from legacy modules (all only-version, Rule 1 trivially resolved):
  - find_running_bouts.py
  - find_grooming_bouts.py
  - find_quiet_bouts.py
  - find_peri_reward_periods.py
"""

from __future__ import annotations

from typing import Any

import numpy as np

from stroke_orofacial._utils.bool_indexing import (
    idx2bool,
    set_short_bool_to_low,
    widen_bool_sparse,
)


# ---------------------------------------------------------------------------
# Running bouts
# ---------------------------------------------------------------------------


def find_running_bouts(
    treadmill_smoothed: np.ndarray,
    Fs: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Identify running bouts in a smoothed treadmill speed signal.

    Algorithm (3-step):
      1. Threshold: ``speed > thresh_speed``
      2. Fill brief gaps shorter than ``max_gap_duration``
      3. Drop bouts shorter than ``min_duration``

    Parameters
    ----------
    treadmill_smoothed : np.ndarray
        Smoothed treadmill speed in mm/s.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``find_running_bouts`` section from defaults.yaml.
        Required keys: ``thresh_speed``, ``max_gap_duration``, ``min_duration``.

    Returns
    -------
    np.ndarray
        Boolean mask (True = running), same length as input.
    """
    bout_mask = treadmill_smoothed > params["thresh_speed"]

    # Fill brief gaps (invert, remove short True runs, re-invert)
    gap_n = int(Fs * params["max_gap_duration"])
    bout_mask = ~set_short_bool_to_low(~bout_mask, n=gap_n)

    # Drop short bouts
    run_n = int(Fs * params["min_duration"])
    bout_mask = set_short_bool_to_low(bout_mask, n=run_n)

    return bout_mask


# ---------------------------------------------------------------------------
# Grooming bouts
# ---------------------------------------------------------------------------


def find_grooming_bouts(
    lick_indices: dict[str, np.ndarray],
    n_samples: int,
    Fs: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Detect grooming periods via bilateral conjunction + long-touch violations.

    Algorithm (6-step):
      1. Convert lick indices to boolean arrays
      2. Widen each channel for conjunction detection (±conj_before/after)
      3. AND the widened channels → bilateral conjunction mask
      4. Detect long-touch violations (True runs > max_long)
      5. Combine: bad = conjunction OR any long violation
      6. Widen bad regions, then remove short good gaps

    Parameters
    ----------
    lick_indices : dict
        ``{"Lick_L": indices, "Lick_R": indices}`` — integer index arrays.
    n_samples : int
        Total number of samples in the session.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``find_grooming_bouts`` section from defaults.yaml.
        Required keys: ``duration_widen_conj_before``, ``duration_widen_conj_after``,
        ``duration_maxThresh_long``, ``duration_widen_bad_before``,
        ``duration_widen_bad_after``, ``duration_minThresh_good``.

    Returns
    -------
    np.ndarray
        Boolean mask (True = grooming/bad lick period).
    """
    # Convert duration params (seconds) to samples
    conj_before = int(params["duration_widen_conj_before"] * Fs)
    conj_after = int(params["duration_widen_conj_after"] * Fs)
    max_long = int(params["duration_maxThresh_long"] * Fs)
    bad_before = int(params["duration_widen_bad_before"] * Fs)
    bad_after = int(params["duration_widen_bad_after"] * Fs)
    min_good = int(params["duration_minThresh_good"] * Fs)

    # 1) Convert indices to boolean
    lick_bool = {
        s: idx2bool(idx=lick_indices[s], length=n_samples)
        for s in ("Lick_L", "Lick_R")
    }

    # 2) Widen for conjunction violations
    wide = {
        s: widen_bool_sparse(
            b=lick_bool[s], n_before=conj_before, n_after=conj_after
        )
        for s in ("Lick_L", "Lick_R")
    }

    # 3) Bilateral conjunction
    wide_conj = wide["Lick_L"] & wide["Lick_R"]

    # 4) Long-touch violations
    long_viol = {
        s: set_short_bool_to_low(b=lick_bool[s], n=max_long)
        for s in ("Lick_L", "Lick_R")
    }

    # 5) Combine
    bad = wide_conj | long_viol["Lick_L"] | long_viol["Lick_R"]

    # 6) Widen bad regions, then remove short good gaps
    bad = widen_bool_sparse(b=bad, n_before=bad_before, n_after=bad_after)
    bad = ~set_short_bool_to_low(b=~bad, n=min_good)

    return bad


# ---------------------------------------------------------------------------
# Quiet bouts
# ---------------------------------------------------------------------------


def find_quiet_bouts(
    treadmill_smoothed: np.ndarray,
    grooming_bool: np.ndarray,
    lick_indices: dict[str, np.ndarray],
    reward_indices: dict[str, np.ndarray],
    n_samples: int,
    Fs: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Detect quiet periods by excluding all behavioral markers.

    Quiet = slow treadmill AND NOT near any grooming, licking, or reward
    event. Each exclusion uses a configurable time buffer. Short quiet
    periods are dropped.

    Parameters
    ----------
    treadmill_smoothed : np.ndarray
        Smoothed treadmill speed in mm/s.
    grooming_bool : np.ndarray
        Boolean mask from grooming detection (True = grooming).
    lick_indices : dict
        ``{"Lick_L": indices, "Lick_R": indices}``.
    reward_indices : dict
        ``{"Reward_L": indices, "Reward_R": indices}``.
    n_samples : int
        Total number of samples in the session.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``find_quiet_bouts`` section from defaults.yaml.
        Required keys: ``speed_threshold``, ``min_quiet_duration``,
        ``treadmillSlow_time_buffer``, ``lick_time_buffer``,
        ``reward_time_buffer``, ``groom_time_buffer``.

    Returns
    -------
    np.ndarray
        Boolean mask (True = quiet period).
    """

    def widen(b: np.ndarray, before_s: float, after_s: float) -> np.ndarray:
        return widen_bool_sparse(
            b=b, n_before=int(before_s * Fs), n_after=int(after_s * Fs)
        )

    # Convert lick/reward indices to boolean
    lick_bool = {
        side: idx2bool(idx=lick_indices[f"Lick_{side}"], length=n_samples)
        for side in ("L", "R")
    }
    reward_bool = {
        side: idx2bool(idx=reward_indices[f"Reward_{side}"], length=n_samples)
        for side in ("L", "R")
    }

    # Base quiet: slow treadmill, buffered
    quiet_speed = treadmill_smoothed < params["speed_threshold"]

    # AND of all exclusion constraints
    quiet = (
        ~widen(~quiet_speed, *params["treadmillSlow_time_buffer"])
        & ~widen(grooming_bool, *params["groom_time_buffer"])
        & ~widen(lick_bool["L"], *params["lick_time_buffer"])
        & ~widen(lick_bool["R"], *params["lick_time_buffer"])
        & ~widen(reward_bool["L"], *params["reward_time_buffer"])
        & ~widen(reward_bool["R"], *params["reward_time_buffer"])
    )

    # Remove short quiet periods
    quiet = set_short_bool_to_low(
        quiet, n=int(params["min_quiet_duration"] * Fs)
    )

    return quiet


# ---------------------------------------------------------------------------
# Peri-reward periods
# ---------------------------------------------------------------------------


def _find_idx_within_eps(
    arr: np.ndarray,
    vals: np.ndarray,
    eps: tuple[int, int],
) -> np.ndarray:
    """Return indices in *arr* within a window around each value in *vals*.

    For each ``v`` in *vals*, finds indices ``i`` in *arr* such that
    ``v - eps[0] <= arr[i] < v + eps[1]``.

    Faithfully ports the legacy ``find_idx_within_eps`` function.
    """
    eps_l, eps_r = eps
    out: list[np.ndarray] = []
    for v in vals:
        il = np.searchsorted(arr, v - eps_l, side="right")
        ir = np.searchsorted(arr, v + eps_r, side="left")
        il = min(max(0, il), len(arr) - 1)
        ir = min(max(0, ir), len(arr) - 1)
        out.append(np.arange(il, ir))
    return np.concatenate(out) if out else np.array([], dtype=int)


def find_peri_reward_periods(
    reward_indices: dict[str, np.ndarray],
    n_samples: int,
    Fs: float,
    params: dict[str, Any],
) -> np.ndarray:
    """Mark samples within a temporal window around each reward event.

    Consolidates Reward_L and Reward_R, then marks all samples within
    ``[reward - window[0]*Fs, reward + window[1]*Fs)``.

    Parameters
    ----------
    reward_indices : dict
        ``{"Reward_L": indices, "Reward_R": indices}``.
    n_samples : int
        Total number of samples in the session.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``find_peri_reward_periods`` section from defaults.yaml.
        Required key: ``window_around_reward`` as ``[before_sec, after_sec]``.

    Returns
    -------
    np.ndarray
        Boolean mask (True = within peri-reward window).
    """
    # Consolidate L + R reward indices
    reward_idx = np.sort(
        np.concatenate([
            reward_indices.get("Reward_L", np.array([], dtype=int)),
            reward_indices.get("Reward_R", np.array([], dtype=int)),
        ])
    )

    window_sec = params["window_around_reward"]
    eps_samples = (int(window_sec[0] * Fs), int(window_sec[1] * Fs))

    # Build boolean mask
    full_idx = np.arange(n_samples)
    idx_mask = _find_idx_within_eps(full_idx, reward_idx, eps_samples)

    peri_reward_bool = np.zeros(n_samples, dtype=bool)
    peri_reward_bool[idx_mask] = True

    return peri_reward_bool


# ---------------------------------------------------------------------------
# Per-side peri-reward + peri-tone periods
# ---------------------------------------------------------------------------


def _make_peri_event_bool(
    event_indices: np.ndarray,
    n_samples: int,
    eps_samples: tuple[int, int],
) -> np.ndarray:
    """Build a boolean mask marking samples within a window around events."""
    full_idx = np.arange(n_samples)
    idx_mask = _find_idx_within_eps(full_idx, event_indices, eps_samples)
    mask = np.zeros(n_samples, dtype=bool)
    mask[idx_mask] = True
    return mask


def find_peri_reward_and_tone_periods(
    reward_indices: dict[str, np.ndarray],
    tone_indices: dict[str, np.ndarray],
    n_samples: int,
    Fs: float,
    params: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Mark samples within a temporal window around each per-side event.

    Produces 4 boolean masks — one per event channel — using the same window.
    Ported from upstream ``find_peri_reward_and_tone_periods.py``.

    Parameters
    ----------
    reward_indices : dict
        ``{"Reward_L": indices, "Reward_R": indices}``.
    tone_indices : dict
        ``{"Tone_L": indices, "Tone_R": indices}``.
    n_samples : int
        Total number of samples in the session.
    Fs : float
        Sampling rate in Hz.
    params : dict
        The ``find_peri_reward_and_tone_periods`` section from defaults.yaml.
        Required key: ``window_around_reward`` as ``[before_sec, after_sec]``.

    Returns
    -------
    dict[str, np.ndarray]
        ``{"peri_reward_L": bool, "peri_reward_R": bool,
          "peri_tone_L": bool, "peri_tone_R": bool}``
    """
    window_sec = params["window_around_reward"]
    eps_samples = (int(window_sec[0] * Fs), int(window_sec[1] * Fs))

    return {
        "peri_reward_L": _make_peri_event_bool(
            reward_indices.get("Reward_L", np.array([], dtype=int)), n_samples, eps_samples
        ),
        "peri_reward_R": _make_peri_event_bool(
            reward_indices.get("Reward_R", np.array([], dtype=int)), n_samples, eps_samples
        ),
        "peri_tone_L": _make_peri_event_bool(
            tone_indices.get("Tone_L", np.array([], dtype=int)), n_samples, eps_samples
        ),
        "peri_tone_R": _make_peri_event_bool(
            tone_indices.get("Tone_R", np.array([], dtype=int)), n_samples, eps_samples
        ),
    }
