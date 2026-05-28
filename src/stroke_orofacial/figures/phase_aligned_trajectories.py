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

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.figures.palette import (
    PHENOTYPE_ORDER,
    phenotype_display_name,
    phenotype_palette,
)
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.aggregators import TRAJECTORY_SIGNALS
from stroke_orofacial.stats.models import fit_paired_pre_post_wilcoxon
from stroke_orofacial.stats.multiple_comparisons import (
    apply_correction_to_results_df,
)

# scipy's MWU import is local to compute_trajectory_mwu_stats to keep
# module-level imports cheap.


# Stats family constants (mirrors Q13b's phase_aligned_endpoint_stats).
POST_EPOCHS: tuple[str, ...] = ("acute", "sub_acute", "chronic")
SIDE_ORDER: tuple[str, ...] = ("L", "R")

# Default rendered phase window — clips bin-coverage edge artifacts at
# phase ≈ 0 and ≈ 1 where the synthetic-ILI assumption breaks down
# (only trials whose first-lick-centered window reaches the extreme
# phases contribute, and the actual next-lick timing varies). Q-lock
# 13.3 (2026-05-28). Pooled CSV always carries the full [0, 1] data;
# only the rendered SVG view is clipped.
DEFAULT_PHASE_DISPLAY_WINDOW: tuple[float, float] = (0.05, 0.95)


