"""Tests for Phase 8a.10 CG-5 cohort-summary tiler
(``stroke_orofacial.spout_behavior.cohort_summary``).

Covers ``make_summary_figures`` + ``make_summary_folder_name`` +
``_grid``. Builds tiny per-mouse PNGs in tmp ``visual_gate_dir``, runs
the tiler, asserts output paths + tile dimensions + skip-set behavior +
missing-PNG placeholder fallback.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.spout_behavior import cohort_summary  # noqa: E402
from stroke_orofacial.spout_behavior.cohort_summary import (  # noqa: E402
    _grid,
    make_summary_figures,
    make_summary_folder_name,
)


# ---- Helpers ----


def _write_per_animal_png(
    resolver: PathResolver, animal: str, family: str, suffix: str = "_relStroke",
) -> None:
    """Write a tiny synthetic PNG at the resolver's visual_gate_dir(animal)
    location to stand in for a CG-2/3/4-rendered per-mouse plot."""
    out_dir = resolver.visual_gate_dir(animal)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(2, 1))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_title(f"{animal} {family}")
    fig.savefig(out_dir / f"{family}{suffix}.png", dpi=72)
    plt.close(fig)


# ---- _grid + folder-name ----


class TestGridDimensions:
    @pytest.mark.parametrize("n,expected", [
        (1, (1, 1)),
        (4, (2, 2)),
        (8, (3, 3)),    # 8 animals → 3×3 (1 empty cell). Phase 8a.10 cohort default.
        (9, (3, 3)),    # exact square
        (10, (3, 4)),   # ceil(sqrt(10))=4 cols; ceil(10/4)=3 rows (2 empty)
        (12, (3, 4)),   # ceil(sqrt(12))=4; 12/4=3 rows (0 empty)
        (16, (4, 4)),   # exact square
    ])
    def test_near_square_layout(self, n, expected):
        assert _grid(n) == expected


class TestMakeSummaryFolderName:
    def test_default_format(self):
        assert make_summary_folder_name(["PS46", "PS47"]) == "summary_PS46_PS47"

    def test_full_phase_8a_10_cohort(self):
        cohort = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
        assert make_summary_folder_name(cohort) == (
            "summary_PS46_PS47_PS48_PS49_PS50_PS51_PS54_PS55"
        )


# ---- make_summary_figures: integration ----


@pytest.fixture
def two_animal_cohort(tmp_path):
    """Synthetic 2-animal cohort with per-mouse PNGs for 3 plot
    families. Returns (resolver, animals, plot_families)."""
    resolver = PathResolver(output_root=tmp_path)
    animals = ["PS46", "PS47"]
    families = ["criteria_performance", "accuracy_firstCorrectLick", "lickiness_bySession"]
    for animal in animals:
        for family in families:
            _write_per_animal_png(resolver, animal, family, suffix="_relStroke")
    return resolver, animals, families


class TestMakeSummaryFigures:
    def test_returns_output_dir_path(self, two_animal_cohort):
        resolver, animals, families = two_animal_cohort
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=families, align_to_stroke=True,
        )
        assert out_dir == resolver.visual_gate_summary_dir(
            "summary_PS46_PS47",
        )
        assert out_dir.exists() and out_dir.is_dir()

    def test_emits_both_svg_and_png_per_family(self, two_animal_cohort):
        resolver, animals, families = two_animal_cohort
        out_dir = make_summary_figures(
            animals, resolver, plot_families=families, align_to_stroke=True,
        )
        for family in families:
            svg = out_dir / f"{family}_relStroke.svg"
            png = out_dir / f"{family}_relStroke.png"
            assert svg.exists() and svg.stat().st_size > 0, f"missing svg for {family}"
            assert png.exists() and png.stat().st_size > 0, f"missing png for {family}"

    def test_absdate_suffix_when_unaligned(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        animals = ["PS46"]
        for family in ["criteria_performance"]:
            _write_per_animal_png(resolver, "PS46", family, suffix="_absDate")
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=["criteria_performance"],
            align_to_stroke=False,
        )
        assert (out_dir / "criteria_performance_absDate.svg").exists()
        assert (out_dir / "criteria_performance_absDate.png").exists()

    def test_respects_skip_set(self, two_animal_cohort):
        """Even when caller passes a family in plot_families, the
        skip_plots set wins (legacy DEFAULT_SKIP semantic)."""
        resolver, animals, _ = two_animal_cohort
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=["criteria_performance", "lick_raster"],
            skip_plots={"lick_raster"},
            align_to_stroke=True,
        )
        assert (out_dir / "criteria_performance_relStroke.svg").exists()
        assert not (out_dir / "lick_raster_relStroke.svg").exists()

    def test_default_skip_includes_lick_raster(self, two_animal_cohort):
        """Legacy DEFAULT_SKIP = {"lick_raster"} carried into the new
        pipeline via visual_gate.summary_skip_plots config."""
        resolver, animals, _ = two_animal_cohort
        # Even with lick_raster in the explicit plot_families, skip_plots
        # default from config should drop it.
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=["criteria_performance", "lick_raster"],
            align_to_stroke=True,
        )
        assert (out_dir / "criteria_performance_relStroke.svg").exists()
        assert not (out_dir / "lick_raster_relStroke.svg").exists()

    def test_handles_missing_png_via_placeholder(self, tmp_path):
        """Missing per-animal PNG → tile cell shows MISSING text;
        composite figure still emits."""
        resolver = PathResolver(output_root=tmp_path)
        animals = ["PS46", "PS47"]
        # Only write the PS46 PNG; PS47 missing.
        _write_per_animal_png(resolver, "PS46", "criteria_performance")
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=["criteria_performance"],
            align_to_stroke=True,
        )
        # The summary still emits (legacy: placeholder text, not skip).
        svg = out_dir / "criteria_performance_relStroke.svg"
        assert svg.exists()
        svg_text = svg.read_text(encoding="utf-8")
        assert "MISSING" in svg_text
        assert "PS47" in svg_text

    def test_default_plot_families_from_config(self, tmp_path):
        """plot_families=None → reads from visual_gate.summary_default_plots."""
        resolver = PathResolver(output_root=tmp_path)
        animals = ["PS46"]
        # Write a PNG for every default plot family so the tiler doesn't
        # warn-per-family. Pull list from the real config.
        from stroke_orofacial.spout_behavior.visual_gate import load_visual_gate_config
        cfg = load_visual_gate_config()
        default_families = list(cfg["summary_default_plots"])
        for family in default_families:
            _write_per_animal_png(resolver, "PS46", family)
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=None,  # → defaults
            align_to_stroke=True,
        )
        # All default families emitted (none of them in default skip
        # set, by construction).
        for family in default_families:
            assert (out_dir / f"{family}_relStroke.svg").exists(), (
                f"default family {family} not emitted"
            )

    def test_default_output_dir_name(self, two_animal_cohort):
        """output_dir_name=None → make_summary_folder_name(animals)."""
        resolver, animals, families = two_animal_cohort
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=families, align_to_stroke=True,
        )
        assert out_dir.name == "summary_PS46_PS47"

    def test_explicit_output_dir_name_override(self, two_animal_cohort):
        resolver, animals, families = two_animal_cohort
        out_dir = make_summary_figures(
            animals, resolver,
            plot_families=families,
            output_dir_name="my_cohort_summary",
            align_to_stroke=True,
        )
        assert out_dir.name == "my_cohort_summary"

    def test_overwrite_raise_blocks_existing(self, two_animal_cohort):
        resolver, animals, families = two_animal_cohort
        # First call to populate.
        make_summary_figures(
            animals, resolver, plot_families=families[:1],
            align_to_stroke=True, overwrite="force",
        )
        # Second call with raise → FileExistsError.
        with pytest.raises(FileExistsError, match="cohort-summary target exists"):
            make_summary_figures(
                animals, resolver, plot_families=families[:1],
                align_to_stroke=True, overwrite="raise",
            )

    def test_overwrite_force_default(self, two_animal_cohort):
        resolver, animals, families = two_animal_cohort
        # Two consecutive calls under force → both succeed; final file
        # exists with non-zero size.
        make_summary_figures(
            animals, resolver, plot_families=families[:1],
            align_to_stroke=True, overwrite="force",
        )
        out_dir = make_summary_figures(
            animals, resolver, plot_families=families[:1],
            align_to_stroke=True, overwrite="force",
        )
        assert (out_dir / f"{families[0]}_relStroke.svg").stat().st_size > 0


class TestModuleExports:
    @pytest.mark.parametrize("name", [
        "make_summary_figures",
        "make_summary_folder_name",
        "_grid",
    ])
    def test_symbol_exists(self, name):
        assert hasattr(cohort_summary, name), (
            f"cohort_summary.{name} missing — CG-5 public surface"
        )
