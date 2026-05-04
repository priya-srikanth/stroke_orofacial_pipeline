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
- 5 ``_plot_*`` family helpers consuming the bundle in-memory; each
  returns a ``matplotlib.figure.Figure`` ready for save.
- ``Agg`` non-interactive backend is forced at module-load time —
  required for headless rendering (cohort runs + CI without a display).

The module deliberately does NOT modify the 7a.3 V3 emit set or its
schemas. It consumes the in-memory bundle and the on-disk
``angle_per_frame`` parquet (the latter only as a side effect of the
bundle helper).

**History note (Phase 7a.4-orientation-and-paths-cleanup, 2026-05-03):**
the legacy-vs-consolidated comparison-grid renderer
(``render_comparison_grid``, ``_resolve_legacy_png_path``,
``_save_comparison_grid``, ``_LEGACY_SUFFIX``) was deleted once the
visual gate locked in PASS. The historical implementation lives in
git history at tag ``v7a.4-tongue-visual-and-day-binned``.
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

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from stroke_orofacial.config_loader import load_defaults  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    TongueVisualBundle,
    TrialEvent,
    build_all_licks_centered_phase_rows,
    build_first_lick_centered_phase_rows,
    build_tongue_visual_bundle,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.manifest import SessionManifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

# Family identifiers. Order matters for the ``families=None`` default
# render order.
_FAMILIES_ALL: tuple[str, ...] = (
    "qc_trials",
    "first_peak_aligned",
    "reward_aligned",
    "phase_aligned_angle",
    "xy_by_phase",
)
# Per-side family — emits 2 PNGs per session.
_PER_SIDE_FAMILIES: frozenset[str] = frozenset({"qc_trials"})

