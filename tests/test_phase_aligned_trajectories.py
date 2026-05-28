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

from stroke_orofacial.figures.palette import (
    PHENOTYPE_ORDER,
    phenotype_display_name,
    phenotype_palette,
)
from stroke_orofacial.figures.phase_aligned_trajectories import (
    EPOCH_DISPLAY_NAMES,
    EPOCH_ORDER,
    FIGURE_SUBDIR,
    FIGURE_SUBTITLE,
    build_phase_aligned_trajectory_figure,
    emit_phase_aligned_trajectory_figures,
    figure_path_for,
    render_phase_aligned_trajectory_figure,
)
from stroke_orofacial.paths import PathResolver


N_PHASE_BINS = 8  # small for tests; production uses 72


def _pooled_df(
    *,
    signals=("angle_deg", "x_centered"),
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


class TestFigurePathFor:
    def test_filename_pattern(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        p = figure_path_for(
            signal="angle_deg", variant="raw", side="L",
            resolver=resolver,
        )
        assert p.name == "angle_deg_raw_L_mean_sem_cleaned_trace.svg"
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
    def test_emits_8_figures_under_force(self, tmp_path):
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        out = emit_phase_aligned_trajectory_figures(
            df, resolver=resolver, overwrite="force",
        )
        assert len(out["emitted"]) == 8
        assert len(out["skipped"]) == 0
        # Confirm filename pattern + on-disk presence.
        names = {p.name for p in out["emitted"]}
        expected_names = {
            f"{signal}_{variant}_{side}_mean_sem_cleaned_trace.svg"
            for signal in ("angle_deg", "x_centered")
            for variant in ("raw", "delta")
            for side in ("L", "R")
        }
        assert names == expected_names

    def test_skip_mode_does_not_overwrite_existing(self, tmp_path):
        df = _pooled_df()
        resolver = PathResolver(output_root=tmp_path)
        # First emit: writes all 8.
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
        assert len(out2["skipped"]) == 8
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
