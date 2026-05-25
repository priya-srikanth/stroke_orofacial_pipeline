r"""Phase 7a.2 unit tests for stroke_orofacial.dlc_kinematics.interpolation.

Covers the 14 tests in ``docs/phase-7/interpolation-strategy.md`` §8
(unit tests; the integration tests under §8's "if MICROSCOPE available"
section live in Task 4) plus extras flagged by the 2026-04-24 Task 2
review (``_center_mode_short``, strict-equality parquet schema, sidecar
X0_data/Y0_data presence, regression-guard dataclass fields).

All tests are MICROSCOPE-free: synthetic arrays, synthetic parquets
under ``tmp_path``, synthetic Phase 2 NPZ + alignment template. No path
under ``\\research.files.med.harvard.edu\...`` is read or written.
"""

from __future__ import annotations

import datetime
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from stroke_orofacial.animals import AnimalInfo, Exclusion, EpochBoundaries
from stroke_orofacial.dlc_io.parquet import _param_sig
from stroke_orofacial.dlc_kinematics.interpolation import (
    INTERPOLATION_VERSION,
    InterpolationResult,
    _BASELINE_SOURCE_STAGE,
    _FILL_METHOD_LINEAR,
    _FILL_METHOD_NONE,
    _FILL_METHOD_PCHIP,
    _build_tone_aligned_pool_mask,
    _center_mode_short,
    _fill_nan_with,
    _interp_small_gaps,
    _interpolate_bodypart_core,
    _stage_drop,
    _stage_thr,
    _stage_xrange,
    build_interpolated_trace,
)
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
)
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver

_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


# ---------------------------------------------------------------------------
# Fixtures — synthetic session scaffolding under tmp_path
# ---------------------------------------------------------------------------


def _default_params() -> dict[str, Any]:
    """Return a defaults.yaml-shaped dict just sufficient for the module."""
    return {
        "alignment": {"fps_cam": 250.0},
        "dlc_kinematics": {
            "interpolation_version": INTERPOLATION_VERSION,
            "interpolation_method": "pchip",
            "interpolation_fallback": "linear",
            "tongue": {
                "center_mode": "centered_spout_midpoint",
                "interpolation": {
                    "x_range_pm": 150.0,
                    "x_range_source": "lk",
                    "lk_thr": 0.5,
                    "n_neigh": 2,
                    "neighbor_ms": 16.0,
                    "max_gap_ms": 56.0,
                    "interp_n_side": 6,
                    "require_bracketed_by_hilk": True,
                },
                "baseline": {
                    "force": True,
                    "y0_lk_thr": 0.95,
                    "y0_percentile": 5.0,
                },
            },
            "jaw": {
                "center_mode": "centered_eye_midpoint",
                "interpolation": {
                    "x_range_pm": 75.0,
                    "x_range_source": "lk",
                    "lk_thr": 0.5,
                    "n_neigh": 3,
                    "neighbor_ms": 16.0,
                    "max_gap_ms": 120.0,
                    "interp_n_side": 6,
                    "require_bracketed_by_hilk": True,
                },
                "baseline": {
                    "force": True,
                    "y0_lk_thr": 0.95,
                    "y0_percentile": 5.0,
                },
            },
        },
    }


def _animal_info(
    *,
    animal: str = "PS46",
    date_: datetime.date | None = None,
    exclusions: list[Exclusion] | None = None,
    baselines: dict[str, dict[str, float]] | None = None,
) -> AnimalInfo:
    """Minimal AnimalInfo with kinematics_baselines populated."""
    if date_ is None:
        date_ = datetime.date(2025, 3, 7)
    if baselines is None:
        baselines = {
            "tongue": {"x0": 0.0, "y0": -110.0},
            "jaw": {"x0": 0.0, "y0": 310.0},
        }
    return AnimalInfo(
        animal_id=animal,
        stroke_date=date_,
        session_start=date_,
        session_end=date_,
        epoch_boundaries=EpochBoundaries(1, 4, 5),
        exclusions=exclusions or [],
        kinematics_baselines=baselines,
        wavesurfer_sides_match_mouse_sides=False,
    )


