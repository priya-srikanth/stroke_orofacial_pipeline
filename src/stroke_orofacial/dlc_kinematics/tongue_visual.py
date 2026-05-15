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
    build_first_n_licks_centered_phase_rows,
    build_tongue_visual_bundle,
    build_tongue_visual_bundle_by_animal_date,
    extract_first_vs_second_peak_pairs,
)
from stroke_orofacial.manifest import SessionManifest  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402

# Family identifiers. Order matters for the ``families=None`` default
# render order.
_FAMILIES_ALL: tuple[str, ...] = (
    "qc_trials",
    "first_peak_aligned",
    "tone_aligned",
    "phase_aligned_angle",
    "first_vs_second_peak_scatter",
    "xy_by_phase",
)
# Per-side family — emits 2 PNGs per session.
_PER_SIDE_FAMILIES: frozenset[str] = frozenset({"qc_trials"})

# Phase 7a.4-cross-session-angle Addendum #3 (lock #3, 2026-05-04):
# the phase-aligned-angle family is per-mode (emits one PNG per
# variant returned by :func:`_phase_aligned_angle_variants`) rather
# than a single bare PNG. The bare ``phase_aligned_angle.png`` is
# retired; callers see the suffixed filenames.
#
# Addendum #11 Part A (2026-05-04): the variant list is now
# config-aware — the ``first_{N}_licks`` variant pulls ``N`` from
# ``dlc_kinematics.tongue_visual.phase_aligned_first_n_peaks``
# (default 2), so the suffix and the helper kwarg track the same
# config knob. ``_phase_aligned_angle_variants(params)`` is the
# single source of truth for the variant set; the driver and the
# skip-fast path resolver both call it.
_MULTI_VARIANT_FAMILIES: frozenset[str] = frozenset({"phase_aligned_angle"})


