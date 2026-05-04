"""Phase 7a.4-cross-session-angle (2026-05-04) — per-mouse cross-
session aggregations of the tongue-angle plot families.

6 plot families × 2 sub-variants = 12 PNGs per mouse, emitted to
``<outputs>/dlc_kinematics/tongue_angle_cohort/{animal}/``.

Plot families:
  - ``first_peak_aligned``: time-series mean ± SEM aligned to first
    detected lick peak (consumes ``df_trials.angle_firstpeak_snip``
    + ``t_firstpeak_align_ms``).
  - ``reward_aligned``: time-series mean ± SEM aligned to reward;
    consumes ``df_trials.angle_snip`` directly per Addendum #8.
  - ``phase_aligned_angle_1st_lick``: centered-on-peak[0] phase
    (single cycle) per Addenda #9 / #15.
  - ``phase_aligned_angle_all_licks``: centered-on-peak phase across
    all multi-bout peaks (single cycle) per Addenda #10 / #15.
  - ``phase_aligned_angle_first_2_licks``: centered-on-peak phase
    multi-cycle per Addendum #11 Part A / #15 / #16.
  - ``first_vs_second_peak_scatter``: per-trial scatter of peak[0]
    angle vs peak[1] angle per Addendum #11 Part B.

Sub-variants per family:
  - ``session_overlays``: one curve / cloud per session per side,
    colored pre-stroke grey + post-stroke plasma by relative day.
  - ``binned_overlays``: one curve / centroid per (rel-day-bin,
    side); bin width from ``animal_info.bin_days``.

The cohort module reads the same per-session bundles as the
per-session ``tongue_visual`` renderer (no separate compute path);
per-animal pre-stroke median ILI is sourced from
``bundle.metadata["pre_stroke_median_ili_ms"]`` (populated by
:func:`build_tongue_visual_bundle_by_animal_date`).

Filename pattern: ``{animal}_{family}_{sub_variant}.png``.

This commit (cross-session #2) ships the skeleton + per-session
aggregator + ``first_peak_aligned`` family. Subsequent commits add
the other 5 families.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from stroke_orofacial.animals import AnimalInfo, get_animal  # noqa: E402
from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics.mean_sem_visual import (  # noqa: E402
    _color_for_rel_day_continuous,
)
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    TongueVisualBundle,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402


# Plot family / sub-variant tokens.
FAMILY_TOKENS: tuple[str, ...] = (
    "first_peak_aligned",
    "reward_aligned",
    "phase_aligned_angle_1st_lick",
    "phase_aligned_angle_all_licks",
    "phase_aligned_angle_first_2_licks",
    "first_vs_second_peak_scatter",
)
SUB_VARIANTS: tuple[str, ...] = ("session_overlays", "binned_overlays")


# ============================================================================
# Per-session aggregate dataclasses
# ============================================================================


@dataclass(frozen=True)
class TimeSeriesSessionAggregate:
    """Per (session, side, family) time-series mean ± SEM.

    Used by 5 of the 6 plot families: first_peak_aligned,
    reward_aligned, phase_aligned_angle_1st_lick,
    phase_aligned_angle_all_licks, phase_aligned_angle_first_2_licks.

    Attributes
    ----------
    family : str
        Plot-family token (one of :data:`FAMILY_TOKENS` minus the
        scatter family).
    side : str
        Trial side, ``"L"`` or ``"R"``.
    date : datetime.date
        Session date.
    rel_day : int
        Days since stroke (negative = pre-stroke). From
        :meth:`AnimalInfo.day_relative_to_stroke`.
    n_trials : int
        Number of trials contributing to this side's aggregate
        (= number of finite-mean rows in the trial × time matrix).
    t : np.ndarray
        Time / phase axis (1D); shape ``(n_bins,)``.
    mu : np.ndarray
        Cross-trial mean per t-bin; shape ``(n_bins,)``. NaN-safe.
    sem : np.ndarray
        Cross-trial SEM per t-bin; shape ``(n_bins,)``. NaN-safe.
        Uses ``ddof=0`` (matches the per-session
        :func:`_robust_mean_sem` convention from
        :mod:`stroke_orofacial.dlc_kinematics.tongue_visual`).
    """

    family: str
    side: str
    date: datetime.date
    rel_day: int
    n_trials: int
    t: np.ndarray
    mu: np.ndarray
    sem: np.ndarray


@dataclass(frozen=True)
class TongueAngleCohortAggregates:
    """Per-animal cross-session aggregates across all rendered
    families. Time-series rows keyed by family/side/date; scatter
    rows added in cross-session #5.
    """

    animal: str
    bin_days: int
    ts_rows: list[TimeSeriesSessionAggregate]


# ============================================================================
# Per-session extractors
# ============================================================================


def _robust_mean_sem(M: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """NaN-safe mean ± SEM per column. Mirrors the per-session
    :func:`_robust_mean_sem` shape: ``(n_trials, n_bins)`` →
    ``(mu, sem, n_trials_contributing)``.

    ``ddof=0`` (matches the per-session phase plot's
    :func:`_np_sem_ddof0`; documented choice in the Addendum #15
    DECISIONS arc).
    """
    M = np.asarray(M, float)
    if M.ndim == 1:
        M = M[None, :]
    n_per_bin = np.sum(np.isfinite(M), axis=0)
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning,
            message=r"(Mean of empty slice|Degrees of freedom <= 0)",
        )
        mu = np.nanmean(M, axis=0)
        sd = np.nanstd(M, axis=0, ddof=0)
    sem = np.full_like(mu, np.nan)
    good = n_per_bin > 0
    sem[good] = sd[good] / np.sqrt(np.maximum(1, n_per_bin[good]))
    n_trials_contrib = int(np.sum(np.any(np.isfinite(M), axis=1)))
    return mu, sem, n_trials_contrib


def _extract_first_peak_aligned(
    bundle: TongueVisualBundle, side: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int] | None:
    """Per-side mean ± SEM of ``angle_firstpeak_snip`` aligned to the
    first detected peak. Returns ``(t, mu, sem, n_trials)`` or
    ``None`` if no trials contribute.
    """
    df_trials = bundle.df_trials
    if df_trials.empty:
        return None
    side_rows = df_trials[
        (df_trials["side"] == side)
        & df_trials["first_peak_t_ms"].notna()
    ]
    if side_rows.empty:
        return None
    M = np.vstack(side_rows["angle_firstpeak_snip"].to_list()).astype(float)
    t = np.asarray(side_rows.iloc[0]["t_firstpeak_align_ms"], float)
    mu, sem, n_trials = _robust_mean_sem(M)
    if n_trials == 0:
        return None
    return t, mu, sem, n_trials


def _extract_reward_aligned(
    bundle: TongueVisualBundle, side: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int] | None:
    """Per-side mean ± SEM of ``angle_snip`` (per Addendum #8: raw
    per-frame trace, not bout-windowed) aligned to reward (t=0).
    Returns ``(t, mu, sem, n_trials)`` or ``None`` if no trials
    contribute.

    Phase 7a.4-cross-session-angle Addendum #8 (2026-05-04):
    reward_aligned consumes ``angle_snip`` directly — every frame
    in the bundle's ``plot_win_ms`` window contributes regardless
    of bout structure. Cross-session aggregator follows the same
    convention for byte-aligned per-session vs cross-session
    semantics.
    """
    df_trials = bundle.df_trials
    if df_trials.empty:
        return None
    side_rows = df_trials[df_trials["side"] == side]
    if side_rows.empty:
        return None
    M = np.vstack(side_rows["angle_snip"].to_list()).astype(float)
    t = np.asarray(side_rows.iloc[0]["t_ms"], float)
    mu, sem, n_trials = _robust_mean_sem(M)
    if n_trials == 0:
        return None
    return t, mu, sem, n_trials


# ============================================================================
# Cohort aggregator
# ============================================================================


def _enumerate_session_dates(
    animal: str, resolver: PathResolver,
) -> list[datetime.date]:
    """List session dates with on-disk per-trial endpoints JSONs
    (= 7a.3 V3 emit set). Matches the
    :func:`compute_pre_stroke_median_ili_ms` enumeration logic.
    """
    endpoints_dir = (
        resolver.pipeline_outputs(subdir="dlc_kinematics")
        / "endpoints" / animal
    )
    if not endpoints_dir.exists():
        return []
    dates: list[datetime.date] = []
    for p in sorted(endpoints_dir.glob("*.json")):
        m = re.match(r"(\d{8})\.json$", p.name)
        if m is None:
            continue
        d = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        dates.append(d)
    return dates


def build_tongue_angle_cohort_aggregates(
    animal: str,
    resolver: PathResolver,
    *,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    families: Sequence[str] | None = None,
    verbose: bool = False,
) -> TongueAngleCohortAggregates:
    """Walk every (animal, date) in the cohort emit set; build the
    per-session bundle once; extract per-family per-side aggregates.

    Parameters
    ----------
    animal
        Animal identifier (e.g., ``"PS46"``).
    resolver
        Configured :class:`PathResolver`. Reads per-session bundles
        from the existing 7a.3 V3 emit set.
    params, animal_info
        Optional overrides; ``None`` defers to :func:`load_defaults`
        and :func:`get_animal`.
    families
        Restrict the extracted families. ``None`` (default) → all
        time-series families currently supported by this commit
        (first_peak_aligned). Used by tests + later cross-session
        commits to restrict scope.
    verbose
        Print progress on each session.

    Returns
    -------
    TongueAngleCohortAggregates
        ``ts_rows`` list contains one row per (family, side, date)
        with finite mean. Sessions where the bundle build raised
        ``FileNotFoundError`` are silently skipped.
    """
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    requested = (
        set(FAMILY_TOKENS) if families is None else set(families)
    )

    ts_rows: list[TimeSeriesSessionAggregate] = []

    for d in _enumerate_session_dates(animal, resolver):
        try:
            bundle = build_tongue_visual_bundle_by_animal_date(
                animal=animal, date=d, resolver=resolver, params=params,
            )
        except FileNotFoundError:
            if verbose:
                print(f"  [skip] {animal}/{d.isoformat()}: bundle FNFE",
                      flush=True)
            continue
        try:
            rel_day = int(animal_info.day_relative_to_stroke(d))
        except Exception:
            continue
        if verbose:
            print(f"  [ok]  {animal}/{d.isoformat()} (d{rel_day:+d})",
                  flush=True)

        for side in ("L", "R"):
            if "first_peak_aligned" in requested:
                triple = _extract_first_peak_aligned(bundle, side)
                if triple is not None:
                    t, mu, sem, n_trials = triple
                    ts_rows.append(TimeSeriesSessionAggregate(
                        family="first_peak_aligned",
                        side=side, date=d, rel_day=rel_day,
                        n_trials=n_trials,
                        t=t, mu=mu, sem=sem,
                    ))
            if "reward_aligned" in requested:
                triple = _extract_reward_aligned(bundle, side)
                if triple is not None:
                    t, mu, sem, n_trials = triple
                    ts_rows.append(TimeSeriesSessionAggregate(
                        family="reward_aligned",
                        side=side, date=d, rel_day=rel_day,
                        n_trials=n_trials,
                        t=t, mu=mu, sem=sem,
                    ))

    return TongueAngleCohortAggregates(
        animal=animal,
        bin_days=int(animal_info.bin_days),
        ts_rows=ts_rows,
    )


# ============================================================================
# Day-binning helpers
# ============================================================================


def _rel_day_to_bin(rel_day: int, bin_days: int) -> tuple[int, int]:
    """Compute the (lo, hi) inclusive bin tuple for a single
    ``rel_day``.

    Phase 7a.4-cross-session-angle Addendum #17 (2026-05-04):
    aligns with the established legacy
    :func:`stroke_orofacial.dlc_kinematics._day_binned._compute_rel_day_bin_label`
    convention. d0 (rel_day == 0) is treated as PRE-stroke (recording
    done before stroke induction earlier that day):

      - ``rel_day <= 0`` (pre): last pre-bin is
        ``(-(B - 1), 0)``; older bins decrement by ``B``.
      - ``rel_day >= 1`` (post): first post-bin is ``(1, B)``; later
        bins increment by ``B``.

    For B=2 (PS46-50): bins ..., (-3, -2), (-1, 0), (1, 2), (3, 4), ...
    For B=7 (PS51/54/55): bins ..., (-13, -7), (-6, 0), (1, 7), (8, 14), ...
    """
    b = int(bin_days)
    if b < 1:
        raise ValueError(f"bin_days must be >= 1; got {bin_days}.")
    r = int(rel_day)
    if r >= 1:
        lo = ((r - 1) // b) * b + 1
        hi = lo + b - 1
    else:
        # Pre-stroke: anchor at d0 inclusive, extend backwards by B.
        # Mirrors legacy Cell 50's _bin_rel_day else-branch.
        hi = -((abs(r)) // b) * b
        lo = hi - (b - 1)
    return (int(lo), int(hi))


def _make_rel_day_bins(
    rel_days: Sequence[int], *, bin_days: int,
) -> list[tuple[int, int]]:
    """Build the set of (lo, hi) bins covering all ``rel_days``.

    Phase 7a.4-cross-session-angle Addendum #17 (2026-05-04): each
    rel_day maps to its own bin via :func:`_rel_day_to_bin`; bins
    are de-duplicated and returned sorted by ``lo``. Pre-stroke is
    binned at the same ``bin_days`` width as post-stroke (NO LONGER
    pooled into a single bin); bins anchor to d0 (inclusive).
    """
    if not rel_days:
        return []
    bins_set = {_rel_day_to_bin(int(r), bin_days) for r in rel_days}
    return sorted(bins_set, key=lambda x: x[0])


def _assign_to_bin(
    rel_day: int, bins: Sequence[tuple[int, int]],
) -> tuple[int, int] | None:
    for lo, hi in bins:
        if lo <= int(rel_day) <= hi:
            return (int(lo), int(hi))
    return None


# ============================================================================
# Generic time-series renderers (shared by first_peak_aligned + reward_aligned;
# subsequent cross-session commits will add a separate phase-plot variant).
# ============================================================================


def _setup_cam_view_axes(
    fig: Figure, axes: np.ndarray,
) -> tuple[Any, Any, dict[str, Any]]:
    """Cam-view subplot layout (R left, L right). Mirrors the
    7a.4-orientation-fix + 7a.6 C7.2 + Addendum #16 conventions.
    """
    ax_left, ax_right = axes[0], axes[1]
    side_to_ax = {"R": ax_left, "L": ax_right}
    return ax_left, ax_right, side_to_ax


def _post_max_rel_day(
    ts_rows: Sequence[TimeSeriesSessionAggregate],
) -> int | None:
    post_days = [r.rel_day for r in ts_rows if r.rel_day >= 1]
    return max(post_days) if post_days else None


def _add_pre_stroke_patch_and_post_colorbar(
    fig: Figure, axes: np.ndarray, *,
    pre_color: str, post_cmap: str, post_max: int | None,
) -> None:
    """Phase 7a.4-cross-session-angle Addendum #17 item 3 (2026-05-04):
    shared right-side legend layout for the cross-session overlays.

    Reserves the rightmost ~22% of the figure (``subplots_adjust``)
    for a small grey ``Patch`` proxy labelling pre-stroke (d≤0)
    plus a vertical post-stroke plasma colorbar showing rel_day
    range. No legends drawn on the subplot axes.
    """
    from matplotlib.patches import Patch
    from matplotlib.colors import Normalize

    fig.subplots_adjust(right=0.80)
    # Pre-stroke patch as a top-right legend on the right subplot.
    ax_right = axes[1]
    pre_handle = Patch(color=pre_color, label="pre-stroke (d≤0)")
    ax_right.legend(
        handles=[pre_handle],
        loc="upper left",
        bbox_to_anchor=(1.04, 1.00),
        frameon=False, fontsize=9,
    )
    # Post-stroke colorbar below the patch.
    if post_max is not None and post_max >= 1:
        cbar_ax = fig.add_axes([0.83, 0.18, 0.015, 0.55])
        sm = plt.cm.ScalarMappable(
            cmap=plt.get_cmap(post_cmap),
            norm=Normalize(vmin=1, vmax=float(post_max)),
        )
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cbar_ax)
        cbar.set_label("Post-stroke day (d)")


def _plot_time_series_session_overlays(
    cohort: TongueAngleCohortAggregates,
    *,
    family_token: str,
    title_label: str,
    x_axis_label: str,
    x_clip: tuple[float, float] | None,
    params: dict[str, Any],
) -> Figure:
    """Generic 1×2 cam-view session-overlays renderer for any
    time-series family (first_peak_aligned, reward_aligned, …).

    Each session of ``family_token`` contributes one curve per side
    (mean ± SEM across trials), colored pre-stroke grey + post-stroke
    plasma by relative day. Reward-marker axvline at t=0; optional
    ``x_clip`` (display window) clips both subplots' x-axes.

    Shared right-margin legend (pre-stroke Patch + post-stroke
    plasma colorbar) per Addendum #17 item 3.
    """
    cohort_cfg = params["dlc_kinematics"]["tongue_angle_cohort"]
    visual = cohort_cfg["visual"]["session_overlays"]
    pre_color = str(cohort_cfg["pre_color"])
    post_cmap = str(cohort_cfg["post_cmap"])
    line_lw = float(visual["line_width"])
    alpha_mean = float(visual["alpha_mean"])
    alpha_sem = float(visual["alpha_sem"])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6), sharex=True, sharey=True)
    ax_left, ax_right, side_to_ax = _setup_cam_view_axes(fig, axes)

    family_rows = [r for r in cohort.ts_rows if r.family == family_token]
    post_max = _post_max_rel_day(family_rows)

    for r in family_rows:
        ax = side_to_ax[r.side]
        c = _color_for_rel_day_continuous(
            r.rel_day, post_max,
            cmap_name=post_cmap, pre_color=pre_color,
        )
        ax.plot(r.t, r.mu, color=c, lw=line_lw, alpha=alpha_mean)
        ax.fill_between(
            r.t, r.mu - r.sem, r.mu + r.sem,
            color=c, alpha=alpha_sem, lw=0,
        )

    for ax, side in [(ax_left, "R"), (ax_right, "L")]:
        ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
        ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
        n_sess = sum(1 for r in family_rows if r.side == side)
        ax.set_title(f"{side} trials  ({n_sess} sessions)")
        ax.set_xlabel(x_axis_label)
        ax.grid(True, alpha=0.2)
        if x_clip is not None:
            ax.set_xlim(float(x_clip[0]), float(x_clip[1]))
    ax_left.set_ylabel("Tongue angle (deg)")

    fig.suptitle(
        f"{cohort.animal} | {title_label} | session overlays",
        y=0.99,
    )
    _add_pre_stroke_patch_and_post_colorbar(
        fig, axes, pre_color=pre_color,
        post_cmap=post_cmap, post_max=post_max,
    )
    return fig


def _plot_time_series_binned_overlays(
    cohort: TongueAngleCohortAggregates,
    *,
    family_token: str,
    title_label: str,
    x_axis_label: str,
    x_clip: tuple[float, float] | None,
    params: dict[str, Any],
) -> Figure:
    """Generic 1×2 cam-view binned-overlays renderer for any
    time-series family. One curve per (rel-day-bin, side); per-bin
    mean = mean of per-session means; per-bin SEM = SEM across
    sessions in the bin. Pre-stroke is binned per Addendum #17
    item 2 (anchored to d0).

    Shared figure-level legend on the right margin (one entry per
    bin) per Addendum #17 item 3.
    """
    cohort_cfg = params["dlc_kinematics"]["tongue_angle_cohort"]
    visual = cohort_cfg["visual"]["binned_overlays"]
    pre_color = str(cohort_cfg["pre_color"])
    post_cmap = str(cohort_cfg["post_cmap"])
    line_lw = float(visual["line_width"])
    alpha_mean = float(visual["alpha_mean"])
    alpha_sem = float(visual["alpha_sem"])
    min_per_bin = int(cohort_cfg["min_sessions_per_bin"])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6), sharex=True, sharey=True)
    ax_left, ax_right, side_to_ax = _setup_cam_view_axes(fig, axes)

    family_rows = [r for r in cohort.ts_rows if r.family == family_token]
    rel_days = [r.rel_day for r in family_rows]
    bins = _make_rel_day_bins(rel_days, bin_days=cohort.bin_days)
    post_max = _post_max_rel_day(family_rows)

    legend_handles: list[Any] = []
    legend_labels: list[str] = []
    seen_bins: set[tuple[int, int]] = set()

    for side in ("L", "R"):
        ax = side_to_ax[side]
        side_rows = [r for r in family_rows if r.side == side]
        for bin_lo, bin_hi in bins:
            bin_rows = [
                r for r in side_rows
                if bin_lo <= r.rel_day <= bin_hi
            ]
            if len(bin_rows) < min_per_bin:
                continue
            t = bin_rows[0].t
            M = np.vstack([r.mu for r in bin_rows]).astype(float)
            mu_bin = np.nanmean(M, axis=0)
            n_bin = np.sum(np.isfinite(M), axis=0)
            sd_bin = np.nanstd(M, axis=0, ddof=0)
            sem_bin = np.full_like(mu_bin, np.nan)
            good = n_bin > 0
            sem_bin[good] = sd_bin[good] / np.sqrt(
                np.maximum(1, n_bin[good])
            )
            bin_center = 0.5 * (bin_lo + bin_hi)
            c = _color_for_rel_day_continuous(
                bin_center, post_max,
                cmap_name=post_cmap, pre_color=pre_color,
            )
            label = (
                f"{bin_lo}..{bin_hi} (pre, n={len(bin_rows)})"
                if bin_hi <= 0 else
                f"{bin_lo}..{bin_hi} (n={len(bin_rows)})"
            )
            line, = ax.plot(
                t, mu_bin, color=c, lw=line_lw, alpha=alpha_mean,
            )
            ax.fill_between(
                t, mu_bin - sem_bin, mu_bin + sem_bin,
                color=c, alpha=alpha_sem, lw=0,
            )
            if (bin_lo, bin_hi) not in seen_bins:
                legend_handles.append(line)
                legend_labels.append(label)
                seen_bins.add((bin_lo, bin_hi))
        ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
        ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
        ax.set_title(f"{side} trials")
        ax.set_xlabel(x_axis_label)
        ax.grid(True, alpha=0.2)
        if x_clip is not None:
            ax.set_xlim(float(x_clip[0]), float(x_clip[1]))
    ax_left.set_ylabel("Tongue angle (deg)")

    fig.suptitle(
        f"{cohort.animal} | {title_label} | "
        f"binned overlays (bin_days={cohort.bin_days})",
        y=0.99,
    )

    # Figure-level legend on the right margin (Addendum #17 item 3).
    fig.subplots_adjust(right=0.80)
    if legend_handles:
        fig.legend(
            legend_handles, legend_labels,
            loc="upper left",
            bbox_to_anchor=(0.82, 0.95),
            frameon=False, fontsize=9,
        )
    return fig


# ============================================================================
# Family-specific thin wrappers
# ============================================================================


def _plot_first_peak_aligned_session_overlays(
    cohort: TongueAngleCohortAggregates, *, params: dict[str, Any],
) -> Figure:
    """Per-mouse session-overlay plot for ``first_peak_aligned``."""
    return _plot_time_series_session_overlays(
        cohort,
        family_token="first_peak_aligned",
        title_label="first peak-aligned tongue angle",
        x_axis_label="Time from first detected lick peak (ms)",
        x_clip=None,
        params=params,
    )


def _plot_first_peak_aligned_binned_overlays(
    cohort: TongueAngleCohortAggregates, *, params: dict[str, Any],
) -> Figure:
    """Per-mouse binned-overlay plot for ``first_peak_aligned``."""
    return _plot_time_series_binned_overlays(
        cohort,
        family_token="first_peak_aligned",
        title_label="first peak-aligned tongue angle",
        x_axis_label="Time from first detected lick peak (ms)",
        x_clip=None,
        params=params,
    )


def _plot_reward_aligned_session_overlays(
    cohort: TongueAngleCohortAggregates, *, params: dict[str, Any],
) -> Figure:
    """Per-mouse session-overlay plot for ``reward_aligned``. X-axis
    clipped to ``dlc_kinematics.tongue_visual.reward_aligned_display_window_ms``
    (default ``[-180, 1000]`` ms) per Addendum #4 — same display
    window as the per-session reward-aligned plot."""
    visual_block = params["dlc_kinematics"]["tongue_visual"]
    display_win = tuple(
        visual_block.get("reward_aligned_display_window_ms", [-180.0, 1000.0])
    )
    return _plot_time_series_session_overlays(
        cohort,
        family_token="reward_aligned",
        title_label="reward-aligned tongue angle",
        x_axis_label="Time from reward (ms)",
        x_clip=(float(display_win[0]), float(display_win[1])),
        params=params,
    )


def _plot_reward_aligned_binned_overlays(
    cohort: TongueAngleCohortAggregates, *, params: dict[str, Any],
) -> Figure:
    """Per-mouse binned-overlay plot for ``reward_aligned``. Same
    display-window clip as :func:`_plot_reward_aligned_session_overlays`.
    """
    visual_block = params["dlc_kinematics"]["tongue_visual"]
    display_win = tuple(
        visual_block.get("reward_aligned_display_window_ms", [-180.0, 1000.0])
    )
    return _plot_time_series_binned_overlays(
        cohort,
        family_token="reward_aligned",
        title_label="reward-aligned tongue angle",
        x_axis_label="Time from reward (ms)",
        x_clip=(float(display_win[0]), float(display_win[1])),
        params=params,
    )


# ============================================================================
# Save helper
# ============================================================================


def _save_and_close(fig: Figure, path: Path, *, dpi: float = 200.0) -> None:
    """Atomic save + close. Matches the per-session
    :func:`tongue_visual._save_and_close` pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp" + path.suffix)
    fig.savefig(tmp, dpi=dpi, bbox_inches="tight", format="png")
    plt.close(fig)
    tmp.replace(path)