# Phase 7a.4-cross-session-angle Addendum #3 (lock #3, 2026-05-04):
# the phase-aligned-angle family is now per-mode (emits one PNG per
# entry below) rather than a single bare PNG. The bare
# ``phase_aligned_angle.png`` is retired; callers see the suffixed
# filenames listed here. Order matters for output discoverability.
# Internal mode tokens stay decoupled from user-facing suffixes:
# ``"first_lick"`` is the new selector (Addendum #3 Option C — first
# peak's phase cycle of the first multi-bout per trial);
# ``"all_multi"`` is the existing all-multi-bout selector. The
# ``"first_multi"`` mode stays in :func:`_select_phase_rows` for
# legacy callers but is no longer wired into any phase-aligned-angle
# filename.
_PHASE_ALIGNED_ANGLE_VARIANTS: tuple[tuple[str, str], ...] = (
    ("1st_lick", "first_lick"),
    ("all_licks", "all_multi"),
)
_MULTI_VARIANT_FAMILIES: frozenset[str] = frozenset({"phase_aligned_angle"})


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
    out_dir = resolver.tongue_angle_dir(animal, date)
    expected_paths_per_family = _resolve_consolidated_paths(
        out_dir, families_to_render, sides=("L", "R"),
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

    out_dir.mkdir(parents=True, exist_ok=True)
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
                png_path = out_dir / f"{family}_side_{side}.png"
                _save_and_close(fig, png_path, params=params)
                family_paths.append(png_path)
            out_paths[family] = family_paths
        elif family in _MULTI_VARIANT_FAMILIES:
            # Phase 7a.4-cross-session-angle Addendum #3 lock #3
            # (2026-05-04): emit one PNG per (suffix, mode) variant
            # listed in :data:`_PHASE_ALIGNED_ANGLE_VARIANTS`. The
            # bare ``phase_aligned_angle.png`` is retired; the driver
            # always passes ``mode`` explicitly.
            family_paths = []
            for suffix, mode in _PHASE_ALIGNED_ANGLE_VARIANTS:
                fig = _plot_phase_aligned_angle(
                    bundle, params=params, mode=mode,
                )
                png_path = out_dir / f"{family}_{suffix}.png"
                _save_and_close(fig, png_path, params=params)
                family_paths.append(png_path)
            out_paths[family] = family_paths
        else:
            fig = _PLOT_FAMILY_HELPERS[family](bundle, params=params)
            png_path = out_dir / f"{family}.png"
            _save_and_close(fig, png_path, params=params)
            out_paths[family] = [png_path]

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
    trials per side (legacy ``_plot_reward_aligned_angle``).

    Data source (Phase 7a.4-cross-session-angle, 2026-05-04, Addendum
    #8): ``angle_snip`` — the raw per-frame tongue angle from the
    upstream parquet, populated for EVERY frame in the bundle's
    ``plot_win_ms`` window regardless of bout structure. Pre-reward
    baseline (frames before t=0 where the tongue is at rest in DLC
    view), between-bout frames, and post-bout decay all contribute.
    The bout-mode distinction (``time_summary``:
    ``first_multi``/``first_bout``/``all_bouts``) is NOT applied to
    this plot family — supersedes Addendum #6's ``all_bouts`` flip,
    which is now dead config. See :func:`_pick_time_array_column`'s
    deprecation note. The cross-session reward-aligned aggregator
    (Phase 7a.4-cross-session-angle Task 3) consumes the same
    ``angle_snip`` source for byte-aligned per-session vs
    cross-session display semantics (matches the Addendum #4 pattern
    of sharing the display window).

    Display window (Phase 7a.4-cross-session-angle, 2026-05-04,
    Addendum #4): the bundle's per-trial array spans the full
    ``plot_win_ms`` (default ``[-180, 8000]`` ms) but the rendered
    x-axis is clipped to
    ``dlc_kinematics.tongue_visual.reward_aligned_display_window_ms``
    (default ``[-180, 1000]`` ms) so per-session and cross-session
    reward-aligned plots share the same x-axis byte-for-byte.
    """
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    display_win_ms = tuple(
        visual.get("reward_aligned_display_window_ms", [-180.0, 1000.0])
    )
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
        T = np.vstack(side_rows["angle_snip"].to_list()).astype(float)
        t = np.asarray(side_rows.iloc[0]["t_ms"], float)
        mu, sem, _ = _robust_mean_sem(T)
        n_trials = int(np.sum(np.any(np.isfinite(T), axis=1)))
        c = side_colors.get(side, "k")
        ax.plot(t, mu, color=c, lw=2.0, label=f"{side} (trials: {n_trials})")
        ax.fill_between(t, mu - sem, mu + sem, color=c, alpha=0.18, lw=0)

    ax.set_xlim(float(display_win_ms[0]), float(display_win_ms[1]))
    ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    ax.set_title(f"{animal} {date_str} | reward-aligned tongue angle")
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
    mode: str | None = None,
) -> Figure:
    """Family 4 — phase-aligned tongue angle. Group df_phase by
    ``phase_bin_center``; mean ± SEM across the selected multi-bout
    frames in each bin (legacy ``_plot_phase_aligned_angle``).

    ``mode`` (Phase 7a.4-cross-session-angle Addendum #3 lock #3,
    2026-05-04): selects which phase rows feed the per-bin aggregate.

      - ``"first_lick"`` — first peak's phase cycle of the first
        multi-bout per (trial, side), via
        :func:`select_first_lick_phase_rows`. New per Addendum #3
        Option C; pure pandas filter on existing df_phase + df_bouts
        columns. The user-facing PNG name is
        ``phase_aligned_angle_1st_lick.png``.
      - ``"all_multi"`` — all multi-bout phase rows (no row filter).
        Existing semantic; the user-facing PNG name is
        ``phase_aligned_angle_all_licks.png``.
      - ``"first_multi"`` — legacy/back-compat: first multi-bout per
        trial only. No longer wired into a phase_aligned_angle PNG
        filename in the production driver, but the mode token stays
        for callers that pass it explicitly.

    ``mode=None`` falls back to the config (``modes.phase_summary``).
    The production driver ``render_tongue_qc_figures`` always passes
    ``mode`` explicitly per :data:`_PHASE_ALIGNED_ANGLE_VARIANTS`.
    """
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    render = visual.get("render", {})
    min_pts = int(render.get("min_phase_points_per_bin_single", 5))
    do_smooth = bool(render.get("do_smooth_phase_curve", True))
    phase_sigma = float(render.get("phase_curve_sigma_bins", 1.0))
    if mode is None:
        phase_mode = str(visual.get("modes", {}).get(
            "phase_summary", "first_multi",
        ))
    else:
        phase_mode = str(mode)
    df_bouts = bundle.df_bouts
    df_phase = _phase_rows_for_mode(bundle, phase_mode)

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
        lick_count = _selected_phase_peak_count(
            df_bouts, phase_mode, side=side, df_phase_subset=df_phase,
        )
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

    # Cam-view convention (Phase 7a.4-orientation-fix, 2026-05-03):
    # the camera mirror-images the mouse, so mouse-left appears on the
    # right of the camera frame. Display R-trials on figure left and
    # L-trials on figure right to match the cam-view. Mirrors the
    # explicit side_to_ax mapping established by 7a.6 C7.2 in
    # mean_sem_visual.py (see _plot_mean_xy_overlays).
    ax_left, ax_right = axes[0], axes[1]
    side_to_ax = {"R": ax_left, "L": ax_right}
    sc = None
    any_points = False
    for side, ax in side_to_ax.items():
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
    out_dir: Path,
    families: Sequence[str],
    *,
    sides: Sequence[str] = ("L", "R"),
) -> dict[str, list[Path]]:
    """Compute the expected output PNG paths for each requested family."""
    out: dict[str, list[Path]] = {}
    for family in families:
        if family in _PER_SIDE_FAMILIES:
            out[family] = [
                out_dir / f"{family}_side_{side}.png" for side in sides
            ]
        elif family in _MULTI_VARIANT_FAMILIES:
            # Phase 7a.4-cross-session-angle Addendum #3 lock #3 —
            # ``phase_aligned_angle`` emits one PNG per
            # :data:`_PHASE_ALIGNED_ANGLE_VARIANTS` entry; bare
            # ``phase_aligned_angle.png`` is retired.
            out[family] = [
                out_dir / f"{family}_{suffix}.png"
                for suffix, _mode in _PHASE_ALIGNED_ANGLE_VARIANTS
            ]
        else:
            out[family] = [out_dir / f"{family}.png"]
    return out


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

    The ``"first_lick"`` mode (Phase 7a.4-cross-session-angle Addendum
    #3 Option C) is NOT handled here because it requires df_bouts as
    well as df_phase. Use :func:`_phase_rows_for_mode` for the
    full mode dispatch.
    """
    if df_phase.empty:
        return df_phase.copy()
    if mode == "all_multi":
        return df_phase.copy()
    if mode == "first_multi":
        return df_phase[df_phase["multi_bout_rank"] == 0].copy()
    raise ValueError(f"phase mode must be 'all_multi' or 'first_multi'; got {mode!r}")


def _phase_rows_for_mode(
    bundle: TongueVisualBundle, mode: str,
) -> pd.DataFrame:
    """Phase 7a.4-cross-session-angle Addenda #9 + #10 — dispatch to
    the right centered-phase builder for ``mode``.

    Routes:
      - ``"first_lick"`` → :func:`build_first_lick_centered_phase_rows`
        (peak[0]-centered, ILI = peak[1] - peak[0]). One peak per
        trial; trials with no first multi-bout contribute nothing.
      - ``"all_multi"`` →
        :func:`build_all_licks_centered_phase_rows` (every peak in
        every multi-bout, centered with forward ILI; last peak per
        bout dropped — no synthetic-ILI fallback per Addendum #10).
      - ``"first_multi"`` → falls back to the legacy peak-to-peak
        ``_select_phase_rows`` filter on ``bundle.df_phase``. Kept for
        external/back-compat callers; not wired into any production
        phase-aligned-angle PNG filename.

    Addendum #9/#10: the rendering path no longer reads from
    ``bundle.df_phase`` for ``"first_lick"`` or ``"all_multi"``
    modes. ``df_phase`` is still populated in the bundle (with the
    legacy peak-to-peak-shifted phase) for any external consumer
    that may rely on it; convention divergence documented in
    DECISIONS.
    """
    if mode == "first_lick":
        return build_first_lick_centered_phase_rows(bundle)
    if mode == "all_multi":
        return build_all_licks_centered_phase_rows(bundle)
    return _select_phase_rows(bundle.df_phase, mode)


def _selected_phase_peak_count(
    df_bouts: pd.DataFrame, mode: str, *, side: str | None = None,
    df_phase_subset: pd.DataFrame | None = None,
) -> int:
    """Count the lick peaks contributing to the phase summary.

    For the centered-phase modes (Phase 7a.4-cross-session-angle
    Addenda #9 + #10) — ``"first_lick"`` and ``"all_multi"`` — the
    count is read from the centered-phase DataFrame's ``peak_t_ms``
    column: each unique ``(trial_index, peak_t_ms)`` tuple is one
    rendered peak. Pass the already-built centered DataFrame via
    ``df_phase_subset``. Returns 0 if missing or empty.

    For the legacy ``"first_multi"`` mode (peak-to-peak-shifted phase,
    not used by any production phase-aligned-angle PNG after
    Addendum #10 but retained for back-compat callers): falls back to
    counting per-peak rows in ``df_bouts``.
    """
    if mode in ("first_lick", "all_multi"):
        if df_phase_subset is None or df_phase_subset.empty:
            return 0
        d = df_phase_subset
        if side is not None:
            d = d[d["side"] == side]
        if d.empty:
            return 0
        if "peak_t_ms" in d.columns:
            return int(len(
                d[["trial_index", "peak_t_ms"]].drop_duplicates(),
            ))
        # Centered DF without peak_t_ms shouldn't happen post-#10;
        # fall through to a trial-count for back-compat.
        return int(len(d[["trial_index"]].drop_duplicates()))
    if df_bouts.empty:
        return 0
    d = df_bouts[df_bouts["peak_t_ms"].notna()].copy()
    if side is not None:
        d = d[d["side"] == side]
    if mode == "first_multi":
        d = d[d["multi_bout_rank"] == 0]
    else:
        raise ValueError(
            f"phase mode must be 'all_multi', 'first_multi', or 'first_lick'; "
            f"got {mode!r}"
        )
    if d.empty:
        return 0
    return int(
        len(d[["trial_index", "bout_idx", "peak_t_ms"]].drop_duplicates())
    )


def _pick_time_array_column(mode: str) -> str:
    """Map ``time_summary_mode`` → df_trials column name (legacy).

    DEPRECATION-PENDING (Phase 7a.4-cross-session-angle Addendum #8,
    2026-05-04). The reward-aligned plot now consumes ``angle_snip``
    directly (the raw per-frame trace), bypassing the bout-windowed
    ``angle_*_snip`` arrays this helper returns. No active caller
    remains in this repo. Helper retained as deprecation-pending to
    preserve API surface for external/legacy scripts; remove in a
    future cleanup phase if no consumers surface.
    """
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