def _phase_aligned_angle_variants(
    params: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Return the list of ``(filename_suffix, mode, mode_kwargs)``
    triples for the phase_aligned_angle family.

    Order matters for output discoverability and for the skip-fast
    path. Each triple emits one PNG named
    ``phase_aligned_angle_{suffix}.png``.

    Variants:
      - ``("1st_lick", "first_lick", {})`` — Addendum #9 centered on
        peak[0] of the first multi-bout.
      - ``("all_licks", "all_multi", {})`` — Addendum #10 centered
        on every peak in every multi-bout (last peak per bout
        dropped).
      - ``("first_{N}_licks", "first_n_licks", {"n_peaks": N})`` —
        Addendum #11 Part A; N consecutive licks of the first
        multi-bout, each centered in its own [i, i+1] cycle.
        ``N`` from
        ``params["dlc_kinematics"]["tongue_visual"]["phase_aligned_first_n_peaks"]``
        (default 2).
    """
    visual = params.get("dlc_kinematics", {}).get("tongue_visual", {})
    n_peaks = int(visual.get("phase_aligned_first_n_peaks", 2))
    return [
        ("1st_lick", "first_lick", {}),
        ("all_licks", "all_multi", {}),
        (f"first_{n_peaks}_licks", "first_n_licks", {"n_peaks": n_peaks}),
    ]


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
    out_dir = resolver.tongue_angle_within_session_dir(animal, date)
    expected_paths_per_family = _resolve_consolidated_paths(
        out_dir, families_to_render, sides=("L", "R"), params=params,
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
            # (2026-05-04) + Addendum #11 Part A (2026-05-04): emit
            # one PNG per (suffix, mode, mode_kwargs) variant
            # returned by :func:`_phase_aligned_angle_variants`. The
            # bare ``phase_aligned_angle.png`` is retired; the
            # driver always passes ``mode`` explicitly + any
            # mode-specific kwargs (e.g., ``n_peaks`` for
            # ``"first_n_licks"``).
            family_paths = []
            for suffix, mode, mode_kwargs in (
                _phase_aligned_angle_variants(params)
            ):
                fig = _plot_phase_aligned_angle(
                    bundle, params=params, mode=mode, **mode_kwargs,
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


def _plot_tone_aligned(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Family 3 — session-wide reward-aligned tongue angle. Mu±SEM across
    trials per side (legacy ``_plot_tone_aligned_angle``).

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
    ``dlc_kinematics.tongue_visual.tone_aligned_display_window_ms``
    (default ``[-180, 1000]`` ms) so per-session and cross-session
    reward-aligned plots share the same x-axis byte-for-byte.
    """
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    display_win_ms = tuple(
        visual.get("tone_aligned_display_window_ms", [-180.0, 1000.0])
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
    n_peaks: int | None = None,
    ili_source: Literal[
        "real_only", "hybrid", "synthetic_only",
    ] | None = None,
) -> Figure:
    """Family 4 — phase-aligned tongue angle. Group selected
    centered-phase rows by ``phase_bin_center``; mean ± SEM across
    selected frames in each bin.

    ``mode`` selects which phase-row builder feeds the per-bin
    aggregate (see :func:`_phase_rows_for_mode`):

      - ``"first_lick"`` (Addendum #9) → single-cycle plot,
        x ∈ [0, 1].
      - ``"all_multi"`` (Addendum #10) → single-cycle plot,
        x ∈ [0, 1].
      - ``"first_n_licks"`` (Addendum #11 Part A) → multi-cycle
        plot, x ∈ [0, ``n_peaks``]. ``n_peaks`` defaults to the
        ``phase_aligned_first_n_peaks`` config knob (= 2) when
        ``None``; otherwise honours the explicit kwarg.
      - ``"first_multi"`` → legacy peak-to-peak shifted; not wired
        into a production filename.

    ``mode=None`` falls back to the config ``modes.phase_summary``
    knob. The production driver
    :func:`render_tongue_qc_figures` always passes ``mode`` (and
    ``n_peaks`` when applicable) explicitly per
    :func:`_phase_aligned_angle_variants`.
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
    if n_peaks is None:
        n_peaks_val = int(visual.get("phase_aligned_first_n_peaks", 2))
    else:
        n_peaks_val = int(n_peaks)

    # Phase 7a.4-cross-session-angle Addendum #15 (2026-05-04):
    # ``phase_aligned_ili_source`` config knob (default
    # ``"synthetic_only"`` per Addendum #14b verdict — Mode 3 won
    # across all three centered-phase families on the PS46/PS50/PS55
    # visual gate). The renderer always passes a finite synthetic
    # ILI alongside synthetic_only / hybrid; real_only ignores it.
    # NaN-fallback: when ``synthetic_only`` is configured but the
    # animal's pre-stroke median is non-finite (no pre-stroke
    # sessions on disk), silently degrade to ``real_only`` rather
    # than raise — same defensive pattern as Addendum #12.
    #
    # Explicit ``ili_source`` kwarg overrides the config knob (used
    # by the Addendum #14 diagnostic 3-way comparison test driver).
    if ili_source is None:
        configured_ili_source = str(
            visual.get("phase_aligned_ili_source", "synthetic_only")
        )
    else:
        configured_ili_source = str(ili_source)

    synthetic_ili_ms_val = bundle.metadata.get(
        "pre_stroke_median_ili_ms", float("nan"),
    )
    synth_finite = (
        synthetic_ili_ms_val is not None
        and np.isfinite(float(synthetic_ili_ms_val))
        and float(synthetic_ili_ms_val) > 0
    )
    if (
        configured_ili_source == "synthetic_only"
        and not synth_finite
    ):
        # NaN-fallback: animal has no pre-stroke baseline → use
        # multi-bout-only.
        ili_source_val = "real_only"
    else:
        ili_source_val = configured_ili_source

    df_bouts = bundle.df_bouts
    df_phase = _phase_rows_for_mode(
        bundle, phase_mode,
        n_peaks=n_peaks_val,
        synthetic_ili_ms=synthetic_ili_ms_val,
        ili_source=ili_source_val,
    )

    is_multi_cycle = phase_mode == "first_n_licks"
    x_max = float(n_peaks_val) if is_multi_cycle else 1.0

    # Figure width tracks the x-span so a 2-peak plot is wider than a
    # 1-peak plot. Base 8.0 inches per cycle (matching the existing
    # single-cycle plot width).
    fig_width = 8.0 * x_max
    fig, ax = plt.subplots(figsize=(fig_width, 4.2))
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
        # Circular smoothing only makes sense on the single-cycle
        # plots where x=0 and x=1 are physically the same retracted
        # position. For multi-cycle (Addendum #11 Part A), x=0 and
        # x=n_peaks are physically different moments — wrap-around
        # smoothing would bleed peak[n-1]'s right edge into peak[0]'s
        # left edge. Skip smoothing for multi-cycle plots.
        if (
            do_smooth and phase_sigma > 0
            and not is_multi_cycle
        ):
            m = _circular_gaussian_smooth(m, phase_sigma)
            s = _circular_gaussian_smooth(s, phase_sigma)
        lick_count = _selected_phase_peak_count(
            df_bouts, phase_mode, side=side, df_phase_subset=df_phase,
        )
        c = side_colors.get(side, "k")
        if is_multi_cycle:
            # Phase 7a.4-cross-session-angle Addendum #16
            # (2026-05-04): under Mode 3 (synthetic_only), each
            # cycle's width is the per-animal pre-stroke median ILI
            # — NOT the real per-trial peak-to-peak interval. At
            # cycle boundaries (x = 1, 2, ..., N-1), the same x
            # position represents different physical times in the
            # trial (gap = real_ILI[i] - synthetic_ILI). A
            # connected line at the boundary draws between two
            # physically distinct time-points → misleading "jump"
            # artifact. Render each cycle as an independent line
            # segment + fill_between so the discontinuity is
            # explicit. Bin centers fall strictly inside cycle
            # intervals (never at the integer boundaries) so
            # ``int(x)`` cleanly identifies each bin's owning
            # cycle.
            label_drawn = False
            cycle_idx_per_bin = np.floor(x).astype(int)
            cycle_idx_per_bin = np.clip(
                cycle_idx_per_bin, 0, n_peaks_val - 1,
            )
            for cycle_i in range(n_peaks_val):
                in_cycle = cycle_idx_per_bin == cycle_i
                if not np.any(in_cycle):
                    continue
                x_seg = x[in_cycle]
                m_seg = m[in_cycle]
                s_seg = s[in_cycle]
                seg_label = (
                    f"{side} (licks: {lick_count})"
                    if not label_drawn else None
                )
                ax.plot(x_seg, m_seg, color=c, lw=2.0, label=seg_label)
                ax.fill_between(
                    x_seg, m_seg - s_seg, m_seg + s_seg,
                    color=c, alpha=0.18, lw=0,
                )
                label_drawn = True
        else:
            ax.plot(
                x, m, color=c, lw=2.0,
                label=f"{side} (licks: {lick_count})",
            )
            ax.fill_between(x, m - s, m + s, color=c, alpha=0.18, lw=0)

    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)

    if is_multi_cycle:
        # Mark each peak's center (x = i + 0.5 for i in [0, n_peaks - 1])
        # and each cycle boundary (x = 1, 2, ..., n_peaks - 1). The
        # cycle-boundary axvlines are rendered faint (Addendum #16
        # alpha=0.2) since the per-cycle line-segment break already
        # makes the boundary visually obvious; the axvline is just a
        # subtle eye-guide.
        for i in range(n_peaks_val):
            ax.axvline(i + 0.5, color="0.7", lw=1.0, ls="--")
        for i in range(1, n_peaks_val):
            ax.axvline(
                float(i), color="0.5", lw=1.0, ls=":", alpha=0.2,
            )
        ax.set_xlim(0, x_max)
        ax.set_xticks(np.arange(0.0, x_max + 0.5, 0.5))
    else:
        ax.axvline(0.0, color="0.7", lw=1.0, ls="--")
        ax.axvline(0.5, color="0.7", lw=1.0, ls="--")
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])

    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    # Phase 7a.4-cross-session-angle Addendum #15 (2026-05-04):
    # title convention reflects the centered-on-peak phase
    # construction. User-facing tokens (1st lick / all licks /
    # first {N} licks) match the PNG filename suffixes.
    if is_multi_cycle:
        title_suffix = f"first {n_peaks_val} licks; centered on peak"
    elif phase_mode == "first_lick":
        title_suffix = "1st lick; centered on peak"
    elif phase_mode == "all_multi":
        title_suffix = "all licks; centered on peak"
    else:
        title_suffix = f"mode={phase_mode}"
    if is_multi_cycle:
        xlabel = (
            "Centered lick phase (peak[i] at x=i+0.5; "
            "cycle width = pre-stroke median ILI)"
        )
    else:
        xlabel = (
            "Normalized lick phase (0.5 = peak protrusion; "
            "cycle width = pre-stroke median ILI)"
        )
    ax.set_title(
        f"{animal} {date_str} | phase-aligned tongue angle ({title_suffix})"
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()
    return fig


def _plot_first_vs_second_peak_scatter(
    bundle: TongueVisualBundle,
    *,
    params: dict[str, Any],
) -> Figure:
    """Phase 7a.4-cross-session-angle Addendum #11 Part B (2026-05-04):
    per-trial scatter of (peak[0]_angle, peak[1]_angle), one point per
    trial, per side. Direct trial-level visualization of the warming-up
    first-lick vs settled second-lick angle phenotype.

    Layout: 1×2 subplots, cam-view L/R per the project convention
    (axes[0] = R-trials on figure-LEFT, axes[1] = L-trials on figure-
    RIGHT — established by 7a.4-orientation-fix PR #93 + 7a.6 C7.2).

    Each subplot:
      - Scatter where x = peak[0] angle (deg), y = peak[1] angle (deg).
      - Diagonal y=x reference line (dashed grey) marks "no first-vs-
        second angle difference".
      - Symmetric square axes: ``x_lim == y_lim ==
        (-max_abs * 1.05, +max_abs * 1.05)`` where ``max_abs`` is the
        max absolute finite angle across both axes (both subplots
        united so L vs R compare directly off the figure).
      - Equal aspect so the diagonal is at 45°.

    Reads peak data via :func:`extract_first_vs_second_peak_pairs`,
    which uses the post-#15 chronological-first-two-peaks semantic
    (any-bout-structure; matches the centered-phase plot family
    convention).
    """
    visual = params["dlc_kinematics"]["tongue_visual"]
    side_colors = visual["side_colors"]
    df_bouts = bundle.df_bouts
    pairs = extract_first_vs_second_peak_pairs(df_bouts)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.2), sharex=True, sharey=True)
    # Cam-view convention: R on figure left, L on figure right.
    side_to_ax = {"R": axes[0], "L": axes[1]}

    if pairs.empty:
        for ax in axes:
            ax.text(0.5, 0.5, "No peak pairs available", ha="center",
                    va="center", transform=ax.transAxes)
            ax.set_axis_off()
        animal = bundle.metadata.get("animal", "?")
        date_str = bundle.metadata.get("date", "?")
        fig.suptitle(
            f"{animal} {date_str} | first vs second peak angle",
            y=0.98,
        )
        plt.tight_layout()
        return fig

    # Symmetric square limits across BOTH subplots (united max abs).
    angle_vals = np.concatenate([
        pairs["peak0_angle_deg"].to_numpy(float),
        pairs["peak1_angle_deg"].to_numpy(float),
    ])
    finite = angle_vals[np.isfinite(angle_vals)]
    max_abs = (
        float(np.nanmax(np.abs(finite))) * 1.05
        if finite.size else 50.0
    )
    max_abs = max(1.0, max_abs)

    for side in ("R", "L"):
        ax = side_to_ax[side]
        side_pairs = pairs[pairs["side"] == side]
        c = side_colors.get(side, "k")
        # y = x reference line first so the scatter renders on top.
        ax.plot(
            [-max_abs, max_abs], [-max_abs, max_abs],
            color="0.5", ls="--", lw=1.0, alpha=0.7, zorder=1,
        )
        # Axis cross at zero for visual reference.
        ax.axhline(0, color="0.7", lw=0.8, alpha=0.6, zorder=0)
        ax.axvline(0, color="0.7", lw=0.8, alpha=0.6, zorder=0)
        if not side_pairs.empty:
            ax.scatter(
                side_pairs["peak0_angle_deg"],
                side_pairs["peak1_angle_deg"],
                color=c, s=20, alpha=0.6, edgecolors="none", zorder=2,
            )
        n_trials = int(len(side_pairs))
        ax.set_title(f"{side} trials  (n={n_trials})")
        ax.set_xlim(-max_abs, +max_abs)
        ax.set_ylim(-max_abs, +max_abs)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Peak[0] angle (deg)")
        ax.grid(True, alpha=0.2)
    axes[0].set_ylabel("Peak[1] angle (deg)")

    animal = bundle.metadata.get("animal", "?")
    date_str = bundle.metadata.get("date", "?")
    fig.suptitle(
        f"{animal} {date_str} | first vs second peak angle "
        f"(per-trial scatter; diagonal = no first-vs-second difference)",
        y=0.98,
    )
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
    "first_peak_aligned":           _plot_first_peak_aligned,
    "tone_aligned":               _plot_tone_aligned,
    "phase_aligned_angle":          _plot_phase_aligned_angle,
    "first_vs_second_peak_scatter": _plot_first_vs_second_peak_scatter,
    "xy_by_phase":                  _plot_xy_by_phase,
}


# ============================================================================
# Helpers (private)
# ============================================================================


def _resolve_consolidated_paths(
    out_dir: Path,
    families: Sequence[str],
    *,
    sides: Sequence[str] = ("L", "R"),
    params: dict[str, Any] | None = None,
) -> dict[str, list[Path]]:
    """Compute the expected output PNG paths for each requested family.

    ``params`` (Phase 7a.4-cross-session-angle Addendum #11 Part A,
    2026-05-04) is consulted to resolve the
    :func:`_phase_aligned_angle_variants` config-aware suffix list
    (specifically the ``first_{N}_licks`` variant pulls ``N`` from
    config). Defaults to :func:`load_defaults` when ``None``.
    """
    if params is None:
        params = load_defaults()
    out: dict[str, list[Path]] = {}
    for family in families:
        if family in _PER_SIDE_FAMILIES:
            out[family] = [
                out_dir / f"{family}_side_{side}.png" for side in sides
            ]
        elif family in _MULTI_VARIANT_FAMILIES:
            out[family] = [
                out_dir / f"{family}_{suffix}.png"
                for suffix, _mode, _kwargs
                in _phase_aligned_angle_variants(params)
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
    *,
    n_peaks: int = 2,
    synthetic_ili_ms: float | None = None,
    ili_source: Literal["real_only", "hybrid", "synthetic_only"] = "hybrid",
) -> pd.DataFrame:
    """Phase 7a.4-cross-session-angle dispatcher to centered-phase
    builders for ``mode``. Forwards ``synthetic_ili_ms`` and
    ``ili_source`` (Addendum #14) to the helper.

    Routes:
      - ``"first_lick"`` → :func:`build_first_lick_centered_phase_rows`.
      - ``"all_multi"`` → :func:`build_all_licks_centered_phase_rows`.
      - ``"first_n_licks"`` →
        :func:`build_first_n_licks_centered_phase_rows`.
      - ``"first_multi"`` → falls back to the legacy peak-to-peak
        ``_select_phase_rows`` filter on ``bundle.df_phase``. Kept
        for external/back-compat callers; not wired into any
        production phase-aligned-angle PNG filename.
    """
    if mode == "first_lick":
        return build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=synthetic_ili_ms,
            ili_source=ili_source,
        )
    if mode == "all_multi":
        return build_all_licks_centered_phase_rows(
            bundle, synthetic_ili_ms=synthetic_ili_ms,
            ili_source=ili_source,
        )
    if mode == "first_n_licks":
        return build_first_n_licks_centered_phase_rows(
            bundle, n_peaks=n_peaks,
            synthetic_ili_ms=synthetic_ili_ms,
            ili_source=ili_source,
        )
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
    if mode in ("first_lick", "all_multi", "first_n_licks"):
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
            f"phase mode must be 'all_multi', 'first_multi', "
            f"'first_lick', or 'first_n_licks'; got {mode!r}"
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
