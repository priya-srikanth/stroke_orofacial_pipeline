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
from stroke_orofacial.stats.models import (
    fit_paired_pre_post_wilcoxon,
    fit_per_epoch_lmm,
)
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


def compute_trajectory_lmm_stats(
    per_session_scalar_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Per-(phenotype × side × signal) LMM: ``scalar ~ epoch + (1|animal)``.

    Q-lock 13.6 (2026-05-28). Proper inferential test that respects
    within-animal correlation — addresses the pseudo-replication that
    inflates the MWU at trial/session grain. Random intercept per
    animal absorbs between-animal baseline offsets; fixed-effect
    coefficient for each post-epoch tests "this epoch differs from
    pre by X units" controlling for animal identity.

    Wraps :func:`stroke_orofacial.stats.models.fit_per_epoch_lmm` with
    one fit per (phenotype × side × signal) cell. Each fit yields per
    (post_epoch) coefficient + p-value (from the categorical
    parameterization with pre as the reference level). After all fits,
    BH-FDR correction across the family.

    Parameters
    ----------
    per_session_scalar_df : pd.DataFrame
        Output of
        :func:`stroke_orofacial.stats.aggregators.compute_per_session_trajectory_scalar`.
        Required columns: ``animal``, ``side``, ``signal``,
        ``epoch_label``, ``scalar``.
    animals_map : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo for cohort.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``.

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``side``, ``signal``,
        ``post_epoch``, ``coef``, ``se``, ``p_value``,
        ``n_observations``, ``n_animals``, ``status``, ``p_adj``,
        ``reject``.
    """
    signals = tuple(signals)
    required = {"animal", "side", "signal", "epoch_label", "scalar"}
    missing = required - set(per_session_scalar_df.columns)
    if missing:
        raise ValueError(
            f"per_session_scalar_df missing column(s) {sorted(missing)}.",
        )

    df = per_session_scalar_df.copy()
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
                n_animals = int(sub["animal"].nunique())
                if n_animals < 2 or len(sub) < 5:
                    for post_epoch in POST_EPOCHS:
                        rows.append({
                            "recovery_phenotype": phenotype,
                            "side": side, "signal": signal,
                            "post_epoch": post_epoch,
                            "coef": float("nan"), "se": float("nan"),
                            "p_value": float("nan"),
                            "n_observations": int(len(sub)),
                            "n_animals": n_animals,
                            "status": "insufficient_data",
                        })
                    continue
                result = fit_per_epoch_lmm(
                    sub, value_col="scalar",
                    epoch_col="epoch_label", animal_col="animal",
                )
                per_epoch = result.details.get("per_epoch", {})
                status_root = result.details.get("status", "unknown")
                for post_epoch in POST_EPOCHS:
                    if post_epoch in per_epoch:
                        rec = per_epoch[post_epoch]
                        rows.append({
                            "recovery_phenotype": phenotype,
                            "side": side, "signal": signal,
                            "post_epoch": post_epoch,
                            "coef": rec["coef"],
                            "se": rec["se"],
                            "p_value": rec["p_value"],
                            "n_observations": result.n_observations,
                            "n_animals": n_animals,
                            "status": status_root,
                        })
                    else:
                        rows.append({
                            "recovery_phenotype": phenotype,
                            "side": side, "signal": signal,
                            "post_epoch": post_epoch,
                            "coef": float("nan"), "se": float("nan"),
                            "p_value": float("nan"),
                            "n_observations": result.n_observations,
                            "n_animals": n_animals,
                            "status": status_root,
                        })

    out = pd.DataFrame(rows)
    out = apply_correction_to_results_df(
        out, p_value_col="p_value", method="bh_fdr", group_cols=(),
    )
    return out


def _per_bin_t_stat(
    pre_arr: np.ndarray, post_arr: np.ndarray,
) -> np.ndarray:
    """Welch's per-bin t-statistic between two (n_obs, n_bins) arrays."""
    n_pre = pre_arr.shape[0]
    n_post = post_arr.shape[0]
    if n_pre < 2 or n_post < 2:
        return np.full(pre_arr.shape[1], np.nan)
    m_pre = np.nanmean(pre_arr, axis=0)
    m_post = np.nanmean(post_arr, axis=0)
    v_pre = np.nanvar(pre_arr, axis=0, ddof=1)
    v_post = np.nanvar(post_arr, axis=0, ddof=1)
    se = np.sqrt(v_pre / n_pre + v_post / n_post)
    se = np.where(se > 0, se, np.nan)
    return (m_post - m_pre) / se


def _find_clusters_above_threshold(
    t_arr: np.ndarray, threshold: float,
) -> list[dict[str, float]]:
    """Find runs of consecutive bins where |t| > threshold.

    Returns a list of dicts ``{start_bin, end_bin, mass, sign}`` —
    one per contiguous cluster. ``mass`` is the sum of |t| within the
    cluster; ``sign`` is +1 if mean(t) > 0, -1 otherwise.
    """
    finite = np.isfinite(t_arr)
    sig = (np.abs(t_arr) > threshold) & finite
    clusters: list[dict[str, float]] = []
    i = 0
    n = len(t_arr)
    while i < n:
        if not sig[i]:
            i += 1
            continue
        j = i
        while j < n and sig[j]:
            j += 1
        # cluster spans [i, j)
        chunk = t_arr[i:j]
        mass = float(np.nansum(np.abs(chunk)))
        sign = float(np.sign(np.nanmean(chunk)))
        clusters.append({
            "start_bin": int(i), "end_bin": int(j - 1),
            "mass": mass, "sign": sign,
        })
        i = j
    return clusters


def compute_trajectory_cluster_permutation_stats(
    densified_cohort_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    variants: Iterable[str] = ("raw", "delta"),
    n_permutations: int = 5000,
    t_threshold: float = 2.0,
    rng_seed: int = 42,
) -> pd.DataFrame:
    """Maris-Oostenveld cluster-based permutation test on session trajectories.

    Q-lock 13.6 (2026-05-28). Gold-standard trajectory comparison:
    properly accounts for adjacent-bin correlation that per-bin
    BH-FDR ignores. Per (phenotype × side × signal × variant ×
    post_epoch), pools session-grain trajectories pre vs post_epoch,
    computes per-bin Welch's t-statistic, identifies clusters of
    adjacent bins where |t| > ``t_threshold``, computes
    cluster-mass = sum |t|. Permutes the pre↔post_epoch session
    labels ``n_permutations`` times, recomputes max cluster-mass
    under the null. P-value per observed cluster = fraction of null
    max cluster-mass ≥ observed.

    Permutation is INDEPENDENT per post_epoch comparison (pre vs
    acute is its own permutation; pre vs sub_acute is its own; etc.).
    No shared null across the family. BH-FDR across all observed
    clusters in the family for the ``p_adj`` column.

    Parameters
    ----------
    densified_cohort_df : pd.DataFrame
        Output of
        :func:`stroke_orofacial.stats.aggregators.densify_phase_rows_via_interp`
        + ``attach_metadata``. Required columns: ``animal``, ``date``,
        ``side``, ``phase_bin``, ``epoch_label``,
        ``recovery_phenotype``, plus one column per ``signals`` entry
        (raw) and one ``<signal>_delta`` column per signal (delta).
    animals_map : Mapping[str, AnimalInfo]
        Used to attach recovery_phenotype if not already in input.
        Kept in signature for API parity; phenotype must already be
        attached.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``.
    variants : Iterable[str], default ``("raw", "delta")``.
    n_permutations : int, default 5000.
    t_threshold : float, default 2.0
        Bin-level threshold for cluster detection. Roughly 2-sided
        alpha=0.05 at small dof; standard convention is t=2.
    rng_seed : int, default 42.

    Returns
    -------
    pd.DataFrame
        One row per observed cluster, or one row with status="no_cluster"
        per cell with no observed cluster. Columns:
        ``recovery_phenotype``, ``side``, ``signal``, ``variant``,
        ``post_epoch``, ``cluster_idx``, ``start_bin``, ``end_bin``,
        ``cluster_mass``, ``sign`` (direction of bins), ``p_value``,
        ``n_pre``, ``n_post``, ``status``, ``p_adj``, ``reject``.
    """
    signals = tuple(signals)
    variants = tuple(variants)
    if not 1 <= n_permutations <= 100000:
        raise ValueError(
            f"n_permutations must be in [1, 100000]; got {n_permutations}.",
        )

    rng = np.random.default_rng(rng_seed)
    required = {
        "animal", "date", "side", "phase_bin", "epoch_label",
        "recovery_phenotype",
    }
    for s in signals:
        if "raw" in variants:
            required.add(s)
        if "delta" in variants:
            required.add(f"{s}_delta")
    missing = required - set(densified_cohort_df.columns)
    if missing:
        raise ValueError(
            f"densified_cohort_df missing column(s) {sorted(missing)}.",
        )

    rows: list[dict[str, object]] = []
    for phenotype in PHENOTYPE_ORDER:
        for side in SIDE_ORDER:
            for signal in signals:
                for variant in variants:
                    value_col = signal if variant == "raw" else f"{signal}_delta"
                    sub = densified_cohort_df[
                        (densified_cohort_df["recovery_phenotype"] == phenotype)
                        & (densified_cohort_df["side"] == side)
                    ][[
                        "animal", "date", "phase_bin", "epoch_label",
                        value_col,
                    ]].copy()
                    sub["_val"] = pd.to_numeric(
                        sub[value_col], errors="coerce",
                    )
                    sub = sub.dropna(subset=["_val"])
                    if sub.empty:
                        for post_epoch in POST_EPOCHS:
                            rows.append({
                                "recovery_phenotype": phenotype,
                                "side": side, "signal": signal,
                                "variant": variant, "post_epoch": post_epoch,
                                "cluster_idx": 0,
                                "start_bin": -1, "end_bin": -1,
                                "cluster_mass": float("nan"),
                                "sign": float("nan"),
                                "p_value": float("nan"),
                                "n_pre": 0, "n_post": 0,
                                "status": "insufficient_data",
                            })
                        continue
                    # Per-session trajectory: mean over trials within
                    # (animal, date, bin).
                    session_traj = (
                        sub.groupby(
                            ["animal", "date", "phase_bin", "epoch_label"],
                            as_index=False,
                        )["_val"].mean()
                    )
                    # Pivot to (session, bin) wide.
                    wide = session_traj.pivot_table(
                        index=["animal", "date", "epoch_label"],
                        columns="phase_bin",
                        values="_val",
                    ).sort_index(axis=1)
                    wide.columns.name = None
                    bins = wide.columns.to_numpy()
                    n_bins = len(bins)
                    wide = wide.reset_index()

                    for post_epoch in POST_EPOCHS:
                        pre_rows = wide[wide["epoch_label"] == "pre"]
                        post_rows = wide[wide["epoch_label"] == post_epoch]
                        n_pre = len(pre_rows)
                        n_post = len(post_rows)
                        if n_pre < 2 or n_post < 2:
                            rows.append({
                                "recovery_phenotype": phenotype,
                                "side": side, "signal": signal,
                                "variant": variant, "post_epoch": post_epoch,
                                "cluster_idx": 0,
                                "start_bin": -1, "end_bin": -1,
                                "cluster_mass": float("nan"),
                                "sign": float("nan"),
                                "p_value": float("nan"),
                                "n_pre": int(n_pre), "n_post": int(n_post),
                                "status": "insufficient_data",
                            })
                            continue
                        pre_arr = pre_rows[bins].to_numpy(dtype=np.float64)
                        post_arr = post_rows[bins].to_numpy(dtype=np.float64)
                        obs_t = _per_bin_t_stat(pre_arr, post_arr)
                        obs_clusters = _find_clusters_above_threshold(
                            obs_t, t_threshold,
                        )

                        # Build joint matrix for permutations.
                        joint = np.vstack([pre_arr, post_arr])
                        n_total = joint.shape[0]
                        # Null max cluster mass distribution.
                        null_masses = np.zeros(n_permutations)
                        for ip in range(n_permutations):
                            perm = rng.permutation(n_total)
                            perm_pre = joint[perm[:n_pre]]
                            perm_post = joint[perm[n_pre:]]
                            t_perm = _per_bin_t_stat(perm_pre, perm_post)
                            perm_clusters = _find_clusters_above_threshold(
                                t_perm, t_threshold,
                            )
                            if perm_clusters:
                                null_masses[ip] = max(
                                    c["mass"] for c in perm_clusters
                                )
                            else:
                                null_masses[ip] = 0.0

                        if not obs_clusters:
                            rows.append({
                                "recovery_phenotype": phenotype,
                                "side": side, "signal": signal,
                                "variant": variant, "post_epoch": post_epoch,
                                "cluster_idx": 0,
                                "start_bin": -1, "end_bin": -1,
                                "cluster_mass": 0.0,
                                "sign": 0.0,
                                "p_value": 1.0,
                                "n_pre": int(n_pre), "n_post": int(n_post),
                                "status": "no_cluster",
                            })
                            continue
                        # Emit one row per observed cluster.
                        for ci, cluster in enumerate(obs_clusters):
                            p = float(
                                np.mean(null_masses >= cluster["mass"])
                            )
                            rows.append({
                                "recovery_phenotype": phenotype,
                                "side": side, "signal": signal,
                                "variant": variant, "post_epoch": post_epoch,
                                "cluster_idx": ci,
                                "start_bin": cluster["start_bin"],
                                "end_bin": cluster["end_bin"],
                                "cluster_mass": cluster["mass"],
                                "sign": cluster["sign"],
                                "p_value": p,
                                "n_pre": int(n_pre), "n_post": int(n_post),
                                "status": "ok",
                            })

    out = pd.DataFrame(rows)
    out = apply_correction_to_results_df(
        out, p_value_col="p_value", method="bh_fdr", group_cols=(),
    )
    return out


def compute_trajectory_bootstrap_pre_ci(
    densified_cohort_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    variants: Iterable[str] = ("raw", "delta"),
    n_bootstrap: int = 5000,
    ci: float = 0.95,
    rng_seed: int = 42,
) -> pd.DataFrame:
    """Animal-level bootstrap CI on per-phenotype pre-stroke trajectory.

    Q-lock 13.6 (2026-05-28). Per (phenotype × side × signal × variant
    × phase_bin), N bootstrap resamples of animals (with replacement)
    from the pre-stroke pool. For each resample: compute pooled
    per-bin mean across animals. Quantiles across resamples give the
    pre-stroke 'noise envelope' to compare post-epoch trajectories
    against.

    Per-animal pre trajectory is the cross-session mean across pre
    sessions × bins of that animal. Bootstrap resamples animals
    (not sessions or trials) — proper unit of independence per
    Phase 9 stats convention.

    Returns
    -------
    pd.DataFrame
        One row per (phenotype × side × signal × variant ×
        phase_bin). Columns: ``recovery_phenotype``, ``side``,
        ``signal``, ``variant``, ``phase_bin``, ``phase_bin_center``,
        ``mean_ci_lo``, ``mean_median``, ``mean_ci_hi``, ``n_animals``.
    """
    signals = tuple(signals)
    variants = tuple(variants)
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1); got {ci}.")
    if not 1 <= n_bootstrap <= 100000:
        raise ValueError(
            f"n_bootstrap must be in [1, 100000]; got {n_bootstrap}.",
        )

    rng = np.random.default_rng(rng_seed)
    lo_q = (1.0 - ci) / 2.0
    hi_q = 1.0 - lo_q

    out_rows: list[dict[str, object]] = []
    pre_df = densified_cohort_df[
        densified_cohort_df["epoch_label"] == "pre"
    ]
    has_center = "phase_bin_center" in pre_df.columns

    for phenotype in PHENOTYPE_ORDER:
        for side in SIDE_ORDER:
            for signal in signals:
                for variant in variants:
                    value_col = signal if variant == "raw" else f"{signal}_delta"
                    if value_col not in pre_df.columns:
                        continue
                    sub = pre_df[
                        (pre_df["recovery_phenotype"] == phenotype)
                        & (pre_df["side"] == side)
                    ][[
                        "animal", "phase_bin",
                        *([("phase_bin_center")] if has_center else []),
                        value_col,
                    ]].copy()
                    sub["_val"] = pd.to_numeric(
                        sub[value_col], errors="coerce",
                    )
                    sub = sub.dropna(subset=["_val"])
                    if sub.empty:
                        continue
                    # Per-animal trajectory: mean over (date, trial) × bin.
                    per_animal = (
                        sub.groupby(
                            ["animal", "phase_bin"], as_index=False,
                        )["_val"].mean()
                    )
                    if has_center:
                        centers = (
                            sub.groupby(
                                "phase_bin", as_index=False,
                            )["phase_bin_center"].first()
                        )
                    # Pivot to (animal, bin).
                    wide = per_animal.pivot_table(
                        index="animal", columns="phase_bin",
                        values="_val",
                    ).sort_index(axis=1)
                    animals_arr = wide.index.to_numpy()
                    n_animals = len(animals_arr)
                    bins = wide.columns.to_numpy()
                    arr = wide.to_numpy(dtype=np.float64)
                    if n_animals < 1:
                        continue
                    # Bootstrap: resample animals with replacement.
                    boot_means = np.zeros((n_bootstrap, len(bins)))
                    for ib in range(n_bootstrap):
                        idx = rng.integers(0, n_animals, size=n_animals)
                        boot_means[ib] = np.nanmean(arr[idx], axis=0)
                    lo_band = np.nanquantile(boot_means, lo_q, axis=0)
                    med_band = np.nanquantile(boot_means, 0.5, axis=0)
                    hi_band = np.nanquantile(boot_means, hi_q, axis=0)
                    for bi, phase_bin in enumerate(bins):
                        row = {
                            "recovery_phenotype": phenotype,
                            "side": side, "signal": signal,
                            "variant": variant,
                            "phase_bin": int(phase_bin),
                            "mean_ci_lo": float(lo_band[bi]),
                            "mean_median": float(med_band[bi]),
                            "mean_ci_hi": float(hi_band[bi]),
                            "n_animals": int(n_animals),
                            "n_bootstrap": int(n_bootstrap),
                            "ci": ci,
                        }
                        if has_center:
                            ctr = centers[
                                centers["phase_bin"] == phase_bin
                            ]["phase_bin_center"].iloc[0]
                            row["phase_bin_center"] = float(ctr)
                        out_rows.append(row)

    if not out_rows:
        cols = [
            "recovery_phenotype", "side", "signal", "variant",
            "phase_bin", "phase_bin_center", "mean_ci_lo", "mean_median",
            "mean_ci_hi", "n_animals", "n_bootstrap", "ci",
        ]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(out_rows)


