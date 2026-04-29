"""Phase 7a.3 V3 — unit tests for tongue per-trial features.

Covers the unified slope detector + 5-cell extractors + Cell 50 angle math
+ driver + I/O + schema lock per kickoff §4a (37 tests). Every test that
invokes a writer uses :class:`PathResolver` with ``output_root=tmp_path``
per :doc:`docs/testing-conventions.md` (no test ever writes to the real
``stroke_orofacial_pipeline_outputs/`` tree).

Synthetic fixtures live at the top:

- :func:`_make_synthetic_tongue_parquet` — 7a.2-shaped parquet (7 cols + 9
  file-level metadata keys).
- :func:`_make_synthetic_eye_landmark_parquet` — centered_spout_midpoint
  parquet with the 10 columns the eye-resolver consumes (plus filler
  to match the 39-col schema Task 1.5 verified).
- :func:`_make_minimal_manifest` — fills only the fields the driver
  actually reads (animal, date, excluded).
"""

from __future__ import annotations

import copy
import datetime
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics._angle import (
    _compute_signed_tongue_angle_deg,
    _evaluate_session_inclusion,
    _extract_angle_at_lick_timestamps,
    _extract_angle_max_signed_per_lick,
    _extract_cell50_own_bout_scalars,
    _extract_per_frame_angle_smoothed,
    _gaussian_smooth_nan,
)
from stroke_orofacial.dlc_kinematics._detector import (
    _filter_peaks_by_bout_mode,
    _slope_detect_lick_peaks,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    FEATURE_EXTRACTION_VERSION,
    INTERPOLATION_VERSION,
    TrialEvent,
    _derive_trial_events_from_spout_behavior,
    _extract_lick1_lick2,
    _extract_licking_dynamics_reductions,
    _extract_licking_dynamics_traces,
    _extract_n_licks_family,
    _extract_peak_velocity_first5,
    _per_cell_bout,
    _per_cell_detector,
    _resolve_eye_midpoint_session_median,
    build_tongue_pertrial,
)
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
)
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver

_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"

# Detector constants used across synthetic fixtures.
_SYNTH_FPS = 250.0


# ===========================================================================
# Helper fixtures — synthetic data generators
# ===========================================================================


def _gaussian_bump(
    t_ms: np.ndarray, center_ms: float, amplitude: float, sigma_ms: float = 12.0,
) -> np.ndarray:
    """A single Gaussian-shaped lick peak in y(t).

    σ = 12 ms gives ``max |dy/dt| ≈ amplitude / (σ × e^0.5)`` ≈ 1.5 px/ms ≈
    1500 px/s for amplitude=30 — easily clears the 250 px/s slope threshold.
    """
    return amplitude * np.exp(-0.5 * ((t_ms - center_ms) / sigma_ms) ** 2)


