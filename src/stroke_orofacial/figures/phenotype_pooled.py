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
  ``pipeline_outputs/stats/figures/phenotype_pooled/<endpoint_slug>/``.
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
from typing import Any, Iterable, Literal

import pandas as pd

from stroke_orofacial.paths import PathResolver

from . import _io, _layout, palette as _palette
from ._line_with_jitter_dots import (
    AGGREGATION_SUBTITLE,
    render_line_with_jitter_dots,
)

logger = logging.getLogger(__name__)

# Phase 9.1 Q-lock 5 output subtree under pipeline_outputs.
PHASE_9_1_FIGURES_SUBDIR = "stats/figures"
V4_VARIANT_FILENAME = "v4_per_bin_phenotype_pooled"
V5_VARIANT_FILENAME = "v5_per_epoch_phenotype_pooled"

# Q-lock 14 split-key hardening (Addendum #1 §5): pool + split the side-
# stratified panels on the lesion-relative ``ipsi_contra`` column rather than
# raw rig-frame ``side`` (L/R). For the current all-L cohort this is a provable
# no-op (L↔ipsi, R↔contra per animal); it becomes the scientifically-correct
# pooling the moment a right-stroke animal joins (its mouse-L = contra would
# otherwise pool against left-stroke animals' mouse-L = ipsi). Panels still
# read "Ipsi (mouse-L)" / "Contra (mouse-R)" for the all-L cohort.
_SIDE_SPLIT_COL = "ipsi_contra"
_IPSI_CONTRA_PANELS: tuple[str, ...] = ("ipsi", "contra")

# 3-tier phenotype collapse (Q-lock 14, Addendum #1 §8 / Q14-D). Merges
# moderate-severe INTO moderate, matching the established convention in the
# Q12/Q13 emitters (PHENOTYPE_REMAP_3TIER). The DATA collapse lives here; the
# OUTPUT-PATH scope (``3_tier`` vs ``4_tier`` subdir) is owned by
# ``_layout.pooled_scalar_endpoint_dir`` — the writer emits the canonical
# ``<endpoint>/<scope>/[no_filter/]`` layout directly (2026-05-31, the legacy
# flat / ``3_phenotype/`` layout + post-emit path_normalization step retired).
_THREE_TIER_REMAP: dict[str, str] = {"moderate-severe": "moderate"}


def _maybe_remap_3tier(df: "pd.DataFrame", remap_3tier: bool) -> "pd.DataFrame":
    """Merge moderate-severe → moderate in the phenotype_tier column (3-tier)."""
    if remap_3tier and "phenotype_tier" in df.columns:
        df = df.copy()
        df["phenotype_tier"] = df["phenotype_tier"].replace(_THREE_TIER_REMAP)
    return df

FigureType = Literal["v4", "v5"]


# ---------------------------------------------------------------------------
# V4 — per_bin phenotype-pooled curves
# ---------------------------------------------------------------------------

def _apply_aggregation_footer(fig: Any, subtitle: str | None) -> None:
    """Stamp the canonical aggregation-method footer at the figure bottom-left.

    Chore ``vChore-dlc-pooled-phenotype-unification``: the V4/V5 phenotype-
    pooled scalar figures use mean ± SEM session-pooling, so they carry the
    same aggregation-method footer line as the DLC v2 re-emits. No-op when
    ``subtitle`` is None.
    """
    if subtitle:
        fig.text(0.01, 0.005, subtitle, fontsize=7, va="bottom", ha="left")


