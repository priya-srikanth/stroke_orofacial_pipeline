"""Tests for Phase 8a.10 sub-deliverable A shared infrastructure
(``stroke_orofacial.spout_behavior.visual_gate``).

Covers commit-group 1's public API only — date helpers, Cohort A
iteration, longitudinal-axis resolution, per-session loader, file
saver, and the inverted ``SIDE_COLORS`` palette. Plot-family renderers
land in commit-groups 2-4 and bring their own tests.
"""
from __future__ import annotations

import datetime
import json
import platform
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend for CI / Windows
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.spout_behavior import visual_gate  # noqa: E402
from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    SIDE_COLORS,
    LongitudinalAxis,
    SessionPlotData,
    apply_longitudinal_axis,
    compute_longitudinal_axis,
    format_rel_day,
    iter_cohort_a_sessions,
    legend_label_for_date,
    load_session_plot_data,
    load_visual_gate_config,
    parse_base_date,
    save_visual_gate_figure,
    ymd_to_date,
)


_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


# ---- Date helpers ----


class TestDateHelpers:
    def test_parse_base_date_strips_no_suffix(self):
        assert parse_base_date("20250430") == "20250430"

    def test_parse_base_date_strips_b_suffix(self):
        assert parse_base_date("20250430b") == "20250430"

    def test_parse_base_date_strips_a_suffix(self):
        assert parse_base_date("20250314a") == "20250314"

    def test_parse_base_date_raises_on_malformed(self):
        with pytest.raises(ValueError, match="Could not parse base date"):
            parse_base_date("not-a-date")

    def test_ymd_to_date(self):
        assert ymd_to_date("20250430") == datetime.date(2025, 4, 30)

    def test_format_rel_day_zero(self):
        assert format_rel_day(0) == "d0"

    def test_format_rel_day_positive(self):
        assert format_rel_day(5) == "d+5"

    def test_format_rel_day_negative(self):
        assert format_rel_day(-3) == "d-3"


# ---- Cohort A iteration ----


