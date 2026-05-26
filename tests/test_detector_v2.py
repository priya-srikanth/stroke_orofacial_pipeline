"""Tests for stroke_orofacial.dlc_kinematics._detector_v2.

Covers Phase 7e Task 3 deliverable: synthetic-trace tests for
``detect_local_maxima`` (find_peaks-based detection with rise/fall
validation + rise_start/fall_end delineation) and
``merge_detector_outputs`` (cross-detector dedupe).

Parity vs the v7 scratch reference on real trial data lives in
``test_v7_parity.py`` (Phase 7e Task 8).
"""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.dlc_kinematics._detector_v2 import (
    _DetectedPeak,
    _PeakList,
    detect_local_maxima,
    merge_detector_outputs,
)

FPS = 250.0

# Detector params mirror configs/defaults.yaml: dlc_kinematics.tongue_pertrial.detector
DETECTOR_PARAMS: dict = {
    "slope_thr_px_per_s": 250.0,
    "rise_min_ms": 16.0,
    "fall_min_ms": 16.0,
    "peak_pad_ms": 52.0,
    "min_peak_y_abs": 20.0,
    "min_finite_samples_per_lick": 5,
    "strict_no_fallback": True,
    "accept_peaks_without_fall_run": False,
    "use_src": "final",
    "do_smooth_y_for_detection": True,
    "smooth_ms_detect_y": 12.0,
    "do_smooth_vel": True,
    "smooth_ms_vel": 12.0,
}
PARAMS_V2: dict = {
    "lm_min_distance_ms": 50.0,
    "dedupe_radius_ms": 50.0,
    "max_fall_search_ms": 52.0,
}
DETECT_WIN_MS = (0.0, 3000.0)


