"""Phase 7a.3 V3 — Cell 50 angle math + per-trial sampling + inclusion (private).

Companion to :mod:`stroke_orofacial.dlc_kinematics._detector`. Exposes:

- The signed-angle math (atan2 with sign-flip baked inside) and NaN-aware
  gaussian smoothing (``_gaussian_smooth_nan``).
- Per-trial scalar sampling of the session-wide smoothed angle at Cell 33
  lick1/lick2 timestamps and Cell 36 first-5 velocity-peak timestamps.
- ``_extract_angle_max_signed_per_lick``: signed-max of angle inside
  ``± peak_pad_ms`` of each lick t (NEW V3 feature defn).
- ``_extract_cell50_own_bout_scalars``: ``n_peaks``, ``n_bouts``,
  ``n_multi_lick_bouts``, ``first_peak_t_ms`` constrained to the apply
  window (Cell 50's own bout scalars).
- ``_evaluate_session_inclusion``: 4-boolean session-level gate.

This module is private; downstream callers go through
:mod:`stroke_orofacial.dlc_kinematics.tongue_pertrial`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d

from stroke_orofacial.dlc_kinematics._detector import (
    _build_bouts,
    _slope_detect_lick_peaks,
)


def _compute_signed_tongue_angle_deg(
    x_geom: np.ndarray, y_geom: np.ndarray,
    eye_x_in_spout_frame: float, eye_y_in_spout_frame: float,
    *, sign_flip: float,
) -> np.ndarray:
    """Per-frame signed angle (degrees) in spout-centered frame.

    Reference vector (eye → spout-origin): ``ref = (-eye_x, -eye_y)``.
    Tongue vector (eye → tongue): ``v = (x_geom - eye_x, y_geom - eye_y)``.
    Signed angle: ``sign_flip * degrees(atan2(cross(ref, v), dot(ref, v)))``.

    The sign-flip is applied INSIDE the atan2 expression — legacy
    convention; do not move it outside (that would invert sign for half
    the trace under symmetric tongue positions). Smoothing is applied
    SEPARATELY by :func:`_extract_per_frame_angle_smoothed` and is NOT
    part of this function's contract.
    """
    eye_x = float(eye_x_in_spout_frame)
    eye_y = float(eye_y_in_spout_frame)
    ref_x = -eye_x
    ref_y = -eye_y
    vx = x_geom.astype(np.float64) - eye_x
    vy = y_geom.astype(np.float64) - eye_y
    dot = ref_x * vx + ref_y * vy
    cross = ref_x * vy - ref_y * vx
    return float(sign_flip) * np.degrees(np.arctan2(cross, dot))


def _gaussian_smooth_nan(
    arr: np.ndarray, sigma_units: float, *, mode: str = "nearest",
) -> np.ndarray:
    """NaN-aware gaussian smoothing.

    Computes ``num/den`` of the smoothed signal divided by the smoothed
    finite-mask, with :func:`scipy.ndimage.gaussian_filter1d` in
    ``mode="nearest"``. Bins with effectively-zero mask weight (no finite
    samples within several sigma) are returned as NaN to avoid dividing
    by ~0.

    ``sigma_units`` is in array-index units (caller converts ms→bins or
    ms→frames as needed).
    """
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0:
        return arr
    finite = np.isfinite(arr).astype(np.float64)
    safe = np.where(np.isfinite(arr), arr, 0.0)
    if sigma_units <= 0:
        return np.where(finite > 0, safe, np.nan)
    num = gaussian_filter1d(safe, sigma_units, mode=mode)
    den = gaussian_filter1d(finite, sigma_units, mode=mode)
    out = np.full_like(arr, np.nan)
    nz = den > 1e-8
    out[nz] = num[nz] / den[nz]
    return out


def _extract_per_frame_angle_smoothed(
    x_final: np.ndarray, y_final: np.ndarray,
    eye_x_in_spout_frame: float, eye_y_in_spout_frame: float,
    fps: float, *, params: dict[str, Any],
) -> np.ndarray:
    """Per-frame smoothed signed angle (degrees), session length.

    Order of operations: ``atan2(cross, dot)`` with sign-flip baked INSIDE,
    THEN gaussian smoothing at σ = ``smoothing_gaussian_sigma_ms``
    (V3 = 8 ms).
    """
    angle_params = params["dlc_kinematics"]["tongue_pertrial"]["angle"]
    sign_flip = float(angle_params["sign_flip"])
    sigma_ms = float(angle_params["smoothing_gaussian_sigma_ms"])
    angle_raw = _compute_signed_tongue_angle_deg(
        x_final, y_final, eye_x_in_spout_frame, eye_y_in_spout_frame,
        sign_flip=sign_flip,
    )
    sigma_frames = sigma_ms / 1000.0 * fps
    return _gaussian_smooth_nan(angle_raw, sigma_frames, mode="nearest")


def _extract_angle_at_lick_timestamps(
    angle_per_frame_session: np.ndarray, fps: float,
    reward_frame_idx: int, lick_t_ms: float,
) -> float:
    """Sample the session-wide per-frame angle at one timestamp (ms post-reward).

    Uses linear interpolation via :func:`np.interp`. Returns NaN if the
    timestamp falls outside the session frame range.
    """
    if not np.isfinite(lick_t_ms):
        return float("nan")
    target_frame = reward_frame_idx + lick_t_ms / 1000.0 * fps
    n = len(angle_per_frame_session)
    if target_frame < 0 or target_frame > n - 1:
        return float("nan")
    frame_idx = np.arange(n, dtype=np.float64)
    return float(np.interp(target_frame, frame_idx, angle_per_frame_session))


def _extract_angle_max_signed_per_lick(
    angle_per_frame_session: np.ndarray, fps: float, reward_frame_idx: int,
    lick_t_peaks_ms: np.ndarray, peak_pad_ms: float,
) -> np.ndarray:
    """Per-lick signed-max of angle inside ``± peak_pad_ms`` of each lick t.

    Output shape ``(5,)`` NaN-padded. ``signed-max`` = the value with the
    largest absolute magnitude inside the window (preserves sign).
    """
    n_lick = len(lick_t_peaks_ms)
    out = np.full(n_lick, np.nan, dtype=np.float64)
    n_frames = len(angle_per_frame_session)
    pad_frames = int(round(peak_pad_ms / 1000.0 * fps))
    for j, t_ms in enumerate(lick_t_peaks_ms):
        if not np.isfinite(t_ms):
            continue
        center = reward_frame_idx + int(round(t_ms / 1000.0 * fps))
        lo = max(0, center - pad_frames)
        hi = min(n_frames, center + pad_frames + 1)
        win = angle_per_frame_session[lo:hi]
        finite = np.isfinite(win)
        if not np.any(finite):
            continue
        idx = int(np.nanargmax(np.abs(win)))
        out[j] = float(win[idx])
    return out


def _extract_cell50_own_bout_scalars(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, params: dict[str, Any],
) -> dict[str, float | int]:
    """Cell 50 own per-trial bout scalars (constrained to apply window).

    Returns ``n_peaks``, ``n_bouts``, ``n_multi_lick_bouts``,
    ``first_peak_t_ms``, ``n_licks_in_first_multi_bout`` for the apply
    window ``angle_apply_win_ms`` (V3: ``[70, 5000]``).

    ``n_licks_in_first_multi_bout`` (Q9 NEW 2026-04-28): peak count inside
    the first multi-lick bout (0 if no multi-lick bout). Feeds the
    session-inclusion ``n_phase_licks`` aggregation
    (``sum(n_licks_in_first_multi_bout)`` across trials).
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detect_win = tuple(tp["angle_detect_win_ms"])
    apply_win = tuple(tp["angle_apply_win_ms"])
    # Per-cell knob overrides (C5.2 2026-04-28). The shared detector + bout
    # blocks are the V3 default; cell50 may carry parity-specific overrides
    # via the harness in legacy_approximate mode.
    from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
        _per_cell_bout,
        _per_cell_detector,
    )
    detector = _per_cell_detector(params, "cell50")
    bout = _per_cell_bout(params, "cell50")
    peaks = _slope_detect_lick_peaks(
        y_t, x_t, t_ms, fps,
        detect_win_ms=detect_win, detector_params=detector,
    )
    in_apply = (
        (peaks.peak_times_ms >= apply_win[0])
        & (peaks.peak_times_ms <= apply_win[1])
    )
    apply_t = peaks.peak_times_ms[in_apply]
    n_peaks = int(len(apply_t))
    bouts = _build_bouts(apply_t, float(bout["max_ili_ms"]))
    n_bouts = len(bouts)
    multi_bouts = [b for b in bouts if len(b) >= 2]
    n_multi = len(multi_bouts)
    first_t = float(apply_t.min()) if n_peaks > 0 else float("nan")
    n_licks_first_multi = int(len(multi_bouts[0])) if multi_bouts else 0
    return {
        "n_peaks": n_peaks,
        "n_bouts": n_bouts,
        "n_multi_lick_bouts": n_multi,
        "first_peak_t_ms": first_t,
        "n_licks_in_first_multi_bout": n_licks_first_multi,
    }