def _write_synthetic_centered_parquet(
    parquet_path: Path,
    bodypart: str,
    n_frames: int,
    *,
    seed: int = 42,
    all_finite: bool = True,
) -> None:
    """Write a minimal centered parquet with the 3 bodypart columns."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 50.0, size=n_frames)
    y = rng.normal(0.0, 50.0, size=n_frames)
    lk = rng.uniform(0.6, 1.0, size=n_frames)
    if not all_finite:
        # Scatter a handful of NaNs for variety.
        nan_idx = rng.choice(n_frames, size=max(5, n_frames // 100), replace=False)
        x[nan_idx] = np.nan
        y[nan_idx] = np.nan
    df = pd.DataFrame({
        f"{bodypart}_x": x.astype(np.float32),
        f"{bodypart}_y": y.astype(np.float32),
        f"{bodypart}_likelihood": lk.astype(np.float32),
    })
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, engine="pyarrow")


def _write_synthetic_licks_npz(
    path: Path,
    *,
    reward_L: np.ndarray | None = None,
    reward_R: np.ndarray | None = None,
    wavesurfer_matches: bool = False,
) -> None:
    """Write a Phase-2-shaped licks NPZ with the v6.8 side-convention stamp."""
    if reward_L is None:
        reward_L = np.array([1000, 3000, 5000], dtype=np.int64)
    if reward_R is None:
        reward_R = np.array([2000, 4000], dtype=np.int64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        Tone_L=reward_L,
        Tone_R=reward_R,
        **{
            SIDE_CONVENTION_MATCH_KEY: np.bool_(wavesurfer_matches),
            SIDE_CONVENTION_VERSION_KEY: np.int64(SIDE_CONVENTION_VERSION),
        },
    )


def _write_synthetic_alignment_template(path: Path, n_ws: int = 20000) -> None:
    """Write a minimal alignment template: WS-index → cam-frame float LUT."""
    # Linear ramp: cam_frame = ws_idx / 4.0 (i.e., ~250 fps cam from 1000 Hz WS).
    sig_camIdx__idx_ws = (np.arange(n_ws) / 4.0).astype(float)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, sig_camIdx__idx_ws=sig_camIdx__idx_ws)


@pytest.fixture()
def minimal_session(tmp_path: Path, monkeypatch):
    """Fixture: synthetic session wired under ``tmp_path``.

    Returns a dict with:
      - ``resolver``: ``PathResolver(output_root=tmp_path)``
      - ``animal_info``: ``AnimalInfo`` with kinematics_baselines
      - ``manifest``: ``SessionManifest`` pointing at synthetic parquet +
        alignment template
      - ``params``: defaults.yaml-shaped dict
      - ``animal``, ``date``, ``bodypart``: metadata
      - ``parquet_path``: path to the synthetic centered parquet
      - ``licks_path``: path to the synthetic Phase 2 NPZ
      - ``align_path``: path to the synthetic alignment template
    """
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)

    animal = "PS46"
    date_ = datetime.date(2025, 3, 7)
    bodypart = "tongue"
    center_mode_long = "centered_spout_midpoint"
    short = "spout_midpoint"
    n_frames = 2500

    resolver = PathResolver(output_root=tmp_path)

    # Synthetic DLC h5 filename (its name is used to derive the
    # centered-parquet filename via _param_sig; the file itself need
    # not exist on disk).
    dlc_h5_name = (
        f"video2_{date_.strftime('%Y-%m-%d')}T12_00_00"
        f"DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
    )
    dlc_h5 = tmp_path / dlc_h5_name

    # Centered parquet path (matches _load_centered_df's lookup).
    sig = _param_sig(short, 0.7)
    parquet_dir = (
        resolver.pipeline_outputs("dlc_analysis")
        / f"centered_{short}"
        / animal
    )
    parquet_path = parquet_dir / f"{dlc_h5_name}.intermediate.{sig}.parquet"
    _write_synthetic_centered_parquet(
        parquet_path, bodypart, n_frames, all_finite=False,
    )

    # Phase 2 licks NPZ (under resolver.pipeline_outputs("spout_behavior")).
    licks_path = (
        resolver.pipeline_outputs("spout_behavior")
        / "licks_and_rewards"
        / animal
        / f"{date_.strftime('%Y%m%d')}.npz"
    )
    _write_synthetic_licks_npz(licks_path)

    # Alignment template — put it under tmp_path directly so the
    # manifest's direct-path plumbing is exercised (and the resolver's
    # real microscope_server fallback is never hit).
    align_path = tmp_path / f"align_{animal}_{date_.strftime('%Y%m%d')}.npz"
    _write_synthetic_alignment_template(align_path)

    animal_info = _animal_info(animal=animal, date_=date_)
    manifest = SessionManifest(
        session_id=f"{animal}_{date_.strftime('%Y%m%d')}",
        animal=animal,
        date=date_,
        day_relative_to_stroke=0,
        phase="baseline",
        dlc_h5_files=[dlc_h5],
        alignment_template=align_path,
        wavesurfer_sides_match_mouse_sides=False,
    )

    return {
        "animal": animal,
        "date": date_,
        "bodypart": bodypart,
        "center_mode": center_mode_long,
        "resolver": resolver,
        "animal_info": animal_info,
        "manifest": manifest,
        "params": _default_params(),
        "parquet_path": parquet_path,
        "licks_path": licks_path,
        "align_path": align_path,
    }


# ---------------------------------------------------------------------------
# §8 test 1 — X-range filter
# ---------------------------------------------------------------------------


class TestStageXrange:
    def test_stage_xrange_drops_outliers(self):
        """Samples outside ``median(x[lk>=thr]) ± x_range_pm`` become NaN;
        within-range samples are preserved."""
        x = np.array([0.0, 1.0, 2.0, 200.0, -200.0, 3.0, 4.0, 5.0])
        y = np.ones_like(x) * 10.0
        lk = np.ones_like(x) * 0.9
        x_out, y_out = _stage_xrange(
            x, y, lk,
            x_range_pm=50.0, x_range_source="lk", lk_thr=0.5,
        )
        # median of x = 2.5; range = [-47.5, 52.5]. 200 and -200 drop; 100
        # would drop too but it's not in the input. Check outliers got NaN'd.
        assert np.isnan(x_out[3])
        assert np.isnan(y_out[3])
        assert np.isnan(x_out[4])
        assert np.isnan(y_out[4])
        # In-range values preserved exactly.
        for i in (0, 1, 2, 5, 6, 7):
            assert x_out[i] == x[i]
            assert y_out[i] == y[i]

    def test_stage_xrange_finite_fallback_when_lk_empty(self):
        """When no sample meets the lk threshold, legacy falls back to
        the finite-support median rather than raising."""
        x = np.array([0.0, 10.0, 20.0, 30.0])
        y = np.ones_like(x) * 5.0
        lk = np.zeros_like(x)  # all below lk_thr=0.5
        x_out, y_out = _stage_xrange(
            x, y, lk, x_range_pm=100.0, x_range_source="lk", lk_thr=0.5,
        )
        # With finite fallback, median=15; all four samples within ±100.
        assert np.all(np.isfinite(x_out))
        assert np.all(np.isfinite(y_out))


# ---------------------------------------------------------------------------
# §8 test 2 — LK threshold
# ---------------------------------------------------------------------------


class TestStageThr:
    def test_stage_thr_drops_low_likelihood(self):
        """Samples with ``lk < lk_thr`` are NaN'd; at/above are preserved."""
        x = np.array([1.0, 2.0, 3.0, 4.0])
        y = np.array([10.0, 20.0, 30.0, 40.0])
        lk = np.array([0.9, 0.3, 0.7, 0.1])
        x_out, y_out = _stage_thr(x, y, lk, lk_thr=0.5)
        assert x_out[0] == 1.0 and y_out[0] == 10.0
        assert np.isnan(x_out[1]) and np.isnan(y_out[1])
        assert x_out[2] == 3.0 and y_out[2] == 30.0
        assert np.isnan(x_out[3]) and np.isnan(y_out[3])


