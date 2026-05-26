"""Tests for stroke_orofacial.dlc_kinematics._preclean.

Covers Phase 7e Task 2 deliverable: synthetic-trace tests for each y-side
gate (Decisions 9-13) and each x-side rule (Addendum #1 Rules 1-4) +
end-to-end ``preclean_trace`` orchestration.

All tests construct ``params`` inline so they're not coupled to the YAML
defaults; parity tests against the v7 scratch reference use real YAML
values and live in ``test_v7_parity.py`` (Phase 7e Task 8).
"""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.dlc_kinematics._preclean import (
    _PrecleanDiagnostics,
    _RawCluster,
    _classify_raw_clusters,
    _clean_x_trace,
    _derive_x0_baseline_fill,
    _extend_pchip_around_range,
    _find_x_isolated_jumps,
    _find_y_frame_outliers,
    _wipe_bracketed_interp,
    preclean_trace,
)

# Default params dict — mirrors configs/defaults.yaml: dlc_kinematics.
# tongue_pertrial.preclean. Tests can override individual keys.
FPS = 250.0
DEFAULT_PARAMS: dict[str, float | int] = {
    "high_thr_px": 130.0,
    "shape_low_thr_px": 80.0,
    "shape_range_thr_px": 50.0,
    "nbrhd_radius_ms": 100.0,
    "isolated_max_n": 3,
    "isolated_radius_ms": 20.0,
    "frame_jump_thr_px": 100.0,
    "frame_radius_ms": 20.0,
    "pchip_extend_ms": 40.0,
    "flat_min_len": 20,
    "flat_max_range_px": 3.0,
    "flat_min_y_px": 30.0,
    "x_abs_max_px": 110.0,
    "x_pchip_extend_ms": 40.0,
    "x_jump_thr_px": 30.0,
    "x_flank_max_distance": 5,
}


