"""Phase 9.1 Q-lock 13b — Stage 4 stats compute + figure renderer.

Stats grid (Addendum #2 D3 lock):

- 3 endpoints × 2 sides × 4 phenotypes × 3 post_epochs = 72 paired
  Wilcoxon tests (one per phenotype × side × endpoint × post_epoch
  comparing pre vs post-epoch per-animal medians).
- Aggregator = "median" (median-of-per-session-medians per animal per
  epoch).
- One BH-FDR family across all 72 tests (NaN-aware: n=1 phenotype tiers
  return status="insufficient_data" + NaN p-value; BH-FDR propagates
  NaN through and excludes those rows from the rank-based adjustment).

Figure grid (Q-lock 15 three-layer marker convention):

- Directory: ``pipeline_outputs/phase_9_1_figures/phenotype_pooled_cleaned_trace/phase_aligned_endpoints/``
- Filename: ``<endpoint>_<side>_cleaned_trace.svg``
- Footer (figure subtitle): ``Source: v7-cleaned-trace cohort re-emit
  (Phase 7e + Phase 7e.4)``
- Count: 3 endpoints × 2 sides = 6 figures.

Each figure shows per-session medians as a boxplot grouped by
(epoch_label × recovery_phenotype). Significance annotations (BH-FDR
adjusted) drawn from the Stage 4a stats table.
"""
from __future__ import annotations

from collections.abc import Iterable
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
from stroke_orofacial.stats.aggregators import (
    PHASE_ALIGNED_ENDPOINT_SLUGS,
)
from stroke_orofacial.stats.models import fit_paired_pre_post_wilcoxon
from stroke_orofacial.stats.multiple_comparisons import (
    apply_correction_to_results_df,
)


# Q-lock 15 marker convention (three layers). Output directory corrected
# per Priya 2026-05-27: figures land under stats/figures/phenotype_pooled/
# (matching the existing V4/V5 phenotype-pooled figure tree) rather than
# a separate phase_9_1_figures/ tree.
FIGURE_SUBDIR: str = (
    "stats/figures/phenotype_pooled/phase_aligned_endpoints"
)
FIGURE_SUBTITLE: str = (
    "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)"
)

EPOCH_ORDER: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")
POST_EPOCHS: tuple[str, ...] = ("acute", "sub_acute", "chronic")
SIDE_ORDER: tuple[str, ...] = ("L", "R")

# Display names for epoch x-tick labels (capitalized, "Subacute" as one
# word per Priya 2026-05-27 figure review).
EPOCH_DISPLAY_NAMES: dict[str, str] = {
    "pre": "Pre",
    "acute": "Acute",
    "sub_acute": "Subacute",
    "chronic": "Chronic",
}

# Human-readable endpoint labels for figure titles + axis text.
ENDPOINT_DISPLAY_NAMES: dict[str, str] = {
    "peak_angle_deg":
        "Peak tongue angle (deg) at phase=0.5",
    "signed_angle_at_max_abs_phase_0_075_deg":
        "Signed tongue angle at max |angle| (deg) over phase ∈ [0, 0.75]",
    "signed_x_at_max_abs_phase_0_075_px":
        "Signed x at argmax(|x|) (px) over phase ∈ [0, 0.75]",
}

# Delta endpoint display names (baseline-normalized per Priya 2026-05-27).
DELTA_ENDPOINT_DISPLAY_NAMES: dict[str, str] = {
    "peak_angle_deg":
        "Δ Peak tongue angle (deg) from pre-stroke baseline",
    "signed_angle_at_max_abs_phase_0_075_deg":
        "Δ Signed tongue angle at max |angle| (deg) from baseline",
    "signed_x_at_max_abs_phase_0_075_px":
        "Δ Signed x at argmax(|x|) (px) from baseline",
}


# ---------------------------------------------------------------------------
# Stage 4a — stats compute (Wilcoxon paired × BH-FDR family of 72)
# ---------------------------------------------------------------------------


