"""Phase 7e — v7 lick detector (find_peaks based) + cross-detector dedupe.

Ports the v7 local-maxima detector from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 441-521)
plus the cross-detector dedupe logic (lines 709-732).

This module is the canonical Stage 2 detector that runs AFTER
:mod:`._preclean` and BEFORE the post-detection gates in :mod:`._gates`.
Designed to run ALONGSIDE the existing legacy slope detector
(:func:`._detector._slope_detect_lick_peaks`) and the bounded-fall
detector (also in scratch ref), with :func:`merge_detector_outputs`
collapsing overlapping peaks (find_peaks wins on overlap because its
local-max location is most accurate).

Algorithm (Decisions 14-15):

  Step 1 — :func:`detect_local_maxima` runs
    ``scipy.signal.find_peaks`` with ``distance=lm_min_distance_ms`` (50
    ms) and ``height=min_peak_y_abs``. Each local max is validated by
    ``consec_rise >= rise_min_n`` AND (``consec_fall >= fall_min_n`` OR
    immediate baseline retraction). Per-peak ``rise_starts`` and
    ``fall_ends`` (yseg-local frame indices) are tracked for the
    ``lick_events/`` parquet's ``rise_start_ms`` / ``fall_end_ms``
    columns per Decision 4.

  Step 2 — cross-detector dedupe via :func:`merge_detector_outputs`.
    Processes peak lists in order ``lmax → bounded → legacy``; collapses
    peaks within ``dedupe_radius_ms`` (50 ms) of an already-added peak.
    find_peaks wins on overlap. See Decision 14.

All numeric constants from ``configs/defaults.yaml:
dlc_kinematics.tongue_pertrial.detector_v2`` + the shared
``.detector`` block (no magic numbers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.signal import find_peaks

from stroke_orofacial.dlc_kinematics._detector import _moving_avg_nan


@dataclass
class _DetectedPeak:
    """Single detected peak with provenance.

    The ``source`` field tracks which detector emitted the peak
    (informational; survives into the per-trial-per-lick parquet's
    ``source`` column per Decision 4). Used by
    :func:`merge_detector_outputs` to track which source won on a
    dedupe overlap.

    Frame coordinates are **yseg-local** (i.e., relative to the
    detect-window slice), matching the legacy ``_LickPeaks`` convention.
    """

    frame: int
    t_ms: float
    y: float
    x: float
    likelihood: float
    source: str  # "lmax" | "bounded" | "legacy"
    rise_start_frame: int = -1   # -1 sentinel = not tracked
    fall_end_frame: int = -1


@dataclass
class _PeakList:
    """Output of :func:`detect_local_maxima`.

    Parallel-array shape matching the legacy
    :class:`stroke_orofacial.dlc_kinematics._detector._LickPeaks`
    convention. All frame indices are yseg-local (relative to the
    detect-window slice).
    """

    peak_times_ms: np.ndarray    # float, ms post-reward (tseg[peak_indices])
    peak_y: np.ndarray           # float, y at peak (yseg[peak_indices])
    peak_x: np.ndarray           # float, x at peak (xseg[peak_indices])
    peak_indices: np.ndarray     # int, yseg-local i_peak
    rise_starts: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.int64),
    )
    fall_ends: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.int64),
    )

    @classmethod
    def empty(cls) -> "_PeakList":
        return cls(
            peak_times_ms=np.zeros(0, dtype=np.float64),
            peak_y=np.zeros(0, dtype=np.float64),
            peak_x=np.zeros(0, dtype=np.float64),
            peak_indices=np.zeros(0, dtype=np.int64),
            rise_starts=np.zeros(0, dtype=np.int64),
            fall_ends=np.zeros(0, dtype=np.int64),
        )

    def __len__(self) -> int:  # n_peaks
        return len(self.peak_times_ms)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_local_maxima(
    y: np.ndarray,
    x: np.ndarray,
    t_ms: np.ndarray,
    fps: float,
    *,
    is_baseline_fill: np.ndarray,
    detect_win_ms: tuple[float, float],
    n_max: int | None = None,
    detector_params: dict[str, Any],
    params: dict[str, Any],
) -> _PeakList:
    """find_peaks-based local-maxima detector.

    Runs ``scipy.signal.find_peaks`` on the smoothed y signal with a
    ``distance`` constraint (``lm_min_distance_ms``). Each candidate
    peak is then validated by:

      - ``consec_rise >= rise_min_n`` consecutive rising frames before
        the peak (slope > ``slope_thr_px_per_s``)
      - ``consec_fall >= fall_min_n`` consecutive falling frames after
        the peak, OR immediate baseline retraction
        (``is_baseline_fill`` True at peak+1)

    Per-peak ``rise_starts`` (earliest consecutive rising frame =
    ``p - consec_rise``) and ``fall_ends`` (last consecutive falling
    frame = ``p + consec_fall``, or ``p + 1`` if accepted via implicit
    baseline retraction) are tracked. These feed the
    ``lick_events/`` parquet's ``rise_start_ms`` / ``fall_end_ms``
    columns per Decision 4 and tongue_velocity per-kept-lick gating per
    Decision 5.

    Direct port of
    ``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.detect_local_maxima``
    (lines 441-521) + NEW rise/fall delineation.

    Parameters
    ----------
    y, x : np.ndarray, shape (n_frames,)
        Pre-cleaned y and x traces (from :func:`._preclean.preclean_trace`).
    t_ms : np.ndarray
        Per-frame time relative to reward/tone (ms).
    fps : float
    is_baseline_fill : np.ndarray, dtype bool
        Post-preclean baseline-fill mask. Used for immediate-baseline-
        retraction fall acceptance.
    detect_win_ms : (float, float)
        (lo, hi) detection window in ms post-reward.
    n_max : int | None
        Optional cap on number of returned peaks (early-exit).
    detector_params : dict
        Shared detector knobs from
        ``configs/defaults.yaml: dlc_kinematics.tongue_pertrial.detector``
        (``slope_thr_px_per_s``, ``rise_min_ms``, ``fall_min_ms``,
        ``min_peak_y_abs``, ``do_smooth_y_for_detection``,
        ``smooth_ms_detect_y``).
    params : dict
        This module's block from
        ``configs/defaults.yaml: dlc_kinematics.tongue_pertrial.detector_v2``
        (``lm_min_distance_ms``).

    Returns
    -------
    _PeakList (possibly empty)
    """
    slope_thr = float(detector_params["slope_thr_px_per_s"])
    rise_min_ms = float(detector_params["rise_min_ms"])
    fall_min_ms = float(detector_params["fall_min_ms"])
    min_peak_y_abs = float(detector_params["min_peak_y_abs"])
    do_smooth_y = bool(detector_params["do_smooth_y_for_detection"])
    smooth_ms_y = float(detector_params["smooth_ms_detect_y"])
    lm_min_distance_ms = float(params["lm_min_distance_ms"])

    if y.size == 0:
        return _PeakList.empty()

    # Window clip.
    in_win = (t_ms >= detect_win_ms[0]) & (t_ms <= detect_win_ms[1])
    if not np.any(in_win):
        return _PeakList.empty()
    i_lo = int(np.argmax(in_win))
    i_hi = int(len(in_win) - 1 - np.argmax(in_win[::-1]))
    yseg = y[i_lo:i_hi + 1].astype(np.float64, copy=True)
    xseg = x[i_lo:i_hi + 1].astype(np.float64, copy=True)
    tseg = t_ms[i_lo:i_hi + 1]
    is_base_seg = is_baseline_fill[i_lo:i_hi + 1]

    # Smooth y for slope evaluation only.
    y_for_slope = (
        _moving_avg_nan(yseg, smooth_ms_y, fps) if do_smooth_y else yseg.copy()
    )
    finite = np.isfinite(y_for_slope)
    dy = np.full_like(y_for_slope, np.nan, dtype=np.float64)
    if np.count_nonzero(finite) >= 2:
        dy = np.gradient(y_for_slope) * fps  # px/s

    rise_min_n = max(1, int(round(rise_min_ms / 1000.0 * fps)))
    fall_min_n = max(1, int(round(fall_min_ms / 1000.0 * fps)))
    min_distance = max(1, int(round(lm_min_distance_ms / 1000.0 * fps)))

    # find_peaks needs no NaNs; replace with -inf so they're never peaks.
    y_search = y_for_slope.copy()
    y_search[~np.isfinite(y_search)] = -np.inf
    peaks_idx, _props = find_peaks(
        y_search, height=min_peak_y_abs, distance=min_distance,
    )

    L = len(yseg)
    times: list[float] = []
    ys: list[float] = []
    xs: list[float] = []
    peak_indices: list[int] = []
    rise_starts: list[int] = []
    fall_ends: list[int] = []

    for p in peaks_idx:
        # Validate rise: rise_min_n consecutive rising frames before p
        consec_rise = 0
        for k in range(p - 1, max(-1, p - rise_min_n * 3), -1):
            if k < 0 or not np.isfinite(dy[k]):
                break
            if dy[k] > slope_thr:
                consec_rise += 1
                if consec_rise >= rise_min_n:
                    break
            else:
                break
        if consec_rise < rise_min_n:
            continue

        # Validate fall: consec dy < -slope_thr OR immediate baseline retraction
        consec_fall = 0
        for k in range(p + 1, min(L, p + fall_min_n * 3)):
            if not np.isfinite(dy[k]):
                break
            if dy[k] < -slope_thr:
                consec_fall += 1
                if consec_fall >= fall_min_n:
                    break
            else:
                break
        fall_ok = consec_fall >= fall_min_n
        implicit_baseline_fall = False
        if not fall_ok:
            # Implicit fall via immediate baseline retraction
            if p + 1 < L and is_base_seg[p + 1]:
                fall_ok = True
                implicit_baseline_fall = True
        if not fall_ok:
            continue

        y_peak = yseg[p]
        if not np.isfinite(y_peak) or abs(y_peak) < min_peak_y_abs:
            continue

        # NEW: track rise/fall bounds (yseg-local indices)
        # rise_start = earliest consecutive rising frame
        rise_start = int(p - consec_rise)
        # fall_end = last consecutive falling frame, or p+1 for
        # implicit-baseline-fall (the first baseline frame after peak)
        if implicit_baseline_fall:
            fall_end = int(p + 1)
        else:
            fall_end = int(p + consec_fall)

        times.append(float(tseg[p]))
        ys.append(float(y_peak))
        xs.append(float(xseg[p]))
        peak_indices.append(int(p))
        rise_starts.append(rise_start)
        fall_ends.append(fall_end)
        if n_max is not None and len(times) >= n_max:
            break

    return _PeakList(
        peak_times_ms=np.asarray(times, dtype=np.float64),
        peak_y=np.asarray(ys, dtype=np.float64),
        peak_x=np.asarray(xs, dtype=np.float64),
        peak_indices=np.asarray(peak_indices, dtype=np.int64),
        rise_starts=np.asarray(rise_starts, dtype=np.int64),
        fall_ends=np.asarray(fall_ends, dtype=np.int64),
    )


def merge_detector_outputs(
    peak_lists: list[tuple[str, _PeakList | None]],
    likelihood: np.ndarray,
    fps: float,
    *,
    params: dict[str, Any],
) -> list[_DetectedPeak]:
    """Cross-detector dedupe (Decision 14).

    Input: list of ``(source_name, peak_list)`` tuples, processed in the
    order given. Caller is expected to pass them in the order
    ``[("lmax", ...), ("bounded", ...), ("legacy", ...)]`` so find_peaks
    wins on overlap (most-accurate peak location).

    For each peak, skip if its frame is within ``dedupe_radius_ms`` of
    any already-added peak. Otherwise add with its source tag.

    Returns the merged peak list sorted by frame index. Each peak's
    ``likelihood`` field is populated by indexing ``likelihood`` at the
    peak's frame.

    Direct port of scratch lines 709-732.

    Parameters
    ----------
    peak_lists : list of (source_name, _PeakList | None)
        Detector outputs in priority order (winner first).
    likelihood : np.ndarray, shape matching the segment the peaks index into
        Per-frame DLC likelihood for the ``_DetectedPeak.likelihood``
        field. Must be in the same yseg-local space as the peak indices.
    fps : float
    params : dict
        This module's block (``dedupe_radius_ms``).

    Returns
    -------
    list[_DetectedPeak] sorted by ``frame``
    """
    dedupe_radius_ms = float(params["dedupe_radius_ms"])
    dedupe_radius = max(1, int(round(dedupe_radius_ms / 1000.0 * fps)))

    added: list[_DetectedPeak] = []
    for source, pl in peak_lists:
        if pl is None or len(pl) == 0:
            continue
        n_peaks_in_pl = len(pl)
        for k in range(n_peaks_in_pl):
            pf = int(pl.peak_indices[k])
            if any(abs(pf - p.frame) <= dedupe_radius for p in added):
                continue
            lik_val = (
                float(likelihood[pf])
                if 0 <= pf < len(likelihood)
                else float("nan")
            )
            rise_start = (
                int(pl.rise_starts[k]) if k < len(pl.rise_starts) else -1
            )
            fall_end = (
                int(pl.fall_ends[k]) if k < len(pl.fall_ends) else -1
            )
            added.append(_DetectedPeak(
                frame=pf,
                t_ms=float(pl.peak_times_ms[k]),
                y=float(pl.peak_y[k]),
                x=float(pl.peak_x[k]),
                likelihood=lik_val,
                source=source,
                rise_start_frame=rise_start,
                fall_end_frame=fall_end,
            ))
    added.sort(key=lambda p: p.frame)
    return added