# Q-lock 13.4 — error band type for the panel ±band overlay. Mean+SEM
# is the canonical default (precision of the mean); mean+SD is an
# alternative emitted into the sd_band/ subdir (shows the per-trial
# value distribution). Priya 2026-05-28 reverted default to SEM after
# eyeballing both; SD plots stay alongside in sd_band/.
ErrorBandType = Literal["sd", "sem"]
DEFAULT_ERROR_BAND_TYPE: ErrorBandType = "sem"

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
    error_band_type: ErrorBandType = DEFAULT_ERROR_BAND_TYPE,
) -> Path:
    """Resolve the canonical SVG output path for one (signal, variant, side, band).

    Filename embeds the error-band type so the SEM and SD variants are
    self-describing even when files are copied out of the canonical
    directory structure (Priya 2026-05-28).
    """
    base = (
        output_dir
        if output_dir is not None
        else resolver.pipeline_outputs(subdir=FIGURE_SUBDIR)
    )
    base.mkdir(parents=True, exist_ok=True)
    band_slug = "mean_sem" if error_band_type == "sem" else "mean_sd"
    return base / (
        f"{signal}_{variant}_{side}_{band_slug}_cleaned_trace.svg"
    )


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
    phase_display_window: tuple[float, float] = DEFAULT_PHASE_DISPLAY_WINDOW,
    error_band_type: ErrorBandType = DEFAULT_ERROR_BAND_TYPE,
    phenotype_order: tuple[str, ...] = PHENOTYPE_ORDER,
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
    # Apply the display-window clip on phase_bin_center if available.
    # When phase_bin_center is missing (older callers), fall through
    # without filtering — clip is render-time-only and graceful.
    lo, hi = float(phase_display_window[0]), float(phase_display_window[1])
    if lo > hi:
        raise ValueError(
            f"phase_display_window lo must be <= hi; got ({lo}, {hi}).",
        )

    sub = pooled_df[
        (pooled_df["signal"] == signal)
        & (pooled_df["variant"] == variant)
        & (pooled_df["side"] == side)
    ]
    if "phase_bin_center" in sub.columns:
        center = pd.to_numeric(sub["phase_bin_center"], errors="coerce")
        sub = sub.loc[(center >= lo) & (center <= hi)]

    if error_band_type not in ("sd", "sem"):
        raise ValueError(
            f"error_band_type must be 'sd' or 'sem'; got {error_band_type!r}.",
        )

    phenotype_order = tuple(phenotype_order)
    if not phenotype_order:
        raise ValueError("phenotype_order must contain at least one phenotype.")

    fig, axes = plt.subplots(
        nrows=len(phenotype_order),
        ncols=len(EPOCH_ORDER),
        figsize=(16.0, 3.0 * len(phenotype_order)),
        dpi=dpi,
        sharex=True,
        sharey="all",
    )
    # Guarantee 2-D ndarray indexing even when nrows == 1.
    if axes.ndim == 1:
        axes = axes[None, :]

    for row_idx, phenotype in enumerate(phenotype_order):
        color = phenotype_palette(phenotype)
        # Empty cell row when this phenotype has no rows in the input
        # (e.g., 3-tier remap dropped 'moderate-severe' but pooled_df
        # still has 4-tier rows from a stale cache). Continue gracefully.
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
            band_col = error_band_type
            if band_col not in panel.columns:
                # Older pooled CSV without sd column → fall back to sem.
                band_col = "sem"
            y_err = panel[band_col].to_numpy(dtype=np.float64)

            # ±1 (sd|sem) band where the band statistic is finite (n=1
            # bins skipped from the band but still drawn on the mean
            # line).
            err_finite = np.isfinite(y_err) & np.isfinite(y_mean)
            if err_finite.any():
                ax.fill_between(
                    x[err_finite],
                    (y_mean - y_err)[err_finite],
                    (y_mean + y_err)[err_finite],
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
            if row_idx == len(phenotype_order) - 1:
                ax.set_xlabel(
                    f"Phase ∈ [{lo:g}, {hi:g}]"
                    if (lo, hi) != (0.0, 1.0)
                    else "Phase ∈ [0, 1]",
                    fontsize=10,
                )

            ax.set_xlim(lo, hi)
            ax.tick_params(axis="both", labelsize=8)

    # Outer title (signal + variant + side); subtitles below:
    # 1) source-data description (variant-aware) + band-type tag,
    # 2) Q-lock 15 cleaned_trace provenance footer.
    signal_label = SIGNAL_DISPLAY_NAMES.get(signal, signal)
    variant_label = VARIANT_DISPLAY_NAMES.get(variant, variant)
    band_tag = "mean ± SEM" if error_band_type == "sem" else "mean ± SD"
    title = f"{signal_label} — {variant_label} — side={side} ({band_tag})"
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
    phase_display_window: tuple[float, float] = DEFAULT_PHASE_DISPLAY_WINDOW,
    error_band_type: ErrorBandType = DEFAULT_ERROR_BAND_TYPE,
    phenotype_order: tuple[str, ...] = PHENOTYPE_ORDER,
) -> Path:
    """Build the figure and save it as SVG.

    Thin wrapper over :func:`build_phase_aligned_trajectory_figure` that
    persists to disk and closes the figure. Returns the saved path.
    """
    fig, _ = build_phase_aligned_trajectory_figure(
        pooled_df, signal=signal, variant=variant, side=side, dpi=dpi,
        phase_display_window=phase_display_window,
        error_band_type=error_band_type,
        phenotype_order=phenotype_order,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def compute_trajectory_wilcoxon_stats(
    per_animal_scalar_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Paired pre-vs-post Wilcoxon family on per-animal trajectory scalars.

    Q-lock 13.1 follow-on stats (2026-05-28). Trajectory analog of
    Q13b's :func:`compute_phase_aligned_endpoint_stats`. For each
    (phenotype, side, signal, post_epoch) cell — 48 total at the
    8-animal cohort scale (4 phen × 2 sides × 2 signals × 3 post
    epochs) — filters the per-animal scalars to that cell, calls
    :func:`stroke_orofacial.stats.models.fit_paired_pre_post_wilcoxon`
    with ``aggregator="mean"`` + ``value_col="scalar"`` and post_epoch
    = the column-cell epoch, then applies a single BH-FDR family-wide
    adjustment across all 48 tests.

    The per-animal scalar (output of
    :func:`stroke_orofacial.stats.aggregators.compute_per_animal_trajectory_scalar`)
    is the cross-trial × cross-bin mean of per-trial frame-means within
    each (animal, side, signal, epoch_label). Conceptually: the
    time-averaged signal value over one ILI cycle for that animal in
    that epoch + side.

    NaN-aware: n=1 phenotypes (currently moderate / mod-severe per F-P-1)
    return ``status="insufficient_data"`` + NaN p-value, and BH-FDR
    propagates NaN through (those rows excluded from rank-based
    adjustment).

    Parameters
    ----------
    per_animal_scalar_df : pd.DataFrame
        Output of :func:`compute_per_animal_trajectory_scalar`. Required
        columns: ``animal``, ``side``, ``signal``, ``epoch_label``,
        ``scalar``.
    animals_map : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo for the cohort. Used to attach
        ``recovery_phenotype``.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``side``, ``signal``,
        ``post_epoch``, ``statistic``, ``p_value``, ``n_observations``,
        ``status``, ``median_diff``, ``p_adj``, ``reject``.
    """
    signals = tuple(signals)
    required = {"animal", "side", "signal", "epoch_label", "scalar"}
    missing = required - set(per_animal_scalar_df.columns)
    if missing:
        raise ValueError(
            f"per_animal_scalar_df missing required column(s) "
            f"{sorted(missing)}; got {list(per_animal_scalar_df.columns)}.",
        )

    # Attach recovery_phenotype.
    df = per_animal_scalar_df.copy()
    df["recovery_phenotype"] = df["animal"].map(
        lambda a: (
            animals_map[a].recovery_phenotype
            if a in animals_map and animals_map[a].recovery_phenotype is not None
            else None
        )
    )
    df = df.dropna(subset=["recovery_phenotype"])

    rows: list[dict[str, object]] = []
    for phenotype in PHENOTYPE_ORDER:
        for side in SIDE_ORDER:
            for signal in signals:
                sub = df[
                    (df["recovery_phenotype"] == phenotype)
                    & (df["side"] == side)
                    & (df["signal"] == signal)
                ]
                for post_epoch in POST_EPOCHS:
                    result = fit_paired_pre_post_wilcoxon(
                        sub,
                        post_epoch=post_epoch,
                        value_col="scalar",
                        aggregator="mean",
                    )
                    rows.append({
                        "recovery_phenotype": phenotype,
                        "side": side,
                        "signal": signal,
                        "post_epoch": post_epoch,
                        "statistic": result.statistic,
                        "p_value": result.p_value,
                        "n_observations": result.n_observations,
                        "status": result.details.get("status", "unknown"),
                        "median_diff": result.details.get(
                            "median_diff", float("nan"),
                        ),
                    })

    out = pd.DataFrame(rows)
    # Single 48-test family across (phenotype × side × signal × post_epoch);
    # no inner family partition — pass group_cols=() to disable it.
    out = apply_correction_to_results_df(
        out, p_value_col="p_value", method="bh_fdr", group_cols=(),
    )
    return out


def compute_trajectory_mwu_stats(
    per_x_scalar_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    grain: Literal["trial", "session"] = "trial",
) -> pd.DataFrame:
    """Unpaired Mann-Whitney U family on per-trial OR per-session scalars.

    Q-lock 13.5 (2026-05-28). Complementary to the per-animal paired
    Wilcoxon (:func:`compute_trajectory_wilcoxon_stats`). Trades the
    pairing structure (which gives more power per animal) for raw n
    inflation (treats each trial / session as an independent
    observation).

    **Pseudo-replication caveat.** Trials within an animal-session and
    sessions within an animal share latent variables (the same animal's
    motor cortex, mouth geometry, daily state); treating them as iid
    inflates power and Type I error vs a properly-modeled mixed-effects
    test. The MWU p-values here should be interpreted as visualization
    aids, not as the primary inferential test. The per-animal paired
    Wilcoxon remains the canonical statistical claim.

    Family size: 4 phenotypes × 2 sides × 2 signals × 3 post epochs =
    48 tests. Single BH-FDR family-wide correction.

    Parameters
    ----------
    per_x_scalar_df : pd.DataFrame
        Output of
        :func:`stroke_orofacial.stats.aggregators.compute_per_trial_trajectory_scalar`
        (when ``grain="trial"``) or
        :func:`stroke_orofacial.stats.aggregators.compute_per_session_trajectory_scalar`
        (when ``grain="session"``). Required columns: ``animal``,
        ``side``, ``signal``, ``epoch_label``, ``scalar``.
    animals_map : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo for the cohort. Used to attach
        ``recovery_phenotype``.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``
    grain : {"trial", "session"}, default "trial"
        Annotated into ``grain`` column of output for downstream
        readers.

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``side``, ``signal``,
        ``post_epoch``, ``grain``, ``statistic``, ``p_value``,
        ``n_pre``, ``n_post``, ``status``, ``p_adj``, ``reject``.
    """
    from scipy.stats import mannwhitneyu

    signals = tuple(signals)
    if grain not in ("trial", "session"):
        raise ValueError(f"grain must be 'trial' or 'session'; got {grain!r}.")
    required = {"animal", "side", "signal", "epoch_label", "scalar"}
    missing = required - set(per_x_scalar_df.columns)
    if missing:
        raise ValueError(
            f"per_x_scalar_df missing required column(s) {sorted(missing)}; "
            f"got {list(per_x_scalar_df.columns)}.",
        )

    df = per_x_scalar_df.copy()
    df["recovery_phenotype"] = df["animal"].map(
        lambda a: (
            animals_map[a].recovery_phenotype
            if a in animals_map and animals_map[a].recovery_phenotype is not None
            else None
        )
    )
    df = df.dropna(subset=["recovery_phenotype"])

    rows: list[dict[str, object]] = []
    for phenotype in PHENOTYPE_ORDER:
        for side in SIDE_ORDER:
            for signal in signals:
                sub = df[
                    (df["recovery_phenotype"] == phenotype)
                    & (df["side"] == side)
                    & (df["signal"] == signal)
                ]
                pre_vals = sub.loc[
                    sub["epoch_label"] == "pre", "scalar",
                ].to_numpy(dtype=np.float64)
                pre_vals = pre_vals[np.isfinite(pre_vals)]
                for post_epoch in POST_EPOCHS:
                    post_vals = sub.loc[
                        sub["epoch_label"] == post_epoch, "scalar",
                    ].to_numpy(dtype=np.float64)
                    post_vals = post_vals[np.isfinite(post_vals)]
                    n_pre = int(pre_vals.size)
                    n_post = int(post_vals.size)
                    row = {
                        "recovery_phenotype": phenotype,
                        "side": side,
                        "signal": signal,
                        "post_epoch": post_epoch,
                        "grain": grain,
                        "n_pre": n_pre,
                        "n_post": n_post,
                    }
                    if n_pre < 1 or n_post < 1:
                        row["statistic"] = float("nan")
                        row["p_value"] = float("nan")
                        row["status"] = "insufficient_data"
                        rows.append(row)
                        continue
                    res = mannwhitneyu(
                        post_vals, pre_vals,
                        alternative="two-sided",
                    )
                    row["statistic"] = float(res.statistic)
                    row["p_value"] = float(res.pvalue)
                    row["status"] = "ok"
                    rows.append(row)

    out = pd.DataFrame(rows)
    out = apply_correction_to_results_df(
        out, p_value_col="p_value", method="bh_fdr", group_cols=(),
    )
    return out


def emit_phase_aligned_trajectory_figures(
    pooled_df: pd.DataFrame,
    *,
    resolver: PathResolver,
    sides: Iterable[str] = ("L", "R"),
    signals: Iterable[str] = ("angle_deg", "x_centered"),
    variants: Iterable[str] = ("raw", "delta"),
    output_dir: Path | None = None,
    overwrite: Literal["skip", "force", "prompt"] = "prompt",
    phase_display_window: tuple[float, float] = DEFAULT_PHASE_DISPLAY_WINDOW,
    error_band_type: ErrorBandType = DEFAULT_ERROR_BAND_TYPE,
    phenotype_order: tuple[str, ...] = PHENOTYPE_ORDER,
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
                    error_band_type=error_band_type,
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
                    phase_display_window=phase_display_window,
                    error_band_type=error_band_type,
                    phenotype_order=phenotype_order,
                )
                emitted.append(output_path)
    return {"emitted": emitted, "skipped": skipped}
