"""Phase 9.1 Q-lock 12a — Per-session W-2 boxplots (q13b shape).

Replacement renderer for the Q-lock 12 Addendum #5 line-plot W-2
recovery figure. Uses per-session W-2 as the unit of pooling
(matching the q13b convention) and renders side-by-side boxplots per
phenotype within each epoch group on the x-axis (Pre / Acute /
Subacute / Chronic), with per-session jittered scatter overlaid on
each box.

Q12-N (locked 2026-05-28): trial-with-licks definition uses the
``(0, 8000)`` ms post-tone window via
:mod:`stroke_orofacial.cohort_filters`.

Q-lock 12a Addendum #6 v1 lock: pre-epoch W-2 = per-pre-session
distance to the FULL pre-pool that includes the session ("naive";
small bias toward 0 is acceptable as a noise-floor reference).

Output path: ``stats/figures/phenotype_pooled/wasserstein_recovery/``
(sibling to the Addendum #5 line plots; Q-lock 12a overwrites them
with the boxplot variant per Priya 2026-05-28 direction). 3-tier
variant in the ``3_phenotype/`` subdir.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
EPOCH_ORDER: tuple[str, ...] = ("pre",) + POST_EPOCHS
EPOCH_DISPLAY_NAMES: dict[str, str] = {
    "pre": "Pre",
    "acute": "Acute",
    "sub_acute": "Subacute",
    "chronic": "Chronic",
}


def render_phenotype_wasserstein_recovery_boxplot(
    bodypart: str,
    side: str,
    per_session_w2: pd.DataFrame,
    *,
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
    box_width: float = 0.18,
    group_pad: float = 0.10,
) -> plt.Figure:
    """Render the per-(bodypart, side) per-session W-2 boxplot figure.

    Layout matches q13b ``render_phase_aligned_endpoint_figure``: 4
    epoch groups on x-axis (Pre, Acute, Subacute, Chronic); within
    each group, one boxplot per phenotype tier side-by-side; per-
    session scatter overlaid on each box.

    Parameters
    ----------
    per_session_w2 : pd.DataFrame
        Long-form rows with columns: ``animal``, ``date``, ``side``,
        ``bodypart``, ``epoch_label``, ``recovery_phenotype``, ``w2``.
        Filtered to the current (bodypart, side) internally.
    phenotype_order : Sequence[str]
        Phenotype tiers to render as rows (PHENOTYPE_ORDER for 4-tier
        canonical; ``("mild", "moderate", "severe")`` for 3-tier).
    box_width : float
        Width of each boxplot in the x-axis units (epoch positions are
        at integers 0..3; each phenotype's box is offset within ±0.5
        of its epoch's integer x).
    group_pad : float
        Extra padding between epoch groups on the x-axis.
    """
    if bodypart not in BODYPART_CENTER_MODES:
        raise ValueError(
            f"bodypart {bodypart!r} not in Q12-B scope; expected one of "
            f"{tuple(BODYPART_CENTER_MODES)}.",
        )
    if side not in SIDES:
        raise ValueError(f"side {side!r} not in {SIDES}.")

    df = per_session_w2[
        (per_session_w2["bodypart"] == bodypart)
        & (per_session_w2["side"] == side)
    ].copy()

    fig, ax = plt.subplots(figsize=(9.0, 5.5), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    epoch_x = {ep: i for i, ep in enumerate(EPOCH_ORDER)}
    n_pheno = len(phenotype_order)
    # Center the phenotype boxes within their epoch group; total span
    # spans roughly ±0.5 around the integer epoch x.
    pheno_offsets = (
        (np.arange(n_pheno) - (n_pheno - 1) / 2.0)
        * (box_width + group_pad / max(1, n_pheno - 1))
    )

    rng = np.random.default_rng(seed=2026)

    for j, phenotype in enumerate(phenotype_order):
        color = phenotype_palette(phenotype)
        for ep in EPOCH_ORDER:
            x_pos = epoch_x[ep] + pheno_offsets[j]
            sub = df[
                (df["recovery_phenotype"] == phenotype)
                & (df["epoch_label"] == ep)
            ]
            vals = sub["w2"].to_numpy(dtype=np.float64)
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                continue
            bp = ax.boxplot(
                vals, positions=[x_pos], widths=box_width,
                patch_artist=True, showfliers=False,
                manage_ticks=False,
            )
            # Box style: phenotype color with edge-alpha
            for patch in bp["boxes"]:
                patch.set_facecolor(color)
                patch.set_alpha(0.5)
                patch.set_edgecolor("black")
                patch.set_linewidth(0.8)
            for line in bp["medians"]:
                line.set_color("black")
                line.set_linewidth(1.5)
            for line in bp["whiskers"] + bp["caps"]:
                line.set_color("black")
                line.set_linewidth(0.8)

            # Per-session scatter inside the box
            jitter = rng.uniform(
                -box_width * 0.35, box_width * 0.35, size=vals.size,
            )
            ax.scatter(
                x_pos + jitter, vals,
                color=color, s=18, alpha=0.7,
                edgecolor="black", linewidth=0.3, zorder=3,
            )

    ax.set_xticks(list(epoch_x.values()))
    ax.set_xticklabels(
        [EPOCH_DISPLAY_NAMES.get(ep, ep) for ep in EPOCH_ORDER],
        fontsize=13,
    )
    ax.set_xlabel("Epoch", fontsize=13)
    ax.set_ylabel("W-2 distance from pre-stroke (pixels)", fontsize=13)
    ax.set_xlim(-0.6, len(EPOCH_ORDER) - 0.4)
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.6)

    # Legend (top-left, q13b convention).
    handles = [
        plt.Rectangle(
            (0, 0), 1, 1,
            facecolor=phenotype_palette(p), alpha=0.5,
            edgecolor="black", linewidth=0.5,
            label=phenotype_display_name(p),
        )
        for p in phenotype_order
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=11, framealpha=0.9)

    subtitle = FIGURE_SUBTITLE_BY_BODYPART.get(
        bodypart, "Source: v7-cleaned-trace cohort re-emit",
    )
    fig.suptitle(
        f"W-2 recovery curve — {bodypart} | side={side}\n{subtitle}",
        fontsize=12,
    )
    return fig


def emit_phenotype_wasserstein_recovery_boxplot_figures(
    per_session_w2: pd.DataFrame,
    *,
    resolver: PathResolver,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
    phenotype_order: Sequence[str] = PHENOTYPE_ORDER,
) -> dict[str, Any]:
    """Emit the 4 boxplot SVGs + manifest CSV.

    Output filenames match the Addendum #5 line-plot convention
    (``<bp>_<side>_wasserstein_recovery_cleaned_trace.svg``) so the
    boxplot variant overwrites the line-plot variant at the same path
    when called with ``overwrite="force"``.
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
                    f"phase 9.1 Q-lock 12a W-2 boxplot figure exists at "
                    f"{target}; caller must confirm overwrite (GR7).",
                )
            try:
                fig = render_phenotype_wasserstein_recovery_boxplot(
                    bodypart=bodypart, side=side,
                    per_session_w2=per_session_w2,
                    phenotype_order=phenotype_order,
                )
                fig.savefig(target, format="svg", bbox_inches="tight")
                plt.close(fig)
                results["OK"].append(key)
            except Exception as exc:  # noqa: BLE001
                results["FAIL"].append((key, repr(exc)))

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
    manifest_csv = out_dir / "w2_boxplot_emit_manifest.csv"
    pd.DataFrame(
        rows, columns=["bodypart", "side", "status", "error"],
    ).to_csv(manifest_csv, index=False)
    results["manifest_csv"] = manifest_csv
    return results


__all__ = [
    "EPOCH_DISPLAY_NAMES",
    "EPOCH_ORDER",
    "FIGURE_SUBDIR",
    "FIGURE_SUBTITLE_BY_BODYPART",
    "emit_phenotype_wasserstein_recovery_boxplot_figures",
    "render_phenotype_wasserstein_recovery_boxplot",
]
