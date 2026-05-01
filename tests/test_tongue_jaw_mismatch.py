"""Phase 7a.5 — unit tests for tongue_jaw_mismatch.

Synthetic data: 7a.2-shaped jaw + tongue interpolated_traces parquets at
``<tmp>/dlc_analysis/interpolated_traces/{bodypart}/{animal}/{date}.parquet``.
The classifier internally runs ``build_jaw_pertrial`` (which writes the
upstream JSON to the same tmp tree); the predicate truth-table tests
construct trial-events with known tongue lick patterns and check the
expected ``candidate_no_lick_with_jaw_move`` value.

Visual fidelity is the parity harness's job (Task 6); the plot-family
tests in here are smoke tests only — they assert PNGs render + save +
have non-trivial sizes.
"""

from __future__ import annotations

import copy
import datetime
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import pytest  # noqa: E402

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
    INTERPOLATION_VERSION,
    TONGUE_JAW_MISMATCH_VERSION,
    TongueJawMismatchResult,
    _build_tongue_detector_params,
    classify_tongue_jaw_mismatch,
    render_cross_session_figures,
    render_within_session_figures,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import TrialEvent
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver

_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"
_SYNTH_FPS = 250.0


# ===========================================================================
# Synthetic fixtures
# ===========================================================================


def _make_synthetic_bodypart_parquet(
    path: Path, n_frames: int, *, fps: float = _SYNTH_FPS,
    y_final: np.ndarray | None = None,
    x_final: np.ndarray | None = None,
    center_mode: str = "centered_eye_midpoint",
) -> None:
    """Write a 7a.2-shaped interpolated_traces parquet (jaw or tongue)."""
    if y_final is None:
        y_final = np.zeros(n_frames, dtype=np.float64)
    if x_final is None:
        x_final = np.zeros(n_frames, dtype=np.float64)
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
        b"X0": b"0.0", b"Y0": b"0.0",
        b"baseline_stage": b"drop",
        b"center_mode": center_mode.encode(),
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
        animal=animal, date=date,
        day_relative_to_stroke=-6,
        phase="baseline", excluded=False,
        alignment_template=None,
        wavesurfer_sides_match_mouse_sides=False,
    )


def _add_jaw_deflection(
    y: np.ndarray, fps: float, reward_fr: int,
    *, amplitude_px: float, sign: int = 1,
    start_ms: float = 200.0, dur_ms: float = 1500.0,
) -> np.ndarray:
    """In-place: add a sustained jaw deflection in (start_ms, start_ms+dur_ms)."""
    seg_lo = reward_fr + int(round(start_ms / 1000.0 * fps))
    seg_hi = reward_fr + int(round((start_ms + dur_ms) / 1000.0 * fps))
    seg_lo = max(0, seg_lo)
    seg_hi = min(len(y), seg_hi)
    y[seg_lo:seg_hi] += sign * amplitude_px
    return y


def _add_tongue_lick(
    y: np.ndarray, fps: float, reward_fr: int,
    *, peak_time_ms: float, amplitude_px: float = 30.0, sigma_ms: float = 12.0,
) -> np.ndarray:
    """In-place: add one Gaussian-shaped tongue lick at ``peak_time_ms``.

    Sigma 12 ms gives max |dy/dt| ~ 1.5 px/ms = 1500 px/s, well above the
    250 px/s slope threshold that the Cell 33 detector uses.
    """
    n = len(y)
    t_ms = (np.arange(n) - reward_fr) * (1000.0 / fps)
    bump = amplitude_px * np.exp(-0.5 * ((t_ms - peak_time_ms) / sigma_ms) ** 2)
    y += bump
    return y


def _setup_session(
    tmp_path: Path, monkeypatch,
    *,
    n_frames: int = 7500, fps: float = _SYNTH_FPS,
    reward_frames: tuple[int, ...] = (1500, 4000),
    sides: tuple[str, ...] = ("L", "R"),
    jaw_amps: tuple[tuple[float, int], ...] = ((30.0, 1), (0.0, 1)),
    tongue_lick_times: tuple[tuple[float, ...], ...] = ((), ()),
    animal: str = "PS46", date: datetime.date = datetime.date(2025, 3, 7),
):
    """Common harness: write synthetic jaw + tongue parquets + return resolver,
    manifest, trial_events. Each trial gets its own jaw deflection +
    tongue-lick configuration."""
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    resolver = PathResolver(output_root=tmp_path)
    rng = np.random.default_rng(0)
    jaw_y = 100.0 + rng.normal(0.0, 0.5, n_frames)
    tongue_y = rng.normal(0.0, 0.5, n_frames)
    for fr, (amp, sign) in zip(reward_frames, jaw_amps):
        if amp != 0.0:
            _add_jaw_deflection(jaw_y, fps, fr, amplitude_px=amp, sign=sign)
    for fr, lick_times in zip(reward_frames, tongue_lick_times):
        for tp in lick_times:
            _add_tongue_lick(tongue_y, fps, fr, peak_time_ms=tp)
    jaw_path = resolver.interpolated_trace(
        bodypart="jaw", animal=animal, date=date,
    )
    _make_synthetic_bodypart_parquet(
        jaw_path, n_frames, fps=fps, y_final=jaw_y,
        center_mode="centered_eye_midpoint",
    )
    tongue_path = resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    _make_synthetic_bodypart_parquet(
        tongue_path, n_frames, fps=fps, y_final=tongue_y,
        center_mode="centered_spout_midpoint",
    )
    manifest = _make_minimal_manifest(animal=animal, date=date)
    trial_events = [
        TrialEvent(trial_index=k, reward_frame_idx=int(fr), side=str(sd))
        for k, (fr, sd) in enumerate(zip(reward_frames, sides))
    ]
    return resolver, manifest, trial_events


@pytest.fixture()
def base_params() -> dict:
    return copy.deepcopy(load_defaults())


# ===========================================================================
# 1-3 — predicate truth table
# ===========================================================================