def _evaluate_session_inclusion(
    n_time_trials: int,
    n_first_peak_trials: int,
    n_phase_licks: int,
    n_phase_trials: int,
    *, params: dict[str, Any],
) -> dict[str, Any]:
    """Cell 50 session-level inclusion (4 booleans + threshold echo).

    Replaces V1/V2's per-trial ``tongue_angle_pass`` mask. Thresholds come
    from ``configs/defaults.yaml dlc_kinematics.tongue_pertrial.session_inclusion``.

    Counts (caller-provided, per Q9 lock 2026-04-28):

    - ``n_time_trials`` — # trials with a finite ``cell50.first_peak_t_ms``
      (Cell 50 own scalars). Gates ``time_aligned``.
    - ``n_first_peak_trials`` — # trials with finite ``lick1_t_peak_ms``
      (Cell 33). Gates ``first_peak_aligned``.
    - ``n_phase_licks`` — sum of ``n_licks_in_first_multi_bout`` across
      trials (Cell 42 reduction; Q9 binding 2026-04-28). Gates
      ``phase_summary_by_lick_count``.
    - ``n_phase_trials`` — # trials with ``n_licks_in_first_multi_bout >= 2``
      (i.e. trials that contributed at least one ILI to the phase summary).
      Gates ``phase_summary_by_trial_count``.
    """
    si = params["dlc_kinematics"]["tongue_pertrial"]["session_inclusion"]
    min_time = int(si["min_time_trials_per_session"])
    min_firstpeak = int(si["min_firstpeak_trials_per_session"])
    min_phase_licks = int(si["min_phase_licks_per_session"])
    min_phase_trials = int(si["min_phase_trials_per_session"])
    return {
        "time_aligned": bool(n_time_trials > min_time),
        "first_peak_aligned": bool(n_first_peak_trials >= min_firstpeak),
        "phase_summary_by_lick_count": bool(n_phase_licks >= min_phase_licks),
        "phase_summary_by_trial_count": bool(n_phase_trials >= min_phase_trials),
        "thresholds": {
            "min_time_trials_per_session": min_time,
            "min_firstpeak_trials_per_session": min_firstpeak,
            "min_phase_licks_per_session": min_phase_licks,
            "min_phase_trials_per_session": min_phase_trials,
        },
        "counts": {
            "n_time_trials": int(n_time_trials),
            "n_first_peak_trials": int(n_first_peak_trials),
            "n_phase_licks": int(n_phase_licks),
            "n_phase_trials": int(n_phase_trials),
        },
    }
