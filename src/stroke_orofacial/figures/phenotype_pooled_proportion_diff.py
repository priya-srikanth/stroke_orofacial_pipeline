"""Phase 9.1 Q-lock 12 — Phenotype-pooled proportion-diff heatmap renderer.

Stage 3 of the Q-lock 12 pipeline. Consumes phenotype-pooled spatial
records (from
:func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`)
and renders 4 SVG figures (Q12-G):

  - One figure per ``(bodypart, side)`` combination.
  - Each figure = 4×3 grid of phenotype × post_epoch panels.
  - Q12-D (revised per Addendum #1): legacy custom blue→#d0d0d0→red
    diverging cmap; data-driven cohort-wide ``shared_vmax`` = 99th
    percentile of ``|D̄|`` across ALL 4 figures × 4×3 panels, applied
    via :class:`matplotlib.colors.Normalize`.
  - Q12-E (revised per Addendum #1): no-data cells (``np.nan`` in
    pooled D̄) render as ``set_bad("white")`` against white panel
    facecolor.
  - Q12-J (revised per Addendum #2): output directory
    ``pipeline_outputs/stats/figures/phenotype_pooled/proportion_diff_heatmaps/``;
    filename ``<bodypart>_<side>_proportion_diff_cleaned_trace.svg``. The
    Q-lock 15 ``cleaned_trace`` marker stays in the filename + footer;
    directory aligned with the q13b ``stats/figures/phenotype_pooled/``
    tree convention.

Renders re-use :func:`stroke_orofacial.dlc_spatial.render_on_demand._render_proportion_diff_panel`
for the per-panel image draw (Q12-C revised lock).
"""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_spatial.render_on_demand import (
    _PROPORTION_DIFF_CMAP,
    _render_proportion_diff_panel,
)
from stroke_orofacial.figures.palette import (
    PHENOTYPE_ORDER,
    phenotype_display_name,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.spatial_proportion_diff import (
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
    get_spatial_recipe,
)

# Q-lock 12b Addendum #7: include ``"pre"`` as the first column (baseline
# noise floor reference). Each Pre cell shows the per-animal mean of
# per-pre-session D arrays against the animal's pre-pool, phenotype-
# averaged the same way the post panels are.
EPOCH_ORDER: tuple[str, ...] = ("pre",) + POST_EPOCHS

logger = logging.getLogger(__name__)


# Q-lock 15 three-layer marker convention. Output directory revised per
# Addendum #2 (2026-05-28) to align with the q13b stats/figures/phenotype_pooled/
# tree; the cleaned_trace marker stays in the filename + footer subtitle.
FIGURE_SUBDIR: str = "stats/figures/phenotype_pooled/proportion_diff_heatmaps"
FIGURE_SUBTITLE_BY_BODYPART: dict[str, str] = {
    "tongue": "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)",
    "jaw": "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4 + Phase 7f)",
    # Chore whisker-nose (Addendum #2): raw DLC (path A; no cleaned traces).
    "whisker": "Source: raw DLC tracking (all whiskers pooled; chore whisker-nose)",
    "nose": "Source: raw DLC tracking (chore whisker-nose)",
    "spout": "Source: raw DLC tracking (both spouts pooled, all trials; chore whisker-nose)",
    "eye": "Source: raw DLC tracking (both eyes pooled, all trials; chore whisker-nose)",
}

# Display names for the epoch column headers (capitalized; "Subacute" as
# one word per the q13b 2026-05-27 figure-review convention). "Pre"
# added per Addendum #7.
EPOCH_DISPLAY_NAMES: dict[str, str] = {
    "pre": "Pre",
    "acute": "Acute",
    "sub_acute": "Subacute",
    "chronic": "Chronic",
}

# Default to a 99th-percentile vmax floor — see compute_cohort_shared_vmax.
SHARED_VMAX_PERCENTILE: float = 99.0
SHARED_VMAX_FLOOR: float = 1e-9


# ---------------------------------------------------------------------------
# vmax computation (Q12-D Addendum #1 revised lock)
# ---------------------------------------------------------------------------


def compute_cohort_shared_vmax(
    pooled_records: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    percentile: float = SHARED_VMAX_PERCENTILE,
) -> float:
    """Compute the cohort-wide ``shared_vmax`` for the 4-figure cohort.

    Concatenates ``|D̄|`` finite values across EVERY pooled record (i.e.
    across all 4 figures × 4×3 panels), then takes the requested
    percentile. Returns a strictly positive float (floored at
    ``SHARED_VMAX_FLOOR``).

    Per Phase 9.1 Q-lock 12 Addendum #1 Q12-D: this replaces the
    original kickoff's ``±0.1`` fixed range — empirical probe showed
    ``|D|`` p99 in the 0.001–0.006 range per-animal × per-epoch, so a
    fixed ±0.1 would render all 48 panels uniformly light-grey. The
    cohort-wide 99th-percentile auto-calibrates to actual phenotype-
    pooled magnitudes and preserves the "all panels share one
    colorbar" Q14 intent.

    Parameters
    ----------
    pooled_records : Mapping
        Output of
        :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`.
        Keyed by ``(phenotype, side, bodypart, post_epoch)``; each value
        carries ``D_mean`` (np.ndarray with NaN for no-data cells).
    percentile : float, default 99.0
        Percentile of ``|D̄|`` to use as the saturation point.

    Returns
    -------
    float
        ``shared_vmax`` value. Always ``>= SHARED_VMAX_FLOOR``.
    """
    finite_vals: list[float] = []
    for rec in pooled_records.values():
        D = np.asarray(rec["D_mean"], dtype=np.float64)
        finite = np.abs(D[np.isfinite(D)])
        if finite.size:
            finite_vals.append(finite)
    if not finite_vals:
        return SHARED_VMAX_FLOOR
    stacked = np.concatenate(finite_vals)
    vmax = float(np.percentile(stacked, percentile))
    return max(vmax, SHARED_VMAX_FLOOR)


# ---------------------------------------------------------------------------
# Single-figure renderer (per bodypart × side)
# ---------------------------------------------------------------------------


def _panel_title(
    phenotype: str,
    post_epoch: str,
    pooled_rec: Mapping[str, Any] | None,
) -> str:
    """Format the per-panel sample-size annotation.

    Layout: ``{Phenotype display} | {Epoch display}\\n n_animals=…
    pre n=… post n=…``. When the pool is empty (record absent), the
    second line reads ``no animals contributed``.
    """
    head = (
        f"{phenotype_display_name(phenotype)} | "
        f"{EPOCH_DISPLAY_NAMES.get(post_epoch, post_epoch)}"
    )
    if pooled_rec is None:
        return f"{head}\n(no animals contributed)"
    n_animals = pooled_rec.get("n_animals", 0)
    pre_counts = pooled_rec.get("n_pre_trials_per_animal", {})
    post_counts = pooled_rec.get("n_post_trials_per_animal", {})
    # Per-panel sample size = total trial count across phenotype animals,
    # so the annotation reads like "n_animals=4, pre trials=1340, post=520".
    total_pre = int(sum(pre_counts.values())) if pre_counts else 0
    total_post = int(sum(post_counts.values())) if post_counts else 0
    return (
        f"{head}\nn_animals={n_animals}, "
        f"pre n={total_pre}, post n={total_post}"
    )


def render_phenotype_pooled_proportion_diff_figure(
    bodypart: str,
    side: str,
    pooled_records: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    shared_vmax: float,
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
    defaults: dict[str, Any] | None = None,
    subtitle_override: str | None = None,
    side_display: dict[str, str] | None = None,
) -> plt.Figure:
    """Render the single (bodypart × side) phenotype × post_epoch figure.

    ``subtitle_override`` replaces the default source-data footer (chore v2
    re-emit passes the unfiltered + ipsi/contra line); ``side_display`` maps
    the rig side key to a display label (chore v2: ``{"L": "Ipsi (mouse-L)",
    ...}``). Both default ``None`` = current behavior.

    Phenotype rows ordered per ``phenotype_order`` (defaults to the
    4-tier :data:`stroke_orofacial.figures.palette.PHENOTYPE_ORDER`;
    callers may pass a 3-tier sequence like
    ``("mild", "moderate", "severe")`` to render the merged-mod-severe
    variant — the figure grid auto-resizes to
    ``len(phenotype_order) × len(POST_EPOCHS)``).

    Epoch columns ordered per
    :data:`stroke_orofacial.stats.spatial_proportion_diff.POST_EPOCHS`
    (acute / sub_acute / chronic left-to-right).

    Each panel re-uses
    :func:`stroke_orofacial.dlc_spatial.render_on_demand._render_proportion_diff_panel`
    with the supplied ``shared_vmax``, the legacy custom diverging
    cmap, and white no-data masking (Q12-D/E Addendum #1 locks).

    A single figure-level colorbar is attached on the right.
    """
    # Recipe-driven (chore whisker-nose Addendum #2): tongue/jaw resolve to
    # their legacy center_mode + ("L", "R") sides — byte-identical behavior.
    # New bodyparts (whisker/nose/spout/eye) resolve their own center_mode +
    # output sides (whisker "both" = combined all-6 heatmap; spout/eye
    # "both" = pooled no-split).
    recipe = get_spatial_recipe(bodypart)
    if side not in recipe.output_sides:
        raise ValueError(
            f"side {side!r} not valid for bodypart {bodypart!r}; expected "
            f"one of {recipe.output_sides}.",
        )
    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    center_mode = recipe.center_mode

    nrows = len(phenotype_order)
    ncols = len(EPOCH_ORDER)
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 4.0, nrows * 3.6),
        constrained_layout=True,
    )
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(h_pad=0.35, hspace=0.05)
    fig.patch.set_facecolor("white")

    axes = np.asarray(axes_obj).reshape(nrows, ncols)
    for i, phenotype in enumerate(phenotype_order):
        for j, post_epoch in enumerate(EPOCH_ORDER):
            ax = axes[i, j]
            rec = pooled_records.get((phenotype, side, bodypart, post_epoch))
            if rec is None:
                _render_proportion_diff_panel(
                    ax, None, None, bodypart, center_mode,
                    spatial_config=spatial_config,
                    title=_panel_title(phenotype, post_epoch, None),
                    shared_vmax=shared_vmax,
                )
                continue
            _render_proportion_diff_panel(
                ax,
                np.asarray(rec["D_mean"], dtype=np.float64),
                rec.get("extent"),
                bodypart, center_mode,
                spatial_config=spatial_config,
                title=_panel_title(phenotype, post_epoch, rec),
                shared_vmax=shared_vmax,
            )

    # Shared colorbar on the figure right (Q24 Addendum #24 pattern).
    shared_im = None
    for ax in axes.flat:
        if ax.images:
            shared_im = ax.images[0]
            break
    if shared_im is None:
        # Fallback: synthesize a hidden mappable so the colorbar still
        # renders against the locked shared_vmax (every panel was
        # no-data — unusual but handled).
        import matplotlib.colors as mcolors
        norm = mcolors.Normalize(vmin=-shared_vmax, vmax=shared_vmax)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=_PROPORTION_DIFF_CMAP)
        sm.set_array(np.array([]))
        shared_im = sm
    cbar = fig.colorbar(
        shared_im, ax=list(axes.flat), shrink=0.6, pad=0.02,
    )
    cbar.set_label("Δ proportion (post − pre)")

    subtitle = (
        subtitle_override if subtitle_override is not None
        else FIGURE_SUBTITLE_BY_BODYPART.get(
            bodypart, "Source: v7-cleaned-trace cohort re-emit",
        )
    )
    side_part = (side_display or {}).get(side, f"side={side}")
    fig.suptitle(
        f"Phenotype-pooled proportion-diff heatmap — "
        f"{bodypart} | {side_part} | shared |vmax|={shared_vmax:.4g}\n"
        f"{subtitle}",
        fontsize=12,
    )
    return fig


