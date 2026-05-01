"""Phase 7a.4 — Cell 50 visual gate: render tongue QC figures.

Ported from the canonical tongue notebook Cell 50 plot families
(``20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb``,
SHA256 ``940f172a996002f49ddae2b3fa4695bbb74b4369005426bf01160bd64c91bf2e``,
vendored at ``docs/legacy_snippets/tongue_pertrial_features.py`` lines
4474-4753). See ``.scratch_7a4/cell50_plot_families_audit.md`` (Task
1.5b output) for the per-family semantic notes.

Module shape:

- :func:`render_tongue_qc_figures` — public driver. Builds a
  :class:`TongueVisualBundle` for ``(animal, date)`` via
  :func:`build_tongue_visual_bundle_by_animal_date` and emits the 5
  plot families. Family 1 (``qc_trials``) emits 2 PNGs per session
  (one per side); families 2-5 emit 1 PNG each. Total: 6 PNGs.
- :func:`render_comparison_grid` — public driver. Reads the
  consolidated PNGs + legacy PNGs from MICROSCOPE and emits 2-col
  side-by-side comparison grids (one per family). Legacy-not-found
  → placeholder pane.
- 5 ``_plot_*`` family helpers consuming the bundle in-memory; each
  returns a ``matplotlib.figure.Figure`` ready for save.
- ``Agg`` non-interactive backend is forced at module-load time —
  required for headless rendering (cohort runs + CI without a display).

The module deliberately does NOT modify the 7a.3 V3 emit set or its
schemas. It consumes the in-memory bundle and the on-disk
``angle_per_frame`` parquet (the latter only as a side effect of the
bundle helper).
"""

from __future__ import annotations

# matplotlib backend MUST be set before any pyplot import. Required for
# headless cohort renders (no display) and to keep test runs deterministic
# across CI vs local.
import matplotlib

matplotlib.use("Agg")

import datetime  # noqa: E402  (ordering after backend setup is intentional)
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Literal, Sequence  # noqa: E402

import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    TongueVisualBundle,
    TrialEvent,
    build_tongue_visual_bundle,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.manifest import SessionManifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

# Family identifiers. Order matters for the ``families=None`` default and
# for the comparison-grid output ordering.
_FAMILIES_ALL: tuple[str, ...] = (
    "qc_trials",
    "first_peak_aligned",
    "reward_aligned",
    "phase_aligned_angle",
    "xy_by_phase",
)
# Per-side family — emits 2 PNGs per session.
_PER_SIDE_FAMILIES: frozenset[str] = frozenset({"qc_trials"})

# Legacy filename suffix patterns. ``{mouse}_{date}_anglePhase_*`` is the
# legacy naming convention preserved here for the comparison grid.
# ``{time_summary_mode}`` etc. resolve to "first_multi" by default.
_LEGACY_SUFFIX = {
    "qc_trials":          "_anglePhase_QCtrials",
    "first_peak_aligned": "_anglePhase_firstPeakAlignedAngle",
    "reward_aligned":     "_anglePhase_rewardAlignedAngle_{time_mode}",
    "phase_aligned_angle": "_anglePhase_phaseAlignedAngle_{phase_mode}",
    "xy_by_phase":        "_anglePhase_XYphase_{xy_mode}",
}


# ============================================================================
# Public API
# ============================================================================


