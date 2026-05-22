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
from typing import Any
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
    TongueVisualBundle,
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
    Only the fields :func:`load_tone_events` consumes are populated;
    Lick_*/Reward_* are empty for these tests. Phase 8a.10.1 X1-β
    (2026-05-14): fixture key rename Reward_L/R → Tone_L/R — the
    DLC loader reads Tone_L/Tone_R post-swap-fix.
    """
    if reward_L_ws is None:
        reward_L_ws = np.array([1000, 3000, 5000], dtype=np.int64)
    if reward_R_ws is None:
        reward_R_ws = np.array([2000, 4000], dtype=np.int64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        Tone_L=reward_L_ws.astype(np.int64),
        Tone_R=reward_R_ws.astype(np.int64),
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
        # Sample at t_ms = 200 ms with tone_frame_idx = 0, fps=250.
        # target_frame = 0 + 200/1000*250 = 50 → angle ≈ 5.0.
        out = _extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, tone_frame_idx=0, lick_t_ms=200.0,
        )
        assert out == pytest.approx(5.0, abs=1e-9)
        # NaN propagation: NaN lick_t_ms → NaN.
        assert np.isnan(_extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, tone_frame_idx=0, lick_t_ms=float("nan"),
        ))
        # Out-of-bounds: large lick_t_ms → NaN.
        assert np.isnan(_extract_angle_at_lick_timestamps(
            angle, _SYNTH_FPS, tone_frame_idx=0, lick_t_ms=1e6,
        ))

    # 28
    def test_extract_angle_max_signed_per_lick_window_pad(self):
        # Build a per-frame angle with a +10 deg spike at frame 100 and a
        # -15 deg spike at frame 200. peak_pad_ms = 52 → 13 frames.
        n = 500
        angle = np.zeros(n, dtype=np.float64)
        angle[100] = 10.0  # signed-max within pad of frame 100
        angle[200] = -15.0  # signed-max (largest |angle|) within pad of frame 200
        # Lick t_ms (with tone_frame_idx=0, fps=250):
        # frame 100 → 400 ms; frame 200 → 800 ms.
        lick_t_ms = np.array([400.0, 800.0, np.nan, np.nan, np.nan])
        out = _extract_angle_max_signed_per_lick(
            angle, _SYNTH_FPS, tone_frame_idx=0, lick_t_peaks_ms=lick_t_ms,
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
            TrialEvent(trial_index=0, tone_frame_idx=500, side="L"),
            TrialEvent(trial_index=1, tone_frame_idx=2500, side="R"),
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
        # All tone_frame_idx in [0, n_frames).
        assert all(0 <= ev.tone_frame_idx < n_frames for ev in events)

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
        assert events[0].tone_frame_idx == 1000
        assert events[0].side == "L"

    # 3 — sides pass through (NPZ already mouse-frame regardless of
    # wavesurfer_sides_match_mouse_sides flag value)
    def test_derive_trial_events_side_in_mouse_frame(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        # Match=True case: NPZ stamped True, manifest=True. Tone_L key
        # (post X1-β fixture rename) → side "L".
        resolver, manifest, date, animal, _ = self._setup(
            tmp_path,
            wavesurfer_sides_match_mouse_sides=True,
            reward_L_ws=np.array([4000], dtype=np.int64),
            reward_R_ws=np.array([8000], dtype=np.int64),
        )
        events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
        sides_by_frame = {ev.tone_frame_idx: ev.side for ev in events}
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
        sides_by_frame2 = {ev.tone_frame_idx: ev.side for ev in events2}
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
        # Phase 7-pre-alignment-templates Task 4 cutover: consumer now
        # reads via alignment_template_for_reading (prefer-new-then-
        # legacy). This test asserts the CONSUMER's own raise
        # ("alignment template missing"), not the resolver's. To force
        # the consumer's existence-check raise rather than the
        # resolver's FileNotFoundError, return a non-existent path from
        # for_reading instead of raising — the consumer then runs its
        # own `not align_path.exists()` check and produces its own error
        # message. Both the legacy and for_reading overrides return
        # non-existent so the consumer hits the missing case
        # regardless of which one is called.
        monkeypatch.setattr(
            resolver, "alignment_template_legacy_read",
            lambda animal, date, cam="cam2", *, session_suffix=None: nonexistent,
        )
        monkeypatch.setattr(
            resolver, "alignment_template_for_reading",
            lambda animal, date, cam="cam2", *, session_suffix=None: nonexistent,
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
        assert events[0].tone_frame_idx == 1000
        # Defensive ValueError: monkeypatch the translator to return a
        # frame index >= n_frames (bypassing its built-in clamp).
        from stroke_orofacial.dlc_kinematics import tongue_pertrial as _tp_mod

        def _patched_translator(ws_samples, lut, n_cam_frames):
            return np.full(len(ws_samples), n_cam_frames + 5, dtype=np.int64)

        monkeypatch.setattr(
            "stroke_orofacial.dlc_spatial.tone_aligned"
            ".ws_samples_to_frame_indices",
            _patched_translator,
        )
        # Re-import path: the helper imports inside its function body.
        # Patch at the source module so the helper's local import resolves
        # to the patched function.
        with pytest.raises(ValueError, match="tone_frame_idx"):
            _tp_mod._derive_trial_events_from_spout_behavior(
                animal=animal, date=date, resolver=resolver, manifest=manifest,
            )


# ===========================================================================
# Phase 7a.4 Task 3.5: visual bundle additive helper
# ===========================================================================


class TestVisualBundle:
    """Phase 7a.4 Task 3.5 — :func:`build_tongue_visual_bundle` exposes the
    in-memory per-trial DataFrames that the Cell 50 plot families
    (tongue_visual.py, Task 4) consume. Bit-identical compute path to
    :func:`build_tongue_pertrial` for shared fields (angle_per_frame +
    metadata scalars); the bundle adds NEW intermediate DataFrames
    (df_trials, df_bouts, df_phase) computed in the same trial loop."""

    def test_returns_correct_dataclass_shape(
        self, monkeypatch, tmp_path, base_params,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import (
            TongueVisualBundle,
            build_tongue_visual_bundle,
        )
        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
        )
        assert isinstance(bundle, TongueVisualBundle)
        assert isinstance(bundle.df_trials, pd.DataFrame)
        assert isinstance(bundle.df_bouts, pd.DataFrame)
        assert isinstance(bundle.df_phase, pd.DataFrame)
        assert isinstance(bundle.angle_per_frame, pd.DataFrame)
        assert isinstance(bundle.metadata, dict)
        # df_trials has one row per trial — synthetic fixture has 2 trials.
        assert len(bundle.df_trials) == 2
        # df_trials carries the per-trial array columns (object-dtype).
        for col in (
            "t_ms", "y_snip", "angle_snip",
            "angle_allbouts_snip", "angle_firstbout_snip",
            "angle_firstmulti_snip",
            "t_firstpeak_align_ms", "angle_firstpeak_snip",
        ):
            assert col in bundle.df_trials.columns, col
        # angle_per_frame schema lock: 2 cols, n_frames rows.
        assert set(bundle.angle_per_frame.columns) == {
            "frame_idx", "angle_deg_smoothed",
        }
        # metadata has the expected keys.
        for key in (
            "animal", "date", "fps", "n_frames",
            "eye_in_spout_frame_x", "eye_in_spout_frame_y",
            "angle_sign_flip", "smoothing_gaussian_sigma_ms",
            "feature_extraction_version", "interpolation_version",
            "plot_win_ms", "detect_win_ms", "first_peak_align_win_ms",
            "n_phase_bins", "max_licks_per_trial",
        ):
            assert key in bundle.metadata, key

    def test_bit_identical_metadata_and_angle_to_emit_set(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Bit-identical-compute lock: shared fields between bundle and
        emit set (angle_per_frame DataFrame + metadata scalars) must
        match exactly. Run build_tongue_pertrial first (which writes the
        emit set), then build_tongue_visual_bundle on the same inputs,
        and compare angle_per_frame element-wise + metadata key-by-key."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import build_tongue_visual_bundle

        # Emit set (writes 3 files).
        out = build_tongue_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        with open(out["endpoints_json"]) as f:
            payload = json.load(f)
        emitted_meta = payload["metadata"]
        emitted_angle = pq.read_table(str(out["angle_parquet"])).to_pandas()

        # Bundle (same inputs, same params).
        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
        )

        # angle_per_frame DataFrames must be element-wise identical.
        pd.testing.assert_frame_equal(
            bundle.angle_per_frame,
            emitted_angle,
            check_exact=True,
            check_like=True,
        )
        # Shared metadata scalars must match exactly.
        for key in (
            "fps", "n_frames",
            "eye_in_spout_frame_x", "eye_in_spout_frame_y",
            "angle_sign_flip", "smoothing_gaussian_sigma_ms",
            "feature_extraction_version", "interpolation_version",
        ):
            assert bundle.metadata[key] == emitted_meta[key], key

    def test_does_not_write_files(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Bundle helper is pure compute — no on-disk artifacts
        produced. Verified by snapshotting the output tree before and
        after the call (the inputs were already written by
        _setup_session_outputs; the bundle helper must not add anything
        under <output_root>/dlc_kinematics/)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import build_tongue_visual_bundle

        kinematics_root = tmp_path / "dlc_kinematics"
        before = (
            sorted(kinematics_root.rglob("*"))
            if kinematics_root.exists() else []
        )
        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
        )
        after = (
            sorted(kinematics_root.rglob("*"))
            if kinematics_root.exists() else []
        )
        assert before == after, (
            f"build_tongue_visual_bundle wrote unexpected files: "
            f"{set(after) - set(before)}"
        )
        # And the bundle is non-empty (sanity).
        assert len(bundle.df_trials) > 0

    def test_default_params_uses_defaults_yaml(
        self, monkeypatch, tmp_path,
    ):
        """Passing ``params=None`` resolves to the loaded defaults.yaml
        block (mirror of build_tongue_pertrial's behavior)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import build_tongue_visual_bundle

        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=None,
        )
        # Bundle metadata reflects the on-disk defaults.yaml values.
        defaults = load_defaults()
        expected_n_phase_bins = int(
            defaults["dlc_kinematics"]["tongue_pertrial"]["phase"]["n_phase_bins"]
        )
        expected_plot_win = list(
            defaults["dlc_kinematics"]["tongue_visual"]["bundle"]["plot_win_ms"]
        )
        assert bundle.metadata["n_phase_bins"] == expected_n_phase_bins
        assert bundle.metadata["plot_win_ms"] == expected_plot_win

    def test_phase_assignment_places_peaks_at_0_5_not_at_boundary(self):
        """C5.5 (2026-04-30) regression: legacy convention places peaks
        at phase=0.5 (peak protrusion), midway between consecutive peaks
        at phase=0.0 (retracted state). A peak frame should map to
        phase ∈ [0.45, 0.55], NOT 0 or 1.

        Direct unit test of ``_assign_phase_peak_to_peak_shifted`` —
        passing pre-known peak frame indices into a phase array sized to
        cover the peaks. The pre-fix bug caused peaks to land at
        phase ≈ 0 or 1 because peak_indices were yseg-local but the
        phase array was trial-slice-local (off by ``i_lo`` =
        detect_win_ms[0] in frames).
        """
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            _assign_phase_peak_to_peak_shifted,
        )
        # Synthetic: 3 peaks at frames 100, 200, 300; phase array length 400.
        peak_indices = np.array([100, 200, 300], dtype=np.int64)
        phase = _assign_phase_peak_to_peak_shifted(400, peak_indices)
        # At each peak frame, phase must be ≈ 0.5.
        for peak_frame in peak_indices:
            assert 0.45 <= phase[peak_frame] <= 0.55, (
                f"phase[{peak_frame}] = {phase[peak_frame]:.3f} "
                f"(expected ≈ 0.5)"
            )
        # At midpoints between consecutive peaks (frames 150, 250),
        # phase must be ≈ 0.0 (legacy "retracted" position).
        for midpoint in (150, 250):
            assert (
                0.0 <= phase[midpoint] <= 0.05
                or 0.95 <= phase[midpoint] <= 1.0
            ), (
                f"phase[{midpoint}] = {phase[midpoint]:.3f} "
                f"(expected ≈ 0.0 — midpoint between peaks)"
            )
        # Outside multi-bout interval (before peak_0, after peak_2),
        # phase is NaN.
        assert np.isnan(phase[50]), "frame before first peak must be NaN"
        assert np.isnan(phase[350]), "frame after last peak must be NaN"

    def test_visual_bundle_peaks_in_df_phase_land_at_0_5(
        self, monkeypatch, tmp_path, base_params,
    ):
        """C5.5 (2026-04-30) integration regression: build a real bundle
        from synthetic upstream parquets and verify that for each
        detected peak in ``df_bouts`` (per-peak rows), the corresponding
        phase value at that peak's frame in ``df_phase`` is ≈ 0.5.

        Catches the off-by-i_lo coordinate bug end-to-end (would not
        trip the unit test above, since that test only exercises the
        phase-assignment helper directly).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import build_tongue_visual_bundle

        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
        )
        if bundle.df_phase.empty or bundle.df_bouts.empty:
            pytest.skip("synthetic fixture has no multi-lick bouts to test")
        # Each per-peak row in df_bouts has peak_t_ms set. Match the
        # closest df_phase row (by t_ms) and verify its phase ≈ 0.5.
        peak_rows = bundle.df_bouts[bundle.df_bouts["peak_t_ms"].notna()]
        if peak_rows.empty:
            pytest.skip("no per-peak rows in df_bouts")
        n_checked = 0
        for _, peak in peak_rows.iterrows():
            side = peak["side"]
            trial_index = int(peak["trial_index"])
            peak_t_ms = float(peak["peak_t_ms"])
            phase_for_trial = bundle.df_phase[
                (bundle.df_phase["side"] == side)
                & (bundle.df_phase["trial_index"] == trial_index)
            ]
            if phase_for_trial.empty:
                continue
            # Closest phase-row to peak_t_ms.
            closest_idx = (phase_for_trial["t_ms"] - peak_t_ms).abs().idxmin()
            closest = phase_for_trial.loc[closest_idx]
            t_diff = abs(float(closest["t_ms"]) - peak_t_ms)
            if t_diff > 4.0 / _SYNTH_FPS * 1000.0:  # > 1 frame off
                continue
            ph = float(closest["phase"])
            assert 0.4 <= ph <= 0.6, (
                f"peak at trial={trial_index} side={side} t={peak_t_ms:.1f}ms: "
                f"phase = {ph:.3f} (expected ≈ 0.5)"
            )
            n_checked += 1
        assert n_checked > 0, "no peaks could be cross-referenced to df_phase"

    def test_visual_bundle_peak_angle_matches_angle_snip(
        self, monkeypatch, tmp_path, base_params,
    ):
        """C5.5 (2026-04-30) regression: each per-peak row in
        ``df_bouts`` must carry ``peak_angle_deg`` equal to
        ``angle_snip`` of the SAME trial at ``t_ms == peak_t_ms``.

        Pre-fix bug: ``peak_angle_deg`` was looked up via
        ``angle_snip[peak_local_idx]`` where ``peak_local_idx`` was
        yseg-local instead of trial-slice-local. The QC plot's peak
        markers (drawn at ``(peak_t_ms, peak_angle_deg)``) consequently
        floated off the angle line by a fixed frame-offset.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver, manifest, trial_events = (
            TestDriverAndSchema._setup_session_outputs(tmp_path)
        )
        from stroke_orofacial.dlc_kinematics import build_tongue_visual_bundle

        bundle = build_tongue_visual_bundle(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
        )
        peak_rows = bundle.df_bouts[bundle.df_bouts["peak_t_ms"].notna()]
        if peak_rows.empty:
            pytest.skip("synthetic fixture has no per-peak rows")
        n_checked = 0
        max_dev = 0.0
        for _, peak in peak_rows.iterrows():
            trial_index = int(peak["trial_index"])
            side = peak["side"]
            peak_t_ms = float(peak["peak_t_ms"])
            recorded_angle = float(peak["peak_angle_deg"])
            trow = bundle.df_trials[
                (bundle.df_trials["side"] == side)
                & (bundle.df_trials["trial_index"] == trial_index)
            ]
            if trow.empty:
                continue
            t_arr = np.asarray(trow.iloc[0]["t_ms"], dtype=np.float64)
            angle_arr = np.asarray(
                trow.iloc[0]["angle_snip"], dtype=np.float64,
            )
            # Find the closest frame to peak_t_ms (one frame ≈ 1000/fps ms).
            closest_idx = int(np.argmin(np.abs(t_arr - peak_t_ms)))
            t_diff = abs(float(t_arr[closest_idx]) - peak_t_ms)
            if t_diff > 1000.0 / float(bundle.metadata["fps"]):
                continue
            angle_at_closest = float(angle_arr[closest_idx])
            if (not np.isfinite(angle_at_closest)
                    or not np.isfinite(recorded_angle)):
                continue
            dev = abs(angle_at_closest - recorded_angle)
            max_dev = max(max_dev, dev)
            n_checked += 1
        if n_checked == 0:
            pytest.skip("no peaks cross-referenceable to angle_snip")
        # Pre-fix bug: tens-of-degrees deviation (frame offset by i_lo).
        # Post-fix: < 1° (single-frame jitter).
        assert max_dev < 1.0, (
            f"peak_angle_deg deviates from angle_snip[peak_frame] by "
            f"max {max_dev:.2f}° (expected < 1°)"
        )

    def test_pertrial_core_result_is_frozen(self):
        """Defensive: _PertrialCoreResult and TongueVisualBundle are
        frozen so callers cannot accidentally mutate the shared core
        return after construction."""
        from dataclasses import FrozenInstanceError

        from stroke_orofacial.dlc_kinematics import (
            TonguePertrialResult,
            TongueVisualBundle,
        )
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            _PertrialCoreResult,
        )
        empty_df = pd.DataFrame()
        tp = TonguePertrialResult(
            angle_per_frame=empty_df,
            licking_dynamics_traces=empty_df,
            endpoints={},
            angle_metadata={},
            licking_dynamics_metadata={},
        )
        vb = TongueVisualBundle(
            df_trials=empty_df, df_bouts=empty_df, df_phase=empty_df,
            angle_per_frame=empty_df, metadata={},
        )
        core = _PertrialCoreResult(tongue_pertrial=tp, visual_bundle=vb)
        with pytest.raises(FrozenInstanceError):
            core.tongue_pertrial = tp  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            vb.df_trials = empty_df  # type: ignore[misc]


