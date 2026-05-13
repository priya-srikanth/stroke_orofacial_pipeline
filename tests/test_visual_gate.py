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
    np.savez(
        ws_dir / f"{date_label}.npz",
        sample_rate_input=np.array(sample_rate),
    )


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