def render_tongue_qc_figures(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    params: dict[str, Any] | None = None,
    families: Sequence[str] | None = None,
    trial_events: Sequence[TrialEvent] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
    bundle: TongueVisualBundle | None = None,
) -> dict[str, list[Path]]:
    """Render the 5 plot families for one ``(animal, date)``.

    Builds the :class:`TongueVisualBundle` internally via
    :func:`build_tongue_visual_bundle_by_animal_date` (auto-deriving
    ``trial_events`` from ``spout_behavior`` if not passed). Family 1
    (``qc_trials``) emits per-side PNGs (one per side present in the
    bundle); families 2-5 emit a single PNG each.

    Parameters
    ----------
    animal, date, resolver
        Session identifier + path resolver.
    params
        Loaded :func:`load_defaults` block. ``None`` → loads the repo
        default. Reads ``dlc_kinematics.tongue_visual.*`` for
        rendering knobs.
    families
        Iterable of family names to render. ``None`` → all 5.
    trial_events
        Optional explicit trial-events list. ``None`` → auto-derive
        via spout_behavior + alignment templates (7a.3 V3 Task 5.0
        pattern).
    overwrite
        ``"skip"`` returns existing paths if all expected PNGs exist.
        ``"force"`` always rewrites.
    bundle
        Optional pre-built bundle (test hook). When provided,
        ``trial_events`` is ignored and no upstream loading happens —
        the renderer projects from the supplied bundle directly.

    Returns
    -------
    dict[str, list[Path]]
        ``{family_name: [png_path1, ...]}`` mapping. Family 1 has up
        to 2 paths (one per side); families 2-5 have 1 each.
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(
            f"overwrite must be 'skip' or 'force'; got {overwrite!r}."
        )
    if params is None:
        params = load_defaults()
    if families is None:
        families_to_render = list(_FAMILIES_ALL)
    else:
        for f in families:
            if f not in _FAMILIES_ALL:
                raise ValueError(
                    f"Unknown family {f!r}. Known: {sorted(_FAMILIES_ALL)}"
                )
        families_to_render = list(families)

    # Pre-resolve every expected output path (used for skip-decision and
    # for the return dict).
    qc_dir = resolver.tongue_visual_qc_dir(animal, date)
    expected_paths_per_family = _resolve_consolidated_paths(
        qc_dir, families_to_render, sides=("L", "R"),
    )

    # Skip-fast: if every PNG exists and overwrite=skip, return immediately.
    if overwrite == "skip":
        all_present = all(
            p.exists()
            for paths in expected_paths_per_family.values()
            for p in paths
        )
        if all_present and expected_paths_per_family:
            return expected_paths_per_family

    # Bundle materialisation. Pre-built bundle wins; otherwise auto-build.
    if bundle is None:
        bundle = build_tongue_visual_bundle_by_animal_date(
            animal=animal,
            date=date,
            resolver=resolver,
            trial_events=trial_events,
            params=params,
        )

    qc_dir.mkdir(parents=True, exist_ok=True)
    out_paths: dict[str, list[Path]] = {}
    sides_present = (
        sorted(bundle.df_trials["side"].unique())
        if not bundle.df_trials.empty
        else []
    )

    for family in families_to_render:
        if family in _PER_SIDE_FAMILIES:
            family_paths: list[Path] = []
            for side in sides_present:
                fig = _plot_per_trial_qc_traces(bundle, side, params=params)
                png_path = qc_dir / f"{family}_side_{side}.png"
                _save_and_close(fig, png_path, params=params)
                family_paths.append(png_path)
            out_paths[family] = family_paths
        else:
            fig = _PLOT_FAMILY_HELPERS[family](bundle, params=params)
            png_path = qc_dir / f"{family}.png"
            _save_and_close(fig, png_path, params=params)
            out_paths[family] = [png_path]

    return out_paths


def render_comparison_grid(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    legacy_figures_root: Path,
    *,
    params: dict[str, Any] | None = None,
    families: Sequence[str] | None = None,
    sides: Sequence[str] = ("L", "R"),
) -> dict[str, list[Path]]:
    """Render legacy-vs-consolidated side-by-side comparison grids.

    Reads consolidated PNGs from
    :meth:`PathResolver.tongue_visual_qc_dir` and legacy PNGs from
    ``legacy_figures_root`` (e.g.
    ``\\\\research.files...\\angle_phase_exploratory\\``). Each output
    PNG is a 2-column grid (legacy ┃ consolidated) for one family. If
    the legacy PNG is missing, the legacy pane is rendered as a
    placeholder with the annotation ``"legacy figure not found"``.

    Output paths land under
    :meth:`PathResolver.tongue_visual_comparison_dir`.

    Returns
    -------
    dict[str, list[Path]]
        ``{family_name: [comparison_grid_path1, ...]}``. Family 1
        emits per-side comparison grids (up to 2); families 2-5 emit
        1 each.
    """
    if params is None:
        params = load_defaults()
    if families is None:
        families_to_grid = list(_FAMILIES_ALL)
    else:
        for f in families:
            if f not in _FAMILIES_ALL:
                raise ValueError(
                    f"Unknown family {f!r}. Known: {sorted(_FAMILIES_ALL)}"
                )
        families_to_grid = list(families)

    visual = params["dlc_kinematics"]["tongue_visual"]
    cmp_cfg = visual.get("comparison_grid", {})
    cmp_cols = int(cmp_cfg.get("cols", 2))
    if cmp_cols != 2:
        raise NotImplementedError(
            "Only the legacy-vs-consolidated 2-column comparison grid is "
            f"implemented; got cols={cmp_cols}."
        )

    qc_dir = resolver.tongue_visual_qc_dir(animal, date)
    cmp_dir = resolver.tongue_visual_comparison_dir(animal, date)
    cmp_dir.mkdir(parents=True, exist_ok=True)

    modes = visual.get("modes", {})
    time_mode = str(modes.get("time_summary", "first_multi"))
    phase_mode = str(modes.get("phase_summary", "first_multi"))
    xy_mode = str(modes.get("xy_summary", "first_multi"))

    out_paths: dict[str, list[Path]] = {}
    for family in families_to_grid:
        if family in _PER_SIDE_FAMILIES:
            grid_paths: list[Path] = []
            for side in sides:
                consolidated = qc_dir / f"{family}_side_{side}.png"
                legacy = _resolve_legacy_png_path(
                    family, animal, date, legacy_figures_root,
                    side=side,
                    time_mode=time_mode,
                    phase_mode=phase_mode,
                    xy_mode=xy_mode,
                )
                grid_path = cmp_dir / f"{family}_side_{side}_comparison.png"
                _save_comparison_grid(
                    consolidated, legacy, grid_path,
                    title=f"{animal} {date.isoformat()} | {family} | side={side}",
                    params=params,
                )
                grid_paths.append(grid_path)
            out_paths[family] = grid_paths
        else:
            consolidated = qc_dir / f"{family}.png"
            legacy = _resolve_legacy_png_path(
                family, animal, date, legacy_figures_root,
                side=None,
                time_mode=time_mode,
                phase_mode=phase_mode,
                xy_mode=xy_mode,
            )
            grid_path = cmp_dir / f"{family}_comparison.png"
            _save_comparison_grid(
                consolidated, legacy, grid_path,
                title=f"{animal} {date.isoformat()} | {family}",
                params=params,
            )
            out_paths[family] = [grid_path]

    return out_paths


# ============================================================================
# Plot family helpers
# ============================================================================


def _plot_per_trial_qc_traces(
    bundle: TongueVisualBundle,
    side: str,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 1 — per-side QC: stacked Y + angle traces with bout shading
    + peak markers (legacy ``_plot_qc_trials``)."""
    visual = params["dlc_kinematics"]["tongue_visual"]
    fam = visual["plot_families"]["qc_trials"]
    side_color = visual["side_colors"].get(side, "k")
    n_view = int(fam.get("view_n_trials_per_side", 10))
    detect_alpha = float(fam.get("detect_alpha", 0.035))
    bout_alpha = float(fam.get("bout_alpha", 0.012))
    peak_size = float(fam.get("peak_size", 18))
    detect_win_ms = tuple(visual["bundle"]["detect_win_ms"])

    df_trials = bundle.df_trials
    df_bouts = bundle.df_bouts
    if df_trials.empty:
        return _empty_figure(f"side={side}: no trials in bundle")

    side_trials = df_trials[df_trials["side"] == side]
    if side_trials.empty:
        return _empty_figure(f"side={side}: no trials of this side")
    trial_ids = sorted(side_trials["trial_index"].unique().tolist())[:n_view]
    if not trial_ids:
        return _empty_figure(f"side={side}: no trial ids")

    fig, (ax_y, ax_a) = plt.subplots(
        2, 1, figsize=(12, max(4.5, 0.8 * len(trial_ids) + 2)), sharex=True,
    )

    # Detection-window shading.
    ax_y.axvspan(detect_win_ms[0], detect_win_ms[1], color="0.25", alpha=detect_alpha, zorder=0)
    ax_a.axvspan(detect_win_ms[0], detect_win_ms[1], color="0.25", alpha=detect_alpha, zorder=0)
    for ax in (ax_y, ax_a):
        ax.axvline(detect_win_ms[0], color="0.4", ls="--", lw=1.0, alpha=0.8)
        ax.axvline(detect_win_ms[1], color="0.4", ls="--", lw=1.0, alpha=0.8)

    # Compute per-trace y-offset from 5-95 percentile range, mirroring legacy.
    ranges_y, ranges_a = [], []
    for tid in trial_ids:
        rr = side_trials[side_trials["trial_index"] == tid].iloc[0]
        yw = np.asarray(rr["y_snip"], float)
        aw = np.asarray(rr["angle_snip"], float)
        if np.any(np.isfinite(yw)):
            ranges_y.append(np.nanpercentile(yw, 95) - np.nanpercentile(yw, 5))
        if np.any(np.isfinite(aw)):
            ranges_a.append(np.nanpercentile(aw, 95) - np.nanpercentile(aw, 5))
    dy_off = 1.2 * np.nanmedian(ranges_y) if ranges_y else 50.0
    da_off = 1.2 * np.nanmedian(ranges_a) if ranges_a else 30.0

    # Bout-window + peak rows, filtered by side.
    side_bouts = df_bouts[df_bouts["side"] == side] if not df_bouts.empty else df_bouts

    for j, tid in enumerate(trial_ids):
        trial_row = side_trials[side_trials["trial_index"] == tid].iloc[0]
        t = np.asarray(trial_row["t_ms"], float)
        yw = np.asarray(trial_row["y_snip"], float)
        aw = np.asarray(trial_row["angle_snip"], float)
        yoff = j * dy_off
        aoff = j * da_off
        ax_y.plot(t, yw + yoff, color=side_color, lw=1.2, alpha=0.9, zorder=2)
        ax_a.plot(t, aw + aoff, color=side_color, lw=1.2, alpha=0.9, zorder=2)

        if not side_bouts.empty:
            sub = side_bouts[side_bouts["trial_index"] == tid]
            if not sub.empty:
                # Bout-summary rows (peak_t_ms NaN) carry bout_t0/t1.
                summary = (
                    sub[sub["peak_t_ms"].isna()]
                    [["bout_t0_ms", "bout_t1_ms"]]
                    .drop_duplicates()
                    .sort_values(["bout_t0_ms", "bout_t1_ms"])
                )
                for _, brow in summary.iterrows():
                    ax_y.axvspan(
                        float(brow["bout_t0_ms"]), float(brow["bout_t1_ms"]),
                        color=side_color, alpha=bout_alpha, zorder=1,
                    )
                    ax_a.axvspan(
                        float(brow["bout_t0_ms"]), float(brow["bout_t1_ms"]),
                        color=side_color, alpha=bout_alpha, zorder=1,
                    )
                # Per-peak rows (bout_t0_ms NaN, peak_t_ms set).
                peaks = sub[sub["peak_t_ms"].notna()]
                if not peaks.empty:
                    ax_y.scatter(
                        peaks["peak_t_ms"], peaks["peak_y"] + yoff,
                        s=peak_size, color="k", zorder=5,
                    )
                    ax_a.scatter(
                        peaks["peak_t_ms"], peaks["peak_angle_deg"] + aoff,
                        s=peak_size, color="k", zorder=5,
                    )

        ax_y.text(t[0] if len(t) else 0, yoff, f"trial {tid}",
                  fontsize=8, va="bottom", ha="left")
        ax_a.text(t[0] if len(t) else 0, aoff, f"trial {tid}",
                  fontsize=8, va="bottom", ha="left")

    for ax in (ax_y, ax_a):
        ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
        ax.set_yticks([])
        ax.grid(True, alpha=0.15)

    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    ax_y.set_title(f"{animal} {date_str} | {side} trials | QC: Y + bouts/peaks")
    ax_a.set_title(f"{animal} {date_str} | {side} trials | QC: angle + bouts/peaks")
    ax_y.set_ylabel("Tongue Y (offset)")
    ax_a.set_ylabel("Angle (deg, offset)")
    ax_a.set_xlabel("Time from reward (ms)")

    plt.tight_layout()
    return fig