# ===========================================================================
# Phase 7a.4-cross-session-angle Addenda #9 + #10:
# centered-on-peak phase row builders
# ===========================================================================


def _make_centered_phase_test_bundle(
    trial_specs: "list[dict[str, Any]]",
    *,
    fps: float = 250.0,
    n_phase_bins: int = 36,
    plot_win_ms: tuple[float, float] = (-180.0, 1500.0),
) -> "TongueVisualBundle":
    """Build a minimal TongueVisualBundle for centered-phase helper tests.

    Each ``trial_specs`` entry is a dict with keys:
      - ``trial_index`` (int)
      - ``side`` (str: "L" or "R")
      - ``bouts``: list of {``peak_t_ms``: list[float]} — one entry per
        bout. Single-element lists model isolated-lick bouts; ≥2-element
        lists model multi-bouts.
      - ``angle_at_peak``: optional dict mapping peak_t_ms → angle_deg
        for the per-frame trace at peak frames; defaults to 0.0.

    Builds a per-trial ``t_ms`` axis at ``fps`` covering ``plot_win_ms``,
    and an ``angle_snip`` array that is finite (= 0.0 by default, with
    the angle-at-peak overrides applied at the closest frames). Builds
    df_bouts with the legacy mixed-row schema (one bout-summary row per
    bout + one per-peak row per peak). Other df_phase / metadata fields
    are populated minimally for the helper signature.
    """
    pre_f = max(0, int(np.floor(-plot_win_ms[0] / 1000.0 * fps)))
    post_f = max(0, int(np.ceil(plot_win_ms[1] / 1000.0 * fps)))
    snip_len = pre_f + post_f + 1
    t_ms = (np.arange(-pre_f, post_f + 1, dtype=np.float64) / fps) * 1000.0

    trial_rows: list[dict[str, Any]] = []
    bout_rows: list[dict[str, Any]] = []
    for spec in trial_specs:
        side = str(spec["side"])
        trial_idx = int(spec["trial_index"])
        bouts = spec["bouts"]
        angle_at_peak: dict[float, float] = spec.get("angle_at_peak", {})

        angle_arr = np.zeros(snip_len, dtype=np.float64)
        # Plant per-peak angle values at the closest frame.
        for bt in bouts:
            for pt in bt["peak_t_ms"]:
                if pt in angle_at_peak:
                    fr_idx = int(np.argmin(np.abs(t_ms - pt)))
                    angle_arr[fr_idx] = float(angle_at_peak[pt])
        # df_trials: minimal columns the helpers consume + a few the
        # bundle dataclass doc names.
        trial_rows.append({
            "side": side,
            "trial_index": trial_idx,
            "n_peaks": int(sum(len(bt["peak_t_ms"]) for bt in bouts)),
            "n_bouts": int(len(bouts)),
            "n_multi_lick_bouts": int(sum(
                1 for bt in bouts if len(bt["peak_t_ms"]) >= 2
            )),
            "first_peak_t_ms": (
                float(bouts[0]["peak_t_ms"][0]) if bouts else float("nan")
            ),
            "t_ms": t_ms.copy(),
            "y_snip": np.zeros(snip_len),
            "angle_snip": angle_arr,
            "angle_allbouts_snip": angle_arr.copy(),
            "angle_firstbout_snip": angle_arr.copy(),
            "angle_firstmulti_snip": angle_arr.copy(),
            "t_firstpeak_align_ms": np.zeros(10),
            "angle_firstpeak_snip": np.zeros(10),
        })

        # df_bouts: bout-summary + per-peak rows.
        multi_rank_counter = 0
        for bout_idx, bt in enumerate(bouts):
            peaks = bt["peak_t_ms"]
            is_multi = len(peaks) >= 2
            multi_rank = (
                float(multi_rank_counter) if is_multi else float("nan")
            )
            if is_multi:
                multi_rank_counter += 1
            bout_rows.append({
                "side": side,
                "trial_index": trial_idx,
                "bout_idx": bout_idx,
                "bout_rank": bout_idx,
                "multi_bout_rank": multi_rank,
                "n_peaks": int(len(peaks)),
                "bout_t0_ms": float(peaks[0] - 50.0),
                "bout_t1_ms": float(peaks[-1] + 50.0),
                "peak_t0_ms": float(peaks[0]) if len(peaks) >= 1 else float("nan"),
                "peak_t1_ms": float(peaks[1]) if len(peaks) >= 2 else float("nan"),
                "peak_y0": 0.0, "peak_angle0": 0.0,
                "peak_y1": 0.0, "peak_angle1": 0.0,
                "peak_t_ms": float("nan"),
                "peak_y": float("nan"),
                "peak_x": float("nan"),
                "peak_angle_deg": float("nan"),
            })
            for pt in peaks:
                bout_rows.append({
                    "side": side,
                    "trial_index": trial_idx,
                    "bout_idx": bout_idx,
                    "bout_rank": bout_idx,
                    "multi_bout_rank": multi_rank,
                    "n_peaks": int(len(peaks)),
                    "bout_t0_ms": float(peaks[0] - 50.0),
                    "bout_t1_ms": float(peaks[-1] + 50.0),
                    "peak_t0_ms": float("nan"),
                    "peak_t1_ms": float("nan"),
                    "peak_y0": float("nan"),
                    "peak_angle0": float("nan"),
                    "peak_y1": float("nan"),
                    "peak_angle1": float("nan"),
                    "peak_t_ms": float(pt),
                    "peak_y": 0.0,
                    "peak_x": 0.0,
                    "peak_angle_deg": float(angle_at_peak.get(pt, 0.0)),
                })

    df_trials = pd.DataFrame(trial_rows)
    df_bouts = pd.DataFrame(bout_rows)
    df_phase = pd.DataFrame()  # not consumed by centered helpers

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
    }
    return TongueVisualBundle(
        df_trials=df_trials,
        df_bouts=df_bouts,
        df_phase=df_phase,
        angle_per_frame=pd.DataFrame(),
        metadata=metadata,
    )


