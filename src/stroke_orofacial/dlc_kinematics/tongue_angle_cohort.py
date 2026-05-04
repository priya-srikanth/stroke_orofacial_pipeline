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

    return TongueAngleCohortAggregates(
        animal=animal,
        bin_days=int(animal_info.bin_days),
        ts_rows=ts_rows,
    )


# ============================================================================
# Day-binning helpers
# ============================================================================


def _make_rel_day_bins(
    rel_days: Sequence[int], *, bin_days: int,
) -> list[tuple[int, int]]:
    """Build (lo, hi) inclusive day-range bins.

    Pre-stroke (rel_day < 0) sessions all pool into a single bin
    ``(min_rel_day, -1)``. Post-stroke sessions are bucketed into
    consecutive ``[1, bin_days]``, ``[bin_days + 1, 2 * bin_days]``,
    etc., using the first day with rel_day ≥ 1 as the alignment
    anchor.

    Returns a list of (lo, hi) pairs ordered by ``lo``.
    """
    if not rel_days:
        return []
    rel = sorted(set(int(r) for r in rel_days))
    pre = [r for r in rel if r < 0]
    post = [r for r in rel if r >= 0]
    bins: list[tuple[int, int]] = []
    if pre:
        bins.append((min(pre), -1))
    if post:
        # bins start at 0 for post-stroke (= stroke day +). Bucket
        # by floor((r - 0) / bin_days).
        for r in post:
            bin_lo = (r // int(bin_days)) * int(bin_days)
            bin_hi = bin_lo + int(bin_days) - 1
            pair = (int(bin_lo), int(bin_hi))
            if pair not in bins:
                bins.append(pair)
    return sorted(bins, key=lambda x: x[0])


def _assign_to_bin(
    rel_day: int, bins: Sequence[tuple[int, int]],
) -> tuple[int, int] | None:
    for lo, hi in bins:
        if lo <= int(rel_day) <= hi:
            return (int(lo), int(hi))
    return None


# ============================================================================
# Render: first_peak_aligned (session_overlays + binned_overlays)
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


def _plot_first_peak_aligned_session_overlays(
    cohort: TongueAngleCohortAggregates,
    *,
    params: dict[str, Any],
) -> Figure:
    """Per-mouse session-overlay plot for ``first_peak_aligned``.
    1×2 cam-view subplots; one curve per session per side.
    """
    cohort_cfg = params["dlc_kinematics"]["tongue_angle_cohort"]
    visual = cohort_cfg["visual"]["session_overlays"]
    pre_color = str(cohort_cfg["pre_color"])
    post_cmap = str(cohort_cfg["post_cmap"])
    line_lw = float(visual["line_width"])
    line_alpha = float(visual["line_alpha"])
    sem_alpha = float(visual["sem_fill_alpha"])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6), sharex=True, sharey=True)
    ax_left, ax_right, side_to_ax = _setup_cam_view_axes(fig, axes)

    family_rows = [
        r for r in cohort.ts_rows if r.family == "first_peak_aligned"
    ]
    post_max = _post_max_rel_day(family_rows)

    for r in family_rows:
        ax = side_to_ax[r.side]
        c = _color_for_rel_day_continuous(
            r.rel_day, post_max,
            cmap_name=post_cmap, pre_color=pre_color,
        )
        ax.plot(r.t, r.mu, color=c, lw=line_lw, alpha=line_alpha)
        ax.fill_between(
            r.t, r.mu - r.sem, r.mu + r.sem,
            color=c, alpha=sem_alpha, lw=0,
        )

    for ax, side in [(ax_left, "R"), (ax_right, "L")]:
        ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
        ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
        n_sess = sum(1 for r in family_rows if r.side == side)
        ax.set_title(f"{side} trials  ({n_sess} sessions)")
        ax.set_xlabel("Time from first detected lick peak (ms)")
        ax.grid(True, alpha=0.2)
    ax_left.set_ylabel("Tongue angle (deg)")

    fig.suptitle(
        f"{cohort.animal} | first peak-aligned tongue angle | "
        f"session overlays (pre-stroke=grey, post-stroke=plasma)",
        y=0.99,
    )
    plt.tight_layout()
    return fig