def render_phenotype_pooled_proportion_diff_multiside_figure(
    bodypart: str,
    sides: Sequence[str],
    pooled_records: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    shared_vmax: float,
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
    defaults: dict[str, Any] | None = None,
    subtitle_override: str | None = None,
    side_display: dict[str, str] | None = None,
) -> plt.Figure:
    """Render ONE figure with multiple sides as side-by-side sub-grids.

    Chore whisker-nose Addendum #4 (Option B): the nose ipsi/contra cue-trial
    sets can't pool into a single ``both`` map, so they are shown as adjacent
    phenotype×epoch sub-grids in a single figure (one matplotlib subfigure per
    side, each carrying the side display label as its header). The per-panel
    draw + shared diverging colorbar reuse the single-side path's primitives,
    so the cmap / no-data masking / shared_vmax conventions are identical.

    ``sides`` are the record-side keys (e.g. ``("L", "R")``); ``side_display``
    maps each to a header label (e.g. ``{"L": "Ipsi (mouse-L)", ...}``).
    """
    recipe = get_spatial_recipe(bodypart)
    for side in sides:
        if side not in recipe.output_sides:
            raise ValueError(
                f"side {side!r} not valid for bodypart {bodypart!r}; expected "
                f"one of {recipe.output_sides}.",
            )
    if not sides:
        raise ValueError("sides must be non-empty.")
    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    center_mode = recipe.center_mode

    nrows = len(phenotype_order)
    nepochs = len(EPOCH_ORDER)
    ncols = len(sides) * nepochs
    # Single flat grid (NOT subfigures) so the shared colorbar can span every
    # panel — a colorbar cannot be stolen across separate subfigures. Each
    # side occupies a contiguous block of EPOCH_ORDER columns; the side label
    # is carried on that block's top-row panel titles.
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 4.0, nrows * 3.6),
        constrained_layout=True,
    )
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(h_pad=0.35, hspace=0.05)
    fig.patch.set_facecolor("white")
    axes = np.asarray(axes_obj).reshape(nrows, ncols)

    def _short_side(s: str) -> str:
        # "Ipsi (mouse-L)" -> "Ipsi"; "both" -> its display or "both".
        return (side_display or {}).get(s, s).split(" (")[0]

    for s_idx, side in enumerate(sides):
        short = _short_side(side)
        for i, phenotype in enumerate(phenotype_order):
            for j, post_epoch in enumerate(EPOCH_ORDER):
                ax = axes[i, s_idx * nepochs + j]
                rec = pooled_records.get((phenotype, side, bodypart, post_epoch))
                base_title = _panel_title(phenotype, post_epoch, rec)
                title = f"[{short}] {base_title}" if i == 0 else base_title
                _render_proportion_diff_panel(
                    ax,
                    None if rec is None
                    else np.asarray(rec["D_mean"], dtype=np.float64),
                    None if rec is None else rec.get("extent"),
                    bodypart, center_mode,
                    spatial_config=spatial_config,
                    title=title,
                    shared_vmax=shared_vmax,
                )

    # Shared diverging colorbar across all panels (same convention as the
    # single-side renderer).
    shared_im = None
    for ax in axes.flat:
        if ax.images:
            shared_im = ax.images[0]
            break
    if shared_im is None:
        import matplotlib.colors as mcolors
        norm = mcolors.Normalize(vmin=-shared_vmax, vmax=shared_vmax)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=_PROPORTION_DIFF_CMAP)
        sm.set_array(np.array([]))
        shared_im = sm
    cbar = fig.colorbar(shared_im, ax=list(axes.flat), shrink=0.6, pad=0.02)
    cbar.set_label("Δ proportion (post − pre)")

    subtitle = (
        subtitle_override if subtitle_override is not None
        else FIGURE_SUBTITLE_BY_BODYPART.get(
            bodypart, "Source: v7-cleaned-trace cohort re-emit",
        )
    )
    sides_part = " + ".join(
        (side_display or {}).get(s, s) for s in sides
    )
    fig.suptitle(
        f"Phenotype-pooled proportion-diff heatmap — "
        f"{bodypart} | {sides_part} | shared |vmax|={shared_vmax:.4g}\n"
        f"{subtitle}",
        fontsize=12,
    )
    return fig


