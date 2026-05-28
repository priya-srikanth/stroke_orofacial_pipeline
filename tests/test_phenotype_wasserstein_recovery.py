"""Phase 9.1 Q-lock 12 Addendum #5 — W-2 recovery figure renderer tests."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # noqa: E402

import pandas as pd
import pytest

from stroke_orofacial.figures.palette import PHENOTYPE_ORDER
from stroke_orofacial.figures.phenotype_wasserstein_recovery import (
    EPOCH_DISPLAY_NAMES,
    FIGURE_SUBDIR,
    emit_phenotype_wasserstein_recovery_figures,
    render_phenotype_wasserstein_recovery_figure,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.spatial_proportion_diff import (
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
)


def _full_pooled_w2(
    severity_factors: dict[str, float] | None = None,
) -> dict:
    """Construct one pooled W-2 record per (phenotype × side × bp × epoch).

    Severity-dependent W-2 magnitude so each phenotype line is
    distinguishable on the plot. n_animals=2 per phenotype to give
    finite SEM.
    """
    if severity_factors is None:
        severity_factors = {
            "mild": 1.0, "moderate": 2.0,
            "moderate-severe": 3.0, "severe": 4.0,
        }
    out = {}
    for pheno in PHENOTYPE_ORDER:
        base = severity_factors[pheno]
        for side in SIDES:
            for bp in BODYPART_CENTER_MODES:
                for ep_idx, ep in enumerate(POST_EPOCHS):
                    # Slight recovery: acute > sub_acute > chronic.
                    w2_mean = base * (1.0 - 0.2 * ep_idx)
                    out[(pheno, side, bp, ep)] = {
                        "w2_mean": w2_mean,
                        "w2_sem": 0.1 * base,
                        "w2_per_animal": {
                            "A": w2_mean - 0.1, "B": w2_mean + 0.1,
                        },
                        "n_animals": 2,
                        "contributing_animals": ["A", "B"],
                    }
    return out


# ---------------------------------------------------------------------------
# render_phenotype_wasserstein_recovery_figure
# ---------------------------------------------------------------------------


class TestRenderWasserstein:
    def test_single_axis_figure(self) -> None:
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="tongue", side="L", pooled_w2=recs,
        )
        # One main axis (no per-row panels).
        assert len(fig.axes) == 1

    def test_legend_contains_4_phenotypes(self) -> None:
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="tongue", side="L", pooled_w2=recs,
        )
        legend = fig.axes[0].get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert len(labels) == 4

    def test_3tier_legend_skips_mod_severe(self) -> None:
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="tongue", side="L", pooled_w2=recs,
            phenotype_order=("mild", "moderate", "severe"),
        )
        labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert len(labels) == 3
        assert not any("mod-severe" in lab for lab in labels)

    def test_xticklabels_match_epoch_display_names(self) -> None:
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="tongue", side="L", pooled_w2=recs,
        )
        xtick_labels = [
            t.get_text() for t in fig.axes[0].get_xticklabels()
        ]
        for ep in POST_EPOCHS:
            assert EPOCH_DISPLAY_NAMES[ep] in xtick_labels

    def test_suptitle_includes_bodypart_and_side(self) -> None:
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="jaw", side="R", pooled_w2=recs,
        )
        sup = fig._suptitle.get_text() if fig._suptitle else ""
        assert "jaw" in sup
        assert "side=R" in sup

    def test_per_animal_scatter_underlay_count(self) -> None:
        """Per-animal scatter: 4 phenotypes × 3 epochs × 2 animals = 24
        underlay dots. The errorbar fmt='o-' calls add their own
        marker collections (4 per call × 4 phenotypes = 4 extras),
        so the floor is 24 and the ceiling is 24 + (some matplotlib
        internals). Just verify we have AT LEAST the 24 underlay dots.
        """
        recs = _full_pooled_w2()
        fig = render_phenotype_wasserstein_recovery_figure(
            bodypart="tongue", side="L", pooled_w2=recs,
        )
        n_pts = 0
        for coll in fig.axes[0].collections:
            n_pts += len(coll.get_offsets())
        assert n_pts >= 24, (
            f"expected at least 24 scattered points (4 phenotypes x 3 "
            f"epochs x 2 animals underlay); got {n_pts}"
        )

    def test_invalid_bodypart_raises(self) -> None:
        with pytest.raises(ValueError, match="not in Q12-B scope"):
            render_phenotype_wasserstein_recovery_figure(
                bodypart="nose", side="L", pooled_w2={},
            )


# ---------------------------------------------------------------------------
# emit_phenotype_wasserstein_recovery_figures
# ---------------------------------------------------------------------------


class TestEmitWasserstein:
    def test_emits_4_svgs(self, tmp_path) -> None:
        recs = _full_pooled_w2()
        results = emit_phenotype_wasserstein_recovery_figures(
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
                    f"{bp}_{side}_wasserstein_recovery_cleaned_trace.svg"
                )
                assert target.exists()

    def test_manifest_csv_4_rows(self, tmp_path) -> None:
        recs = _full_pooled_w2()
        results = emit_phenotype_wasserstein_recovery_figures(
            recs,
            resolver=PathResolver(output_root=tmp_path),
            output_dir=tmp_path,
            overwrite="force",
        )
        df = pd.read_csv(results["manifest_csv"])
        assert len(df) == 4
        assert (df["status"] == "OK").all()
        assert set(df.columns) == {"bodypart", "side", "status", "error"}

    def test_prompt_overwrite_raises(self, tmp_path) -> None:
        existing = tmp_path / (
            "tongue_L_wasserstein_recovery_cleaned_trace.svg"
        )
        existing.write_bytes(b"<svg></svg>")
        recs = _full_pooled_w2()
        with pytest.raises(RuntimeError, match="caller must confirm overwrite"):
            emit_phenotype_wasserstein_recovery_figures(
                recs,
                resolver=PathResolver(output_root=tmp_path),
                output_dir=tmp_path,
                overwrite="prompt",
            )


def test_figure_subdir_lock() -> None:
    assert FIGURE_SUBDIR == "stats/figures/phenotype_pooled/wasserstein_recovery"