def _make_lick_trace(
    duration_ms: float, peak_centers_ms: list[float], amplitude: float = 30.0,
    fps: float = _SYNTH_FPS, sigma_ms: float = 12.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a trial slice (y_t, x_t, t_ms) with Gaussian-shaped peaks.

    ``peak_centers_ms`` lists peak times relative to t=0 (post-reward).
    Returns NaN-clean traces; x_t is zeros (the angle math needs only the
    y dynamics for detection).
    """
    n = int(round(duration_ms / 1000.0 * fps)) + 1
    t_ms = np.arange(n, dtype=np.float64) / fps * 1000.0
    y_t = np.zeros(n, dtype=np.float64)
    for c in peak_centers_ms:
        y_t += _gaussian_bump(t_ms, c, amplitude, sigma_ms)
    x_t = np.zeros(n, dtype=np.float64)
    return y_t, x_t, t_ms


def _make_synthetic_tongue_parquet(
    path: Path, n_frames: int, fps: float = _SYNTH_FPS,
    *, x_final: np.ndarray | None = None, y_final: np.ndarray | None = None,
) -> None:
    """Write a 7a.2-shaped tongue interpolated_traces parquet.

    Schema: 7 cols + 9 file-level metadata keys (matches the upstream
    ``build_interpolated_trace`` writer).
    """
    if x_final is None:
        x_final = np.zeros(n_frames, dtype=np.float64)
    if y_final is None:
        y_final = np.zeros(n_frames, dtype=np.float64)
    df = pd.DataFrame({
        "frame_idx": np.arange(n_frames, dtype=np.int64),
        "x_final": x_final.astype(np.float64),
        "y_final": y_final.astype(np.float64),
        "likelihood_raw": np.full(n_frames, 0.95, dtype=np.float64),
        "is_interp_fill": np.zeros(n_frames, dtype=bool),
        "is_baseline_fill": np.zeros(n_frames, dtype=bool),
        "fill_method": np.zeros(n_frames, dtype=np.int8),
    })
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = {
        b"X0": b"0.0",
        b"Y0": b"-110.0",
        b"baseline_stage": b"drop",
        b"center_mode": b"centered_spout_midpoint",
        b"fps": repr(fps).encode(),
        b"interpolation_version": INTERPOLATION_VERSION.encode(),
        b"n_frames": str(n_frames).encode(),
        b"side_convention_version": b"1",
        b"wavesurfer_sides_match_mouse_sides": b"False",
    }
    existing = table.schema.metadata or {}
    merged = {**{bytes(k): bytes(v) for k, v in existing.items()}, **meta}
    table = table.replace_schema_metadata(merged)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(path), compression="snappy")


# Full 39-col schema for the centered_spout_midpoint parquet (Task 1.5
# verified). The eye-resolver consumes only L/R_eye + L/R_spout × {x, y,
# likelihood}; the rest are filler so the schema matches what
# read_centered_parquet expects.
_CSM_COLS = [
    "nose_x", "nose_y", "nose_likelihood",
    "jaw_x", "jaw_y", "jaw_likelihood",
    "tongue_x", "tongue_y", "tongue_likelihood",
    "L_whiskers_1_x", "L_whiskers_1_y", "L_whiskers_1_likelihood",
    "L_whiskers_2_x", "L_whiskers_2_y", "L_whiskers_2_likelihood",
    "L_whiskers_3_x", "L_whiskers_3_y", "L_whiskers_3_likelihood",
    "R_whiskers_1_x", "R_whiskers_1_y", "R_whiskers_1_likelihood",
    "R_whiskers_2_x", "R_whiskers_2_y", "R_whiskers_2_likelihood",
    "R_whiskers_3_x", "R_whiskers_3_y", "R_whiskers_3_likelihood",
    "L_eye_x", "L_eye_y", "L_eye_likelihood",
    "R_eye_x", "R_eye_y", "R_eye_likelihood",
    "L_spout_x", "L_spout_y", "L_spout_likelihood",
    "R_spout_x", "R_spout_y", "R_spout_likelihood",
]


def _make_synthetic_eye_landmark_df(
    n_frames: int, *,
    L_eye_pos: tuple[float, float] = (138.0, -432.0),
    R_eye_pos: tuple[float, float] = (-124.0, -434.0),
    L_spout_pos: tuple[float, float] = (75.0, 1.0),
    R_spout_pos: tuple[float, float] = (-78.0, -1.0),
    L_eye_likelihood: float = 0.95,
    R_eye_likelihood: float = 0.95,
    L_spout_likelihood: float = 0.95,
    R_spout_likelihood: float = 0.95,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a centered_spout_midpoint-shaped DataFrame.

    Eye + spout positions are constant across frames (real data has small
    per-frame jitter; for unit testing we fix them so medians are
    deterministic). All 39 columns are filled to match the schema.
    """
    rng = np.random.default_rng(seed)
    data: dict[str, np.ndarray] = {}
    for col in _CSM_COLS:
        data[col] = rng.normal(0.0, 5.0, n_frames).astype(np.float32)
    # Fix the columns the eye-resolver actually consumes.
    data["L_eye_x"] = np.full(n_frames, L_eye_pos[0], dtype=np.float32)
    data["L_eye_y"] = np.full(n_frames, L_eye_pos[1], dtype=np.float32)
    data["L_eye_likelihood"] = np.full(n_frames, L_eye_likelihood, dtype=np.float32)
    data["R_eye_x"] = np.full(n_frames, R_eye_pos[0], dtype=np.float32)
    data["R_eye_y"] = np.full(n_frames, R_eye_pos[1], dtype=np.float32)
    data["R_eye_likelihood"] = np.full(n_frames, R_eye_likelihood, dtype=np.float32)
    data["L_spout_x"] = np.full(n_frames, L_spout_pos[0], dtype=np.float32)
    data["L_spout_y"] = np.full(n_frames, L_spout_pos[1], dtype=np.float32)
    data["L_spout_likelihood"] = np.full(
        n_frames, L_spout_likelihood, dtype=np.float32,
    )
    data["R_spout_x"] = np.full(n_frames, R_spout_pos[0], dtype=np.float32)
    data["R_spout_y"] = np.full(n_frames, R_spout_pos[1], dtype=np.float32)
    data["R_spout_likelihood"] = np.full(
        n_frames, R_spout_likelihood, dtype=np.float32,
    )
    return pd.DataFrame(data)


def _make_synthetic_eye_landmark_parquet(
    path: Path, n_frames: int, **df_kwargs,
) -> None:
    """Write a centered_spout_midpoint-shaped parquet.

    Filename pattern follows the upstream convention
    ``video2_{YYYY-MM-DD}T*.parquet``; caller picks the path so it matches
    the date-prefix glob in :meth:`PathResolver.dlc_centered_spout_midpoint_parquet`.
    """
    df = _make_synthetic_eye_landmark_df(n_frames, **df_kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(path), index=False, compression="snappy")


def _make_minimal_manifest(
    animal: str = "PS46", date: datetime.date = datetime.date(2025, 3, 7),
    *,
    alignment_template: Path | None = None,
    wavesurfer_sides_match_mouse_sides: bool = False,
) -> SessionManifest:
    """A SessionManifest filled only with the fields the driver reads."""
    return SessionManifest(
        session_id=f"{animal}_{date.strftime('%Y%m%d')}",
        animal=animal,
        date=date,
        day_relative_to_stroke=-6,
        phase="baseline",
        excluded=False,
        alignment_template=alignment_template,
        wavesurfer_sides_match_mouse_sides=wavesurfer_sides_match_mouse_sides,
    )


def _make_synthetic_licks_npz(
    path: Path, *,
    reward_L_ws: np.ndarray | None = None,
    reward_R_ws: np.ndarray | None = None,
    wavesurfer_sides_match_mouse_sides: bool = False,
) -> None:
    """Phase-2-shaped licks NPZ with the v6.8 side-convention stamp.

    Mirrors the writer in
    ``src/stroke_orofacial/spout_behavior/session_processing.py:354-366``.
    Only the fields :func:`load_reward_events` consumes are populated;
    Lick_*/Tone_* are empty for these tests.
    """
    if reward_L_ws is None:
        reward_L_ws = np.array([1000, 3000, 5000], dtype=np.int64)
    if reward_R_ws is None:
        reward_R_ws = np.array([2000, 4000], dtype=np.int64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        Reward_L=reward_L_ws.astype(np.int64),
        Reward_R=reward_R_ws.astype(np.int64),
        **{
            SIDE_CONVENTION_MATCH_KEY: np.bool_(wavesurfer_sides_match_mouse_sides),
            SIDE_CONVENTION_VERSION_KEY: np.int64(SIDE_CONVENTION_VERSION),
        },
    )


def _make_synthetic_alignment_template_npz(
    path: Path, n_ws: int = 20000, *, slope_ws_per_camFrame: float = 4.0,
) -> None:
    """Linear-ramp alignment template: ``cam_idx = ws_idx / slope_ws_per_camFrame``.

    Default slope = 4.0 (typical for fps=250 Hz cam ↔ Fs=1000 Hz wavesurfer).
    """
    sig_camIdx__idx_ws = (np.arange(n_ws) / float(slope_ws_per_camFrame)).astype(
        np.float64,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, sig_camIdx__idx_ws=sig_camIdx__idx_ws)


@pytest.fixture()
def base_params() -> dict:
    """Loaded ``configs/defaults.yaml`` (deep-copied per test)."""
    return copy.deepcopy(load_defaults())


# ===========================================================================
# 1-7. Unified slope detector + bout-mode filter
# ===========================================================================


class TestSlopeDetector:
    """Detector + bout helpers (private to ``_detector.py``)."""

    def _detector_params(self, base_params: dict) -> dict:
        return base_params["dlc_kinematics"]["tongue_pertrial"]["detector"]

    # 1
    def test_slope_detect_lick_peaks_synthetic_two_peaks(self, base_params):
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2000.0, peak_centers_ms=[500.0, 1500.0], amplitude=30.0,
        )
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0),
            detector_params=self._detector_params(base_params),
        )
        assert len(peaks) == 2
        assert peaks.peak_times_ms[0] == pytest.approx(500.0, abs=8.0)
        assert peaks.peak_times_ms[1] == pytest.approx(1500.0, abs=8.0)
        assert np.all(peaks.peak_y >= 20.0)

    # 2 — V3-NEW MIN_PEAK_Y_ABS gate
    def test_slope_detect_lick_peaks_min_peak_y_abs_filter(self, base_params):
        # Amplitude 15 < min_peak_y_abs (20) → all peaks rejected.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2000.0, peak_centers_ms=[500.0, 1500.0], amplitude=15.0,
        )
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0),
            detector_params=self._detector_params(base_params),
        )
        assert len(peaks) == 0

    # 3 — V3-NEW MIN_FINITE_SAMPLES_PER_LICK gate
    def test_slope_detect_lick_peaks_min_finite_samples_filter(
        self, base_params,
    ):
        """When peak-pad window has too few finite samples, peak is rejected.

        We craft this by inserting NaN mostly inside the peak's ± peak_pad_ms
        window so n_finite < min_finite_samples_per_lick (5).
        """
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2000.0, peak_centers_ms=[500.0], amplitude=30.0,
        )
        # peak_pad_ms = 52 → 13 frames at 250 fps.
        center_idx = int(round(500.0 / 1000.0 * _SYNTH_FPS))
        # Punch NaN into samples [center-13, center+13] except keep 4 finite
        # samples (less than min_finite=5). Keep the peak sample itself
        # finite so the rise/turnover phase still passes; we want the
        # MIN_FINITE check to be the rejector.
        for j in range(-13, 14):
            if j not in (-2, 0, 2, 6) and 0 <= center_idx + j < len(y_t):
                y_t[center_idx + j] = np.nan
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0),
            detector_params=self._detector_params(base_params),
        )
        assert len(peaks) == 0

    # 4 — strict_no_fallback returns empty when no peak satisfies all gates
    def test_slope_detect_lick_peaks_strict_no_fallback_returns_empty(
        self, base_params,
    ):
        # Flat trace: dy/dt is zero everywhere → no rise mask → empty.
        n = int(round(2000.0 / 1000.0 * _SYNTH_FPS)) + 1
        t_ms = np.arange(n, dtype=np.float64) / _SYNTH_FPS * 1000.0
        y_t = np.zeros(n, dtype=np.float64)
        x_t = np.zeros(n, dtype=np.float64)
        det = self._detector_params(base_params)
        assert det["strict_no_fallback"] is True  # YAML lock check
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0), detector_params=det,
        )
        assert len(peaks) == 0
        assert peaks.peak_times_ms.shape == (0,)

    # 5
    def test_filter_peaks_by_bout_mode_all(self, base_params):
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=4000.0,
            peak_centers_ms=[200.0, 350.0, 500.0, 1500.0, 2000.0],
            amplitude=30.0,
        )
        det = self._detector_params(base_params)
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS, detect_win_ms=(70.0, 4000.0),
            detector_params=det,
        )
        assert len(peaks) >= 3
        out = _filter_peaks_by_bout_mode(
            peaks, mode="all",
            bout_params=base_params["dlc_kinematics"]["tongue_pertrial"]["bout"],
        )
        assert len(out) == len(peaks)

    # 6
    def test_filter_peaks_by_bout_mode_first_bout(self, base_params):
        # Two clear bouts: peaks at [200, 350, 500] (one bout), then a gap
        # > bout.max_ili_ms (300 ms) before [1500, 2000].
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=4000.0,
            peak_centers_ms=[200.0, 350.0, 500.0, 1500.0, 2000.0],
            amplitude=30.0,
        )
        det = self._detector_params(base_params)
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS, detect_win_ms=(70.0, 4000.0),
            detector_params=det,
        )
        out = _filter_peaks_by_bout_mode(
            peaks, mode="first_bout",
            bout_params=base_params["dlc_kinematics"]["tongue_pertrial"]["bout"],
        )
        # First bout = [200, 350, 500] — three licks; the 1500/2000 split
        # by 1000 ms gap ≫ 300 ms threshold.
        assert len(out) == 3
        assert out.peak_times_ms.max() < 800.0

    # 7b — next-lick search starts at end_idx + 1 (post-fall-run-end)
    # (port-bug fix C5.1, 2026-04-28)
    def test_slope_detect_next_lick_starts_after_fall_run(self, base_params):
        """Two close peaks separated by a fall run. Pre-fix our impl started
        the next-lick search at ``i_peak + 1`` (peak position) and could
        re-detect a phantom peak inside the first peak's fall edge. Post-fix
        we use ``end_idx + 1`` (post-fall-run-end), matching legacy's
        Cell 33 contract.

        Synthetic: two narrow Gaussian bumps with a clean dy <= 0 fall
        between them. We assert exactly 2 peaks come back (not 3+).
        """
        # σ = 10 ms peaks at 400 + 700 ms; close enough that a buggy
        # next-start could find an extra peak in the fall tail.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=1500.0, peak_centers_ms=[400.0, 700.0],
            amplitude=30.0, sigma_ms=10.0,
        )
        det = self._detector_params(base_params)
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 1500.0), detector_params=det,
        )
        assert len(peaks) == 2
        assert peaks.peak_times_ms[0] == pytest.approx(400.0, abs=12.0)
        assert peaks.peak_times_ms[1] == pytest.approx(700.0, abs=12.0)

    # 7c2 — accept_peaks_without_fall_run=True bypasses strict rejection
    # (C5.5 2026-04-29). Cells 36/39/42 legacy accept peaks regardless of
    # fall validation; per-cell knob flips the strict path off.
    def test_slope_detect_accept_peaks_without_fall_run_overrides_strict(
        self, base_params,
    ):
        # Same rise-then-plateau synthetic as test_slope_detect_strict_no_fallback
        # below. Strict mode would reject (test 7c). With accept_no_fall=True
        # the peak is accepted instead.
        n = int(round(2000.0 / 1000.0 * _SYNTH_FPS)) + 1
        t_ms = np.arange(n, dtype=np.float64) / _SYNTH_FPS * 1000.0
        y_t = np.zeros(n, dtype=np.float64)
        ramp_lo = int(round(400.0 / 1000.0 * _SYNTH_FPS))
        ramp_hi = int(round(500.0 / 1000.0 * _SYNTH_FPS))
        for i in range(ramp_lo, ramp_hi + 1):
            y_t[i] = 50.0 * (i - ramp_lo) / max(1, ramp_hi - ramp_lo)
        y_t[ramp_hi:] = 50.0
        x_t = np.zeros(n, dtype=np.float64)
        det = copy.deepcopy(self._detector_params(base_params))
        det["accept_peaks_without_fall_run"] = True
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0), detector_params=det,
        )
        # Without strict-on-no-fall, the apex peak is accepted.
        assert len(peaks) >= 1
        assert peaks.peak_y[0] >= 20.0  # passes MIN_PEAK_Y_ABS

    # 7c — strict_no_fallback rejects peaks with no fall run after them
    # (port-bug fix C5.1, 2026-04-28)
    def test_slope_detect_strict_no_fallback_rejects_no_fall_run(
        self, base_params,
    ):
        """A rise-then-plateau (no fall) lick must be rejected under
        ``strict_no_fallback=True``. Pre-fix our impl accepted such peaks
        because the fall validation was a soft/no-op check.
        """
        # Synthetic: ramp up from 0 to 50 over 100 ms, then HOLD at 50 to
        # the end of the window. There's a strong rise, a clear apex, but
        # no symmetric fall (dy is ~0 after the apex, never crosses below
        # -slope_thr). Legacy + post-fix should reject.
        n = int(round(2000.0 / 1000.0 * _SYNTH_FPS)) + 1
        t_ms = np.arange(n, dtype=np.float64) / _SYNTH_FPS * 1000.0
        y_t = np.zeros(n, dtype=np.float64)
        # Linear ramp: 0 → 50 over [400, 500] ms (25 ms × 4 frames).
        ramp_lo = int(round(400.0 / 1000.0 * _SYNTH_FPS))
        ramp_hi = int(round(500.0 / 1000.0 * _SYNTH_FPS))
        for i in range(ramp_lo, ramp_hi + 1):
            y_t[i] = 50.0 * (i - ramp_lo) / max(1, ramp_hi - ramp_lo)
        # Hold at 50 from ramp_hi to end.
        y_t[ramp_hi:] = 50.0
        x_t = np.zeros(n, dtype=np.float64)
        det = self._detector_params(base_params)
        assert det["strict_no_fallback"] is True
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS,
            detect_win_ms=(70.0, 2000.0), detector_params=det,
        )
        # No fall run after the apex → rejected under strict mode.
        assert len(peaks) == 0

    # 7
    def test_filter_peaks_by_bout_mode_first_multi_bout(self, base_params):
        # First bout = singleton (1 lick), then a multi-lick bout at 1500/1700/1900.
        # The 200→1500 ILI = 1300 ms ≫ 300 → bout split.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2500.0,
            peak_centers_ms=[200.0, 1500.0, 1700.0, 1900.0],
            amplitude=30.0,
        )
        det = self._detector_params(base_params)
        peaks = _slope_detect_lick_peaks(
            y_t, x_t, t_ms, _SYNTH_FPS, detect_win_ms=(70.0, 2500.0),
            detector_params=det,
        )
        out = _filter_peaks_by_bout_mode(
            peaks, mode="first_multi_bout",
            bout_params=base_params["dlc_kinematics"]["tongue_pertrial"]["bout"],
        )
        # Output should be the multi-lick bout, not the singleton.
        assert len(out) == 3
        assert out.peak_times_ms.min() > 1000.0