# ---------------------------------------------------------------------------
# Emit driver — 4 figures + manifest
# ---------------------------------------------------------------------------


def emit_phenotype_pooled_proportion_diff_figures(
    pooled_records: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    resolver: PathResolver,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
    shared_vmax: float | None = None,
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
    defaults: dict[str, Any] | None = None,
    subtitle_override: str | None = None,
    side_display: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit the 4 Q-lock 12 SVG figures (2 bodyparts × 2 sides) + manifest.

    Computes the cohort-wide ``shared_vmax`` once (across all 4 figures)
    so the colorbar is comparable end-to-end. If the caller supplies
    ``shared_vmax``, that value is used verbatim (useful for tests).

    Parameters
    ----------
    pooled_records : Mapping
        Output of
        :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`.
    resolver : PathResolver
    output_dir : Path, optional
        Override the canonical Q12-J subdir (used by tests). When None,
        resolves to ``resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)``.
    overwrite : {"skip", "force", "prompt"}, default "prompt"
        Confirm-once-then-force pattern matching Q-lock 13b.
    shared_vmax : float, optional
        Override the cohort-wide computed vmax.
    defaults : dict, optional
        Pre-loaded :func:`load_defaults` output.

    Returns
    -------
    dict
        ``{"OK": [...], "SKIP": [...], "FAIL": [(key, repr(exc)), ...],
        "shared_vmax": float, "manifest_csv": Path}``.
    """
    if defaults is None:
        defaults = load_defaults()
    if shared_vmax is None:
        shared_vmax = compute_cohort_shared_vmax(pooled_records)

    out_dir = (
        output_dir
        if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "OK": [], "SKIP": [], "FAIL": [],
        "shared_vmax": float(shared_vmax),
    }

    for bodypart in BODYPART_CENTER_MODES:
        for side in SIDES:
            key = (bodypart, side)
            filename = f"{bodypart}_{side}_proportion_diff_cleaned_trace.svg"
            target = out_dir / filename
            if target.exists() and overwrite == "skip":
                results["SKIP"].append(key)
                continue
            if target.exists() and overwrite == "prompt":
                raise RuntimeError(
                    f"phase 9.1 Q-lock 12 figure exists at {target}; "
                    "caller must confirm overwrite (GR7).",
                )
            try:
                fig = render_phenotype_pooled_proportion_diff_figure(
                    bodypart=bodypart, side=side,
                    pooled_records=pooled_records,
                    shared_vmax=shared_vmax,
                    phenotype_order=phenotype_order,
                    defaults=defaults,
                    subtitle_override=subtitle_override,
                    side_display=side_display,
                )
                fig.savefig(target, format="svg", bbox_inches="tight")
                plt.close(fig)
                results["OK"].append(key)
            except Exception as exc:  # noqa: BLE001
                results["FAIL"].append((key, repr(exc)))

    manifest_rows = []
    for status in ("OK", "SKIP"):
        for key in results[status]:
            manifest_rows.append({
                "bodypart": key[0], "side": key[1],
                "status": status, "error": "",
            })
    for key, err in results["FAIL"]:
        manifest_rows.append({
            "bodypart": key[0], "side": key[1],
            "status": "FAIL", "error": err,
        })
    manifest_csv = out_dir / "emit_manifest.csv"
    import pandas as pd
    pd.DataFrame(
        manifest_rows,
        columns=["bodypart", "side", "status", "error"],
    ).to_csv(manifest_csv, index=False)
    results["manifest_csv"] = manifest_csv
    return results


__all__ = [
    "EPOCH_DISPLAY_NAMES",
    "FIGURE_SUBDIR",
    "FIGURE_SUBTITLE_BY_BODYPART",
    "SHARED_VMAX_FLOOR",
    "SHARED_VMAX_PERCENTILE",
    "compute_cohort_shared_vmax",
    "emit_phenotype_pooled_proportion_diff_figures",
    "render_phenotype_pooled_proportion_diff_figure",
    "render_phenotype_pooled_proportion_diff_multiside_figure",
]
