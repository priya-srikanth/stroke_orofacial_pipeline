"""Tests for stroke_orofacial.dlc_kinematics._gates.

Covers Phase 7e Task 4 deliverable: synthetic-trace tests for each gate
(F/D/E + parabolic/spline imputation + run_m_gate with Addendum #1
Rule 5 early-window relaxation).

Parity vs the v7 scratch reference on real trial data lives in
``test_v7_parity.py`` (Phase 7e Task 8).
"""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.dlc_kinematics._gates import (
    LickEventRecord,
    gate_D,
    gate_E,
    gate_F,
    parabolic_excise,
    run_m_gate,
    spline_excise,
)

FPS = 250.0

GATES_PARAMS: dict = {
    "f_wp_win_ms": 20.0,
    "f_wp_std_thr": 1.0,
    "f_k_min_raw": 3,
    "d_win_ms": 150.0,
    "d_y_thr_px": 130.0,
    "e_z_thr": 3.0,
    "e_lik_override": 0.85,
    "e_k_min_peers": 4,
    "parabolic_tight_radius_ms": 60.0,
    "parabolic_min_anchors": 5,
    "spline_excise_radius_ms": 8.0,
    "spline_anchor_win_ms": 160.0,
    "spline_local_max_win_ms": 20.0,
    "spline_min_anchors": 4,
    "x_outlier_excise_ms": 8.0,    # Task 5b — x-side outlier-window excision width
    "m_min_interval_ms": 80.0,
    "m_conf_radius_ms": 20.0,
    "m_early_interval_ms": 60.0,
    "m_early_win_ms": 250.0,
}


# ===========================================================================
# gate_F — within-peak raw std
# ===========================================================================