# ---------------------------------------------------------------------------
# §8 test 3 — isolated hi-lk rejection
# ---------------------------------------------------------------------------


class TestStageDrop:
    @pytest.mark.parametrize("n_hi_in_window,expect_kept", [
        (0, False),  # isolated point: 0 neighbors in ±neighbor_f
        (1, False),  # 1 neighbor, n_neigh=2 → reject
        (2, True),   # 2 neighbors, n_neigh=2 → keep
        (5, True),   # clustered → keep
    ])
    def test_stage_drop_isolated_hilk(self, n_hi_in_window: int, expect_kept: bool):
        """Drop samples with fewer than ``n_neigh`` hi-lk neighbors in
        ±``neighbor_f`` frames."""
        n_frames = 40
        neighbor_f = 4
        n_neigh = 2
        # Place hi-lk samples around index 20 with the requested cluster size.
        x = np.full(n_frames, np.nan)
        y = np.full(n_frames, np.nan)
        center = 20
        # Add the center point + n_hi_in_window others inside ±neighbor_f.
        offsets = [0] + list(range(1, n_hi_in_window + 1))
        for off in offsets:
            idx = center + off
            if 0 <= idx < n_frames:
                x[idx] = 10.0 + off
                y[idx] = 20.0 + off
        x_out, y_out = _stage_drop(x, y, n_neigh=n_neigh, neighbor_f=neighbor_f)
        if expect_kept:
            assert np.isfinite(x_out[center])
        else:
            assert np.isnan(x_out[center])

    def test_stage_drop_preserves_clustered_hilk(self):
        """A tight cluster of hi-lk samples: all survive."""
        n_frames = 20
        x = np.full(n_frames, np.nan)
        y = np.full(n_frames, np.nan)
        # 5 consecutive hi-lk samples → each has >=2 neighbors in ±4.
        for i in range(10, 15):
            x[i] = float(i)
            y[i] = float(-i)
        x_out, _ = _stage_drop(x, y, n_neigh=2, neighbor_f=4)
        for i in range(10, 15):
            assert np.isfinite(x_out[i])