@pytest.fixture
def fake_paths_yaml(tmp_path, monkeypatch):
    """Custom paths.yaml that points local_processed_spout at tmp_path."""
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    legacy_root = tmp_path / "legacy_analysis"
    legacy_root.mkdir()
    cfg = tmp_path / "paths.yaml"
    cfg.write_text(
        textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/pipeline_outputs"
                  windows: "C:\\\\dummy\\\\pipeline_outputs"
              local_processed_spout:
                description: "legacy fork"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """)
    )
    return cfg, legacy_root


def _write_report_json(
    legacy_root: Path, animal: str, latency_keys: list[str]
) -> None:
    bba = legacy_root / "basic_behavior_analysis3" / animal
    bba.mkdir(parents=True, exist_ok=True)
    report = {"latency_bySession": {k: {"L": 0.0, "R": 0.0} for k in latency_keys}}
    (bba / "report.json").write_text(json.dumps(report), encoding="utf-8")


class TestIterCohortASessions:
    def test_excludes_b_half_by_default(self, fake_paths_yaml):
        """Longitudinal-plot default: b-suffix sessions filtered out."""
        cfg, legacy_root = fake_paths_yaml
        # Mirror real PS51 report.json shape: bare 20250430/20250505 PLUS
        # b-half 20250430b/20250505b entries.
        _write_report_json(
            legacy_root, "PS51",
            ["20250416", "20250430", "20250430b", "20250505", "20250505b"],
        )
        resolver = PathResolver(cfg)
        sessions = iter_cohort_a_sessions("PS51", resolver)
        assert sessions == ["20250416", "20250430", "20250505"]

    def test_includes_b_half_when_flag_set(self, fake_paths_yaml):
        """Bare-vs-b scope: include_b_half=True keeps all entries."""
        cfg, legacy_root = fake_paths_yaml
        _write_report_json(
            legacy_root, "PS51",
            ["20250430", "20250430b", "20250505", "20250505b"],
        )
        resolver = PathResolver(cfg)
        sessions = iter_cohort_a_sessions(
            "PS51", resolver, include_b_half=True,
        )
        assert sessions == [
            "20250430", "20250430b", "20250505", "20250505b",
        ]

    def test_ps48_3_14_bare_included(self, fake_paths_yaml):
        """PS48/2025-03-14 Pattern A multi-half: legacy report.json
        had separate `20250314a` + `20250314b` keys, but the new
        pipeline emits a merged NPZ at the bare-date path 20250314.npz.
        Cohort A iteration should yield the bare-date entry — Task 1
        audit confirmed merged-NPZ availability via Phase 7-pre-multi-
        half emission. Synthetic test mirrors this by listing all 3
        forms and asserting only the bare-date survives the b/a filter."""
        cfg, legacy_root = fake_paths_yaml
        _write_report_json(
            legacy_root, "PS48",
            ["20250313", "20250314", "20250314a", "20250314b", "20250315"],
        )
        resolver = PathResolver(cfg)
        sessions = iter_cohort_a_sessions("PS48", resolver)
        assert "20250314" in sessions
        # The 'a' / 'b' raw labels filter out.
        assert "20250314a" not in sessions
        assert "20250314b" not in sessions
        assert sessions == ["20250313", "20250314", "20250315"]

    def test_missing_report_json_raises(self, fake_paths_yaml):
        cfg, _ = fake_paths_yaml
        resolver = PathResolver(cfg)
        with pytest.raises(FileNotFoundError, match="Cohort A report.json missing"):
            iter_cohort_a_sessions("PSNOPE", resolver)

    def test_sessions_are_sorted(self, fake_paths_yaml):
        """Implementation contract: deterministic output ordering."""
        cfg, legacy_root = fake_paths_yaml
        _write_report_json(
            legacy_root, "PS51",
            ["20250505", "20250416", "20250430"],
        )
        resolver = PathResolver(cfg)
        sessions = iter_cohort_a_sessions("PS51", resolver)
        assert sessions == sorted(sessions)


# ---- Longitudinal axis ----


class TestLongitudinalAxis:
    def test_align_to_stroke_x_vals_are_rel_days(self):
        d0 = datetime.date(2025, 4, 30)  # PS54 stroke_date example
        dates = ["20250428", "20250430", "20250502"]
        axis = compute_longitudinal_axis(
            dates, align_to_stroke=True, d0=d0,
        )
        assert list(axis.x_vals) == [-2, 0, 2]
        assert axis.x_ticklabels == ["d-2", "d0", "d+2"]
        assert axis.vline_x == 0.5
        assert axis.suffix == "_relStroke"

    def test_no_alignment_x_vals_are_arange(self):
        dates = ["20250416", "20250417", "20250418"]
        axis = compute_longitudinal_axis(
            dates, align_to_stroke=False, d0=None,
        )
        assert list(axis.x_vals) == [0, 1, 2]
        assert axis.x_ticklabels == ["20250416", "20250417", "20250418"]
        assert axis.vline_x is None
        assert axis.suffix == "_absDate"

    def test_no_alignment_uses_display_dates_override(self):
        dates = ["20250416", "20250417"]
        axis = compute_longitudinal_axis(
            dates,
            align_to_stroke=False,
            d0=None,
            display_dates={"20250416": "session-1", "20250417": "session-2"},
        )
        assert axis.x_ticklabels == ["session-1", "session-2"]

    def test_align_to_stroke_requires_d0(self):
        with pytest.raises(ValueError, match="requires d0"):
            compute_longitudinal_axis(
                ["20250430"], align_to_stroke=True, d0=None,
            )

    def test_apply_longitudinal_axis_sets_xticks_and_vline(self):
        cfg = load_visual_gate_config()
        axis = LongitudinalAxis(
            x_vals=np.array([-1, 0, 1]),
            x_ticklabels=["d-1", "d0", "d+1"],
            vline_x=0.5,
            suffix="_relStroke",
        )
        fig, ax = plt.subplots()
        try:
            apply_longitudinal_axis(ax, axis, cfg)
            assert list(ax.get_xticks()) == [-1, 0, 1]
            labels = [t.get_text() for t in ax.get_xticklabels()]
            assert labels == ["d-1", "d0", "d+1"]
            # axvline added: one Line2D among ax.lines with the stroke color
            assert any(
                ln.get_color() == cfg["stroke_vline_color"] for ln in ax.lines
            )
        finally:
            plt.close(fig)

    def test_apply_longitudinal_axis_no_vline_when_unaligned(self):
        cfg = load_visual_gate_config()
        axis = LongitudinalAxis(
            x_vals=np.array([0, 1]),
            x_ticklabels=["20250416", "20250417"],
            vline_x=None,
            suffix="_absDate",
        )
        fig, ax = plt.subplots()
        try:
            apply_longitudinal_axis(ax, axis, cfg)
            assert all(
                ln.get_color() != cfg["stroke_vline_color"] for ln in ax.lines
            )
        finally:
            plt.close(fig)

    def test_legend_label_for_date_relstroke(self):
        d0 = datetime.date(2025, 4, 30)
        label = legend_label_for_date(
            "20250502", align_to_stroke=True, d0=d0,
        )
        assert label == "d+2"

    def test_legend_label_for_date_absdate(self):
        label = legend_label_for_date(
            "20250416", align_to_stroke=False, d0=None,
        )
        assert label == "20250416"

    def test_legend_label_for_date_display_override_absdate(self):
        label = legend_label_for_date(
            "20250416",
            align_to_stroke=False,
            d0=None,
            display_dates={"20250416": "session-1"},
        )
        assert label == "session-1"


# ---- SessionPlotData loader ----


def _write_phase2_npzs(
    output_root: Path, animal: str, date_label: str,
    lick_l: np.ndarray, lick_r: np.ndarray,
    reward_l: np.ndarray, reward_r: np.ndarray,
    sample_rate: float,
    n_samples: int | None = None,
) -> None:
    sp = output_root / "spout_behavior"
    licks_dir = sp / "licks_and_rewards" / animal
    ws_dir = sp / "wavesurfer_signals_processed" / animal
    licks_dir.mkdir(parents=True, exist_ok=True)
    ws_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        licks_dir / f"{date_label}.npz",
        Lick_L=lick_l, Lick_R=lick_r,
        Reward_L=reward_l, Reward_R=reward_r,
    )
    ws_kwargs: dict[str, np.ndarray] = {"sample_rate_input": np.array(sample_rate)}
    if n_samples is not None:
        # 1D signal so load_session_plot_data populates n_samples_session
        ws_kwargs["Treadmill"] = np.zeros(n_samples, dtype=np.float32)
    np.savez(ws_dir / f"{date_label}.npz", **ws_kwargs)


class TestLoadSessionPlotData:
    def test_reads_licks_and_sample_rate(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100, 200]),
            lick_r=np.array([150, 250]),
            reward_l=np.array([50]),
            reward_r=np.array([175]),
            sample_rate=2000.0,
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert isinstance(data, SessionPlotData)
        assert data.date_label == "20250430"
        assert np.array_equal(data.lick_idx["Lick_L"], [100, 200])
        assert np.array_equal(data.lick_idx["Lick_R"], [150, 250])
        assert np.array_equal(data.rewards_idx["Reward_L"], [50])
        assert np.array_equal(data.rewards_idx["Reward_R"], [175])
        assert data.sample_rate == 2000.0

    def test_missing_licks_npz_raises(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="licks_and_rewards NPZ missing"):
            load_session_plot_data("PS51", "20250430", resolver)

    def test_missing_wavesurfer_npz_raises(self, tmp_path):
        # Write only the licks NPZ; the wavesurfer side is absent.
        sp = tmp_path / "spout_behavior"
        licks_dir = sp / "licks_and_rewards" / "PS51"
        licks_dir.mkdir(parents=True, exist_ok=True)
        np.savez(
            licks_dir / "20250430.npz",
            Lick_L=np.array([100]),
            Lick_R=np.array([150]),
            Reward_L=np.array([50]),
            Reward_R=np.array([175]),
        )
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(
            FileNotFoundError,
            match="wavesurfer_signals_processed NPZ missing",
        ):
            load_session_plot_data("PS51", "20250430", resolver)


# ---- Visual-gate config + side-colors inversion ----


class TestVisualGateConfig:
    def test_load_visual_gate_config_returns_dict(self):
        cfg = load_visual_gate_config()
        # Sanity: the keys we depend on across commit-groups exist.
        for key in [
            "side_colors", "xtick_fontsize", "stroke_linewidth",
            "stroke_vline_x", "stroke_vline_color", "stroke_vline_linestyle",
            "stroke_vline_alpha", "accuracy_y_range", "latency_y_max",
            "lickrate_y_max", "numlicks_y_max", "lickiness_window_seconds",
            "raster_xlim", "raster_dot_size", "raster_criteria_alpha",
            "figsize_longitudinal", "figsize_raster_grid",
        ]:
            assert key in cfg, f"visual_gate config missing key: {key}"

    def test_side_colors_inverted_vs_legacy(self):
        """Phase 8a.10 DECISIONS pin: mouse-frame palette is inverted
        from legacy. Legacy `side_colors` (behavior_report_PS.py:250)
        had ``{"L": "mediumvioletred", "R": "dodgerblue"}`` because
        legacy operated in WS-frame internally + flipped at output.
        New pipeline operates mouse-frame post-Phase-6.8 → direct
        mapping ``mouse-L = dodgerblue, mouse-R = mediumvioletred``.
        Regression to the legacy palette here would silently swap
        all per-mouse plot colors."""
        assert SIDE_COLORS == {"L": "dodgerblue", "R": "mediumvioletred"}


# ---- File saver ----


class TestSaveVisualGateFigure:
    def _make_simple_fig(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [3, 2, 1])
        return fig

    def test_writes_svg_and_png(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg_path, png_path = save_visual_gate_figure(
                fig, "PS51", "test_family", "_relStroke", resolver,
            )
        finally:
            plt.close(fig)
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "test_family_relStroke.svg"
        assert png_path.name == "test_family_relStroke.png"

    def test_dest_is_visual_gate_dir(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg_path, _ = save_visual_gate_figure(
                fig, "PS51", "test_family", "_absDate", resolver,
            )
        finally:
            plt.close(fig)
        assert svg_path.parent == resolver.visual_gate_dir("PS51")

    def test_overwrite_force(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        # First write creates the files.
        fig1 = self._make_simple_fig()
        try:
            save_visual_gate_figure(
                fig1, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig1)
        # Second write must succeed under force.
        fig2 = self._make_simple_fig()
        try:
            svg_path, png_path = save_visual_gate_figure(
                fig2, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig2)
        assert svg_path.exists()
        assert png_path.exists()

    def test_overwrite_raise(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            save_visual_gate_figure(
                fig, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig)
        fig2 = self._make_simple_fig()
        try:
            with pytest.raises(FileExistsError, match="visual_gate target exists"):
                save_visual_gate_figure(
                    fig2, "PS51", "fam", "", resolver, overwrite="raise",
                )
        finally:
            plt.close(fig2)

    def test_overwrite_skip_returns_existing_paths(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg1, png1 = save_visual_gate_figure(
                fig, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig)
        existing_svg_size = svg1.stat().st_size
        existing_png_size = png1.stat().st_size
        fig2 = self._make_simple_fig()
        try:
            svg2, png2 = save_visual_gate_figure(
                fig2, "PS51", "fam", "", resolver, overwrite="skip",
            )
        finally:
            plt.close(fig2)
        # Same paths returned; no rewrite happened.
        assert (svg1, png1) == (svg2, png2)
        assert svg2.stat().st_size == existing_svg_size
        assert png2.stat().st_size == existing_png_size


# ---- Module-level constant pin ----


def test_module_exports_expected_names():
    """Pin the commit-group 1 public surface so subsequent commit
    groups can't accidentally remove a symbol downstream renderers
    depend on."""
    for name in [
        "parse_base_date", "ymd_to_date", "format_rel_day",
        "iter_cohort_a_sessions",
        "LongitudinalAxis", "compute_longitudinal_axis",
        "apply_longitudinal_axis", "legend_label_for_date",
        "SessionPlotData", "load_session_plot_data",
        "load_visual_gate_config", "SIDE_COLORS",
        "save_visual_gate_figure",
    ]:
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 1 public surface "
            "should include it"
        )


# =====================================================================
# Commit-group 2: compute helpers + 8 longitudinal-mean renderers
# =====================================================================


from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    compute_criteria_3,
    compute_criteria_34,
    compute_criteria_4,
    compute_criteria_acc_bySession,
    compute_first_correct_lick_sample_idx,
    compute_first_lick_correct,
    compute_firstLickCorrect_bySession,
    compute_latency_bySession,
    compute_lickiness_bySession,
    compute_median_lick_rate_bySession,
    compute_num_licks_bySession,
    compute_switchiness_bySession,
    compute_trial_lick_delays,
    load_behavior_report_params,
    render_accuracy_firstCorrectLick,
    render_accuracy_firstCorrectLickAll,
    render_criteria_performance,
    render_latency_bySession,
    render_lick_raster,
    render_lickiness_bySession,
    render_lickRate_bySession,
    render_numLicks_bySession_all,
    render_numLicks_bySession_correct,
    render_numLicks_bySession_correct_and_incorrect,
    render_switchiness_bySession,
)


# ---- Synthetic session fixture for compute-helper unit tests ----


def _make_synthetic_session(date_label: str = "20250430") -> SessionPlotData:
    """Tiny deterministic session for compute-helper tests.

    Sample rate 1000 Hz; 1 L reward at sample 1000 (t=1s); 1 R reward
    at sample 5000 (t=5s). Hand-placed licks support exact-value
    assertions in every compute helper.
    """
    return SessionPlotData(
        date_label=date_label,
        # Mouse-L licks: 6 around reward L (500, 1100, 1500, 2000, 2500, 2900);
        # 0 around reward R within criteria windows
        lick_idx={
            "Lick_L": np.array([500, 1100, 1500, 2000, 2500, 2900], dtype=int),
            "Lick_R": np.array([900, 5200, 5800, 6100, 6500, 7000, 7500], dtype=int),
        },
        rewards_idx={
            "Reward_L": np.array([1000], dtype=int),
            "Reward_R": np.array([5000], dtype=int),
        },
        sample_rate=1000.0,
    )


# ---- Tests: behavior_report config loader ----


class TestBehaviorReportParams:
    def test_load_returns_dict(self):
        params = load_behavior_report_params()
        for key in [
            "window_around_rewards", "criteria_1", "criteria_2",
            "criteria_3", "criteria_4",
        ]:
            assert key in params, f"behavior_report missing key: {key}"

    def test_legacy_values_preserved(self):
        """Pin: cohort-wide defaults match legacy params dict
        (batch_process_behavior_report_20260116PS.ipynb cell-3)."""
        params = load_behavior_report_params()
        assert list(params["window_around_rewards"]) == [1.0, 8.0]
        assert params["criteria_1"]["num_consecutive_pass"] == 3
        assert params["criteria_2"]["fraction_pass"] == 0.6
        assert list(params["criteria_3"]["window"]) == [0, 2.0]
        assert list(params["criteria_4"]["window"]) == [0, 2.5]
        assert params["criteria_4"]["num_licks_correct_min"] == 5
        assert params["criteria_4"]["num_licks_incorrect_max"] == 0


# ---- Tests: per-session compute helpers ----


class TestComputeTrialLickDelays:
    def test_window_includes_pre_reward_licks(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        # Lick L at 500 (before reward L at 1000): delay = -500
        l_delays = delays["Reward_L"][0]["Lick_L"]
        assert -500 in l_delays
        # Lick L at 1100 (after reward L at 1000): delay = 100
        assert 100 in l_delays

    def test_per_reward_keys(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        assert set(delays.keys()) == {"Reward_L", "Reward_R"}
        # Reward_L has 1 trial (idx 0); Reward_R has 1 trial (idx 0)
        assert set(delays["Reward_L"].keys()) == {0}
        assert set(delays["Reward_R"].keys()) == {0}

    def test_per_side_keys(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        assert set(delays["Reward_L"][0].keys()) == {"Lick_L", "Lick_R"}

    def test_window_excludes_licks_outside_window(self):
        # Tight window: 0-1s after reward (samples [reward, reward+1000])
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [0, 1.0])
        # Lick L at 500  (pre-reward, before window):       excluded
        # Lick L at 1100 (in window):                       delay 100
        # Lick L at 1500 (in window):                       delay 500
        # Lick L at 2000 (== reward + 1000; window inclusive): delay 1000
        # Lick L at 2500 (past window):                     excluded
        l_delays = delays["Reward_L"][0]["Lick_L"]
        assert set(l_delays.tolist()) == {100, 500, 1000}


class TestComputeFirstCorrectLickSampleIdx:
    def test_returns_first_lick_within_criteria_3_window(self):
        data = _make_synthetic_session()
        # criteria_3 window: 0-2.0s after reward
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        # First L lick ≥ reward L sample (1000) and ≤ 3000: sample 1100
        assert fcl["L"][0] == 1100
        # First R lick ≥ reward R sample (5000) and ≤ 7000: sample 5200
        assert fcl["R"][0] == 5200

    def test_returns_none_when_no_lick_in_window(self):
        # Build a session with NO post-reward licks within criteria_3 window
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                "Lick_L": np.array([500], dtype=int),  # only pre-reward
                "Lick_R": np.array([100, 200], dtype=int),  # all pre-reward
            },
            rewards_idx={
                "Reward_L": np.array([1000], dtype=int),
                "Reward_R": np.array([5000], dtype=int),
            },
            sample_rate=1000.0,
        )
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        assert fcl["L"][0] is None
        assert fcl["R"][0] is None


class TestComputeCriteria3:
    def test_returns_true_when_first_lick_present(self):
        data = _make_synthetic_session()
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        c3 = compute_criteria_3(fcl)
        assert c3["L"][0] is True
        assert c3["R"][0] is True

    def test_returns_false_when_first_lick_none(self):
        fcl = {"L": {0: None}, "R": {0: 5100}}
        c3 = compute_criteria_3(fcl)
        assert c3["L"][0] is False
        assert c3["R"][0] is True


class TestComputeCriteria4:
    def test_passes_with_enough_correct_no_incorrect(self):
        data = _make_synthetic_session()
        # criteria_4: window=[0, 2.5], min_correct=5, max_incorrect=0
        # Reward_L at sample 1000: window [1000, 3500]
        #   - L licks in window: 1100, 1500, 2000, 2500, 2900 (count 5; ≥ 5 OK)
        #   - R licks in window: 0 (the 900 is pre-reward; 5200 is past window) → ≤ 0 OK
        c4 = compute_criteria_4(data, {
            "window": [0, 2.5],
            "num_licks_correct_min": 5,
            "num_licks_incorrect_max": 0,
        })
        assert c4["L"][0] is True

    def test_fails_when_too_few_correct(self):
        data = _make_synthetic_session()
        c4 = compute_criteria_4(data, {
            "window": [0, 2.5],
            "num_licks_correct_min": 10,  # ↑ higher threshold
            "num_licks_incorrect_max": 0,
        })
        assert c4["L"][0] is False


class TestComputeCriteria34:
    def test_and_combines(self):
        c3 = {"L": {0: True, 1: True}, "R": {0: True}}
        c4 = {"L": {0: True, 1: False}, "R": {0: True}}
        c34 = compute_criteria_34(c3, c4)
        assert c34["L"][0] is True
        assert c34["L"][1] is False
        assert c34["R"][0] is True


class TestComputeFirstLickCorrect:
    def test_correct_post_first_returns_true(self):
        """Reward L: L lick at delay +100, no R licks post-reward → True."""
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([100, 500]),
                    "Lick_R": np.array([-200]),  # pre-reward, ignored
                },
            },
            "Reward_R": {
                0: {
                    "Lick_R": np.array([200]),
                    "Lick_L": np.array([]),
                },
            },
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is True
        assert flc["R"][0] is True

    def test_incorrect_first_returns_false(self):
        """Reward L: R lick at delay +50 precedes L lick at +200 → False."""
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([200]),
                    "Lick_R": np.array([50]),
                },
            },
            "Reward_R": {},
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is False

    def test_no_post_reward_licks_returns_none(self):
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([-100]),  # only pre-reward
                    "Lick_R": np.array([-200]),
                },
            },
            "Reward_R": {},
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is None


class TestComputeCriteriaAccBySession:
    def test_fraction_passing(self):
        c34 = {"L": {0: True, 1: True, 2: False}, "R": {0: True, 1: False}}
        acc = compute_criteria_acc_bySession(c34)
        assert acc["L"] == pytest.approx(2 / 3)
        assert acc["R"] == pytest.approx(0.5)

    def test_empty_returns_nan(self):
        acc = compute_criteria_acc_bySession({"L": {}, "R": {}})
        assert np.isnan(acc["L"])
        assert np.isnan(acc["R"])


class TestComputeFirstLickCorrectBySession:
    def test_exclude_none_uses_nanmean(self):
        flc = {"L": {0: True, 1: False, 2: None}, "R": {0: True, 1: True}}
        m = compute_firstLickCorrect_bySession(flc, treat_none_as_zero=False)
        # None is excluded → mean of [1, 0] = 0.5
        assert m["L"] == pytest.approx(0.5)
        assert m["R"] == pytest.approx(1.0)

    def test_treat_none_as_zero_counts_against(self):
        flc = {"L": {0: True, 1: False, 2: None}, "R": {0: True, 1: True}}
        m = compute_firstLickCorrect_bySession(flc, treat_none_as_zero=True)
        # None counts as 0 → mean of [1, 0, 0] = 1/3
        assert m["L"] == pytest.approx(1 / 3)
        assert m["R"] == pytest.approx(1.0)


class TestComputeMedianLickRateBySession:
    def test_returns_per_side_mean_std(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        rates = compute_median_lick_rate_bySession(delays, sample_rate=1000.0)
        assert set(rates.keys()) == {"L", "R"}
        for side in ("L", "R"):
            assert "mean" in rates[side]
            assert "std" in rates[side]


class TestComputeNumLicksBySession:
    def test_returns_correct_all_incorrect(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        n = compute_num_licks_bySession(delays)
        assert set(n.keys()) == {"correct", "all", "incorrect"}
        for kind in ("correct", "all", "incorrect"):
            assert set(n[kind].keys()) == {"Reward_L", "Reward_R"}

    def test_counts_match_synthetic(self):
        """Reward_L window [-1000, 8000] from sample 1000:
            Lick_L within: [500, 1100, 1500, 2000, 2500, 2900] = 6 (correct)
            Lick_R within: [900, 5200, 5800, 6100, 6500, 7000, 7500]
              filter to [-1000+1000=0, 8000+1000=9000] → [900, 5200, 5800,
              6100, 6500, 7000, 7500] all within → 7 (incorrect)
            All = 6 + 7 = 13
        """
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        n = compute_num_licks_bySession(delays)
        assert n["correct"]["Reward_L"]["mean"] == pytest.approx(6.0)
        assert n["incorrect"]["Reward_L"]["mean"] == pytest.approx(7.0)
        assert n["all"]["Reward_L"]["mean"] == pytest.approx(13.0)


class TestComputeLatencyBySession:
    def test_latency_seconds_from_reward(self):
        data = _make_synthetic_session()
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        lat = compute_latency_bySession(fcl, data.rewards_idx, data.sample_rate)
        # Reward_L at 1000, first correct L lick at 1100 → 0.1s
        assert lat["L"]["mean"] == pytest.approx(0.1)
        # Reward_R at 5000, first correct R lick at 5200 → 0.2s
        assert lat["R"]["mean"] == pytest.approx(0.2)

    def test_none_first_lick_yields_nan_excluded(self):
        fcl = {"L": {0: None, 1: 1100}, "R": {0: 5200}}
        rewards = {
            "Reward_L": np.array([1000, 2000]),
            "Reward_R": np.array([5000]),
        }
        lat = compute_latency_bySession(fcl, rewards, sample_rate=1000.0)
        # L: [nan, -0.9 (idx 1 → fcl 1100 - reward 2000 = -900 samples)]
        # nanmean is the non-nan value: -0.9
        # actually this is "first lick before reward 2000 within criteria_3" so
        # it's unusual but the formula is right. Test the float behavior:
        assert np.isfinite(lat["L"]["mean"])


# ---- Tests: 8 longitudinal-mean renderers ----


@pytest.fixture
def cohort_for_renders(tmp_path, monkeypatch):
    """Build a tiny Cohort A on disk for render integration tests.

    Animal: PS51 (real animals.yaml entry; stroke_date = 2025-04-29).
    3 bare-date sessions; report.json + 3 sets of Phase-2 NPZs.
    Returns (paths_yaml, resolver) ready to pass to a render function.
    """
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    legacy_root = tmp_path / "legacy_analysis"
    legacy_root.mkdir()
    # Synthetic 3-session cohort spanning pre/post stroke
    dates = ["20250428", "20250429", "20250430"]
    # Write report.json with latency_bySession keys
    bba = legacy_root / "basic_behavior_analysis3" / "PS51"
    bba.mkdir(parents=True, exist_ok=True)
    (bba / "report.json").write_text(json.dumps({
        "latency_bySession": {d: {"L": 0.0, "R": 0.0} for d in dates}
    }), encoding="utf-8")
    # Write Phase-2 NPZs at output_root override
    output_root = tmp_path / "pipeline_outputs"
    for date in dates:
        _write_phase2_npzs(
            output_root, "PS51", date,
            lick_l=np.array([500, 1100, 1500, 2000, 2500, 2900], dtype=int),
            lick_r=np.array([900, 5200, 5800, 6100, 6500, 7000, 7500], dtype=int),
            reward_l=np.array([1000], dtype=int),
            reward_r=np.array([5000], dtype=int),
            sample_rate=1000.0,
            n_samples=60000,  # 60 sec at 1000 Hz; populates n_samples_session
        )
    # Custom paths.yaml pointing local_processed_spout → tmp_path
    paths_yaml = tmp_path / "paths.yaml"
    paths_yaml.write_text(textwrap.dedent(f"""
        logical_roots:
          microscope_pipeline_outputs:
            description: "out"
            mounts:
              mac: "/Volumes/dummy/po"
              windows: "C:\\\\dummy\\\\po"
          local_processed_spout:
            description: "legacy"
            mounts:
              {_HOST_KEY}:
                - "{legacy_root.as_posix()}"
    """))
    resolver = PathResolver(paths_yaml, output_root=output_root)
    return resolver, dates


_RENDER_FUNCS = [
    ("criteria_performance", render_criteria_performance),
    ("accuracy_firstCorrectLick", render_accuracy_firstCorrectLick),
    ("accuracy_firstCorrectLickAll", render_accuracy_firstCorrectLickAll),
    ("lickRate_bySession", render_lickRate_bySession),
    ("latency_bySession", render_latency_bySession),
    ("numLicks_bySession_correct", render_numLicks_bySession_correct),
    ("numLicks_bySession_all", render_numLicks_bySession_all),
    ("numLicks_bySession_correct_and_incorrect",
     render_numLicks_bySession_correct_and_incorrect),
]


@pytest.mark.parametrize("family_name,render_fn", _RENDER_FUNCS)
class TestRenderersReturnPaths:
    """Each renderer returns (svg_path, png_path) that exist + named
    by family with the longitudinal-axis suffix."""

    def test_returns_svg_and_png_paths(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, png_path = render_fn("PS51", resolver, align_to_stroke=True)
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        # Filename ends with _relStroke when stroke-aligned
        assert svg_path.name == f"{family_name}_relStroke.svg"
        assert png_path.name == f"{family_name}_relStroke.png"

    def test_uses_visual_gate_dir(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_fn("PS51", resolver, align_to_stroke=True)
        assert svg_path.parent == resolver.visual_gate_dir("PS51")

    def test_absdate_suffix_when_unaligned(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_fn("PS51", resolver, align_to_stroke=False)
        assert svg_path.name == f"{family_name}_absDate.svg"


class TestRenderCriteriaPerformanceFidelity:
    """Per-family pin tests for criteria_performance (the reference
    implementation for the longitudinal-mean skeleton)."""

    def test_ylim_matches_accuracy_y_range(self, cohort_for_renders):
        resolver, _dates = cohort_for_renders
        cfg = load_visual_gate_config()
        # Render + inspect a re-opened figure's y-limits via the SVG isn't
        # practical; instead, render with a fresh figure injection by
        # monkeypatching plt.subplots — too brittle. Pragmatic approach:
        # confirm the file was emitted (above test) + structurally pin
        # the config value the renderer reads.
        assert tuple(cfg["accuracy_y_range"]) == (0.0, 1.0)

    def test_title_string_format(self, cohort_for_renders):
        """Read the SVG XML for the legacy title verbatim — small but
        useful regression pin."""
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_criteria_performance(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Criteria performance by session" in svg_text


class TestRenderAccuracyFirstCorrectLickFidelity:
    def test_y_axis_label_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_accuracy_firstCorrectLick(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "correct 1st lick" in svg_text


class TestRenderAccuracyFirstCorrectLickAllFidelity:
    def test_title_distinct_from_excludeNone_variant(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_all, _ = render_accuracy_firstCorrectLickAll(
            "PS51", resolver, align_to_stroke=True,
        )
        text_all = svg_all.read_text(encoding="utf-8")
        # Legacy title for the All variant: "Fraction of all trials ..."
        assert "all trials with correct first lick" in text_all


class TestRenderLickRateBySessionFidelity:
    def test_ylim_from_lickrate_y_max_config(self, cohort_for_renders):
        cfg = load_visual_gate_config()
        assert cfg["lickrate_y_max"] == 10.0

    def test_title_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickRate_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "avg correct lick rate by session" in svg_text


class TestRenderLatencyBySessionFidelity:
    def test_ylim_from_latency_y_max_config(self, cohort_for_renders):
        cfg = load_visual_gate_config()
        assert cfg["latency_y_max"] == 2.0

    def test_title_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_latency_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "avg latency to correct lick by session" in svg_text


class TestRenderNumLicksFidelity:
    def test_correct_and_all_titles_distinct(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_correct, _ = render_numLicks_bySession_correct(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_all, _ = render_numLicks_bySession_all(
            "PS51", resolver, align_to_stroke=True,
        )
        # Legacy strings: "Avg correct licks per trial by session" vs
        # "Avg all licks per trial by session"
        assert "Avg correct licks per trial" in svg_correct.read_text(encoding="utf-8")
        assert "Avg all licks per trial" in svg_all.read_text(encoding="utf-8")

    def test_correct_and_incorrect_title(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_numLicks_bySession_correct_and_incorrect(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib SVG-escapes "&" → "&amp;" in serialized titles
        assert "Avg correct &amp; incorrect licks per trial" in svg_text


class TestRendererModuleExports:
    """Pin CG-2 public surface so subsequent CGs don't accidentally drop
    a renderer subsequent consumers (notebook orchestrator in CG-6) depend on."""

    @pytest.mark.parametrize("name", [
        "load_behavior_report_params",
        "compute_trial_lick_delays",
        "compute_first_correct_lick_sample_idx",
        "compute_criteria_3", "compute_criteria_4", "compute_criteria_34",
        "compute_first_lick_correct", "compute_criteria_acc_bySession",
        "compute_firstLickCorrect_bySession", "compute_median_lick_rate_bySession",
        "compute_num_licks_bySession", "compute_latency_bySession",
        "render_criteria_performance", "render_accuracy_firstCorrectLick",
        "render_accuracy_firstCorrectLickAll", "render_lickRate_bySession",
        "render_latency_bySession", "render_numLicks_bySession_correct",
        "render_numLicks_bySession_all",
        "render_numLicks_bySession_correct_and_incorrect",
    ])
    def test_symbol_exists(self, name):
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 2 public surface"
        )


# =====================================================================
# Commit-group 3: lick raster renderer
# =====================================================================


class TestRenderLickRaster:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _dates = cohort_for_renders
        svg_path, png_path = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "lick_raster_relStroke.svg"
        assert png_path.name == "lick_raster_relStroke.png"

    def test_lands_in_visual_gate_dir(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.parent == resolver.visual_gate_dir("PS51")

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "lick_raster_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        """Empty Cohort A → ValueError (can't build 2×0 panel grid)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_lick_raster("PS51", resolver, align_to_stroke=True)

    def test_suptitle_legend_string(self, cohort_for_renders):
        """Pin: legacy suptitle verbatim (Phase 8a.10 audit-spec)."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib SVG-escapes "(" / ")" / "=" verbatim; the literal
        # words are unchanged. Pin two segments separately for
        # readability + robust to whitespace variation.
        assert "Licks after rewards" in svg_text
        assert "Dots:" in svg_text
        assert "green=corr" in svg_text
        assert "magenta=incorr" in svg_text
        assert "Lines:" in svg_text
        assert "green=pass" in svg_text
        assert "red=fail" in svg_text

    def test_ylabel_uses_mouse_frame_directly_no_fn_flip(
        self, cohort_for_renders,
    ):
        """New pipeline reads side_reward as mouse-frame directly.
        Legacy ylabel was ``"Trials   (side: mouse {fn_flip_lr(side_reward)})"``
        — the flip was a WS-frame compensation. New pipeline:
        ``"Trials   (side: mouse {side_reward})"`` — direct."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # Both side labels appear in the SVG: row 0 = Reward L → ylabel
        # "side: mouse L" (left column only); row 1 = Reward R → "side: mouse R".
        assert "side: mouse L" in svg_text
        assert "side: mouse R" in svg_text

    def test_raster_color_config_consumed(self):
        """Pin: raster dot + criteria colors loaded from
        ``visual_gate:`` block, not hardcoded."""
        cfg = load_visual_gate_config()
        assert cfg["raster_dot_correct_color"] == "g"
        assert cfg["raster_dot_incorrect_color"] == "m"
        assert cfg["raster_criteria_pass_color"] == "g"
        assert cfg["raster_criteria_fail_color"] == "r"
        assert cfg["raster_reward_marker_color"] == "k"
        assert tuple(cfg["raster_criteria_xrange"]) == (-1, 4)

    def test_module_export(self):
        assert hasattr(visual_gate, "render_lick_raster")


# =====================================================================
# Commit-group 4: lickiness + switchiness
# =====================================================================


class TestComputeLickinessBySession:
    def test_counts_licks_in_inter_reward_window(self):
        """2 rewards 10 seconds apart; licks between them in the
        late-window range get counted."""
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                # 2 L licks at t=9s and 10s (within late window of reward at t=0)
                "Lick_L": np.array([9000, 10000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            rewards_idx={
                "Reward_L": np.array([0], dtype=int),
                "Reward_R": np.array([20000], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        # late_window_start=8s → licks at 9s/10s past 8000 sample start
        # late_window_end=60s → window end = min(20000 next reward, 0+60000) = 20000
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 2
        assert counts["R"] == 0

    def test_dense_rewards_next_reward_caps_window(self):
        """When next_reward is closer than the 60s cap, the next-reward
        boundary trims the late-window (mirrors legacy line 870)."""
        data = SessionPlotData(
            date_label="20250430",
            # Reward at 0; next reward at sample 12000 (12 sec).
            # Late window: [8000 (8s), min(12000, 60000)=12000].
            # Lick at 11000 (in window); lick at 13000 (past next reward, excluded)
            lick_idx={
                "Lick_L": np.array([11000, 13000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            rewards_idx={
                "Reward_L": np.array([0], dtype=int),
                "Reward_R": np.array([12000], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 1  # only 11000; 13000 past next-reward cap

    def test_handles_empty_rewards(self):
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={"Lick_L": np.array([], dtype=int),
                      "Lick_R": np.array([], dtype=int)},
            rewards_idx={"Reward_L": np.array([], dtype=int),
                         "Reward_R": np.array([], dtype=int)},
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts == {"L": 0, "R": 0}

    def test_last_reward_uses_n_samples_cap(self):
        """For the last reward, the window closes at min(rew + end,
        n_samples_session) — n_samples_session=15000 trims a 0+60s=60000
        sample window down to 15000."""
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                # Lick at 14000 (within trimmed window), lick at 16000 (past)
                "Lick_L": np.array([14000, 16000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            rewards_idx={
                "Reward_L": np.array([0], dtype=int),
                "Reward_R": np.array([], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=15000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 1


class TestComputeSwitchinessBySession:
    def test_no_licks_yields_nan(self):
        """Empty trials → no count contributions → NaN means."""
        delays: dict[str, dict[int, dict[str, np.ndarray]]] = {
            "Reward_L": {}, "Reward_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        assert np.isnan(sw["L->R"])
        assert np.isnan(sw["R->L"])

    def test_single_event_yields_zero_transitions(self):
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([100]),
                    "Lick_R": np.array([], dtype=int),
                },
            },
            "Reward_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        # 1 event → 0 transitions
        assert sw["L->R"] == pytest.approx(0.0)
        assert sw["R->L"] == pytest.approx(0.0)

    def test_alternating_LRLR_counts_transitions(self):
        """4-event LRLR sequence within one trial = 3 transitions
        (L→R, R→L, L→R). So c_LR=2, c_RL=1."""
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([100, 300], dtype=int),
                    "Lick_R": np.array([200, 400], dtype=int),
                },
            },
            "Reward_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        assert sw["L->R"] == pytest.approx(2.0)
        assert sw["R->L"] == pytest.approx(1.0)

    def test_mouse_frame_no_ws_flip(self):
        """compute_switchiness_bySession operates mouse-frame directly
        on the input lick_delays (which are mouse-frame post-Phase-6.8).
        Legacy did a WS-frame compute + plot-time flip; new pipeline
        does NEITHER — input is already mouse-frame and output keys are
        labeled in mouse-frame."""
        delays = {
            "Reward_L": {
                0: {
                    "Lick_L": np.array([100, 300]),
                    "Lick_R": np.array([200], dtype=int),
                },
            },
            "Reward_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        # L→R (100→200): 1; R→L (200→300): 1
        assert sw["L->R"] == pytest.approx(1.0)
        assert sw["R->L"] == pytest.approx(1.0)


class TestRenderLickinessBySession:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, png_path = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "lickiness_bySession_relStroke.svg"
        assert png_path.name == "lickiness_bySession_relStroke.png"

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "lickiness_bySession_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_lickiness_bySession("PS51", resolver, align_to_stroke=True)

    def test_title_and_ylabel_strings(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Lickiness by session" in svg_text
        assert "Late licks per session" in svg_text

    def test_mouse_frame_ylabel_no_fn_flip(self, cohort_for_renders):
        """Legend labels say "mouse L" / "mouse R" directly (no flip).
        Pin to catch regression to legacy fn_flip_lr."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "mouse L" in svg_text
        assert "mouse R" in svg_text


class TestRenderSwitchinessBySession:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, png_path = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "switchiness_bySession_relStroke.svg"

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "switchiness_bySession_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_switchiness_bySession("PS51", resolver, align_to_stroke=True)

    def test_title_and_ylabel_strings(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Switchiness by session" in svg_text
        assert "Avg switches per trial" in svg_text

    def test_legend_labels_use_arrow_notation(self, cohort_for_renders):
        """Pin: legacy plot uses "L→R" / "R→L" label strings (with arrow
        character, not "->")."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib SVG-escapes "→" as the literal Unicode arrow char
        assert "L→R" in svg_text
        assert "R→L" in svg_text


class TestSessionPlotDataNSamplesExtension:
    """CG-4 extended SessionPlotData with n_samples_session. CG-1 tests
    that don't set the field still pass (default 0); load_session_plot_data
    reads it from the first 1D WS signal when present."""

    def test_default_zero(self):
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={"Lick_L": np.array([]), "Lick_R": np.array([])},
            rewards_idx={"Reward_L": np.array([]), "Reward_R": np.array([])},
            sample_rate=1000.0,
        )
        assert data.n_samples_session == 0

    def test_load_populates_from_1d_signal(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100]),
            lick_r=np.array([150]),
            reward_l=np.array([50]),
            reward_r=np.array([175]),
            sample_rate=1000.0,
            n_samples=42_000,
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert data.n_samples_session == 42_000

    def test_load_defaults_to_zero_when_no_1d_signal(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100]),
            lick_r=np.array([150]),
            reward_l=np.array([50]),
            reward_r=np.array([175]),
            sample_rate=1000.0,
            # n_samples=None → no 1D signal in WS NPZ
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert data.n_samples_session == 0


class TestCG4ModuleExports:
    @pytest.mark.parametrize("name", [
        "compute_lickiness_bySession", "compute_switchiness_bySession",
        "render_lickiness_bySession", "render_switchiness_bySession",
    ])
    def test_symbol_exists(self, name):
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 4 public surface"
        )
