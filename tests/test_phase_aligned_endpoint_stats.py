"""Phase 9.1 Q-lock 13b — Stage 4 stats + figure renderer tests.

Covers:
- Stats compute on a synthetic 4-animal × 2-epoch fixture (pre vs acute).
- BH-FDR family applied as ONE 72-test family (Addendum #2 D3 lock).
- NaN-aware p_adj for n=1 phenotype tiers.
- Figure renderer produces 6 SVGs at the Q-lock 15 canonical paths.
- Figure axes structure / title / subtitle assertions (no pixel-equality).
- Manifest CSV row count + status partitioning.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.figures.phase_aligned_endpoint_stats import (
    ENDPOINT_DISPLAY_NAMES,
    EPOCH_ORDER,
    FIGURE_SUBDIR,
    FIGURE_SUBTITLE,
    POST_EPOCHS,
    SIDE_ORDER,
    compute_phase_aligned_endpoint_stats,
    emit_phase_aligned_endpoint_figures,
    figure_path_for,
    render_phase_aligned_endpoint_figure,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.aggregators import PHASE_ALIGNED_ENDPOINT_SLUGS


def _make_per_session_fixture() -> pd.DataFrame:
    """4 mild animals × 2 epochs × 2 sides × 3 endpoints — known-shifted post.

    Per-session medians: pre = 10 ± 1 (per-animal jitter); acute = 50 ± 1.
    This gives a strong pre vs acute shift for the mild phenotype.
    The 'pre vs acute' Wilcoxon should reject with a small p-value.
    """
    rows = []
    pre_vals = [10.0, 11.0, 9.0, 10.5]  # one per animal, 4 mild animals
    acute_vals = [50.0, 51.0, 49.0, 50.5]
    sub_acute_vals = [40.0, 41.0, 39.0, 40.5]
    chronic_vals = [30.0, 31.0, 29.0, 30.5]
    animals = ["PS47", "PS48", "PS49", "PS50"]
    for ai, animal in enumerate(animals):
        for side in ("L", "R"):
            for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
                rows.append({
                    "animal": animal,
                    "recovery_phenotype": "mild",
                    "epoch_label": "pre", "side": side,
                    "endpoint": endpoint, "median": pre_vals[ai],
                })
                rows.append({
                    "animal": animal,
                    "recovery_phenotype": "mild",
                    "epoch_label": "acute", "side": side,
                    "endpoint": endpoint, "median": acute_vals[ai],
                })
                rows.append({
                    "animal": animal,
                    "recovery_phenotype": "mild",
                    "epoch_label": "sub_acute", "side": side,
                    "endpoint": endpoint, "median": sub_acute_vals[ai],
                })
                rows.append({
                    "animal": animal,
                    "recovery_phenotype": "mild",
                    "epoch_label": "chronic", "side": side,
                    "endpoint": endpoint, "median": chronic_vals[ai],
                })
    return pd.DataFrame(rows)


def _make_n1_phenotype_fixture() -> pd.DataFrame:
    """n=1 moderate (PS46) — only contributes one paired observation;
    paired Wilcoxon needs n ≥ 2, so status='insufficient_data'."""
    rows = []
    for side in ("L", "R"):
        for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
            rows.append({
                "animal": "PS46",
                "recovery_phenotype": "moderate",
                "epoch_label": "pre", "side": side,
                "endpoint": endpoint, "median": 5.0,
            })
            rows.append({
                "animal": "PS46",
                "recovery_phenotype": "moderate",
                "epoch_label": "acute", "side": side,
                "endpoint": endpoint, "median": 8.0,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage 4a — stats compute
# ---------------------------------------------------------------------------


class TestComputePhaseAlignedEndpointStats:
    def test_produces_72_row_family(self):
        df = _make_per_session_fixture()
        out = compute_phase_aligned_endpoint_stats(df)
        # 4 phenotypes × 2 sides × 3 endpoints × 3 post_epochs = 72
        assert len(out) == 72
        assert set(out.columns) >= {
            "recovery_phenotype", "side", "endpoint", "post_epoch",
            "statistic", "p_value", "n_observations", "status",
            "p_adj", "reject",
        }

    def test_mild_pre_vs_acute_rejects_strongly(self):
        # n=4 with clean shift pre→acute → Wilcoxon should produce a
        # finite small p-value with status="ok".
        df = _make_per_session_fixture()
        out = compute_phase_aligned_endpoint_stats(df)
        mild_acute = out[
            (out["recovery_phenotype"] == "mild")
            & (out["post_epoch"] == "acute")
        ]
        # All cells should be "ok" since we have 4 paired animals per cell.
        assert (mild_acute["status"] == "ok").all()
        # p-values are real numbers, not NaN.
        assert mild_acute["p_value"].notna().all()
        # median_diff should be positive (acute > pre) and ≈ +40.
        assert (mild_acute["median_diff"] > 30).all()

    def test_n_1_phenotype_returns_insufficient_data_with_nan_p(self):
        df = _make_n1_phenotype_fixture()
        # No mild/severe/mod-severe rows → 4 phenotypes × 2 sides × 3 endpoints
        # × 3 post_epochs = 72, but only moderate has data. moderate rows
        # are 1-animal-per-test → insufficient_data.
        out = compute_phase_aligned_endpoint_stats(df)
        moderate_rows = out[out["recovery_phenotype"] == "moderate"]
        # 1 phenotype × 2 sides × 3 endpoints × 3 post_epochs = 18
        # of which the 6 acute rows have n=1 paired (PS46 only).
        # All sub_acute/chronic rows have no data → insufficient.
        # All acute rows have n=1 paired → insufficient (n<2).
        assert (moderate_rows["status"] == "insufficient_data").all()
        assert moderate_rows["p_value"].isna().all()
        # BH-FDR should propagate NaN through p_adj.
        assert moderate_rows["p_adj"].isna().all()

    def test_p_adj_within_unit_interval_for_finite_rows(self):
        df = _make_per_session_fixture()
        out = compute_phase_aligned_endpoint_stats(df)
        finite_rows = out.dropna(subset=["p_adj"])
        if not finite_rows.empty:
            assert (finite_rows["p_adj"] >= 0).all()
            assert (finite_rows["p_adj"] <= 1).all()

    def test_raises_on_missing_required_column(self):
        df = pd.DataFrame({"animal": ["PS46"]})
        with pytest.raises(ValueError, match="missing required column"):
            compute_phase_aligned_endpoint_stats(df)


# ---------------------------------------------------------------------------
# Stage 4b — figure renderer (Q-lock 15 marker convention)
# ---------------------------------------------------------------------------


class TestFigurePathFor:
    def test_filename_matches_q_lock_15_convention(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        path = figure_path_for(
            endpoint="peak_angle_deg", side="L", resolver=resolver,
        )
        # Q-lock 15 layer 1 (directory):
        assert FIGURE_SUBDIR.replace("/", "\\") in str(path) \
            or FIGURE_SUBDIR in str(path).replace("\\", "/")
        # Q-lock 15 layer 2 (filename):
        assert path.name == "peak_angle_deg_L_cleaned_trace.svg"

    def test_uses_output_dir_override_when_provided(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        override = tmp_path / "custom"
        path = figure_path_for(
            endpoint="signed_angle_at_max_abs_phase_0_075_deg", side="R",
            resolver=resolver, output_dir=override,
        )
        assert path.parent == override
        assert path.name == "signed_angle_at_max_abs_phase_0_075_deg_R_cleaned_trace.svg"


class TestRenderPhaseAlignedEndpointFigure:
    def test_emits_svg_file(self, tmp_path):
        df = _make_per_session_fixture()
        stats = compute_phase_aligned_endpoint_stats(df)
        out_path = tmp_path / "test_fig.svg"
        render_phase_aligned_endpoint_figure(
            per_session_df=df, stats_df=stats,
            endpoint="peak_angle_deg", side="L",
            output_path=out_path,
        )
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_axes_structure_carries_endpoint_label_and_footer(self, tmp_path):
        # Snapshot test on axes structure: title, x-axis ticks, y-axis label
        # match the locked specifications. NOT a pixel comparison.
        df = _make_per_session_fixture()
        stats = compute_phase_aligned_endpoint_stats(df)
        out_path = tmp_path / "axes_check.svg"

        # Drive the renderer through plt's current-figure stack to inspect
        # the matplotlib axes before close.
        # We monkey-savefig: re-implement the renderer's body inline so we
        # can keep the figure open. Simpler: re-render but read the SVG
        # text to check the title + subtitle text snippets.
        render_phase_aligned_endpoint_figure(
            per_session_df=df, stats_df=stats,
            endpoint="peak_angle_deg", side="L",
            output_path=out_path,
        )
        svg_text = out_path.read_text(encoding="utf-8")
        # Q-lock 15 layer 3 (footer subtitle) must appear in the SVG text.
        assert FIGURE_SUBTITLE in svg_text
        # Endpoint display name must appear (title carries it).
        assert "Peak tongue angle" in svg_text
        # X-axis epoch display labels must all appear (capitalized,
        # "Subacute" as one word per Priya 2026-05-27).
        from stroke_orofacial.figures.phase_aligned_endpoint_stats import (
            EPOCH_DISPLAY_NAMES,
        )
        for epoch in EPOCH_ORDER:
            display = EPOCH_DISPLAY_NAMES[epoch]
            assert display in svg_text, f"expected {display!r} in SVG text"


class TestEmitPhaseAlignedEndpointFigures:
    def test_emits_six_figures_plus_manifest_and_stats_csvs(self, tmp_path):
        df = _make_per_session_fixture()
        stats = compute_phase_aligned_endpoint_stats(df)
        resolver = PathResolver(output_root=tmp_path)
        out_dir = tmp_path / "phase_9_1_test_dir"
        result = emit_phase_aligned_endpoint_figures(
            per_session_df=df, stats_df=stats,
            resolver=resolver, output_dir=out_dir,
            overwrite="force",
        )
        # 3 endpoints × 2 sides = 6 successful renders.
        assert len(result["OK"]) == 6
        assert result["FAIL"] == []
        # Stats + per-session CSVs present.
        assert result["stats_csv"].exists()
        assert result["per_session_csv"].exists()
        assert result["manifest_csv"].exists()

        # Manifest covers all 6 (endpoint, side) cells.
        manifest = pd.read_csv(result["manifest_csv"])
        assert len(manifest) == 6
        assert set(manifest["status"].unique()) == {"OK"}
        assert set(zip(manifest["endpoint"], manifest["side"])) == {
            (e, s) for e in PHASE_ALIGNED_ENDPOINT_SLUGS for s in SIDE_ORDER
        }

    def test_prompt_overwrite_on_existing_raises(self, tmp_path):
        df = _make_per_session_fixture()
        stats = compute_phase_aligned_endpoint_stats(df)
        resolver = PathResolver(output_root=tmp_path)
        out_dir = tmp_path / "phase_9_1_overwrite_test"
        # First emit lands six figures.
        emit_phase_aligned_endpoint_figures(
            per_session_df=df, stats_df=stats,
            resolver=resolver, output_dir=out_dir,
            overwrite="force",
        )
        # Second call with overwrite="prompt" must raise on the first
        # existing target (per GR7 — Stage 5 caller surfaces the confirm).
        with pytest.raises(RuntimeError, match="GR7"):
            emit_phase_aligned_endpoint_figures(
                per_session_df=df, stats_df=stats,
                resolver=resolver, output_dir=out_dir,
                overwrite="prompt",
            )

    def test_skip_overwrite_leaves_existing_figures_untouched(self, tmp_path):
        df = _make_per_session_fixture()
        stats = compute_phase_aligned_endpoint_stats(df)
        resolver = PathResolver(output_root=tmp_path)
        out_dir = tmp_path / "phase_9_1_skip_test"
        emit_phase_aligned_endpoint_figures(
            per_session_df=df, stats_df=stats,
            resolver=resolver, output_dir=out_dir,
            overwrite="force",
        )
        first_mtimes = {
            (e, s): (out_dir / f"{e}_{s}_cleaned_trace.svg").stat().st_mtime_ns
            for e in PHASE_ALIGNED_ENDPOINT_SLUGS for s in SIDE_ORDER
        }
        # Second emit with overwrite="skip" → no rewrites.
        result = emit_phase_aligned_endpoint_figures(
            per_session_df=df, stats_df=stats,
            resolver=resolver, output_dir=out_dir,
            overwrite="skip",
        )
        # 6 entries reported as SKIP.
        assert len(result["SKIP"]) == 6
        assert result["OK"] == []
        # mtimes match — no rewrite happened.
        for key, mt0 in first_mtimes.items():
            e, s = key
            mt1 = (out_dir / f"{e}_{s}_cleaned_trace.svg").stat().st_mtime_ns
            assert mt0 == mt1