class TestBuildFirstLickCenteredPhaseRows:
    """Phase 7a.4-cross-session-angle Addendum #9 (2026-05-04) — centered
    on peak[0] of the first multi-bout per (trial, side); ILI = peak[1]
    - peak[0]; window (peak[0] - ILI/2, peak[0] + ILI/2); peak[0] lands
    at phase=0.5.
    """

    def test_peak_lands_at_phase_0_5(self):
        """A frame at peak[0]'s time should map to phase ≈ 0.5 (= the
        defining property of the centered convention)."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
                "angle_at_peak": {200.0: -10.0},  # warming-up first lick
            },
        ])
        out = build_first_lick_centered_phase_rows(bundle, ili_source="real_only")
        # ILI = 100, window = [150, 250]; peak[0] at t=200 → phase = 0.5
        at_peak = out[np.isclose(out["t_ms"], 200.0)]
        assert len(at_peak) == 1
        assert at_peak.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)
        # angle_deg at that frame should be the planted -10.0
        assert at_peak.iloc[0]["angle_deg"] == pytest.approx(-10.0)
        # peak_t_ms column carries the centered peak's time
        assert at_peak.iloc[0]["peak_t_ms"] == pytest.approx(200.0)

    def test_window_excludes_frames_outside_ILI_centered_range(self):
        """ILI = 100 (peaks at 200, 300); window = [150, 250]. Frames at
        t=100 and t=300 are outside; t=160 (in window) is included."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        out = build_first_lick_centered_phase_rows(bundle, ili_source="real_only")
        # All emitted t_ms values must be in [150, 250]
        assert (out["t_ms"] >= 150.0 - 0.01).all()
        assert (out["t_ms"] <= 250.0 + 0.01).all()

    def test_skips_isolated_lick_only_trials(self):
        """Trial with only single-lick bouts (no multi-bout) → no rows
        per Addendum #5 Option α."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [400.0]}],   # isolated lick
            },
        ])
        out = build_first_lick_centered_phase_rows(bundle, ili_source="real_only")
        assert out.empty

    def test_per_trial_per_side_isolation(self):
        """Each (trial, side) gets its own peak[0] window; trial 0's
        window doesn't leak into trial 1's filter."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0]}],
            },
            {
                "trial_index": 1, "side": "R",
                "bouts": [{"peak_t_ms": [600.0, 700.0]}],
            },
        ])
        out = build_first_lick_centered_phase_rows(bundle, ili_source="real_only")
        # Both trials contribute rows; each trial's peak_t_ms must
        # match its own peak[0]. (Use np.isclose for the float
        # comparison — pytest.approx isn't a vector predicate.)
        peak_ts = sorted(out["peak_t_ms"].unique().tolist())
        assert peak_ts == [200.0, 600.0]
        # No row from trial 0 has peak_t_ms = 600 (cross-leak check)
        trial0 = out[out["trial_index"] == 0]
        assert (trial0["peak_t_ms"] == 200.0).all()

    def test_empty_bundle(self):
        """Empty df_trials and df_bouts → empty centered DataFrame with
        the expected columns."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        empty = TongueVisualBundle(
            df_trials=pd.DataFrame(), df_bouts=pd.DataFrame(),
            df_phase=pd.DataFrame(), angle_per_frame=pd.DataFrame(),
            metadata={"n_phase_bins": 36},
        )
        out = build_first_lick_centered_phase_rows(
            empty, ili_source="real_only",
        )
        assert out.empty
        # Expected columns are present even on empty result
        for col in (
            "side", "trial_index", "peak_t_ms", "t_ms", "phase",
            "phase_bin", "phase_bin_center", "angle_deg",
        ):
            assert col in out.columns


class TestBuildAllLicksCenteredPhaseRows:
    """Phase 7a.4-cross-session-angle Addendum #10 (2026-05-04) — every
    peak in every multi-bout per (trial, side); each peak ``p[i]``
    centered with forward ILI = ``p[i+1] - p[i]``; LAST peak per bout
    is dropped (no synthetic-ILI fallback).
    """

    def test_emits_one_cycle_per_peak_except_last_in_bout(self):
        """3 peaks in one multi-bout → 2 cycles emitted (peaks 0 and 1
        center their cycles; peak 2 is the last in bout, dropped)."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
                "angle_at_peak": {
                    200.0: -10.0, 300.0: 5.0, 400.0: 5.0,
                },
            },
        ])
        out = build_all_licks_centered_phase_rows(bundle, ili_source="real_only")
        # peak_t_ms values rendered: 200 and 300; 400 dropped
        peak_ts_rendered = sorted(out["peak_t_ms"].unique().tolist())
        assert peak_ts_rendered == [200.0, 300.0]
        # Each rendered peak lands at phase=0.5 in its own cycle
        for pt in peak_ts_rendered:
            at_peak = out[
                np.isclose(out["t_ms"], pt) & (out["peak_t_ms"] == pt)
            ]
            assert len(at_peak) == 1
            assert at_peak.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)

    def test_handles_multiple_multi_bouts_in_one_trial(self):
        """Trial with two multi-bouts (3 peaks each, ILI=100) →
        2 + 2 = 4 cycles emitted (last peak per bout dropped twice)."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [
                    {"peak_t_ms": [200.0, 300.0, 400.0]},
                    {"peak_t_ms": [800.0, 900.0, 1000.0]},
                ],
            },
        ])
        out = build_all_licks_centered_phase_rows(bundle, ili_source="real_only")
        peak_ts_rendered = sorted(out["peak_t_ms"].unique().tolist())
        # 200 + 300 from bout 0; 800 + 900 from bout 1; 400 + 1000 dropped
        assert peak_ts_rendered == [200.0, 300.0, 800.0, 900.0]

    def test_excludes_isolated_lick_bouts(self):
        """Single-peak bouts (multi_bout_rank == NaN) contribute nothing
        — phase requires ≥2 peaks per Addendum #5 Option α."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [
                    {"peak_t_ms": [200.0, 300.0]},   # multi-bout: 1 cycle
                    {"peak_t_ms": [600.0]},          # isolated: skipped
                    {"peak_t_ms": [800.0, 900.0]},   # multi-bout: 1 cycle
                ],
            },
        ])
        out = build_all_licks_centered_phase_rows(bundle, ili_source="real_only")
        # Two multi-bouts × (n_peaks - 1) cycles each = 1 + 1 = 2
        peak_ts_rendered = sorted(out["peak_t_ms"].unique().tolist())
        assert peak_ts_rendered == [200.0, 800.0]
        # Confirm 600 (isolated) is absent
        assert (out["peak_t_ms"] != 600.0).all()

    def test_last_peak_per_bout_dropped(self):
        """5-peak multi-bout → 4 cycles (peaks 0-3); peak 4 dropped."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        peak_ts = [200.0, 300.0, 400.0, 500.0, 600.0]
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": peak_ts}],
            },
        ])
        out = build_all_licks_centered_phase_rows(bundle, ili_source="real_only")
        rendered = sorted(out["peak_t_ms"].unique().tolist())
        assert rendered == peak_ts[:-1]   # 600 dropped

    def test_empty_bundle(self):
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        empty = TongueVisualBundle(
            df_trials=pd.DataFrame(), df_bouts=pd.DataFrame(),
            df_phase=pd.DataFrame(), angle_per_frame=pd.DataFrame(),
            metadata={"n_phase_bins": 36},
        )
        out = build_all_licks_centered_phase_rows(
            empty, ili_source="real_only",
        )
        assert out.empty


class TestBuildFirstNLicksCenteredPhaseRows:
    """Phase 7a.4-cross-session-angle Addendum #11 Part A (2026-05-04):
    parameterized first-N-licks centered-phase builder. Each peak[i]
    for i in [0, n_peaks - 1] occupies its own [i, i + 1] cycle with
    peak[i] at x = i + 0.5; cycle width = peak[i + 1] - peak[i].
    """

    def test_each_peak_centered_in_its_own_cycle(self):
        """3 peaks at t=200, 300, 400 (ILI=100 throughout) with N=2:
        peak[0] at x=0.5 (cycle [0, 1]); peak[1] at x=1.5 (cycle
        [1, 2])."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        out = build_first_n_licks_centered_phase_rows(bundle, n_peaks=2, ili_source="real_only")
        # Peak[0] frame at t=200 → x = 0.5
        at_p0 = out[
            np.isclose(out["t_ms"], 200.0)
            & (out["peak_t_ms"] == 200.0)
        ]
        assert len(at_p0) == 1
        assert at_p0.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)
        # Peak[1] frame at t=300 → x = 1.5
        at_p1 = out[
            np.isclose(out["t_ms"], 300.0)
            & (out["peak_t_ms"] == 300.0)
        ]
        assert len(at_p1) == 1
        assert at_p1.iloc[0]["phase"] == pytest.approx(1.5, abs=1e-6)

    def test_x_span_within_0_to_n_peaks(self):
        """All emitted ``phase`` values must be in ``[0, n_peaks]``."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        out = build_first_n_licks_centered_phase_rows(bundle, n_peaks=2, ili_source="real_only")
        assert (out["phase"] >= -1e-9).all()
        assert (out["phase"] <= 2.0 + 1e-9).all()

    def test_skips_trials_with_too_few_peaks(self):
        """Trial with only 2 peaks (no peak[2] to define ILI[1]) and
        N=2 → contributes nothing per Addendum #11 Part A lock."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0]}],   # only 2 peaks
            },
        ])
        out = build_first_n_licks_centered_phase_rows(bundle, n_peaks=2, ili_source="real_only")
        assert out.empty

    def test_skips_isolated_lick_only_trials(self):
        """Trial with only single-lick bouts → no rows."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [400.0]}],
            },
        ])
        out = build_first_n_licks_centered_phase_rows(bundle, n_peaks=2, ili_source="real_only")
        assert out.empty

    def test_n_peaks_must_be_at_least_2(self):
        """N=1 is degenerate — raises ValueError."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([])
        with pytest.raises(ValueError):
            build_first_n_licks_centered_phase_rows(bundle, n_peaks=1)

    def test_emits_n_peaks_cycles_per_qualifying_trial(self):
        """Trial with 4 peaks and N=3 → 3 cycles emitted (peaks 0, 1,
        2 each centered; peak[3] supplies the final ILI's right
        edge)."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0, 500.0]}],
            },
        ])
        out = build_first_n_licks_centered_phase_rows(
            bundle, n_peaks=3, ili_source="real_only",
        )
        rendered = sorted(out["peak_t_ms"].unique().tolist())
        assert rendered == [200.0, 300.0, 400.0]   # peak[3]=500 dropped


# ===========================================================================
# Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04):
# synthetic ILI for isolated licks + last-peak-of-multi-bout
# ===========================================================================


class TestSyntheticILIInCenteredPhaseHelpers:
    """Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04):
    centered-phase helpers gain a ``synthetic_ili_ms`` kwarg that
    enables isolated-lick contribution + last-peak-of-multi-bout
    fallback. ``synthetic_ili_ms=None`` (default) preserves the
    legacy multi-bout-only behaviour.
    """

    def test_first_lick_includes_isolated_only_trial_with_synthetic_ili(self):
        """Trial with only ONE peak (isolated lick) → with
        ``synthetic_ili_ms=100``, contributes a centered-on-peak
        cycle of width 100 ms. Without (None), contributes nothing."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [400.0]}],
                "angle_at_peak": {400.0: -8.0},
            },
        ])
        # ili_source="real_only" (= legacy / multi-bout-only):
        # empty (no multi-bout to anchor a cycle).
        out_none = build_first_lick_centered_phase_rows(
            bundle, ili_source="real_only",
        )
        assert out_none.empty
        # ili_source="hybrid" + synthetic ILI: trial contributes;
        # peak at x=0.5.
        out_synth = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=100.0, ili_source="hybrid",
        )
        assert not out_synth.empty
        at_peak = out_synth[np.isclose(out_synth["t_ms"], 400.0)]
        assert len(at_peak) == 1
        assert at_peak.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)
        assert at_peak.iloc[0]["angle_deg"] == pytest.approx(-8.0)

    def test_first_lick_uses_real_ili_when_forward_neighbour_exists(self):
        """Trial with isolated bout AND a separate multi-bout: the
        chronologically first peak is the isolated one. Its forward
        neighbour (first peak of the next multi-bout) supplies the
        REAL ILI; synthetic_ili_ms is only used if no neighbour
        exists.
        """
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [
                    {"peak_t_ms": [200.0]},                # isolated
                    {"peak_t_ms": [600.0, 700.0, 800.0]},  # multi
                ],
            },
        ])
        out = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=999.0, ili_source="hybrid",
        )
        # First peak = 200 (isolated). Forward neighbour = 600.
        # ILI = 600 - 200 = 400 (NOT 999 synthetic).
        # Window = [200 - 200, 200 + 200] = [0, 400]. Frame at t=200
        # → phase = 0.5.
        at_peak = out[np.isclose(out["t_ms"], 200.0)]
        assert len(at_peak) == 1
        assert at_peak.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)
        assert at_peak.iloc[0]["peak_t_ms"] == pytest.approx(200.0)

    def test_all_licks_includes_last_peak_with_synthetic(self):
        """3 peaks in one multi-bout, no other bouts. Without
        synthetic: 2 cycles (peak 0 + peak 1; peak 2 dropped). With
        synthetic: 3 cycles (peak 2 uses synthetic ILI for its
        forward width)."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        n_legacy_simple = sorted(
            build_all_licks_centered_phase_rows(
                bundle, ili_source="real_only",
            )["peak_t_ms"].unique().tolist()
        )
        n_synth = sorted(
            build_all_licks_centered_phase_rows(
                bundle, synthetic_ili_ms=100.0, ili_source="hybrid",
            )["peak_t_ms"].unique().tolist()
        )
        assert n_legacy_simple == [200.0, 300.0]
        assert n_synth == [200.0, 300.0, 400.0]

    def test_all_licks_includes_isolated_bouts_with_synthetic(self):
        """Trial with 1 multi-bout + 1 isolated bout. Without
        synthetic: only multi-bout peaks (minus last). With
        synthetic: all peaks across all bouts contribute."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [
                    {"peak_t_ms": [200.0, 300.0]},     # multi (drops 300 in legacy)
                    {"peak_t_ms": [800.0]},             # isolated
                ],
            },
        ])
        legacy = sorted(
            build_all_licks_centered_phase_rows(
                bundle, ili_source="real_only",
            )["peak_t_ms"].unique().tolist()
        )
        # Multi-bout: pair (200, 300). 200 contributes; 300 dropped.
        assert legacy == [200.0]
        synth = sorted(
            build_all_licks_centered_phase_rows(
                bundle, synthetic_ili_ms=150.0, ili_source="hybrid",
            )["peak_t_ms"].unique().tolist()
        )
        # Synthetic: all 3 peaks contribute. 200 → forward = 300
        # (real); 300 → forward = 800 (real, across bouts);
        # 800 → no forward, synthetic 150.
        assert synth == [200.0, 300.0, 800.0]

    def test_first_n_licks_uses_synthetic_for_last_cycle(self):
        """Trial with exactly N peaks (no peak[N] forward neighbour)
        → without synthetic: contributes nothing; with synthetic:
        cycle N-1 uses synthetic ILI."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0]}],
            },
        ])
        # ili_source="real_only": N=2 needs N+1=3 peaks → empty.
        legacy = build_first_n_licks_centered_phase_rows(
            bundle, n_peaks=2, ili_source="real_only",
        )
        assert legacy.empty
        # ili_source="hybrid" + synthetic: N=2 needs only 2 peaks
        # (cycle 1 uses synthetic).
        synth = build_first_n_licks_centered_phase_rows(
            bundle, n_peaks=2, synthetic_ili_ms=100.0, ili_source="hybrid",
        )
        assert not synth.empty
        rendered = sorted(synth["peak_t_ms"].unique().tolist())
        assert rendered == [200.0, 300.0]


class TestILISourceEnum:
    """Phase 7a.4-cross-session-angle Addendum #14 (2026-05-04):
    centered-phase helpers gain an ``ili_source`` kwarg with three
    choices — ``real_only`` (multi-bout-only, ignores synthetic),
    ``hybrid`` (default; synthetic as fallback), ``synthetic_only``
    (synthetic for every cycle, real-ILI lookup bypassed).
    """

    def test_real_only_drops_isolated_lick_trials(self):
        """real_only ignores synthetic_ili_ms even when supplied —
        falls back to multi-bout-only behaviour."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [400.0]}],   # isolated only
            },
        ])
        # synthetic_ili_ms IS supplied but ili_source="real_only"
        # ignores it. Trial drops because no multi-bout exists.
        out = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=100.0, ili_source="real_only",
        )
        assert out.empty

    def test_synthetic_only_uses_synthetic_for_all_cycles(self):
        """synthetic_only forces uniform cycle width regardless of
        forward-neighbour existence. Multi-bout's real ILI is
        IGNORED — every cycle's width = synthetic_ili_ms."""
        from stroke_orofacial.dlc_kinematics import (
            build_first_n_licks_centered_phase_rows,
        )
        # Real ILIs are 100 ms (200 → 300 → 400). Synthetic = 200 ms.
        # Under synthetic_only, both cycles span 200 ms regardless.
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        out = build_first_n_licks_centered_phase_rows(
            bundle, n_peaks=2, synthetic_ili_ms=200.0,
            ili_source="synthetic_only",
        )
        # Cycle 0 window = (200 - 100, 200 + 100) = (100, 300).
        # Cycle 1 window = (300 - 100, 300 + 100) = (200, 400).
        # Synthetic_only frame at t=200 → x = 0 + 0.5 + 0/200 = 0.5.
        # If REAL ILI = 100 had been used, window would be (150, 250)
        # and t=300 wouldn't be in cycle 0; under synthetic_only,
        # t=300 IS in cycle 0 (window 100..300, end-inclusive) AND
        # in cycle 1 (window 200..400, start-inclusive).
        at_p0 = out[(out["peak_t_ms"] == 200.0)]
        at_p1 = out[(out["peak_t_ms"] == 300.0)]
        # At t=200 in cycle 0: phase = (200 - 100) / 200 = 0.5.
        at_p0_t200 = at_p0[at_p0["t_ms"] == 200.0]
        assert len(at_p0_t200) == 1
        assert at_p0_t200.iloc[0]["phase"] == pytest.approx(0.5, abs=1e-6)
        # At t=300 in cycle 1: phase = 1 + 0.5 + 0/200 = 1.5.
        at_p1_t300 = at_p1[at_p1["t_ms"] == 300.0]
        assert len(at_p1_t300) == 1
        assert at_p1_t300.iloc[0]["phase"] == pytest.approx(1.5, abs=1e-6)

    def test_synthetic_only_requires_synthetic_ili(self):
        """synthetic_only with no synthetic_ili_ms supplied →
        ValueError (no fallback for fallback-less mode)."""
        from stroke_orofacial.dlc_kinematics import (
            build_all_licks_centered_phase_rows,
            build_first_lick_centered_phase_rows,
            build_first_n_licks_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        for fn in (
            build_first_lick_centered_phase_rows,
            build_all_licks_centered_phase_rows,
        ):
            with pytest.raises(ValueError, match="synthetic_only"):
                fn(bundle, ili_source="synthetic_only")
            with pytest.raises(ValueError, match="synthetic_only"):
                fn(bundle, synthetic_ili_ms=float("nan"),
                   ili_source="synthetic_only")
        with pytest.raises(ValueError, match="synthetic_only"):
            build_first_n_licks_centered_phase_rows(
                bundle, n_peaks=2, ili_source="synthetic_only",
            )

    def test_synthetic_only_is_default_after_addendum_15(self):
        """Phase 7a.4-cross-session-angle Addendum #15 (2026-05-04):
        helper default ``ili_source`` flipped from ``"hybrid"`` to
        ``"synthetic_only"`` per the verdict that Mode 3 won the
        3-way comparison across all centered-phase plot families on
        PS46/PS50/PS55. The default-no-kwarg call now matches the
        explicit ``ili_source="synthetic_only"`` call.
        """
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([
            {
                "trial_index": 0, "side": "L",
                "bouts": [{"peak_t_ms": [200.0, 300.0, 400.0]}],
            },
        ])
        out_default = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=200.0,
        )
        out_explicit = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=200.0, ili_source="synthetic_only",
        )
        assert not out_default.empty
        assert not out_explicit.empty
        for col in ("trial_index", "peak_t_ms", "t_ms", "phase"):
            assert (
                out_default[col].to_numpy()
                == out_explicit[col].to_numpy()
            ).all()

    def test_invalid_ili_source_raises(self):
        from stroke_orofacial.dlc_kinematics import (
            build_first_lick_centered_phase_rows,
        )
        bundle = _make_centered_phase_test_bundle([])
        with pytest.raises(ValueError, match="ili_source"):
            build_first_lick_centered_phase_rows(
                bundle, ili_source="bogus",
            )


