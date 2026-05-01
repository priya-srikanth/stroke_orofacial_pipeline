"""Phase 7a.5 — unit tests for jaw per-trial features.

Synthetic-trace fixtures use the same shape as the 7a.2 jaw
interpolated_traces parquet (single ``y_final`` column + ``fps`` and
``n_frames`` file-level metadata keys). All driver-invoking tests use
:class:`PathResolver` with ``output_root=tmp_path`` per
:doc:`docs/testing-conventions.md`.
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
from stroke_orofacial.dlc_kinematics.jaw_pertrial import (
    INTERPOLATION_VERSION,
    JAW_PERTRIAL_VERSION,
    JawPertrialResult,
    _check_sustained_density,
    _compute_jaw_baseline,
    _compute_jaw_deflections,
    _compute_jaw_threshold,
    build_jaw_pertrial,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import TrialEvent
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver

_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"
_SYNTH_FPS = 250.0


# ===========================================================================
# Synthetic fixtures
# ===========================================================================


def _make_synthetic_jaw_parquet(
    path: Path, n_frames: int, *, fps: float = _SYNTH_FPS,
    y_final: np.ndarray | None = None,
) -> None:
    """Write a 7a.2-shaped jaw interpolated_traces parquet (1 column + metadata)."""
    if y_final is None:
        y_final = np.zeros(n_frames, dtype=np.float64)
    df = pd.DataFrame({
        "frame_idx": np.arange(n_frames, dtype=np.int64),
        "x_final": np.zeros(n_frames, dtype=np.float64),
        "y_final": y_final.astype(np.float64),
        "likelihood_raw": np.full(n_frames, 0.95, dtype=np.float64),
        "is_interp_fill": np.zeros(n_frames, dtype=bool),
        "is_baseline_fill": np.zeros(n_frames, dtype=bool),
        "fill_method": np.zeros(n_frames, dtype=np.int8),
    })
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = {
        b"X0": b"0.0",
        b"Y0": b"0.0",
        b"baseline_stage": b"drop",
        b"center_mode": b"centered_eye_midpoint",
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


def _make_minimal_manifest(
    animal: str = "PS46", date: datetime.date = datetime.date(2025, 3, 7),
) -> SessionManifest:
    return SessionManifest(
        session_id=f"{animal}_{date.strftime('%Y%m%d')}",
        animal=animal,
        date=date,
        day_relative_to_stroke=-6,
        phase="baseline",
        excluded=False,
        alignment_template=None,
        wavesurfer_sides_match_mouse_sides=False,
    )


def _build_trial_jaw_y(
    n_frames: int, fps: float, reward_fr: int,
    *,
    baseline_level_px: float = 100.0,
    baseline_jitter_px: float = 0.5,
    deflection_amplitude_px: float | None = None,
    deflection_sign: int = 1,
    deflection_start_ms: float = 100.0,
    deflection_dur_ms: float = 1000.0,
    seed: int = 0,
) -> np.ndarray:
    """Synthetic jaw-Y trace with one trial's worth of behavior.

    Pre-reward (frames < reward_fr): low-amplitude jitter around baseline_level.
    Post-reward window: optional sustained deflection of given amplitude
    + sign in [deflection_start_ms, deflection_start_ms + deflection_dur_ms).
    """
    rng = np.random.default_rng(seed)
    y = baseline_level_px + rng.normal(0.0, baseline_jitter_px, n_frames)
    if deflection_amplitude_px is not None:
        start_fr = reward_fr + int(round(deflection_start_ms / 1000.0 * fps))
        end_fr = reward_fr + int(round(
            (deflection_start_ms + deflection_dur_ms) / 1000.0 * fps,
        ))
        start_fr = max(0, start_fr)
        end_fr = min(n_frames, end_fr)
        y[start_fr:end_fr] += deflection_sign * deflection_amplitude_px
    return y


@pytest.fixture()
def base_params() -> dict:
    return copy.deepcopy(load_defaults())


# ===========================================================================
# Helper-level tests (in-process, no I/O)
# ===========================================================================


class TestJawPertrialHelpers:
    """Tests 1-7 — direct helper-level coverage."""

    # 1
    def test_compute_jaw_baseline_mean_and_sd_correct(self):
        """Synthetic flat-then-rising trace: baseline window is flat
        @100 px → baseline_mean ~ 100, baseline_sd > 0 from jitter."""
        n = 1000
        fps = 250.0
        reward_fr = 500
        y = _build_trial_jaw_y(
            n, fps, reward_fr,
            baseline_level_px=100.0, baseline_jitter_px=2.0,
            deflection_amplitude_px=20.0, deflection_sign=1,
            deflection_start_ms=200.0, deflection_dur_ms=500.0,
        )
        # Use same snippet+window-mask path as the driver: t_ms here is
        # constructed for a (-500, 5000) ms snippet.
        pre_f = int(round(0.5 * fps))
        post_f = int(round(5.0 * fps))
        t_ms = np.arange(-pre_f, post_f + 1) * (1000.0 / fps)
        # snippet centered on reward_fr; reward_fr=500 is in-bounds for
        # the pre window (-500 ms → frame 375) but the post window
        # (5000 ms → frame 1750) overshoots the n=1000 trace, so the
        # right edge gets NaN-padded — same semantics as the driver's
        # ``_snippet`` helper.
        lo = reward_fr - pre_f
        hi = reward_fr + post_f
        out = np.full(t_ms.shape, np.nan, dtype=float)
        src_lo = max(lo, 0)
        src_hi = min(hi, n - 1)
        dst_lo = src_lo - lo
        dst_hi = dst_lo + (src_hi - src_lo)
        out[dst_lo:dst_hi + 1] = y[src_lo:src_hi + 1]

        mean, sd = _compute_jaw_baseline(out, t_ms, baseline_win_ms=(-500, 0))
        assert mean == pytest.approx(100.0, abs=0.5)
        assert sd > 0.0
        assert sd < 10.0  # jitter is 2 px → sd ~ 2

    # 2
    def test_compute_jaw_baseline_handles_nan(self):
        """NaN in baseline window → np.nanmean / np.nanstd skip NaN."""
        t_ms = np.linspace(-1000, 1000, 501)
        y = np.full(501, 50.0)
        # Inject NaN at half the baseline-window samples.
        base_idx = np.where((t_ms >= -500) & (t_ms <= 0))[0]
        y[base_idx[::2]] = np.nan
        mean, sd = _compute_jaw_baseline(y, t_ms, baseline_win_ms=(-500, 0))
        assert mean == pytest.approx(50.0, abs=1e-9)
        assert sd == pytest.approx(0.0, abs=1e-9)

    # 3
    def test_compute_jaw_deflections_pos_neg_abs_selected(self):
        """Synthetic trace with known +10 and -25 px deflections; verify
        all 4 values come out with correct signs + magnitudes, and
        ``selected`` picks the larger-magnitude (-25) with sign preserved."""
        t_ms = np.linspace(0, 5000, 251)  # detect window only
        y = np.zeros(251) + 100.0
        y[20:30] = 110.0   # +10 px
        y[100:120] = 75.0  # -25 px
        baseline_mean = 100.0
        peaks = _compute_jaw_deflections(
            y, t_ms, baseline_mean, detect_win_ms=(0, 5000),
        )
        assert peaks["pos"] == pytest.approx(10.0, abs=1e-9)
        assert peaks["neg"] == pytest.approx(-25.0, abs=1e-9)
        assert peaks["abs"] == pytest.approx(25.0, abs=1e-9)
        # selected = signed value at argmax(|defl|) = -25 (sign preserved)
        assert peaks["selected"] == pytest.approx(-25.0, abs=1e-9)

    # 4
    def test_compute_jaw_threshold_sd_scaled_wins(self):
        """Large baseline_sd: 4 * sd > 4 px floor → label = 'sd_scaled'."""
        v, label = _compute_jaw_threshold(baseline_sd=3.0, sd_mult=4.0, min_px=4.0)
        assert v == pytest.approx(12.0, abs=1e-9)
        assert label == "sd_scaled"

    # 5
    def test_compute_jaw_threshold_floor_wins(self):
        """Small baseline_sd: 4 * sd < 4 px floor → label = 'px_floor'."""
        v, label = _compute_jaw_threshold(baseline_sd=0.5, sd_mult=4.0, min_px=4.0)
        assert v == pytest.approx(4.0, abs=1e-9)
        assert label == "px_floor"
        # Tie-break: equal values → label = 'px_floor' (deterministic
        # floor-preferred per the helper's docstring).
        v_tie, label_tie = _compute_jaw_threshold(
            baseline_sd=1.0, sd_mult=4.0, min_px=4.0,
        )
        assert v_tie == pytest.approx(4.0, abs=1e-9)
        assert label_tie == "px_floor"

    # 6
    def test_check_sustained_density_passes_at_5_of_8(self):
        """8-frame window with 5 frames over threshold → passes."""
        t_ms = np.linspace(0, 5000, 251)
        # Build defl such that |defl| > 5 in indices 100..104 (5 frames),
        # below threshold elsewhere → any 8-window covering [100..104] ⊂
        # 8 contiguous frames yields ≥5/8 → passes.
        y = np.full(251, 100.0)
        y[100:105] = 200.0  # |defl| = 100 >> 5
        baseline_mean = 100.0
        threshold = 5.0
        pass_qc, n_over = _check_sustained_density(
            y, t_ms, baseline_mean, threshold,
            detect_win_ms=(0, 5000), window_n=8, density_thr=0.625,
        )
        assert n_over == 5
        assert pass_qc is True

    # 7
    def test_check_sustained_density_fails_below_density(self):
        """Sparse suprathreshold frames (4 in a row of 8): fails the 5/8 rule."""
        t_ms = np.linspace(0, 5000, 251)
        y = np.full(251, 100.0)
        y[100:104] = 200.0  # only 4 contiguous high frames
        baseline_mean = 100.0
        threshold = 5.0
        pass_qc, n_over = _check_sustained_density(
            y, t_ms, baseline_mean, threshold,
            detect_win_ms=(0, 5000), window_n=8, density_thr=0.625,
        )
        assert n_over == 4
        # ceil(0.625 * 8) = 5; 4 < 5 → fail.
        assert pass_qc is False


# ===========================================================================
# Driver-level tests (round-trip JSON write)
# ===========================================================================


def _setup_session_with_one_strong_deflection(
    tmp_path: Path, monkeypatch,
    *,
    deflection_amplitude_px: float = 30.0,
    deflection_sign: int = 1,
):
    """Common harness: write a synthetic jaw parquet for a one-trial session,
    return ``(resolver, manifest, trial_events)`` for driver invocation."""
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    resolver = PathResolver(output_root=tmp_path)
    animal = "PS46"
    date = datetime.date(2025, 3, 7)
    n = 5000  # 20 s @ 250 Hz
    fps = 250.0
    reward_fr = 1500
    y = _build_trial_jaw_y(
        n, fps, reward_fr,
        baseline_level_px=120.0, baseline_jitter_px=0.5,
        deflection_amplitude_px=deflection_amplitude_px,
        deflection_sign=deflection_sign,
        deflection_start_ms=200.0, deflection_dur_ms=2000.0,
        seed=0,
    )
    parquet_path = resolver.interpolated_trace(
        bodypart="jaw", animal=animal, date=date,
    )
    _make_synthetic_jaw_parquet(parquet_path, n, fps=fps, y_final=y)
    manifest = _make_minimal_manifest(animal=animal, date=date)
    trial_events = [TrialEvent(trial_index=0, reward_frame_idx=reward_fr, side="L")]
    return resolver, manifest, trial_events


class TestJawPertrialDriver:
    """Tests 8-10 — round-trip through ``build_jaw_pertrial``."""

    # 8
    def test_build_jaw_pertrial_emits_json_with_full_schema(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Driver round-trip: emits JSON with the kickoff §4a top-level
        + ``jaw_pertrial`` + ``metadata`` keys; one strong-deflection trial
        passes QC; baseline scalars are sane."""
        resolver, manifest, trial_events = (
            _setup_session_with_one_strong_deflection(tmp_path, monkeypatch)
        )
        out_path = build_jaw_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        assert out_path is not None and out_path.exists()
        ep = json.loads(out_path.read_text(encoding="utf-8"))

        # Top-level schema lock
        assert ep["schema_version"] == JAW_PERTRIAL_VERSION
        assert ep["animal"] == "PS46"
        assert ep["date"] == "2025-03-07"
        assert ep["n_trials"] == 1
        assert ep["trial_indices"] == [0]
        assert ep["sides"] == ["L"]

        jp = ep["jaw_pertrial"]
        # All 8 scalar arrays present, each length == n_trials
        for k in (
            "jaw_baseline_mean", "jaw_baseline_sd",
            "jaw_peak_pos_deflection", "jaw_peak_neg_deflection",
            "jaw_peak_abs_deflection", "jaw_peak_selected_deflection",
            "jaw_thresh_abs", "jaw_thresh_px_used",
            "jaw_n_frames_over_thresh", "jaw_pass_qc",
        ):
            assert k in jp, f"missing key {k!r}"
            assert len(jp[k]) == 1, f"{k} length != n_trials"

        # Sanity: baseline ~120; pos deflection ~30; QC passes.
        assert jp["jaw_baseline_mean"][0] == pytest.approx(120.0, abs=1.0)
        assert jp["jaw_peak_pos_deflection"][0] == pytest.approx(30.0, abs=2.0)
        assert jp["jaw_pass_qc"][0] is True
        assert jp["jaw_n_frames_over_thresh"][0] > 100

        # Metadata round-trip
        meta = ep["metadata"]
        assert meta["fps"] == pytest.approx(_SYNTH_FPS, abs=1e-9)
        assert meta["feature_extraction_version"] == JAW_PERTRIAL_VERSION
        assert meta["interpolation_version"] == INTERPOLATION_VERSION
        assert meta["detect_win_ms"] == [0, 5000]
        assert meta["baseline_win_ms"] == [-500, 0]
        assert meta["sustained_density_threshold"] == 0.625
        assert meta["sustained_window_n_frames"] == 8

    # 9
    def test_build_jaw_pertrial_overwrite_semantics(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``skip`` returns existing path when JSON already exists; ``force``
        always rewrites (mtime advances)."""
        resolver, manifest, trial_events = (
            _setup_session_with_one_strong_deflection(tmp_path, monkeypatch)
        )
        p1 = build_jaw_pertrial(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        assert p1 is not None and p1.exists()
        mtime_1 = p1.stat().st_mtime_ns

        # skip-and-exists → returns same path, file not rewritten.
        p2 = build_jaw_pertrial(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="skip",
        )
        assert p2 == p1
        assert p2.stat().st_mtime_ns == mtime_1

        # force → rewrite (mtime advances or stays equal under fast disks;
        # what we really care about is no error and identical content).
        p3 = build_jaw_pertrial(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        assert p3 == p1
        assert p3.exists()
        ep_initial = json.loads(p1.read_text(encoding="utf-8"))
        ep_rewritten = json.loads(p3.read_text(encoding="utf-8"))
        assert ep_initial == ep_rewritten

        # Bad value raises.
        with pytest.raises(ValueError, match="overwrite must be"):
            build_jaw_pertrial(
                manifest=manifest, resolver=resolver,
                trial_events=trial_events, params=base_params,
                overwrite="bogus",  # type: ignore[arg-type]
            )

    # 10
    def test_build_jaw_pertrial_endpoints_schema_locked(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Predicate truth-table for sustained-density QC pass/fail across
        a 3-trial session: strong+ deflection passes, strong- deflection
        passes (above_or_below mode), tiny deflection fails. Locks the
        kickoff §4a per-trial schema (all 8 fields populated, no None for
        non-degenerate-baseline trials)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        animal = "PS46"
        date = datetime.date(2025, 3, 7)
        n = 7500  # 30 s @ 250 Hz
        fps = 250.0
        reward_frs = [500, 3000, 5500]
        # Trial 0: +30 px sustained → passes.
        y = _build_trial_jaw_y(
            n, fps, reward_frs[0],
            baseline_level_px=100.0, baseline_jitter_px=0.5,
            deflection_amplitude_px=30.0, deflection_sign=1,
            deflection_start_ms=200.0, deflection_dur_ms=1500.0,
            seed=0,
        )
        # Trial 1: overlay -30 px sustained → passes (above_or_below).
        rng = np.random.default_rng(1)
        seg_lo = reward_frs[1] + int(0.2 * fps)
        seg_hi = reward_frs[1] + int(1.7 * fps)
        y[seg_lo:seg_hi] = 100.0 - 30.0 + rng.normal(0.0, 0.5, seg_hi - seg_lo)
        # Trial 2: tiny ±1 px deflection (well below 4 px floor) → fails.
        seg_lo2 = reward_frs[2] + int(0.2 * fps)
        seg_hi2 = reward_frs[2] + int(1.7 * fps)
        y[seg_lo2:seg_hi2] = 100.0 + 1.0 + rng.normal(
            0.0, 0.2, seg_hi2 - seg_lo2,
        )
        parquet_path = resolver.interpolated_trace(
            bodypart="jaw", animal=animal, date=date,
        )
        _make_synthetic_jaw_parquet(parquet_path, n, fps=fps, y_final=y)
        manifest = _make_minimal_manifest(animal=animal, date=date)
        trial_events = [
            TrialEvent(trial_index=k, reward_frame_idx=fr, side=sd)
            for k, (fr, sd) in enumerate(zip(reward_frs, ["L", "R", "L"]))
        ]
        out_path = build_jaw_pertrial(
            manifest=manifest, resolver=resolver,
            trial_events=trial_events, params=base_params,
            overwrite="force",
        )
        assert out_path is not None and out_path.exists()
        ep = json.loads(out_path.read_text(encoding="utf-8"))
        jp = ep["jaw_pertrial"]
        assert ep["n_trials"] == 3
        # Trial 0 — strong + → pass
        assert jp["jaw_pass_qc"][0] is True
        assert jp["jaw_peak_pos_deflection"][0] >= 25.0
        # Trial 1 — strong - → pass; selected deflection should be SIGNED neg
        assert jp["jaw_pass_qc"][1] is True
        assert jp["jaw_peak_selected_deflection"][1] < -20.0
        # Trial 2 — tiny → fail
        assert jp["jaw_pass_qc"][2] is False
        # All trials non-degenerate-baseline → no None scalars
        for k in (
            "jaw_baseline_mean", "jaw_baseline_sd",
            "jaw_peak_pos_deflection", "jaw_peak_neg_deflection",
            "jaw_peak_abs_deflection", "jaw_peak_selected_deflection",
            "jaw_thresh_abs",
        ):
            assert all(v is not None for v in jp[k]), (
                f"non-None expected for {k!r}, got {jp[k]!r}"
            )
        # threshold-label is in the categorical set
        for label in jp["jaw_thresh_px_used"]:
            assert label in ("sd_scaled", "px_floor")


# ===========================================================================
# Edge cases (manifest excluded, dataclass shape)
# ===========================================================================


class TestJawPertrialEdgeCases:
    """Extra coverage beyond the kickoff §4b 10-test target."""

    def test_excluded_manifest_short_circuits_to_none(
        self, monkeypatch, tmp_path, base_params,
    ):
        resolver, manifest, trial_events = (
            _setup_session_with_one_strong_deflection(tmp_path, monkeypatch)
        )
        manifest = SessionManifest(
            session_id=manifest.session_id, animal=manifest.animal,
            date=manifest.date,
            day_relative_to_stroke=manifest.day_relative_to_stroke,
            phase=manifest.phase, excluded=True,
            alignment_template=None,
            wavesurfer_sides_match_mouse_sides=False,
        )
        out = build_jaw_pertrial(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        assert out is None

    def test_jaw_pertrial_result_is_frozen(self):
        """``JawPertrialResult`` is a frozen dataclass — assignment raises."""
        result = JawPertrialResult(endpoints={"x": 1}, metadata={"y": 2})
        with pytest.raises(Exception):  # noqa: B017
            result.endpoints = {"new": 3}  # type: ignore[misc]