def _empty_masks(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (is_interp_fill, is_baseline_fill) all-False of length n."""
    return np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)


# ===========================================================================
# Step 1a — cluster classifier (Decisions 9-11)
# ===========================================================================


class TestClassifyRawClusters:
    def test_low_cluster_kept(self):
        """cluster_max < HIGH_THR (130) → keep_low regardless of shape."""
        y = np.array([20, 40, 60, 80, 100, 80, 60, 40, 20], dtype=float)
        is_intp, is_base = _empty_masks(len(y))
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, len(y), FPS, params=DEFAULT_PARAMS,
        )
        assert len(clusters) == 1
        assert clusters[0].label == "keep_low"

    def test_rule_a_low_min(self):
        """High cluster with cluster_min < SHAPE_LOW (80) → keep_real (A)."""
        y = np.array([20, 60, 100, 140, 100, 60, 20], dtype=float)
        is_intp, is_base = _empty_masks(len(y))
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, len(y), FPS, params=DEFAULT_PARAMS,
        )
        assert len(clusters) == 1
        assert clusters[0].label.startswith("keep_real")
        # min=20 < SHAPE_LOW=80 → A=1
        assert "A=1" in clusters[0].label

    def test_rule_a_wide_range(self):
        """High cluster with cluster_range > SHAPE_RANGE (50) → keep_real (A)."""
        y = np.array([90, 110, 130, 150, 130, 110, 90], dtype=float)
        is_intp, is_base = _empty_masks(len(y))
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, len(y), FPS, params=DEFAULT_PARAMS,
        )
        assert clusters[0].label.startswith("keep_real")
        # min=90 >= 80 (A_low fails) BUT range=60 > 50 (A_range passes)
        assert "A=1" in clusters[0].label

    def test_rule_b_neighbor(self):
        """High narrow cluster with non-base low PCHIP neighbor → keep_real (B).

        Must use n > isolated_max_n (=3) so the isolated-short override doesn't
        fire first.
        """
        # Cluster at frames 8-12 (high, flat, n=5); surrounding frames 0-7 are
        # PCHIP-interp (is_intp=True, ~is_base) with low y → non-base low neighbor
        n = 20
        y = np.full(n, 50.0)
        y[8:13] = 140.0   # n=5 cluster (above isolated_max_n=3)
        is_intp = np.zeros(n, dtype=bool)
        is_intp[:8] = True
        is_intp[13:] = True
        is_base = np.zeros(n, dtype=bool)
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # The high cluster is at [8,12]. min=140 (>=80, fails A_low),
        # range=0 (<=50, fails A_range). But non-base neighbor at 7 with
        # y=50 < 130 satisfies Rule B.
        high_cluster = next(c for c in clusters if c.y_max >= 130)
        assert high_cluster.label.startswith("keep_real"), (
            f"got {high_cluster.label!r}"
        )
        assert "B1=1" in high_cluster.label and "B2=1" in high_cluster.label

    def test_artifact_narrow(self):
        """High narrow cluster with all-baseline neighbors → artifact_narrow."""
        n = 20
        y = np.zeros(n)
        y[8:11] = 140.0   # high narrow cluster
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.ones(n, dtype=bool)  # everywhere else is baseline-fill
        is_base[8:11] = False             # cluster itself is raw
        # Make it not pass isolated-short by making n > 3
        y[7:12] = 140.0
        is_base[7:12] = False
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # Should be one cluster spanning 7..11, all baseline-fill around
        assert len(clusters) == 1
        assert clusters[0].label.startswith("artifact_narrow")

    def test_artifact_isolated_short(self):
        """Short cluster (n≤3) with no other raw within ±20ms → artifact_isolated_short."""
        n = 30
        y = np.zeros(n)
        y[15] = 140.0   # 1-frame high spike
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.ones(n, dtype=bool)
        is_base[15] = False
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        assert len(clusters) == 1
        assert clusters[0].label.startswith("artifact_isolated_short")

    def test_isolated_short_with_nearby_raw_not_overridden(self):
        """Short cluster with ANOTHER raw cluster within ±20ms → NOT artifact_isolated_short."""
        n = 30
        y = np.zeros(n)
        # Two short clusters 3 frames apart (~12 ms at 250fps, well within ±20ms)
        y[15] = 140.0
        y[18] = 140.0
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.ones(n, dtype=bool)
        is_base[15] = False
        is_base[18] = False
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # Both single-frame clusters are within ±20ms (5 frames) of each
        # other → isolated-short override does NOT fire on either.
        for c in clusters:
            assert "artifact_isolated_short" not in c.label

    def test_artifact_flat(self):
        """Long flat plateau (n≥20, range<3, median>30) → artifact_flat."""
        n = 30
        y = np.full(n, 50.0)  # flat at 50, length 30 (well > 20)
        # tiny noise so range < 3
        y[1::2] += 1.0
        is_intp, is_base = _empty_masks(n)
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        assert len(clusters) == 1
        # Note: cluster_max=51 < 130 so HIGH_THR check is skipped, but
        # the flat belt-and-suspenders catches it regardless.
        assert clusters[0].label.startswith("artifact_flat")


# ===========================================================================
# Step 1b — frame-level y outlier (Decision 12)
# ===========================================================================


class TestFindYFrameOutliers:
    def test_single_frame_jump_detected(self):
        """y=160 spike at end of real descending cluster → flagged (PS54 24L
        ~1224ms pattern)."""
        # Cluster of length 21: rise 0→160, descent 160→0, then spike to 160
        y = np.array(
            [10, 30, 50, 80, 110, 140, 160, 150, 130, 110, 90, 70, 50, 30,
             20, 15, 10, 8, 6, 4, 160],  # last frame is spike
            dtype=float,
        )
        n = len(y)
        is_intp, is_base = _empty_masks(n)
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        assert clusters[0].label.startswith("keep_real")
        seeds = _find_y_frame_outliers(
            y, clusters, n, FPS, params=DEFAULT_PARAMS,
        )
        assert seeds == [20]  # the spike at the last frame

    def test_smooth_cluster_no_outliers(self):
        """Smooth lick rise/peak/fall → no frames flagged."""
        y = np.array(
            [10, 30, 50, 80, 110, 140, 160, 150, 130, 110, 90, 70, 50, 30, 10],
            dtype=float,
        )
        n = len(y)
        is_intp, is_base = _empty_masks(n)
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        seeds = _find_y_frame_outliers(
            y, clusters, n, FPS, params=DEFAULT_PARAMS,
        )
        assert seeds == []

    def test_artifact_cluster_skipped(self):
        """Artifact-labeled clusters skip the frame check."""
        n = 30
        y = np.zeros(n)
        y[15] = 140.0
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.ones(n, dtype=bool)
        is_base[15] = False
        clusters = _classify_raw_clusters(
            y, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # This is artifact_isolated_short. Frame check should skip it.
        seeds = _find_y_frame_outliers(
            y, clusters, n, FPS, params=DEFAULT_PARAMS,
        )
        assert seeds == []


# ===========================================================================
# Step 1d — PCHIP-extend helper (Decision 13)
# ===========================================================================


class TestExtendPchipAroundRange:
    def test_extends_into_intp_neighbors(self):
        """Walks left + right into is_intp frames, stops at non-intp."""
        n = 20
        y_clean = np.arange(n, dtype=float)
        is_base_clean = np.zeros(n, dtype=bool)
        is_intp = np.zeros(n, dtype=bool)
        is_intp[5:8] = True   # is_intp frames to the LEFT of seed at 10
        is_intp[11:14] = True # is_intp frames to the RIGHT of seed at 10
        # frames 8,9 and 14,15 are raw (~is_intp & ~is_base) — should stop extend
        n_ext = _extend_pchip_around_range(
            lo=10, hi=10, y_clean=y_clean, is_base_clean=is_base_clean,
            is_interp_fill=is_intp, n_frames=n, pchip_extend=10,
        )
        # Extended left: starts at 9 (not is_intp, stops); 0 frames left
        # Extended right: starts at 11, 12, 13 are is_intp (3 frames), 14 is not
        assert n_ext == 3
        assert (y_clean[11:14] == 0.0).all()
        assert is_base_clean[11:14].all()
        # Frame 9 untouched (not is_intp)
        assert y_clean[9] == 9.0
        assert not is_base_clean[9]

    def test_respects_max_extend(self):
        """Won't extend past pchip_extend frames per side."""
        n = 30
        y_clean = np.arange(n, dtype=float)
        is_base_clean = np.zeros(n, dtype=bool)
        is_intp = np.ones(n, dtype=bool)  # everything is is_intp
        n_ext = _extend_pchip_around_range(
            lo=15, hi=15, y_clean=y_clean, is_base_clean=is_base_clean,
            is_interp_fill=is_intp, n_frames=n, pchip_extend=3,
        )
        # 3 frames left (14,13,12) + 3 right (16,17,18) = 6 total
        assert n_ext == 6
        assert (y_clean[12:15] == 0.0).all()
        assert (y_clean[16:19] == 0.0).all()

    def test_stops_at_already_wiped(self):
        """Won't double-wipe frames already in is_base_clean."""
        n = 20
        y_clean = np.ones(n, dtype=float)
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_clean[7] = True  # already wiped
        is_intp = np.zeros(n, dtype=bool)
        is_intp[5:7] = True
        n_ext = _extend_pchip_around_range(
            lo=10, hi=10, y_clean=y_clean, is_base_clean=is_base_clean,
            is_interp_fill=is_intp, n_frames=n, pchip_extend=10,
        )
        # Right walk from 11: not is_intp, stops immediately (0 right)
        # Left walk from 9: not is_intp, stops immediately (0 left)
        assert n_ext == 0


# ===========================================================================
# Step 1e — bracketed-interp wipe
# ===========================================================================


class TestWipeBracketedInterp:
    def test_bracketed_interp_wiped(self):
        """is_intp run with wiped/baseline-fill on BOTH sides → wiped."""
        n = 10
        y_clean = np.ones(n, dtype=float) * 50
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_clean[:3] = True   # left baseline
        is_base_clean[7:] = True   # right baseline
        is_intp = np.zeros(n, dtype=bool)
        is_intp[3:7] = True        # is_intp run bracketed
        n_wiped = _wipe_bracketed_interp(
            y_clean, is_intp, is_base_clean, n,
        )
        assert n_wiped == 4
        assert (y_clean[3:7] == 0.0).all()
        assert is_base_clean[3:7].all()

    def test_unbracketed_kept(self):
        """is_intp run with raw neighbor on one side → NOT wiped."""
        n = 10
        y_clean = np.ones(n, dtype=float) * 50
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_clean[:3] = True
        is_intp = np.zeros(n, dtype=bool)
        is_intp[3:7] = True
        # Frame 7+ is RAW (not is_intp, not is_base_clean) → right side
        # not wiped → don't wipe the interp run
        n_wiped = _wipe_bracketed_interp(
            y_clean, is_intp, is_base_clean, n,
        )
        assert n_wiped == 0
        assert (y_clean[3:7] == 50.0).all()


# ===========================================================================
# Addendum #1 Rule 1 — x0 baseline-fill derivation
# ===========================================================================


class TestDeriveX0BaselineFill:
    def test_median_of_baseline_fill(self):
        x = np.array([10, 20, 30, 40, 50], dtype=float)
        is_base = np.array([True, True, False, True, True], dtype=bool)
        # median of x[is_base] = median([10, 20, 40, 50]) = 30
        assert _derive_x0_baseline_fill(x, is_base) == 30.0

    def test_zero_when_no_baseline(self):
        x = np.array([10, 20, 30], dtype=float)
        is_base = np.zeros(3, dtype=bool)
        assert _derive_x0_baseline_fill(x, is_base) == 0.0

    def test_zero_when_all_nan(self):
        x = np.array([np.nan, np.nan, np.nan], dtype=float)
        is_base = np.ones(3, dtype=bool)
        assert _derive_x0_baseline_fill(x, is_base) == 0.0


# ===========================================================================
# Addendum #1 Rule 4 — direction-aware nearest-raw-flank jump detector
# ===========================================================================


class TestFindXIsolatedJumps:
    def test_ps54_51l_pattern_flagged(self):
        """Burst x=0 at peak frame, flanks +40 — direction TOWARD x0=0 → flag."""
        n = 11
        x = np.full(n, 40.0)
        x[5] = 0.0  # burst — closer to x0=0 than flanks
        is_intp = np.zeros(n, dtype=bool)
        is_intp[4] = True
        is_intp[6] = True  # immediate neighbors are PCHIP-fill (matches 51L)
        is_base = np.zeros(n, dtype=bool)
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert flag[5] == True   # the burst flagged
        assert flag.sum() == 1   # only the burst

    def test_ps54_76l_pattern_not_flagged(self):
        """Real lick protrusion: burst x=+90, flanks +50, x0=0.
        Burst FURTHER from x0 than flanks → real protrusion → NOT flagged."""
        n = 11
        x = np.full(n, 50.0)
        x[5] = 90.0  # real lick peak — further from x0
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert not flag.any()

    def test_ps54_24l_1700ms_pattern_not_flagged(self):
        """Peak frame +95 amid neighboring +90 peaks — deviation only 5 < 30 → NOT flagged."""
        n = 11
        x = np.full(n, 90.0)
        x[5] = 95.0  # small deviation
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert not flag.any()

    def test_wide_trough_not_flagged(self):
        """Wide trough — flanks at similar low x → flank deviation insufficient."""
        n = 15
        x = np.array(
            [60, 50, 40, 30, 20, 10, 10, 10, 10, 10, 20, 30, 40, 50, 60],
            dtype=float,
        )
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert not flag.any()  # smooth descent + plateau — no isolated jumps

    def test_smooth_motion_not_flagged(self):
        """Smooth rise / fall — adjacent frames change gradually, no jumps."""
        x = np.linspace(0, 100, 15)
        n = len(x)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert not flag.any()

    def test_skips_baseline_fill_frames(self):
        """is_baseline_fill_clean=True frames are not flagged regardless."""
        n = 11
        x = np.full(n, 40.0)
        x[5] = 0.0
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        is_base[5] = True   # the burst frame is already baseline-fill
        flag = _find_x_isolated_jumps(
            x, is_intp, is_base, n, x0=0.0, params=DEFAULT_PARAMS,
        )
        assert not flag.any()


# ===========================================================================
# Addendum #1 Rules 1-4 orchestration via _clean_x_trace
# ===========================================================================


class TestCleanXTrace:
    def test_x_hard_outlier_pchip_extended(self):
        """|x|>110 frame wiped + adjacent is_intp PCHIP-extended."""
        n = 20
        x = np.full(n, 50.0)
        x[10] = 200.0  # |x|>110 hard outlier
        is_intp = np.zeros(n, dtype=bool)
        is_intp[8:10] = True   # PCHIP-fill on left of outlier
        is_intp[11:13] = True  # PCHIP-fill on right
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_orig = np.zeros(n, dtype=bool)
        (x_clean, hard, joint, ext, base_aug, x0) = _clean_x_trace(
            x, is_intp, is_base_clean, is_base_orig, n, FPS,
            params=DEFAULT_PARAMS,
        )
        assert hard[10] and hard.sum() == 1
        assert not joint.any()
        # PCHIP-extend: frames 8,9 left + 11,12 right
        assert ext.sum() == 4
        # x_clean at hard outlier should be re-interpolated to ~50
        assert abs(x_clean[10] - 50.0) < 1.0

    def test_x_joint_outlier_pchip_interp_not_x0(self):
        """Joint x+y outlier → x_clean = PCHIP-interp (NOT snapped to x0=0)."""
        n = 11
        x = np.full(n, 40.0)
        x[5] = 0.0  # joint outlier (PS54 51L-like)
        is_intp = np.zeros(n, dtype=bool)
        is_intp[4] = True
        is_intp[6] = True
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_orig = np.zeros(n, dtype=bool)
        (x_clean, hard, joint, ext, base_aug, x0) = _clean_x_trace(
            x, is_intp, is_base_clean, is_base_orig, n, FPS,
            params=DEFAULT_PARAMS,
        )
        assert x0 == 0.0
        assert joint[5] and joint.sum() == 1
        # PCHIP through flank +40 anchors → x_clean[5] ≈ +40, NOT 0
        assert abs(x_clean[5] - 40.0) < 1.0
        # is_base_clean_augmented marks the joint frame for y-side wipe
        assert base_aug[5]

    def test_x_at_y_wiped_frames_snaps_to_x0(self):
        """Rule 1: at y-side base_clean frames, x = x0 (NOT PCHIP-interp)."""
        n = 10
        x = np.array([5, 5, 5, 5, -95, -95, 5, 5, 5, 5], dtype=float)
        is_intp = np.zeros(n, dtype=bool)
        is_base_orig = np.array(
            [True, True, True, True, False, False, True, True, True, True],
            dtype=bool,
        )
        # Y-side pre-clean wiped frames 4,5 (artifact cluster):
        is_base_clean = is_base_orig.copy()
        is_base_clean[4:6] = True
        (x_clean, hard, joint, ext, base_aug, x0) = _clean_x_trace(
            x, is_intp, is_base_clean, is_base_orig, n, FPS,
            params=DEFAULT_PARAMS,
        )
        # x0 = median(x[is_base_orig]) = median([5,5,5,5,5,5,5,5]) = 5.0
        assert x0 == 5.0
        # Y-wiped frames 4,5 snap to x0=5, not preserve raw -95
        assert x_clean[4] == 5.0
        assert x_clean[5] == 5.0

    def test_rule_2_y_wiped_dropped_from_anchors(self):
        """Y-wiped frame is excluded from x's PCHIP anchor set.

        PS54 46L-like: outlier (y=211, x=-42) gets y-side wiped. Surrounding
        x at +50-60 should be the only anchors for x at nearby is_intp frames.
        """
        n = 12
        x = np.array(
            [50, 50, 55, 60, -42, 60, 55, 50, 55, 55, 50, 50],
            dtype=float,
        )
        is_intp = np.zeros(n, dtype=bool)
        is_intp[3] = True   # frame 3 is PCHIP-interp
        is_intp[5] = True   # frame 5 is PCHIP-interp
        # Y-side wiped frame 4 (the outlier):
        is_base_clean = np.zeros(n, dtype=bool)
        is_base_clean[4] = True
        is_base_orig = np.zeros(n, dtype=bool)
        (x_clean, hard, joint, ext, base_aug, x0) = _clean_x_trace(
            x, is_intp, is_base_clean, is_base_orig, n, FPS,
            params=DEFAULT_PARAMS,
        )
        # Frame 4 (y-wiped) → x_clean = x0 = 0 (no original baseline-fill
        # frames exist in this test, so x0 fallback to 0)
        assert x_clean[4] == 0.0
        # Frame 3 and 5 (is_intp) get re-interpolated through anchors at
        # frames 0,1,2,6,7,8,9,10,11 (all ~50-60). Frame 4 is EXCLUDED
        # from the anchor set per Rule 2 → x_clean[3], x_clean[5] ≈ 55
        # NOT pulled toward the -42 outlier.
        assert 45 <= x_clean[3] <= 65
        assert 45 <= x_clean[5] <= 65


# ===========================================================================
# Public entry — preclean_trace orchestration
# ===========================================================================


class TestPrecleanTrace:
    def test_clean_trace_no_artifacts(self):
        """All-raw, no artifacts → cleaned trace matches input."""
        n = 20
        y = np.array(
            [10, 30, 50, 80, 110, 140, 160, 150, 130, 110,
             80, 50, 30, 10, 10, 10, 10, 10, 10, 10],
            dtype=float,
        )
        x = np.full(n, 50.0)
        is_intp, is_base = _empty_masks(n)
        y_clean, x_clean, is_base_clean, diag = preclean_trace(
            y, x, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        np.testing.assert_array_equal(y_clean, y)
        # x_clean: raw frames preserve raw value; no is_intp frames so no
        # PCHIP-interp; no joint/hard outliers
        np.testing.assert_array_equal(x_clean, x)
        assert not is_base_clean.any()
        assert diag.n_artifact_clusters == 0
        assert diag.n_x_joint_outliers == 0

    def test_isolated_short_artifact_wiped(self):
        """Isolated 1-frame high spike → wiped to baseline."""
        n = 30
        y = np.zeros(n)
        y[15] = 140.0
        x = np.zeros(n)
        x[15] = 50.0  # x value at the artifact frame
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.ones(n, dtype=bool)
        is_base[15] = False
        y_clean, x_clean, is_base_clean, diag = preclean_trace(
            y, x, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # Cluster wiped (y=0, is_base=True at frame 15)
        assert y_clean[15] == 0.0
        assert is_base_clean[15]
        assert diag.n_artifact_frames == 1
        # x at wiped frame snaps to x0=0 (Rule 1)
        assert x_clean[15] == 0.0

    def test_joint_outlier_wipes_both_y_and_x(self):
        """Joint x+y outlier (Rule 4) wipes y=0 AND x→PCHIP-interp."""
        n = 11
        # Build a synthetic 51L-pattern within a real lick cluster
        y = np.array([20, 50, 80, 110, 130, 130, 130, 110, 80, 50, 20], dtype=float)
        x = np.full(n, 40.0)
        x[5] = 0.0  # joint outlier at the peak
        is_intp = np.zeros(n, dtype=bool)
        is_intp[4] = True
        is_intp[6] = True
        is_base = np.zeros(n, dtype=bool)
        y_clean, x_clean, is_base_clean, diag = preclean_trace(
            y, x, is_intp, is_base, n, FPS, params=DEFAULT_PARAMS,
        )
        # Joint outlier flagged
        assert diag.n_x_joint_outliers == 1
        # Production-only addition per Addendum: y=0 + is_base=True at joint frame
        assert y_clean[5] == 0.0
        assert is_base_clean[5]
        # x_clean PCHIP-interp through flanks ≈ +40 (NOT snapped to x0=0)
        assert abs(x_clean[5] - 40.0) < 1.0
