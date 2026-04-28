"""Phase 7a.3 V3 — unified slope detector + bout helpers (private).

Implements the V3 unified slope detector shared by Cells 33/36/39/42/50,
plus bout building and per-metric bout-mode filtering. Public callers go
through :mod:`stroke_orofacial.dlc_kinematics.tongue_pertrial`; this
module is private (underscore prefix) and reserved for that module + its
unit tests (Task 4).

V3-NEW knob additions (Task 1.5 + Q1–Q9 lock):

- ``min_peak_y_abs``: reject peaks with ``|y_peak|`` below threshold.
  Added to Cells 36/39/42 (legacy lacked).
- ``min_finite_samples_per_lick``: reject peaks with too few finite
  samples in ``[i_peak − peak_pad, i_peak + peak_pad]``. Added to
  Cells 33/39/42.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


@dataclass
class _LickPeaks:
    """Detected lick peaks within one trial slice.

    Per-lick window indices (``rise_starts``, ``turnover``, ``peak_indices``)
    index into the trial slice (NOT session indices). Cell 36 uses them to
    pick the velocity window; Cell 50 uses them via the lick t_peak times
    to sample the per-frame angle trace.
    """

    peak_times_ms: np.ndarray  # float, ms post-reward
    peak_y: np.ndarray         # float, y at peak
    peak_x: np.ndarray         # float, x at peak
    rise_starts: np.ndarray    # int, i_rise per lick
    turnover: np.ndarray       # int, i_turn per lick (sample where dy crosses 0)
    peak_indices: np.ndarray   # int, i_peak per lick (argmax in [r0, k+pad])

    @classmethod
    def empty(cls) -> "_LickPeaks":
        return cls(
            peak_times_ms=np.zeros(0, dtype=np.float64),
            peak_y=np.zeros(0, dtype=np.float64),
            peak_x=np.zeros(0, dtype=np.float64),
            rise_starts=np.zeros(0, dtype=np.int64),
            turnover=np.zeros(0, dtype=np.int64),
            peak_indices=np.zeros(0, dtype=np.int64),
        )

    def __len__(self) -> int:  # n_peaks
        return len(self.peak_times_ms)


def _moving_avg_nan(arr: np.ndarray, window_ms: float, fps: float) -> np.ndarray:
    """NaN-tolerant centered moving average over a small window (ms)."""
    win_n = max(1, int(round(window_ms / 1000.0 * fps)))
    if win_n <= 1:
        return arr.astype(np.float64, copy=True)
    finite = np.isfinite(arr).astype(np.float64)
    safe = np.where(np.isfinite(arr), arr, 0.0)
    kernel = np.ones(win_n, dtype=np.float64)
    num = np.convolve(safe, kernel, mode="same")
    den = np.convolve(finite, kernel, mode="same")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    nz = den > 0
    out[nz] = num[nz] / den[nz]
    return out


def _first_run_from(
    mask: np.ndarray, min_len: int, start: int,
) -> tuple[int | None, int | None]:
    """First ``True`` run of length >= ``min_len`` starting at index >= ``start``.

    Returns ``(run_start, run_end_inclusive)`` or ``(None, None)``.
    """
    n = len(mask)
    i = start
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            run_len = j - i
            if run_len >= min_len:
                return i, j - 1
            i = j
        else:
            i += 1
    return None, None


def _slope_detect_lick_peaks(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, detect_win_ms: tuple[float, float], detector_params: dict[str, Any],
    n_max: int | None = None,
) -> _LickPeaks:
    """Slope-based rise/fall detector. Cells 33/36/39/42/50 share this routine.

    Per-lick acceptance:
      * rise: ``dy/dt > slope_thr`` for >= ``rise_min_ms``
      * turnover: first sample after rise where ``dy/dt`` crosses 0
      * fall (optional, gated by min length): ``dy/dt < -slope_thr`` for
        >= ``fall_min_ms`` after turnover
      * peak: argmax of y inside ``[r0, min(k + peak_pad, end)]``
      * |y_peak| >= ``min_peak_y_abs`` (V3-NEW for Cells 36/39/42)
      * count of finite samples in ``[i_peak - peak_pad, i_peak + peak_pad]``
        >= ``min_finite_samples_per_lick`` (V3-NEW for Cells 33/39/42)

    Returns peaks whose ``t_ms`` falls inside ``detect_win_ms``.
    """
    slope_thr = float(detector_params["slope_thr_px_per_s"])
    rise_min_ms = float(detector_params["rise_min_ms"])
    fall_min_ms = float(detector_params["fall_min_ms"])
    peak_pad_ms = float(detector_params["peak_pad_ms"])
    min_peak_y_abs = float(detector_params["min_peak_y_abs"])
    min_finite = int(detector_params["min_finite_samples_per_lick"])
    do_smooth_y = bool(detector_params["do_smooth_y_for_detection"])
    smooth_ms_y = float(detector_params["smooth_ms_detect_y"])

    if y_t.size == 0:
        return _LickPeaks.empty()

    # Window clip.
    in_win = (t_ms >= detect_win_ms[0]) & (t_ms <= detect_win_ms[1])
    if not np.any(in_win):
        return _LickPeaks.empty()
    i_lo = int(np.argmax(in_win))
    i_hi = int(len(in_win) - 1 - np.argmax(in_win[::-1]))
    yseg = y_t[i_lo:i_hi + 1].astype(np.float64, copy=True)
    xseg = x_t[i_lo:i_hi + 1].astype(np.float64, copy=True)
    tseg = t_ms[i_lo:i_hi + 1]

    # Smooth y for slope evaluation only (per V3 detector knobs).
    y_for_slope = (
        _moving_avg_nan(yseg, smooth_ms_y, fps) if do_smooth_y else yseg.copy()
    )
    finite = np.isfinite(y_for_slope)
    dy = np.full_like(y_for_slope, np.nan, dtype=np.float64)
    if np.count_nonzero(finite) >= 2:
        dy = np.gradient(y_for_slope) * fps  # px/s
    finite_dy = np.isfinite(dy) & np.isfinite(yseg) & np.isfinite(xseg)

    rise_mask = finite_dy & (dy > slope_thr)
    fall_mask = finite_dy & (dy < -slope_thr)
    rise_min_n = max(1, int(round(rise_min_ms / 1000.0 * fps)))
    fall_min_n = max(1, int(round(fall_min_ms / 1000.0 * fps)))
    peak_pad_n = max(1, int(round(peak_pad_ms / 1000.0 * fps)))

    L = len(yseg)
    rise_starts: list[int] = []
    turnovers: list[int] = []
    peaks: list[int] = []
    times: list[float] = []
    ys: list[float] = []
    xs: list[float] = []
    start = 0
    while True:
        if n_max is not None and len(peaks) >= n_max:
            break
        r0, r1 = _first_run_from(rise_mask, rise_min_n, start)
        if r0 is None:
            break

        # Turnover: first sample after r1 where dy <= 0.
        k = r1
        while k < L - 1 and (np.isfinite(dy[k]) and dy[k] > 0):
            k += 1
        if k >= L:
            break

        # Peak inside [r0, min(k + peak_pad, L-1)].
        k_end = min(L - 1, k + peak_pad_n)
        seg = yseg[r0:k_end + 1]
        if seg.size == 0 or not np.any(np.isfinite(seg)):
            start = k + 1
            continue
        j_peak_local = int(np.nanargmax(seg))
        i_peak = r0 + j_peak_local

        # MIN_PEAK_Y_ABS gate (V3-NEW for Cells 36/39/42).
        y_peak_val = yseg[i_peak]
        if not np.isfinite(y_peak_val) or abs(y_peak_val) < min_peak_y_abs:
            start = k + 1
            continue

        # MIN_FINITE_SAMPLES_PER_LICK gate (V3-NEW for Cells 33/39/42).
        win_lo = max(0, i_peak - peak_pad_n)
        win_hi = min(L - 1, i_peak + peak_pad_n)
        n_finite = int(np.count_nonzero(np.isfinite(yseg[win_lo:win_hi + 1])))
        if n_finite < min_finite:
            start = k + 1
            continue

        # Optional fall validation (legacy pattern; soft check, doesn't reject).
        _fall_run = _first_run_from(fall_mask, fall_min_n, k)
        del _fall_run

        rise_starts.append(r0)
        turnovers.append(k)
        peaks.append(i_peak)
        ys.append(float(y_peak_val))
        xs.append(float(xseg[i_peak]))
        times.append(float(tseg[i_peak]))
        start = i_peak + 1

    return _LickPeaks(
        peak_times_ms=np.asarray(times, dtype=np.float64),
        peak_y=np.asarray(ys, dtype=np.float64),
        peak_x=np.asarray(xs, dtype=np.float64),
        rise_starts=np.asarray(rise_starts, dtype=np.int64),
        turnover=np.asarray(turnovers, dtype=np.int64),
        peak_indices=np.asarray(peaks, dtype=np.int64),
    )


def _build_bouts(
    peak_times_ms: np.ndarray, max_ili_ms: float,
) -> list[np.ndarray]:
    """Group consecutive peaks (ILI <= ``max_ili_ms``) into bouts.

    Returns a list of arrays of indices into ``peak_times_ms``. Each array
    is contiguous and sorted; bouts are separated by ILIs > ``max_ili_ms``.
    """
    n = len(peak_times_ms)
    if n == 0:
        return []
    order = np.argsort(peak_times_ms)
    sorted_t = peak_times_ms[order]
    bouts: list[list[int]] = [[int(order[0])]]
    for k in range(1, n):
        ili = sorted_t[k] - sorted_t[k - 1]
        if ili <= max_ili_ms:
            bouts[-1].append(int(order[k]))
        else:
            bouts.append([int(order[k])])
    return [np.asarray(b, dtype=np.int64) for b in bouts]


def _filter_peaks_by_bout_mode(
    peaks: _LickPeaks, *,
    mode: Literal["all", "first_bout", "first_multi_bout"],
    bout_params: dict[str, Any],
) -> _LickPeaks:
    """Subset detected peaks per bout-mode.

    - ``"all"``: no filtering.
    - ``"first_bout"``: peaks of the first bout.
    - ``"first_multi_bout"``: peaks of the first bout containing >= 2 licks.
    """
    if mode == "all" or len(peaks) == 0:
        return peaks
    bouts = _build_bouts(peaks.peak_times_ms, float(bout_params["max_ili_ms"]))
    if not bouts:
        return _LickPeaks.empty()
    if mode == "first_bout":
        keep = bouts[0]
    elif mode == "first_multi_bout":
        multi = [b for b in bouts if len(b) >= 2]
        if not multi:
            return _LickPeaks.empty()
        keep = multi[0]
    else:
        raise ValueError(f"unknown bout mode {mode!r}")
    return _LickPeaks(
        peak_times_ms=peaks.peak_times_ms[keep],
        peak_y=peaks.peak_y[keep],
        peak_x=peaks.peak_x[keep],
        rise_starts=peaks.rise_starts[keep],
        turnover=peaks.turnover[keep],
        peak_indices=peaks.peak_indices[keep],
    )