# ---------------------------------------------------------------------------
# §8 tests 4+5 — interp fills / preserves gaps
# ---------------------------------------------------------------------------


class TestStageInterp:
    def test_stage_interp_fills_short_gaps(self):
        """A NaN run of length ``<= max_gap_f`` bracketed by hi-lk anchors
        gets filled via PCHIP; ``fill_codes`` marks those frames."""
        n = 20
        arr = np.arange(n, dtype=float)
        # Carve a short gap in [10, 12]
        arr[10] = np.nan
        arr[11] = np.nan
        hi_mask = np.ones(n, dtype=bool)
        # Mark the gap positions as not hi (irrelevant; hi_mask reads the
        # anchors only at left/right of the gap here — both hi).
        hi_mask[10] = False
        hi_mask[11] = False

        out, fill_codes = _interp_small_gaps(
            arr, hi_mask, max_gap_f=5,
            require_bracketed_by_hi=True,
            method="pchip", n_side=6, min_total_context=6,
            fallback="linear",
        )
        # Gap filled; for a monotonic linear ramp PCHIP reproduces the ramp.
        assert np.isfinite(out[10])
        assert np.isfinite(out[11])
        assert fill_codes[10] in (_FILL_METHOD_PCHIP, _FILL_METHOD_LINEAR)
        assert fill_codes[11] in (_FILL_METHOD_PCHIP, _FILL_METHOD_LINEAR)
        # Anchor frames unchanged.
        assert fill_codes[9] == _FILL_METHOD_NONE
        assert fill_codes[12] == _FILL_METHOD_NONE

    def test_stage_interp_preserves_long_gaps(self):
        """Gaps of length ``> max_gap_f`` stay NaN and ``fill_codes``
        stays at ``_FILL_METHOD_NONE``."""
        n = 20
        arr = np.arange(n, dtype=float)
        # Long gap in [5, 14] (length 10)
        for i in range(5, 15):
            arr[i] = np.nan
        hi_mask = np.ones(n, dtype=bool)
        out, fill_codes = _interp_small_gaps(
            arr, hi_mask, max_gap_f=5,
            require_bracketed_by_hi=True,
            method="pchip", n_side=6, min_total_context=6,
            fallback="linear",
        )
        for i in range(5, 15):
            assert np.isnan(out[i])
            assert fill_codes[i] == _FILL_METHOD_NONE