class TestComputePreStrokeMedianILI:
    """Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04):
    per-animal pre-stroke median multi-bout ILI helper.

    Smoke-level coverage only — the function reads from on-disk
    7a.3 V3 endpoints + builds bundles, so a meaningful unit test
    would either need a heavy synthetic pipeline mock or a real-
    data integration fixture. The smoke test verifies the empty-
    case contract; the cache-test verifies idempotence.
    """

    def test_returns_nan_when_no_endpoints_dir(self, monkeypatch, tmp_path):
        """A real animal (in animals.yaml) but no on-disk endpoints
        for that animal → returns NaN. Tests the empty-data
        short-circuit path."""
        from stroke_orofacial.dlc_kinematics import (
            compute_pre_stroke_median_ili_ms,
        )
        from stroke_orofacial.animals import get_animal
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        animal_info = get_animal("PS46")
        v = compute_pre_stroke_median_ili_ms(
            "PS46", resolver=resolver, animal_info=animal_info,
        )
        assert np.isnan(v)

    def test_get_with_cache_is_idempotent(self, monkeypatch, tmp_path):
        from stroke_orofacial.dlc_kinematics import (
            get_pre_stroke_median_ili_ms,
        )
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            _PRE_STROKE_MEDIAN_ILI_CACHE,
        )
        from stroke_orofacial.animals import get_animal
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        animal_info = get_animal("PS46")
        cache_key = "PS46"
        # Clear cache first to avoid leakage from prior tests.
        _PRE_STROKE_MEDIAN_ILI_CACHE.pop(cache_key, None)
        v1 = get_pre_stroke_median_ili_ms(
            cache_key, resolver=resolver, animal_info=animal_info,
        )
        v2 = get_pre_stroke_median_ili_ms(
            cache_key, resolver=resolver, animal_info=animal_info,
        )
        # Both NaN (no endpoints dir at tmp_path); cache hit on
        # second call.
        assert np.isnan(v1) and np.isnan(v2)
        assert cache_key in _PRE_STROKE_MEDIAN_ILI_CACHE
        # Tidy up so the cache state doesn't leak into other tests.
        _PRE_STROKE_MEDIAN_ILI_CACHE.pop(cache_key, None)