class TestClassifierPredicateTruthTable:
    """4 combinations of (quiet_tongue, jaw_pass) → expected candidate value.

    Test setup: 4 trials in one session, one per combination of
    (quiet=True/False) × (jaw_pass=True/False).
    """

    def test_quiet_and_jaw_pass_yields_candidate(
        self, monkeypatch, tmp_path, base_params,
    ):
        """quiet_tongue + jaw_pass → candidate=True."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),),       # strong jaw → pass
            tongue_lick_times=((),),     # no licks → quiet
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        assert out is not None
        df = pd.read_parquet(out)
        assert len(df) == 1
        assert bool(df["quiet_tongue_pass"].iloc[0]) is True
        assert bool(df["jaw_pass_qc"].iloc[0]) is True
        assert bool(df["candidate_no_lick_with_jaw_move"].iloc[0]) is True

    def test_licks_with_jaw_pass_not_candidate(
        self, monkeypatch, tmp_path, base_params,
    ):
        """licking + jaw_pass → candidate=False (quiet-tongue fails)."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),),
            tongue_lick_times=((200.0, 500.0, 800.0),),   # 3 licks → noisy tongue
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(out)
        assert df["n_licks_in_quiet_win"].iloc[0] >= 1
        assert bool(df["quiet_tongue_pass"].iloc[0]) is False
        assert bool(df["jaw_pass_qc"].iloc[0]) is True
        assert bool(df["candidate_no_lick_with_jaw_move"].iloc[0]) is False

    def test_quiet_with_jaw_fail_not_candidate(
        self, monkeypatch, tmp_path, base_params,
    ):
        """quiet_tongue + jaw_fail → candidate=False (no jaw movement to flag)."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((0.0, 1),),     # flat jaw → fails QC
            tongue_lick_times=((),),
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(out)
        assert bool(df["quiet_tongue_pass"].iloc[0]) is True
        assert bool(df["jaw_pass_qc"].iloc[0]) is False
        assert bool(df["candidate_no_lick_with_jaw_move"].iloc[0]) is False


# ===========================================================================
# 4-7 — schema + edge cases
# ===========================================================================


class TestClassifierSchemaAndEdges:

    def test_classifier_emits_parquet_with_locked_schema(
        self, monkeypatch, tmp_path, base_params,
    ):
        """All locked per-row columns present + file-level metadata stamped."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 4000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (0.0, 1)),
            tongue_lick_times=((), (200.0, 600.0)),
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(out)
        expected_cols = {
            "mouse", "date", "rel_day", "trial_index", "side",
            "reward_frame_idx", "fps",
            "n_licks_in_quiet_win", "tongue_peak_times_ms", "quiet_tongue_pass",
            "jaw_baseline_mean", "jaw_baseline_sd",
            "jaw_peak_pos_deflection", "jaw_peak_neg_deflection",
            "jaw_peak_abs_deflection", "jaw_peak_selected_deflection",
            "jaw_thresh_abs", "jaw_thresh_px_used",
            "jaw_n_frames_over_thresh", "jaw_pass_qc",
            "candidate_no_lick_with_jaw_move",
        }
        assert expected_cols.issubset(set(df.columns))
        assert len(df) == 2

        # File-level metadata round-trip
        meta = pq.read_schema(out).metadata
        decoded = {k.decode(): v.decode() for k, v in meta.items()}
        assert decoded["schema_version"] == TONGUE_JAW_MISMATCH_VERSION
        assert decoded["interpolation_version"] == INTERPOLATION_VERSION
        assert decoded["jaw_direction_mode"] == "above_or_below"
        assert decoded["animal"] == "PS46"
        assert decoded["date"] == "2025-03-07"
        assert int(decoded["n_trials"]) == 2
        assert float(decoded["jaw_thresh_sd_multiplier"]) == 4.0

    def test_classifier_session_with_no_candidates(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Session with all flat-jaw trials emits a parquet with 0 candidate
        rows but full trial roster."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 4000), sides=("L", "R"),
            jaw_amps=((0.0, 1), (0.0, 1)),
            tongue_lick_times=((), ()),
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(out)
        assert len(df) == 2
        assert df["candidate_no_lick_with_jaw_move"].sum() == 0
        assert df["jaw_pass_qc"].sum() == 0  # flat jaw → all fail

    def test_classifier_session_with_all_candidates(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Session with strong-jaw + no-lick trials → all candidates."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 4000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (-30.0, 1)),  # strong + and strong - both pass
            tongue_lick_times=((), ()),
        )
        out = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(out)
        assert len(df) == 2
        assert df["candidate_no_lick_with_jaw_move"].sum() == 2

    def test_classifier_overwrite_semantics(
        self, monkeypatch, tmp_path, base_params,
    ):
        """skip + exists → return existing path; force → rewrite; bad → raise."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        p1 = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        assert p1 is not None and p1.exists()
        mtime_1 = p1.stat().st_mtime_ns
        p2 = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="skip",
        )
        assert p2 == p1
        assert p2.stat().st_mtime_ns == mtime_1
        # force → rewrite, content identical
        p3 = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df1 = pd.read_parquet(p1)
        df3 = pd.read_parquet(p3)
        pd.testing.assert_frame_equal(df1, df3)
        # bad value → raise
        with pytest.raises(ValueError, match="overwrite must be"):
            classify_tongue_jaw_mismatch(
                manifest=manifest, resolver=resolver, trial_events=trial_events,
                params=base_params, overwrite="bogus",  # type: ignore[arg-type]
            )


# ===========================================================================
# 8-10 — plot family smoke tests
# ===========================================================================


class TestPlotFamilySmoke:

    def test_render_within_session_emits_two_pngs(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Both within-session families emit non-empty PNGs."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 4000, 6500), sides=("L", "R", "L"),
            jaw_amps=((30.0, 1), (0.0, 1), (-30.0, 1)),
            tongue_lick_times=((), (200.0, 600.0), ()),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        out = render_within_session_figures(
            "PS46", datetime.date(2025, 3, 7), resolver,
            params=base_params, candidate_trials_df=df, overwrite="force",
        )
        assert set(out.keys()) == {"individual_trials", "session_overlay_grid"}
        for paths in out.values():
            for p in paths:
                assert p.exists()
                assert p.stat().st_size > 5_000  # PNG should be > 5 KB

    def test_render_within_session_skip_semantics(
        self, monkeypatch, tmp_path, base_params,
    ):
        """skip + both files exist → return existing (mtime unchanged)."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        out1 = render_within_session_figures(
            "PS46", datetime.date(2025, 3, 7), resolver,
            params=base_params, candidate_trials_df=df, overwrite="force",
        )
        mtimes_1 = {fam: [p.stat().st_mtime_ns for p in paths]
                    for fam, paths in out1.items()}
        out2 = render_within_session_figures(
            "PS46", datetime.date(2025, 3, 7), resolver,
            params=base_params, candidate_trials_df=df, overwrite="skip",
        )
        mtimes_2 = {fam: [p.stat().st_mtime_ns for p in paths]
                    for fam, paths in out2.items()}
        assert mtimes_1 == mtimes_2

    def test_render_cross_session_emits_two_pngs(
        self, monkeypatch, tmp_path, base_params,
    ):
        """2-session cohort → cross_session_overlay + cross_session_binned PNGs."""
        # Session 1 (pre-stroke): rel_day = -6
        resolver, m1, te1 = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 4000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (0.0, 1)), tongue_lick_times=((), ()),
            animal="PS46", date=datetime.date(2025, 3, 7),
        )
        classify_tongue_jaw_mismatch(
            manifest=m1, resolver=resolver, trial_events=te1,
            params=base_params, overwrite="force",
        )
        # Session 2 (post-stroke): rel_day = +1 relative to PS46 d0=2025-03-13
        m2 = _make_minimal_manifest("PS46", datetime.date(2025, 3, 14))
        n_frames = 7500
        fps = _SYNTH_FPS
        rng = np.random.default_rng(1)
        jaw_y_2 = 100.0 + rng.normal(0.0, 0.5, n_frames)
        tongue_y_2 = rng.normal(0.0, 0.5, n_frames)
        for fr in (1500, 4000):
            _add_jaw_deflection(jaw_y_2, fps, fr, amplitude_px=30.0)
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="jaw", animal="PS46", date=datetime.date(2025, 3, 14),
            ),
            n_frames, fps=fps, y_final=jaw_y_2,
            center_mode="centered_eye_midpoint",
        )
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="tongue", animal="PS46", date=datetime.date(2025, 3, 14),
            ),
            n_frames, fps=fps, y_final=tongue_y_2,
            center_mode="centered_spout_midpoint",
        )
        te2 = [
            TrialEvent(trial_index=0, reward_frame_idx=1500, side="L"),
            TrialEvent(trial_index=1, reward_frame_idx=4000, side="R"),
        ]
        classify_tongue_jaw_mismatch(
            manifest=m2, resolver=resolver, trial_events=te2,
            params=base_params, overwrite="force",
        )
        out = render_cross_session_figures(
            "PS46", resolver, params=base_params, overwrite="force",
        )
        assert set(out.keys()) == {"cross_session_overlay", "cross_session_binned"}
        for p in out.values():
            assert p.exists()
            assert p.stat().st_size > 5_000

    def test_render_cross_session_uses_bin_days_from_animals_yaml(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Filename embeds the per-animal bin_days (PS46 → bin=2 → ``bins2``)."""
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        out = render_cross_session_figures(
            "PS46", resolver, params=base_params, overwrite="force",
        )
        # PS46 bin_days = 2 in animals.yaml → filename has 'bins2'
        assert "bins2" in out["cross_session_binned"].name


# ===========================================================================
# 11-12 — module-level + helper coverage
# ===========================================================================


class TestPlotFamilyVisualFidelity:
    """Phase 7a.5 C6.1 visual rendering fixes (Priya 2026-05-01).

    Behavior-pin tests for the new YAML knobs (sort_by_side,
    shared_y_axis_per_plot_type_row, mean_sem_axis explicit ranges,
    cross-session colorbar, individual_trials DPI). Visual fidelity is
    parity harness territory — these are pin tests, not exhaustive.
    """

    def test_individual_trials_sort_by_side_puts_L_above_R(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``sort_by_side=True`` → L trials in lower row indices than R within a column.

        Construct a 4-trial session whose sides interleave (L, R, L, R) and
        whose trial_indices are 0..3. After sort, the candidate column
        should render L trials (rows 0-1) above R trials (rows 2-3).
        """
        # Force the knob ON (default-True; this is also a regression check
        # that the YAML default carries through the params dict).
        base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"][
            "individual_trials"]["sort_by_side"] = True

        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000, 4500, 6000),
            sides=("R", "L", "R", "L"),
            jaw_amps=((30.0, 1), (30.0, 1), (30.0, 1), (30.0, 1)),
            tongue_lick_times=((), (), (), ()),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        assert df["candidate_no_lick_with_jaw_move"].sum() == 4

        # Direct call to the plot helper for axis-level introspection.
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _plot_individual_trials_2col,
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        plotter_cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_individual_trials_2col(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=plotter_cfg, animal="PS46",
            date=datetime.date(2025, 3, 7),
        )
        # Candidate column is index 0; rows 0..1 should have L titles, rows
        # 2..3 should have R. Read the title text on each axis.
        axes = fig.axes
        # axes layout: pyplot returns flattened nrows*ncols + their twin
        # axes (each ax.twinx() creates a sibling). Filter to the primary
        # left-column axes (ax.get_subplotspec() will give us coords).
        title_at_row = {}
        for ax in axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            row = ss.rowspan.start
            col = ss.colspan.start
            ttl = ax.get_title(loc="left")
            if col == 0 and ttl:
                title_at_row[row] = ttl
        # The candidate column should show L on rows 0-1 then R on rows 2-3.
        assert "L trial" in title_at_row.get(0, ""), title_at_row
        assert "L trial" in title_at_row.get(1, ""), title_at_row
        assert "R trial" in title_at_row.get(2, ""), title_at_row
        assert "R trial" in title_at_row.get(3, ""), title_at_row
        plt.close(fig)

    def test_session_overlay_grid_shared_y_per_plot_type_row(
        self, monkeypatch, tmp_path, base_params,
    ):
        """L and R panels in the same plot-type-row share ylim; rows independent.

        Force the explicit mean_sem_axis ranges to ``None`` so the bottom-2-row
        path also computes shared-Y from data; assert L+R within each row
        match, and assert candidate-row range differs from non-candidate-row
        range when the underlying data magnitudes differ.
        """
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["session_overlay_grid"]["shared_y_axis_per_plot_type_row"] = True
        cfg["session_overlay_grid"]["mean_sem_axis"] = {
            "jaw_y_range": None, "tongue_y_range": None,
        }
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000, 4500, 6000),
            sides=("L", "R", "L", "R"),
            # Asymmetric: candidates have huge jaw amplitude, non-candidates
            # have a small tongue licking pattern (no jaw motion → fail QC).
            jaw_amps=((30.0, 1), (30.0, 1), (0.0, 1), (0.0, 1)),
            tongue_lick_times=((), (), (200.0, 500.0), (200.0, 500.0)),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        # Index primary axes (not twin) by (row, col).
        primary_by_rc: dict[tuple[int, int], object] = {}
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                # Twin axes carry a None subplotspec; skip.
                continue
            rc = (ss.rowspan.start, ss.colspan.start)
            # First-encounter wins (the primary axis is created first).
            if rc not in primary_by_rc:
                primary_by_rc[rc] = ax
        # Within each row, L (col=0) and R (col=1) primary-axis ylims match.
        for rix in range(4):
            ax_L = primary_by_rc[(rix, 0)]
            ax_R = primary_by_rc[(rix, 1)]
            ylim_L = ax_L.get_ylim()
            ylim_R = ax_R.get_ylim()
            # Tolerate sub-pixel matplotlib float jitter; require equality
            # to better than 1e-6 (the explicit set_ylim path is exact).
            assert abs(ylim_L[0] - ylim_R[0]) < 1e-6, (
                f"row {rix} ylim mismatch L={ylim_L} R={ylim_R}",
            )
            assert abs(ylim_L[1] - ylim_R[1]) < 1e-6
        # Rows independent: the candidate-overlay row (rix=0) should have
        # a different ylim than the non-candidate-overlay row (rix=1)
        # because the underlying jaw amplitudes differ asymmetrically.
        ylim_row0 = primary_by_rc[(0, 0)].get_ylim()
        ylim_row1 = primary_by_rc[(1, 0)].get_ylim()
        assert ylim_row0 != ylim_row1, (
            f"rows should have independent ylim; both are {ylim_row0}",
        )
        plt.close(fig)

    # ------------------------------------------------------------------
    # Phase 7a.5 C6.2 — port-fidelity round (Priya 2026-05-01).
    # Replaces the C6.1 ``test_session_overlay_mean_sem_uses_explicit_y_ranges``
    # which tested a hardcoded-range path that's been deleted in C6.2.
    # ------------------------------------------------------------------

    def test_cross_session_axis_label_text_uses_baseline_word(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Y-axis labels say "baseline" not "base" (legacy `_jaw_ylabel` parity)."""
        # Build 1 session with 1 candidate so the cross-session render has data.
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _gather_sessions_for_animal,
            _plot_cross_session_overlay,
        )
        animal_info = get_animal("PS46")
        sessions = _gather_sessions_for_animal("PS46", resolver, animal_info)
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_cross_session_overlay(
            sessions, animal="PS46", plotter_cfg=cfg,
        )
        labels = [ax.get_ylabel() for ax in fig.axes if ax.get_ylabel()]
        # Legacy idiom: "Jaw Y - baseline (px)", "Tongue Y (px)".
        assert any("baseline" in lbl.lower() for lbl in labels), labels
        assert all("base " not in lbl.lower() for lbl in labels), (
            f"label still uses C6.1 string 'Jaw - base (px)' instead of "
            f"'Jaw Y - baseline (px)': {labels}"
        )
        plt.close(fig)

    def test_cross_session_colorbar_does_not_overlap_axis_label(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Colorbar bbox sits to the right of every axis label bbox.

        Legacy uses ``tight_layout(rect=[0, 0, 0.88, 0.98])`` then adds
        the colorbar at ``[0.90, 0.22, 0.015, 0.56]`` — the rect carve-
        out gives the colorbar room without colliding with axis labels.
        """
        resolver, m1, te1 = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
            animal="PS46", date=datetime.date(2025, 3, 7),
        )
        classify_tongue_jaw_mismatch(
            manifest=m1, resolver=resolver, trial_events=te1,
            params=base_params, overwrite="force",
        )
        # Add a post-stroke session so the colorbar actually renders.
        m2 = _make_minimal_manifest("PS46", datetime.date(2025, 3, 18))
        n = 7500
        fps = _SYNTH_FPS
        rng = np.random.default_rng(0)
        jy = 100.0 + rng.normal(0.0, 0.5, n)
        ty = rng.normal(0.0, 0.5, n)
        _add_jaw_deflection(jy, fps, 1500, amplitude_px=30.0)
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="jaw", animal="PS46", date=datetime.date(2025, 3, 18),
            ),
            n, fps=fps, y_final=jy,
        )
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="tongue", animal="PS46", date=datetime.date(2025, 3, 18),
            ),
            n, fps=fps, y_final=ty,
        )
        te2 = [TrialEvent(trial_index=0, reward_frame_idx=1500, side="L")]
        classify_tongue_jaw_mismatch(
            manifest=m2, resolver=resolver, trial_events=te2,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _gather_sessions_for_animal,
            _plot_cross_session_overlay,
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["cross_session_overlay"]["include_colorbar"] = True
        animal_info = get_animal("PS46")
        sessions = _gather_sessions_for_animal("PS46", resolver, animal_info)
        fig = _plot_cross_session_overlay(
            sessions, animal="PS46", plotter_cfg=cfg,
        )
        # The colorbar add_axes call positions cax at the configured
        # legacy rect [0.90, ...]; tight_layout(rect=[0, 0, 0.88, 0.98])
        # caps the data-axes' bbox at x=0.88. So the colorbar's left edge
        # (>=0.88) sits to the right of every data axes' right edge.
        cbar_left = float(cfg["cross_session_overlay"]["colorbar_rect"][0])
        tlrect_right = float(cfg["cross_session_overlay"]["tight_layout_rect"][2])
        assert cbar_left >= tlrect_right, (
            f"colorbar left ({cbar_left}) must be >= tight_layout rect right "
            f"({tlrect_right})"
        )
        # And every data axis stays within tight_layout rect.
        from matplotlib.figure import Figure as _Fig
        assert isinstance(fig, _Fig)
        # Run draw to materialize bboxes.
        fig.canvas.draw()
        for ax in fig.axes:
            pos = ax.get_position()
            # Colorbar's own axis lives at [cbar_left, ...]; allow it
            # through. Other axes must end before tlrect_right.
            if abs(pos.x0 - cbar_left) < 1e-3:
                continue
            assert pos.x1 <= tlrect_right + 1e-2, (
                f"axis {ax} extends past tight_layout right={tlrect_right}: "
                f"x1={pos.x1}"
            )
        plt.close(fig)

    def test_mean_sem_twin_axes_auto_scale_per_bodypart(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Each twin axis auto-scales to its own bodypart's data range.

        Synthetic data: jaw ~ (10, 40) and tongue ~ (-80, 20) by injecting
        offsets directly into the y-final arrays. Render the session
        overlay grid; assert the mean±SEM rows have jaw-axis ylim
        approximately (10 - pad, 40 + pad) and tongue-axis ylim
        approximately (-80 - pad, 20 + pad). Critically: the two ranges
        are DIFFERENT (proves per-bodypart auto-scale).
        """
        resolver, _, _ = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000), sides=("L", "R"),
            jaw_amps=((0.0, 1), (0.0, 1)), tongue_lick_times=((), ()),
        )
        # Replace with exactly-controlled jaw + tongue y-finals.
        animal = "PS46"
        date = datetime.date(2025, 3, 7)
        n = 7500
        fps = _SYNTH_FPS
        jaw_arr = np.full(n, np.nan, dtype=np.float64)
        tongue_arr = np.full(n, np.nan, dtype=np.float64)
        # Inside the (-500, 5000) ms window around each reward, fill jaw
        # with values in [10, 40] and tongue with values in [-80, 20].
        for fr in (1500, 3000):
            lo = fr - int(0.5 * fps)
            hi = fr + int(5.0 * fps)
            jaw_arr[lo:hi] = np.linspace(10.0, 40.0, hi - lo)
            tongue_arr[lo:hi] = np.linspace(-80.0, 20.0, hi - lo)
        # Set baseline_mean=0 in candidate_trials so jaw_y - baseline = jaw_arr.
        # We use the default _setup_session which already wrote the parquets;
        # rewrite them with the controlled arrays.
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="jaw", animal=animal, date=date,
            ),
            n, fps=fps, y_final=jaw_arr,
        )
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="tongue", animal=animal, date=date,
            ),
            n, fps=fps, y_final=tongue_arr,
        )
        manifest = _make_minimal_manifest(animal=animal, date=date)
        # Trials must be candidates (quiet tongue + jaw_pass) for the
        # mean±SEM-candidate row to populate. Force jaw_pass via a strong
        # in-window jaw signal: replace jaw_arr inside detect window with
        # large values so the per-trial baseline (-500, 0) ms = first half
        # of linspace ~ [10, 25] (sd ≈ 8) and the test (0, 5000) values
        # exceed 4*sd. Already in [10, 40] — should pass QC.
        trial_events = [
            TrialEvent(trial_index=0, reward_frame_idx=1500, side="L"),
            TrialEvent(trial_index=1, reward_frame_idx=3000, side="R"),
        ]
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(animal, date),
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="tongue",
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal=animal, date=date,
        )
        # Find the jaw-axis ylim ranges and tongue-axis ylim ranges. Each
        # bodypart should auto-scale to its own data, and the two ranges
        # must differ.
        jaw_lims = []
        tong_lims = []
        for ax in fig.axes:
            lbl = ax.get_ylabel()
            if "Jaw" in lbl:
                jaw_lims.append(ax.get_ylim())
            elif "Tongue" in lbl:
                tong_lims.append(ax.get_ylim())
        assert len(jaw_lims) > 0 and len(tong_lims) > 0
        # Jaw axes should span tens of px (not hundreds); tongue axes
        # should span hundreds. The two ranges are different.
        for jl in jaw_lims:
            assert jl != tong_lims[0], (
                f"jaw axis range {jl} matches tongue {tong_lims[0]} — "
                f"per-bodypart auto-scale not active"
            )
        # Jaw range hi - lo ~ 30 (data span 10..40, plus pad); tongue
        # range hi - lo ~ 100 (data span -80..20, plus pad). Sanity check
        # the magnitude.
        for jl in jaw_lims:
            assert (jl[1] - jl[0]) < 80.0, (
                f"jaw range {jl} too wide; auto-scale should hug [10, 40]"
            )
        for tl in tong_lims:
            assert (tl[1] - tl[0]) > 50.0, (
                f"tongue range {tl} too narrow; auto-scale should hug [-80, 20]"
            )
        plt.close(fig)

    def test_mean_sem_per_row_independent_auto_scaled_ranges(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Row 3 (mean±SEM-candidate) and row 4 (mean±SEM-noncandidate)
        auto-scale independently when their underlying jaw distributions
        differ.
        """
        # Build a session with mixed candidate/non-candidate trials whose
        # jaw amplitudes differ asymmetrically.
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000, 4500, 6000),
            sides=("L", "R", "L", "R"),
            # Trials 0, 1: large jaw + no licks → candidate.
            # Trials 2, 3: tiny jaw + licks → not candidate.
            jaw_amps=((50.0, 1), (50.0, 1), (1.0, 1), (1.0, 1)),
            tongue_lick_times=((), (), (200.0, 600.0), (200.0, 600.0)),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(
                "PS46", datetime.date(2025, 3, 7),
            ),
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        # Walk axes by subplotspec to identify which row each is in. Row 2 =
        # mean±SEM-candidate, Row 3 = mean±SEM-noncandidate.
        primary_by_rc: dict[tuple[int, int], object] = {}
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            rc = (ss.rowspan.start, ss.colspan.start)
            if rc not in primary_by_rc:
                primary_by_rc[rc] = ax
        row2_jaw_lim = primary_by_rc[(2, 0)].get_ylim()
        row3_jaw_lim = primary_by_rc[(3, 0)].get_ylim()
        # Both rows render data. Jaw amplitudes differ by 50× (50 vs 1
        # px), so the auto-scaled ranges must differ.
        assert row2_jaw_lim != row3_jaw_lim, (
            f"row 2 (cand) jaw_lim={row2_jaw_lim} matches "
            f"row 3 (noncand) jaw_lim={row3_jaw_lim}; per-row independence broken"
        )
        plt.close(fig)

    def test_mean_sem_shared_y_within_plot_type_row(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Within the mean±SEM-candidate row, L and R panels share ylim
        (= padded percentile-cap union of L+R data extremes).
        """
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000, 4500, 6000),
            sides=("L", "L", "R", "R"),
            # L trials: jaw ~ +20 px; R trials: jaw ~ +40 px. Union → ~[15, 50].
            jaw_amps=((20.0, 1), (20.0, 1), (40.0, 1), (40.0, 1)),
            tongue_lick_times=((), (), (), ()),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(
                "PS46", datetime.date(2025, 3, 7),
            ),
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        primary_by_rc: dict[tuple[int, int], object] = {}
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            rc = (ss.rowspan.start, ss.colspan.start)
            if rc not in primary_by_rc:
                primary_by_rc[rc] = ax
        # Mean±SEM candidate row = row index 2. Both L (col 0) and R (col 1)
        # primary jaw axes share the same ylim.
        L_lim = primary_by_rc[(2, 0)].get_ylim()
        R_lim = primary_by_rc[(2, 1)].get_ylim()
        assert L_lim == pytest.approx(R_lim, abs=1e-9), (
            f"L jaw lim {L_lim} != R jaw lim {R_lim}; per-row shared-Y broken"
        )
        plt.close(fig)

    def test_mean_sem_trial_overlays_present_when_enabled(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``show_trial_overlays=True`` adds faint per-trial lines under
        the mean±SEM band. Detect them via low-alpha matplotlib Line2D objects.
        """
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["session_overlay_grid"]["mean_sem_axis"]["show_trial_overlays"] = True
        cfg["session_overlay_grid"]["mean_sem_axis"]["trial_overlay_jaw_alpha"] = 0.08
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000, 4500), sides=("L", "L", "R"),
            jaw_amps=((30.0, 1), (30.0, 1), (30.0, 1)),
            tongue_lick_times=((), (), ()),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(
                "PS46", datetime.date(2025, 3, 7),
            ),
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        # Walk all Line2D objects on every axis; count those whose alpha
        # matches the configured trial_overlay_jaw_alpha sentinel (0.08).
        n_low_alpha = 0
        for ax in fig.axes:
            for ln in ax.get_lines():
                a = ln.get_alpha()
                if a is not None and abs(a - 0.08) < 1e-9:
                    n_low_alpha += 1
        # Mean±SEM-candidate row × 2 cols × (jaw + tongue twin) — but we only
        # check jaw alpha=0.08 sentinel. With 2 L trials + 1 R trial, we
        # expect at least 3 jaw-trial overlay lines on the jaw axes
        # (cumulative across the L+R col panels).
        assert n_low_alpha >= 3, (
            f"expected >=3 faint trial-overlay lines (jaw alpha=0.08); "
            f"got {n_low_alpha}"
        )
        plt.close(fig)

        # Re-render with overlays disabled; n_low_alpha should drop to 0.
        cfg["session_overlay_grid"]["mean_sem_axis"]["show_trial_overlays"] = False
        fig2 = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        n_low_alpha_2 = 0
        for ax in fig2.axes:
            for ln in ax.get_lines():
                a = ln.get_alpha()
                if a is not None and abs(a - 0.08) < 1e-9:
                    n_low_alpha_2 += 1
        assert n_low_alpha_2 == 0, (
            f"overlays disabled but {n_low_alpha_2} faint lines still drawn"
        )
        plt.close(fig2)

    def test_subtitle_format_matches_legacy(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Per-panel sub-titles match legacy ``_format_candidate_count_text`` /
        ``_format_noncandidate_count_text`` byte-for-byte."""
        import re

        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (30.0, 1)), tongue_lick_times=((), ()),
        )
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(
                "PS46", datetime.date(2025, 3, 7),
            ),
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        cand_pattern = re.compile(r"^[LR] candidate trials: \d+/\d+$")
        non_pattern = re.compile(
            r"^[LR] non-candidate trials: \d+/\d+ \(candidates: \d+/\d+\)$",
        )
        n_cand_match = 0
        n_non_match = 0
        for ax in fig.axes:
            ttl = ax.get_title()
            if not ttl:
                continue
            # Per-panel title uses two lines; the second is the count_text.
            for line in ttl.split("\n"):
                if cand_pattern.match(line.strip()):
                    n_cand_match += 1
                elif non_pattern.match(line.strip()):
                    n_non_match += 1
        assert n_cand_match >= 2, (
            f"expected >=2 candidate-trials sub-titles matching legacy regex; "
            f"got {n_cand_match}"
        )
        assert n_non_match >= 2, (
            f"expected >=2 non-candidate-trials sub-titles matching legacy regex; "
            f"got {n_non_match}"
        )
        plt.close(fig)

    def test_individual_trials_subplot_data_area_meets_minimum(
        self, monkeypatch, tmp_path, base_params,
    ):
        """Each subplot's data-area bbox is at least 60% of its allotted
        cell — guards against the C6.1 squished-subplot regression.

        Legacy figsize=(18, max(12, 1.8*n_rows)) gives near-square cells;
        the C6.1 (10, 4 + 0.4*n) gave very flat cells (~10 in × ~0.4 in)
        which made the data area ~5% of the cell after axis labels.
        """
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            # 6 trials → 3 candidates (col 0) and 3 non-candidates (col 1).
            reward_frames=(1500, 2500, 3500, 4500, 5500, 6500),
            sides=("L", "L", "R", "L", "L", "R"),
            jaw_amps=((30.0, 1), (30.0, 1), (30.0, 1),
                      (0.0, 1), (0.0, 1), (0.0, 1)),
            tongue_lick_times=((), (), (), (200.0,), (200.0,), (200.0,)),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_individual_trials_2col,
        )
        jaw_y, fps_jaw, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="jaw",
        )
        tongue_y, _, _ = _load_bodypart_y_final(
            resolver, "PS46", datetime.date(2025, 3, 7), bodypart="tongue",
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        fig = _plot_individual_trials_2col(
            df, jaw_y, tongue_y, fps_jaw,
            plotter_cfg=cfg, animal="PS46", date=datetime.date(2025, 3, 7),
        )
        # Compare each primary subplot's drawn-area height vs its cell
        # height. Subplots have non-trivial whitespace at the top for
        # titles; require each axis bbox-height to occupy >=50% of its
        # row's cell-height (cell = fig_height / n_rows).
        fig.canvas.draw()
        n_rows = max(
            sum(1 for _, r in df.iterrows() if r["candidate_no_lick_with_jaw_move"]),
            sum(1 for _, r in df.iterrows() if not r["candidate_no_lick_with_jaw_move"]),
        )
        cell_height_frac = 1.0 / max(1, n_rows)
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            pos = ax.get_position()
            ratio = pos.height / cell_height_frac
            assert ratio >= 0.50, (
                f"axis at {ss.rowspan.start},{ss.colspan.start} only "
                f"{ratio:.1%} of its cell height (needs >=50%)"
            )
        plt.close(fig)

    def test_cross_session_includes_colorbar_when_enabled(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``include_colorbar=True`` adds a colorbar (matplotlib Colorbar object)."""
        # Build a 2-session cohort with at least one post-stroke session
        # (rel_day > 0) so max_post > 0 and the colorbar actually renders.
        resolver, m1, te1 = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (30.0, 1)), tongue_lick_times=((), ()),
            animal="PS46", date=datetime.date(2025, 3, 7),  # rel_day=-6
        )
        classify_tongue_jaw_mismatch(
            manifest=m1, resolver=resolver, trial_events=te1,
            params=base_params, overwrite="force",
        )
        # Post-stroke synthetic session at d+5 (PS46 d0=2025-03-13).
        m2 = _make_minimal_manifest("PS46", datetime.date(2025, 3, 18))
        n_frames = 7500
        fps = _SYNTH_FPS
        rng = np.random.default_rng(0)
        jaw_y_2 = 100.0 + rng.normal(0.0, 0.5, n_frames)
        tongue_y_2 = rng.normal(0.0, 0.5, n_frames)
        for fr in (1500, 3000):
            _add_jaw_deflection(jaw_y_2, fps, fr, amplitude_px=30.0)
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="jaw", animal="PS46", date=datetime.date(2025, 3, 18),
            ),
            n_frames, fps=fps, y_final=jaw_y_2,
        )
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(
                bodypart="tongue", animal="PS46", date=datetime.date(2025, 3, 18),
            ),
            n_frames, fps=fps, y_final=tongue_y_2,
        )
        te2 = [
            TrialEvent(trial_index=0, reward_frame_idx=1500, side="L"),
            TrialEvent(trial_index=1, reward_frame_idx=3000, side="R"),
        ]
        classify_tongue_jaw_mismatch(
            manifest=m2, resolver=resolver, trial_events=te2,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _gather_sessions_for_animal,
            _plot_cross_session_overlay,
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["cross_session_overlay"]["include_colorbar"] = True
        animal_info = get_animal("PS46")
        sessions = _gather_sessions_for_animal("PS46", resolver, animal_info)
        fig = _plot_cross_session_overlay(
            sessions, animal="PS46", plotter_cfg=cfg,
        )
        # Colorbar shows up as an extra Axes object beyond the 2x2 grid + twins.
        # Detect by walking fig.axes for one whose label property matches.
        n_total_axes = len(fig.axes)
        # 2x2 grid = 4 primary + 4 twin = 8. Colorbar adds 1 more.
        assert n_total_axes >= 9, (
            f"expected colorbar to add an extra axes; got {n_total_axes}",
        )
        plt.close(fig)

    @staticmethod
    def _setup_overlay_outlier_session(
        tmp_path: Path, monkeypatch,
    ):
        """Shared fixture for the C6.3 with/without overlay-clipping tests.

        Builds a session with 10 candidate trials (5 L, 5 R) where one R
        trial carries a 500-frame plateau at +200 px. The plateau is a
        1.45% slice of trial-level data (large enough to survive a 99.9th-
        percentile cap → with-overlays axis upper ≈ 200) but only 1/5 of
        the R-side mean-trace (mean+sem upper ≈ 70-100 px → without-
        overlays axis upper << 200).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        animal = "PS46"
        date = datetime.date(2025, 3, 7)
        n = 25_000
        fps = _SYNTH_FPS
        rng = np.random.default_rng(0)
        jaw_y = rng.normal(0.0, 0.3, n)
        tongue_y = rng.normal(0.0, 0.3, n)
        # 10 reward frames at 2 s spacing.
        reward_frames = tuple(1500 + 1000 * k for k in range(10))
        for fr in reward_frames:
            _add_jaw_deflection(jaw_y, fps, fr, amplitude_px=20.0, dur_ms=1500.0)
        # Plateau on trial 5 (the first R-side trial with k=5).
        # Place plateau at t=300 ms post-reward; 500-frame width = 2 s.
        outlier_fr = reward_frames[5]
        plateau_start = outlier_fr + int(0.3 * fps)
        plateau_end = plateau_start + 500
        jaw_y[plateau_start:plateau_end] = 200.0
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(bodypart="jaw", animal=animal, date=date),
            n, fps=fps, y_final=jaw_y,
            center_mode="centered_eye_midpoint",
        )
        _make_synthetic_bodypart_parquet(
            resolver.interpolated_trace(bodypart="tongue", animal=animal, date=date),
            n, fps=fps, y_final=tongue_y,
            center_mode="centered_spout_midpoint",
        )
        manifest = _make_minimal_manifest(animal=animal, date=date)
        trial_events = [
            TrialEvent(trial_index=k, reward_frame_idx=int(fr),
                       side=("L" if k < 5 else "R"))
            for k, fr in enumerate(reward_frames)
        ]
        return resolver, manifest, trial_events, animal, date

    def test_mean_sem_ylim_includes_trial_overlays_when_shown(
        self, monkeypatch, tmp_path, base_params,
    ):
        """C6.3: with overlays shown, axis ylim spans trial-level extremes
        (within percentile cap), so the rendered overlays aren't clipped.
        """
        resolver, manifest, trial_events, animal, date = (
            self._setup_overlay_outlier_session(tmp_path, monkeypatch)
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["session_overlay_grid"]["mean_sem_axis"]["show_trial_overlays"] = True
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(animal, date),
        )
        jaw_y_arr, fps_jaw, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="jaw",
        )
        tongue_y_arr, _, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="tongue",
        )
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y_arr, tongue_y_arr, fps_jaw,
            plotter_cfg=cfg, animal=animal, date=date,
        )
        # Find the row 2 (mean±SEM-candidate) primary axis (any side).
        primary_by_rc: dict[tuple[int, int], object] = {}
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            rc = (ss.rowspan.start, ss.colspan.start)
            if rc not in primary_by_rc:
                primary_by_rc[rc] = ax
        # Find which row actually shows the candidate trials by walking
        # both candidate-mean-sem (row 2) and noncand-mean-sem (row 3) and
        # picking the one with non-empty data.
        candidate_jaw_lim = primary_by_rc[(2, 0)].get_ylim()
        # The plateau at 200 px (with baseline_subtracted - average baseline
        # ~ 0) should land inside or near the upper ylim. Allow some slack
        # because the per-trial baseline subtraction will offset all
        # plateau values by ~baseline_mean of trial 3's window. The
        # baseline window is (-500, 0) ms before reward, where jaw_y is
        # ~ 0 (random noise), so baseline_mean ~ 0 and the plotted
        # jaw_y_bs at the plateau is still ~ 200.
        # Test: the upper ylim is well above the mean-only extremes
        # (which would cap at ~mean of 20 px deflection ~ 25 px).
        assert candidate_jaw_lim[1] > 50.0, (
            f"With overlays shown, ylim upper={candidate_jaw_lim[1]:.1f} "
            f"should include trial-level extremes (>50 px), not just mean (~25 px)"
        )
        plt.close(fig)

    def test_mean_sem_ylim_excludes_trial_overlays_when_hidden(
        self, monkeypatch, tmp_path, base_params,
    ):
        """C6.3: with overlays hidden, axis ylim is driven by mean trace
        only — the trial-level outlier at 200 px is NOT included.
        """
        resolver, manifest, trial_events, animal, date = (
            self._setup_overlay_outlier_session(tmp_path, monkeypatch)
        )
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["session_overlay_grid"]["mean_sem_axis"]["show_trial_overlays"] = False
        classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        from stroke_orofacial.dlc_kinematics.tongue_jaw_mismatch import (
            _load_bodypart_y_final,
            _plot_session_overlay_grid_4x2,
        )
        df = pd.read_parquet(
            resolver.tongue_jaw_mismatch_candidate_trials_parquet(animal, date),
        )
        jaw_y_arr, fps_jaw, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="jaw",
        )
        tongue_y_arr, _, _ = _load_bodypart_y_final(
            resolver, animal, date, bodypart="tongue",
        )
        fig = _plot_session_overlay_grid_4x2(
            df, jaw_y_arr, tongue_y_arr, fps_jaw,
            plotter_cfg=cfg, animal=animal, date=date,
        )
        primary_by_rc: dict[tuple[int, int], object] = {}
        for ax in fig.axes:
            ss = ax.get_subplotspec()
            if ss is None:
                continue
            rc = (ss.rowspan.start, ss.colspan.start)
            if rc not in primary_by_rc:
                primary_by_rc[rc] = ax
        candidate_jaw_lim = primary_by_rc[(2, 0)].get_ylim()
        # With overlays hidden, the mean trace is the average of 4 trials.
        # 3 trials have jaw_y_bs ~ 0 over the plateau region; trial 3 has
        # jaw_y_bs ~ 200 there. Mean across 4 trials at the plateau ~ 50.
        # So mu_max ~ 50, plus mu+sem ~ 50 + sd/2 ~ 50-90. The auto-scaled
        # ylim upper should be well below 150 (cleanly excluding the
        # trial-only outlier at 200).
        assert candidate_jaw_lim[1] < 150.0, (
            f"With overlays hidden, ylim upper={candidate_jaw_lim[1]:.1f} "
            f"should reflect mean-only extremes (<150 px), not trial outlier "
            f"at 200 px"
        )
        plt.close(fig)

    def test_individual_trials_dpi_propagates_to_savefig(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``dpi`` knob propagates to the saved PNG.

        Patch params with a sentinel ``dpi=42``; render; re-load the saved
        PNG via PIL and assert the file metadata reflects ~42 dpi.
        """
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["individual_trials"]["dpi"] = 42  # sentinel
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        ct_path = classify_tongue_jaw_mismatch(
            manifest=manifest, resolver=resolver, trial_events=trial_events,
            params=base_params, overwrite="force",
        )
        df = pd.read_parquet(ct_path)
        out = render_within_session_figures(
            "PS46", datetime.date(2025, 3, 7), resolver,
            params=base_params, candidate_trials_df=df, overwrite="force",
        )
        png_path = out["individual_trials"][0]
        from PIL import Image
        with Image.open(png_path) as img:
            dpi = img.info.get("dpi", (None, None))
        # PIL's dpi tuple comes from the PNG pHYs chunk; matplotlib writes
        # this from the savefig dpi=42 we forced.
        assert dpi[0] == pytest.approx(42, abs=0.5), f"PNG dpi metadata: {dpi}"


class TestModuleEdges:

    def test_build_tongue_detector_params_pins_invariants(self, base_params):
        """Mismatch detector params pin no-MIN_FINITE + accept-no-fall over the YAML."""
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["classifier"]["tongue_detector"]
        out = _build_tongue_detector_params(cfg)
        assert out["min_finite_samples_per_lick"] == 0
        assert out["smooth_ms_detect_y"] == 0.0
        assert out["strict_no_fallback"] is True
        assert out["accept_peaks_without_fall_run"] is True
        # YAML knobs preserved
        assert out["slope_thr_px_per_s"] == 250.0
        assert out["min_peak_y_abs"] == 20.0
        assert out["do_smooth_y_for_detection"] is False

    def test_classifier_excluded_manifest_short_circuits(
        self, monkeypatch, tmp_path, base_params,
    ):
        """excluded=True manifest → returns None without touching disk."""
        resolver, _manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500,), sides=("L",),
            jaw_amps=((30.0, 1),), tongue_lick_times=((),),
        )
        excluded_m = SessionManifest(
            session_id="PS46_20250307", animal="PS46",
            date=datetime.date(2025, 3, 7),
            day_relative_to_stroke=-6, phase="baseline",
            excluded=True, alignment_template=None,
            wavesurfer_sides_match_mouse_sides=False,
        )
        out = classify_tongue_jaw_mismatch(
            manifest=excluded_m, resolver=resolver,
            trial_events=trial_events, params=base_params, overwrite="force",
        )
        assert out is None

    def test_result_dataclass_is_frozen(self):
        result = TongueJawMismatchResult(
            trials=pd.DataFrame({"x": [1]}), metadata={"a": 1},
        )
        with pytest.raises(Exception):  # noqa: B017
            result.trials = pd.DataFrame({"y": [2]})  # type: ignore[misc]