# ===========================================================================
# Per-cell knob override mechanism (C5.2 2026-04-28)
# ===========================================================================


class TestPerCellOverrides:
    """Cover ``_per_cell_detector`` + ``_per_cell_bout`` (C5.2).

    Default-mode params have empty per-cell dicts → behavior unchanged
    (tested via TestSlopeDetector + TestCell33-50 already). These tests
    exercise the override path.
    """

    # 7d — empty per-cell dicts fall back to base detector knobs
    def test_per_cell_empty_override_uses_base_params(self, base_params):
        for cell in ("cell33", "cell36", "cell39", "cell42", "cell50"):
            base = base_params["dlc_kinematics"]["tongue_pertrial"]["detector"]
            out = _per_cell_detector(base_params, cell)
            assert out == base, f"cell={cell} not equal to base"
            base_b = base_params["dlc_kinematics"]["tongue_pertrial"]["bout"]
            out_b = _per_cell_bout(base_params, cell)
            assert out_b == base_b, f"cell={cell} bout not equal to base"

    # 7e — per-cell detector override applied in shallow merge + isolated
    def test_per_cell_detector_override_isolation(self, base_params):
        params = copy.deepcopy(base_params)
        tp = params["dlc_kinematics"]["tongue_pertrial"]
        # Override min_peak_y_abs on cell36 ONLY.
        tp["detector_per_cell"]["cell36"] = {"min_peak_y_abs": 0.0}
        cell33_det = _per_cell_detector(params, "cell33")
        cell36_det = _per_cell_detector(params, "cell36")
        # cell33 unaffected.
        assert cell33_det["min_peak_y_abs"] == base_params[
            "dlc_kinematics"]["tongue_pertrial"]["detector"]["min_peak_y_abs"]
        # cell36 picks up the override.
        assert cell36_det["min_peak_y_abs"] == 0.0
        # Other knobs unchanged on cell36.
        assert cell36_det["slope_thr_px_per_s"] == base_params[
            "dlc_kinematics"]["tongue_pertrial"]["detector"]["slope_thr_px_per_s"]

    # 7f — per-cell bout override applied + isolated
    def test_per_cell_bout_override_isolation(self, base_params):
        params = copy.deepcopy(base_params)
        tp = params["dlc_kinematics"]["tongue_pertrial"]
        # Override max_ili_ms on cell42 ONLY (legacy=400, V3=300).
        tp["bout_per_cell"]["cell42"] = {"max_ili_ms": 400.0}
        cell33_bout = _per_cell_bout(params, "cell33")
        cell42_bout = _per_cell_bout(params, "cell42")
        # cell33 unaffected.
        assert cell33_bout["max_ili_ms"] == 300.0
        # cell42 picks up the override.
        assert cell42_bout["max_ili_ms"] == 400.0
        # Other knobs unchanged on cell42.
        assert cell42_bout["min_ili_ms"] == base_params[
            "dlc_kinematics"]["tongue_pertrial"]["bout"]["min_ili_ms"]
        assert cell42_bout["min_licks_in_bout_for_ili"] == base_params[
            "dlc_kinematics"]["tongue_pertrial"]["bout"]["min_licks_in_bout_for_ili"]

    # 7g — extractor under per-cell override produces a different result
    # vs no override (smoke check that the override actually flows).
    def test_per_cell_override_changes_extractor_output(self, base_params):
        # Synthetic: 3 peaks in apply window, two close (bout 1 = [400, 700])
        # and one far (4000 ms). With bout_max_ili=300 (V3 default), 400/700
        # are ONE bout (Δ=300 borderline). With bout_max_ili=400 (legacy),
        # they're definitively ONE bout. Either way the SAME 1 multi-bout
        # exists, so bout_count = 1 in both cases. To get a divergent
        # output, use peaks 400 and 750 (Δ=350): exceeds V3 threshold (300)
        # → bout_count=0 multi-lick bouts; under legacy threshold (400) →
        # bout_count=1 multi-lick bout.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=5000.0, peak_centers_ms=[400.0, 750.0],
            amplitude=30.0,
        )
        # Default (V3): bout_max_ili=300 → 350 > 300, separate bouts → 0
        # multi-bouts.
        out_default = _extract_licking_dynamics_reductions(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        # Override cell42's bout_max_ili to 400 (legacy).
        params = copy.deepcopy(base_params)
        params["dlc_kinematics"]["tongue_pertrial"]["bout_per_cell"]["cell42"] = {
            "max_ili_ms": 400.0,
        }
        out_override = _extract_licking_dynamics_reductions(
            y_t, x_t, t_ms, _SYNTH_FPS, params=params,
        )
        # Under V3 default: 0 multi-bouts. Under legacy override: 1 multi-bout.
        assert out_default["bout_count"] == 0
        assert out_override["bout_count"] == 1


# ===========================================================================
# 8-10. Cell 33 — lick1 / lick2
# ===========================================================================


class TestCell33:

    # 8
    def test_extract_lick1_lick2_two_peaks_returns_six_scalars(self, base_params):
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2500.0, peak_centers_ms=[500.0, 1500.0], amplitude=30.0,
        )
        out = _extract_lick1_lick2(y_t, x_t, t_ms, _SYNTH_FPS, params=base_params)
        assert set(out.keys()) == {
            "lick1_y_peak", "lick1_t_peak_ms", "lick1_x_at_ypeak",
            "lick2_y_peak", "lick2_t_peak_ms", "lick2_x_at_ypeak",
        }
        assert np.isfinite(out["lick1_t_peak_ms"])
        assert np.isfinite(out["lick2_t_peak_ms"])
        assert out["lick1_t_peak_ms"] < out["lick2_t_peak_ms"]
        assert out["lick1_y_peak"] >= 20.0
        assert out["lick2_y_peak"] >= 20.0

    # 9
    def test_extract_lick1_lick2_one_peak_lick2_nan(self, base_params):
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2500.0, peak_centers_ms=[500.0], amplitude=30.0,
        )
        out = _extract_lick1_lick2(y_t, x_t, t_ms, _SYNTH_FPS, params=base_params)
        assert np.isfinite(out["lick1_t_peak_ms"])
        assert np.isnan(out["lick2_y_peak"])
        assert np.isnan(out["lick2_t_peak_ms"])
        assert np.isnan(out["lick2_x_at_ypeak"])

    # 10
    def test_extract_lick1_lick2_no_peak_all_nan(self, base_params):
        n = int(round(2500.0 / 1000.0 * _SYNTH_FPS)) + 1
        y_t = np.zeros(n, dtype=np.float64)
        x_t = np.zeros(n, dtype=np.float64)
        t_ms = np.arange(n, dtype=np.float64) / _SYNTH_FPS * 1000.0
        out = _extract_lick1_lick2(y_t, x_t, t_ms, _SYNTH_FPS, params=base_params)
        for k in out:
            assert np.isnan(out[k])


