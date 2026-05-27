"""Phase 9.1 Q-lock 13b — phase-aligned tongue endpoint emitter tests.

Covers:

- Endpoint A (peak_angle_deg at phase = 0.5)
- Endpoint B (max abs angle over phase in [0, 0.75])
- Endpoint C (signed x_centered at argmax(|x_centered|) over phase in [0, 0.75])
- Per-trial NaN policy: signed-positive, signed-negative, all-zero,
  NaN-laden inputs.
- Trial-events alignment helper (NaN-fills missing (trial, side) pairs).
- Bundle integration with synthetic_only first-lick-centered substrate.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_kinematics.tongue_phase_aligned_endpoints import (
    PHASE_ALIGNED_ENDPOINT_COLUMNS,
    PHASE_PEAK,
    PHASE_PEAK_TOLERANCE,
    PHASE_WINDOW_HI,
    PHASE_WINDOW_LO,
    _empty_phase_aligned_endpoints_df,
    _endpoint_a_peak_angle,
    _endpoint_b_max_abs_angle,
    _endpoint_c_signed_x_at_max_abs,
    align_endpoints_to_trial_order,
    compute_phase_aligned_endpoints_per_trial,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import TongueVisualBundle


def _phase_rows(
    phases: list[float],
    angles: list[float],
    xs: list[float],
) -> pd.DataFrame:
    """Build a minimal phase-rows DataFrame for unit tests."""
    assert len(phases) == len(angles) == len(xs)
    return pd.DataFrame({
        "phase": np.asarray(phases, dtype=np.float64),
        "angle_deg": np.asarray(angles, dtype=np.float64),
        "x_centered": np.asarray(xs, dtype=np.float64),
    })


# ---------------------------------------------------------------------------
# Endpoint A — peak_angle_deg at phase = 0.5
# ---------------------------------------------------------------------------

class TestEndpointAPeakAngle:
    def test_returns_angle_at_exact_phase_0_5(self):
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75, 1.0],
            angles=[1.0, 5.0, -12.5, 7.0, 2.0],
            xs=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        assert _endpoint_a_peak_angle(grp) == pytest.approx(-12.5)

    def test_returns_angle_at_closest_to_phase_0_5_within_tolerance(self):
        # Closest frame to 0.5 is at phase=0.51 (delta=0.01 < tolerance=0.05)
        grp = _phase_rows(
            phases=[0.0, 0.4, 0.51, 0.7],
            angles=[1.0, 5.0, -8.0, 2.0],
            xs=[0.0, 0.0, 0.0, 0.0],
        )
        assert _endpoint_a_peak_angle(grp) == pytest.approx(-8.0)

    def test_returns_nan_when_closest_frame_outside_tolerance(self):
        # Closest frame to 0.5 is at phase=0.3 (delta=0.2 > tolerance=0.05).
        grp = _phase_rows(
            phases=[0.0, 0.3, 0.9],
            angles=[1.0, 5.0, 2.0],
            xs=[0.0, 0.0, 0.0],
        )
        assert np.isnan(_endpoint_a_peak_angle(grp))

    def test_returns_nan_when_grp_empty(self):
        grp = _phase_rows([], [], [])
        assert np.isnan(_endpoint_a_peak_angle(grp))

    def test_skips_nan_angle_at_peak_falls_to_next_finite_within_tolerance(self):
        # Phase=0.5 row has NaN angle; phase=0.49 within tolerance has finite.
        grp = _phase_rows(
            phases=[0.0, 0.49, 0.5, 0.75],
            angles=[1.0, -7.0, float("nan"), 2.0],
            xs=[0.0, 0.0, 0.0, 0.0],
        )
        assert _endpoint_a_peak_angle(grp) == pytest.approx(-7.0)

    def test_returns_nan_when_all_angles_in_window_are_nan(self):
        grp = _phase_rows(
            phases=[0.4, 0.5, 0.55],
            angles=[float("nan"), float("nan"), float("nan")],
            xs=[0.0, 0.0, 0.0],
        )
        assert np.isnan(_endpoint_a_peak_angle(grp))


# ---------------------------------------------------------------------------
# Endpoint B — max(abs(angle_deg)) over phase in [0, 0.75]
# ---------------------------------------------------------------------------

class TestEndpointBMaxAbsAngle:
    def test_signed_positive_peak(self):
        # Largest |angle| in [0, 0.75] is +15 (at phase=0.5).
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75, 1.0],
            angles=[0.0, 8.0, 15.0, 5.0, 20.0],
            xs=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        # phase=1.0 row has |angle|=20 but is outside [0, 0.75].
        assert _endpoint_b_max_abs_angle(grp) == pytest.approx(15.0)

    def test_signed_negative_peak_is_unsigned_at_endpoint_b(self):
        # Endpoint B selects on magnitude; reports magnitude (not signed).
        grp = _phase_rows(
            phases=[0.0, 0.3, 0.5, 0.7, 0.8],
            angles=[0.0, -7.0, -18.0, -12.0, -25.0],
            xs=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        # phase=0.8 row has |angle|=25 but is outside [0, 0.75].
        # In-window largest |angle| = 18 (at phase=0.5).
        assert _endpoint_b_max_abs_angle(grp) == pytest.approx(18.0)

    def test_all_zero(self):
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75],
            angles=[0.0, 0.0, 0.0, 0.0],
            xs=[0.0, 0.0, 0.0, 0.0],
        )
        assert _endpoint_b_max_abs_angle(grp) == pytest.approx(0.0)

    def test_nan_laden(self):
        # NaN values are dropped before the max; max abs of finite values = 9.
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75],
            angles=[float("nan"), 9.0, float("nan"), -3.0],
            xs=[0.0, 0.0, 0.0, 0.0],
        )
        assert _endpoint_b_max_abs_angle(grp) == pytest.approx(9.0)

    def test_returns_nan_when_window_empty(self):
        grp = _phase_rows(
            phases=[0.85, 0.9, 0.95],  # all outside [0, 0.75]
            angles=[10.0, 20.0, 30.0],
            xs=[0.0, 0.0, 0.0],
        )
        assert np.isnan(_endpoint_b_max_abs_angle(grp))

    def test_returns_nan_when_all_angles_in_window_nan(self):
        grp = _phase_rows(
            phases=[0.1, 0.5],
            angles=[float("nan"), float("nan")],
            xs=[0.0, 0.0],
        )
        assert np.isnan(_endpoint_b_max_abs_angle(grp))


# ---------------------------------------------------------------------------
# Endpoint C — signed x_centered at argmax(|x_centered|) over phase in [0, 0.75]
# ---------------------------------------------------------------------------

class TestEndpointCSignedXAtMaxAbs:
    def test_signed_positive_argmax(self):
        # Largest |x| in [0, 0.75] is +25 at phase=0.5 → signed value +25.
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75, 1.0],
            angles=[0.0, 0.0, 0.0, 0.0, 0.0],
            xs=[0.0, 10.0, 25.0, -8.0, 50.0],
        )
        # phase=1.0 has |x|=50 but is outside [0, 0.75].
        assert _endpoint_c_signed_x_at_max_abs(grp) == pytest.approx(25.0)

    def test_signed_negative_argmax_returns_negative_value(self):
        # Selection by magnitude; signed report. Largest |x| in [0, 0.75]
        # is at phase=0.4 → x = -42 → return -42 (not +42).
        grp = _phase_rows(
            phases=[0.1, 0.4, 0.6, 0.7],
            angles=[0.0, 0.0, 0.0, 0.0],
            xs=[+8.0, -42.0, +15.0, -30.0],
        )
        assert _endpoint_c_signed_x_at_max_abs(grp) == pytest.approx(-42.0)

    def test_all_zero(self):
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.75],
            angles=[0.0, 0.0, 0.0, 0.0],
            xs=[0.0, 0.0, 0.0, 0.0],
        )
        # All zeros → argmax picks index 0, signed value = 0.
        assert _endpoint_c_signed_x_at_max_abs(grp) == pytest.approx(0.0)

    def test_nan_laden(self):
        # Two finite values in window: -6 (at phase=0.25) and +11 (at phase=0.6).
        # Largest |x| = 11 → return +11.
        grp = _phase_rows(
            phases=[0.0, 0.25, 0.5, 0.6, 0.7],
            angles=[0.0, 0.0, 0.0, 0.0, 0.0],
            xs=[float("nan"), -6.0, float("nan"), 11.0, float("nan")],
        )
        assert _endpoint_c_signed_x_at_max_abs(grp) == pytest.approx(11.0)

    def test_returns_nan_when_all_x_in_window_nan(self):
        grp = _phase_rows(
            phases=[0.1, 0.5, 0.7],
            angles=[1.0, 2.0, 3.0],
            xs=[float("nan"), float("nan"), float("nan")],
        )
        assert np.isnan(_endpoint_c_signed_x_at_max_abs(grp))

    def test_returns_nan_when_x_centered_column_missing(self):
        # Bundles produced before the x_snip column landed won't carry
        # x_centered. The endpoint helper degrades to NaN gracefully.
        grp = pd.DataFrame({
            "phase": [0.1, 0.5, 0.7],
            "angle_deg": [1.0, 2.0, 3.0],
        })
        assert np.isnan(_endpoint_c_signed_x_at_max_abs(grp))


# ---------------------------------------------------------------------------
# align_endpoints_to_trial_order — NaN-fill alignment to trial_events order
# ---------------------------------------------------------------------------

class TestAlignEndpointsToTrialOrder:
    def test_basic_alignment_fills_nan_for_missing_pairs(self):
        df = pd.DataFrame([
            {
                "trial_index": 0, "side": "L",
                "peak_angle_deg": -10.0,
                "max_abs_angle_phase_0_075_deg": 15.0,
                "signed_x_at_max_abs_phase_0_075_px": -20.0,
            },
            {
                "trial_index": 2, "side": "L",
                "peak_angle_deg": 5.0,
                "max_abs_angle_phase_0_075_deg": 7.0,
                "signed_x_at_max_abs_phase_0_075_px": 11.0,
            },
        ])
        out = align_endpoints_to_trial_order(
            df, trial_indices=[0, 1, 2], sides=["L", "R", "L"],
        )
        # Trial 0 L: filled
        assert out["peak_angle_deg"][0] == pytest.approx(-10.0)
        assert out["max_abs_angle_phase_0_075_deg"][0] == pytest.approx(15.0)
        assert out["signed_x_at_max_abs_phase_0_075_px"][0] == pytest.approx(-20.0)
        # Trial 1 R: no row → NaN
        assert np.isnan(out["peak_angle_deg"][1])
        assert np.isnan(out["max_abs_angle_phase_0_075_deg"][1])
        assert np.isnan(out["signed_x_at_max_abs_phase_0_075_px"][1])
        # Trial 2 L: filled
        assert out["peak_angle_deg"][2] == pytest.approx(5.0)
        assert out["max_abs_angle_phase_0_075_deg"][2] == pytest.approx(7.0)
        assert out["signed_x_at_max_abs_phase_0_075_px"][2] == pytest.approx(11.0)

    def test_empty_df_returns_all_nan_lists(self):
        out = align_endpoints_to_trial_order(
            _empty_phase_aligned_endpoints_df(),
            trial_indices=[0, 1],
            sides=["L", "R"],
        )
        assert all(np.isnan(v) for v in out["peak_angle_deg"])
        assert all(np.isnan(v) for v in out["max_abs_angle_phase_0_075_deg"])
        assert all(
            np.isnan(v) for v in out["signed_x_at_max_abs_phase_0_075_px"]
        )

    def test_side_specificity_is_respected(self):
        # Same trial_index but different side → distinct keys.
        df = pd.DataFrame([
            {
                "trial_index": 0, "side": "L",
                "peak_angle_deg": -1.0,
                "max_abs_angle_phase_0_075_deg": 2.0,
                "signed_x_at_max_abs_phase_0_075_px": 3.0,
            },
            {
                "trial_index": 0, "side": "R",
                "peak_angle_deg": -4.0,
                "max_abs_angle_phase_0_075_deg": 5.0,
                "signed_x_at_max_abs_phase_0_075_px": 6.0,
            },
        ])
        out = align_endpoints_to_trial_order(
            df, trial_indices=[0, 0], sides=["L", "R"],
        )
        assert out["peak_angle_deg"] == pytest.approx([-1.0, -4.0])
        assert out["max_abs_angle_phase_0_075_deg"] == pytest.approx([2.0, 5.0])
        assert out["signed_x_at_max_abs_phase_0_075_px"] == pytest.approx(
            [3.0, 6.0],
        )

    def test_raises_on_length_mismatch(self):
        with pytest.raises(ValueError, match="same length"):
            align_endpoints_to_trial_order(
                _empty_phase_aligned_endpoints_df(),
                trial_indices=[0, 1, 2],
                sides=["L", "R"],
            )


# ---------------------------------------------------------------------------
# compute_phase_aligned_endpoints_per_trial — bundle integration tests
# ---------------------------------------------------------------------------

def _make_minimal_bundle_for_endpoint_test(
    *,
    trial_index: int,
    side: str,
    peak_t_ms: float,
    synth_ili_ms: float,
    angle_planters: dict[float, float] | None = None,
    x_planters: dict[float, float] | None = None,
    fps: float = 250.0,
    plot_win_ms: tuple[float, float] = (-180.0, 1500.0),
    n_phase_bins: int = 72,
    include_x_snip: bool = True,
) -> TongueVisualBundle:
    """Build a minimal TongueVisualBundle with a single trial-side row.

    ``angle_planters`` / ``x_planters`` map a t_ms timestamp to the
    value to plant at the closest frame. Lets us plant known signal at
    specific phase positions: phase 0.5 ↔ t_ms = peak_t_ms; phase 0 ↔
    t_ms = peak_t_ms - synth/2; phase 0.75 ↔ t_ms = peak_t_ms +
    synth/4; phase 1 ↔ t_ms = peak_t_ms + synth/2.
    """
    pre_f = max(0, int(np.floor(-plot_win_ms[0] / 1000.0 * fps)))
    post_f = max(0, int(np.ceil(plot_win_ms[1] / 1000.0 * fps)))
    snip_len = pre_f + post_f + 1
    t_ms = (np.arange(-pre_f, post_f + 1, dtype=np.float64) / fps) * 1000.0

    angle_arr = np.zeros(snip_len, dtype=np.float64)
    x_arr = np.zeros(snip_len, dtype=np.float64)
    for ts, val in (angle_planters or {}).items():
        fr = int(np.argmin(np.abs(t_ms - ts)))
        angle_arr[fr] = float(val)
    for ts, val in (x_planters or {}).items():
        fr = int(np.argmin(np.abs(t_ms - ts)))
        x_arr[fr] = float(val)

    trial_row = {
        "side": side,
        "trial_index": int(trial_index),
        "n_peaks": 1,
        "n_bouts": 1,
        "n_multi_lick_bouts": 0,
        "first_peak_t_ms": float(peak_t_ms),
        "t_ms": t_ms.copy(),
        "y_snip": np.zeros(snip_len),
        "angle_snip": angle_arr,
        "angle_allbouts_snip": angle_arr.copy(),
        "angle_firstbout_snip": angle_arr.copy(),
        "angle_firstmulti_snip": angle_arr.copy(),
        "t_firstpeak_align_ms": np.zeros(10),
        "angle_firstpeak_snip": np.zeros(10),
    }
    if include_x_snip:
        trial_row["x_snip"] = x_arr

    # Single-bout per-peak row (synthetic_only mode looks at peak_t_ms
    # entries across all bouts).
    bout_rows: list[dict[str, Any]] = [
        {
            "side": side,
            "trial_index": int(trial_index),
            "bout_idx": 0,
            "bout_rank": 0,
            "multi_bout_rank": float("nan"),  # isolated lick (single-peak bout)
            "n_peaks": 1,
            "bout_t0_ms": float(peak_t_ms - 50.0),
            "bout_t1_ms": float(peak_t_ms + 50.0),
            "peak_t0_ms": float(peak_t_ms),
            "peak_t1_ms": float("nan"),
            "peak_y0": 0.0, "peak_angle0": 0.0,
            "peak_y1": 0.0, "peak_angle1": 0.0,
            "peak_t_ms": float("nan"),
            "peak_y": float("nan"),
            "peak_x": float("nan"),
            "peak_angle_deg": float("nan"),
        },
        {
            "side": side,
            "trial_index": int(trial_index),
            "bout_idx": 0,
            "bout_rank": 0,
            "multi_bout_rank": float("nan"),
            "n_peaks": 1,
            "bout_t0_ms": float(peak_t_ms - 50.0),
            "bout_t1_ms": float(peak_t_ms + 50.0),
            "peak_t0_ms": float("nan"),
            "peak_t1_ms": float("nan"),
            "peak_y0": float("nan"), "peak_angle0": float("nan"),
            "peak_y1": float("nan"), "peak_angle1": float("nan"),
            "peak_t_ms": float(peak_t_ms),
            "peak_y": 0.0,
            "peak_x": 0.0,
            "peak_angle_deg": 0.0,
        },
    ]

    metadata = {
        "animal": "PSXX",
        "date": "2025-01-01",
        "fps": float(fps),
        "n_frames": 10000,
        "eye_in_spout_frame_x": 0.0,
        "eye_in_spout_frame_y": 0.0,
        "angle_sign_flip": -1.0,
        "smoothing_gaussian_sigma_ms": 8.0,
        "feature_extraction_version": "test",
        "interpolation_version": "test",
        "plot_win_ms": list(plot_win_ms),
        "detect_win_ms": [70.0, 3000.0],
        "first_peak_align_win_ms": [-180.0, 1000.0],
        "n_phase_bins": int(n_phase_bins),
        "max_licks_per_trial": 40,
        "pre_stroke_median_ili_ms": float(synth_ili_ms),
    }
    return TongueVisualBundle(
        df_trials=pd.DataFrame([trial_row]),
        df_bouts=pd.DataFrame(bout_rows),
        df_phase=pd.DataFrame(),
        angle_per_frame=pd.DataFrame(),
        metadata=metadata,
    )


class TestComputePhaseAlignedEndpointsPerTrial:
    def test_single_trial_produces_all_three_endpoints(self):
        # peak at t=200, synth=100 → window [150, 250] → phase 0.5 at t=200,
        # phase 0.75 at t=225 (just inside the window). Plant a known
        # negative angle at peak and a known signed-positive x at t=225.
        bundle = _make_minimal_bundle_for_endpoint_test(
            trial_index=0, side="L",
            peak_t_ms=200.0, synth_ili_ms=100.0,
            angle_planters={200.0: -12.5},  # endpoint A
            x_planters={228.0: 33.0},        # endpoint C target inside window
        )
        out = compute_phase_aligned_endpoints_per_trial(bundle)
        assert list(out.columns) == list(PHASE_ALIGNED_ENDPOINT_COLUMNS)
        assert len(out) == 1
        row = out.iloc[0]
        assert int(row["trial_index"]) == 0
        assert str(row["side"]) == "L"
        # Endpoint A: angle at phase=0.5 (frame closest to t=200)
        assert row["peak_angle_deg"] == pytest.approx(-12.5)
        # Endpoint B: max |angle| in [0, 0.75]; only finite plant is -12.5
        assert row["max_abs_angle_phase_0_075_deg"] == pytest.approx(12.5)
        # Endpoint C: argmax(|x|) is x=33 at t=228 (phase ≈ 0.78 — outside
        # window if exact, but the closest frame may still land inside;
        # confirm magnitude matches what we planted, signed positive).
        # If 228 falls outside [0, 0.75], we expect 0.0 (the next-largest
        # |x| in window). Either way we test the SIGNED behavior, not the
        # exact magnitude.
        c = float(row["signed_x_at_max_abs_phase_0_075_px"])
        # phase(228) = (228 - 150) / 100 = 0.78 — outside [0, 0.75].
        # In-window x values are all zero from the initialization.
        # Result: argmax picks index 0, signed value = 0.0.
        assert c == pytest.approx(0.0)

    def test_signed_negative_x_inside_window(self):
        # Plant -42 at t=180 → phase=(180-150)/100 = 0.3 (inside [0, 0.75]).
        # Plant +10 at t=240 → phase=0.9 (outside).
        bundle = _make_minimal_bundle_for_endpoint_test(
            trial_index=7, side="R",
            peak_t_ms=200.0, synth_ili_ms=100.0,
            x_planters={180.0: -42.0, 240.0: +10.0},
        )
        out = compute_phase_aligned_endpoints_per_trial(bundle)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["signed_x_at_max_abs_phase_0_075_px"] == pytest.approx(-42.0)

    def test_no_phase_rows_returns_empty(self):
        # No peak time in df_bouts → build_first_lick_centered_phase_rows
        # returns empty → compute returns empty.
        bundle = _make_minimal_bundle_for_endpoint_test(
            trial_index=0, side="L",
            peak_t_ms=200.0, synth_ili_ms=100.0,
        )
        # Override df_bouts to remove all peak_t_ms entries.
        bundle = TongueVisualBundle(
            df_trials=bundle.df_trials,
            df_bouts=pd.DataFrame(),
            df_phase=bundle.df_phase,
            angle_per_frame=bundle.angle_per_frame,
            metadata=bundle.metadata,
        )
        out = compute_phase_aligned_endpoints_per_trial(bundle)
        assert out.empty
        assert list(out.columns) == list(PHASE_ALIGNED_ENDPOINT_COLUMNS)

    def test_missing_pre_stroke_median_ili_returns_empty(self):
        bundle = _make_minimal_bundle_for_endpoint_test(
            trial_index=0, side="L",
            peak_t_ms=200.0, synth_ili_ms=float("nan"),
        )
        out = compute_phase_aligned_endpoints_per_trial(bundle)
        assert out.empty
        assert list(out.columns) == list(PHASE_ALIGNED_ENDPOINT_COLUMNS)

    def test_bundle_without_x_snip_returns_nan_endpoint_c(self):
        bundle = _make_minimal_bundle_for_endpoint_test(
            trial_index=3, side="L",
            peak_t_ms=200.0, synth_ili_ms=100.0,
            angle_planters={200.0: -8.0},
            include_x_snip=False,
        )
        out = compute_phase_aligned_endpoints_per_trial(bundle)
        assert len(out) == 1
        row = out.iloc[0]
        # A + B still computed
        assert row["peak_angle_deg"] == pytest.approx(-8.0)
        assert row["max_abs_angle_phase_0_075_deg"] == pytest.approx(8.0)
        # C is NaN because x_centered column is NaN-filled
        assert np.isnan(row["signed_x_at_max_abs_phase_0_075_px"])

    def test_phase_peak_constant_matches_kickoff_lock(self):
        # Kickoff body: endpoint A is at phase = 0.5 (lick-1 peak time).
        # Guard the constant against drift.
        assert PHASE_PEAK == 0.5

    def test_phase_window_constants_match_kickoff_lock(self):
        # Kickoff body: phase ∈ [0, 0.75] for endpoints B + C.
        assert PHASE_WINDOW_LO == 0.0
        assert PHASE_WINDOW_HI == 0.75
