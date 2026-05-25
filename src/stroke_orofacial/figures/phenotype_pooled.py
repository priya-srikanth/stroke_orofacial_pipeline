"""V4 (per_bin curves) + V5 (per_epoch boxplots) phenotype-pooled figure emitters.

Phase 9.1 Tasks 1-2. Consumes Phase 9 stats input parquets at
``pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet`` for the 35
LMM-run scalar endpoints pinned at Task 0.5
(``configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml``).

Q-locks:
- Q-lock 1 — 4-tier ``AnimalInfo.recovery_phenotype`` grouping (n=1 tiers
  render as single-animal traces with explicit ``n=1`` annotation).
- Q-lock 2 — V4/V5 = all 35 scalar (non-spatial) LMM-run endpoints.
- Q-lock 5 — outputs under
  ``pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/``.
- Q-lock 6 — parameterized ``--endpoint-list`` runner; ``spatial_*`` slugs
  skipped at runner level (V4/V5 scalar-only).
- Q-lock 9 — preview-then-full task structure (Tasks 1a/1b/1c and 2a/2b/2c).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd

from stroke_orofacial.paths import PathResolver

from . import _io, _layout, palette as _palette

logger = logging.getLogger(__name__)

# Phase 9.1 Q-lock 5 output subtree under pipeline_outputs.
PHASE_9_1_FIGURES_SUBDIR = "phase_9_1_figures"
V4_VARIANT_FILENAME = "v4_per_bin_phenotype_pooled"


def emit_v4_per_endpoint(
    endpoint_slug: str,
    resolver: PathResolver,
    *,
    phenotype_tiers: Iterable[str] | None = None,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    dpi: int = 150,
) -> tuple[Path, Path] | None:
    """Emit one V4 phenotype-pooled per_bin recovery curve as SVG + PNG.

    Loads per-animal stats input parquets for ``endpoint_slug``, computes
    per-(animal, bin_midpoint_rel_day) means, then pools across animals
    within each phenotype tier to mean ± SEM. One panel; multiple traces
    (one per requested phenotype tier).

    Parameters
    ----------
    endpoint_slug : str
        Endpoint identifier (e.g. ``"first_lick_accuracy_all"``). Must NOT
        start with ``"spatial_"`` — those route through
        :mod:`stroke_orofacial.figures.phenotype_pooled_spatial` per Q-C dedup.
    resolver : PathResolver
        Provides the ``pipeline_outputs(subdir="stats")`` source root and the
        ``pipeline_outputs(subdir="phase_9_1_figures")`` output root.
    phenotype_tiers : iterable of str, optional
        Subset of ``{"mild", "moderate", "moderate-severe", "severe"}`` to
        include. Default = all 4 (Q-lock 1).
    output_dir : Path, optional
        Override the default output directory. Default =
        ``<output_root>/phase_9_1_figures/phenotype_pooled``.
    overwrite : {"skip", "force"}, optional
        Skip writes if either SVG or PNG already exists (``"skip"``, default)
        or always overwrite (``"force"``).
    dpi : int, optional
        PNG export DPI (SVG is vector).

    Returns
    -------
    tuple[Path, Path] or None
        ``(svg_path, png_path)`` on emit; ``None`` if skipped or the endpoint
        has no data on disk.
    """
    if endpoint_slug.startswith("spatial_"):
        logger.warning(
            "skipping spatial endpoint %r in V4 runner (Q-C dedup; route via "
            "phenotype_pooled_spatial)", endpoint_slug,
        )
        return None

    if output_dir is None:
        output_dir = (
            resolver.pipeline_outputs(subdir=PHASE_9_1_FIGURES_SUBDIR)
            / "phenotype_pooled"
        )
    endpoint_dir = output_dir / endpoint_slug
    svg_path = endpoint_dir / f"{V4_VARIANT_FILENAME}.svg"
    png_path = endpoint_dir / f"{V4_VARIANT_FILENAME}.png"

    if overwrite == "skip" and svg_path.exists() and png_path.exists():
        logger.info("skip (exists): %s", svg_path)
        return None

    # Load + aggregate.
    df = _io.load_stats_inputs(endpoint_slug, resolver)
    if df.empty:
        logger.warning("no stats inputs on disk for endpoint %r; skipping", endpoint_slug)
        return None

    animals = _io.load_cohort_animals()
    df = _io.attach_per_bin_columns(df, animals)
    per_animal = _io.per_animal_bin_means(df)
    pooled = _io.phenotype_pooled_per_bin(per_animal)

    tiers_filter = set(phenotype_tiers) if phenotype_tiers else None
    if tiers_filter is not None:
        pooled = pooled[pooled["phenotype_tier"].isin(tiers_filter)]
        per_animal = per_animal[per_animal["phenotype_tier"].isin(tiers_filter)]

    if pooled.empty:
        logger.warning(
            "no rows after phenotype-tier filter for endpoint %r; tiers=%r",
            endpoint_slug, list(tiers_filter) if tiers_filter else "(all)",
        )
        return None

    n_by_tier = _count_animals_per_tier(per_animal)

    fig = _build_v4_figure(pooled, endpoint_slug, n_by_tier)
    endpoint_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return svg_path, png_path


def _count_animals_per_tier(per_animal: pd.DataFrame) -> dict[str, int]:
    """Return ``{phenotype_tier: n_animals}`` after dedup on (tier, animal)."""
    return (
        per_animal[["phenotype_tier", "animal"]]
        .drop_duplicates()
        .groupby("phenotype_tier")
        .size()
        .to_dict()
    )


def _build_v4_figure(
    pooled: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    """Render one V4 panel: per-phenotype mean ± SEM vs bin_midpoint_rel_day."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.0))

    for tier in _palette.PHENOTYPE_ORDER:
        sub = pooled[pooled["phenotype_tier"] == tier]
        if sub.empty:
            continue
        sub = sub.sort_values("bin_midpoint_rel_day")
        color = _palette.phenotype_palette(tier)
        ax.plot(
            sub["bin_midpoint_rel_day"], sub["mean"],
            color=color, marker="o", linewidth=2.0, markersize=4.0,
            label=tier, zorder=3,
        )
        if sub["sem"].notna().any():
            ax.fill_between(
                sub["bin_midpoint_rel_day"],
                sub["mean"] - sub["sem"].fillna(0.0),
                sub["mean"] + sub["sem"].fillna(0.0),
                color=color, alpha=0.25, linewidth=0, zorder=2,
            )

    _layout.phenotype_panel(
        ax,
        endpoint_slug=endpoint_slug,
        n_by_tier=n_by_tier,
    )
    _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stroke_orofacial.figures.phenotype_pooled",
        description=(
            "Phase 9.1 V4 phenotype-pooled per_bin recovery-curve emitter. "
            "Reads stats inputs parquets, pools by recovery_phenotype tier, "
            "writes SVG + PNG per endpoint."
        ),
    )
    parser.add_argument(
        "--endpoint-list", type=Path, required=True,
        help="Path to a txt file with one endpoint slug per line "
             "(comments + blank lines ignored). Q-lock 6 parameterization.",
    )
    parser.add_argument(
        "--phenotype-tiers", default="all",
        help='Comma-separated subset of {mild,moderate,moderate-severe,severe}, '
             'or "all" (default).',
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override default output dir "
             "(<pipeline_outputs>/phase_9_1_figures/phenotype_pooled).",
    )
    parser.add_argument(
        "--overwrite", choices=("skip", "force"), default="skip",
        help='Skip emit if SVG+PNG already exist ("skip", default) or '
             'always re-emit ("force").',
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="PNG export DPI (default 150).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    slugs = _io.load_endpoint_list(args.endpoint_list)
    if not slugs:
        logger.error("endpoint list at %s is empty", args.endpoint_list)
        return 2

    if args.phenotype_tiers == "all":
        tiers: Iterable[str] | None = None
    else:
        tiers = [s.strip() for s in args.phenotype_tiers.split(",") if s.strip()]

    resolver = PathResolver()
    n_emitted = 0
    n_skipped = 0
    n_missing = 0
    for slug in slugs:
        result = emit_v4_per_endpoint(
            slug, resolver,
            phenotype_tiers=tiers,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            dpi=args.dpi,
        )
        if result is None:
            n_missing += 1
            continue
        svg, png = result
        logger.info("emit %s + %s", svg, png.name)
        n_emitted += 1

    logger.info(
        "done. emitted=%d skipped=%d missing/no-data=%d total_endpoints=%d",
        n_emitted, n_skipped, n_missing, len(slugs),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