# ===========================================================================
# 11-13. Cell 36 — peak velocity, first 5 licks
# ===========================================================================


class TestCell36:

    # 11
    def test_extract_peak_velocity_first5_synthetic_seven_licks(self, base_params):
        # Seven peaks in [70, 3000] window — only first 5 should populate.
        peak_centers = [400.0 + 350.0 * i for i in range(7)]  # 400..2500 ms
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=3000.0, peak_centers_ms=peak_centers, amplitude=30.0,
        )
        out = _extract_peak_velocity_first5(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        assert out["vy_peaks_bylick"].shape == (5,)
        assert out["vxy_peaks_bylick"].shape == (5,)
        assert out["lick_t_peaks_bylick"].shape == (5,)
        assert np.all(np.isfinite(out["vy_peaks_bylick"]))
        assert np.all(np.isfinite(out["vxy_peaks_bylick"]))

    # 12
    def test_extract_peak_velocity_first5_three_licks_padded(self, base_params):
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=3000.0,
            peak_centers_ms=[400.0, 1000.0, 1700.0],
            amplitude=30.0,
        )
        out = _extract_peak_velocity_first5(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        assert out["vy_peaks_bylick"].shape == (5,)
        # First 3 finite, last 2 NaN-padded.
        assert np.all(np.isfinite(out["vy_peaks_bylick"][:3]))
        assert np.all(np.isnan(out["vy_peaks_bylick"][3:]))

    # 13
    def test_extract_peak_velocity_first5_velocity_smoothing_applied(
        self, base_params,
    ):
        """``do_smooth_vel=True`` should produce a different (smaller) peak
        velocity than ``do_smooth_vel=False`` on a sharp-edge synthetic peak.

        Smoothing happens at the velocity stage (post-differentiation,
        legacy SMOOTH_VEL pattern); turning it off should let the raw
        gradient produce sharper extrema.
        """
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=2000.0, peak_centers_ms=[500.0], amplitude=30.0,
            sigma_ms=8.0,  # narrower bump → larger raw velocity
        )
        params_smooth = copy.deepcopy(base_params)
        params_smooth["dlc_kinematics"]["tongue_pertrial"]["detector"]["do_smooth_vel"] = True
        out_smooth = _extract_peak_velocity_first5(
            y_t, x_t, t_ms, _SYNTH_FPS, params=params_smooth,
        )
        params_raw = copy.deepcopy(base_params)
        params_raw["dlc_kinematics"]["tongue_pertrial"]["detector"]["do_smooth_vel"] = False
        out_raw = _extract_peak_velocity_first5(
            y_t, x_t, t_ms, _SYNTH_FPS, params=params_raw,
        )
        # Smoothing reduces peak velocity (averaging across rising edge).
        assert out_smooth["vy_peaks_bylick"][0] < out_raw["vy_peaks_bylick"][0]


# ===========================================================================
# 14-17. Cell 39 — n_licks family
# ===========================================================================


