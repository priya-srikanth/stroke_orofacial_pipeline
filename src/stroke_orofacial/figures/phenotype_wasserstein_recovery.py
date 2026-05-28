"""Phase 9.1 Q-lock 12 Addendum #5 — Phenotype-pooled W-2 recovery plots.

Consumes phenotype-pooled W-2 records (from
:func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_wasserstein`)
and renders 4 SVG figures (one per ``(bodypart, side)``). Each figure
shows W-2 (pre-stroke-normalized Wasserstein-2 distance) vs post-epoch,
with one colored line per phenotype tier.

Layout per figure:
  - X axis: 3 post-epochs ``("acute", "sub_acute", "chronic")``.
  - Y axis: W-2 distance (pixel units).
  - One line per phenotype, colored per
    :data:`stroke_orofacial.figures.palette.PHENOTYPE_ORDER`.
  - ±SEM ribbon around each line (NaN for n=1 tiers → marker only,
    no ribbon).
  - Per-animal scatter underlay (one semi-transparent dot per animal
    at each epoch) per Priya 2026-05-28 direction.

Q12-J Addendum #2 path tree (matches the heatmap module):
  ``pipeline_outputs/stats/figures/phenotype_pooled/wasserstein_recovery/``
  ``<bp>_<side>_wasserstein_recovery_cleaned_trace.svg``
"""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.figures.palette import (
    PHENOTYPE_ORDER,
    phenotype_display_name,
    phenotype_palette,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.spatial_proportion_diff import (
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
)

logger = logging.getLogger(__name__)


FIGURE_SUBDIR: str = "stats/figures/phenotype_pooled/wasserstein_recovery"
FIGURE_SUBTITLE_BY_BODYPART: dict[str, str] = {
    "tongue": "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)",
    "jaw": "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4 + Phase 7f)",
}

EPOCH_DISPLAY_NAMES: dict[str, str] = {
    "acute": "Acute",
    "sub_acute": "Subacute",
    "chronic": "Chronic",
}


def render_phenotype_wasserstein_recovery_figure(
    bodypart: str,
    side: str,
    pooled_w2: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
) -> plt.Figure:
    """Render one (bodypart × side) W-2-vs-epoch line plot.

    One line per phenotype tier in ``phenotype_order``. Markers at the
    3 post-epochs. ±SEM error bars; NaN SEM (n=1 tier) drops the bar
    so the marker still appears. Per-animal scatter underlay (one dot
    per (animal × epoch) at α=0.4, colored per phenotype).
    """
    if bodypart not in BODYPART_CENTER_MODES:
        raise ValueError(
            f"bodypart {bodypart!r} not in Q12-B scope; expected one of "
            f"{tuple(BODYPART_CENTER_MODES)}.",
        )
    if side not in SIDES:
        raise ValueError(f"side {side!r} not in {SIDES}.")

    fig, ax = plt.subplots(figsize=(7.0, 5.5), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    epoch_x = np.arange(len(POST_EPOCHS), dtype=np.float64)
    # Phenotype-specific small horizontal jitter so per-animal scatter
    # dots don't all stack on the same x value.
    n_pheno = len(phenotype_order)
    jitter_step = 0.10
    jitter_offsets = (
        (np.arange(n_pheno) - (n_pheno - 1) / 2.0) * jitter_step
    )

    rng = np.random.default_rng(seed=2026)
    for i, phenotype in enumerate(phenotype_order):
        color = phenotype_palette(phenotype)
        means: list[float] = []
        sems: list[float] = []
        for j, epoch in enumerate(POST_EPOCHS):
            rec = pooled_w2.get((phenotype, side, bodypart, epoch))
            if rec is None:
                means.append(np.nan)
                sems.append(np.nan)
                continue
            means.append(float(rec["w2_mean"]))
            sems.append(float(rec["w2_sem"]))
            # Per-animal scatter at this (phenotype, epoch).
            per_animal = rec.get("w2_per_animal", {}) or {}
            if per_animal:
                vals = np.array(list(per_animal.values()), dtype=np.float64)
                jx = jitter_offsets[i] + rng.uniform(
                    -0.04, 0.04, size=len(vals),
                )
                ax.scatter(
                    np.full_like(vals, epoch_x[j]) + jx,
                    vals,
                    color=color, s=24, alpha=0.4,
                    edgecolor="black", linewidth=0.3, zorder=2,
                )

        # Line + markers + error bars at the phenotype's jitter offset.
        xs = epoch_x + jitter_offsets[i]
        means_arr = np.asarray(means, dtype=np.float64)
        sems_arr = np.asarray(sems, dtype=np.float64)
        ax.errorbar(
            xs, means_arr,
            yerr=np.where(np.isfinite(sems_arr), sems_arr, 0.0),
            fmt="o-",
            color=color, markeredgecolor="black", markeredgewidth=0.5,
            linewidth=2.0, markersize=9, capsize=4, zorder=4,
            label=phenotype_display_name(phenotype),
        )

    ax.set_xticks(epoch_x)
    ax.set_xticklabels(
        [EPOCH_DISPLAY_NAMES.get(e, e) for e in POST_EPOCHS],
        fontsize=12,
    )
    ax.set_xlabel("Post-stroke epoch", fontsize=13)
    ax.set_ylabel("W-2 distance from pre-stroke (pixels)", fontsize=13)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_xlim(epoch_x[0] - 0.5, epoch_x[-1] + 0.5)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.6)
    ax.legend(loc="best", fontsize=11, framealpha=0.9)

    subtitle = FIGURE_SUBTITLE_BY_BODYPART.get(
        bodypart, "Source: v7-cleaned-trace cohort re-emit",
    )
    fig.suptitle(
        f"W-2 recovery curve — {bodypart} | side={side}\n{subtitle}",
        fontsize=12,
    )
    return fig


def emit_phenotype_wasserstein_recovery_figures(
    pooled_w2: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    *,
    resolver: PathResolver,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
) -> dict[str, Any]:
    """Emit the 4 W-2 recovery SVGs + manifest CSV.

    Same overwrite semantics as the heatmap emit driver: ``force``
    overwrites; ``skip`` leaves existing untouched; ``prompt`` raises
    on first existing target.
    """
    out_dir = (
        output_dir if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {"OK": [], "SKIP": [], "FAIL": []}
    for bodypart in BODYPART_CENTER_MODES:
        for side in SIDES:
            key = (bodypart, side)
            filename = f"{bodypart}_{side}_wasserstein_recovery_cleaned_trace.svg"
            target = out_dir / filename
            if target.exists() and overwrite == "skip":
                results["SKIP"].append(key)
                continue
            if target.exists() and overwrite == "prompt":
                raise RuntimeError(
                    f"phase 9.1 Q-lock 12 W-2 recovery figure exists at "
                    f"{target}; caller must confirm overwrite (GR7).",
                )
            try:
                fig = render_phenotype_wasserstein_recovery_figure(
                    bodypart=bodypart, side=side,
                    pooled_w2=pooled_w2,
                    phenotype_order=phenotype_order,
                )
                fig.savefig(target, format="svg", bbox_inches="tight")
                plt.close(fig)
                results["OK"].append(key)
            except Exception as exc:  # noqa: BLE001
                results["FAIL"].append((key, repr(exc)))

    import pandas as pd
    rows = []
    for status in ("OK", "SKIP"):
        for key in results[status]:
            rows.append({
                "bodypart": key[0], "side": key[1],
                "status": status, "error": "",
            })
    for key, err in results["FAIL"]:
        rows.append({
            "bodypart": key[0], "side": key[1],
            "status": "FAIL", "error": err,
        })
    manifest_csv = out_dir / "w2_emit_manifest.csv"
    pd.DataFrame(
        rows, columns=["bodypart", "side", "status", "error"],
    ).to_csv(manifest_csv, index=False)
    results["manifest_csv"] = manifest_csv
    return results


__all__ = [
    "EPOCH_DISPLAY_NAMES",
    "FIGURE_SUBDIR",
    "FIGURE_SUBTITLE_BY_BODYPART",
    "emit_phenotype_wasserstein_recovery_figures",
    "render_phenotype_wasserstein_recovery_figure",
]