class TestGateF:
    def test_plateau_peak_rejected(self):
        """Flat raw-y region around peak → std < 1.0 → reject."""
        n = 50
        y = np.full(n, 100.0)  # perfectly flat → std=0
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        reject, reason, std_raw = gate_F(
            y, is_intp, is_base, peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert reject is True
        assert reason.startswith("F_raw_flat")
        assert std_raw == 0.0

    def test_real_peak_kept(self):
        """Raw rise/peak/fall with std > 1.0 → keep."""
        n = 50
        y = np.array([0, 20, 50, 80, 110, 140, 150, 140, 110, 80,
                      50, 20, 0, 0, 0, 0, 0, 0, 0, 0] + [0] * 30, dtype=float)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        reject, reason, std_raw = gate_F(
            y, is_intp, is_base, peak_frame=6, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert reject is False
        assert std_raw > 1.0

    def test_too_few_raw_rejected(self):
        """Fewer than f_k_min_raw=3 raw frames in window → reject."""
        n = 50
        y = np.full(n, 100.0)
        is_intp = np.ones(n, dtype=bool)  # all PCHIP-fill → 0 raw
        is_base = np.zeros(n, dtype=bool)
        reject, reason, std_raw = gate_F(
            y, is_intp, is_base, peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert reject is True
        assert reason.startswith("F_too_few_raw")
        assert np.isnan(std_raw)


# ===========================================================================
# gate_D — left/right low context
# ===========================================================================


class TestGateD:
    def test_both_sides_with_low_raw_kept(self):
        """Both sides have raw y < 130 → keep."""
        n = 100
        y = np.zeros(n, dtype=float)
        y[40:50] = 50    # low raw on left
        y[50] = 140      # peak
        y[51:60] = 50    # low raw on right
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        keep, reason = gate_D(
            y, is_intp, is_base, peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert keep is True

    def test_no_left_context_rejected(self):
        """Left side has only HIGH raw y → reject with D_left."""
        n = 100
        y = np.full(n, 150.0)  # everything high → no low raw anywhere
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        # peak at 50; right side is also all high. Left fails first.
        keep, reason = gate_D(
            y, is_intp, is_base, peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert keep is False
        assert reason == "D_left"

    def test_baseline_fill_satisfies_context(self):
        """Baseline-fill on one side satisfies the context requirement."""
        n = 100
        y = np.full(n, 150.0)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        is_base[:30] = True   # left side has baseline-fill
        # Right side still missing context; should reject with D_right
        keep, reason = gate_D(
            y, is_intp, is_base, peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert keep is False
        assert reason == "D_right"

        # Add right-side context
        is_base[60:] = True
        keep, reason = gate_D(
            y, is_intp, is_base, peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert keep is True


# ===========================================================================
# gate_E — outlier z-vs-peers + likelihood escape
# ===========================================================================


class TestGateE:
    def test_outlier_above_z_thresh_rejected(self):
        """Candidate >> peer median + low likelihood → reject."""
        peers = [100.0, 105.0, 95.0, 102.0, 98.0]   # stable around 100
        reject, reason, z, median = gate_E(
            candidate_y=200.0, candidate_lik=0.5,
            peer_ys=peers, params=GATES_PARAMS,
        )
        assert reject is True
        assert reason.startswith("E_outlier")
        assert z > 3.0

    def test_high_likelihood_escapes_rejection(self):
        """Candidate is an outlier BUT high likelihood → keep (escape hatch)."""
        peers = [100.0, 105.0, 95.0, 102.0, 98.0]
        reject, reason, z, median = gate_E(
            candidate_y=200.0, candidate_lik=0.95,
            peer_ys=peers, params=GATES_PARAMS,
        )
        assert reject is False
        assert reason == ""

    def test_few_peers_abstain(self):
        """Fewer than e_k_min_peers finite peers → abstain (not reject)."""
        peers = [100.0, 105.0]  # only 2 < e_k_min_peers=4
        reject, reason, z, median = gate_E(
            candidate_y=200.0, candidate_lik=0.5,
            peer_ys=peers, params=GATES_PARAMS,
        )
        assert reject is False
        assert reason == "abstain_few_peers"

    def test_stationary_peers_abstain(self):
        """Peer MAD too small → robust_std < 0.5 → abstain."""
        peers = [100.0, 100.0, 100.0, 100.0, 100.0]  # zero MAD
        reject, reason, z, median = gate_E(
            candidate_y=200.0, candidate_lik=0.5,
            peer_ys=peers, params=GATES_PARAMS,
        )
        assert reject is False
        assert reason == "abstain_stationary"

    def test_candidate_close_to_peers_kept(self):
        """Candidate near peer median → z below threshold → keep."""
        peers = [100.0, 105.0, 95.0, 102.0, 98.0]
        reject, reason, z, median = gate_E(
            candidate_y=103.0, candidate_lik=0.5,
            peer_ys=peers, params=GATES_PARAMS,
        )
        assert reject is False
        # z = (103 - 100) / (1.4826 * MAD=2) ≈ 1.0; well below e_z_thr=3
        assert abs(z) < 3.0


# ===========================================================================
# parabolic_excise — quadratic-fit imputation
# ===========================================================================


class TestParabolicExcise:
    def test_concave_down_returns_vertex(self):
        """Smooth concave-down parabola → vertex returned + new_peak_x."""
        n = 50
        # y = -2*(x-25)^2 + 200  has vertex at x=25, y=200
        x_arr = np.arange(n, dtype=float)
        y = -2.0 * (x_arr - 25.0) ** 2 + 200.0
        x = np.full(n, 50.0)  # flat x for the smooth case
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        # outlier_peak_frame at 25 (the true vertex); the excise window
        # near it doesn't really matter — surrounding anchors fit cleanly
        result = parabolic_excise(
            y, x, is_intp, is_base, outlier_peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is not None
        assert result["method"] == "parabolic"
        # Vertex of the true parabola at frame 25, y=200
        assert result["new_peak_frame"] == 25
        assert result["new_peak_y"] == pytest.approx(200.0, abs=1.0)
        # Task 5b: new_peak_x via wide-anchor PCHIP excluding outlier window.
        # Since x is flat at 50, the result should be ~50.
        assert result["new_peak_x"] == pytest.approx(50.0, abs=1.0)

    def test_concave_up_returns_none(self):
        """Concave-up data (no peak shape) → returns None."""
        n = 50
        x_arr = np.arange(n, dtype=float)
        y = 2.0 * (x_arr - 25.0) ** 2 + 10.0  # concave UP (valley not peak)
        x = np.full(n, 50.0)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        result = parabolic_excise(
            y, x, is_intp, is_base, outlier_peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is None

    def test_too_few_anchors_returns_none(self):
        """When the anchor window has < parabolic_min_anchors raw frames → None."""
        n = 50
        y = np.full(n, 100.0)
        x = np.full(n, 50.0)
        is_intp = np.ones(n, dtype=bool)   # everything is PCHIP-fill
        is_base = np.zeros(n, dtype=bool)
        result = parabolic_excise(
            y, x, is_intp, is_base, outlier_peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is None

    def test_new_peak_x_excludes_outlier_window(self):
        """Task 5b: x at outlier frame is anomalous; new_peak_x should
        IGNORE it and use wide flank values via PCHIP. Mirrors PS54
        46L pattern at synthetic scale."""
        n = 100
        # Smooth concave-down y centered at frame 50
        x_arr = np.arange(n, dtype=float)
        y = -2.0 * (x_arr - 50.0) ** 2 + 200.0
        # x is flat at +50 everywhere EXCEPT the outlier window (±2 frames
        # around frame 50 — within x_outlier_excise_ms=8ms = ±2 frames)
        x = np.full(n, 50.0)
        x[48:53] = -45.0   # outlier value at and around frame 50
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        result = parabolic_excise(
            y, x, is_intp, is_base, outlier_peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is not None
        # new_peak_x should ignore the outlier-window values and produce
        # ~+50 from the flanking anchors. Without the excise, it would be
        # pulled toward -45.
        assert result["new_peak_x"] == pytest.approx(50.0, abs=2.0)


# ===========================================================================
# spline_excise — PCHIP-fit fallback
# ===========================================================================


class TestSplineExcise:
    def test_smooth_peak_returns_max(self):
        """Smooth Gaussian-ish peak → spline finds max near outlier frame."""
        n = 100
        x_arr = np.arange(n, dtype=float)
        y = 150.0 * np.exp(-((x_arr - 50.0) ** 2) / (2 * 8.0 ** 2))
        x = np.full(n, 50.0)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        result = spline_excise(
            y, x, is_intp, is_base, outlier_peak_frame=50, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is not None
        # new_peak_frame should be near 50 (within the local-max search window)
        assert 45 <= result["new_peak_frame"] <= 55
        # PCHIP excludes ±8ms (= ±2 frames) around the outlier, so the
        # peak frame itself is NOT in the anchor set. PCHIP through the
        # surrounding anchors slightly under-estimates the true Gaussian
        # peak (~140 instead of 150 — ~7% under). Tolerance reflects this
        # excise-window-induced undershoot.
        assert result["new_peak_y"] == pytest.approx(150.0, abs=15.0)
        # Task 5b: new_peak_x via wide-anchor PCHIP. Flat x → ~50.
        assert result["new_peak_x"] == pytest.approx(50.0, abs=1.0)

    def test_too_few_anchors_returns_none(self):
        """Anchor window with < spline_min_anchors raw frames → None."""
        n = 50
        y = np.full(n, 100.0)
        x = np.full(n, 50.0)
        is_intp = np.ones(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        result = spline_excise(
            y, x, is_intp, is_base, outlier_peak_frame=25, n_frames=n, fps=FPS,
            params=GATES_PARAMS,
        )
        assert result is None


# ===========================================================================
# run_m_gate — confidence-based inter-lick + Addendum #1 Rule 5
# ===========================================================================


def _make_decision(t_ms: float, y: float, peak_frame: int, keep: bool = True) -> dict:
    """Helper: build a decisions-list entry matching scratch shape."""
    return {
        "t_ms": t_ms, "y": y,
        "peak_frame_local": peak_frame,
        "keep": keep,
    }


class TestRunMGate:
    def test_far_apart_peaks_both_kept(self):
        """Peaks > 80 ms apart → both kept."""
        n = 1000
        decisions = [
            _make_decision(t_ms=500.0, y=140.0, peak_frame=125),
            _make_decision(t_ms=700.0, y=150.0, peak_frame=175),
        ]
        likelihood = np.full(n, 0.9)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        promoted = decisions[0]
        new_promoted = run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        assert all(d["keep"] for d in decisions)
        assert new_promoted is promoted

    def test_close_pair_outside_early_window_drops_lower_confidence(self):
        """Peaks 50 ms apart, both well past 250 ms → 80 ms threshold fires
        → lower confidence dropped."""
        n = 1000
        # Peak 1 at 500 ms (frame 125), Peak 2 at 550 ms (frame 138)
        decisions = [
            _make_decision(t_ms=500.0, y=140.0, peak_frame=125),
            _make_decision(t_ms=550.0, y=150.0, peak_frame=138),
        ]
        likelihood = np.full(n, 0.9)
        # Make peak 1 have HIGHER confidence (more raw frames around it)
        is_intp = np.ones(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        is_intp[120:130] = False  # raw around peak 1
        # peak 2 has all-intp around it → confidence ≈ 0
        is_intp[135:141] = True  # confirm
        promoted = decisions[0]
        run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        # Peak 1 (higher confidence) kept; peak 2 dropped
        assert decisions[0]["keep"] is True
        assert decisions[1]["keep"] is False
        assert decisions[1]["gate"] == "M"
        assert "thr=80" in decisions[1]["reason"]

    def test_early_window_relaxation_keeps_60ms_pair(self):
        """Two peaks 60 ms apart inside first 250 ms → relaxed threshold
        (60) fires (interval >= 60, not <60), both kept."""
        n = 1000
        # Peak 1 at 100 ms, Peak 2 at 160 ms (60 ms apart, both < 250 ms)
        decisions = [
            _make_decision(t_ms=100.0, y=140.0, peak_frame=25),
            _make_decision(t_ms=160.0, y=150.0, peak_frame=40),
        ]
        likelihood = np.full(n, 0.9)
        is_intp = np.zeros(n, dtype=bool)
        is_base = np.zeros(n, dtype=bool)
        promoted = decisions[0]
        run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        # interval (60 ms) >= relaxed threshold (60 ms) → kept
        # Note: the check is "< threshold" (strict) so 60 ms passes
        assert all(d["keep"] for d in decisions)

    def test_early_window_50ms_pair_still_dropped(self):
        """Two peaks 50 ms apart inside first 250 ms → still violates
        the relaxed 60 ms threshold → lower-confidence dropped."""
        n = 1000
        decisions = [
            _make_decision(t_ms=100.0, y=140.0, peak_frame=25),
            _make_decision(t_ms=150.0, y=150.0, peak_frame=38),  # 50 ms after
        ]
        likelihood = np.full(n, 0.9)
        is_intp = np.ones(n, dtype=bool)
        is_intp[20:30] = False  # peak 1 has more raw frames → higher conf
        is_base = np.zeros(n, dtype=bool)
        promoted = decisions[0]
        run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        # 50 ms < 60 ms relaxed threshold → conflict; lower-conf dropped
        assert decisions[0]["keep"] is True
        assert decisions[1]["keep"] is False
        assert "thr=60" in decisions[1]["reason"]   # early-window threshold used

    def test_outside_early_window_uses_80ms(self):
        """Two peaks 60 ms apart with one >= 250 ms → 80 ms threshold
        fires → conflict (60 < 80) → lower-conf dropped."""
        n = 1000
        decisions = [
            _make_decision(t_ms=240.0, y=140.0, peak_frame=60),
            _make_decision(t_ms=300.0, y=150.0, peak_frame=75),  # 60 ms after, >= 250
        ]
        likelihood = np.full(n, 0.9)
        is_intp = np.ones(n, dtype=bool)
        is_intp[55:65] = False  # peak 1 higher conf
        is_base = np.zeros(n, dtype=bool)
        promoted = decisions[0]
        run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        # 60 ms < 80 ms threshold (because peak 2 is OUTSIDE early window)
        # → conflict
        assert decisions[1]["keep"] is False
        assert "thr=80" in decisions[1]["reason"]

    def test_promoted_re_promoted_when_dropped(self):
        """If the dropped peak was promoted, run_m_gate re-promotes
        the highest-conf survivor."""
        n = 1000
        # Peak 1 (promoted) at 500 ms, Peak 2 at 550 ms with HIGHER conf
        decisions = [
            _make_decision(t_ms=500.0, y=140.0, peak_frame=125),
            _make_decision(t_ms=550.0, y=150.0, peak_frame=138),
        ]
        likelihood = np.full(n, 0.9)
        # Peak 2 has more raw frames → higher conf → peak 1 dropped
        is_intp = np.ones(n, dtype=bool)
        is_intp[133:144] = False  # raw around peak 2
        is_base = np.zeros(n, dtype=bool)
        promoted = decisions[0]  # initially peak 1 is promoted
        new_promoted = run_m_gate(
            decisions, np.zeros(n), likelihood, is_intp, is_base,
            n_frames=n, fps=FPS, promoted=promoted, params=GATES_PARAMS,
        )
        # Peak 1 dropped; promoted re-set to peak 2 (the survivor)
        assert decisions[0]["keep"] is False
        assert decisions[1]["keep"] is True
        assert new_promoted is decisions[1]


# ===========================================================================
# LickEventRecord schema (covered in test_preclean.py but verify shape here too)
# ===========================================================================


class TestLickEventRecord:
    def test_dataclass_construction(self):
        rec = LickEventRecord(
            animal="PS54", date="2025-06-13", trial=51, side="L",
            lick_idx=0, t_ms=860.0, y=129.4, x=39.31, y_original=float("nan"),
            rise_start_ms=844.0, fall_end_ms=876.0, imputed=False,
            source="lmax", confidence=5.5, likelihood=0.78,
        )
        assert rec.animal == "PS54"
        assert rec.t_ms == 860.0
        assert rec.imputed is False
        assert np.isnan(rec.y_original)
        assert rec.source == "lmax"