# ===========================================================================
# Phase 7a.4-cross-session-angle Addendum #11 Part B (2026-05-04):
# extract_first_vs_second_peak_pairs
# ===========================================================================


class TestExtractFirstVsSecondPeakPairs:
    """Phase 7a.4-cross-session-angle Addendum #11 Part B (2026-05-04):
    helper that extracts the chronologically-first two detected peak
    angles per (trial, side) from ``df_bouts``. Used by the
    ``first_vs_second_peak_scatter`` plot family.
    """

    @staticmethod
    def _make_per_peak_row(
        *, trial_index: int, side: str, peak_t_ms: float,
        peak_angle_deg: float,
    ) -> dict[str, Any]:
        return dict(
            side=side,
            trial_index=int(trial_index),
            bout_idx=0,
            bout_rank=0,
            multi_bout_rank=0.0,
            n_peaks=2,
            bout_t0_ms=float(peak_t_ms - 50.0),
            bout_t1_ms=float(peak_t_ms + 50.0),
            peak_t0_ms=float("nan"),
            peak_t1_ms=float("nan"),
            peak_y0=float("nan"),
            peak_angle0=float("nan"),
            peak_y1=float("nan"),
            peak_angle1=float("nan"),
            peak_t_ms=float(peak_t_ms),
            peak_y=0.0,
            peak_x=0.0,
            peak_angle_deg=float(peak_angle_deg),
        )

    def test_extracts_first_two_peaks_per_trial(self):
        from stroke_orofacial.dlc_kinematics import (
            extract_first_vs_second_peak_pairs,
        )
        # Trial 0: 3 peaks at 200/300/400 ms with angles -10/+5/+8.
        # Pair extracted = (-10, +5).
        df_bouts = pd.DataFrame([
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=200.0,
                peak_angle_deg=-10.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=300.0,
                peak_angle_deg=5.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=400.0,
                peak_angle_deg=8.0,
            ),
        ])
        out = extract_first_vs_second_peak_pairs(df_bouts)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["trial_index"] == 0
        assert row["side"] == "L"
        assert row["peak0_t_ms"] == pytest.approx(200.0)
        assert row["peak0_angle_deg"] == pytest.approx(-10.0)
        assert row["peak1_t_ms"] == pytest.approx(300.0)
        assert row["peak1_angle_deg"] == pytest.approx(5.0)

    def test_skips_trials_with_fewer_than_two_peaks(self):
        from stroke_orofacial.dlc_kinematics import (
            extract_first_vs_second_peak_pairs,
        )
        df_bouts = pd.DataFrame([
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=200.0,
                peak_angle_deg=-10.0,
            ),  # only 1 peak — skip
            self._make_per_peak_row(
                trial_index=1, side="R", peak_t_ms=400.0,
                peak_angle_deg=2.0,
            ),
            self._make_per_peak_row(
                trial_index=1, side="R", peak_t_ms=500.0,
                peak_angle_deg=8.0,
            ),  # 2 peaks — kept
        ])
        out = extract_first_vs_second_peak_pairs(df_bouts)
        assert len(out) == 1
        assert int(out.iloc[0]["trial_index"]) == 1
        assert out.iloc[0]["side"] == "R"

    def test_chronological_order_across_bouts(self):
        """Peak ordering is chronological by ``peak_t_ms`` regardless
        of bout structure. Trial with isolated bout (peak[0]=200ms)
        + later multi-bout (peak[1]=600, peak[2]=700): first two
        peaks are 200 and 600.
        """
        from stroke_orofacial.dlc_kinematics import (
            extract_first_vs_second_peak_pairs,
        )
        df_bouts = pd.DataFrame([
            # Isolated bout, multi_bout_rank=NaN (per-peak row).
            dict(
                side="L", trial_index=0,
                bout_idx=0, bout_rank=0,
                multi_bout_rank=float("nan"),
                n_peaks=1,
                bout_t0_ms=150.0, bout_t1_ms=250.0,
                peak_t0_ms=float("nan"), peak_t1_ms=float("nan"),
                peak_y0=float("nan"), peak_angle0=float("nan"),
                peak_y1=float("nan"), peak_angle1=float("nan"),
                peak_t_ms=200.0, peak_y=0.0, peak_x=0.0,
                peak_angle_deg=-15.0,
            ),
            # Multi-bout peaks
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=600.0,
                peak_angle_deg=5.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=700.0,
                peak_angle_deg=8.0,
            ),
        ])
        out = extract_first_vs_second_peak_pairs(df_bouts)
        assert len(out) == 1
        assert out.iloc[0]["peak0_t_ms"] == pytest.approx(200.0)
        assert out.iloc[0]["peak0_angle_deg"] == pytest.approx(-15.0)
        assert out.iloc[0]["peak1_t_ms"] == pytest.approx(600.0)
        assert out.iloc[0]["peak1_angle_deg"] == pytest.approx(5.0)

    def test_per_trial_per_side_isolation(self):
        from stroke_orofacial.dlc_kinematics import (
            extract_first_vs_second_peak_pairs,
        )
        df_bouts = pd.DataFrame([
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=200.0,
                peak_angle_deg=-10.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="L", peak_t_ms=300.0,
                peak_angle_deg=5.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="R", peak_t_ms=600.0,
                peak_angle_deg=12.0,
            ),
            self._make_per_peak_row(
                trial_index=0, side="R", peak_t_ms=700.0,
                peak_angle_deg=15.0,
            ),
        ])
        out = extract_first_vs_second_peak_pairs(df_bouts)
        assert len(out) == 2
        keys = sorted(zip(out["trial_index"], out["side"]))
        assert keys == [(0, "L"), (0, "R")]

    def test_empty_df_bouts(self):
        from stroke_orofacial.dlc_kinematics import (
            extract_first_vs_second_peak_pairs,
        )
        out = extract_first_vs_second_peak_pairs(pd.DataFrame())
        assert out.empty
        for col in (
            "side", "trial_index",
            "peak0_t_ms", "peak0_angle_deg",
            "peak1_t_ms", "peak1_angle_deg",
        ):
            assert col in out.columns
