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

    def test_session_overlay_mean_sem_uses_explicit_y_ranges(
        self, monkeypatch, tmp_path, base_params,
    ):
        """``mean_sem_axis`` explicit ranges drive ylim on bottom 2 rows.

        Patch params with sentinel ranges and assert the rendered ylims match.
        """
        cfg = base_params["dlc_kinematics"]["tongue_jaw_mismatch"]["plotter"]
        cfg["session_overlay_grid"]["mean_sem_axis"] = {
            "jaw_y_range": [-50, 50],
            "tongue_y_range": [-200, 200],
        }
        resolver, manifest, trial_events = _setup_session(
            tmp_path, monkeypatch,
            reward_frames=(1500, 3000), sides=("L", "R"),
            jaw_amps=((30.0, 1), (30.0, 1)), tongue_lick_times=((), ()),
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
        # Identify primary vs twin axes by Y-label text. The plot helper
        # sets jaw axes to "Jaw - base (px)" and twin tongue axes to
        # "Tongue Y (px)". This is more robust than subplotspec inspection
        # (twin axes inherit their parent's subplotspec in modern
        # matplotlib).
        jaw_axes: list[object] = []
        tongue_axes: list[object] = []
        for ax in fig.axes:
            ylabel = ax.get_ylabel()
            if ylabel == "Jaw - base (px)":
                jaw_axes.append(ax)
            elif ylabel == "Tongue Y (px)":
                tongue_axes.append(ax)
        # Synthetic setup: all 4 trials are candidates → row 0 (overlay-cand)
        # + row 2 (mean±SEM-cand) render in both cols (4 panels); rows 1, 3
        # (non-cand) show "no trials" placeholders (no y-labels). So we have
        # 4 labeled jaw + 4 labeled tongue axes total. Of those, the 2
        # mean±SEM-candidate panels (row 2, cols L+R) carry the explicit
        # ranges; the 2 overlay-candidate panels carry data-driven shared-Y.
        n_jaw_match = sum(
            1 for ax in jaw_axes if ax.get_ylim() == pytest.approx((-50, 50))
        )
        n_tong_match = sum(
            1 for ax in tongue_axes if ax.get_ylim() == pytest.approx((-200, 200))
        )
        assert n_jaw_match == 2, (
            f"expected 2 jaw axes at (-50, 50); got {n_jaw_match} of {len(jaw_axes)}",
        )
        assert n_tong_match == 2, (
            f"expected 2 tongue axes at (-200, 200); got {n_tong_match} of {len(tongue_axes)}",
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