def compute_phase_aligned_endpoint_stats(
    per_session_df: pd.DataFrame,
    *,
    phenotype_order: Iterable[str] = PHENOTYPE_ORDER,
    side_order: Iterable[str] = SIDE_ORDER,
    aggregator: str = "median",
    value_col: str = "median",
) -> pd.DataFrame:
    """Run the Wilcoxon × BH-FDR family on per-session medians.

    Iterates over the phenotype × side × endpoint × post_epoch grid; for
    each cell, filters the per-session DataFrame to that slice and calls
    ``fit_paired_pre_post_wilcoxon(..., aggregator="median",
    value_col="median", post_epoch=...)``. After all fits, applies a
    single BH-FDR family-wide adjustment.

    Parameters
    ----------
    per_session_df : pd.DataFrame
        Output of :func:`stroke_orofacial.stats.aggregators.attach_phenotype_and_epoch`
        applied to per-session aggregates. Required columns: ``animal``,
        ``recovery_phenotype``, ``epoch_label``, ``side``, ``endpoint``,
        ``median``.
    phenotype_order : iterable of str, default :data:`PHENOTYPE_ORDER`
        Phenotype tiers to iterate. Pass the 3-tier order for the
        moderate-severe→moderate collapse (chore v2 3_tier scope).
    side_order : iterable of str, default :data:`SIDE_ORDER` (``("L","R")``)
        Side labels to iterate. The chore v2 re-emit passes
        ``("ipsi", "contra")`` since it pools on the lesion-relative
        recoded side rather than rig-frame L/R.

    Returns
    -------
    pd.DataFrame
        One row per phenotype × side × endpoint × post_epoch with columns:
        ``recovery_phenotype``, ``side``, ``endpoint``, ``post_epoch``,
        ``statistic``, ``p_value``, ``n_observations``, ``status``,
        ``median_diff``, ``p_adj``, ``reject``. NaN-aware: n=1 phenotype
        tiers carry NaN p_value + p_adj.
    """
    required = {
        "animal", "recovery_phenotype", "epoch_label",
        "side", "endpoint", value_col,
    }
    missing = required - set(per_session_df.columns)
    if missing:
        raise ValueError(
            f"per_session_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(per_session_df.columns)}.",
        )

    rows: list[dict[str, object]] = []
    for phenotype in phenotype_order:
        for side in side_order:
            for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
                sub = per_session_df[
                    (per_session_df["recovery_phenotype"] == phenotype)
                    & (per_session_df["side"] == side)
                    & (per_session_df["endpoint"] == endpoint)
                ]
                for post_epoch in POST_EPOCHS:
                    if sub.empty:
                        rows.append(_empty_stats_row(
                            phenotype, side, endpoint, post_epoch,
                        ))
                        continue
                    result = fit_paired_pre_post_wilcoxon(
                        sub,
                        post_epoch=post_epoch,
                        value_col=value_col,
                        aggregator=aggregator,
                    )
                    rows.append({
                        "recovery_phenotype": phenotype,
                        "side": side,
                        "endpoint": endpoint,
                        "post_epoch": post_epoch,
                        "statistic": result.statistic,
                        "p_value": result.p_value,
                        "n_observations": result.n_observations,
                        "status": result.details.get(
                            "status", "unknown",
                        ),
                        "median_diff": result.details.get(
                            "median_diff", float("nan"),
                        ),
                    })

    raw_df = pd.DataFrame(rows)
    # Single BH-FDR family (Addendum #2 D3: one family of 72).
    adjusted = apply_correction_to_results_df(
        raw_df, method="bh_fdr", group_cols=(),
    )
    return adjusted


def _empty_stats_row(
    phenotype: str, side: str, endpoint: str, post_epoch: str,
) -> dict[str, object]:
    """Build a NaN-placeholder row for a cell with zero per-session data."""
    return {
        "recovery_phenotype": phenotype,
        "side": side,
        "endpoint": endpoint,
        "post_epoch": post_epoch,
        "statistic": float("nan"),
        "p_value": float("nan"),
        "n_observations": 0,
        "status": "insufficient_data",
        "median_diff": float("nan"),
    }


# ---------------------------------------------------------------------------
# Stage 4b — figure renderer (6 figures, Q-lock 15 marker convention)
# ---------------------------------------------------------------------------