def _plot_first_peak_aligned_binned_overlays(
    cohort: TongueAngleCohortAggregates,
    *,
    params: dict[str, Any],
) -> Figure:
    """Per-mouse binned-overlay plot for ``first_peak_aligned``. One
    curve per (rel-day-bin, side); per-bin mean = mean of per-
    session means; per-bin SEM = SEM across sessions in the bin.
    """
    cohort_cfg = params["dlc_kinematics"]["tongue_angle_cohort"]
    visual = cohort_cfg["visual"]["binned_overlays"]
    pre_color = str(cohort_cfg["pre_color"])
    post_cmap = str(cohort_cfg["post_cmap"])
    line_lw = float(visual["line_width"])
    line_alpha = float(visual["line_alpha"])
    sem_alpha = float(visual["sem_fill_alpha"])
    min_per_bin = int(cohort_cfg["min_sessions_per_bin"])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.6), sharex=True, sharey=True)
    ax_left, ax_right, side_to_ax = _setup_cam_view_axes(fig, axes)

    family_rows = [
        r for r in cohort.ts_rows if r.family == "first_peak_aligned"
    ]
    rel_days = [r.rel_day for r in family_rows]
    bins = _make_rel_day_bins(rel_days, bin_days=cohort.bin_days)
    post_max = _post_max_rel_day(family_rows)

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
            # Per-bin mean = mean of per-session means; per-bin SEM
            # = SEM of per-session means (treat each session-mean as
            # one sample). Pad to the same t-axis (assume identical
            # across sessions of one family, which holds because
            # first_peak_align_win_ms is fixed).
            M = np.vstack([r.mu for r in bin_rows]).astype(float)
            mu_bin = np.nanmean(M, axis=0)
            n_bin = np.sum(np.isfinite(M), axis=0)
            sd_bin = np.nanstd(M, axis=0, ddof=0)
            sem_bin = np.full_like(mu_bin, np.nan)
            good = n_bin > 0
            sem_bin[good] = sd_bin[good] / np.sqrt(
                np.maximum(1, n_bin[good])
            )
            # Color by bin center.
            bin_center = 0.5 * (bin_lo + bin_hi)
            c = _color_for_rel_day_continuous(
                bin_center, post_max,
                cmap_name=post_cmap, pre_color=pre_color,
            )
            label = (
                f"pre (d{bin_lo}..{bin_hi}, n={len(bin_rows)})"
                if bin_lo < 0 else
                f"d{bin_lo}..{bin_hi} (n={len(bin_rows)})"
            )
            ax.plot(t, mu_bin, color=c, lw=line_lw, alpha=line_alpha,
                    label=label)
            ax.fill_between(
                t, mu_bin - sem_bin, mu_bin + sem_bin,
                color=c, alpha=sem_alpha, lw=0,
            )
        ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
        ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
        ax.set_title(f"{side} trials")
        ax.set_xlabel("Time from first detected lick peak (ms)")
        ax.grid(True, alpha=0.2)
        ax.legend(frameon=False, fontsize=8)
    ax_left.set_ylabel("Tongue angle (deg)")

    fig.suptitle(
        f"{cohort.animal} | first peak-aligned tongue angle | "
        f"binned overlays (bin_days={cohort.bin_days})",
        y=0.99,
    )
    plt.tight_layout()
    return fig


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

    If ``cohort`` is provided, reuses it; otherwise builds via
    :func:`build_tongue_angle_cohort_aggregates`. Subsequent cross-session
    commits will add a top-level composite that builds the cohort
    once and dispatches to all 6 family renderers.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}",
        )
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)

    out_dir = resolver.tongue_angle_cohort_dir(animal)
    paths = {
        "session_overlays": out_dir / (
            f"{animal}_first_peak_aligned_session_overlays.png"
        ),
        "binned_overlays": out_dir / (
            f"{animal}_first_peak_aligned_binned_overlays.png"
        ),
    }
    if (
        overwrite == "skip"
        and all(p.exists() for p in paths.values())
    ):
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


__all__ = [
    "FAMILY_TOKENS",
    "SUB_VARIANTS",
    "TimeSeriesSessionAggregate",
    "TongueAngleCohortAggregates",
    "build_tongue_angle_cohort_aggregates",
    "build_first_peak_aligned_cohort",
]
