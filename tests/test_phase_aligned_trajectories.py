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
    SOURCE_DATA_SUBTITLE_DELTA,
    SOURCE_DATA_SUBTITLE_RAW,
    build_phase_aligned_trajectory_figure,
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