class TestCell39:

    # 14
    def test_extract_n_licks_family_count_within_apply_window(self, base_params):
        # 3 peaks in [70, 5000]; 1 outside (at 6000 ms, in detect [70, 8000]
        # but outside apply [70, 5000]).
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=8000.0,
            peak_centers_ms=[500.0, 2000.0, 4500.0, 6000.0],
            amplitude=30.0,
        )
        out = _extract_n_licks_family(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        assert out["n_licks"] == 3  # 6000 ms peak excluded by apply window

    # 15
    def test_extract_n_licks_family_direction_tally(self, base_params):
        # Three peaks; manually shift x so they land left/right/center.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=5000.0,
            peak_centers_ms=[500.0, 2000.0, 3500.0],
            amplitude=30.0,
        )
        # Apply window peaks land at indices ≈ 125, 500, 875.
        # Left (>+5), right (<-5), other (in [-5, +5]).
        for i, x_at in zip([125, 500, 875], [10.0, -10.0, 0.0]):
            x_t[i] = x_at
        out = _extract_n_licks_family(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        assert out["n_left"] == 1
        assert out["n_right"] == 1
        assert out["n_other"] == 1
        assert out["n_left"] + out["n_right"] + out["n_other"] == out["n_licks"]

    # 16
    def test_extract_n_licks_family_lick_ge10_threshold(self, base_params):
        # 9 peaks → False; 10 peaks → True.
        peak_centers_9 = [400.0 + 200.0 * i for i in range(9)]
        peak_centers_10 = [400.0 + 200.0 * i for i in range(10)]
        for centers, expected in [(peak_centers_9, False), (peak_centers_10, True)]:
            y_t, x_t, t_ms = _make_lick_trace(
                duration_ms=5000.0, peak_centers_ms=centers, amplitude=30.0,
            )
            out = _extract_n_licks_family(
                y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
            )
            assert out["lick_ge10"] is expected, (
                f"n_licks={out['n_licks']}, lick_ge10={out['lick_ge10']}, "
                f"expected={expected}",
            )

    # 17
    def test_extract_n_licks_family_clean_1s_bins_over_5070_window(
        self, base_params,
    ):
        # One peak in each 1-s bin: centers at 500, 1500, 2500, 3500, 4500.
        # Bin edges: [70, 1070, 2070, 3070, 4070, 5070].
        peak_centers = [500.0, 1500.0, 2500.0, 3500.0, 4500.0]
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=5500.0, peak_centers_ms=peak_centers, amplitude=30.0,
        )
        out = _extract_n_licks_family(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        assert out["n_licks_per_bin"].shape == (5,)
        np.testing.assert_array_equal(
            out["n_licks_per_bin"], np.array([1, 1, 1, 1, 1], dtype=np.int64),
        )


# ===========================================================================
# 18-21. Cell 42 — licking dynamics
# ===========================================================================


class TestCell42:

    # 18
    def test_extract_licking_dynamics_traces_emits_four_columns(self, base_params):
        # Build 3 trials of "L" side, each with 4 peaks within apply window.
        peak_lists_L = []
        for _ in range(3):
            peak_lists_L.append(np.array([500.0, 1000.0, 1500.0, 2000.0]))
        per_side = {"L": peak_lists_L, "R": []}
        df = _extract_licking_dynamics_traces(per_side, params=base_params)
        # Columns: timebin_ms, side, lick_rate_per_t,
        # ili_within_bout_rate_per_t, p_lick_per_t, p_within_bout_per_t.
        assert set(df.columns) == {
            "timebin_ms", "side",
            "lick_rate_per_t", "ili_within_bout_rate_per_t",
            "p_lick_per_t", "p_within_bout_per_t",
        }
        # Both L and R sides should produce rows (R is empty-trials → NaN).
        sides_emitted = set(df["side"].unique())
        assert sides_emitted == {"L", "R"}

    # 19
    def test_extract_licking_dynamics_traces_bin_count_matches_apply_window(
        self, base_params,
    ):
        per_side = {"L": [np.array([500.0, 1000.0])], "R": []}
        df = _extract_licking_dynamics_traces(per_side, params=base_params)
        # apply_win [70, 5000] @ bin_ms=20 → (5000 - 70) / 20 = 246.5 → 246 bins.
        # np.arange(70, 5020, 20) → 248 edges → 247 bin centers.
        # Exact count varies on edge inclusion; we assert per-side row count
        # equals the bin count, and L+R have the same.
        n_per_side = len(df[df["side"] == "L"])
        assert n_per_side == len(df[df["side"] == "R"])
        assert n_per_side > 200  # rough sanity

    # 20
    def test_extract_licking_dynamics_reductions_bout_count_first_multi_bout(
        self, base_params,
    ):
        # Two multi-lick bouts in apply window (separated by > 300 ms gap).
        # Each bout needs >= bout.min_licks_in_bout_for_ili (=3) licks to
        # produce a valid mean_within_bout_ili_ms.
        # Bout 1: [400, 600, 800] (ILIs = [200, 200] → mean = 200 ms).
        # Bout 2: [2000, 2200, 2400].
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=5000.0,
            peak_centers_ms=[400.0, 600.0, 800.0, 2000.0, 2200.0, 2400.0],
            amplitude=30.0,
        )
        out = _extract_licking_dynamics_reductions(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        # Q8 lock: bout_count is the count of multi-lick bouts, not 0/1.
        assert out["bout_count"] == 2
        # mean_within_bout_ili_ms uses first_multi_bout (= bout 1: ILI = 200 ms).
        assert out["mean_within_bout_ili_ms"] == pytest.approx(200.0, abs=8.0)

    # 21
    def test_extract_licking_dynamics_reductions_lick_rate_uses_apply_window(
        self, base_params,
    ):
        # 5 peaks within apply window [70, 5000] → 5 / 4.93 ≈ 1.014 Hz.
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=8000.0,
            peak_centers_ms=[500.0, 1500.0, 2500.0, 3500.0, 4500.0],
            amplitude=30.0,
        )
        out = _extract_licking_dynamics_reductions(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        # apply window = [70, 5000] → duration = 4.93 s.
        expected_rate = 5.0 / 4.93
        assert out["lick_rate_hz"] == pytest.approx(expected_rate, rel=0.01)


# ===========================================================================
# 22-30. Cell 50 — angle math + per-trial scalars + own-bout + inclusion
# ===========================================================================


class TestCell50Angle:

    # 22
    def test_compute_signed_tongue_angle_zero_on_reference_line(self):
        """Tongue point along the eye→origin line should give angle ≈ 0."""
        eye_x, eye_y = 100.0, 100.0
        # Reference vector = (-100, -100) (eye → spout origin).
        # Tongue at (50, 50): v = (-50, -50) — parallel to ref → angle = 0.
        x_geom = np.array([50.0])
        y_geom = np.array([50.0])
        angle = _compute_signed_tongue_angle_deg(
            x_geom, y_geom, eye_x, eye_y, sign_flip=-1.0,
        )
        assert angle[0] == pytest.approx(0.0, abs=1e-6)

    # 23
    def test_compute_signed_tongue_angle_perpendicular(self):
        """Tongue at perpendicular direction should give |angle| ≈ 90."""
        eye_x, eye_y = 0.0, 100.0  # ref = (0, -100), pointing -y
        # Tongue at (50, 100): v = (50, 0) — perpendicular to ref → |angle|=90.
        x_geom = np.array([50.0])
        y_geom = np.array([100.0])
        angle = _compute_signed_tongue_angle_deg(
            x_geom, y_geom, eye_x, eye_y, sign_flip=-1.0,
        )
        assert abs(abs(angle[0]) - 90.0) < 1e-6

    # 24
    def test_compute_signed_tongue_angle_sign_flip_applied(self):
        """``sign_flip=-1`` should invert the sign vs ``sign_flip=+1``."""
        eye_x, eye_y = 0.0, 100.0
        x_geom = np.array([50.0, -50.0])
        y_geom = np.array([100.0, 100.0])
        angle_pos = _compute_signed_tongue_angle_deg(
            x_geom, y_geom, eye_x, eye_y, sign_flip=+1.0,
        )
        angle_neg = _compute_signed_tongue_angle_deg(
            x_geom, y_geom, eye_x, eye_y, sign_flip=-1.0,
        )
        np.testing.assert_array_almost_equal(angle_pos, -angle_neg, decimal=10)

    # 25
    def test_gaussian_smooth_nan_propagates_at_full_nan_window(self):
        # A run of all-NaN samples wider than several sigma should produce
        # NaN in the smoothed output (denominator near zero).
        n = 100
        arr = np.zeros(n, dtype=np.float64)
        arr[40:60] = np.nan  # 20-sample NaN window
        smoothed = _gaussian_smooth_nan(arr, sigma_units=1.0)
        # In the middle of the NaN run, smoothed should be NaN.
        assert np.isnan(smoothed[50])
        # Far from the NaN run, smoothed should be finite (≈ 0).
        assert np.isfinite(smoothed[5])

    # 26
    def test_extract_per_frame_angle_smooth_after_flip_order(self, base_params):
        """The smoothing operates on the post-flip angle, NOT on raw atan2.

        Test: a per-frame trace with a known sign pattern. With sign_flip
        baked inside atan2 + smoothing applied AFTER, the smoothed output
        should preserve the post-flip sign in steady-state regions.
        """
        # 100 frames, tongue oscillating across the spout midline.
        n = 1000
        x_final = np.linspace(-50.0, 50.0, n)
        y_final = np.full(n, 50.0)
        eye_x, eye_y = 0.0, 100.0
        # Run our extractor.
        params = copy.deepcopy(base_params)
        smoothed = _extract_per_frame_angle_smoothed(
            x_final, y_final, eye_x, eye_y, _SYNTH_FPS, params=params,
        )
        # Expectation: at x_final = -50, with sign_flip=-1, the angle should
        # be of the opposite sign vs at x_final = +50. The smoothed signal
        # reflects this in steady state (away from the boundary where the
        # gaussian kernel mixes signs).
        sign_flip = float(params["dlc_kinematics"]["tongue_pertrial"]["angle"]["sign_flip"])
        assert sign_flip == -1.0
        # At idx 100 (x ≈ -40) and idx 900 (x ≈ +40), signs should be opposite.
        assert smoothed[100] * smoothed[900] < 0

    # 27
    def test_extract_angle_at_lick_timestamps_linear_interp(self):
        # Per-frame angle linear ramp: angle[k] = k * 0.1 deg.
        n = 1000
        angle = np.arange(n, dtype=np.float64) * 0.1
        # Sample at t_ms = 200 ms with reward_frame_idx = 0, fps=250.
        # target_frame = 0 + 200/1000*250 = 50 → angle ≈ 5.0.
        out = _extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, reward_frame_idx=0, lick_t_ms=200.0,
        )
        assert out == pytest.approx(5.0, abs=1e-9)
        # NaN propagation: NaN lick_t_ms → NaN.
        assert np.isnan(_extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, reward_frame_idx=0, lick_t_ms=float("nan"),
        ))
        # Out-of-bounds: large lick_t_ms → NaN.
        assert np.isnan(_extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, reward_frame_idx=0, lick_t_ms=1e6,
        ))

    # 28
    def test_extract_angle_max_signed_per_lick_window_pad(self):
        # Build a per-frame angle with a +10 deg spike at frame 100 and a
        # -15 deg spike at frame 200. peak_pad_ms = 52 → 13 frames.
        n = 500
        angle = np.zeros(n, dtype=np.float64)
        angle[100] = 10.0  # signed-max within pad of frame 100
        angle[200] = -15.0  # signed-max (largest |angle|) within pad of frame 200
        # Lick t_ms (with reward_frame_idx=0, fps=250):
        # frame 100 → 400 ms; frame 200 → 800 ms.
        lick_t_ms = np.array([400.0, 800.0, np.nan, np.nan, np.nan])
        out = _extract_angle_max_signed_per_lick(
            angle, _SYNTH_FPS, reward_frame_idx=0, lick_t_peaks_ms=lick_t_ms,
            peak_pad_ms=52.0,
        )
        assert out.shape == (5,)
        assert out[0] == pytest.approx(10.0)
        assert out[1] == pytest.approx(-15.0)
        assert np.all(np.isnan(out[2:]))

    # 29 — Cell 50 own-bout scalars + Q9 new field
    def test_extract_cell50_own_bout_scalars_within_apply_window(
        self, base_params,
    ):
        # 4 peaks: 3 in apply window [70, 5000], 1 outside (at 6000 ms).
        y_t, x_t, t_ms = _make_lick_trace(
            duration_ms=8000.0,
            peak_centers_ms=[500.0, 700.0, 4000.0, 6000.0],
            amplitude=30.0,
        )
        out = _extract_cell50_own_bout_scalars(
            y_t, x_t, t_ms, _SYNTH_FPS, params=base_params,
        )
        # apply window has 3 peaks: [500, 700, 4000].
        # Bout split at 4000-700 = 3300 ms ≫ 300 ms threshold.
        # → bout 1 = [500, 700] (multi-lick), bout 2 = [4000] (single).
        assert out["n_peaks"] == 3
        assert out["n_bouts"] == 2
        assert out["n_multi_lick_bouts"] == 1
        assert out["first_peak_t_ms"] == pytest.approx(500.0, abs=8.0)
        # Q9 NEW: n_licks_in_first_multi_bout = 2 (peaks 500 + 700).
        assert out["n_licks_in_first_multi_bout"] == 2

    # 30
    def test_evaluate_session_inclusion_phase_lick_count_threshold(
        self, base_params,
    ):
        # min_phase_licks_per_session = 15 (per defaults.yaml lock).
        for n_phase_licks, expected in [(14, False), (15, True), (16, True)]:
            inc = _evaluate_session_inclusion(
                n_time_trials=10, n_first_peak_trials=10,
                n_phase_licks=n_phase_licks, n_phase_trials=10,
                params=base_params,
            )
            assert inc["phase_summary_by_lick_count"] is expected
        # Threshold echoed.
        inc = _evaluate_session_inclusion(
            n_time_trials=0, n_first_peak_trials=0,
            n_phase_licks=0, n_phase_trials=0, params=base_params,
        )
        assert inc["thresholds"]["min_phase_licks_per_session"] == 15
        assert inc["counts"]["n_phase_licks"] == 0


