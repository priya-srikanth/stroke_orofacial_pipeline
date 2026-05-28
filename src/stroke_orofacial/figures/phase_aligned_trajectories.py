"""Phase 9.1 Q-lock 13 — phase-aligned mean+SEM trajectory figures.

Renders the 8 trajectory figures consumed by the Q-lock 13 cohort emit:
2 signals (``angle_deg``, ``x_centered``) × 2 variants (raw, delta) ×
2 sides (L, R). Each figure is a 4 × 4 grid of panels — rows = phenotype
(mild / moderate / mod-severe / severe per Q-lock 1 / F-P-1); columns =
epoch (pre / acute / sub_acute / chronic per
:func:`stroke_orofacial.stats.recovery_epochs.assign_epoch_label`).

Per-panel content (locked decisions from kickoff):
- **Q13-B:** mean trajectory line + ±1 SEM band (parametric).
- **Q13-D:** trace color = phenotype YlOrRd shade; all 4 epoch panels in
  a phenotype row share the same color (epoch differentiation comes
  from column position).
- **Q13-E:** post-epoch panels (acute / sub_acute / chronic) overlay a
  dashed grey trace = the same phenotype's pre-stroke mean trajectory
  (sourced from the ``epoch_label == "pre"`` row of the same pooled
  DataFrame). Pre column does not overlay (it IS the baseline trace).
- **Q13-F:** ``n=N trials`` annotation, top-right of each panel, small
  font. ``N`` is the maximum of ``n_trials`` across phase_bins in the
  panel (every trial contributes to ~every bin via the centered phase
  cycle; max is a tight upper bound on panel coverage).

Output convention (Q-lock 15 three-layer cleaned_trace markers; output
dir corrected per Q-lock 13b precedent to land under the existing
``stats/figures/phenotype_pooled/`` tree rather than a new
``phase_9_1_figures/`` tree):

- Directory: ``stats/figures/phenotype_pooled/phase_aligned_trajectories/``
- Filename: ``<signal>_<variant>_<side>_mean_sem_cleaned_trace.svg``
  e.g. ``angle_deg_raw_L_mean_sem_cleaned_trace.svg``.
- Footer (figure subtitle): ``Source: v7-cleaned-trace cohort re-emit
  (Phase 7e + Phase 7e.4)``
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

# Output layout (Q-lock 15 marker convention; subdir mirrors Q13b
# correction 2026-05-27 — figures land under stats/figures/phenotype_pooled/
# alongside V4/V5 and Q13b endpoint-stats figures, NOT under a separate
# phase_9_1_figures/ tree).
FIGURE_SUBDIR: str = (
    "stats/figures/phenotype_pooled/phase_aligned_trajectories"
)
FIGURE_SUBTITLE: str = (
    "Source: v7-cleaned-trace cohort re-emit (Phase 7e + Phase 7e.4)"
)

# Column ordering for the 4×4 panel grid.
EPOCH_ORDER: tuple[str, ...] = ("pre", "acute", "sub_acute", "chronic")

# Display names matching Q13b endpoint-stats figures (capitalized;
# Subacute as one word per 2026-05-27 review).
EPOCH_DISPLAY_NAMES: dict[str, str] = {
    "pre": "Pre",
    "acute": "Acute",
    "sub_acute": "Subacute",
    "chronic": "Chronic",
}

# Human-readable axis labels for the two trajectory signals.
SIGNAL_DISPLAY_NAMES: dict[str, str] = {
    "angle_deg": "Tongue angle (deg)",
    "x_centered": "Tongue x (spout-midpoint frame, px)",
}

VARIANT_DISPLAY_NAMES: dict[str, str] = {
    "raw": "raw",
    "delta": "Δ from per-animal pre-stroke baseline",
}


# Source-data subtitle — one line under the figure suptitle, describing
# the substrate phase definition + (for delta) the normalization rule.
# Distinct from FIGURE_SUBTITLE which is the Q-lock 15 cleaned_trace
# provenance footer (stays at the bottom).
SOURCE_DATA_SUBTITLE_RAW: str = (
    "Source data: first-lick centered phase ∈ [0, 1] "
    "(one inter-lick-interval window centered on first detected lick peak)"
)
SOURCE_DATA_SUBTITLE_DELTA: str = (
    "Source data: first-lick centered phase ∈ [0, 1]; "
    "Δ = trial signal − per-(animal, side, phase bin) pre-stroke baseline"
)


def _source_data_subtitle(variant: str) -> str:
    """Return the variant-appropriate source-data subtitle line."""
    if variant == "delta":
        return SOURCE_DATA_SUBTITLE_DELTA
    return SOURCE_DATA_SUBTITLE_RAW


def figure_path_for(
    *,
    signal: str,
    variant: str,
    side: str,
    resolver: PathResolver,
    output_dir: Path | None = None,
) -> Path:
    """Resolve the canonical SVG output path for one (signal, variant, side)."""
    base = (
        output_dir
        if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{signal}_{variant}_{side}_mean_sem_cleaned_trace.svg"


def _panel_x_axis(panel: pd.DataFrame) -> np.ndarray:
    """Return per-row x coordinate. Prefer ``phase_bin_center``;
    fall back to ``phase_bin / max(phase_bin)`` if center missing.
    """
    if (
        "phase_bin_center" in panel.columns
        and not panel["phase_bin_center"].isna().all()
    ):
        return panel["phase_bin_center"].to_numpy(dtype=np.float64)
    bins = panel["phase_bin"].to_numpy(dtype=np.float64)
    n = float(max(1.0, bins.max() if bins.size else 1.0))
    return bins / n


def build_phase_aligned_trajectory_figure(
    pooled_df: pd.DataFrame,
    *,
    signal: str,
    variant: str,
    side: str,
    dpi: int = 150,
) -> tuple[plt.Figure, np.ndarray]:
    """Build the matplotlib Figure for one (signal, variant, side) figure.

    Public Figure-returning entry point separated from
    :func:`render_phase_aligned_trajectory_figure` so tests can inspect
    the in-memory structure (panel count, axes labels, title, n-annotation
    text) without depending on the SVG roundtrip.

    Parameters
    ----------
    pooled_df : pd.DataFrame
        Output of :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_phase_bin_mean_sem`.
        Required columns: ``recovery_phenotype``, ``epoch_label``,
        ``side``, ``phase_bin``, ``signal``, ``variant``, ``mean``,
        ``sem``, ``n_trials``. ``phase_bin_center`` is preferred for the
        panel x-axis but optional (falls back to ``phase_bin / max``).
    signal : str
        One of the substrate signal column names (``"angle_deg"`` /
        ``"x_centered"``).
    variant : str
        ``"raw"`` or ``"delta"``.
    side : str
        ``"L"`` or ``"R"``.
    dpi : int, default 150

    Returns
    -------
    (Figure, axes_array)
        Caller is responsible for ``plt.close(fig)`` after consuming.
    """
    sub = pooled_df[
        (pooled_df["signal"] == signal)
        & (pooled_df["variant"] == variant)
        & (pooled_df["side"] == side)
    ]

    fig, axes = plt.subplots(
        nrows=len(PHENOTYPE_ORDER),
        ncols=len(EPOCH_ORDER),
        figsize=(16.0, 12.0),
        dpi=dpi,
        sharex=True,
        sharey="row",
    )

    for row_idx, phenotype in enumerate(PHENOTYPE_ORDER):
        color = phenotype_palette(phenotype)
        # Pre-stroke baseline trace within this phenotype × side, for
        # the dashed grey overlay on post-epoch panels.
        pre_panel = sub[
            (sub["recovery_phenotype"] == phenotype)
            & (sub["epoch_label"] == "pre")
        ].sort_values("phase_bin")
        if pre_panel.empty:
            pre_x = np.zeros(0)
            pre_y = np.zeros(0)
        else:
            pre_x = _panel_x_axis(pre_panel)
            pre_y = pre_panel["mean"].to_numpy(dtype=np.float64)

        for col_idx, epoch in enumerate(EPOCH_ORDER):
            ax = axes[row_idx, col_idx]
            panel = sub[
                (sub["recovery_phenotype"] == phenotype)
                & (sub["epoch_label"] == epoch)
            ].sort_values("phase_bin")

            # Per-panel sample size: max(n_trials) across bins (every
            # trial contributes to ~every bin via the centered cycle).
            if not panel.empty and "n_trials" in panel.columns:
                n_finite = panel["n_trials"].to_numpy(dtype=np.float64)
                n_max = int(np.nanmax(n_finite)) if n_finite.size else 0
            else:
                n_max = 0

            ax.annotate(
                f"n={n_max} trials",
                xy=(0.98, 0.95), xycoords="axes fraction",
                ha="right", va="top", fontsize=8,
            )

            if panel.empty:
                # Empty cell — keep frame for grid uniformity, only
                # show the n=0 annotation we already added.
                if row_idx == 0:
                    ax.set_title(
                        EPOCH_DISPLAY_NAMES.get(epoch, epoch),
                        fontsize=12,
                    )
                if col_idx == 0:
                    ax.set_ylabel(
                        phenotype_display_name(phenotype),
                        fontsize=11,
                    )
                continue

            x = _panel_x_axis(panel)
            y_mean = panel["mean"].to_numpy(dtype=np.float64)
            y_sem = panel["sem"].to_numpy(dtype=np.float64)

            # ±1 SEM band where SEM is finite (n=1 bins skipped from
            # the band but still drawn on the mean line).
            sem_finite = np.isfinite(y_sem) & np.isfinite(y_mean)
            if sem_finite.any():
                ax.fill_between(
                    x[sem_finite],
                    (y_mean - y_sem)[sem_finite],
                    (y_mean + y_sem)[sem_finite],
                    color=color, alpha=0.25, linewidth=0,
                )
            ax.plot(x, y_mean, color=color, linewidth=1.5)

            # Q13-E: post-epoch panels overlay the phenotype's pre
            # trajectory as dashed grey. Pre column shows the trace
            # directly; no overlay.
            if epoch != "pre" and pre_y.size > 0:
                ax.plot(
                    pre_x, pre_y,
                    color="grey", linestyle="--", linewidth=1.0,
                    alpha=0.75, zorder=1,
                )

            # Per-row + per-column axis labels.
            if row_idx == 0:
                ax.set_title(
                    EPOCH_DISPLAY_NAMES.get(epoch, epoch),
                    fontsize=12,
                )
            if col_idx == 0:
                ax.set_ylabel(
                    phenotype_display_name(phenotype),
                    fontsize=11,
                )
            if row_idx == len(PHENOTYPE_ORDER) - 1:
                ax.set_xlabel("Phase ∈ [0, 1]", fontsize=10)

            ax.tick_params(axis="both", labelsize=8)

    # Outer title (signal + variant + side); two subtitles below it:
    # 1) source-data description (variant-aware), 2) Q-lock 15
    # cleaned_trace provenance footer.
    signal_label = SIGNAL_DISPLAY_NAMES.get(signal, signal)
    variant_label = VARIANT_DISPLAY_NAMES.get(variant, variant)
    title = f"{signal_label} — {variant_label} — side={side}"
    fig.suptitle(title, fontsize=14, y=0.995)
    fig.text(
        0.5, 0.970, _source_data_subtitle(variant),
        ha="center", va="top", fontsize=9,
    )
    fig.text(
        0.5, 0.948, FIGURE_SUBTITLE,
        ha="center", va="top", fontsize=8, style="italic",
    )

    # Outer y-label = signal display name (helps when stripchart-style
    # readers scan the figure).
    fig.text(
        0.005, 0.5, signal_label,
        ha="left", va="center", rotation=90, fontsize=12,
    )

    fig.tight_layout(rect=[0.02, 0.0, 1.0, 0.925])
    return fig, axes


def render_phase_aligned_trajectory_figure(
    pooled_df: pd.DataFrame,
    *,
    signal: str,
    variant: str,
    side: str,
    output_path: Path,
    dpi: int = 150,
) -> Path:
    """Build the figure and save it as SVG.

    Thin wrapper over :func:`build_phase_aligned_trajectory_figure` that
    persists to disk and closes the figure. Returns the saved path.
    """
    fig, _ = build_phase_aligned_trajectory_figure(
        pooled_df, signal=signal, variant=variant, side=side, dpi=dpi,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def emit_phase_aligned_trajectory_figures(
    pooled_df: pd.DataFrame,
    *,
    resolver: PathResolver,
    sides: Iterable[str] = ("L", "R"),
    signals: Iterable[str] = ("angle_deg", "x_centered"),
    variants: Iterable[str] = ("raw", "delta"),
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
) -> dict[str, Any]:
    """Emit all 8 trajectory figures + a manifest dict.

    For each (signal, variant, side) triple in the Cartesian product,
    renders one figure to the canonical Q-lock 15 path. Same
    confirm-once-then-force pattern as Q13b's emit_phase_aligned_endpoint_figures.

    Parameters
    ----------
    pooled_df : pd.DataFrame
        Output of :func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_phase_bin_mean_sem`.
    resolver : PathResolver
    sides, signals, variants : Iterable[str]
        Override defaults to render a subset. Defaults render all 8
        figures.
    output_dir : Path, optional
        Override the canonical figure subdir (used by tests with
        ``tmp_path``).
    overwrite : {"skip", "force", "prompt"}, default "prompt"
        ``"skip"``: any existing target path is left as-is + recorded
        as skipped. ``"force"``: existing files are overwritten without
        prompting. ``"prompt"``: first existing target prompts once;
        subsequent existing targets follow the answer (Q-lock 13b
        emit_cohort.py precedent).

    Returns
    -------
    dict
        ``{"emitted": [Path, ...], "skipped": [Path, ...]}``.
    """
    emitted: list[Path] = []
    skipped: list[Path] = []
    effective_overwrite: str = overwrite

    for signal in signals:
        for variant in variants:
            for side in sides:
                output_path = figure_path_for(
                    signal=signal, variant=variant, side=side,
                    resolver=resolver, output_dir=output_dir,
                )
                if output_path.exists():
                    if effective_overwrite == "skip":
                        skipped.append(output_path)
                        continue
                    if effective_overwrite == "prompt":
                        # Confirm-once-then-force pattern.
                        ans = input(
                            f"{output_path} exists. Overwrite all? "
                            f"[y/N]: "
                        ).strip().lower()
                        if ans not in {"y", "yes"}:
                            skipped.append(output_path)
                            effective_overwrite = "skip"
                            continue
                        effective_overwrite = "force"
                render_phase_aligned_trajectory_figure(
                    pooled_df,
                    signal=signal, variant=variant, side=side,
                    output_path=output_path,
                )
                emitted.append(output_path)
    return {"emitted": emitted, "skipped": skipped}