def emit_v4_per_endpoint(
    endpoint_slug: str,
    resolver: PathResolver,
    *,
    phenotype_tiers: Iterable[str] | None = None,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    dpi: int = 150,
    remap_3tier: bool = False,
    filter_variant: str = "none",
    aggregation_subtitle: str | None = AGGREGATION_SUBTITLE,
) -> tuple[Path, Path] | None:
    """Emit one V4 phenotype-pooled per_bin recovery curve as SVG + PNG.

    Side-split per Q-lock 10(a) when the endpoint's stats input parquets
    have a populated ``side`` column; degrades to single-panel cohort-pooled
    per Q-lock 10(c) otherwise.

    When ``remap_3tier`` is True, moderate-severe is merged into moderate
    (3-tier collapse) and output routes to the ``<endpoint>/3_tier/`` scope
    subdir (``4_tier`` otherwise); the ``no_filter/`` layer is added for
    DLC-filterable scalars per :func:`_layout.pooled_scalar_endpoint_dir`.
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
    endpoint_dir = _layout.pooled_scalar_endpoint_dir(
        output_dir, endpoint_slug,
        remap_3tier=remap_3tier,
        filtered_slugs=_layout.load_filtered_slugs(resolver),
        filter_variant=filter_variant,
    )
    svg_path = endpoint_dir / f"{V4_VARIANT_FILENAME}.svg"
    png_path = endpoint_dir / f"{V4_VARIANT_FILENAME}.png"

    if overwrite == "skip" and svg_path.exists() and png_path.exists():
        logger.info("skip (exists): %s", svg_path)
        return None

    df = _io.load_stats_inputs(endpoint_slug, resolver, filter_variant=filter_variant)
    if df.empty:
        logger.warning("no stats inputs on disk for endpoint %r; skipping", endpoint_slug)
        return None

    animals = _io.load_cohort_animals()
    has_side = _io.endpoint_has_side(df)
    df = _io.attach_per_bin_columns(df, animals)
    df = _maybe_remap_3tier(df, remap_3tier)
    if phenotype_tiers:
        df = df[df["phenotype_tier"].isin(set(phenotype_tiers))]
        if df.empty:
            logger.warning(
                "no rows after phenotype-tier filter for endpoint %r", endpoint_slug,
            )
            return None

    per_animal = _io.per_animal_bin_means(
        df, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )
    pooled = _io.phenotype_pooled_per_bin(
        per_animal, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )
    n_by_tier = _count_animals_per_tier(per_animal)

    if has_side:
        fig = _build_v4_side_split_figure(pooled, endpoint_slug, n_by_tier)
    else:
        fig = _build_v4_cohort_pooled_figure(pooled, endpoint_slug, n_by_tier)

    _apply_aggregation_footer(fig, aggregation_subtitle)
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
    display_name, short_y_label = _layout.get_endpoint_labels(endpoint_slug)
    fig, ipsi_ax, contra_ax = _layout.phenotype_side_split_panels()
    for ic, ax in zip(_IPSI_CONTRA_PANELS, (ipsi_ax, contra_ax)):
        side_df = pooled[pooled[_SIDE_SPLIT_COL] == ic]
        _draw_v4_traces(ax, side_df, pad_y=False)
        _layout.phenotype_panel(
            ax,
            endpoint_slug=endpoint_slug,
            n_by_tier=n_by_tier,
            ylabel=short_y_label,
            set_title=False,  # ipsi/contra titles already set
        )
        _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    # Shared (sharey) y-range = union over BOTH panels, set once after both
    # are drawn (fixes the per-panel expand_y_axis sharey-clip bug).
    yr = _side_split_yrange(pooled["mean"], pooled["sem"])
    if yr is not None:
        ipsi_ax.set_ylim(*yr)
    # V4 plots cohort recovery curves; not baseline-subtracted, so no
    # italic subheading. Suptitle = display_name only.
    _layout.apply_side_split_suptitle(
        fig, endpoint_slug, baseline_subtracted=False,
    )
    _layout.apply_top_room(fig)
    return fig


def _build_v4_cohort_pooled_figure(
    pooled: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    """Render V4 single panel — Q-lock 10(c) fallback when side absent."""
    display_name, short_y_label = _layout.get_endpoint_labels(endpoint_slug)
    fig, ax = _layout.cohort_pooled_panel()
    _draw_v4_traces(ax, pooled)
    _layout.phenotype_panel(
        ax,
        endpoint_slug=endpoint_slug,
        n_by_tier=n_by_tier,
        ylabel=short_y_label,
        set_title=False,  # suptitle owns the title
    )
    _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    _layout.apply_figure_suptitle(
        fig, display_name, baseline_subtracted=False,
    )
    _layout.apply_top_room(fig)
    return fig


def _side_split_yrange(
    means: "pd.Series", sems: "pd.Series", extra: "pd.Series | None" = None,
) -> tuple[float, float] | None:
    """Union padded y-range over mean±SEM (and optional per-session deltas).

    Computed across BOTH ipsi+contra panels (the caller passes the full,
    not side-filtered, frames) so the shared y-axis fits every panel.
    """
    lo = (means - sems.fillna(0.0)).tolist()
    hi = (means + sems.fillna(0.0)).tolist()
    vals = lo + hi
    if extra is not None:
        vals += extra.tolist()
    return _layout.padded_range(vals)


def _draw_v4_traces(ax, sub: pd.DataFrame, *, pad_y: bool = True) -> None:
    """Draw 4 phenotype traces (mean line + SEM band) onto one axes.

    ``pad_y`` (default True) applies the single-panel :func:`expand_y_axis`.
    Side-split callers pass ``pad_y=False`` and set a shared union range after
    both panels are drawn (avoids the sharey-clip bug).
    """
    for tier in _palette.PHENOTYPE_ORDER:
        tier_df = sub[sub["phenotype_tier"] == tier]
        if tier_df.empty:
            continue
        tier_df = tier_df.sort_values("bin_midpoint_rel_day")
        color = _palette.phenotype_palette(tier)
        marker = _palette.phenotype_marker(tier)
        ax.plot(
            tier_df["bin_midpoint_rel_day"], tier_df["mean"],
            color=color, marker=marker, linewidth=2.0, markersize=5.0,
            label=tier, zorder=3,
        )
        if tier_df["sem"].notna().any():
            ax.fill_between(
                tier_df["bin_midpoint_rel_day"],
                tier_df["mean"] - tier_df["sem"].fillna(0.0),
                tier_df["mean"] + tier_df["sem"].fillna(0.0),
                color=color, alpha=0.25, linewidth=0, zorder=2,
            )
    if pad_y:
        _layout.expand_y_axis(ax)


# ---------------------------------------------------------------------------
# V5 — per_epoch phenotype-pooled delta line + scatter underlay (Q-lock 11)
# ---------------------------------------------------------------------------

# 4 epochs along x at positions 0..3. Phenotype lines run THROUGH each
# epoch position (no horizontal offset — overlapping points + lines stay
# vertically distinguishable by color/SEM). Scatter underlay applies a
# small jitter ±_V5_JITTER_WIDTH around each epoch x-position to defang
# overplotting at identical x.
_V5_EPOCH_ORDER: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")
_V5_JITTER_WIDTH: float = 0.15


def emit_v5_per_endpoint(
    endpoint_slug: str,
    resolver: PathResolver,
    *,
    phenotype_tiers: Iterable[str] | None = None,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    dpi: int = 150,
    remap_3tier: bool = False,
    filter_variant: str = "none",
    aggregation_subtitle: str | None = AGGREGATION_SUBTITLE,
) -> tuple[Path, Path] | None:
    """Emit one V5 phenotype-pooled per_epoch delta line as SVG + PNG.

    Q-lock 11 — delta-from-baseline (per-animal pre-epoch mean) line plot
    with faded per-session scatter underlay. Side-split per Q-lock 10(a);
    single-panel fallback per Q-lock 10(c).

    Pipeline:
    1. Load raw stats input parquets.
    2. Compute per-(animal[, side]) baseline mean from pre-epoch rows.
    3. Collapse to per-(animal, date[, side], epoch) means; subtract
       baseline to get ``delta_value`` per session.
    4. Pool deltas across (animal, session) within (phenotype[, side],
       epoch) to mean ± SEM.
    5. Render: phenotype-colored line connectors with SEM bars across
       the 4 epoch positions (foreground); per-session jittered scatter
       at α≈0.25 (background); y=0 reference at zorder=0.
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
    endpoint_dir = _layout.pooled_scalar_endpoint_dir(
        output_dir, endpoint_slug,
        remap_3tier=remap_3tier,
        filtered_slugs=_layout.load_filtered_slugs(resolver),
        filter_variant=filter_variant,
    )
    svg_path = endpoint_dir / f"{V5_VARIANT_FILENAME}.svg"
    png_path = endpoint_dir / f"{V5_VARIANT_FILENAME}.png"

    if overwrite == "skip" and svg_path.exists() and png_path.exists():
        logger.info("skip (exists): %s", svg_path)
        return None

    df = _io.load_stats_inputs(endpoint_slug, resolver, filter_variant=filter_variant)
    if df.empty:
        logger.warning("no stats inputs on disk for endpoint %r; skipping", endpoint_slug)
        return None

    animals = _io.load_cohort_animals()
    has_side = _io.endpoint_has_side(df)
    df = _io.attach_phenotype_column(df, animals)
    df = _maybe_remap_3tier(df, remap_3tier)
    if phenotype_tiers:
        df = df[df["phenotype_tier"].isin(set(phenotype_tiers))]
        if df.empty:
            logger.warning(
                "no rows after phenotype-tier filter for endpoint %r", endpoint_slug,
            )
            return None

    # Q-lock 11 pipeline: baseline → per-session → delta → phenotype-pool.
    baseline = _io.per_animal_side_baseline(
        df, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )
    per_session = _io.per_session_within_epoch(
        df, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )
    sessions_with_delta = _io.apply_baseline_delta(
        per_session, baseline, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )
    if sessions_with_delta.empty:
        logger.warning(
            "no per-session deltas computable for endpoint %r (no pre-epoch "
            "rows for any animal[/side]?); skipping", endpoint_slug,
        )
        return None
    pooled = _io.phenotype_pooled_per_epoch_delta(
        sessions_with_delta, by_side=has_side, side_col=_SIDE_SPLIT_COL,
    )

    n_by_tier = _count_animals_per_tier(sessions_with_delta)

    if has_side:
        fig = _build_v5_side_split_figure(
            pooled, sessions_with_delta, endpoint_slug, n_by_tier,
        )
    else:
        fig = _build_v5_cohort_pooled_figure(
            pooled, sessions_with_delta, endpoint_slug, n_by_tier,
        )

    _apply_aggregation_footer(fig, aggregation_subtitle)
    endpoint_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return svg_path, png_path