# ============================================================================
# Public entry: per-family family-render driver
# ============================================================================


def _family_paths(
    out_dir: Path, animal: str, family_token: str,
) -> dict[str, Path]:
    """Standard 2-PNG path tuple for any time-series family."""
    return {
        "session_overlays": out_dir / (
            f"{animal}_{family_token}_session_overlays.png"
        ),
        "binned_overlays": out_dir / (
            f"{animal}_{family_token}_binned_overlays.png"
        ),
    }


def build_first_peak_aligned_cohort(
    animal: str,
    resolver: PathResolver,
    *,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    cohort: TongueAngleCohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path]:
    """Render the ``first_peak_aligned`` cross-session family for one
    animal: emits ``session_overlays`` + ``binned_overlays`` PNGs.

    Returns a dict ``{"session_overlays": Path, "binned_overlays": Path}``.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}",
        )
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)

    out_dir = resolver.tongue_angle_cross_session_dir(animal)
    paths = _family_paths(out_dir, animal, "first_peak_aligned")
    if overwrite == "skip" and all(p.exists() for p in paths.values()):
        return paths

    if cohort is None:
        cohort = build_tongue_angle_cohort_aggregates(
            animal, resolver, params=params, animal_info=animal_info,
            families=["first_peak_aligned"],
        )

    fig_so = _plot_first_peak_aligned_session_overlays(cohort, params=params)
    _save_and_close(fig_so, paths["session_overlays"])

    fig_bo = _plot_first_peak_aligned_binned_overlays(cohort, params=params)
    _save_and_close(fig_bo, paths["binned_overlays"])

    return paths


def build_reward_aligned_cohort(
    animal: str,
    resolver: PathResolver,
    *,
    params: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    cohort: TongueAngleCohortAggregates | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, Path]:
    """Render the ``reward_aligned`` cross-session family for one
    animal: emits ``session_overlays`` + ``binned_overlays`` PNGs.

    Phase 7a.4-cross-session-angle Cross-session #3 (2026-05-04):
    consumes ``angle_snip`` (per-frame raw angle, per Addendum #8);
    x-axis clipped to
    ``dlc_kinematics.tongue_visual.reward_aligned_display_window_ms``
    (default ``[-180, 1000]`` ms; per Addendum #4) — same display
    window as the per-session reward-aligned plot for byte-aligned
    visual identity.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}",
        )
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)

    out_dir = resolver.tongue_angle_cross_session_dir(animal)
    paths = _family_paths(out_dir, animal, "reward_aligned")
    if overwrite == "skip" and all(p.exists() for p in paths.values()):
        return paths

    if cohort is None:
        cohort = build_tongue_angle_cohort_aggregates(
            animal, resolver, params=params, animal_info=animal_info,
            families=["reward_aligned"],
        )

    fig_so = _plot_reward_aligned_session_overlays(cohort, params=params)
    _save_and_close(fig_so, paths["session_overlays"])

    fig_bo = _plot_reward_aligned_binned_overlays(cohort, params=params)
    _save_and_close(fig_bo, paths["binned_overlays"])

    return paths


__all__ = [
    "FAMILY_TOKENS",
    "SUB_VARIANTS",
    "TimeSeriesSessionAggregate",
    "TongueAngleCohortAggregates",
    "build_first_peak_aligned_cohort",
    "build_reward_aligned_cohort",
    "build_tongue_angle_cohort_aggregates",
]