# ---------------------------------------------------------------------------
# §8 tests 6+7 — baseline substitution + final subtraction
# ---------------------------------------------------------------------------


class TestStageFilledAndFinal:
    def test_stage_interp_filled_baseline_substitution(self):
        """``_fill_nan_with`` replaces NaNs with ``X0``; finite entries
        are preserved."""
        arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        out = _fill_nan_with(arr, fill_value=99.0)
        assert list(out) == [1.0, 99.0, 3.0, 99.0, 5.0]

    def test_stage_final_baseline_subtraction(self, minimal_session):
        """``x_final = x_interp_filled - X0`` and ``y_final = y_interp_filled - Y0``."""
        m = minimal_session
        df = pd.read_parquet(m["parquet_path"])
        # Reward centers — synthesize directly so we bypass I/O.
        tone_centers_cam = np.array([100.0, 500.0, 1500.0])
        bp_params = m["params"]["dlc_kinematics"]["tongue"].copy()
        bp_params["interpolation_method"] = "pchip"
        bp_params["interpolation_fallback"] = "linear"

        result = _interpolate_bodypart_core(
            df=df,
            bodypart="tongue",
            center_mode="centered_spout_midpoint",
            bodypart_params=bp_params,
            tone_centers_cam=tone_centers_cam,
            animal_info=m["animal_info"],
            fps=250.0,
        )
        expected_x = result.x_interp_filled - result.X0
        expected_y = result.y_interp_filled - result.Y0
        np.testing.assert_array_equal(result.x_final, expected_x)
        np.testing.assert_array_equal(result.y_final, expected_y)


# ---------------------------------------------------------------------------
# §8 tests 8+9 — bodypart dispatch
# ---------------------------------------------------------------------------