def _build_v5_side_split_figure(
    pooled: pd.DataFrame,
    sessions_with_delta: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    display_name, short_y_label = _layout.get_endpoint_labels(endpoint_slug)
    fig, ipsi_ax, contra_ax = _layout.phenotype_side_split_panels()
    for ic, ax in zip(_IPSI_CONTRA_PANELS, (ipsi_ax, contra_ax)):
        pooled_side = pooled[pooled[_SIDE_SPLIT_COL] == ic]
        scatter_side = sessions_with_delta[sessions_with_delta[_SIDE_SPLIT_COL] == ic]
        _draw_v5_delta_line_with_scatter(ax, pooled_side, scatter_side, pad_y=False)
        _layout.phenotype_panel(
            ax,
            endpoint_slug=endpoint_slug,
            n_by_tier=n_by_tier,
            xlabel="Epoch",
            ylabel=short_y_label,
            set_title=False,
            draw_stroke_onset=False,
        )
        _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    # Shared (sharey) y-range = union over BOTH panels incl. the per-session
    # delta scatter, set once after both are drawn (fixes the sharey-clip bug
    # where the contra panel's larger range was cut off — e.g. tongue_n_right).
    yr = _side_split_yrange(
        pooled["mean"], pooled["sem"], extra=sessions_with_delta["delta_value"],
    )
    if yr is not None:
        ipsi_ax.set_ylim(*yr)
    _layout.apply_side_split_suptitle(
        fig, endpoint_slug, baseline_subtracted=True,
    )
    _layout.apply_top_room(fig)
    return fig


def _build_v5_cohort_pooled_figure(
    pooled: pd.DataFrame,
    sessions_with_delta: pd.DataFrame,
    endpoint_slug: str,
    n_by_tier: dict[str, int],
):
    display_name, short_y_label = _layout.get_endpoint_labels(endpoint_slug)
    fig, ax = _layout.cohort_pooled_panel()
    _draw_v5_delta_line_with_scatter(ax, pooled, sessions_with_delta)
    _layout.phenotype_panel(
        ax,
        endpoint_slug=endpoint_slug,
        n_by_tier=n_by_tier,
        xlabel="Epoch",
        ylabel=short_y_label,
        set_title=False,  # suptitle owns the title
        draw_stroke_onset=False,
    )
    _layout.phenotype_legend(ax, n_by_tier=n_by_tier)
    _layout.apply_figure_suptitle(
        fig, display_name, baseline_subtracted=True,
    )
    _layout.apply_top_room(fig)
    return fig


def _draw_v5_delta_line_with_scatter(
    ax,
    pooled: pd.DataFrame,
    sessions_with_delta: pd.DataFrame,
    *,
    pad_y: bool = True,
) -> None:
    """Render Q-lock 11 V5: per-phenotype delta lines + faded scatter underlay.

    Background layer: per-(animal, session) scatter dots at epoch positions
    with horizontal jitter; same color as the phenotype's connecting line;
    α=0.25; zorder=1. Foreground: phenotype-colored line connecting the
    cohort-mean delta across the 4 epoch positions, with SEM error bars;
    zorder=3. y=0 reference line at zorder=0 (drawn separately by
    :func:`phenotype_panel`).

    Delegates the per-tier line+dots drawing to the shared
    :func:`render_line_with_jitter_dots` primitive (chore
    ``vChore-dlc-pooled-phenotype-unification`` Stage 1 extraction). Drawing
    is now interleaved per tier rather than all-scatter-then-all-lines, but
    the explicit ``zorder`` (dots=1 < lines=3) keeps every line above every
    dot, so the rendered output is unchanged. Per-tier marker shape carries
    through to the faded background so silhouette identity survives the color
    wash-out (Task 1a v5).
    """
    order_idx = {e: i for i, e in enumerate(_V5_EPOCH_ORDER)}
    for tier in _palette.PHENOTYPE_ORDER:
        color = _palette.phenotype_palette(tier)
        marker = _palette.phenotype_marker(tier)

        # Background underlay inputs — one (center, per-session-values) pair
        # per epoch that has contributing sessions for this tier.
        tier_scatter = sessions_with_delta[
            sessions_with_delta["phenotype_tier"] == tier
        ]
        scatter_centers: list[int] = []
        scatter_values: list[Any] = []
        for epoch_idx, epoch in enumerate(_V5_EPOCH_ORDER):
            cell = tier_scatter[tier_scatter["epoch_label"] == epoch]
            if cell.empty:
                continue
            scatter_centers.append(epoch_idx)
            scatter_values.append(cell["delta_value"].to_numpy())

        # Foreground line inputs — reindex to canonical epoch order so the
        # line walks pre→chronic, plotting only epochs the pool summarizes.
        tier_pool = pooled[pooled["phenotype_tier"] == tier]
        if tier_pool.empty:
            line_x: list[int] = []
            line_y: list[float] = []
            line_yerr: list[float] | None = None
        else:
            tier_pool = tier_pool.assign(
                epoch_idx=tier_pool["epoch_label"].map(order_idx)
            ).sort_values("epoch_idx")
            line_x = tier_pool["epoch_idx"].tolist()
            line_y = tier_pool["mean"].tolist()
            line_yerr = tier_pool["sem"].tolist()

        if not scatter_centers and not line_x:
            continue
        render_line_with_jitter_dots(
            ax,
            line_x=line_x, line_y=line_y, line_yerr=line_yerr,
            scatter_centers=scatter_centers, scatter_values=scatter_values,
            color=color, marker=marker, label=tier,
            jitter_width=_V5_JITTER_WIDTH,
        )

    ax.set_xticks(range(len(_V5_EPOCH_ORDER)))
    ax.set_xticklabels(
        [_layout.get_epoch_display(e) for e in _V5_EPOCH_ORDER]
    )
    ax.set_xlim(-0.5, len(_V5_EPOCH_ORDER) - 0.5)
    if pad_y:
        _layout.expand_y_axis(ax)


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
             "(<pipeline_outputs>/stats/figures/phenotype_pooled).",
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
    parser.add_argument(
        "--remap-phenotypes", choices=("none", "3tier"), default="none",
        help='Phenotype-tier scope. "none" (default) = 4-tier (F-P-1). '
             '"3tier" merges moderate-severe into moderate; output routes to '
             'the "<endpoint>/3_tier/" scope subdir ("4_tier" otherwise), so '
             'the 4-tier figures are preserved.',
    )
    parser.add_argument(
        "--filter-variant",
        choices=("none", "filtered_v1", "filtered_v1_na_masked"), default="none",
        help='Stats-input variant. "none" (default) = unfiltered tree '
             '(stats/inputs/<slug>/) → "<endpoint>/<scope>/no_filter/" '
             '(flat for non-filterable jaw/spout). "filtered_v1" = '
             'lick-filtered tree (stats/inputs/filtered_v1/<slug>/) → '
             '"<endpoint>/<scope>/v3/"; only the DLC-filterable tongue '
             'scalars have a filtered_v1 input, so non-filterable slugs are '
             'skipped (no-data).',
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
    remap_3tier = args.remap_phenotypes == "3tier"

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
                remap_3tier=remap_3tier,
                filter_variant=args.filter_variant,
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
                remap_3tier=remap_3tier,
                filter_variant=args.filter_variant,
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
