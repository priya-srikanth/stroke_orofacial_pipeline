"""Lick, reward, and tone detection from wavesurfer signals.

Ported from legacy module ``find_licks_and_rewards.py``:
  - Phase 2: from Priya's fork (lick + reward only).
  - Phase 2.5: extended with tone detection from Rich's upstream
    ``find_licks_and_rewards.py`` (Rule 1 trivially resolved, only version).

Lick detection uses a double-threshold algorithm:
  - **Upward lick onset**: signal falls below ``thresh_upper`` (spout contact
    pulls voltage down).
  - **Downward lick offset**: signal rises above ``thresh_lower``.
  - **Lockout cleaning**: upward events within an asymmetric window around
    each downward event are removed (debounce).

Reward and tone detection find rising edges on digital channels
(Reward_L/R, Tone_L/R) using the same threshold.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def find_reward_indices(
    signals: dict[str, np.ndarray],
    thresh: float = 0.5,
) -> dict[str, np.ndarray]:
    """Detect reward onsets as rising edges on digital reward channels.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Wavesurfer signals dict containing ``Reward_L`` and ``Reward_R``.
    thresh : float
        Threshold for rising-edge detection on ``np.diff``.

    Returns
    -------
    dict[str, np.ndarray]
        ``{"Reward_L": indices, "Reward_R": indices}`` — integer arrays
        of sample indices where rewards were detected.
    """
    def _detect(arr: np.ndarray) -> np.ndarray:
        return np.where(np.diff(arr, prepend=0) > thresh)[0]

    return {f"Reward_{side}": _detect(signals[f"Reward_{side}"]) for side in ("L", "R")}


def find_tone_indices(
    signals: dict[str, np.ndarray],
    thresh: float = 0.5,
) -> dict[str, np.ndarray]:
    """Detect tone onsets as rising edges on digital tone channels.

    Same algorithm as reward detection, applied to ``Tone_L`` and ``Tone_R``.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Wavesurfer signals dict containing ``Tone_L`` and ``Tone_R``.
    thresh : float
        Threshold for rising-edge detection on ``np.diff``.

    Returns
    -------
    dict[str, np.ndarray]
        ``{"Tone_L": indices, "Tone_R": indices}`` — integer arrays
        of sample indices where tones were detected.
    """
    def _detect(arr: np.ndarray) -> np.ndarray:
        return np.where(np.diff(arr, prepend=0) > thresh)[0]

    return {f"Tone_{side}": _detect(signals[f"Tone_{side}"]) for side in ("L", "R")}


def _find_upward_lick_indices(
    signals: dict[str, np.ndarray],
    thresh_upper: float,
) -> dict[str, np.ndarray]:
    """Detect upward lick events (signal falling below upper threshold).

    Lick onset = spout contact pulls the analog voltage below thresh_upper.
    """
    def _detect(arr: np.ndarray) -> np.ndarray:
        return np.where(
            np.diff(arr < thresh_upper, prepend=0).astype(np.float32) > 0.5
        )[0]

    return {f"Lick_{side}": _detect(signals[f"Lick_{side}"]) for side in ("L", "R")}


def _find_downward_lick_indices(
    signals: dict[str, np.ndarray],
    thresh_lower: float,
) -> dict[str, np.ndarray]:
    """Detect downward lick events (signal rising above lower threshold).

    Lick offset = spout release lets voltage rise above thresh_lower.
    """
    def _detect(arr: np.ndarray) -> np.ndarray:
        return np.where(
            np.diff(arr > thresh_lower, prepend=0).astype(np.float32) > 0.5
        )[0]

    return {f"Lick_{side}": _detect(signals[f"Lick_{side}"]) for side in ("L", "R")}


def _clean_lick_indices(
    up_idx: dict[str, np.ndarray],
    down_idx: dict[str, np.ndarray],
    lockout_samples: tuple[int, int],
) -> dict[str, np.ndarray]:
    """Remove upward lick events within a lockout window around downward events.

    Parameters
    ----------
    up_idx : dict
        Upward (onset) lick indices per side.
    down_idx : dict
        Downward (offset) lick indices per side.
    lockout_samples : tuple[int, int]
        (left, right) lockout window in samples. For each downward event at
        index ``v``, any upward event in ``[v + left, v + right)`` is removed.
        Legacy values: left = int(0.001 * Fs), right = int(0.02 * Fs).

    Returns
    -------
    dict[str, np.ndarray]
        Cleaned upward lick indices per side.
    """
    def _indices_within(
        arr: np.ndarray, vals: np.ndarray, window: tuple[int, int]
    ) -> np.ndarray:
        left, right = window
        out: list[np.ndarray] = []
        for v in vals:
            il = np.searchsorted(arr, v + left, side="right")
            ir = np.searchsorted(arr, v + right, side="left")
            il = np.clip(il, 0, len(arr) - 1)
            ir = np.clip(ir, 0, len(arr) - 1)
            out.append(np.arange(il, ir))
        return np.concatenate(out) if out else np.array([], dtype=int)

    cleaned = {}
    for side in ("L", "R"):
        key = f"Lick_{side}"
        remove = _indices_within(up_idx[key], down_idx[key], lockout_samples)
        cleaned[key] = np.delete(up_idx[key], remove)
    return cleaned


def find_licks_and_rewards(
    signals: dict[str, np.ndarray],
    params: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Detect lick and reward events from wavesurfer signals.

    This is the main entry point, combining reward detection, double-threshold
    lick detection, and lockout cleaning into a single call.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Wavesurfer signals dict containing at minimum ``Lick_L``, ``Lick_R``,
        ``Reward_L``, ``Reward_R``, ``Tone_L``, ``Tone_R``, and
        ``sample_rate_input``.
    params : dict
        The ``find_licks_and_rewards`` section from defaults.yaml. Expected
        keys: ``lick_detection.thresh_upper``, ``lick_detection.thresh_lower``,
        ``lick_detection.duration_lockout_falling_edge``,
        ``reward_detection.thresh``.

    Returns
    -------
    dict[str, np.ndarray]
        Keys: ``Lick_L``, ``Lick_R`` (cleaned onset indices),
        ``Reward_L``, ``Reward_R``, ``Tone_L``, ``Tone_R`` (onset indices),
        ``Fs`` (float), ``n_samples`` (int).
    """
    Fs = float(signals.get("Fs", signals.get("sample_rate_input")))

    # Reward + tone detection (same threshold, same algorithm)
    reward_thresh = params["reward_detection"]["thresh"]
    rewards = find_reward_indices(signals, reward_thresh)
    tones = find_tone_indices(signals, reward_thresh)

    # Lick detection: double-threshold + lockout
    lick_params = params["lick_detection"]
    up = _find_upward_lick_indices(signals, lick_params["thresh_upper"])
    down = _find_downward_lick_indices(signals, lick_params["thresh_lower"])

    lockout_sec = lick_params["duration_lockout_falling_edge"]
    lockout_samples = (int(lockout_sec[0] * Fs), int(lockout_sec[1] * Fs))
    licks = _clean_lick_indices(up, down, lockout_samples)

    # Determine n_samples from the first signal array
    n_samples = None
    for key in ("Lick_L", "Lick_R", "Treadmill"):
        if key in signals:
            n_samples = signals[key].shape[0]
            break
    if n_samples is None:
        n_samples = next(
            v.shape[0] for v in signals.values() if isinstance(v, np.ndarray) and v.ndim == 1
        )

    return {
        "Lick_L": licks["Lick_L"],
        "Lick_R": licks["Lick_R"],
        "Reward_L": rewards["Reward_L"],
        "Reward_R": rewards["Reward_R"],
        "Tone_L": tones["Tone_L"],
        "Tone_R": tones["Tone_R"],
        "Fs": Fs,
        "n_samples": n_samples,
    }