def _plot_first_peak_aligned(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 2 — session-wide first-peak-aligned tongue angle. Mu±SEM
    across trials per side (legacy ``_plot_first_peak_aligned_angle``)."""
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    df_trials = bundle.df_trials

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    if df_trials.empty:
        ax.text(0.5, 0.5, "No trials in bundle", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    for side in sorted(df_trials["side"].unique()):
        side_rows = df_trials[
            (df_trials["side"] == side)
            & df_trials["first_peak_t_ms"].notna()
        ]
        if side_rows.empty:
            continue
        T = np.vstack(side_rows["angle_firstpeak_snip"].to_list()).astype(float)
        t = np.asarray(side_rows.iloc[0]["t_firstpeak_align_ms"], float)
        mu, sem, _ = _robust_mean_sem(T)
        n_trials = int(np.sum(np.any(np.isfinite(T), axis=1)))
        c = side_colors.get(side, "k")
        ax.plot(t, mu, color=c, lw=2.0, label=f"{side} (trials: {n_trials})")
        ax.fill_between(t, mu - sem, mu + sem, color=c, alpha=0.18, lw=0)

    ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    ax.set_title(f"{animal} {date_str} | angle aligned to first detected lick peak")
    ax.set_xlabel("Time from first detected lick peak (ms)")
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()
    return fig


def _plot_reward_aligned(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 3 — session-wide reward-aligned tongue angle. Mu±SEM across
    trials per side (legacy ``_plot_reward_aligned_angle``)."""
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    time_mode = str(visual.get("modes", {}).get("time_summary", "first_multi"))
    arr_col = _pick_time_array_column(time_mode)
    df_trials = bundle.df_trials

    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    if df_trials.empty:
        ax.text(0.5, 0.5, "No trials in bundle", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    for side in sorted(df_trials["side"].unique()):
        side_rows = df_trials[df_trials["side"] == side]
        if side_rows.empty:
            continue
        T = np.vstack(side_rows[arr_col].to_list()).astype(float)
        t = np.asarray(side_rows.iloc[0]["t_ms"], float)
        mu, sem, _ = _robust_mean_sem(T)
        n_trials = int(np.sum(np.any(np.isfinite(T), axis=1)))
        c = side_colors.get(side, "k")
        ax.plot(t, mu, color=c, lw=2.0, label=f"{side} (trials: {n_trials})")
        ax.fill_between(t, mu - sem, mu + sem, color=c, alpha=0.18, lw=0)

    ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    ax.set_title(
        f"{animal} {date_str} | reward-aligned tongue angle | mode={time_mode}"
    )
    ax.set_xlabel("Time from reward (ms)")
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()
    return fig


def _plot_phase_aligned_angle(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 4 — phase-aligned tongue angle. Group df_phase by
    ``phase_bin_center``; mean ± SEM across all multi-bout frames in
    each bin (legacy ``_plot_phase_aligned_angle``)."""
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    render = visual.get("render", {})
    min_pts = int(render.get("min_phase_points_per_bin_single", 5))
    do_smooth = bool(render.get("do_smooth_phase_curve", True))
    phase_sigma = float(render.get("phase_curve_sigma_bins", 1.0))
    phase_mode = str(visual.get("modes", {}).get(
        "phase_summary", "first_multi",
    ))
    df_phase = _select_phase_rows(bundle.df_phase, phase_mode)
    df_bouts = bundle.df_bouts

    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    if df_phase.empty:
        ax.text(0.5, 0.5, f"No phase rows for mode={phase_mode}",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    for side in sorted(df_phase["side"].unique()):
        dd = df_phase[df_phase["side"] == side]
        if dd.empty:
            continue
        grouped = dd.groupby("phase_bin_center", as_index=False).agg(
            angle_mean=("angle_deg", "mean"),
            angle_sem=("angle_deg", _np_sem_ddof0),
            n=("angle_deg", lambda v: int(np.sum(np.isfinite(np.asarray(v, float))))),
        )
        x = grouped["phase_bin_center"].to_numpy(float).copy()
        m = grouped["angle_mean"].to_numpy(float).copy()
        s = grouped["angle_sem"].to_numpy(float).copy()
        n = grouped["n"].to_numpy(float).copy()
        m[n < min_pts] = np.nan
        s[n < min_pts] = np.nan
        if do_smooth and phase_sigma > 0:
            m = _circular_gaussian_smooth(m, phase_sigma)
            s = _circular_gaussian_smooth(s, phase_sigma)
        lick_count = _selected_phase_peak_count(df_bouts, phase_mode, side=side)
        c = side_colors.get(side, "k")
        ax.plot(x, m, color=c, lw=2.0, label=f"{side} (licks: {lick_count})")
        ax.fill_between(x, m - s, m + s, color=c, alpha=0.18, lw=0)

    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    ax.axvline(0.0, color="0.7", lw=1.0, ls="--")
    ax.axvline(0.5, color="0.7", lw=1.0, ls="--")
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    ax.set_title(
        f"{animal} {date_str} | phase-aligned tongue angle | mode={phase_mode}"
    )
    ax.set_xlabel(
        "Normalized lick phase (0 = between peaks, 0.5 = peak protrusion)"
    )
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()
    return fig


def _plot_xy_by_phase(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 5 — XY tongue location coloured by lick-cycle phase.
    Per-side panels sharing axes (legacy ``_plot_xy_colored_by_phase``)."""
    visual = params["dlc_kinematics"]["tongue_visual"]
    fam = visual["plot_families"]["xy_by_phase"]
    cmap_name = str(fam.get("cmap", "twilight"))
    sc_size = float(fam.get("scatter_size", 8))
    sc_alpha = float(fam.get("scatter_alpha", 0.65))
    xy_mode = str(visual.get("modes", {}).get("xy_summary", "first_multi"))

    df_phase = _select_phase_rows(bundle.df_phase, xy_mode)
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), sharex=True, sharey=True)
    norm = Normalize(vmin=0.0, vmax=1.0)
    fig.subplots_adjust(right=0.86, wspace=0.08)

    # Symmetric x-extent from data; legacy adds 5% padding.
    if df_phase.empty:
        xmax = 50.0
    else:
        x_all = pd.to_numeric(df_phase["x_geom"], errors="coerce").to_numpy(float)
        xmax = (
            float(np.nanmax(np.abs(x_all))) * 1.05
            if x_all.size and np.any(np.isfinite(x_all)) else 50.0
        )
        xmax = max(1.0, xmax)

    sides = ("L", "R")
    sc = None
    any_points = False
    for ax, side in zip(axes, sides):
        ax.set_title(f"{side} trials")
        ax.set_xlabel("Tongue X (spout-centered px)")
        ax.set_xlim(-xmax, xmax)
        ax.grid(True, alpha=0.15)
        if df_phase.empty:
            ax.text(0.5, 0.5, "No multi-lick bouts",
                    ha="center", va="center", transform=ax.transAxes)
            continue
        dd = df_phase[df_phase["side"] == side]
        if dd.empty:
            ax.text(0.5, 0.5, "No multi-lick bouts",
                    ha="center", va="center", transform=ax.transAxes)
            continue
        any_points = True
        sc = ax.scatter(
            dd["x_geom"], dd["y_geom"],
            c=dd["phase"], cmap=cmap_name, norm=norm,
            s=sc_size, alpha=sc_alpha, edgecolors="none",
        )

    axes[0].set_ylabel("Tongue Y (geom source)")
    for ax in axes:
        if not ax.yaxis_inverted():
            ax.invert_yaxis()

    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    fig.suptitle(
        f"{animal} {date_str} | XY trajectory coloured by phase | mode={xy_mode}",
        y=0.98,
    )
    if any_points and sc is not None:
        cax = fig.add_axes([0.875, 0.16, 0.015, 0.68])
        cbar = fig.colorbar(sc, cax=cax)
        cbar.set_label("Normalized phase")
    return fig


# Family-name → helper dispatch (qc_trials handled separately because it
# is per-side; the rest take the bundle directly).
_PLOT_FAMILY_HELPERS = {
    "first_peak_aligned":  _plot_first_peak_aligned,
    "reward_aligned":      _plot_reward_aligned,
    "phase_aligned_angle": _plot_phase_aligned_angle,
    "xy_by_phase":         _plot_xy_by_phase,
}


# ============================================================================
# Helpers (private)
# ============================================================================


def _resolve_consolidated_paths(
    qc_dir: Path,
    families: Sequence[str],
    *,
    sides: Sequence[str] = ("L", "R"),
) -> dict[str, list[Path]]:
    """Compute the expected output PNG paths for each requested family."""
    out: dict[str, list[Path]] = {}
    for family in families:
        if family in _PER_SIDE_FAMILIES:
            out[family] = [
                qc_dir / f"{family}_side_{side}.png" for side in sides
            ]
        else:
            out[family] = [qc_dir / f"{family}.png"]
    return out


def _resolve_legacy_png_path(
    family: str,
    animal: str,
    date: datetime.date,
    legacy_root: Path,
    *,
    side: str | None,
    time_mode: str,
    phase_mode: str,
    xy_mode: str,
) -> Path | None:
    """Resolve a legacy PNG candidate path. Returns ``None`` if missing.

    Legacy filename conventions (Cell 50 vendor lines 4556, 4592, 4628,
    4687, 4747):

    - qc_trials:           ``{mouse}_{YYYYMMDD}_{side}_anglePhase_QCtrials.png``
    - first_peak_aligned:  ``{mouse}_{YYYYMMDD}_anglePhase_firstPeakAlignedAngle.png``
    - reward_aligned:      ``{mouse}_{YYYYMMDD}_anglePhase_rewardAlignedAngle_{time_mode}.png``
    - phase_aligned_angle: ``{mouse}_{YYYYMMDD}_anglePhase_phaseAlignedAngle_{phase_mode}.png``
    - xy_by_phase:         ``{mouse}_{YYYYMMDD}_anglePhase_XYphase_{xy_mode}.png``
    """
    suffix = _LEGACY_SUFFIX[family].format(
        time_mode=time_mode, phase_mode=phase_mode, xy_mode=xy_mode,
    )
    date_str = date.strftime("%Y%m%d")
    if family == "qc_trials":
        if side is None:
            return None
        name = f"{animal}_{date_str}_{side}{suffix}.png"
    else:
        name = f"{animal}_{date_str}{suffix}.png"
    candidate = legacy_root / name
    return candidate if candidate.exists() else None


def _save_and_close(fig: Figure, path: Path, *, params: dict[str, Any]) -> None:
    """Save a figure to ``path`` (atomic-ish: temp + replace) and close it.

    The temp filename keeps the ``.png`` extension and adds a ``.tmp``
    middle segment so matplotlib's format-by-extension inference resolves
    correctly (a ``.png.tmp`` filename would be rejected as an unsupported
    format).
    """
    visual = params["dlc_kinematics"]["tongue_visual"]
    dpi = float(visual.get("figure", {}).get("dpi", 200))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp" + path.suffix)
    fig.savefig(tmp, dpi=dpi, bbox_inches="tight", format="png")
    plt.close(fig)
    tmp.replace(path)


def _save_comparison_grid(
    consolidated: Path,
    legacy: Path | None,
    out_path: Path,
    *,
    title: str,
    params: dict[str, Any],
) -> None:
    """Render a 2-column comparison grid (legacy | consolidated) to disk.

    ``legacy=None`` triggers a placeholder pane with "legacy figure not
    found" annotation. Consolidated is always loaded; if it doesn't
    exist either, the cell renders a similar placeholder so the grid
    is at least non-empty.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    titles = ("legacy", "consolidated")
    panes: list[Path | None] = [legacy, consolidated]
    for ax, pane_path, label in zip(axes, panes, titles):
        if pane_path is not None and pane_path.exists():
            try:
                img = mpimg.imread(str(pane_path))
                ax.imshow(img)
            except Exception as exc:  # noqa: BLE001 — best-effort renderer
                ax.text(0.5, 0.5, f"{label}: unreadable\n{exc}",
                        ha="center", va="center", transform=ax.transAxes)
        else:
            label_str = (
                "legacy figure not found"
                if label == "legacy" else "consolidated PNG missing"
            )
            ax.text(0.5, 0.5, label_str, ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
        ax.set_title(label)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title, y=0.98)
    _save_and_close(fig, out_path, params=params)


def _empty_figure(message: str) -> Figure:
    """Return a 1-axes Figure with a centred message (used when a plot
    family has no data to render). Keeps the `Figure has at least one
    Axes` invariant so the smoke tests don't crash."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, message, ha="center", va="center",
            transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    return fig


def _robust_mean_sem(M: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``np.nanmean`` + ddof=0 SEM (legacy Cell 50 ``_robust_mean_sem``).

    Different from the day-binner aggregator which uses ddof=1 (Task 3).
    Cell 50 plot families use ddof=0 across trials within a session,
    matching the legacy renderer.
    """
    M = np.asarray(M, float)
    if M.ndim == 1:
        M = M[None, :]
    n = np.sum(np.isfinite(M), axis=0)
    with warnings.catch_warnings():
        # nanmean / nanstd emit benign warnings on all-NaN columns; the
        # output is correctly NaN there (good[col]==False), so suppress.
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning,
            message=r"(Mean of empty slice|Degrees of freedom <= 0)",
        )
        mu = np.nanmean(M, axis=0)
        sd = np.nanstd(M, axis=0, ddof=0)
    sem = np.full_like(mu, np.nan)
    good = n > 0
    sem[good] = sd[good] / np.sqrt(np.maximum(1, n[good]))
    return mu, sem, n


def _np_sem_ddof0(values: pd.Series | np.ndarray) -> float:
    """ddof=0 SEM scalar (groupby-agg helper for family 4)."""
    arr = np.asarray(values, float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return float("nan")
    return float(np.nanstd(arr, ddof=0) / np.sqrt(max(1, int(finite.size))))


def _circular_gaussian_smooth(y: np.ndarray, sigma_bins: float) -> np.ndarray:
    """NaN-aware circular Gaussian smoothing (legacy uses
    ``scipy.ndimage.gaussian_filter1d`` with ``mode='wrap'``)."""
    from scipy.ndimage import gaussian_filter1d
    y = np.asarray(y, float)
    if sigma_bins <= 0 or not np.any(np.isfinite(y)):
        return y.copy()
    finite = np.isfinite(y).astype(float)
    y0 = np.where(np.isfinite(y), y, 0.0)
    num = gaussian_filter1d(y0, sigma=sigma_bins, mode="wrap")
    den = gaussian_filter1d(finite, sigma=sigma_bins, mode="wrap")
    out = np.full_like(y, np.nan)
    good = den > 1e-8
    out[good] = num[good] / den[good]
    return out


def _select_phase_rows(df_phase: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Filter df_phase by phase_summary_mode (legacy ``_select_phase_rows``).

    - ``"all_multi"``: keep all multi-bout rows (no filter — all df_phase
      rows are already from multi-bouts by construction).
    - ``"first_multi"``: keep rows with ``multi_bout_rank == 0``.
    """
    if df_phase.empty:
        return df_phase.copy()
    if mode == "all_multi":
        return df_phase.copy()
    if mode == "first_multi":
        return df_phase[df_phase["multi_bout_rank"] == 0].copy()
    raise ValueError(f"phase mode must be 'all_multi' or 'first_multi'; got {mode!r}")


def _selected_phase_peak_count(
    df_bouts: pd.DataFrame, mode: str, *, side: str | None = None,
) -> int:
    """Count the lick peaks contributing to the phase summary.

    Per-peak rows in df_bouts have ``peak_t_ms`` set; bout-summary rows
    have ``peak_t_ms`` NaN. Filter by mode + optional side, count unique
    (trial_index, bout_idx, peak_t_ms) tuples.
    """
    if df_bouts.empty:
        return 0
    d = df_bouts[df_bouts["peak_t_ms"].notna()].copy()
    if side is not None:
        d = d[d["side"] == side]
    if mode == "first_multi":
        d = d[d["multi_bout_rank"] == 0]
    elif mode == "all_multi":
        d = d[d["multi_bout_rank"].notna()]
    else:
        raise ValueError(
            f"phase mode must be 'all_multi' or 'first_multi'; got {mode!r}"
        )
    if d.empty:
        return 0
    return int(
        len(d[["trial_index", "bout_idx", "peak_t_ms"]].drop_duplicates())
    )


def _pick_time_array_column(mode: str) -> str:
    """Map ``time_summary_mode`` → df_trials column name (legacy)."""
    return {
        "all_bouts":   "angle_allbouts_snip",
        "first_bout":  "angle_firstbout_snip",
        "first_multi": "angle_firstmulti_snip",
    }[mode]


# Public helpers exported for the parity runner (Task 5).
def render_for_manifest(
    manifest: SessionManifest,
    resolver: PathResolver,
    *,
    trial_events: Sequence[TrialEvent] | None = None,
    params: dict[str, Any] | None = None,
    families: Sequence[str] | None = None,
    overwrite: Literal["skip", "force"] = "skip",
) -> dict[str, list[Path]]:
    """Render directly from a :class:`SessionManifest` (Task 5 hook).

    Builds the bundle via :func:`build_tongue_visual_bundle` (no
    :func:`get_animal` lookup required since the manifest already
    carries the animal info). Trial events must either be provided
    explicitly or auto-derived by the caller.
    """
    if params is None:
        params = load_defaults()
    if trial_events is None:
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            _derive_trial_events_from_spout_behavior,
        )
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=manifest.animal, date=manifest.date,
            resolver=resolver, manifest=manifest,
        )
    bundle = build_tongue_visual_bundle(
        manifest=manifest, resolver=resolver,
        trial_events=trial_events, params=params,
    )
    return render_tongue_qc_figures(
        animal=manifest.animal, date=manifest.date, resolver=resolver,
        params=params, families=families,
        overwrite=overwrite, bundle=bundle,
    )