# ===========================================================================
# 31-32. Eye-resolver
# ===========================================================================


class TestEyeMidpointResolver:

    # 31
    def test_resolve_eye_midpoint_session_median_both_eyes_valid(
        self, base_params,
    ):
        df = _make_synthetic_eye_landmark_df(
            n_frames=200,
            L_eye_pos=(140.0, -430.0), R_eye_pos=(-120.0, -430.0),
        )
        eye_x, eye_y = _resolve_eye_midpoint_session_median(
            df, params=base_params,
        )
        # 0.5 * ((140 + -120), (-430 + -430)) = (10.0, -430.0)
        assert eye_x == pytest.approx(10.0, abs=1e-6)
        assert eye_y == pytest.approx(-430.0, abs=1e-6)

    # 31b — spout-frame check filters by likelihood (C5.6, 2026-04-29)
    def test_resolve_eye_midpoint_filters_low_lik_spout_drift(
        self, base_params,
    ):
        """Bimodal R_spout (high-lik on one side, low-lik drifted to L_spout's
        side) must NOT trip the sanity check — the centering algorithm
        used high-lik medians, so the sanity check should too.

        Synthetic: 200 frames where R_spout likelihood is HIGH (0.95) and
        positioned correctly at -78 px, but with 800 additional low-lik
        (0.4) frames placed at +75 (drifted to where L_spout sits — same
        pattern as PS55/2025-05-02). The unfiltered median falls at
        ~+45 px (off-center, would fail). The likelihood-filtered median
        correctly falls at -78 (R_spout's true location).
        """
        n_hi = 200
        n_lo = 800
        # High-lik frames (correct R_spout position).
        df_hi = _make_synthetic_eye_landmark_df(
            n_frames=n_hi,
            R_spout_pos=(-78.0, -1.0), R_spout_likelihood=0.95,
        )
        # Low-lik drift frames (R_spout DLC drifted to L_spout's location).
        df_lo = _make_synthetic_eye_landmark_df(
            n_frames=n_lo,
            R_spout_pos=(+75.0, +1.0), R_spout_likelihood=0.4,
        )
        df = pd.concat([df_hi, df_lo], ignore_index=True)
        # Sanity-check the input distribution itself: unfilt R_spout median
        # should be off-center (around +45), filtered should be at -78.
        unfilt_R_x = float(np.nanmedian(df["R_spout_x"]))
        assert unfilt_R_x > 0  # contaminated by low-lik drift
        # Now invoke the resolver — should NOT raise.
        eye_x, eye_y = _resolve_eye_midpoint_session_median(
            df, params=base_params,
        )
        assert np.isfinite(eye_x) and np.isfinite(eye_y)

    # 32
    def test_resolve_eye_midpoint_session_median_one_eye_fallback(
        self, base_params,
    ):
        # Mixed-likelihood frames: per-frame randomly low for one eye such
        # that n_both < 100 but per-eye n_L and n_R each >= 100.
        n = 250
        rng = np.random.default_rng(seed=0)
        df = _make_synthetic_eye_landmark_df(
            n_frames=n,
            L_eye_pos=(140.0, -430.0), R_eye_pos=(-120.0, -430.0),
        )
        # Drop L_eye likelihood for half the frames; drop R_eye likelihood
        # for the OTHER half. Per-eye valid = 125 each (≥ 100); intersection
        # = 0 (< 100). Fallback path triggered.
        idx = rng.permutation(n)
        df["L_eye_likelihood"] = df["L_eye_likelihood"].astype(np.float32)
        df["R_eye_likelihood"] = df["R_eye_likelihood"].astype(np.float32)
        L_low = idx[:n // 2]
        R_low = idx[n // 2:]
        df.loc[L_low, "L_eye_likelihood"] = 0.1
        df.loc[R_low, "R_eye_likelihood"] = 0.1
        eye_x, eye_y = _resolve_eye_midpoint_session_median(
            df, params=base_params,
        )
        # Per-eye fallback still produces 0.5 * (140 + -120, -430 + -430).
        assert eye_x == pytest.approx(10.0, abs=1e-6)
        assert eye_y == pytest.approx(-430.0, abs=1e-6)


# ===========================================================================
# 33-37. Driver + I/O + schema
# ===========================================================================


class TestDriverAndSchema:
    """Full-driver integration tests with synthetic parquets."""

    @staticmethod
    def _setup_session_outputs(tmp_path, animal="PS46", date=datetime.date(2025, 3, 7)):
        """Create the input parquets the driver needs.

        Returns ``(resolver, manifest, trial_events)``.
        """
        n_frames = 5000  # 20 seconds at 250 fps
        # Build a tongue trace with peaks at known reward-relative times.
        # Trial 1: reward at frame 500 (= 2 s); peaks at frame 500+125 (500 ms),
        # 500+250 (1 s), 500+375 (1.5 s) etc.
        x_final = np.zeros(n_frames, dtype=np.float64)
        y_final = np.zeros(n_frames, dtype=np.float64)
        # Synthetic per-trial peaks: trial 1 at frame 500 with peaks at +125,
        # +250 frames; trial 2 at frame 2500 with peaks at +125, +375 frames.
        for reward in (500, 2500):
            for offset in (125, 250, 375):
                center = reward + offset
                for j in range(-3, 4):
                    if 0 <= center + j < n_frames:
                        y_final[center + j] += 30.0 * (1 - abs(j) / 3.5)

        resolver = PathResolver(output_root=tmp_path)
        manifest = _make_minimal_manifest(animal=animal, date=date)

        # Tongue parquet at the resolver-derived path.
        tongue_path = resolver.interpolated_trace(
            "tongue", animal, date, variant="parquet",
        )
        _make_synthetic_tongue_parquet(
            tongue_path, n_frames, fps=_SYNTH_FPS,
            x_final=x_final, y_final=y_final,
        )
        # Eye parquet at the date-prefix-glob path.
        date_iso = date.isoformat()
        eye_dir = tmp_path / "dlc_analysis" / "centered_spout_midpoint" / animal
        eye_dir.mkdir(parents=True)
        eye_path = (
            eye_dir
            / f"video2_{date_iso}T12_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.deadbeef.parquet"
        )
        _make_synthetic_eye_landmark_parquet(eye_path, n_frames)

        trial_events = [
            TrialEvent(trial_index=0, reward_frame_idx=500, side="L"),
            TrialEvent(trial_index=1, reward_frame_idx=2500, side="R"),
        ]
        return resolver, manifest, trial_events

    # 33
    def test_build_tongue_pertrial_emits_three_files(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        assert out is not None
        assert set(out.keys()) == {
            "angle_parquet",
            "licking_dynamics_traces_parquet",
            "endpoints_json",
        }
        for name, path in out.items():
            assert path.exists(), f"{name} did not write to {path}"
            assert path.stat().st_size > 0
            # No leftover .tmp files from atomic write.
            assert not path.with_name(path.name + ".tmp").exists()

    # 34
    def test_build_tongue_pertrial_overwrite_skip_partial_rebuild(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        # First emit.
        out1 = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        assert out1 is not None
        mtimes = {k: p.stat().st_mtime_ns for k, p in out1.items()}

        # All three exist + skip → returns paths, files unchanged.
        out2 = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params, overwrite="skip",
        )
        assert out2 is not None
        for k, p in out2.items():
            assert p.stat().st_mtime_ns == mtimes[k]  # untouched

        # Delete one file → skip should still rebuild all three.
        out1["endpoints_json"].unlink()
        out3 = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params, overwrite="skip",
        )
        assert out3 is not None
        for k, p in out3.items():
            assert p.exists()

    # 35
    def test_endpoints_json_schema_locked(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        with open(out["endpoints_json"]) as f:
            payload = json.load(f)

        # Top-level schema lock.
        assert payload["schema_version"] == FEATURE_EXTRACTION_VERSION
        assert payload["animal"] == manifest.animal
        assert payload["date"] == manifest.date.isoformat()
        assert payload["n_trials"] == 2
        assert payload["trial_indices"] == [0, 1]
        assert payload["sides"] == ["L", "R"]

        # tongue.* sub-blocks present.
        assert set(payload["tongue"].keys()) == {
            "lick1_lick2_metrics",
            "peak_velocity_per_lick",
            "n_licks_family",
            "licking_dynamics_reductions",
            "tongue_angle",
            "cell50_own_bout_scalars",
        }

        # Q8 lock: licking_dynamics_reductions has 3 fields (Q9 metric moved
        # to cell50_own_bout_scalars).
        assert set(payload["tongue"]["licking_dynamics_reductions"].keys()) == {
            "bout_count", "mean_within_bout_ili_ms", "lick_rate_hz",
        }

        # Q9 lock: cell50_own_bout_scalars has 5 fields including
        # n_licks_in_first_multi_bout.
        assert set(payload["tongue"]["cell50_own_bout_scalars"].keys()) == {
            "n_peaks", "n_bouts", "n_multi_lick_bouts",
            "first_peak_t_ms", "n_licks_in_first_multi_bout",
        }

        # session_inclusion: 4 booleans + thresholds + counts.
        assert set(payload["session_inclusion"].keys()) >= {
            "time_aligned", "first_peak_aligned",
            "phase_summary_by_lick_count", "phase_summary_by_trial_count",
            "thresholds", "counts",
        }
        assert "tongue_angle_pass" not in payload["session_inclusion"]

    # 36
    def test_angle_parquet_metadata_locked(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        schema = pq.read_schema(out["angle_parquet"])
        assert {f.name for f in schema} == {"frame_idx", "angle_deg_smoothed"}
        meta_keys = {
            k.decode("utf-8")
            for k in (schema.metadata or {}).keys()
        }
        # 10 V3 keys (per kickoff §3b) + the pyarrow-emitted "pandas" key.
        expected = {
            "animal", "date", "fps", "n_frames", "center_mode",
            "eye_in_spout_frame_x", "eye_in_spout_frame_y",
            "smoothing_gaussian_sigma_ms", "angle_sign_flip",
            "feature_extraction_version", "interpolation_version",
        }
        assert expected.issubset(meta_keys)
        # Spot-check a value.
        meta = {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in (schema.metadata or {}).items()
            if k.decode("utf-8") in expected
        }
        assert meta["feature_extraction_version"] == FEATURE_EXTRACTION_VERSION
        assert meta["center_mode"] == "centered_spout_midpoint"

    # 37
    def test_traces_parquet_metadata_locked(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        schema = pq.read_schema(out["licking_dynamics_traces_parquet"])
        assert {f.name for f in schema} == {
            "timebin_ms", "side",
            "lick_rate_per_t", "ili_within_bout_rate_per_t",
            "p_lick_per_t", "p_within_bout_per_t",
        }
        meta_keys = {
            k.decode("utf-8")
            for k in (schema.metadata or {}).keys()
        }
        # Subset: 17+ V3 keys per kickoff §3c.
        expected = {
            "animal", "date", "fps", "n_trials",
            "bin_ms", "lickrate_smooth_sigma_ms", "ili_smooth_sigma_ms",
            "prob_smooth_movavg_ms", "bout_max_ili_ms", "bout_min_ili_ms",
            "min_licks_in_bout_for_ili", "min_trials_per_bin",
            "max_licks_per_trial", "apply_win_start_ms", "apply_win_end_ms",
            "feature_extraction_version", "interpolation_version",
        }
        assert expected.issubset(meta_keys)

    # 38 — sides array co-indexed with trial_indices (Task 5.0 schema add)
    def test_endpoints_json_schema_includes_sides_array(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = self._setup_session_outputs(tmp_path)
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        with open(out["endpoints_json"]) as f:
            payload = json.load(f)
        # Top-level "sides" present, length matches n_trials, all values "L"/"R".
        assert "sides" in payload
        assert len(payload["sides"]) == payload["n_trials"]
        assert len(payload["sides"]) == len(payload["trial_indices"])
        assert all(s in ("L", "R") for s in payload["sides"])
        # Co-indexed: the i-th side corresponds to trial_index i.
        for i, te in enumerate(trial_events):
            assert payload["sides"][i] == te.side


# ===========================================================================
# 38-43. Trial-events auto-derive (Task 5.0)
# ===========================================================================


class TestTrialEventsAutoDerive:
    """Cover :func:`_derive_trial_events_from_spout_behavior` end-to-end.

    Synthetic upstream products under ``tmp_path``: tongue parquet,
    licks_and_rewards NPZ, alignment template (linear ramp WS→cam).
    """

    @staticmethod
    def _setup(
        tmp_path: Path,
        *,
        animal: str = "PS46",
        date: datetime.date = datetime.date(2025, 3, 7),
        n_frames: int = 5000,
        n_ws: int = 20000,
        wavesurfer_sides_match_mouse_sides: bool = False,
        reward_L_ws: np.ndarray | None = None,
        reward_R_ws: np.ndarray | None = None,
        write_licks: bool = True,
        write_alignment: bool = True,
        slope_ws_per_camFrame: float = 4.0,
    ) -> tuple[PathResolver, SessionManifest, datetime.date, str, int]:
        resolver = PathResolver(output_root=tmp_path)
        # Tongue parquet (the helper reads n_frames from its metadata).
        tongue_path = resolver.interpolated_trace(
            "tongue", animal, date, variant="parquet",
        )
        _make_synthetic_tongue_parquet(tongue_path, n_frames)
        # Licks NPZ.
        licks_path = (
            resolver.pipeline_outputs("spout_behavior")
            / "licks_and_rewards" / animal / f"{date.strftime('%Y%m%d')}.npz"
        )
        if write_licks:
            _make_synthetic_licks_npz(
                licks_path,
                reward_L_ws=reward_L_ws,
                reward_R_ws=reward_R_ws,
                wavesurfer_sides_match_mouse_sides=(
                    wavesurfer_sides_match_mouse_sides
                ),
            )
        # Alignment template under tmp_path so the manifest's direct-path
        # plumbing is exercised (resolver.alignment_template's
        # microscope_server fallback would otherwise be hit).
        align_path = tmp_path / f"align_{animal}_{date.strftime('%Y%m%d')}.npz"
        if write_alignment:
            _make_synthetic_alignment_template_npz(
                align_path, n_ws=n_ws,
                slope_ws_per_camFrame=slope_ws_per_camFrame,
            )
        manifest = _make_minimal_manifest(
            animal=animal, date=date,
            alignment_template=align_path if write_alignment else None,
            wavesurfer_sides_match_mouse_sides=(
                wavesurfer_sides_match_mouse_sides
            ),
        )
        return resolver, manifest, date, animal, n_frames

    # 1
    def test_derive_trial_events_returns_list_of_trialevent(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, date, animal, n_frames = self._setup(tmp_path)
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        # Default fixture: 3 L + 2 R = 5 trials.
        assert isinstance(events, list)
        assert len(events) == 5
        assert all(isinstance(ev, TrialEvent) for ev in events)
        # trial_index contiguous 0..N-1.
        assert [ev.trial_index for ev in events] == list(range(5))
        # All sides in {"L", "R"}.
        assert all(ev.side in ("L", "R") for ev in events)
        # All reward_frame_idx in [0, n_frames).
        assert all(0 <= ev.reward_frame_idx < n_frames for ev in events)

    # 2 — alignment translation: WS index → cam frame
    def test_derive_trial_events_alignment_translation(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        # Slope = 4 → ws_idx 4000 maps to cam frame 1000.
        resolver, manifest, date, animal, _ = self._setup(
            tmp_path,
            reward_L_ws=np.array([4000], dtype=np.int64),
            reward_R_ws=np.array([], dtype=np.int64),
        )
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        assert len(events) == 1
        assert events[0].reward_frame_idx == 1000
        assert events[0].side == "L"

    # 3 — sides pass through (NPZ already mouse-frame regardless of
    # wavesurfer_sides_match_mouse_sides flag value)
    def test_derive_trial_events_side_in_mouse_frame(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        # Match=True case: NPZ stamped True, manifest=True. Reward_L key →
        # side "L".
        resolver, manifest, date, animal, _ = self._setup(
            tmp_path,
            wavesurfer_sides_match_mouse_sides=True,
            reward_L_ws=np.array([4000], dtype=np.int64),
            reward_R_ws=np.array([8000], dtype=np.int64),
        )
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        sides_by_frame = {ev.reward_frame_idx: ev.side for ev in events}
        assert sides_by_frame == {1000: "L", 2000: "R"}

        # Match=False case: NPZ stamped False, manifest=False. Same NPZ
        # keys → same mouse-frame sides (translation already applied at
        # NPZ emit, so 7a.3 reads them verbatim).
        date2 = datetime.date(2025, 3, 8)
        resolver2, manifest2, date2, animal2, _ = self._setup(
            tmp_path,
            date=date2,
            wavesurfer_sides_match_mouse_sides=False,
            reward_L_ws=np.array([4000], dtype=np.int64),
            reward_R_ws=np.array([8000], dtype=np.int64),
        )
        events2 = _derive_trial_events_from_spout_behavior(
            animal=animal2, date=date2,
            resolver=resolver2, manifest=manifest2,
        )
        sides_by_frame2 = {ev.reward_frame_idx: ev.side for ev in events2}
        assert sides_by_frame2 == {1000: "L", 2000: "R"}

    # 4 — missing licks NPZ → FileNotFoundError
    def test_derive_trial_events_raises_on_missing_licks_and_rewards(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, date, animal, _ = self._setup(
            tmp_path, write_licks=False,
        )
        with pytest.raises(FileNotFoundError):
            _derive_trial_events_from_spout_behavior(
                animal=animal, date=date, resolver=resolver, manifest=manifest,
            )

    # 5 — missing alignment template → FileNotFoundError
    def test_derive_trial_events_raises_on_missing_alignment_template(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, date, animal, _ = self._setup(
            tmp_path, write_alignment=False,
        )
        # On Windows host, the resolver fallback hits microscope_server which
        # may or may not actually contain the file. To make this test
        # deterministic, also clear manifest.alignment_template (already
        # None when write_alignment=False); resolver fallback target may
        # exist on the real share. Patch resolver to a non-existent path.
        # We do this by overriding the alignment_template method.
        nonexistent = tmp_path / "no_alignment_anywhere.npz"
        monkeypatch.setattr(
            resolver, "alignment_template",
            lambda animal, date, cam="cam2": nonexistent,
        )
        with pytest.raises(FileNotFoundError, match="alignment template missing"):
            _derive_trial_events_from_spout_behavior(
                animal=animal, date=date, resolver=resolver, manifest=manifest,
            )

    # 6 — reward_frame validation: in-range check + defensive ValueError branch
    def test_derive_trial_events_validates_reward_frame_in_range(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        # Place a WS reward index that maps cam_frame >= n_frames. The
        # underlying ws_samples_to_frame_indices clamps these to -1, so
        # the helper drops them silently. Verify all returned events are
        # in [0, n_frames).
        # n_frames=5000 + slope=4 → cam_frame = ws_idx / 4. WS index
        # 21000 → cam frame 5250 > n_frames=5000 → clamped to -1 → dropped.
        resolver, manifest, date, animal, n_frames = self._setup(
            tmp_path, n_frames=5000, n_ws=25000,
            reward_L_ws=np.array([4000, 21000], dtype=np.int64),
            reward_R_ws=np.array([], dtype=np.int64),
        )
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        assert len(events) == 1  # the out-of-range one was dropped
        assert events[0].reward_frame_idx == 1000
        # Defensive ValueError: monkeypatch the translator to return a
        # frame index >= n_frames (bypassing its built-in clamp).
        from stroke_orofacial.dlc_kinematics import tongue_pertrial as _tp_mod

        def _patched_translator(ws_samples, lut, n_cam_frames):
            return np.full(len(ws_samples), n_cam_frames + 5, dtype=np.int64)

        monkeypatch.setattr(
            "stroke_orofacial.dlc_spatial.reward_aligned"
            ".ws_samples_to_frame_indices",
            _patched_translator,
        )
        # Re-import path: the helper imports inside its function body.
        # Patch at the source module so the helper's local import resolves
        # to the patched function.
        with pytest.raises(ValueError, match="reward_frame_idx"):
            _tp_mod._derive_trial_events_from_spout_behavior(
                animal=animal, date=date, resolver=resolver, manifest=manifest,
            )