class TestBodypartDispatch:
    def test_bodypart_dispatch_tongue(self, minimal_session):
        """Core reads ``tongue_x`` / ``tongue_y`` / ``tongue_likelihood``
        columns; tongue-parameter-set values flow through to the result."""
        m = minimal_session
        df = pd.read_parquet(m["parquet_path"])
        assert {"tongue_x", "tongue_y", "tongue_likelihood"}.issubset(df.columns)
        bp_params = m["params"]["dlc_kinematics"]["tongue"].copy()
        bp_params["interpolation_method"] = "pchip"
        bp_params["interpolation_fallback"] = "linear"
        result = _interpolate_bodypart_core(
            df=df, bodypart="tongue",
            center_mode="centered_spout_midpoint",
            bodypart_params=bp_params,
            tone_centers_cam=np.array([100.0, 500.0]),
            animal_info=m["animal_info"], fps=250.0,
        )
        assert result.bodypart == "tongue"
        assert result.center_mode == "centered_spout_midpoint"
        # Tongue baseline seeded above = (0.0, -110.0).
        assert result.X0 == 0.0
        assert result.Y0 == -110.0

    def test_bodypart_dispatch_jaw(self, tmp_path, monkeypatch):
        """Core reads jaw columns; jaw-parameter-set values differ
        (e.g. ``x_range_pm=75``, ``n_neigh=3``, ``max_gap_ms=120``)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        n_frames = 1500
        parquet_path = tmp_path / "jaw_synthetic.parquet"
        _write_synthetic_centered_parquet(parquet_path, "jaw", n_frames, all_finite=False)
        df = pd.read_parquet(parquet_path)
        assert {"jaw_x", "jaw_y", "jaw_likelihood"}.issubset(df.columns)
        bp_params = _default_params()["dlc_kinematics"]["jaw"].copy()
        bp_params["interpolation_method"] = "pchip"
        bp_params["interpolation_fallback"] = "linear"
        result = _interpolate_bodypart_core(
            df=df, bodypart="jaw",
            center_mode="centered_eye_midpoint",
            bodypart_params=bp_params,
            tone_centers_cam=np.array([200.0, 800.0]),
            animal_info=_animal_info(),
            fps=250.0,
        )
        assert result.bodypart == "jaw"
        assert result.center_mode == "centered_eye_midpoint"
        # Jaw baseline from the synthetic AnimalInfo = (0.0, 310.0).
        assert result.X0 == 0.0
        assert result.Y0 == 310.0


# ---------------------------------------------------------------------------
# §8 test 10 — forced baseline from AnimalInfo
# ---------------------------------------------------------------------------


class TestForceBaseline:
    def test_force_baseline_from_animal_info(self, minimal_session):
        """With ``baseline.force=true``, X0/Y0 come from AnimalInfo's
        ``kinematics_baselines`` — not from the data-driven pool."""
        m = minimal_session
        result = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force",
            animal_info=m["animal_info"],
        )
        assert result is not None
        meta = pq.ParquetFile(result).metadata.metadata
        assert float(meta[b"X0"]) == 0.0
        assert float(meta[b"Y0"]) == -110.0

    def test_force_baseline_missing_bodypart_raises(self, minimal_session):
        """With ``force=true`` and a bodypart missing from
        ``kinematics_baselines``, the accessor raises ``KeyError``."""
        m = minimal_session
        # AnimalInfo with only 'jaw' — requesting 'tongue' raises.
        animal_info = _animal_info(
            baselines={"jaw": {"x0": 0.0, "y0": 310.0}},
        )
        with pytest.raises(KeyError, match="tongue"):
            build_interpolated_trace(
                m["manifest"], "tongue", m["resolver"],
                params=m["params"], overwrite="force",
                animal_info=animal_info,
            )


# ---------------------------------------------------------------------------
# §8 test 11 — excluded session
# ---------------------------------------------------------------------------


class TestExcludedSession:
    def test_excluded_session_returns_none(self, minimal_session):
        """An animal with ``applies_to=[dlc]`` exclusion for the session
        date → ``build_interpolated_trace`` returns None without writing."""
        m = minimal_session
        animal_info = _animal_info(
            animal=m["animal"], date_=m["date"],
            exclusions=[Exclusion(m["date"], "bad session", ["dlc"])],
        )
        result = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force",
            animal_info=animal_info,
        )
        assert result is None
        # No parquet written — path derived the same way but must not exist.
        out_path = m["resolver"].interpolated_trace(
            bodypart="tongue", animal=m["animal"], date=m["date"],
        )
        assert not out_path.exists()


# ---------------------------------------------------------------------------
# §8 test 12 — parquet schema (strict)
# ---------------------------------------------------------------------------


class TestParquetSchema:
    def test_parquet_schema(self, minimal_session):
        """Emitted parquet has exactly 7 §2c columns and exactly 9
        file-level metadata attributes."""
        m = minimal_session
        out = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force",
            animal_info=m["animal_info"],
        )
        assert out is not None

        pf = pq.ParquetFile(out)
        # Columns — strict equality.
        expected_cols = {
            "frame_idx", "x_final", "y_final", "likelihood_raw",
            "is_interp_fill", "is_baseline_fill", "fill_method",
        }
        actual_cols = set(pf.schema.names)
        assert actual_cols == expected_cols, (
            f"Unexpected columns: extras={actual_cols - expected_cols}, "
            f"missing={expected_cols - actual_cols}"
        )

        # Dtypes (spot-check — strategy §2c types).
        arrow_schema = pf.schema_arrow
        assert str(arrow_schema.field("frame_idx").type) == "int64"
        assert str(arrow_schema.field("x_final").type) == "double"
        assert str(arrow_schema.field("y_final").type) == "double"
        assert str(arrow_schema.field("likelihood_raw").type) == "double"
        assert str(arrow_schema.field("is_interp_fill").type) == "bool"
        assert str(arrow_schema.field("is_baseline_fill").type) == "bool"
        assert str(arrow_schema.field("fill_method").type) == "int8"

        # File-level metadata — strict equality on the 9 required keys.
        meta = pf.metadata.metadata
        # Strip pandas/arrow-auto-added keys (b"pandas", b"ARROW:schema").
        user_meta = {
            k: v for k, v in meta.items()
            if k not in (b"pandas", b"ARROW:schema")
        }
        expected_keys = {
            b"X0", b"Y0", b"fps", b"n_frames", b"center_mode",
            b"baseline_stage", b"interpolation_version",
            SIDE_CONVENTION_MATCH_KEY.encode(),
            SIDE_CONVENTION_VERSION_KEY.encode(),
        }
        actual_keys = set(user_meta.keys())
        assert actual_keys == expected_keys, (
            f"Metadata key mismatch: extras={actual_keys - expected_keys}, "
            f"missing={expected_keys - actual_keys}"
        )

        # Spot-check values.
        assert meta[b"interpolation_version"].decode() == INTERPOLATION_VERSION
        assert meta[b"center_mode"].decode() == "centered_spout_midpoint"
        assert meta[b"baseline_stage"].decode() == _BASELINE_SOURCE_STAGE


# ---------------------------------------------------------------------------
# §8 test 13 — overwrite semantics
# ---------------------------------------------------------------------------


class TestOverwriteSemantics:
    def test_overwrite_skip_respects_existing(self, minimal_session):
        """``overwrite='skip'`` returns the existing path without
        re-running; ``'force'`` re-runs and updates the file."""
        m = minimal_session
        first = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force",
            animal_info=m["animal_info"],
        )
        assert first is not None
        mtime_first = first.stat().st_mtime_ns

        # skip — no re-run, same path, same mtime.
        second = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="skip",
            animal_info=m["animal_info"],
        )
        assert second == first
        assert second.stat().st_mtime_ns == mtime_first

        # force — re-runs, mtime changes.
        # Python resolves stat() at ns precision; tiny delay to ensure
        # the OS timestamp ticks.
        import time
        time.sleep(0.05)
        third = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force",
            animal_info=m["animal_info"],
        )
        assert third == first
        assert third.stat().st_mtime_ns > mtime_first


# ---------------------------------------------------------------------------
# §8 test 14 — QC NPZ sidecar
# ---------------------------------------------------------------------------


class TestEmitQcBundle:
    def test_emit_qc_bundle_emits_npz(self, minimal_session):
        """``emit_qc_bundle=True`` writes the sidecar with all 7-stage
        intermediate arrays + the diagnostic ``X0_data``/``Y0_data``
        scalars + the ``fill_method`` per-frame array."""
        m = minimal_session
        out = build_interpolated_trace(
            m["manifest"], "tongue", m["resolver"],
            params=m["params"], overwrite="force", emit_qc_bundle=True,
            animal_info=m["animal_info"],
        )
        assert out is not None

        qc_path = m["resolver"].interpolated_trace(
            bodypart="tongue", animal=m["animal"], date=m["date"],
            variant="qc_npz",
        )
        assert qc_path.exists()
        data = np.load(qc_path, allow_pickle=False)
        expected_arrays = {
            "x_raw", "y_raw", "lk_raw",
            "x_xrange", "y_xrange",
            "x_thr", "y_thr",
            "x_drop", "y_drop",
            "x_interp", "y_interp",
            "x_interp_filled", "y_interp_filled",
            "x_final", "y_final",
            "is_interp_fill", "is_baseline_fill", "fill_method",
        }
        expected_scalars = {
            "X0", "Y0", "X0_data", "Y0_data", "fps", "n_frames",
            "center_mode", "baseline_stage", "interpolation_version",
            "bodypart", "animal", "tone_centers_cam",
        }
        expected = expected_arrays | expected_scalars
        actual = set(data.files)
        assert expected.issubset(actual), (
            f"Sidecar missing keys: {expected - actual}"
        )
        # fill_method same length as x/y arrays.
        assert data["fill_method"].shape == data["x_final"].shape


# ---------------------------------------------------------------------------
# Item 2 (2026-04-24 review) — _center_mode_short helper
# ---------------------------------------------------------------------------


class TestCenterModeShort:
    def test_center_mode_short_strip_prefix(self):
        """The legacy long form ``centered_spout_midpoint`` strips to
        ``spout_midpoint`` for Phase 4.5-lite parquet lookup."""
        assert _center_mode_short("centered_spout_midpoint") == "spout_midpoint"
        assert _center_mode_short("centered_eye_midpoint") == "eye_midpoint"
        assert _center_mode_short("centered_nose") == "nose"

    def test_center_mode_short_passthrough_when_already_short(self):
        """Short forms pass through unchanged (Phase 4.5-lite callers
        may supply them directly)."""
        assert _center_mode_short("spout_midpoint") == "spout_midpoint"
        assert _center_mode_short("eye_midpoint") == "eye_midpoint"
        assert _center_mode_short("nose") == "nose"


# ---------------------------------------------------------------------------
# Sanity — reward-aligned pool mask (not in §8 but exercised for coverage)
# ---------------------------------------------------------------------------


def test_build_tone_aligned_pool_mask_shape_and_membership():
    """Windows OR cleanly around rounded-int reward centers; mask stays
    within ``[0, n_frames)``."""
    centers = np.array([100.0, 500.0, 1800.0])
    mask = _build_tone_aligned_pool_mask(
        n_frames=2000, tone_centers_float=centers,
        fps=250.0, win_ms=(0.0, 200.0),
    )
    # 200 ms at 250 fps → 50 frames after center.
    assert mask.shape == (2000,)
    assert mask[100] and mask[149]  # in window of center 100
    # Last center 1800, window ends at 1800+50=1850.
    assert mask[1850]
    # Out-of-window frames False.
    assert not mask[50]
    assert not mask[1900]


def test_interpolation_result_dataclass_has_expected_fields():
    """Regression guard: the dataclass field set must stay stable."""
    import dataclasses
    expected_fields = {
        "x_raw", "y_raw", "lk_raw",
        "x_xrange", "y_xrange",
        "x_thr", "y_thr",
        "x_drop", "y_drop",
        "x_interp", "y_interp",
        "x_interp_filled", "y_interp_filled",
        "x_final", "y_final",
        "is_interp_fill", "is_baseline_fill", "fill_method",
        "X0", "Y0", "X0_data", "Y0_data",
        "fps", "n_frames", "center_mode", "baseline_stage",
        "interpolation_version", "bodypart", "animal", "date",
        "wavesurfer_sides_match_mouse_sides",
        "tone_centers_cam",
    }
    actual_fields = {f.name for f in dataclasses.fields(InterpolationResult)}
    assert actual_fields == expected_fields