def compute_trajectory_bootstrap_effect_ci(
    densified_cohort_df: pd.DataFrame,
    animals_map: dict[str, AnimalInfo],
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    variants: Iterable[str] = ("raw", "delta"),
    n_bootstrap: int = 5000,
    ci: float = 0.95,
    rng_seed: int = 42,
) -> pd.DataFrame:
    """Animal-level bootstrap CI on the (post − pre) effect trajectory.

    Q-lock 13.7 (2026-05-28). Per (phenotype × side × signal × variant
    × post_epoch × phase_bin): resample animals from the phenotype
    pool with replacement N times. For each resample, compute each
    animal's per-bin pre mean + per-bin post_epoch mean (averaging
    across that animal's sessions/trials), then take the cross-resampled-
    animals mean of (post − pre) per bin. Quantiles across resamples
    give a CI on the observed effect.

    Animal-level bootstrap (resample WHICH animals are in the cohort
    with replacement) respects per-animal independence — the proper
    unit of resampling. Trial- and session-level bootstraps would
    inflate the CI tightness via pseudo-replication.

    Significant cells (per-bin): the 1-CI tail excludes 0. Output
    column ``excludes_zero`` is the bool flag.

    Parameters
    ----------
    densified_cohort_df : pd.DataFrame
        Output of ``densify_phase_rows_via_interp`` + ``attach_metadata``
        + ``apply_phase_bin_baseline_delta`` (for delta columns).
        Required columns: ``animal``, ``date``, ``side``, ``phase_bin``,
        ``epoch_label``, ``recovery_phenotype``, signal columns, and
        ``<signal>_delta`` columns if delta variant requested.
    animals_map : Mapping[str, AnimalInfo]
        Kept in signature for API parity; phenotype must already be
        attached to ``densified_cohort_df``.
    signals, variants : Iterable[str]
    n_bootstrap : int, default 5000
    ci : float, default 0.95
    rng_seed : int, default 42

    Returns
    -------
    pd.DataFrame
        One row per (phenotype × side × signal × variant × post_epoch
        × phase_bin). Columns: ``recovery_phenotype``, ``side``,
        ``signal``, ``variant``, ``post_epoch``, ``phase_bin``,
        ``phase_bin_center``, ``effect_median``, ``effect_ci_lo``,
        ``effect_ci_hi``, ``excludes_zero`` (bool), ``n_animals_pre``,
        ``n_animals_post``, ``n_bootstrap``, ``ci``.
    """
    signals = tuple(signals)
    variants = tuple(variants)
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1); got {ci}.")
    if not 1 <= n_bootstrap <= 100000:
        raise ValueError(
            f"n_bootstrap must be in [1, 100000]; got {n_bootstrap}.",
        )

    rng = np.random.default_rng(rng_seed)
    lo_q = (1.0 - ci) / 2.0
    hi_q = 1.0 - lo_q
    has_center = "phase_bin_center" in densified_cohort_df.columns

    out_rows: list[dict[str, object]] = []
    for phenotype in PHENOTYPE_ORDER:
        for side in SIDE_ORDER:
            for signal in signals:
                for variant in variants:
                    value_col = signal if variant == "raw" else f"{signal}_delta"
                    if value_col not in densified_cohort_df.columns:
                        continue
                    sub = densified_cohort_df[
                        (densified_cohort_df["recovery_phenotype"] == phenotype)
                        & (densified_cohort_df["side"] == side)
                    ][[
                        "animal", "phase_bin",
                        *([("phase_bin_center")] if has_center else []),
                        "epoch_label", value_col,
                    ]].copy()
                    sub["_val"] = pd.to_numeric(
                        sub[value_col], errors="coerce",
                    )
                    sub = sub.dropna(subset=["_val"])
                    if sub.empty:
                        continue
                    # Per-(animal, epoch, bin) mean trajectory.
                    per_animal_epoch = (
                        sub.groupby(
                            ["animal", "epoch_label", "phase_bin"],
                            as_index=False,
                        )["_val"].mean()
                    )
                    if has_center:
                        centers = (
                            sub.groupby(
                                "phase_bin", as_index=False,
                            )["phase_bin_center"].first()
                        )

                    pre_pivot = per_animal_epoch[
                        per_animal_epoch["epoch_label"] == "pre"
                    ].pivot_table(
                        index="animal", columns="phase_bin", values="_val",
                    ).sort_index(axis=1)
                    pre_animals = pre_pivot.index.to_numpy()
                    pre_arr = pre_pivot.to_numpy(dtype=np.float64)
                    bins = pre_pivot.columns.to_numpy()
                    n_bins = len(bins)
                    n_pre_animals = pre_arr.shape[0]
                    if n_pre_animals < 1:
                        continue

                    for post_epoch in POST_EPOCHS:
                        post_pivot = per_animal_epoch[
                            per_animal_epoch["epoch_label"] == post_epoch
                        ].pivot_table(
                            index="animal", columns="phase_bin",
                            values="_val",
                        ).reindex(columns=bins).sort_index(axis=1)
                        post_animals = post_pivot.index.to_numpy()
                        post_arr = post_pivot.to_numpy(dtype=np.float64)
                        n_post_animals = post_arr.shape[0]
                        if n_post_animals < 1:
                            continue
                        # Bootstrap: resample animals with replacement
                        # independently for pre and post (since the
                        # phenotype pool may have different animals in
                        # each epoch — e.g. some animals may have no
                        # post sessions if dates were truncated).
                        eff_samples = np.zeros((n_bootstrap, n_bins))
                        for ib in range(n_bootstrap):
                            pre_idx = rng.integers(
                                0, n_pre_animals, size=n_pre_animals,
                            )
                            post_idx = rng.integers(
                                0, n_post_animals, size=n_post_animals,
                            )
                            pre_mean = np.nanmean(
                                pre_arr[pre_idx], axis=0,
                            )
                            post_mean = np.nanmean(
                                post_arr[post_idx], axis=0,
                            )
                            eff_samples[ib] = post_mean - pre_mean
                        lo_band = np.nanquantile(
                            eff_samples, lo_q, axis=0,
                        )
                        med_band = np.nanquantile(
                            eff_samples, 0.5, axis=0,
                        )
                        hi_band = np.nanquantile(
                            eff_samples, hi_q, axis=0,
                        )
                        # 1 - CI tail excludes 0?
                        excludes = (lo_band > 0.0) | (hi_band < 0.0)
                        for bi, phase_bin in enumerate(bins):
                            row = {
                                "recovery_phenotype": phenotype,
                                "side": side, "signal": signal,
                                "variant": variant,
                                "post_epoch": post_epoch,
                                "phase_bin": int(phase_bin),
                                "effect_median": float(med_band[bi]),
                                "effect_ci_lo": float(lo_band[bi]),
                                "effect_ci_hi": float(hi_band[bi]),
                                "excludes_zero": bool(excludes[bi]),
                                "n_animals_pre": int(n_pre_animals),
                                "n_animals_post": int(n_post_animals),
                                "n_bootstrap": int(n_bootstrap),
                                "ci": ci,
                            }
                            if has_center:
                                ctr = centers[
                                    centers["phase_bin"] == phase_bin
                                ]["phase_bin_center"].iloc[0]
                                row["phase_bin_center"] = float(ctr)
                            out_rows.append(row)

    if not out_rows:
        cols = [
            "recovery_phenotype", "side", "signal", "variant",
            "post_epoch", "phase_bin", "phase_bin_center",
            "effect_median", "effect_ci_lo", "effect_ci_hi",
            "excludes_zero", "n_animals_pre", "n_animals_post",
            "n_bootstrap", "ci",
        ]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(out_rows)


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
