"""Phase 9.1 Q-lock 12 Stage 3 — figure renderer tests.

Unit tests for
:mod:`stroke_orofacial.figures.phenotype_pooled_proportion_diff`:
- ``compute_cohort_shared_vmax`` percentile + floor behavior.
- Figure structure: 4×3 grid, expected titles, colorbar present,
  no-data panels handled.
- ``emit_phenotype_pooled_proportion_diff_figures`` overwrite semantics,
  manifest CSV layout, on-disk SVG creation in a tmp_path.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # noqa: E402

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.figures.palette import PHENOTYPE_ORDER
from stroke_orofacial.figures.phenotype_pooled_proportion_diff import (
    EPOCH_DISPLAY_NAMES,
    FIGURE_SUBDIR,
    FIGURE_SUBTITLE_BY_BODYPART,
    SHARED_VMAX_FLOOR,
    compute_cohort_shared_vmax,
    emit_phenotype_pooled_proportion_diff_figures,
    render_phenotype_pooled_proportion_diff_figure,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.spatial_proportion_diff import (
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
)


def _make_pooled(
    phenotype: str, side: str, bodypart: str, post_epoch: str,
    D: np.ndarray,
    *,
    contributing_animals: list[str] | None = None,
    n_pre_trials_per_animal: dict[str, int] | None = None,
    n_post_trials_per_animal: dict[str, int] | None = None,
    extent: list[float] | None = None,
) -> tuple[tuple[str, str, str, str], dict[str, object]]:
    contributing = contributing_animals or ["PS_A"]
    pre_counts = n_pre_trials_per_animal or {a: 100 for a in contributing}
    post_counts = n_post_trials_per_animal or {a: 80 for a in contributing}
    key = (phenotype, side, bodypart, post_epoch)
    rec = {
        "D_mean": D,
        "n_contributing_animals_per_cell": np.where(
            np.isfinite(D), len(contributing), 0,
        ).astype(np.int64),
        "contributing_animals": contributing,
        "n_pre_trials_per_animal": pre_counts,
        "n_post_trials_per_animal": post_counts,
        "extent": extent or [-200.0, 200.0, 50.0, 550.0],
        "n_animals": len(contributing),
    }
    return key, rec


def _full_pooled_records(D_shape: tuple[int, int] = (8, 8)) -> dict:
    """Construct one pooled record per (phenotype × side × bp × epoch).

    Uses small deterministic D arrays scaled by phenotype severity so
    the cohort-wide vmax is non-trivial.
    """
    rng = np.random.default_rng(seed=42)
    records: dict = {}
    severity_scale = {
        "mild": 0.001,
        "moderate": 0.002,
        "moderate-severe": 0.004,
        "severe": 0.008,
    }
    for pheno in PHENOTYPE_ORDER:
        scale = severity_scale[pheno]
        for side in SIDES:
            for bp in BODYPART_CENTER_MODES:
                for ep in POST_EPOCHS:
                    D = rng.normal(0.0, scale, size=D_shape)
                    # Inject a couple of NaN cells per array to exercise
                    # the no-data mask path through the panel renderer.
                    D[0, 0] = np.nan
                    key, rec = _make_pooled(pheno, side, bp, ep, D)
                    records[key] = rec
    return records


# ---------------------------------------------------------------------------
# compute_cohort_shared_vmax
# ---------------------------------------------------------------------------


class TestComputeCohortSharedVmax:
    def test_99th_percentile_across_all_panels(self) -> None:
        recs = {}
        # Two pooled records with deterministic finite values: arr of
        # 0.01 ... 1.00 across 100 cells.
        for i, (pheno, side, bp, ep) in enumerate([
            ("mild", "L", "tongue", "acute"),
            ("severe", "R", "jaw", "chronic"),
        ]):
            D = np.linspace(0.01, 1.0, 100).reshape(10, 10) * (1 if i == 0 else -1)
            key, rec = _make_pooled(pheno, side, bp, ep, D)
            recs[key] = rec
        # |D| across both arrays = linspace(0.01, 1.0, 100), repeated.
        # 99th percentile of that set is ~0.99 (not exactly 0.99 because
        # of the linear-interpolation default).
        vmax = compute_cohort_shared_vmax(recs, percentile=99.0)
        # Expected from np.concatenate of two identical linspace arrays
        # → percentile is the same as a single array, i.e. ~0.9901.
        assert 0.95 <= vmax <= 1.0
        # Strictly positive.
        assert vmax > 0

    def test_returns_floor_on_empty_records(self) -> None:
        vmax = compute_cohort_shared_vmax({})
        assert vmax == SHARED_VMAX_FLOOR

    def test_all_nan_panels_yield_floor(self) -> None:
        key, rec = _make_pooled(
            "mild", "L", "tongue", "acute",
            np.array([[np.nan, np.nan], [np.nan, np.nan]]),
        )
        vmax = compute_cohort_shared_vmax({key: rec})
        assert vmax == SHARED_VMAX_FLOOR

    def test_signed_values_use_abs_magnitude(self) -> None:
        D = np.array([[-0.5, 0.5], [-0.5, 0.5]])
        key, rec = _make_pooled("mild", "L", "tongue", "acute", D)
        vmax = compute_cohort_shared_vmax({key: rec}, percentile=100.0)
        np.testing.assert_allclose(vmax, 0.5, atol=1e-12)


# ---------------------------------------------------------------------------
# render_phenotype_pooled_proportion_diff_figure
# ---------------------------------------------------------------------------


class TestRenderPhenotypePooledProportionDiffFigure:
    def test_4x3_grid_layout(self) -> None:
        recs = _full_pooled_records()
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart="tongue", side="L", pooled_records=recs,
            shared_vmax=0.01,
        )
        # 4 phenotypes × 3 epochs = 12 panels, plus 1 colorbar axis.
        # plt.subplots returns 12 axes; add_axes for the colorbar adds
        # one more.
        assert len(fig.axes) >= 12

    def test_panel_title_includes_phenotype_and_epoch(self) -> None:
        recs = _full_pooled_records()
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart="tongue", side="L", pooled_records=recs,
            shared_vmax=0.01,
        )
        # Collect non-empty axis titles.
        titles = [ax.get_title() for ax in fig.axes if ax.get_title()]
        # At least one panel mentions "Acute"; at least one "Subacute"; one "Chronic".
        for label in ("Acute", "Subacute", "Chronic"):
            assert any(label in t for t in titles), (
                f"no panel title mentions {label!r}; got {titles!r}"
            )

    def test_empty_pool_panel_renders_no_data_text(self) -> None:
        # Build a partial-pool set: missing (mild, L, tongue, acute).
        recs = _full_pooled_records()
        del recs[("mild", "L", "tongue", "acute")]
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart="tongue", side="L", pooled_records=recs,
            shared_vmax=0.01,
        )
        # The (mild, acute) panel should be the top-left of the grid.
        # _render_proportion_diff_panel calls ax.text(...) with "(no data)"
        # or "(no animals contributed)" for None pools.
        all_text = []
        for ax in fig.axes:
            for child in ax.get_children():
                if hasattr(child, "get_text"):
                    txt = child.get_text()
                    if txt:
                        all_text.append(txt)
        # Title now includes "no animals contributed" for the empty panel.
        assert any("no animals contributed" in t for t in all_text), (
            "missing 'no animals contributed' annotation for empty pool"
        )

    def test_suptitle_includes_bodypart_side_and_vmax(self) -> None:
        recs = _full_pooled_records()
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart="jaw", side="R", pooled_records=recs,
            shared_vmax=0.007,
        )
        sup = fig._suptitle.get_text() if fig._suptitle else ""
        assert "jaw" in sup
        assert "side=R" in sup
        assert "0.007" in sup
        # Bodypart-specific source footer (Phase 7e + 7e.4 + Phase 7f for jaw).
        assert FIGURE_SUBTITLE_BY_BODYPART["jaw"] in sup

    def test_invalid_bodypart_raises(self) -> None:
        with pytest.raises(ValueError, match="not in Q12-B scope"):
            render_phenotype_pooled_proportion_diff_figure(
                bodypart="nose", side="L", pooled_records={},
                shared_vmax=0.01,
            )

    def test_invalid_side_raises(self) -> None:
        with pytest.raises(ValueError, match="not in"):
            render_phenotype_pooled_proportion_diff_figure(
                bodypart="tongue", side="C", pooled_records={},
                shared_vmax=0.01,
            )

    def test_panel_annotation_reports_trial_counts(self) -> None:
        """Sample size annotation = n_animals + total_pre_trials + total_post_trials
        across animals in phenotype."""
        D = np.full((4, 4), 0.005)
        key, rec = _make_pooled(
            "mild", "L", "tongue", "acute", D,
            contributing_animals=["PS_A", "PS_B"],
            n_pre_trials_per_animal={"PS_A": 100, "PS_B": 50},
            n_post_trials_per_animal={"PS_A": 80, "PS_B": 40},
        )
        recs = {key: rec}
        fig = render_phenotype_pooled_proportion_diff_figure(
            bodypart="tongue", side="L", pooled_records=recs,
            shared_vmax=0.01,
        )
        titles = [ax.get_title() for ax in fig.axes if ax.get_title()]
        # Annotation: n_animals=2, pre n=150, post n=120.
        target = [t for t in titles if "n_animals=2" in t]
        assert target, f"no panel title with n_animals=2; got {titles!r}"
        assert any("pre n=150" in t for t in target)
        assert any("post n=120" in t for t in target)


# ---------------------------------------------------------------------------
# emit_phenotype_pooled_proportion_diff_figures
# ---------------------------------------------------------------------------


class TestEmitPhenotypePooledProportionDiffFigures:
    def test_emits_4_figures_with_canonical_filenames(self, tmp_path) -> None:
        recs = _full_pooled_records()
        results = emit_phenotype_pooled_proportion_diff_figures(
            recs,
            resolver=PathResolver(output_root=tmp_path),
            output_dir=tmp_path,
            overwrite="force",
        )
        assert set(results["OK"]) == {
            ("tongue", "L"), ("tongue", "R"),
            ("jaw", "L"), ("jaw", "R"),
        }
        for bp in BODYPART_CENTER_MODES:
            for side in SIDES:
                target = tmp_path / (
                    f"{bp}_{side}_proportion_diff_cleaned_trace.svg"
                )
                assert target.exists()

    def test_manifest_csv_columns_and_rows(self, tmp_path) -> None:
        recs = _full_pooled_records()
        results = emit_phenotype_pooled_proportion_diff_figures(
            recs,
            resolver=PathResolver(output_root=tmp_path),
            output_dir=tmp_path,
            overwrite="force",
        )
        manifest_csv = results["manifest_csv"]
        assert manifest_csv.exists()
        df = pd.read_csv(manifest_csv)
        assert set(df.columns) == {"bodypart", "side", "status", "error"}
        assert len(df) == 4
        assert (df["status"] == "OK").all()

    def test_prompt_overwrite_raises_on_existing(self, tmp_path) -> None:
        # Seed a file at one target path.
        existing = tmp_path / (
            "tongue_L_proportion_diff_cleaned_trace.svg"
        )
        existing.write_bytes(b"<svg></svg>")
        recs = _full_pooled_records()
        with pytest.raises(RuntimeError, match="caller must confirm overwrite"):
            emit_phenotype_pooled_proportion_diff_figures(
                recs,
                resolver=PathResolver(output_root=tmp_path),
                output_dir=tmp_path,
                overwrite="prompt",
            )

    def test_skip_overwrite_records_skip(self, tmp_path) -> None:
        existing = tmp_path / (
            "tongue_L_proportion_diff_cleaned_trace.svg"
        )
        existing.write_bytes(b"<svg></svg>")
        recs = _full_pooled_records()
        results = emit_phenotype_pooled_proportion_diff_figures(
            recs,
            resolver=PathResolver(output_root=tmp_path),
            output_dir=tmp_path,
            overwrite="skip",
        )
        assert ("tongue", "L") in results["SKIP"]
        # Other 3 should have emitted.
        assert len(results["OK"]) == 3

    def test_caller_supplied_shared_vmax_overrides(self, tmp_path) -> None:
        recs = _full_pooled_records()
        results = emit_phenotype_pooled_proportion_diff_figures(
            recs,
            resolver=PathResolver(output_root=tmp_path),
            output_dir=tmp_path,
            overwrite="force",
            shared_vmax=0.0123,
        )
        np.testing.assert_allclose(results["shared_vmax"], 0.0123)


# ---------------------------------------------------------------------------
# Module-level lock tests
# ---------------------------------------------------------------------------


def test_figure_subdir_q12_j_lock() -> None:
    """Q12-J revised per Addendum #2 — aligned with q13b stats/figures/phenotype_pooled/."""
    assert FIGURE_SUBDIR == (
        "stats/figures/phenotype_pooled/proportion_diff_heatmaps"
    )


def test_epoch_display_names_capitalization() -> None:
    assert EPOCH_DISPLAY_NAMES == {
        "acute": "Acute",
        "sub_acute": "Subacute",
        "chronic": "Chronic",
    }
