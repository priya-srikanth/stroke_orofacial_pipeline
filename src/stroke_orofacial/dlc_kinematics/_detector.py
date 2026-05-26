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

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np


@dataclass
class _LickPeaks:
    """Output of :func:`_slope_detect_lick_peaks`.

    Coordinate convention (C5.6 clarification, 2026-04-30):

    - ``peak_indices`` (and the sister ``rise_starts`` / ``turnover``) index
      into the **detect-window subset** ``yseg = y_t[i_lo:i_hi+1]``, where
      ``i_lo`` is the first frame in ``t_ms`` within ``detect_win_ms``.
      To convert to trial-slice frames, add
      ``detect_lo_offset = i_lo``. Most consumers should use
      ``peak_times_ms`` and ``peak_y`` (already pre-offset via the
      detector's ``tseg = t_ms[i_lo:i_hi+1]`` / ``yseg`` indexing — safe
      to use directly). Use ``peak_indices`` directly only when you need
      a frame-resolved position; in that case ALWAYS apply
      ``detect_lo_offset``.
    - ``peak_times_ms`` is in trial-relative ms (post-reward) — already
      pre-offset.
    - ``peak_y`` / ``peak_x`` are values sampled from ``yseg`` / ``xseg``
      at ``peak_indices`` — consistent with the yseg-local convention.

    Cell 36 uses ``peak_indices`` for velocity windowing inside ``yseg``
    (consistent yseg-local space); Cell 50 (V3) and the per-trial scalar
    extractors use ``peak_times_ms`` to sample the per-frame angle trace.
    Phase 7a.4's :func:`_build_visual_bundle_per_trial` is the first
    consumer that crosses the boundary — it converts ``peak_indices`` to
    trial-slice space via the ``detect_lo_offset`` adjustment described
    above (C5.5 fix, 2026-04-30).
    """

    peak_times_ms: np.ndarray  # float, ms post-reward
    peak_y: np.ndarray         # float, y at peak (yseg[peak_indices])
    peak_x: np.ndarray         # float, x at peak (xseg[peak_indices])
    rise_starts: np.ndarray    # int, yseg-local i_rise per lick
    turnover: np.ndarray       # int, yseg-local i_turn (where dy crosses 0)
    peak_indices: np.ndarray   # int, yseg-local i_peak (argmax in [r0, k+pad])
    # Phase 7e Task 5c: end-of-fall-run frame index per lick (yseg-local).
    # Defaults to empty for backwards compat with callers that construct
    # _LickPeaks without setting it explicitly. _slope_detect_lick_peaks
    # populates it with the loop's ``end_idx`` value per peak (= f1 - 1
    # when a fall run was found, or i_peak + 1 for implicit-baseline-fall
    # acceptance, or i_peak otherwise). Consumed by the v7 orchestrator's
    # _legacy_peaks_to_peak_list adapter to populate the lick_events
    # parquet's fall_end_ms column.
    fall_ends: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))

    @classmethod
    def empty(cls) -> "_LickPeaks":
        return cls(
            peak_times_ms=np.zeros(0, dtype=np.float64),
            peak_y=np.zeros(0, dtype=np.float64),
            peak_x=np.zeros(0, dtype=np.float64),
            rise_starts=np.zeros(0, dtype=np.int64),
            turnover=np.zeros(0, dtype=np.int64),
            peak_indices=np.zeros(0, dtype=np.int64),
            fall_ends=np.zeros(0, dtype=np.int64),
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
    is_baseline_fill: np.ndarray | None = None,
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

    **Phase 7e Task 5c — bounded-fall mode** (optional, gated by two
    detector_params keys + the ``is_baseline_fill`` kwarg):
      * If ``max_fall_search_ms`` is set in ``detector_params``, the fall
        search after a peak is BOUNDED to ±max_fall_search_ms frames
        (mirrors scratch's ``detect_bounded_fall``). When unset (default
        None / missing key), fall search is unbounded (legacy behavior
        for Cells 33/36/39/42/50).
      * If ``accept_implicit_baseline_fall`` is True in ``detector_params``
        AND ``is_baseline_fill`` is provided, peaks with no fall run found
        within the bounded search are ACCEPTED if the immediately-next
        frame is ``is_baseline_fill=True`` (implicit baseline retraction).
        Mirrors scratch's bounded_fall acceptance path.

    With both keys set, the function behaves as the scratch's
    ``detect_bounded_fall``; with neither set, behavior is unchanged
    (legacy Cell 33/36/39/42/50 detector). Used by the v7 orchestrator
    in :mod:`.tongue_pertrial._run_v7_pipeline_per_trial` to invoke the
    same function in both "bounded" and "legacy" modes per Decision 14.
    """
    slope_thr = float(detector_params["slope_thr_px_per_s"])
    rise_min_ms = float(detector_params["rise_min_ms"])
    fall_min_ms = float(detector_params["fall_min_ms"])
    peak_pad_ms = float(detector_params["peak_pad_ms"])
    min_peak_y_abs = float(detector_params["min_peak_y_abs"])
    min_finite = int(detector_params["min_finite_samples_per_lick"])
    do_smooth_y = bool(detector_params["do_smooth_y_for_detection"])
    smooth_ms_y = float(detector_params["smooth_ms_detect_y"])
    strict_no_fallback = bool(detector_params.get("strict_no_fallback", True))
    # C5.5 (2026-04-29): legacy Cell 33 requires a fall run for peak
    # acceptance (under STRICT_NO_FALLBACK); Cells 36/39/42 accept peaks
    # regardless of whether a fall run is found. Default False reproduces
    # Cell 33's strict V3 behavior; per-cell override in
    # legacy_approximate flips Cells 36/39/42 to legacy's accept-always
    # semantics.
    accept_no_fall = bool(detector_params.get("accept_peaks_without_fall_run", False))
    # Phase 7e Task 5c — bounded-fall mode knobs (default-off; legacy
    # callers unaffected). See function docstring.
    _max_fall_search_ms_raw = detector_params.get("max_fall_search_ms")
    max_fall_search_n: int | None = (
        max(1, int(round(float(_max_fall_search_ms_raw) / 1000.0 * fps)))
        if _max_fall_search_ms_raw is not None
        else None
    )
    accept_implicit_baseline_fall = bool(
        detector_params.get("accept_implicit_baseline_fall", False)
    )

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
    # Task 5c: slice is_baseline_fill to match yseg (for implicit-baseline-
    # fall acceptance). None if caller didn't pass it (legacy callers).
    is_base_seg = (
        is_baseline_fill[i_lo:i_hi + 1]
        if is_baseline_fill is not None
        else None
    )

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
    fall_ends: list[int] = []   # Task 5c
    start = 0
    while True:
        if n_max is not None and len(peaks) >= n_max:
            break
        r0, r1 = _first_run_from(rise_mask, rise_min_n, start)
        if r0 is None:
            break

        # Turnover: walk past dy > 0 OR non-finite dy samples (legacy
        # tongue_cell33.py:326 semantics — fix #1 of three port bugs
        # surfaced by the Task 5b smoke parity, 2026-04-28). Treating NaN
        # as turnover (the prior buggy behavior) caused an extra early
        # peak on trials with brief tracking dropouts in the rise→fall
        # window.
        k = r1
        while k < L and (not np.isfinite(dy[k]) or dy[k] > 0):
            k += 1
        if k >= L:
            # No turnover found within the window. Legacy
            # ``STRICT_NO_FALLBACK=True`` rejects the lick and stops
            # searching (the loop has fallen off the end). Fix #3 (Task
            # 5b): match legacy by breaking here under strict mode.
            if strict_no_fallback:
                break
            start = r1 + 1
            continue

        # Peak inside [r0, min(k + peak_pad, L-1)].
        k_end = min(L - 1, k + peak_pad_n)
        seg = yseg[r0:k_end + 1]
        if seg.size == 0 or not np.any(np.isfinite(seg)):
            start = k + 1
            continue
        j_peak_local = int(np.nanargmax(seg))
        i_peak = r0 + j_peak_local

        # MIN_PEAK_Y_ABS gate (V3-NEW for Cells 36/39/42; pre-existing for
        # Cell 33, value 20.0 — per-cell knob handling lives in the main
        # module's _per_cell_detector helper).
        y_peak_val = yseg[i_peak]
        if not np.isfinite(y_peak_val) or abs(y_peak_val) < min_peak_y_abs:
            start = k + 1
            continue

        # MIN_FINITE_SAMPLES_PER_LICK gate (V3-NEW for Cells 33/39/42;
        # pre-existing for Cell 36, value 5).
        win_lo = max(0, i_peak - peak_pad_n)
        win_hi = min(L - 1, i_peak + peak_pad_n)
        n_finite = int(np.count_nonzero(np.isfinite(yseg[win_lo:win_hi + 1])))
        if n_finite < min_finite:
            start = k + 1
            continue

        # Fall validation + end_idx tracking (legacy tongue_cell33.py:348-355
        # — fix #2 + fix #3 of three port bugs surfaced by the Task 5b smoke
        # parity, 2026-04-28). The next-lick search must start at
        # ``end_idx + 1`` (post-fall-run-end), not ``i_peak + 1``; otherwise
        # the loop can re-detect an early peak that legacy walked past.
        # C5.5 (2026-04-29): the rejection-on-no-fall semantic is Cell 33-
        # specific. Cells 36/39/42 always append regardless of fall validation
        # (per their vendored detectors at cell{36,39,42}.py — no
        # ``return (None, ...)`` on ``f0 is None``). The ``accept_no_fall``
        # knob (per-cell, default False) controls this branch.
        end_idx = i_peak
        if fall_min_n > 1:
            # Task 5c bounded-fall mode: bound the fall search to
            # [i_peak, i_peak + max_fall_search_n] if the knob is set.
            # Default (None) preserves legacy unbounded search.
            if max_fall_search_n is not None:
                search_hi = min(L, i_peak + max_fall_search_n + 1)
                effective_fall_mask = fall_mask.copy()
                effective_fall_mask[search_hi:] = False
            else:
                effective_fall_mask = fall_mask
            f0, f1 = _first_run_from(effective_fall_mask, fall_min_n, i_peak)
            if f0 is None:
                # Task 5c implicit-baseline-fall acceptance: if the knob
                # is True AND is_baseline_fill was provided AND the next
                # frame is baseline-fill, accept the peak with end_idx
                # = i_peak + 1. Mirrors scratch's bounded_fall acceptance
                # path. Falls through to legacy strict / accept_no_fall
                # otherwise.
                implicit_baseline_accept = (
                    accept_implicit_baseline_fall
                    and is_base_seg is not None
                    and (i_peak + 1) < L
                    and bool(is_base_seg[i_peak + 1])
                )
                if implicit_baseline_accept:
                    end_idx = i_peak + 1
                elif strict_no_fallback and not accept_no_fall:
                    start = i_peak + 1  # advance past peak; do not append
                    continue
                # else: accept the peak with end_idx = i_peak (no fall extension).
            else:
                end_idx = max(end_idx, f1 - 1)

        rise_starts.append(r0)
        turnovers.append(k)
        peaks.append(i_peak)
        ys.append(float(y_peak_val))
        xs.append(float(xseg[i_peak]))
        times.append(float(tseg[i_peak]))
        fall_ends.append(end_idx)   # Task 5c
        start = end_idx + 1

    return _LickPeaks(
        peak_times_ms=np.asarray(times, dtype=np.float64),
        peak_y=np.asarray(ys, dtype=np.float64),
        peak_x=np.asarray(xs, dtype=np.float64),
        rise_starts=np.asarray(rise_starts, dtype=np.int64),
        turnover=np.asarray(turnovers, dtype=np.int64),
        peak_indices=np.asarray(peaks, dtype=np.int64),
        fall_ends=np.asarray(fall_ends, dtype=np.int64),
    )


def _build_bouts(
    peak_times_ms: np.ndarray, max_ili_ms: float,
) -> list[np.ndarray]:
    """Group consecutive peaks (ILI <= ``max_ili_ms``) into bouts.

    Returns a list of arrays of indices into ``peak_times_ms``. Each array
    is contiguous and sorted; bouts are separated by ILIs > ``max_ili_ms``.
    """
    # NOTE (2026-05-04, Phase 7a.4-cross-session-angle Addendum #6 audit):
    # ``configs/defaults.yaml`` carries ``allow_single_lick_bouts: true``
    # under ``dlc_kinematics.tongue_pertrial.bout`` for documentation
    # parity with legacy ``ALLOW_SINGLE_LICK_BOUTS`` (= True default).
    # The consolidated implementation hard-wires the True behavior:
    # this function always returns single-peak bouts (every detected
    # peak ends up in some bout, regardless of whether it has neighbors
    # within ``max_ili_ms``). The config knob currently has no consume
    # path. To gate singletons in a future phase, add the filter here
    # (e.g., drop single-element ``bouts[i]`` when the knob is False)
    # and wire the config read at the caller layer.
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
    # Task 5c: preserve fall_ends through the filter; tolerate the
    # backwards-compat case where the input _LickPeaks has empty
    # fall_ends (some callers construct without setting it).
    fall_ends_in = peaks.fall_ends
    fall_ends_out = (
        fall_ends_in[keep]
        if len(fall_ends_in) == len(peaks.peak_indices)
        else np.zeros(0, dtype=np.int64)
    )
    return _LickPeaks(
        peak_times_ms=peaks.peak_times_ms[keep],
        peak_y=peaks.peak_y[keep],
        peak_x=peaks.peak_x[keep],
        rise_starts=peaks.rise_starts[keep],
        turnover=peaks.turnover[keep],
        peak_indices=peaks.peak_indices[keep],
        fall_ends=fall_ends_out,
    )
