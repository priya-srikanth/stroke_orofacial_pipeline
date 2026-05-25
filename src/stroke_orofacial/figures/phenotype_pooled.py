"""V4 (per_bin curves) + V5 (per_epoch boxplots) phenotype-pooled emitters.

Phase 9.1 Tasks 1a/1b/1c (per Q-lock 10(b): V5 bundled into Task 1, original
Task 2 subsumed). Consumes raw Phase 9 stats input parquets at
``pipeline_outputs/stats/inputs/<endpoint_slug>/<animal>.parquet`` for the 35
LMM-run scalar endpoints pinned at Task 0.5
(``configs/phase_9_1_endpoint_lists/v4_v5_scalar_endpoints.yaml``).

Q-locks:
- Q-lock 1 — 4-tier ``AnimalInfo.recovery_phenotype`` grouping (n=1 tiers
  render as single-animal traces with explicit ``n=1`` annotation).
- Q-lock 2 — V4/V5 = all 35 scalar (non-spatial) LMM-run endpoints.
- Q-lock 4 — ipsi/contra panel labels (mouse-L = ipsi, mouse-R = contra per
  cohort-uniformity caveat).
- Q-lock 5 — outputs under
  ``pipeline_outputs/phase_9_1_figures/phenotype_pooled/<endpoint_slug>/``.
- Q-lock 6 — parameterized ``--endpoint-list`` runner; ``spatial_*`` slugs
  skipped at runner level (V4/V5 scalar-only).
- Q-lock 9 — preview-then-full task structure (Tasks 1a/1b/1c).
- Q-lock 10 — V4/V5 side-split (ipsi vs contra panels); V5 bundled with V4
  in Task 1; raw ``stats/inputs/`` parquets are the data source (not the
  cohort-side-pooled ``stats/results/recovery/`` CSVs). Fallback to
  single-panel cohort-pooled when ``side`` column absent or all-NaN.
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
V5_VARIANT_FILENAME = "v5_per_epoch_phenotype_pooled"

FigureType = Literal["v4", "v5"]


# ---------------------------------------------------------------------------
# V4 — per_bin phenotype-pooled curves
# ---------------------------------------------------------------------------

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

    Side-split per Q-lock 10(a) when the endpoint's stats input parquets
    have a populated ``side`` column; degrades to single-panel cohort-pooled
    per Q-lock 10(c) otherwise.
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

    df = _io.load_stats_inputs(endpoint_slug, resolver)
    if df.empty:
        logger.warning("no stats inputs on disk for endpoint %r; skipping", endpoint_slug)
        return None

    animals = _io.load_cohort_animals()
    has_side = _io.endpoint_has_side(df)
    df = _io.attach_per_bin_columns(df, animals)
    if phenotype_tiers:
        df = df[df["phenotype_tier"].isin(set(phenotype_tiers))]
        if df.empty:
            logger.warning(
                "no rows after phenotype-tier filter for endpoint %r", endpoint_slug,
            )
            return None

    per_animal = _io.per_animal_bin_means(df, by_side=has_side)
    pooled = _io.phenotype_pooled_per_bin(per_animal, by_side=has_side)
    n_by_tier = _count_animals_per_tier(per_animal)

    if has_side:
        fig = _build_v4_side_split_figure(pooled, endpoint_slug, n_by_tier)
    else:
        fig = _build_v4_cohort_pooled_figure(pooled, endpoint_slug, n_by_tier)

    endpoint_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return svg_path, png_path


def _build_v4_side_split_figure(
    pooled: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    """Render V4 with ipsi + contra side-by-side panels (Q-lock 10(a))."""
    fig, ipsi_ax, contra_ax = _layout.phenotype_side_split_panels()
    for side, ax in (("L", ipsi_ax), ("R", contra_ax)):
        side_df = pooled[pooled["side"] == side]
        _draw_v4_traces(ax, side_df)
        _layout.phenotype_panel(
            ax,
            endpoint_slug=endpoint_slug,
            n_by_tier=n_by_tier,
            set_title=False,  # ipsi/contra titles already set
        )
        _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    _layout.apply_side_split_suptitle(fig, endpoint_slug)
    fig.tight_layout()
    return fig


def _build_v4_cohort_pooled_figure(
    pooled: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    """Render V4 single panel — Q-lock 10(c) fallback when side absent."""
    fig, ax = _layout.cohort_pooled_panel()
    _draw_v4_traces(ax, pooled)
    _layout.phenotype_panel(
        ax,
        endpoint_slug=endpoint_slug,
        n_by_tier=n_by_tier,
        set_title=True,
    )
    _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    fig.tight_layout()
    return fig


def _draw_v4_traces(ax, sub: pd.DataFrame) -> None:
    """Draw 4 phenotype traces (mean line + SEM band) onto one axes."""
    for tier in _palette.PHENOTYPE_ORDER:
        tier_df = sub[sub["phenotype_tier"] == tier]
        if tier_df.empty:
            continue
        tier_df = tier_df.sort_values("bin_midpoint_rel_day")
        color = _palette.phenotype_palette(tier)
        ax.plot(
            tier_df["bin_midpoint_rel_day"], tier_df["mean"],
            color=color, marker="o", linewidth=2.0, markersize=4.0,
            label=tier, zorder=3,
        )
        if tier_df["sem"].notna().any():
            ax.fill_between(
                tier_df["bin_midpoint_rel_day"],
                tier_df["mean"] - tier_df["sem"].fillna(0.0),
                tier_df["mean"] + tier_df["sem"].fillna(0.0),
                color=color, alpha=0.25, linewidth=0, zorder=2,
            )


# ---------------------------------------------------------------------------
# V5 — per_epoch phenotype-pooled boxplots
# ---------------------------------------------------------------------------

def emit_v5_per_endpoint(
    endpoint_slug: str,
    resolver: PathResolver,
    *,
    phenotype_tiers: Iterable[str] | None = None,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    dpi: int = 150,
) -> tuple[Path, Path] | None:
    """Emit one V5 phenotype-pooled per_epoch boxplot as SVG + PNG.

    Side-split per Q-lock 10(a); single-panel fallback per Q-lock 10(c).
    Per Phase 9 Addendum #6 the unit of pooling is the per-session value
    within an epoch (NOT per-trial), so this runner aggregates trial-grain
    parquets to per-session means before boxplot rendering.
    """
    if endpoint_slug.startswith("spatial_"):
        logger.warning(
            "skipping spatial endpoint %r in V5 runner (Q-C dedup; route via "
            "phenotype_pooled_spatial)", endpoint_slug,
        )
        return None

    if output_dir is None:
        output_dir = (
            resolver.pipeline_outputs(subdir=PHASE_9_1_FIGURES_SUBDIR)
            / "phenotype_pooled"
        )
    endpoint_dir = output_dir / endpoint_slug
    svg_path = endpoint_dir / f"{V5_VARIANT_FILENAME}.svg"
    png_path = endpoint_dir / f"{V5_VARIANT_FILENAME}.png"

    if overwrite == "skip" and svg_path.exists() and png_path.exists():
        logger.info("skip (exists): %s", svg_path)
        return None

    df = _io.load_stats_inputs(endpoint_slug, resolver)
    if df.empty:
        logger.warning("no stats inputs on disk for endpoint %r; skipping", endpoint_slug)
        return None

    animals = _io.load_cohort_animals()
    has_side = _io.endpoint_has_side(df)
    df = _io.attach_phenotype_column(df, animals)
    if phenotype_tiers:
        df = df[df["phenotype_tier"].isin(set(phenotype_tiers))]
        if df.empty:
            logger.warning(
                "no rows after phenotype-tier filter for endpoint %r", endpoint_slug,
            )
            return None

    per_session = _io.per_session_within_epoch(df, by_side=has_side)
    if per_session.empty:
        logger.warning(
            "no per-session-within-epoch rows for endpoint %r (epoch_label "
            "all missing?); skipping", endpoint_slug,
        )
        return None

    n_by_tier = _count_animals_per_tier(per_session)

    if has_side:
        fig = _build_v5_side_split_figure(per_session, endpoint_slug, n_by_tier)
    else:
        fig = _build_v5_cohort_pooled_figure(per_session, endpoint_slug, n_by_tier)

    endpoint_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return svg_path, png_path


def _build_v5_side_split_figure(
    per_session: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    fig, ipsi_ax, contra_ax = _layout.phenotype_side_split_panels()
    for side, ax in (("L", ipsi_ax), ("R", contra_ax)):
        side_df = per_session[per_session["side"] == side]
        _draw_v5_boxplots(ax, side_df)
        _layout.phenotype_panel(
            ax,
            endpoint_slug=endpoint_slug,
            n_by_tier=n_by_tier,
            xlabel="Epoch",
            set_title=False,
            draw_stroke_onset=False,
        )
        _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    _layout.apply_side_split_suptitle(fig, endpoint_slug)
    fig.tight_layout()
    return fig


def _build_v5_cohort_pooled_figure(
    per_session: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    fig, ax = _layout.cohort_pooled_panel()
    _draw_v5_boxplots(ax, per_session)
    _layout.phenotype_panel(
        ax,
        endpoint_slug=endpoint_slug,
        n_by_tier=n_by_tier,
        xlabel="Epoch",
        set_title=True,
        draw_stroke_onset=False,
    )
    _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    fig.tight_layout()
    return fig


# V5 boxplot layout: epochs along x; phenotypes grouped within each epoch.
# 4 phenotype boxes per epoch, offset by ±_V5_PHENOTYPE_OFFSETS from the
# epoch center so they don't overlap.
_V5_EPOCH_ORDER: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")
_V5_BOX_WIDTH: float = 0.18
_V5_PHENOTYPE_OFFSETS: dict[str, float] = {
    "mild": -0.30,
    "moderate": -0.10,
    "moderate-severe": +0.10,
    "severe": +0.30,
}


def _draw_v5_boxplots(ax, per_session: pd.DataFrame) -> None:
    """Draw phenotype-grouped boxplots: 4 phenotype boxes per epoch position.

    Layout: epochs on x (pre/acute/sub_acute/chronic at positions 0..3); 4
    phenotype boxes per epoch, offset by ±0.30 around the epoch center.
    Whiskers default to matplotlib's 1.5*IQR; outliers = open circles in
    palette color. Box fill at α=0.55; box edge + whisker/cap in palette
    color; median line in dark gray for contrast.
    """
    seen_tiers: set[str] = set()
    for epoch_idx, epoch in enumerate(_V5_EPOCH_ORDER):
        epoch_df = per_session[per_session["epoch_label"] == epoch]
        if epoch_df.empty:
            continue
        for tier in _palette.PHENOTYPE_ORDER:
            tier_df = epoch_df[epoch_df["phenotype_tier"] == tier]
            if tier_df.empty:
                continue
            color = _palette.phenotype_palette(tier)
            x_position = float(epoch_idx) + _V5_PHENOTYPE_OFFSETS[tier]
            box = ax.boxplot(
                tier_df["value"].to_numpy(),
                positions=[x_position],
                widths=_V5_BOX_WIDTH,
                patch_artist=True,
                showfliers=True,
                flierprops=dict(
                    marker="o", markersize=3.0, markerfacecolor="none",
                    markeredgecolor=color, alpha=0.5,
                ),
                medianprops=dict(color="0.15", linewidth=1.5),
                whiskerprops=dict(color=color, linewidth=1.0),
                capprops=dict(color=color, linewidth=1.0),
                manage_ticks=False,
            )
            for patch in box["boxes"]:
                patch.set_facecolor(color)
                patch.set_edgecolor(color)
                patch.set_alpha(0.55)
            # Add a single legend handle per phenotype tier (across the whole
            # ax) so phenotype_legend has something to grab via labels.
            if tier not in seen_tiers:
                ax.plot([], [], color=color, linewidth=6.0, label=tier)
                seen_tiers.add(tier)

    ax.set_xticks(range(len(_V5_EPOCH_ORDER)))
    ax.set_xticklabels(_V5_EPOCH_ORDER)
    ax.set_xlim(-0.6, len(_V5_EPOCH_ORDER) - 0.4)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _count_animals_per_tier(rows: pd.DataFrame) -> dict[str, int]:
    """Return ``{phenotype_tier: n_animals}`` after dedup on (tier, animal)."""
    return (
        rows[["phenotype_tier", "animal"]]
        .drop_duplicates()
        .groupby("phenotype_tier")
        .size()
        .to_dict()
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stroke_orofacial.figures.phenotype_pooled",
        description=(
            "Phase 9.1 V4 + V5 phenotype-pooled emitter. Reads stats inputs "
            "parquets, side-splits + pools by recovery_phenotype tier, writes "
            "SVG + PNG per endpoint per figure type."
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
        "--figure-types", default="v4,v5",
        help='Comma-separated subset of {v4,v5}, default "v4,v5" (both).',
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


def _parse_figure_types(raw: str) -> tuple[FigureType, ...]:
    types = tuple(s.strip() for s in raw.split(",") if s.strip())
    valid = {"v4", "v5"}
    for t in types:
        if t not in valid:
            raise SystemExit(
                f"--figure-types: unknown figure type {t!r}; expected v4 and/or v5",
            )
    return types  # type: ignore[return-value]


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

    figure_types = _parse_figure_types(args.figure_types)

    resolver = PathResolver()
    n_emitted = 0
    n_missing = 0
    for slug in slugs:
        any_emitted = False
        if "v4" in figure_types:
            result = emit_v4_per_endpoint(
                slug, resolver,
                phenotype_tiers=tiers,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                dpi=args.dpi,
            )
            if result is not None:
                svg, png = result
                logger.info("emit V4 %s + %s", svg, png.name)
                n_emitted += 1
                any_emitted = True
        if "v5" in figure_types:
            result = emit_v5_per_endpoint(
                slug, resolver,
                phenotype_tiers=tiers,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                dpi=args.dpi,
            )
            if result is not None:
                svg, png = result
                logger.info("emit V5 %s + %s", svg, png.name)
                n_emitted += 1
                any_emitted = True
        if not any_emitted:
            n_missing += 1

    logger.info(
        "done. emitted=%d missing/no-data=%d total_endpoints=%d figure_types=%s",
        n_emitted, n_missing, len(slugs), figure_types,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