def figure_path_for(
    *,
    endpoint: str,
    side: str,
    resolver: PathResolver,
    output_dir: Path | None = None,
) -> Path:
    """Resolve the canonical SVG output path under the Q-lock 15 markers."""
    base = (
        output_dir
        if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{endpoint}_{side}_cleaned_trace.svg"


def render_phase_aligned_endpoint_figure(
    per_session_df: pd.DataFrame,
    stats_df: pd.DataFrame,
    *,
    endpoint: str,
    side: str,
    output_path: Path,
    value_col: str = "median",
    display_names: dict[str, str] | None = None,
    dpi: int = 150,
) -> Path:
    """Render one (endpoint, side) figure as SVG.

    Layout: x-axis = epoch label (Pre, Acute, Subacute, Chronic);
    within each epoch, one box per phenotype (mild / moderate /
    mod-severe / severe) showing the distribution of per-session
    values. Individual session dots with jitter overlay each box.
    Title = endpoint display name + side; subtitle = the Q-lock 15
    footer string.

    Parameters
    ----------
    value_col : str, default "median"
        Column to plot. Use ``"median"`` for raw endpoint figures,
        ``"delta_median"`` for baseline-delta figures.
    display_names : dict, optional
        Override ``ENDPOINT_DISPLAY_NAMES`` (used for delta titles).
    """
    names = display_names or ENDPOINT_DISPLAY_NAMES
    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=dpi)

    sub = per_session_df[
        (per_session_df["endpoint"] == endpoint)
        & (per_session_df["side"] == side)
    ]

    rng = np.random.default_rng(seed=42)
    n_phen = len(PHENOTYPE_ORDER)
    box_width = 0.7 / n_phen

    for ei, epoch in enumerate(EPOCH_ORDER):
        for pi, phenotype in enumerate(PHENOTYPE_ORDER):
            cell = sub[
                (sub["epoch_label"] == epoch)
                & (sub["recovery_phenotype"] == phenotype)
            ]
            vals = cell[value_col].to_numpy(dtype=np.float64)
            vals = vals[np.isfinite(vals)]
            pos = ei + (pi - (n_phen - 1) / 2.0) * box_width
            color = phenotype_palette(phenotype)

            if len(vals) == 0:
                continue

            if len(vals) >= 2:
                bp = ax.boxplot(
                    vals,
                    positions=[pos],
                    widths=box_width * 0.85,
                    patch_artist=True,
                    showfliers=False,
                )
                for patch in bp["boxes"]:
                    patch.set_facecolor(color)
                    patch.set_alpha(0.45)
                    patch.set_edgecolor("black")
                    patch.set_linewidth(0.5)
                for whisker in bp["whiskers"] + bp["caps"]:
                    whisker.set_color("black")
                    whisker.set_linewidth(0.5)
                for median_line in bp["medians"]:
                    median_line.set_color("black")
                    median_line.set_linewidth(1.2)

            # Session dots with jitter (always, regardless of n).
            jitter = rng.uniform(
                -box_width * 0.3, box_width * 0.3, size=len(vals),
            )
            ax.scatter(
                pos + jitter, vals,
                color=color, s=18, alpha=0.7,
                edgecolor="black", linewidth=0.3, zorder=3,
            )

    ax.set_xticks(list(range(len(EPOCH_ORDER))))
    ax.set_xticklabels(
        [EPOCH_DISPLAY_NAMES.get(e, e) for e in EPOCH_ORDER],
        fontsize=13,
    )
    ax.set_xlabel("Epoch", fontsize=14)
    ax.set_ylabel(names.get(endpoint, endpoint), fontsize=13)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_xlim(-0.5, len(EPOCH_ORDER) - 0.5)

    title = f"{names.get(endpoint, endpoint)} (side={side})"
    fig.suptitle(title, fontsize=14, y=0.98)
    ax.set_title(FIGURE_SUBTITLE, fontsize=10, loc="left")

    handles = []
    for phenotype in PHENOTYPE_ORDER:
        handles.append(plt.Rectangle(
            (0, 0), 1, 1, facecolor=phenotype_palette(phenotype),
            edgecolor="black", linewidth=0.5,
            label=phenotype_display_name(phenotype),
        ))
    ax.legend(handles=handles, loc="best", fontsize=11, framealpha=0.9)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def emit_phase_aligned_endpoint_figures(
    per_session_df: pd.DataFrame,
    stats_df: pd.DataFrame,
    *,
    resolver: PathResolver,
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
) -> dict[str, Any]:
    """Emit 12 figures (6 raw + 6 delta) + manifest + provenance CSVs.

    Raw figures show per-session medians as epoch-binned boxplots with
    session-level jittered dots. Delta figures show the same data
    baseline-normalized per animal (delta = session_median -
    animal_pre_stroke_mean).

    Parameters
    ----------
    per_session_df : pd.DataFrame
        Output of ``attach_phenotype_and_epoch(aggregate_per_session_median_iqr(...))``.
        Must contain ``median``, ``epoch_label``, ``recovery_phenotype``,
        ``animal``, ``side``, ``endpoint`` columns.
    stats_df : pd.DataFrame
        Output of :func:`compute_phase_aligned_endpoint_stats`.
    resolver : PathResolver
    output_dir : Path, optional
        Override the default Q-lock 15 subdir (used by tests).
    overwrite : {"skip", "force", "prompt"}, default "prompt"

    Returns
    -------
    dict
        ``{"OK": [...], "SKIP": [...], "FAIL": [...]}`` plus CSV paths.
    """
    from stroke_orofacial.stats.aggregators import (
        apply_baseline_delta,
        compute_per_animal_baseline,
    )

    out_dir = (
        output_dir
        if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # Compute delta layer.
    baseline = compute_per_animal_baseline(per_session_df)
    delta_df = apply_baseline_delta(per_session_df, baseline)

    results: dict[str, list[Any]] = {"OK": [], "SKIP": [], "FAIL": []}

    def _emit_one(
        df: pd.DataFrame, endpoint: str, side: str,
        filename: str, value_col: str,
        display_names: dict[str, str] | None,
    ) -> None:
        key = (filename.replace("_cleaned_trace.svg", ""), side)
        target = out_dir / filename
        if target.exists() and overwrite == "skip":
            results["SKIP"].append(key)
            return
        if target.exists() and overwrite == "prompt":
            raise RuntimeError(
                f"phase 9.1 Q-lock 13b figure exists at {target}; "
                f"caller must confirm overwrite (GR7).",
            )
        try:
            render_phase_aligned_endpoint_figure(
                per_session_df=df,
                stats_df=stats_df,
                endpoint=endpoint,
                side=side,
                output_path=target,
                value_col=value_col,
                display_names=display_names,
            )
            results["OK"].append(key)
        except Exception as exc:
            results["FAIL"].append((key, repr(exc)))

    # 6 raw figures.
    for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
        for side in SIDE_ORDER:
            _emit_one(
                per_session_df, endpoint, side,
                f"{endpoint}_{side}_cleaned_trace.svg",
                value_col="median",
                display_names=None,
            )

    # 6 delta figures.
    for endpoint in PHASE_ALIGNED_ENDPOINT_SLUGS:
        for side in SIDE_ORDER:
            _emit_one(
                delta_df, endpoint, side,
                f"delta_{endpoint}_{side}_cleaned_trace.svg",
                value_col="delta_median",
                display_names=DELTA_ENDPOINT_DISPLAY_NAMES,
            )

    # Provenance CSVs.
    stats_csv = out_dir / "phase_aligned_endpoint_stats.csv"
    per_session_csv = out_dir / "per_session_medians.csv"
    delta_csv = out_dir / "per_session_delta_medians.csv"
    stats_df.to_csv(stats_csv, index=False)
    per_session_df.to_csv(per_session_csv, index=False)
    delta_df.to_csv(delta_csv, index=False)
    results["stats_csv"] = stats_csv
    results["per_session_csv"] = per_session_csv
    results["delta_csv"] = delta_csv

    # Manifest CSV.
    manifest_csv = out_dir / "emit_manifest.csv"
    manifest_rows = []
    for status in ("OK", "SKIP"):
        for key in results[status]:
            manifest_rows.append({
                "figure": str(key), "status": status, "error": "",
            })
    for key, err in results["FAIL"]:
        manifest_rows.append({
            "figure": str(key), "status": "FAIL", "error": err,
        })
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    results["manifest_csv"] = manifest_csv
    return results
