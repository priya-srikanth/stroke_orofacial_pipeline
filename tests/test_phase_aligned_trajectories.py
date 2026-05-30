"""Phase 9.1 Q-lock 13 — phase-aligned trajectory figure tests.

Snapshot-style tests on the in-memory Figure structure: panel grid
dimensions, panel titles, n-annotation text, baseline-overlay presence
on post-epoch panels (but NOT on pre), SEM-band presence, output-path
resolution + emit-all routing.

NOT pixel-equality tests (per kickoff Stage 3 contract).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.figures.palette import (
    PHENOTYPE_ORDER,
    phenotype_display_name,
    phenotype_palette,
)
from stroke_orofacial.figures.phase_aligned_trajectories import (
    DEFAULT_PHASE_DISPLAY_WINDOW,
    EPOCH_DISPLAY_NAMES,
    EPOCH_ORDER,
    FIGURE_SUBDIR,
    FIGURE_SUBTITLE,
    RESULTS_SUBDIR,
    SOURCE_DATA_SUBTITLE_DELTA,
    SOURCE_DATA_SUBTITLE_RAW,
    build_phase_aligned_trajectory_figure,
    compute_trajectory_bootstrap_effect_ci,
    compute_trajectory_bootstrap_pre_ci,
    compute_trajectory_cluster_permutation_stats,
    compute_trajectory_lmm_stats,
    compute_trajectory_mwu_stats,
    compute_trajectory_wilcoxon_stats,
    emit_phase_aligned_trajectory_figures,
    figure_path_for,
    render_phase_aligned_trajectory_figure,
)
from stroke_orofacial.paths import PathResolver


N_PHASE_BINS = 8  # small for tests; production uses 72


def _pooled_df(
    *,
    signals=("angle_deg", "x_centered", "y_centered"),
    variants=("raw", "delta"),
    sides=("L", "R"),
    epochs=EPOCH_ORDER,
    phenotypes=PHENOTYPE_ORDER,
    n_phase_bins: int = N_PHASE_BINS,
    n_trials: int = 5,
) -> pd.DataFrame:
    """Build a synthetic phenotype-pooled DataFrame with the full grid.

    Each cell carries a deterministic mean (sin-shaped over phase) with
    a tiny phenotype offset so panels are distinguishable in snapshot
    inspection. SEM = 0.1 for finite-band coverage.

    Q-lock 13c Stage 3 (2026-05-29): default signals tuple gained
    ``y_centered`` so the synthetic fixture matches the now-canonical
    3-signal trajectory matrix.
    """
    rows = []
    for phen_idx, phen in enumerate(phenotypes):
        for epoch_idx, epoch in enumerate(epochs):
            for side in sides:
                for signal in signals:
                    for variant in variants:
                        for bin_idx in range(n_phase_bins):
                            center = (bin_idx + 0.5) / n_phase_bins
                            mean = (
                                np.sin(2 * np.pi * center)
                                + 0.1 * phen_idx
                                + 0.05 * epoch_idx
                            )
                            rows.append({
                                "recovery_phenotype": phen,
                                "epoch_label": epoch,
                                "side": side,
                                "phase_bin": bin_idx,
                                "phase_bin_center": center,
                                "sd": 0.3,  # Q-lock 13.4 SD column
                                "signal": signal,
                                "variant": variant,
                                "mean": float(mean),
                                "sem": 0.1,
                                "n_trials": n_trials,
                                "n_sessions": 2,
                                "n_animals": 2,
                            })
    return pd.DataFrame(rows)


class TestBuildPhaseAlignedTrajectoryFigure:
    def test_panel_grid_is_4_by_4(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        assert axes.shape == (len(PHENOTYPE_ORDER), len(EPOCH_ORDER))
        assert axes.shape == (4, 4)
        plt.close(fig)

    def test_column_titles_are_epoch_display_names(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Top row carries the epoch column titles.
        for col_idx, epoch in enumerate(EPOCH_ORDER):
            assert axes[0, col_idx].get_title() == EPOCH_DISPLAY_NAMES[epoch]
        plt.close(fig)

    def test_row_ylabels_are_phenotype_display_names(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        for row_idx, phen in enumerate(PHENOTYPE_ORDER):
            assert axes[row_idx, 0].get_ylabel() == phenotype_display_name(phen)
        plt.close(fig)

    def test_n_trials_annotation_present_per_panel(self):
        df = _pooled_df(n_trials=42)
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Every panel must carry an n=N trials annotation.
        for ax in axes.ravel():
            annotation_texts = [
                child.get_text() for child in ax.get_children()
                if hasattr(child, "get_text")
                and "n=" in str(child.get_text())
            ]
            assert any("n=42 trials" in t for t in annotation_texts), (
                f"axis {ax} missing n=N trials annotation"
            )
        plt.close(fig)

    def test_n_zero_annotation_on_empty_panel(self):
        # Build a df missing the (severe, chronic) cell entirely.
        df = _pooled_df()
        df = df[~(
            (df["recovery_phenotype"] == "severe")
            & (df["epoch_label"] == "chronic")
        )]
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        severe_row = PHENOTYPE_ORDER.index("severe")
        chronic_col = EPOCH_ORDER.index("chronic")
        empty_ax = axes[severe_row, chronic_col]
        empty_texts = [
            child.get_text() for child in empty_ax.get_children()
            if hasattr(child, "get_text")
            and "n=" in str(child.get_text())
        ]
        assert any("n=0 trials" in t for t in empty_texts)
        plt.close(fig)

    def test_baseline_overlay_present_on_post_panels_only(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Pre column (col 0): one mean line (no grey overlay).
        # Post columns: mean line + grey dashed overlay.
        for row_idx in range(len(PHENOTYPE_ORDER)):
            pre_ax = axes[row_idx, EPOCH_ORDER.index("pre")]
            pre_dashed = [
                ln for ln in pre_ax.get_lines()
                if ln.get_linestyle() == "--" and ln.get_color() == "grey"
            ]
            assert len(pre_dashed) == 0, (
                f"pre panel row {row_idx} unexpectedly has dashed-grey overlay"
            )

            for epoch in ("acute", "sub_acute", "chronic"):
                post_ax = axes[row_idx, EPOCH_ORDER.index(epoch)]
                post_dashed = [
                    ln for ln in post_ax.get_lines()
                    if ln.get_linestyle() == "--" and ln.get_color() == "grey"
                ]
                assert len(post_dashed) == 1, (
                    f"row {row_idx} epoch {epoch}: expected 1 dashed-grey "
                    f"baseline overlay, got {len(post_dashed)}"
                )
        plt.close(fig)

    def test_phenotype_palette_applied_to_traces(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        for row_idx, phen in enumerate(PHENOTYPE_ORDER):
            expected = phenotype_palette(phen)
            for col_idx in range(len(EPOCH_ORDER)):
                ax = axes[row_idx, col_idx]
                # Mean trace = the line that is NOT grey-dashed.
                colored_lines = [
                    ln for ln in ax.get_lines()
                    if ln.get_linestyle() != "--"
                ]
                assert len(colored_lines) >= 1
                # matplotlib normalizes color to a tuple sometimes;
                # compare via to_rgba for robustness.
                from matplotlib.colors import to_rgba
                actual = colored_lines[0].get_color()
                assert to_rgba(actual) == to_rgba(expected), (
                    f"row {row_idx} col {col_idx} trace color {actual} "
                    f"!= expected phenotype color {expected}"
                )
        plt.close(fig)

    def test_sem_band_drawn_when_sem_finite(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Each panel should have at least one PolyCollection from
        # fill_between (the SEM band).
        from matplotlib.collections import PolyCollection
        for ax in axes.ravel():
            polys = [
                c for c in ax.collections
                if isinstance(c, PolyCollection)
            ]
            assert len(polys) >= 1
        plt.close(fig)

    def test_suptitle_carries_signal_variant_side(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="x_centered", variant="delta", side="R",
        )
        sup = fig._suptitle.get_text() if fig._suptitle else ""
        assert "Tongue x" in sup
        assert "Δ" in sup or "delta" in sup.lower()
        assert "side=R" in sup
        plt.close(fig)

    def test_figure_subtitle_text_present(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Figure-level texts include the subtitle (footer).
        fig_texts = [
            t.get_text() for t in fig.texts
        ]
        assert FIGURE_SUBTITLE in fig_texts
        plt.close(fig)

    def test_phase_display_window_clips_xlim(self):
        df = _pooled_df()
        # Custom narrow window — verify the xlim reflects it on every panel.
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            phase_display_window=(0.2, 0.8),
        )
        for ax in axes.ravel():
            lo, hi = ax.get_xlim()
            assert lo == pytest.approx(0.2)
            assert hi == pytest.approx(0.8)
        plt.close(fig)

    def test_phase_display_window_default_clips_edges(self):
        df = _pooled_df()
        # Default window applies edge clip.
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        for ax in axes.ravel():
            lo, hi = ax.get_xlim()
            assert lo == pytest.approx(DEFAULT_PHASE_DISPLAY_WINDOW[0])
            assert hi == pytest.approx(DEFAULT_PHASE_DISPLAY_WINDOW[1])
        plt.close(fig)

    def test_phase_display_window_invalid_raises(self):
        df = _pooled_df()
        with pytest.raises(ValueError, match="phase_display_window"):
            build_phase_aligned_trajectory_figure(
                df, signal="angle_deg", variant="raw", side="L",
                phase_display_window=(0.8, 0.2),
            )

    def _band_thickness_at_first_x(self, ax) -> float:
        """Measure the SD/SEM band thickness at the leftmost x of a panel.

        Reads the fill_between's PolyCollection and returns the y extent
        between upper and lower band edges at the smallest-x vertex.
        Robust to the sin-shaped mean trajectory in the fixture.
        """
        from matplotlib.collections import PolyCollection
        polys = [c for c in ax.collections if isinstance(c, PolyCollection)]
        assert polys, "no fill_between band on populated panel"
        verts = polys[0].get_paths()[0].vertices
        x_vals = verts[:, 0]
        # leftmost x — there should be two vertices at this x (upper +
        # lower band edge).
        leftmost = float(np.min(x_vals))
        on_left = np.isclose(x_vals, leftmost)
        y_on_left = verts[on_left, 1]
        return float(np.max(y_on_left) - np.min(y_on_left))

    def test_error_band_default_uses_sem(self):
        df = _pooled_df()
        df["sem"] = 0.05
        df["sd"] = 0.4
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        # Default error_band_type = "sem" → ±0.05 band thickness = 0.1.
        thickness = self._band_thickness_at_first_x(axes[0, 1])
        assert thickness == pytest.approx(0.1, abs=0.02)
        plt.close(fig)

    def test_error_band_sd_kwarg_uses_sd(self):
        df = _pooled_df()
        df["sem"] = 0.05
        df["sd"] = 0.4
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            error_band_type="sd",
        )
        # ±0.4 band thickness = 0.8.
        thickness = self._band_thickness_at_first_x(axes[0, 1])
        assert thickness == pytest.approx(0.8, abs=0.05)
        plt.close(fig)

    def test_error_band_sem_kwarg_uses_sem(self):
        df = _pooled_df()
        df["sem"] = 0.05
        df["sd"] = 0.4
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            error_band_type="sem",
        )
        # error_band_type="sem" → ±0.05 band thickness = 0.1.
        thickness = self._band_thickness_at_first_x(axes[0, 1])
        assert thickness == pytest.approx(0.1, abs=0.02)
        plt.close(fig)

    def test_error_band_invalid_raises(self):
        df = _pooled_df()
        with pytest.raises(ValueError, match="error_band_type"):
            build_phase_aligned_trajectory_figure(
                df, signal="angle_deg", variant="raw", side="L",
                error_band_type="ci95",
            )

    def test_3tier_phenotype_order_yields_3_row_grid(self):
        # Synthesize a pooled_df that has the 3-tier phenotype set.
        df = _pooled_df(phenotypes=("mild", "moderate", "severe"))
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            phenotype_order=("mild", "moderate", "severe"),
        )
        assert axes.shape == (3, 4)
        plt.close(fig)

    def test_phenotype_order_empty_raises(self):
        df = _pooled_df()
        with pytest.raises(ValueError, match="phenotype_order"):
            build_phase_aligned_trajectory_figure(
                df, signal="angle_deg", variant="raw", side="L",
                phenotype_order=(),
            )

    def test_y_range_applied_to_every_panel(self):
        df = _pooled_df()
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            y_range=(-3.0, 7.0),
        )
        for ax in axes.ravel():
            lo, hi = ax.get_ylim()
            assert lo == pytest.approx(-3.0)
            assert hi == pytest.approx(7.0)
        plt.close(fig)

    def test_y_range_invalid_raises(self):
        df = _pooled_df()
        with pytest.raises(ValueError, match="y_range"):
            build_phase_aligned_trajectory_figure(
                df, signal="angle_deg", variant="raw", side="L",
                y_range=(1.0, -1.0),
            )

    def test_share_y_across_sides_default_emits_both_with_same_range(
        self, tmp_path,
    ):
        # When emit_phase_aligned_trajectory_figures is called with the
        # default share_y_across_sides=True + sides=(L, R), both sides
        # should render with the same y_range. We can't easily inspect
        # the SVGs here but we can verify the renderer was called for
        # both and produced files of similar dimension. Direct unit
        # test on _compute_shared_y_range follows.
        from stroke_orofacial.figures.phase_aligned_trajectories import (
            _compute_shared_y_range,
        )
        df = _pooled_df()
        # Inject a much larger mean for side=R to verify the range
        # widens to span BOTH sides, not just one.
        df_widened = df.copy()
        mask = (df_widened["side"] == "R") & (df_widened["signal"] == "angle_deg")
        df_widened.loc[mask, "mean"] = df_widened.loc[mask, "mean"] + 100.0
        rng_with_both = _compute_shared_y_range(
            df_widened,
            signal="angle_deg", variant="raw",
            sides=("L", "R"),
            phase_display_window=(0.0, 1.0),
            error_band_type="sem",
            phenotype_order=PHENOTYPE_ORDER,
        )
        rng_L_only = _compute_shared_y_range(
            df_widened,
            signal="angle_deg", variant="raw",
            sides=("L",),
            phase_display_window=(0.0, 1.0),
            error_band_type="sem",
            phenotype_order=PHENOTYPE_ORDER,
        )
        # L+R should reach higher (because R was shifted +100).
        assert rng_with_both[1] > rng_L_only[1] + 50.0

    def test_raw_variant_carries_raw_source_subtitle(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        fig_texts = [t.get_text() for t in fig.texts]
        assert SOURCE_DATA_SUBTITLE_RAW in fig_texts
        assert SOURCE_DATA_SUBTITLE_DELTA not in fig_texts
        plt.close(fig)

    def test_delta_variant_carries_delta_source_subtitle(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="x_centered", variant="delta", side="R",
        )
        fig_texts = [t.get_text() for t in fig.texts]
        assert SOURCE_DATA_SUBTITLE_DELTA in fig_texts
        assert SOURCE_DATA_SUBTITLE_RAW not in fig_texts
        plt.close(fig)


class TestFigurePathFor:
    def test_filename_pattern(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        # Default error_band_type = "sem" → 'mean_sem' slug.
        p = figure_path_for(
            signal="angle_deg", variant="raw", side="L",
            resolver=resolver,
        )
        assert p.name == "angle_deg_raw_L_mean_sem_cleaned_trace.svg"
        # SD variant → 'mean_sd' slug.
        p_sd = figure_path_for(
            signal="angle_deg", variant="raw", side="L",
            resolver=resolver, error_band_type="sd",
        )
        assert p_sd.name == "angle_deg_raw_L_mean_sd_cleaned_trace.svg"
        # FIGURE_SUBDIR uses POSIX separators; compare via Path parts.
        for part in Path(FIGURE_SUBDIR).parts:
            assert part in p.parts

    def test_output_dir_override(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        custom = tmp_path / "custom"
        p = figure_path_for(
            signal="x_centered", variant="delta", side="R",
            resolver=resolver, output_dir=custom,
        )
        assert p.parent == custom
        assert p.name == "x_centered_delta_R_mean_sem_cleaned_trace.svg"


class TestRenderPhaseAlignedTrajectoryFigure:
    def test_writes_svg_file(self, tmp_path):
        df = _pooled_df()
        out_path = tmp_path / "out.svg"
        result = render_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            output_path=out_path,
        )
        assert result == out_path
        assert out_path.exists()
        # SVG starts with <?xml or <svg...
        head = out_path.read_text(encoding="utf-8")[:200]
        assert "<svg" in head or "<?xml" in head


class TestEmitPhaseAlignedTrajectoryFigures:
    def test_emits_12_figures_under_force(self, tmp_path):
        # Q-lock 13c Stage 3: 3 signals × 2 variants × 2 sides = 12 figures.
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        out = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
        )
        assert len(out["emitted"]) == 12
        assert len(out["skipped"]) == 0
        # Confirm filename pattern + on-disk presence.
        names = {p.name for p in out["emitted"]}
        expected_names = {
            f"{signal}_{variant}_{side}_mean_sem_cleaned_trace.svg"
            for signal in ("angle_deg", "x_centered", "y_centered")
            for variant in ("raw", "delta")
            for side in ("L", "R")
        }
        assert names == expected_names

    def test_skip_mode_does_not_overwrite_existing(self, tmp_path):
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        # First emit: writes all 12.
        emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
        )
        # Capture mtimes.
        out_dir = resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
        mtimes_before = {
            p.name: p.stat().st_mtime
            for p in out_dir.glob("*.svg")
        }
        # Second emit with skip mode: nothing rewritten.
        out2 = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="skip",
        )
        assert len(out2["emitted"]) == 0
        assert len(out2["skipped"]) == 12
        mtimes_after = {
            p.name: p.stat().st_mtime
            for p in out_dir.glob("*.svg")
        }
        assert mtimes_before == mtimes_after

    def test_subset_render_via_signals_variants_sides_args(self, tmp_path):
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        out = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
            signals=("angle_deg",), variants=("raw",), sides=("L", "R"),
        )
        assert len(out["emitted"]) == 2
        names = {p.name for p in out["emitted"]}
        assert names == {
            "angle_deg_raw_L_mean_sem_cleaned_trace.svg",
            "angle_deg_raw_R_mean_sem_cleaned_trace.svg",
        }


# ---------------------------------------------------------------------------
# Q-lock 13c Addendum #2 — figures vs results tree split
# ---------------------------------------------------------------------------


class TestFiguresResultsTreeSplit:
    """Q-lock 13c Addendum #2 (2026-05-29): numerical CSVs split from
    the figures tree. FIGURE_SUBDIR keeps SVGs; RESULTS_SUBDIR receives
    CSVs. Both share the same relative-subpath structure (root,
    3_phenotype/, null_calibration/, 3_phenotype/null_calibration/)."""

    def test_results_subdir_constant_lock(self):
        # Lock the literal so future renames are intentional.
        assert RESULTS_SUBDIR == (
            "stats/results/phenotype_pooled/phase_aligned_trajectories"
        )

    def test_figure_subdir_constant_unchanged(self):
        # FIGURE_SUBDIR stays at the same tree it had at Q13 close.
        assert FIGURE_SUBDIR == (
            "stats/figures/phenotype_pooled/phase_aligned_trajectories"
        )

    def test_results_and_figure_subdirs_differ_only_in_figures_vs_results(self):
        # The two trees mirror each other at the project-wide split
        # point: ``stats/figures/`` (renders) vs ``stats/results/`` (CSVs).
        assert FIGURE_SUBDIR.replace("figures", "results") == RESULTS_SUBDIR

    def test_emit_phase_aligned_trajectory_figures_writes_no_csvs(
        self, tmp_path,
    ):
        # The renderer only produces SVGs. CSVs are written by the
        # cohort emit driver (run_stats_and_figures), which routes them
        # to results_dir; this test locks the figure-side invariant.
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        out = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
            output_dir=tmp_path / "figs",
        )
        # All emitted paths end in .svg; no .csv siblings appear under
        # the figures output dir.
        for p in out["emitted"]:
            assert p.suffix == ".svg", f"unexpected non-SVG emit: {p}"
        csvs = list((tmp_path / "figs").glob("*.csv"))
        assert csvs == [], f"unexpected CSVs under figures dir: {csvs}"


# ---------------------------------------------------------------------------
# Q-lock 13c Stage 3 — y_centered figure renderer regression
# ---------------------------------------------------------------------------


class TestYCenteredTrajectoryFigure:
    """Q-lock 13c Stage 3 (2026-05-29): y_centered joins the trajectory
    figure matrix. The renderer is parametric on the signal column, so a
    minimal regression on a y-only fixture confirms the new figures
    render through the existing build + emit pipeline."""

    def test_y_centered_panel_grid_is_4_by_4(self):
        df = _pooled_df(signals=("y_centered",))
        fig, axes = build_phase_aligned_trajectory_figure(
            df, signal="y_centered", variant="raw", side="L",
        )
        assert axes.shape == (4, 4)
        plt.close(fig)

    def test_y_centered_filename_matches_kickoff_lock(self, tmp_path):
        # Q-lock 13c-H lock: y figures land alongside angle/x in
        # stats/figures/phenotype_pooled/phase_aligned_trajectories/
        # with the existing <signal>_<variant>_<side>_mean_sem_cleaned_trace
        # filename convention (Q13 de-facto convention).
        from stroke_orofacial.figures.phase_aligned_trajectories import (
            figure_path_for,
        )
        resolver = PathResolver(output_root=tmp_path)
        path_raw = figure_path_for(
            signal="y_centered", variant="raw", side="L", resolver=resolver,
        )
        path_delta = figure_path_for(
            signal="y_centered", variant="delta", side="R", resolver=resolver,
        )
        assert path_raw.name == (
            "y_centered_raw_L_mean_sem_cleaned_trace.svg"
        )
        assert path_delta.name == (
            "y_centered_delta_R_mean_sem_cleaned_trace.svg"
        )
        # Both land under the Q-lock 13c-H locked subdir.
        assert str(path_raw).endswith(
            "stats/figures/phenotype_pooled/phase_aligned_trajectories/"
            "y_centered_raw_L_mean_sem_cleaned_trace.svg"
        ) or str(path_raw).endswith(
            "stats\\figures\\phenotype_pooled\\phase_aligned_trajectories\\"
            "y_centered_raw_L_mean_sem_cleaned_trace.svg"
        )

    def test_y_centered_signal_display_name_is_protrusion_label(self):
        from stroke_orofacial.figures.phase_aligned_trajectories import (
            SIGNAL_DISPLAY_NAMES,
        )
        # Y-axis label semantic: spout-midpoint frame; protrusion-aware
        # phrasing acceptable. Lock the literal Q-lock 13c Stage 3
        # decision so future renames are intentional.
        assert SIGNAL_DISPLAY_NAMES["y_centered"] == (
            "Tongue y (spout-midpoint frame, px)"
        )

    def test_emit_default_includes_y_centered_in_signal_loop(self, tmp_path):
        # The emit default tracks TRAJECTORY_SIGNALS (Stage 3 lock).
        # Confirm y figures appear in the default-arg emit.
        df = _pooled_df()  # full 3-signal pool
        resolver = PathResolver(output_root=tmp_path)
        out = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
        )
        names = {p.name for p in out["emitted"]}
        # 4 y figures (2 variants × 2 sides) must be present.
        y_names = {
            n for n in names if n.startswith("y_centered_")
        }
        assert y_names == {
            "y_centered_raw_L_mean_sem_cleaned_trace.svg",
            "y_centered_raw_R_mean_sem_cleaned_trace.svg",
            "y_centered_delta_L_mean_sem_cleaned_trace.svg",
            "y_centered_delta_R_mean_sem_cleaned_trace.svg",
        }


# ---------------------------------------------------------------------------
# Q-lock 13.1 — paired Wilcoxon family on per-animal trajectory scalars
# ---------------------------------------------------------------------------


def _animal_info(
    animal_id: str, *,
    phenotype: str | None = "mild",
) -> AnimalInfo:
    import datetime
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=datetime.date(2025, 3, 7),
        session_start=datetime.date(2025, 2, 5),
        session_end=datetime.date(2025, 5, 6),
        epoch_boundaries=EpochBoundaries(
            acute_max_rel_day=7,
            subacute_max_rel_day=14,
            chronic_min_rel_day=15,
        ),
        recovery_phenotype=phenotype,
        kinematics_baselines={
            "tongue": {"x0": 0.0, "y0": 0.0},
            "jaw": {"x0": 0.0, "y0": 0.0},
        },
        bin_days=2,
    )


def _scalar_rows(rows: list[dict]) -> pd.DataFrame:
    canonical = []
    for r in rows:
        canonical.append({
            "animal": r["animal"],
            "side": r.get("side", "L"),
            "signal": r.get("signal", "angle_deg"),
            "epoch_label": r["epoch_label"],
            "scalar": float(r["scalar"]),
        })
    return pd.DataFrame(canonical)


class TestComputeTrajectoryWilcoxonStats:
    def test_returns_48_cells_with_correction_columns(self):
        # Build per-animal scalars for 3 mild animals × 4 epochs × 2
        # sides × 1 signal — 24 rows. compute_trajectory_wilcoxon_stats
        # should still emit one row per (4 phen × 2 sides × 2 signals
        # × 3 epochs) = 48 cells; cells without n≥2 animals get NaN p.
        rows: list[dict] = []
        for ai, animal in enumerate(("PS47", "PS48", "PS49")):
            for ei, epoch in enumerate(("pre", "acute", "sub_acute", "chronic")):
                for side in ("L", "R"):
                    rows.append({
                        "animal": animal, "side": side,
                        "signal": "angle_deg", "epoch_label": epoch,
                        "scalar": 10.0 + ei + ai * 0.1,
                    })
        scalars = _scalar_rows(rows)
        animals = {
            "PS47": _animal_info("PS47", phenotype="mild"),
            "PS48": _animal_info("PS48", phenotype="mild"),
            "PS49": _animal_info("PS49", phenotype="mild"),
        }
        out = compute_trajectory_wilcoxon_stats(
            scalars, animals, signals=("angle_deg", "x_centered"),
        )
        # 4 phen × 2 sides × 2 signals × 3 post epochs = 48 rows.
        assert len(out) == 48
        for col in (
            "recovery_phenotype", "side", "signal", "post_epoch",
            "statistic", "p_value", "n_observations", "status",
            "median_diff", "p_adj", "reject",
        ):
            assert col in out.columns
        # mild × L × angle_deg × acute should be 'ok' (n=3).
        mild_L_angle_acute = out[
            (out["recovery_phenotype"] == "mild")
            & (out["side"] == "L")
            & (out["signal"] == "angle_deg")
            & (out["post_epoch"] == "acute")
        ].iloc[0]
        assert mild_L_angle_acute["status"] == "ok"
        assert int(mild_L_angle_acute["n_observations"]) == 3

    def test_n_eq_1_phenotype_marks_insufficient_data(self):
        # Single moderate animal → all moderate cells should be
        # status=insufficient_data with NaN p_value.
        rows = []
        for ei, epoch in enumerate(("pre", "acute", "sub_acute", "chronic")):
            for side in ("L", "R"):
                rows.append({
                    "animal": "PS46", "side": side,
                    "signal": "angle_deg", "epoch_label": epoch,
                    "scalar": 1.0 + ei,
                })
        scalars = _scalar_rows(rows)
        animals = {
            "PS46": _animal_info("PS46", phenotype="moderate"),
        }
        out = compute_trajectory_wilcoxon_stats(
            scalars, animals, signals=("angle_deg",),
        )
        mod_rows = out[out["recovery_phenotype"] == "moderate"]
        assert len(mod_rows) == 6  # 1 signal × 2 sides × 3 post epochs
        for _, r in mod_rows.iterrows():
            assert r["status"] == "insufficient_data"
            assert not np.isfinite(r["p_value"])

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({
            "animal": ["PS46"], "side": ["L"], "epoch_label": ["pre"],
            # signal + scalar missing
        })
        with pytest.raises(ValueError, match="missing required column"):
            compute_trajectory_wilcoxon_stats(bad, {})

    def test_unknown_phenotype_animal_dropped(self):
        rows = [
            {"animal": "PS47", "side": "L", "signal": "angle_deg",
             "epoch_label": "pre", "scalar": 1.0},
            {"animal": "PS_unknown", "side": "L", "signal": "angle_deg",
             "epoch_label": "pre", "scalar": 99.0},
        ]
        scalars = _scalar_rows(rows)
        animals = {
            "PS47": _animal_info("PS47", phenotype="mild"),
        }
        # No exception; unknown animal dropped before stats compute.
        out = compute_trajectory_wilcoxon_stats(
            scalars, animals, signals=("angle_deg",),
        )
        assert len(out) > 0
        # mild PS47 alone is n=1 → insufficient_data.
        mild_acute = out[
            (out["recovery_phenotype"] == "mild")
            & (out["post_epoch"] == "acute")
            & (out["side"] == "L")
            & (out["signal"] == "angle_deg")
        ].iloc[0]
        assert mild_acute["status"] in {"insufficient_data", "all_zero_diffs"}


# ---------------------------------------------------------------------------
# Q-lock 13.5 — unpaired MWU family on per-trial / per-session scalars
# ---------------------------------------------------------------------------


class TestComputeTrajectoryMwuStats:
    def test_returns_48_cells_with_correction_columns(self):
        # 6 mild trials × {pre, acute, sub_acute, chronic} × {L, R}.
        rows = []
        for ai, animal in enumerate(("PS47", "PS48", "PS49")):
            for trial_idx in range(4):
                for epoch in ("pre", "acute", "sub_acute", "chronic"):
                    for side in ("L", "R"):
                        rows.append({
                            "animal": animal, "side": side,
                            "signal": "angle_deg", "epoch_label": epoch,
                            "scalar": 1.0 + ai * 0.1 + trial_idx * 0.01,
                        })
        scalars = _scalar_rows(rows)
        animals = {
            a: _animal_info(a, phenotype="mild")
            for a in ("PS47", "PS48", "PS49")
        }
        out = compute_trajectory_mwu_stats(
            scalars, animals, signals=("angle_deg", "x_centered"),
            grain="trial",
        )
        assert len(out) == 48
        for col in (
            "recovery_phenotype", "side", "signal", "post_epoch", "grain",
            "statistic", "p_value", "n_pre", "n_post", "status",
            "p_adj", "reject",
        ):
            assert col in out.columns
        # mild × L × angle_deg × acute should be 'ok' (n_pre=12, n_post=12).
        mild_L_angle_acute = out[
            (out["recovery_phenotype"] == "mild")
            & (out["side"] == "L")
            & (out["signal"] == "angle_deg")
            & (out["post_epoch"] == "acute")
        ].iloc[0]
        assert mild_L_angle_acute["status"] == "ok"
        # Grain column annotation.
        assert (out["grain"] == "trial").all()

    def test_grain_session_annotation(self):
        rows = [
            {"animal": "PS47", "side": "L", "signal": "angle_deg",
             "epoch_label": "pre", "scalar": 1.0},
            {"animal": "PS47", "side": "L", "signal": "angle_deg",
             "epoch_label": "acute", "scalar": 2.0},
        ]
        out = compute_trajectory_mwu_stats(
            _scalar_rows(rows),
            {"PS47": _animal_info("PS47", phenotype="mild")},
            signals=("angle_deg",), grain="session",
        )
        assert (out["grain"] == "session").all()

    def test_invalid_grain_raises(self):
        with pytest.raises(ValueError, match="grain"):
            compute_trajectory_mwu_stats(
                pd.DataFrame(
                    columns=[
                        "animal", "side", "signal", "epoch_label", "scalar",
                    ]
                ),
                {}, grain="bogus",
            )

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({
            "animal": ["PS46"], "side": ["L"], "epoch_label": ["pre"],
        })
        with pytest.raises(ValueError, match="missing required column"):
            compute_trajectory_mwu_stats(bad, {}, grain="trial")


# ---------------------------------------------------------------------------
# Q-lock 13.6 — LMM + cluster permutation + bootstrap CI
# ---------------------------------------------------------------------------


def _make_session_scalars(
    n_animals: int = 3,
    n_sessions_per_animal: int = 5,
    phenotype: str = "mild",
) -> tuple[pd.DataFrame, dict]:
    """Build a per-session scalar DataFrame for LMM smoke tests."""
    import datetime
    rows = []
    animals = {}
    for ai in range(n_animals):
        aid = f"PS{40 + ai:02d}"
        animals[aid] = _animal_info(aid, phenotype=phenotype)
        for ei, epoch in enumerate(("pre", "acute", "sub_acute", "chronic")):
            for si in range(n_sessions_per_animal):
                for side in ("L", "R"):
                    rows.append({
                        "animal": aid,
                        "date": datetime.date(2025, 3, 1) + datetime.timedelta(
                            days=ei * 10 + si,
                        ),
                        "side": side,
                        "signal": "angle_deg",
                        "epoch_label": epoch,
                        "scalar": 1.0 + ei * 0.5 + ai * 0.1 + si * 0.05,
                    })
    return pd.DataFrame(rows), animals


class TestComputeTrajectoryLmmStats:
    def test_smoke_emits_48_cells_with_p_adj(self):
        scalars, animals = _make_session_scalars()
        out = compute_trajectory_lmm_stats(
            scalars, animals, signals=("angle_deg", "x_centered"),
        )
        # 4 phen × 2 sides × 2 signals × 3 post epochs = 48 rows.
        assert len(out) == 48
        for col in (
            "recovery_phenotype", "side", "signal", "post_epoch",
            "coef", "se", "p_value", "n_observations", "n_animals",
            "status", "p_adj", "reject",
        ):
            assert col in out.columns

    def test_n_eq_1_yields_insufficient_data(self):
        scalars, animals = _make_session_scalars(n_animals=1)
        out = compute_trajectory_lmm_stats(
            scalars, animals, signals=("angle_deg",),
        )
        mild_rows = out[out["recovery_phenotype"] == "mild"]
        # All mild rows should be insufficient_data (n=1 < 2 animals).
        assert (mild_rows["status"] == "insufficient_data").all()

    def test_missing_required_column_raises(self):
        bad = pd.DataFrame({"animal": ["PS46"]})
        with pytest.raises(ValueError, match="missing column"):
            compute_trajectory_lmm_stats(bad, {})


class TestComputeTrajectoryClusterPermutationStats:
    def test_smoke_runs_emits_rows(self):
        # Build a tiny densified-shaped cohort with 2 mild animals × 4
        # sessions × 2 sides × 8 bins × 4 epochs × 2 signals.
        import datetime
        rows = []
        n_bins = 8
        for animal in ("PS47", "PS48"):
            for di in range(4):
                date = datetime.date(2025, 3, 1) + datetime.timedelta(
                    days=di * 5,
                )
                for ei, epoch in enumerate(
                    ("pre", "acute", "sub_acute", "chronic"),
                ):
                    for side in ("L", "R"):
                        for bin_idx in range(n_bins):
                            rows.append({
                                "animal": animal,
                                "date": date + datetime.timedelta(days=ei * 30),
                                "side": side,
                                "phase_bin": bin_idx,
                                "phase_bin_center": (bin_idx + 0.5) / n_bins,
                                "epoch_label": epoch,
                                "recovery_phenotype": "mild",
                                "angle_deg": ei + bin_idx * 0.1,
                                "x_centered": -ei + bin_idx * 0.1,
                                "angle_deg_delta": ei * 0.5,
                                "x_centered_delta": -ei * 0.5,
                            })
        cohort = pd.DataFrame(rows)
        animals = {
            "PS47": _animal_info("PS47", phenotype="mild"),
            "PS48": _animal_info("PS48", phenotype="mild"),
        }
        out = compute_trajectory_cluster_permutation_stats(
            cohort, animals,
            signals=("angle_deg",), variants=("raw",),
            n_permutations=50,  # small for test speed
            rng_seed=0,
        )
        assert len(out) >= 1
        for col in (
            "recovery_phenotype", "side", "signal", "variant",
            "post_epoch", "cluster_idx",
            "start_bin", "end_bin", "cluster_mass", "sign", "p_value",
            "n_pre", "n_post", "status", "p_adj", "reject",
        ):
            assert col in out.columns

    def test_invalid_n_permutations_raises(self):
        with pytest.raises(ValueError, match="n_permutations"):
            compute_trajectory_cluster_permutation_stats(
                pd.DataFrame(
                    columns=[
                        "animal", "date", "side", "phase_bin",
                        "epoch_label", "recovery_phenotype",
                        "angle_deg", "x_centered",
                        "angle_deg_delta", "x_centered_delta",
                    ]
                ),
                {}, n_permutations=0,
            )


class TestComputeTrajectoryBootstrapPreCi:
    def test_smoke_emits_per_bin_rows(self):
        import datetime
        rows = []
        for animal in ("PS47", "PS48"):
            for date in (
                datetime.date(2025, 3, 1), datetime.date(2025, 3, 2),
            ):
                for side in ("L", "R"):
                    for bin_idx in range(8):
                        rows.append({
                            "animal": animal, "date": date,
                            "side": side,
                            "phase_bin": bin_idx,
                            "phase_bin_center": (bin_idx + 0.5) / 8,
                            "epoch_label": "pre",
                            "recovery_phenotype": "mild",
                            "angle_deg": bin_idx + 0.1,
                            "x_centered": -bin_idx,
                            "angle_deg_delta": 0.0,
                            "x_centered_delta": 0.0,
                        })
        cohort = pd.DataFrame(rows)
        animals = {
            "PS47": _animal_info("PS47", phenotype="mild"),
            "PS48": _animal_info("PS48", phenotype="mild"),
        }
        out = compute_trajectory_bootstrap_pre_ci(
            cohort, animals, signals=("angle_deg",), variants=("raw",),
            n_bootstrap=100, ci=0.95,
        )
        # 1 phen × 2 sides × 1 signal × 1 variant × 8 bins = 16 rows.
        assert len(out) == 16
        for col in (
            "recovery_phenotype", "side", "signal", "variant",
            "phase_bin", "phase_bin_center",
            "mean_ci_lo", "mean_median", "mean_ci_hi",
            "n_animals",
        ):
            assert col in out.columns
        # CI ordering: lo ≤ median ≤ hi.
        assert (out["mean_ci_lo"] <= out["mean_median"]).all()
        assert (out["mean_median"] <= out["mean_ci_hi"]).all()

    def test_invalid_ci_raises(self):
        with pytest.raises(ValueError, match="ci"):
            compute_trajectory_bootstrap_pre_ci(
                pd.DataFrame(), {}, ci=1.5,
            )


class TestComputeTrajectoryBootstrapEffectCi:
    def test_smoke_emits_per_bin_rows_with_ci(self):
        import datetime
        rows = []
        # 2 mild animals × pre + acute sessions × 2 sides × 8 bins.
        for animal in ("PS47", "PS48"):
            for ei, epoch in enumerate(("pre", "acute")):
                for di in range(3):
                    for side in ("L", "R"):
                        for bin_idx in range(8):
                            rows.append({
                                "animal": animal,
                                "date": datetime.date(2025, 3, 1)
                                + datetime.timedelta(days=ei * 30 + di),
                                "side": side,
                                "phase_bin": bin_idx,
                                "phase_bin_center": (bin_idx + 0.5) / 8,
                                "epoch_label": epoch,
                                "recovery_phenotype": "mild",
                                "angle_deg": ei * 2.0 + bin_idx * 0.1,
                                "x_centered": -ei + bin_idx * 0.1,
                                "angle_deg_delta": ei * 2.0,
                                "x_centered_delta": -ei * 1.0,
                            })
        cohort = pd.DataFrame(rows)
        animals = {
            "PS47": _animal_info("PS47", phenotype="mild"),
            "PS48": _animal_info("PS48", phenotype="mild"),
        }
        out = compute_trajectory_bootstrap_effect_ci(
            cohort, animals, signals=("angle_deg",), variants=("raw",),
            n_bootstrap=100,
        )
        # 1 phen × 2 sides × 1 signal × 1 variant × 1 post_epoch
        # (acute, since that's the only post present) × 8 bins = 16 rows.
        assert len(out) == 16
        for col in (
            "recovery_phenotype", "side", "signal", "variant",
            "post_epoch", "phase_bin", "phase_bin_center",
            "effect_median", "effect_ci_lo", "effect_ci_hi",
            "excludes_zero", "n_animals_pre", "n_animals_post",
        ):
            assert col in out.columns
        # CI ordering invariant.
        assert (out["effect_ci_lo"] <= out["effect_median"]).all()
        assert (out["effect_median"] <= out["effect_ci_hi"]).all()
        # Synthetic data: acute = pre + 2 → effect ~= +2 → excludes_zero
        # should be True (lo > 0).
        assert out["excludes_zero"].any()

    def test_invalid_ci_raises(self):
        with pytest.raises(ValueError, match="ci"):
            compute_trajectory_bootstrap_effect_ci(
                pd.DataFrame(), {}, ci=1.5,
            )


class TestTrajectorySubtitleSideOverride:
    """Chore v2 re-emit: subtitle_override + side_display params."""

    def test_subtitle_override_replaces_source_subtitle(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            subtitle_override="V2 FILTERED IPSI CONTRA SUBTITLE",
        )
        assert any(
            "V2 FILTERED IPSI CONTRA SUBTITLE" in t.get_text()
            for t in fig.texts
        )
        plt.close(fig)

    def test_side_display_relabels_title(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
            side_display={"L": "Ipsi (mouse-L)", "R": "Contra (mouse-R)"},
        )
        assert "Ipsi (mouse-L)" in fig._suptitle.get_text()
        assert "side=L" not in fig._suptitle.get_text()
        plt.close(fig)

    def test_defaults_unchanged(self):
        df = _pooled_df()
        fig, _ = build_phase_aligned_trajectory_figure(
            df, signal="angle_deg", variant="raw", side="L",
        )
        assert "side=L" in fig._suptitle.get_text()
        plt.close(fig)