def _make_synthetic_trace(
    n_frames: int = 200,
    peak_frames: list[int] | None = None,
    peak_amp: float = 150.0,
    rise_n: int = 8,
    fall_n: int = 8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Make a synthetic y trace with triangular peaks at given frames.

    Returns (y, x, t_ms, is_baseline_fill). x is fixed at 50.0;
    is_baseline_fill is False everywhere except outside the peak windows.

    Rise/fall use ``peak_amp * (N + 1 - d) / (N + 1)`` so y[p-1] < peak_amp
    (strict local max — find_peaks needs strict, not plateau).
    """
    y = np.zeros(n_frames, dtype=float)
    x = np.full(n_frames, 50.0)
    is_base = np.ones(n_frames, dtype=bool)  # baseline-fill outside peaks
    for p in (peak_frames or []):
        # Triangular rise — strictly less than peak_amp at d=1
        for d in range(1, rise_n + 1):
            if p - d >= 0:
                val = peak_amp * (rise_n + 1 - d) / (rise_n + 1)
                y[p - d] = max(y[p - d], val)
                is_base[p - d] = False
        y[p] = peak_amp
        is_base[p] = False
        # Triangular fall — strictly less than peak_amp at d=1
        for d in range(1, fall_n + 1):
            if p + d < n_frames:
                val = peak_amp * (fall_n + 1 - d) / (fall_n + 1)
                y[p + d] = max(y[p + d], val)
                is_base[p + d] = False
    t_ms = np.arange(n_frames) / FPS * 1000.0
    return y, x, t_ms, is_base


# ===========================================================================
# detect_local_maxima — find_peaks + rise/fall validation
# ===========================================================================


class TestDetectLocalMaxima:
    def test_empty_input_returns_empty(self):
        pl = detect_local_maxima(
            y=np.array([], dtype=float),
            x=np.array([], dtype=float),
            t_ms=np.array([], dtype=float),
            fps=FPS,
            is_baseline_fill=np.array([], dtype=bool),
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 0

    def test_no_window_overlap_returns_empty(self):
        n = 50
        y, x, t_ms, is_base = _make_synthetic_trace(n, peak_frames=[25])
        # Window outside trace's t range
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=(10_000.0, 20_000.0),
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 0

    def test_single_clean_peak_detected(self):
        """One triangular peak — detector finds it with rise_start/fall_end set."""
        n = 100
        y, x, t_ms, is_base = _make_synthetic_trace(n, peak_frames=[50])
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 1
        assert pl.peak_indices[0] == 50
        assert pl.peak_y[0] == pytest.approx(150.0, rel=0.05)
        assert pl.peak_x[0] == 50.0
        # rise_start should be before the peak; fall_end after
        assert pl.rise_starts[0] < pl.peak_indices[0]
        assert pl.fall_ends[0] > pl.peak_indices[0]

    def test_well_separated_peaks_both_kept(self):
        """Peaks 30 frames apart (>> 12-frame distance) → both kept."""
        n = 150
        y, x, t_ms, is_base = _make_synthetic_trace(
            n, peak_frames=[40, 80], peak_amp=150.0, rise_n=8, fall_n=8,
        )
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 2
        # Returned in frame order
        assert pl.peak_indices[0] < pl.peak_indices[1]

    def test_peak_below_min_y_rejected(self):
        """find_peaks(height=20) drops peaks below the threshold."""
        n = 100
        y, x, t_ms, is_base = _make_synthetic_trace(
            n, peak_frames=[50], peak_amp=15.0,  # below min_peak_y_abs=20
        )
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 0

    def test_no_rise_rejects_peak(self):
        """Peak with NO consecutive rising frames before it → rejected
        (flat-then-spike-then-flat pattern)."""
        n = 50
        y = np.zeros(n, dtype=float)
        x = np.full(n, 50.0)
        is_base = np.ones(n, dtype=bool)
        # Spike: just one frame at peak with no rise (jump from 0)
        y[25] = 150.0
        is_base[25] = False
        t_ms = np.arange(n) / FPS * 1000.0
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        # Single-frame spike: no rise → rejected
        assert len(pl) == 0

    # NOTE: implicit-baseline-fall acceptance (fall_n=0 with is_baseline
    # next-frame) is hard to test cleanly in synthetic because the sharp
    # post-peak drop creates smoothing artifacts that shift find_peaks'
    # picked frame. Covered by parity test on real PS54 51L data
    # (.scratch_phase_7e/parity_check_detector_v2.py) which exercises
    # this code path naturally.

    def test_rise_start_fall_end_consistency(self):
        """For a normal triangular peak, rise_start < peak < fall_end and
        rise_start/fall_end count rise_min_n / fall_min_n consec frames."""
        n = 100
        y, x, t_ms, is_base = _make_synthetic_trace(n, peak_frames=[50])
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        # rise_min_n = fall_min_n = ceil(16ms * 250fps / 1000) = 4 frames
        rise_min_n = max(1, int(round(16.0 / 1000.0 * FPS)))
        p = pl.peak_indices[0]
        # rise_start = p - consec_rise; consec_rise stops at rise_min_n
        assert pl.rise_starts[0] == p - rise_min_n
        assert pl.fall_ends[0] == p + rise_min_n  # same n for rise/fall

    def test_n_max_caps_output(self):
        """n_max parameter caps the returned peak count."""
        n = 200
        y, x, t_ms, is_base = _make_synthetic_trace(
            n, peak_frames=[30, 60, 90, 120, 150],
        )
        pl = detect_local_maxima(
            y=y, x=x, t_ms=t_ms, fps=FPS,
            is_baseline_fill=is_base,
            detect_win_ms=DETECT_WIN_MS,
            n_max=2,
            detector_params=DETECTOR_PARAMS,
            params=PARAMS_V2,
        )
        assert len(pl) == 2


# ===========================================================================
# merge_detector_outputs — cross-detector dedupe
# ===========================================================================


def _make_peak_list(frames: list[int], y_vals: list[float] | None = None) -> _PeakList:
    """Build a synthetic _PeakList for dedupe testing."""
    n = len(frames)
    return _PeakList(
        peak_times_ms=np.array(frames, dtype=float) * 4.0,  # 250fps
        peak_y=np.array(y_vals or [100.0] * n, dtype=float),
        peak_x=np.full(n, 50.0),
        peak_indices=np.array(frames, dtype=np.int64),
        rise_starts=np.array([f - 4 for f in frames], dtype=np.int64),
        fall_ends=np.array([f + 4 for f in frames], dtype=np.int64),
    )


class TestMergeDetectorOutputs:
    def test_single_source_passthrough(self):
        """One source, peaks 30 frames apart → all 3 kept, source tagged."""
        pl = _make_peak_list([10, 40, 70])
        merged = merge_detector_outputs(
            [("lmax", pl)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 3
        assert all(p.source == "lmax" for p in merged)
        assert all(p.likelihood == 0.9 for p in merged)
        assert [p.frame for p in merged] == [10, 40, 70]
        # rise/fall carried through
        assert merged[0].rise_start_frame == 6
        assert merged[0].fall_end_frame == 14

    def test_lmax_wins_over_legacy_on_overlap(self):
        """lmax peak at 50, legacy peak at 55 (within 12-frame dedupe radius)
        → lmax wins, legacy dropped."""
        lmax_pl = _make_peak_list([50])
        legacy_pl = _make_peak_list([55])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("legacy", legacy_pl)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].source == "lmax"
        assert merged[0].frame == 50

    def test_non_overlapping_peaks_all_kept(self):
        """Peaks far apart from different sources → all kept."""
        lmax_pl = _make_peak_list([20])
        bounded_pl = _make_peak_list([60])
        legacy_pl = _make_peak_list([100])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("bounded", bounded_pl), ("legacy", legacy_pl)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 3
        assert [p.frame for p in merged] == [20, 60, 100]
        # Source ordering preserved by frame sort
        srcs = [p.source for p in merged]
        assert srcs == ["lmax", "bounded", "legacy"]

    def test_none_peak_list_skipped(self):
        """None entries in peak_lists list are skipped gracefully."""
        lmax_pl = _make_peak_list([50])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("bounded", None), ("legacy", None)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].frame == 50

    def test_empty_peak_list_skipped(self):
        """Empty _PeakList entries are skipped."""
        merged = merge_detector_outputs(
            [("lmax", _PeakList.empty()), ("legacy", _make_peak_list([42]))],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].source == "legacy"

    def test_likelihood_lookup_at_each_frame(self):
        """Per-peak likelihood is sampled from likelihood[peak_frame]."""
        pl = _make_peak_list([10, 30])
        lik = np.linspace(0.0, 1.0, 200)
        merged = merge_detector_outputs(
            [("lmax", pl)],
            likelihood=lik,
            fps=FPS,
            params=PARAMS_V2,
        )
        assert merged[0].likelihood == pytest.approx(lik[10], abs=1e-9)
        assert merged[1].likelihood == pytest.approx(lik[30], abs=1e-9)

    def test_likelihood_out_of_bounds_returns_nan(self):
        """Peak frame outside likelihood array bounds → NaN."""
        pl = _make_peak_list([500])  # out of bounds
        merged = merge_detector_outputs(
            [("lmax", pl)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert np.isnan(merged[0].likelihood)

    def test_intra_source_dedupe(self):
        """Two peaks within dedupe radius from the SAME source → second dropped.
        (Defensive — detect_local_maxima already enforces distance, but
        legacy / bounded may emit closer peaks.)"""
        pl = _make_peak_list([50, 55])  # 5 frames apart, < 12-frame dedupe
        merged = merge_detector_outputs(
            [("legacy", pl)],
            likelihood=np.full(200, 0.9),
            fps=FPS,
            params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].frame == 50  # first one wins

    # Task 5c — Decision 14 three-detector dedupe coverage

    def test_lmax_only_peaks_survive(self):
        """If only lmax fires, all its peaks survive (bounded + legacy empty)."""
        lmax_pl = _make_peak_list([20, 60, 100])
        merged = merge_detector_outputs(
            [
                ("lmax", lmax_pl),
                ("bounded", _PeakList.empty()),
                ("legacy", _PeakList.empty()),
            ],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert [p.frame for p in merged] == [20, 60, 100]
        assert all(p.source == "lmax" for p in merged)

    def test_bounded_only_peaks_survive(self):
        """If only bounded fires (lmax / legacy empty), all bounded peaks survive."""
        bounded_pl = _make_peak_list([30, 70])
        merged = merge_detector_outputs(
            [
                ("lmax", _PeakList.empty()),
                ("bounded", bounded_pl),
                ("legacy", _PeakList.empty()),
            ],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert [p.frame for p in merged] == [30, 70]
        assert all(p.source == "bounded" for p in merged)

    def test_overlap_lmax_bounded_lmax_wins(self):
        """lmax peak at frame 50 + bounded peak at frame 55 (5 < 12-frame
        dedupe radius) → lmax wins, bounded dropped (Decision 14)."""
        lmax_pl = _make_peak_list([50])
        bounded_pl = _make_peak_list([55])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("bounded", bounded_pl), ("legacy", _PeakList.empty())],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].source == "lmax"
        assert merged[0].frame == 50

    def test_three_way_overlap_lmax_wins(self):
        """lmax + bounded + legacy all within dedupe radius → lmax wins."""
        lmax_pl = _make_peak_list([50])
        bounded_pl = _make_peak_list([54])
        legacy_pl = _make_peak_list([56])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("bounded", bounded_pl), ("legacy", legacy_pl)],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].source == "lmax"
        assert merged[0].frame == 50

    def test_bounded_legacy_overlap_bounded_wins(self):
        """No lmax + bounded + legacy within dedupe radius → bounded wins
        (processing order)."""
        bounded_pl = _make_peak_list([50])
        legacy_pl = _make_peak_list([55])
        merged = merge_detector_outputs(
            [("lmax", _PeakList.empty()), ("bounded", bounded_pl), ("legacy", legacy_pl)],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert len(merged) == 1
        assert merged[0].source == "bounded"
        assert merged[0].frame == 50

    def test_well_separated_three_source_peaks_all_survive(self):
        """Peaks > 50 ms apart from each source → all 3 kept."""
        lmax_pl = _make_peak_list([20])
        bounded_pl = _make_peak_list([60])
        legacy_pl = _make_peak_list([100])
        merged = merge_detector_outputs(
            [("lmax", lmax_pl), ("bounded", bounded_pl), ("legacy", legacy_pl)],
            likelihood=np.full(200, 0.9), fps=FPS, params=PARAMS_V2,
        )
        assert len(merged) == 3
        assert [p.frame for p in merged] == [20, 60, 100]
        assert [p.source for p in merged] == ["lmax", "bounded", "legacy"]
