"""Phase 7c.2 Task 5 — Compute-on-demand DLC heatmap renderers (Addendum #3 Q4.B).

Replaces the cached `spatial_tone_aligned/` NPZ tree (eliminated per
Addendum #3 Interpretation 1) with thin wrappers that compute
tone-aligned + whole-session heatmaps on-demand from Phase 4 centered
parquets + tone events + alignment templates. The same primitive
handles both alignments via the ``window_ms`` parameter:

  - ``window_ms = (pre_ms, post_ms)`` → tone-aligned heatmap.
  - ``window_ms = None``              → whole-session heatmap (no
                                          alignment; full-session
                                          bodypart spatial distribution).

Two granularities:

  1. Per-session: :func:`render_tone_aligned_heatmap_session` and
     :func:`render_whole_session_heatmap` produce one ``matplotlib.figure.Figure``
     for a single (animal, date) cell.

  2. Per-animal aggregated: :func:`render_animal_aggregated_heatmap`
     concatenates frames (or, more precisely, sums per-session
     histograms) across all in-YAML-range dates for one animal, then
     renders a single aggregated heatmap. Memory-efficient via
     :func:`build_histogram` per-session + array sum at the
     ``H_counts`` level.

Phase 7a.7's visual gate output and Phase 7c.3's whole-session
heatmap output both reduce to these primitives — Phase 7c.3 retired
into Phase 7c.2 Task 5 per Addendum #3.

Allowlist enforcement: the 5-family / 10-bodypart allowlist
(Q10.A) is honored at the driver layer (scripts/phase_7c2/
render_visual_gate.py + render_whole_session.py). This module accepts
any (bodypart, center_mode) pair the caller supplies and validates
only via ``lookup_tone_family`` for per-family parameters.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults, lookup_tone_family
from stroke_orofacial.dlc_spatial.pixel_bins import (
    _get_per_center_mode_params,
    build_histogram,
)
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_window,
    load_tone_events,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver


def _load_centered_df_for(
    manifest: SessionManifest,
    center_mode: str,
    resolver: PathResolver,
) -> pd.DataFrame:
    """Locate + load the Phase 4 centered parquet for this manifest +
    center_mode. Mirrors the resolver logic in
    :func:`stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_analysis`.
    """
    from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet

    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{manifest.session_id}: manifest.dlc_h5_files is empty. "
            "Phase 4 centered parquet cannot be located without a DLC H5 "
            "filename anchor."
        )
    lik_thr_centering = 0.7  # Phase 4 centering threshold
    sig = _param_sig(center_mode, lik_thr_centering)
    parquet_dir = (
        resolver.pipeline_outputs("dlc_analysis")
        / f"centered_{center_mode}"
        / manifest.animal
    )
    parquet_path = parquet_dir / (
        f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
    )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}/{center_mode}: Phase 4 centered parquet "
            f"missing at {parquet_path}."
        )
    return read_centered_parquet(parquet_path)


def _build_tone_window(
    manifest: SessionManifest,
    trial_group: str,
    window_ms: tuple[float, float],
    n_frames: int,
    resolver: PathResolver,
    tone_config: dict[str, Any],
    *,
    wavesurfer_sides_match_mouse_sides: bool | None = None,
) -> Any | None:
    """Build the tone-aligned WindowSelector for one (animal, date,
    trial_group, window). Returns ``None`` if the session has zero tone
    events for ``trial_group``.
    """
    date_str = manifest.date.strftime("%Y%m%d")
    spout_root = resolver.pipeline_outputs("spout_behavior")
    licks_path = spout_root / "licks_and_rewards" / manifest.animal / f"{date_str}.npz"
    if not licks_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: Phase 2 licks NPZ missing at {licks_path}."
        )

    tone_ws = load_tone_events(
        licks_path, trial_group,
        wavesurfer_sides_match_mouse_sides=wavesurfer_sides_match_mouse_sides,
    )
    if len(tone_ws) == 0:
        return None

    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_legacy_read(
            manifest.animal, manifest.date, cam="cam2",
        )
    if not align_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: cam2 alignment template missing at "
            f"{align_path}."
        )
    aln = np.load(str(align_path), allow_pickle=True)
    sig_camIdx = aln["sig_camIdx__idx_ws"]

    fps = float(tone_config.get("fps", 250.0))
    return build_tone_aligned_window(tone_ws, sig_camIdx, window_ms, fps, n_frames)


def _resolve_family_params(
    tone_config: dict[str, Any],
    bodypart: str,
    center_mode: str,
) -> dict[str, Any]:
    """Read per-family tone-aligned params (likelihood_threshold,
    x_range) via the Q10.A allowlist helper, with safe defaults when no
    families block is loaded (e.g., synthetic test configs).
    """
    try:
        return lookup_tone_family(tone_config, bodypart, center_mode)
    except KeyError:
        # Not in allowlist; fall back to permissive defaults.
        return {
            "family_name": None,
            "bodyparts": (bodypart,),
            "center_mode": center_mode,
            "likelihood_thresholds": [0.8],
            "x_range": None,
        }


def _h_counts_to_figure(
    H_counts: np.ndarray,
    extent: list[float],
    bodypart: str,
    center_mode: str,
    spatial_config: dict[str, Any],
    *,
    title: str,
    figsize: tuple[float, float] = (8, 6),
) -> plt.Figure:
    """Render a precomputed ``H_counts`` array as a 2D heatmap figure.

    Used by the aggregator path so callers can sum per-session
    histograms into one cohort/animal-level array, then render once.
    Axis limits + colormap come from the Phase 5 ``dlc_spatial`` config's
    per-(bodypart, center_mode) block.
    """
    bp_cfg = spatial_config.get("bodyparts", {}).get(bodypart, {}) or {}
    cmap_name = bp_cfg.get("cmap", "viridis")
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    x_limits = per_mode["xlim"] or (extent[0], extent[1])
    y_limits = per_mode["ylim"] or (extent[2], extent[3])

    fig, ax = plt.subplots(figsize=figsize)
    total = float(H_counts.sum())
    if total > 0:
        H_prop = H_counts / total
        try:
            cmap = plt.get_cmap(cmap_name)
        except ValueError:
            cmap = plt.get_cmap("viridis")
        # imshow uses the histogram extent (matches build_histogram output).
        finite_nonzero = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_nonzero.size > 0:
            vmin = float(finite_nonzero.min())
            vmax = float(H_prop.max())
            norm = mcolors.LogNorm(vmin=max(vmin, 1e-10), vmax=vmax)
        else:
            norm = None
        ax.imshow(
            H_prop.T,
            origin="lower",
            extent=extent,
            cmap=cmap,
            aspect="auto",
            norm=norm,
        )

    ax.set_xlabel(f"{bodypart}_x (centered)")
    ax.set_ylabel(f"{bodypart}_y (centered)")
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    ax.invert_yaxis()  # camera-view convention
    ax.set_title(title)
    return fig


def render_tone_aligned_heatmap_session(
    animal: str,
    date: dt.date,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    window_ms: tuple[float, float],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure | None:
    """Render a tone-aligned heatmap for one (animal, date) cell.

    Returns ``None`` when the session has zero tone events for
    ``trial_group`` (e.g., a post-stroke session with no L-only trials).
    Caller may show an empty-tile placeholder in that case.
    """
    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    if animal_info is None:
        animal_info = get_animal(animal)

    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.spatial",
    )
    df = _load_centered_df_for(manifest, center_mode, resolver)
    n_frames = len(df)
    window = _build_tone_window(
        manifest, trial_group, window_ms, n_frames, resolver, tone_config,
        wavesurfer_sides_match_mouse_sides=animal_info.wavesurfer_sides_match_mouse_sides,
    )
    if window is None:
        return None

    family = _resolve_family_params(tone_config, bodypart, center_mode)
    bp_x_range = (
        tuple(family["x_range"]) if family.get("x_range") is not None else None
    )
    lik_thresholds = family.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8
    nbins_cfg = tone_config.get("default_nbins", [80, 80])
    nbins = int(nbins_cfg[0]) if isinstance(nbins_cfg, list) else int(nbins_cfg)

    # Build the (single-session) histogram using the same plumbing as
    # build_tone_aligned_analysis, then render. We override the per-family
    # likelihood_threshold into a per-bodypart spatial_config copy so
    # build_histogram's lookup picks up the tone-aligned threshold.
    config_for_hist = dict(spatial_config)
    config_for_hist["bodyparts"] = dict(config_for_hist.get("bodyparts", {}))
    bp_existing = dict(config_for_hist["bodyparts"].get(bodypart, {}))
    bp_existing["likelihood_threshold"] = lik_thr
    config_for_hist["bodyparts"][bodypart] = bp_existing

    hist = build_histogram(
        df, bodypart, config_for_hist,
        center_mode=center_mode,
        x_range=bp_x_range,
        nbins=nbins,
        window=window,
    )

    win_label = f"[{int(window_ms[0])}, {int(window_ms[1])}] ms"
    title = (
        f"{animal}/{date.isoformat()}  {bodypart}/{center_mode}  "
        f"tg={trial_group}  win={win_label}  n_tones={window.n_events}"
    )
    return _h_counts_to_figure(
        hist["H_counts"], hist["extent"], bodypart, center_mode,
        spatial_config, title=title,
    )


def render_whole_session_heatmap(
    animal: str,
    date: dt.date,
    bodypart: str,
    center_mode: str,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure:
    """Render a whole-session heatmap (no tone alignment) for one
    (animal, date) cell. Frames are all session frames passing the
    bodypart's likelihood threshold + optional x_range filter.
    """
    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    if animal_info is None:
        animal_info = get_animal(animal)

    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.spatial",
    )
    df = _load_centered_df_for(manifest, center_mode, resolver)

    family = _resolve_family_params(tone_config, bodypart, center_mode)
    bp_x_range = (
        tuple(family["x_range"]) if family.get("x_range") is not None else None
    )
    lik_thresholds = family.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8
    nbins_cfg = tone_config.get("default_nbins", [80, 80])
    nbins = int(nbins_cfg[0]) if isinstance(nbins_cfg, list) else int(nbins_cfg)

    config_for_hist = dict(spatial_config)
    config_for_hist["bodyparts"] = dict(config_for_hist.get("bodyparts", {}))
    bp_existing = dict(config_for_hist["bodyparts"].get(bodypart, {}))
    bp_existing["likelihood_threshold"] = lik_thr
    config_for_hist["bodyparts"][bodypart] = bp_existing

    hist = build_histogram(
        df, bodypart, config_for_hist,
        center_mode=center_mode,
        x_range=bp_x_range,
        nbins=nbins,
        window=None,  # whole-session = no frame mask
    )

    title = (
        f"{animal}/{date.isoformat()}  {bodypart}/{center_mode}  "
        f"WHOLE SESSION  n_frames={len(df):,}"
    )
    return _h_counts_to_figure(
        hist["H_counts"], hist["extent"], bodypart, center_mode,
        spatial_config, title=title,
    )


def compute_animal_aggregated_histogram(
    animal: str,
    dates: list[dt.date],
    bodypart: str,
    center_mode: str,
    resolver: PathResolver,
    *,
    trial_group: str | None,
    window_ms: tuple[float, float] | None,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    nbins_override: int | None = None,
) -> tuple[np.ndarray | None, list[float] | None, int, int, int]:
    """Compute-only variant of :func:`render_animal_aggregated_heatmap`.

    Returns ``(H_total, extent, n_sessions_contributing, n_total_tones,
    n_total_frames_aggregated)`` so a caller can cache the histogram +
    render multiple SVG layouts (per-animal panel + cohort tile-grid
    subplot) from one compute pass, AND compute the Q17 H_proportion
    via ``H_total / n_total_frames_aggregated``.

    Returns ``(None, None, 0, 0, 0)`` when no session contributes data
    (no parquets, no tone events for the trial_group, etc.).

    ``nbins_override`` (Phase 7c.2 Addendum #15 Q15) lets the UOT
    renderer request a coarser histogram resolution than the
    config-level default (legacy NBINS=50 vs default_nbins=80×80).

    ``n_total_frames_aggregated`` (Phase 7c.2 Addendum #16 Q17/Q19):
    sum across contributing sessions of the per-session denominator.
    Per-session denominator = ``window.n_selected`` for tone_aligned
    scope (frames within the (pre, post)ms window after dedup) or
    ``len(df)`` for whole_session (all frames in the centered parquet).
    Used as the universal proportion denominator: ``H_total /
    n_total_frames_aggregated`` instead of legacy ``H_total /
    H_total.sum()``.
    """
    if (trial_group is None) != (window_ms is None):
        raise ValueError(
            "compute_animal_aggregated_histogram: trial_group and window_ms "
            "must both be set (tone-aligned) or both None (whole-session); "
            f"got trial_group={trial_group!r}, window_ms={window_ms!r}."
        )

    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    if animal_info is None:
        animal_info = get_animal(animal)

    family = _resolve_family_params(tone_config, bodypart, center_mode)
    bp_x_range = (
        tuple(family["x_range"]) if family.get("x_range") is not None else None
    )
    lik_thresholds = family.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8
    if nbins_override is not None:
        nbins = int(nbins_override)
    else:
        nbins_cfg = tone_config.get("default_nbins", [80, 80])
        nbins = int(nbins_cfg[0]) if isinstance(nbins_cfg, list) else int(nbins_cfg)

    config_for_hist = dict(spatial_config)
    config_for_hist["bodyparts"] = dict(config_for_hist.get("bodyparts", {}))
    bp_existing = dict(config_for_hist["bodyparts"].get(bodypart, {}))
    bp_existing["likelihood_threshold"] = lik_thr
    config_for_hist["bodyparts"][bodypart] = bp_existing

    H_total: np.ndarray | None = None
    extent: list[float] | None = None
    n_sessions_contributing = 0
    n_total_tones = 0
    n_total_frames_aggregated = 0  # Q17 denominator (sum over sessions)
    for date in dates:
        try:
            manifest = build_manifest(
                animal, date, resolver, animal_info,
                analysis_context="dlc.spatial",
            )
            df = _load_centered_df_for(manifest, center_mode, resolver)
        except FileNotFoundError:
            continue

        if window_ms is not None and trial_group is not None:
            try:
                window = _build_tone_window(
                    manifest, trial_group, window_ms, len(df),
                    resolver, tone_config,
                    wavesurfer_sides_match_mouse_sides=animal_info.wavesurfer_sides_match_mouse_sides,
                )
            except FileNotFoundError:
                continue
            if window is None:
                continue
            n_total_tones += window.n_events
            # Q17/Q19: tone-aligned denominator = frames within window
            # (after dedup of overlapping windows).
            session_n_total = int(window.n_selected)
        else:
            window = None
            # Q17/Q19: whole_session denominator = ALL frames in the
            # centered parquet (the WS-bounded session length).
            session_n_total = int(len(df))

        hist = build_histogram(
            df, bodypart, config_for_hist,
            center_mode=center_mode,
            x_range=bp_x_range,
            nbins=nbins,
            window=window,
            n_total_frames=session_n_total,
        )
        n_sessions_contributing += 1
        n_total_frames_aggregated += session_n_total
        if H_total is None:
            H_total = hist["H_counts"].copy()
            extent = list(hist["extent"])
        else:
            H_total += hist["H_counts"]

    return (
        H_total, extent, n_sessions_contributing, n_total_tones,
        n_total_frames_aggregated,
    )


def render_h_counts_panel(
    H_counts: np.ndarray | None,
    extent: list[float] | None,
    bodypart: str,
    center_mode: str,
    *,
    title: str,
    defaults: dict[str, Any] | None = None,
    figsize: tuple[float, float] = (8, 6),
    ax: plt.Axes | None = None,
    n_total_frames: int | None = None,
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure | plt.Axes:
    """Public render-only variant.

    When ``ax`` is None, returns a new Figure (single-panel layout). When
    ``ax`` is provided, renders into the existing Axes (subplot layout)
    and returns the Axes. Empty-data path (``H_counts is None``) renders
    a "no data" placeholder.

    ``n_total_frames`` (Q17 Addendum #16): when given, use total-frame
    normalization (H_proportion = H_counts / n_total_frames). When None,
    fall back to legacy passed-count normalization (H_proportion =
    H_counts / H_counts.sum()).

    ``shared_vmin`` / ``shared_vmax`` (Q18 Addendum #17): when both given,
    use these as LogNorm bounds (per-bucket shared scale). When None,
    fall back to per-panel data-derived range (legacy Q14 per-SVG scope,
    preserved for unit-test + standalone callers).
    """
    if defaults is None:
        defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    if H_counts is None or extent is None or float(H_counts.sum()) == 0.0:
        ax.text(
            0.5, 0.5, "no data",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        if not standalone:
            ax.set_title(title, fontsize=8)
        return fig if standalone else ax

    bp_cfg = spatial_config.get("bodyparts", {}).get(bodypart, {}) or {}
    cmap_name = bp_cfg.get("cmap", "viridis")
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    x_limits = per_mode["xlim"] or (extent[0], extent[1])
    y_limits = per_mode["ylim"] or (extent[2], extent[3])

    # Q17 Addendum #16: total-frame denominator when provided; legacy
    # H_counts.sum() fallback otherwise.
    if n_total_frames is not None and n_total_frames > 0:
        total = float(n_total_frames)
    else:
        total = float(H_counts.sum())
    H_prop = H_counts / total
    try:
        cmap = plt.get_cmap(cmap_name)
    except ValueError:
        cmap = plt.get_cmap("viridis")
    # Q18 Addendum #17: bucket-shared (vmin, vmax) when both given;
    # otherwise per-panel data-derived range (legacy Q14 per-SVG scope).
    if shared_vmin is not None and shared_vmax is not None and shared_vmax > 0:
        norm = mcolors.LogNorm(
            vmin=max(float(shared_vmin), 1e-10),
            vmax=float(shared_vmax),
        )
    else:
        finite_nonzero = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_nonzero.size > 0:
            vmin = float(finite_nonzero.min())
            vmax = float(H_prop.max())
            norm = mcolors.LogNorm(vmin=max(vmin, 1e-10), vmax=vmax)
        else:
            norm = None
    im = ax.imshow(
        H_prop.T,
        origin="lower",
        extent=extent,
        cmap=cmap,
        aspect="auto",
        norm=norm,
    )
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    ax.invert_yaxis()
    # Q22 Addendum #21: uniform tick + axis-label polish across all
    # plot types. Per-panel title sized for subplot context;
    # standalone-figure mode gets a larger title (Q22 suptitle-fontsize).
    _apply_q22_panel_polish(ax)
    if standalone:
        ax.set_title(title, fontsize=_Q22_SUPTITLE_FONTSIZE)
    else:
        ax.set_title(title, fontsize=_Q22_PANEL_TITLE_FONTSIZE)

    # Q24 Addendum #24: per-panel colorbar for IS + BS single-bp heatmaps
    # (LogNorm scale). Label "frame proportion" matches the Q17
    # total-frame-denominator H_proportion semantics.
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("frame proportion", fontsize=_Q22_AXIS_LABELSIZE)
    _apply_q22_colorbar_polish(cbar)

    return fig if standalone else ax


def render_animal_aggregated_heatmap(
    animal: str,
    dates: list[dt.date],
    bodypart: str,
    center_mode: str,
    resolver: PathResolver,
    *,
    trial_group: str | None,
    window_ms: tuple[float, float] | None,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure:
    """Render a per-animal heatmap aggregating frames across all in-scope
    sessions for one (bodypart, center_mode) cell.

    Aggregation works at the ``H_counts`` array level (memory-efficient):
    per-session histograms are computed with build_histogram + summed.
    The resulting summed histogram is normalized + rendered once.

    Tone-aligned mode (``trial_group`` + ``window_ms`` both non-None):
    each session's histogram is windowed to the tone-aligned frames for
    the given trial_group. Sessions with zero tone events for that group
    contribute zero counts (no exception; the session is just absent).

    Whole-session mode (``trial_group is None`` and ``window_ms is None``):
    each session contributes all frames passing the likelihood / x_range
    filter.

    Parameters
    ----------
    animal : str
    dates : list[datetime.date]
        Sessions to aggregate. Typically the YAML-filtered cohort list
        from :func:`stroke_orofacial.animals.AnimalInfo.session_start/end`.
    bodypart : str
    center_mode : str
    resolver : PathResolver
    trial_group : "all" | "L" | "R" | None
    window_ms : tuple[float, float] | None
        Pair → tone-aligned window. ``None`` + ``trial_group=None`` →
        whole-session aggregation.
    defaults : dict, optional
    animal_info : AnimalInfo, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    if defaults is None:
        defaults = load_defaults()
    H_total, extent, n_sessions, n_tones, n_total_frames = (
        compute_animal_aggregated_histogram(
            animal, dates, bodypart, center_mode, resolver,
            trial_group=trial_group, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
    )
    if window_ms is not None:
        win_label = f"[{int(window_ms[0])}, {int(window_ms[1])}] ms"
        title = (
            f"{animal}  {bodypart}/{center_mode}  tg={trial_group}  "
            f"win={win_label}  n_sessions={n_sessions}  "
            f"n_tones={n_tones}  n_total_frames={n_total_frames}"
        )
    else:
        title = (
            f"{animal}  {bodypart}/{center_mode}  WHOLE SESSION pooled  "
            f"n_sessions={n_sessions}  n_total_frames={n_total_frames}"
        )
    return render_h_counts_panel(
        H_total, extent, bodypart, center_mode,
        title=title, defaults=defaults,
    )


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #9 — Task 5 plot types (individual_session,
# binned_sessions). Trial-group panel layout: 3-panel (all, L, R) for
# tone-aligned plot types; 1-panel (all only) for whole-session.
# Single tone-aligned window = (0, 8000) ms per Q12.B.
# ---------------------------------------------------------------------------

# Tone-aligned single window per Addendum #9 Issue 4.
TASK5_TONE_WINDOW_MS: tuple[float, float] = (0.0, 8000.0)
TASK5_TRIAL_GROUPS_TONE_ALIGNED: tuple[str, str, str] = ("all", "L", "R")
TASK5_TRIAL_GROUPS_WHOLE_SESSION: tuple[str, ...] = ("all",)

# Q22 Addendum #21 — plot polish constants applied uniformly across all
# 4 plot types × 2 scopes × 7 families. Promote to config if tunability
# is needed; pure constants for now.
_Q22_TICK_LABELSIZE: int = 12       # axes + colorbar tick labels
_Q22_AXIS_LABELSIZE: int = 12       # X/Y axis labels
_Q22_PANEL_TITLE_FONTSIZE: int = 11  # per-panel titles (composite, UOT subplots, PD bin panels)
_Q22_SUPTITLE_FONTSIZE: int = 14     # figure-level suptitle
# Centered-parquet coordinates are pure pixel offsets (raw_pixel −
# center_pixel from the per-frame centering transform). No mm conversion;
# axis labels stay in pixel units.
_Q22_X_AXIS_LABEL: str = "X (px, centered)"
_Q22_Y_AXIS_LABEL: str = "Y (px, centered)"


def _apply_q22_panel_polish(
    ax: plt.Axes, *, set_labels: bool = True, label_fontsize: int | None = None,
) -> None:
    """Q22 Addendum #21: tick labelsize 12 + ``X (px, centered)`` /
    ``Y (px, centered)`` axis labels. Only sets labels when
    ``set_labels=True``; whole-session-scope single-panel callers may
    skip via False if they have a custom label.
    """
    ax.tick_params(axis="both", labelsize=_Q22_TICK_LABELSIZE)
    if set_labels:
        size = label_fontsize if label_fontsize is not None else _Q22_AXIS_LABELSIZE
        ax.set_xlabel(_Q22_X_AXIS_LABEL, fontsize=size)
        ax.set_ylabel(_Q22_Y_AXIS_LABEL, fontsize=size)


def _apply_q22_colorbar_polish(cbar: Any) -> None:
    """Q22: colorbar tick labelsize 12."""
    cbar.ax.tick_params(labelsize=_Q22_TICK_LABELSIZE)


Scope = str  # Literal["tone_aligned", "whole_session"]; relaxed for older type-checkers.


def _resolve_family_entry(
    family_entry: str,
    defaults: dict[str, Any],
) -> tuple[list[str], str]:
    """Look up (bodyparts, center_mode) for a family entry from defaults.yaml.

    Reads ``dlc_spatial_tone_aligned.families.<family_entry>``. Returns
    a list of bodyparts (single-element for non-whisker families; 6
    individual whisker bodyparts for ``whiskers_eye_midpoint``).
    """
    tone_config = defaults["dlc_spatial_tone_aligned"]
    families = tone_config.get("families") or {}
    if family_entry not in families:
        raise KeyError(
            f"family_entry {family_entry!r} not in "
            f"dlc_spatial_tone_aligned.families allowlist: "
            f"{sorted(families.keys())}"
        )
    fam = families[family_entry]
    return list(fam["bodyparts"]), str(fam["center_mode"])


def _compute_panels_for_session(
    animal: str,
    date: dt.date,
    bodypart: str,
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> dict[str, tuple[np.ndarray | None, list[float] | None, int, int]]:
    """Compute per-trial-group histograms for a single (animal, date) cell.

    Returns ``{tg: (H_counts, extent, n_tones, n_total_frames)}`` for every
    trial group in the scope-specific panel set. Missing-data panels (no
    tone events for a trial_group) map to ``(None, None, 0, 0)``.

    ``n_total_frames`` (Q17 Addendum #16) is the per-tg denominator for
    proportion normalization (sum of per-session window.n_selected or
    len(df) across the date set — always 1 session here).
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    panels: dict[str, tuple[np.ndarray | None, list[float] | None, int, int]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        H, ext, _n_sess, n_tones, n_total = compute_animal_aggregated_histogram(
            animal, [date], bodypart, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
        panels[tg] = (
            H, ext,
            int(n_tones) if window_ms is not None else 0,
            int(n_total),
        )
    return panels


def _compute_panels_for_dates(
    animal: str,
    dates: list[dt.date],
    bodypart: str,
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> dict[str, tuple[np.ndarray | None, list[float] | None, int, int, int]]:
    """Compute per-trial-group aggregated histograms for a date set
    (e.g., one rel_day_bin's sessions). Returns
    ``{tg: (H_counts, extent, n_sessions, n_tones, n_total_frames)}``.

    ``n_total_frames`` (Q17 Addendum #16) is the per-tg denominator for
    proportion normalization (sum of per-session window.n_selected or
    len(df) across all sessions in the bin).
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    panels: dict[str, tuple[np.ndarray | None, list[float] | None, int, int, int]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        H, ext, n_sess, n_tones, n_total = compute_animal_aggregated_histogram(
            animal, dates, bodypart, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
        panels[tg] = (
            H, ext, int(n_sess),
            int(n_tones) if window_ms is not None else 0,
            int(n_total),
        )
    return panels


def _assemble_panel_figure(
    panels: dict[str, tuple],
    bodypart: str,
    center_mode: str,
    scope: Scope,
    suptitle: str,
    *,
    defaults: dict[str, Any],
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Render the per-trial-group panels as one Figure.

    Tone-aligned scope: 1×3 grid (all, L, R). Whole-session scope: 1×1.
    Each panel's title carries n_sessions / n_tones depending on the
    panel payload shape (4-tuple for single-session, 5-tuple for
    bin-aggregated).

    Q18 Addendum #17: ``shared_vmin`` / ``shared_vmax`` (when both given)
    enforce a bucket-shared LogNorm range across all panels in the
    figure (and across other figures in the same bucket if the driver
    re-uses the values).
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        figsize = (18.0, 5.0)
    else:
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        figsize = (8.0, 6.0)

    fig, axes_obj = plt.subplots(
        nrows=1, ncols=len(trial_groups),
        figsize=figsize, constrained_layout=True,
    )
    axes = list(axes_obj.flat) if hasattr(axes_obj, "flat") else [axes_obj]
    for tg, ax in zip(trial_groups, axes, strict=False):
        payload = panels.get(tg)
        if payload is None:
            ax.text(0.5, 0.5, f"tg={tg}\n(no data)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        # Q22 Addendum #21: per-panel title carries the trial-group +
        # count qualifier; figure suptitle has the (animal, family, scope,
        # plot-type, date/bin) prefix.
        if len(payload) == 4:
            # individual_session: (H, ext, n_tones, n_total_frames)
            H, ext, n_tones, n_total = payload
            panel_title = (
                f"trial_group={tg} | n_tones={n_tones}"
                if scope == "tone_aligned"
                else "whole session"
            )
        elif len(payload) == 5:
            # binned_sessions: (H, ext, n_sess, n_tones, n_total_frames)
            H, ext, n_sess, n_tones, n_total = payload
            if scope == "tone_aligned":
                panel_title = (
                    f"trial_group={tg} | n_sess={n_sess} | n_tones={n_tones}"
                )
            else:
                panel_title = f"whole session | n_sess={n_sess}"
        else:
            raise ValueError(
                f"_assemble_panel_figure: unexpected payload length "
                f"{len(payload)} for tg={tg} (expected 4 or 5)"
            )
        render_h_counts_panel(
            H, ext, bodypart, center_mode,
            title=panel_title, defaults=defaults, ax=ax,
            n_total_frames=n_total,
            shared_vmin=shared_vmin, shared_vmax=shared_vmax,
        )
    fig.suptitle(suptitle, fontsize=_Q22_SUPTITLE_FONTSIZE)
    return fig


# ---------------------------------------------------------------------------
# Multi-bp composite renderer — Pattern B layered overlay.
#
# Originally written for the whiskers composite (Addendum #10 Q1) which
# ports legacy lines 676-738 of 20251202_DLC_analysis_all_bodyparts_stats_
# pixelbin.ipynb: sequential ``ax.hist2d`` over PART_DRAW_ORDER with cmap +
# alpha=0.8 + LogNorm + density=True, then per-part colorbars stacked
# vertically on the right. Our port works at the imshow level (since we
# already have H_counts arrays from compute_animal_aggregated_histogram)
# and renders the colormap key as a compact figure-right legend instead
# of N colorbars per panel.
#
# Generalized in Phase 7c.2 Addendum #13 to also serve the two fiducial
# bilateral-pair composite families (``spout_spout_midpoint`` and
# ``eye_eye_midpoint``). Dispatch from per-family entry: any family with
# > 1 bodypart routes here, regardless of which bodyparts. cmap lookup
# is config-driven via ``_get_bodypart_cmap``; composite axis range uses
# the first bp's per_center_mode block (per legacy whiskers convention).
# ---------------------------------------------------------------------------

# Per-bodypart cmap is loaded from ``dlc_spatial.bodyparts.{bp}.cmap``
# (defaults.yaml). Whiskers cmaps echo legacy lines 582-587 / 830-835 /
# 1394-1399 of 20251202_..._pixelbin.ipynb (L/R whiskers share cmap per
# index). Fiducial bilateral-pair cmaps were added Phase 7c.2 Addendum #13
# (L=Reds, R=Blues; clear visual L/R contrast).
_COMPOSITE_FALLBACK_CMAP: str = "viridis"
_COMPOSITE_ALPHA: float = 0.5  # Slight softening vs legacy 0.8 for multi-bp overlay readability.


def _get_bodypart_cmap(spatial_config: dict[str, Any], bp: str) -> str:
    """Look up the per-bp cmap from ``dlc_spatial.bodyparts.{bp}.cmap``.
    Returns a fallback when missing (so callers stay robust against
    incomplete configs)."""
    cmap = (spatial_config.get("bodyparts", {}).get(bp, {}) or {}).get("cmap")
    return str(cmap) if cmap else _COMPOSITE_FALLBACK_CMAP


def _compute_composite_panels(
    animal: str,
    dates: list[dt.date],
    bodyparts: list[str],
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]]]:
    """Per-trial-group + per-bodypart histogram compute for a composite family.

    Returns ``{tg: [(bp, H_counts, extent, n_sessions, n_tones,
    n_total_frames), ...]}`` — one entry per (trial_group, bp). For
    whole_session scope the only trial_group key is ``"all"`` and
    ``n_tones`` is 0. Used by all composite families (whiskers + fiducial
    bilateral pairs).

    ``n_total_frames`` (Q17 Addendum #16): per-bp denominator for the
    Q17 proportion normalization (sum of per-session window.n_selected
    or len(df) across the date set).
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        per_tg: list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]] = []
        for bp in bodyparts:
            H, ext, n_sess, n_tones, n_total = compute_animal_aggregated_histogram(
                animal, dates, bp, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
            )
            per_tg.append((
                bp, H, ext, int(n_sess),
                int(n_tones) if window_ms is not None else 0,
                int(n_total),
            ))
        panels[tg] = per_tg
    return panels


def _render_composite_panel_axis(
    ax: plt.Axes,
    composite_panels: list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]],
    spatial_config: dict[str, Any],
    *,
    family_bodyparts: list[str],
    family_center_mode: str,
    panel_title: str,
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
    layered_overlay_floor_fraction: float = 0.05,
) -> None:
    """Render N sequential layered ``imshow`` plots on one axes — one per
    bodypart in the composite family, each with its own cmap + LogNorm +
    alpha. Mirrors the legacy ``ax.hist2d`` loop at lines 676-697 of
    20251202_..._pixelbin.ipynb, adapted to consume precomputed
    ``H_counts`` arrays (vs hist2d which consumes raw xy). cmap lookup
    is config-driven via ``_get_bodypart_cmap``.

    Q17 Addendum #16: H_proportion normalization uses ``n_total_frames``
    (per-bp total in-window frames) instead of ``H.sum()`` (legacy).

    Q18 Addendum #17: ``shared_vmin`` / ``shared_vmax`` (when both given)
    override the per-bp LogNorm bounds with the bucket-shared range.

    Q32 Addendum #29:
      - Per-layer magnitude floor (``layered_overlay_floor_fraction``,
        default 0.05). Bins with H_prop < (layer_vmax × fraction) are
        NaN-masked so blank regions render invisible.
      - NaN bins set to TRANSPARENT (RGBA (1,1,1,0)) — opaque-white
        NaN caused lower layers to be washed out under alpha blending.
        Single-cmap callers keep set_bad("white") elsewhere; composite
        layering is the only place transparency is needed.
      - Axes facecolor set to white so the canvas background showing
        through transparent NaN cells is consistent.
    """
    ax.set_facecolor("white")  # Q32: showthrough color for transparent NaN.
    extent_first: list[float] | None = None
    n_layered = 0
    for bp, H, ext, _n_sess, _n_tones, n_total in composite_panels:
        if H is None or n_total == 0:
            continue
        if extent_first is None:
            extent_first = ext
        H_prop = H / float(n_total)
        finite_nonzero = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_nonzero.size == 0:
            continue
        # Q18 Addendum #17: bucket-shared range when given, else per-bp range.
        if shared_vmin is not None and shared_vmax is not None and shared_vmax > 0:
            norm_vmin = max(float(shared_vmin), 1e-10)
            norm_vmax = float(shared_vmax)
        else:
            norm_vmin = max(float(finite_nonzero.min()), 1e-10)
            norm_vmax = float(H_prop.max())
        # Q32 Addendum #29: per-layer magnitude floor + transparent NaN.
        layer_floor = norm_vmax * float(layered_overlay_floor_fraction)
        H_prop_masked = np.where(
            H_prop >= layer_floor, H_prop, np.nan,
        ) if layer_floor > 0 else H_prop
        try:
            cmap = plt.get_cmap(_get_bodypart_cmap(spatial_config, bp)).copy()
        except ValueError:
            cmap = plt.get_cmap(_COMPOSITE_FALLBACK_CMAP).copy()
        cmap.set_bad((1.0, 1.0, 1.0, 0.0))  # Q32: transparent for NaN.
        ax.imshow(
            H_prop_masked.T,
            origin="lower",
            extent=ext,
            cmap=cmap,
            alpha=_COMPOSITE_ALPHA,
            aspect="auto",
            norm=mcolors.LogNorm(vmin=max(norm_vmin, layer_floor), vmax=norm_vmax),
        )
        n_layered += 1

    if extent_first is None:
        # No data for any bodypart — placeholder.
        ax.text(
            0.5, 0.5, f"{panel_title}\n(no data)",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return

    # Composite axis range = first bp's per_center_mode block. For
    # whiskers the 6 per_center_mode entries differ by ~10s of px (each
    # whisker pad has a slightly different baseline) and we accept that
    # the first-bp range will under-cover the others slightly. For
    # fiducial pairs the config supplies a UNIFIED bilateral range so
    # the first-bp lookup already covers L+R. If both lookups miss the
    # config, fall back to the union of bp extents.
    per_mode = _get_per_center_mode_params(
        spatial_config, family_bodyparts[0], family_center_mode,
    )
    if per_mode["xlim"]:
        ax.set_xlim(per_mode["xlim"])
    else:
        ax.set_xlim(extent_first[0], extent_first[1])
    if per_mode["ylim"]:
        ax.set_ylim(per_mode["ylim"])
    else:
        ax.set_ylim(extent_first[2], extent_first[3])
    ax.invert_yaxis()
    # Q22 Addendum #21: uniform tick + axis-label polish.
    _apply_q22_panel_polish(ax)
    ax.set_title(panel_title, fontsize=_Q22_PANEL_TITLE_FONTSIZE)


def _attach_composite_colorbars(
    fig: plt.Figure,
    family_bodyparts: list[str],
    spatial_config: dict[str, Any],
    *,
    family_label: str,
    shared_vmin: float | None,
    shared_vmax: float | None,
) -> None:
    """Pattern B composite legend / colorbar block on figure right.

    Q24 Addendum #24 (original): per-bp colorbars stacked vertically.
    Q30 Addendum #28 (refinement): switch to a swatch legend when n_bps
    ≥ 3 (whiskers = 6 bps overlapped labels at stacked-cbar density).
    For n_bps = 2 (fiducial bilateral pairs spout / eye) keep the
    stacked-colorbar path with Q31 layout fixes.

    Trade-off: swatch legend loses per-bp density quantitation but
    gains readability. Acceptable for whiskers since the layered
    overlay is primarily about spatial extent + which-whisker-is-where,
    not per-whisker density.

    When ``shared_vmin`` / ``shared_vmax`` are missing (standalone
    smoke without a bucket precompute pass), the colorbar / legend
    block is skipped silently.
    """
    if shared_vmin is None or shared_vmax is None or shared_vmax <= 0:
        return
    n_bps = len(family_bodyparts)
    if n_bps == 0:
        return
    if n_bps >= 3:
        # Q30 Addendum #28: swatch legend (no quantitative scale, just
        # which-bp-is-which-color). Sample at 0.7 of each cmap so the
        # swatch reads as a saturated middle shade rather than the
        # near-white low end.
        import matplotlib.patches as mpatches
        handles: list[Any] = []
        for bp in family_bodyparts:
            cmap_name = _get_bodypart_cmap(spatial_config, bp)
            try:
                cmap = plt.get_cmap(cmap_name)
            except ValueError:
                cmap = plt.get_cmap(_COMPOSITE_FALLBACK_CMAP)
            handles.append(mpatches.Patch(color=cmap(0.7), label=bp))
        # Attach to the figure (anchored to the right edge) so the
        # legend persists across the 3 trial-group sub-axes.
        fig.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(0.86, 0.5),
            fontsize=_Q22_PANEL_TITLE_FONTSIZE,
            framealpha=0.9, frameon=True,
            title=family_label,
            title_fontsize=_Q22_AXIS_LABELSIZE,
        )
        return
    # n_bps < 3 → keep stacked per-bp colorbars (Q24 original path).
    norm = mcolors.LogNorm(
        vmin=max(float(shared_vmin), 1e-10), vmax=float(shared_vmax),
    )
    # Allocate stacked axes at fig right (one row per bp).
    cbar_left = 0.88
    cbar_width = 0.018
    total_height = 0.7
    spacing = 0.04  # Q31 Addendum #28: generous spacing to prevent label overlap.
    block_height = (total_height - spacing * (n_bps - 1)) / n_bps
    base_bottom = 0.5 - total_height / 2.0
    for i, bp in enumerate(family_bodyparts):
        cmap_name = _get_bodypart_cmap(spatial_config, bp)
        try:
            cmap = plt.get_cmap(cmap_name)
        except ValueError:
            cmap = plt.get_cmap(_COMPOSITE_FALLBACK_CMAP)
        # Top → bottom in the order of family_bodyparts (visual reading order).
        bottom = base_bottom + (n_bps - 1 - i) * (block_height + spacing)
        cax = fig.add_axes([cbar_left, bottom, cbar_width, block_height])
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(bp, fontsize=_Q22_AXIS_LABELSIZE - 2)
        cbar.ax.tick_params(labelsize=_Q22_TICK_LABELSIZE - 2)


def _assemble_composite_figure(
    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int]]],
    scope: Scope,
    suptitle: str,
    *,
    family_bodyparts: list[str],
    family_center_mode: str,
    family_label: str,
    defaults: dict[str, Any],
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Render the multi-bp composite figure — 1×3 grid (tone_aligned) /
    1×1 (whole_session), each panel layering N bodyparts via
    :func:`_render_composite_panel_axis`. Per-trial-group panel title
    includes session count + tone-event count when tone-aligned.

    Q31 Addendum #28: figsize bumped wider for the right-anchored
    swatch legend / stacked colorbar block. Manual subplots_adjust
    reserves room; ``constrained_layout=False`` preserved per the
    matplotlib API note below.
    """
    spatial_config = defaults["dlc_spatial"]
    tone_cfg = defaults.get("dlc_spatial_tone_aligned", {}) or {}
    # Q32 Addendum #29: per-layer magnitude floor for Pattern B overlays.
    layered_overlay_floor_fraction = float(
        tone_cfg.get("layered_overlay_floor_fraction", 0.05),
    )
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        # Q31 Addendum #28: width 18 → 20 to accommodate the right-anchored
        # swatch legend / stacked cbar block.
        figsize = (20.0, 5.0)
    else:
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        figsize = (10.0, 6.0)

    # NOTE: constrained_layout=False here — the right-edge legend needs
    # manual room reserved via fig.subplots_adjust(right=...) at the
    # bottom of this function. constrained_layout would override that
    # call (incompatible APIs per matplotlib docs).
    fig, axes_obj = plt.subplots(
        nrows=1, ncols=len(trial_groups),
        figsize=figsize, constrained_layout=False,
    )
    axes = list(axes_obj.flat) if hasattr(axes_obj, "flat") else [axes_obj]
    for tg, ax in zip(trial_groups, axes, strict=False):
        composite_panels = panels.get(tg, [])
        if not composite_panels:
            ax.set_axis_off()
            continue
        # Summarize sessions + tones across bps (same values per bp
        # within a tg, modulo missing data; use first non-empty for title).
        n_sess = 0
        n_tones = 0
        for _bp, H, _ext, ns, nt, _n_total in composite_panels:
            if H is not None and float(H.sum()) > 0:
                n_sess = max(n_sess, ns)
                n_tones = max(n_tones, nt)
        if scope == "tone_aligned":
            panel_title = f"trial_group={tg} | n_sess={n_sess} | n_tones={n_tones}"
        else:
            panel_title = f"whole session | n_sess={n_sess}"
        _render_composite_panel_axis(
            ax, composite_panels, spatial_config,
            family_bodyparts=family_bodyparts,
            family_center_mode=family_center_mode,
            panel_title=panel_title,
            shared_vmin=shared_vmin, shared_vmax=shared_vmax,
            layered_overlay_floor_fraction=layered_overlay_floor_fraction,
        )
    # Q24 Addendum #24: stacked per-bp colorbars on figure right.
    _attach_composite_colorbars(
        fig, family_bodyparts, spatial_config,
        family_label=family_label,
        shared_vmin=shared_vmin, shared_vmax=shared_vmax,
    )
    fig.suptitle(suptitle, fontsize=_Q22_SUPTITLE_FONTSIZE)
    # Make room for the right-edge colorbar block.
    fig.subplots_adjust(right=0.85)
    return fig


def render_individual_session_heatmap(
    animal: str,
    family_entry: str,
    date: dt.date,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Render the per-session heatmap figure for one (animal, family,
    date, scope) cell.

    Tone-aligned: 1×3 panel grid (all, L, R) using the
    (0, 8000) ms window. Whole-session: 1×1 panel (all only; no
    trial-group split).

    Composite families (whiskers + fiducial bilateral pairs; any family
    with > 1 bodypart) dispatch to the Pattern B layered-overlay
    renderer (Addendum #10 Q1, generalized in Addendum #13).

    Q18 Addendum #17: ``shared_vmin`` / ``shared_vmax`` propagate
    bucket-shared LogNorm bounds into the panel renderers (used by the
    cohort driver's two-pass-per-bucket flow).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    # Q22 Addendum #21 title spec: animal | family | date | scope | plot_type.
    suptitle = (
        f"{animal} | {family_entry} | {date.isoformat()} | {scope} "
        f"| individual_session"
    )
    if len(bodyparts) > 1:
        # Composite family — Pattern B layered overlay (Addenda #10/#13).
        composite_panels = _compute_composite_panels(
            animal, [date], bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        return _assemble_composite_figure(
            composite_panels, scope, suptitle,
            family_bodyparts=bodyparts,
            family_center_mode=center_mode,
            family_label=family_entry,
            defaults=defaults,
            shared_vmin=shared_vmin, shared_vmax=shared_vmax,
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_session(
        animal, date, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
    )
    return _assemble_panel_figure(
        panels, bp, center_mode, scope, suptitle, defaults=defaults,
        shared_vmin=shared_vmin, shared_vmax=shared_vmax,
    )


def render_binned_sessions_heatmap(  # noqa: D401
    animal: str,
    family_entry: str,
    rel_day_bin_label: str,
    dates_in_bin: list[dt.date],
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Render the per-(rel_day_bin) heatmap figure for one (animal,
    family, rel_day_bin, scope) cell.

    Aggregates frames across all ``dates_in_bin`` for the bin (single
    bin per call; cohort driver groups sessions by bin using
    ``_compute_rel_day_bin_label`` from ``_day_binned`` module).

    Panel layout same as :func:`render_individual_session_heatmap`.
    Composite families (any family with > 1 bodypart) dispatch to the
    Pattern B layered-overlay renderer.

    Q18 Addendum #17: ``shared_vmin`` / ``shared_vmax`` propagate
    bucket-shared LogNorm bounds (driver uses them across all bins ×
    trial-groups in the (family, bin_size, scope) bucket).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    # Q22 Addendum #21 title spec: animal | family | bin_label | scope | plot_type.
    suptitle = (
        f"{animal} | {family_entry} | rel_day_bin={rel_day_bin_label} "
        f"| {scope} | binned_sessions  "
        f"(n_dates_in_bin={len(dates_in_bin)})"
    )
    if len(bodyparts) > 1:
        # Composite family — Pattern B layered overlay (Addenda #10/#13).
        composite_panels = _compute_composite_panels(
            animal, dates_in_bin, bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        return _assemble_composite_figure(
            composite_panels, scope, suptitle,
            family_bodyparts=bodyparts,
            family_center_mode=center_mode,
            family_label=family_entry,
            defaults=defaults,
            shared_vmin=shared_vmin, shared_vmax=shared_vmax,
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_dates(
        animal, dates_in_bin, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
    )
    return _assemble_panel_figure(
        panels, bp, center_mode, scope, suptitle, defaults=defaults,
        shared_vmin=shared_vmin, shared_vmax=shared_vmax,
    )


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #10 Q2 — proportion_differences plot type.
# Math per legacy 20260111_DLC_analysis_build-parquet_tongue.ipynb cells
# 2270-2360: D = H_post_prop - H_pre_prop. Divergent cmap with
# TwoSlopeNorm centered on 0. Animal-level baseline = pool of all
# pre-stroke sessions (rel_day <= 0).
# ---------------------------------------------------------------------------

# Phase 7c.2 Addendum #19 Q20: proportion_differences uses a custom
# red→gray→blue diverging cmap with `set_bad("white")` for NaN /
# no-data cells; figure + panel facecolor set to "white" so NaN cells
# blend into the background. Supersedes the legacy ``RdBu_r``
# white-at-zero convention from the 3 bodypart-specific notebooks
# (20260111_tongue, 20251117_nose, 20251117_jaw, DIFF_CMAP_NAME = "RdBu_r")
# and the whisker-composite ``_WHISKER_DIVERGENT_CMAPS`` dispatch from
# 20251202_..._pixelbin.ipynb. Gray-at-zero gives near-zero diffs a
# visible neutral color against the white background (white-at-zero
# would blend them into the no-data cells).
#
# Sign convention: 0.0 → red (negative diffs), 0.5 → gray (zero),
# 1.0 → blue (positive diffs). Matches Q20 statement; legacy "RdBu_r"
# was already (red=negative, blue=positive) so the sign convention is
# inherited from legacy.
_PROPORTION_DIFF_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "rgb_diverging",
    # Q22 Addendum #21: midpoint lightened from "gray" (RGB ~0.5) to
    # "#d0d0d0" (~0.82) so near-zero diffs aren't visually heavy against
    # the white panel background.
    # Q25 Addendum #24: cmap direction FLIPPED — blue for negative diffs
    # (post < pre, decreased proportion), red for positive diffs
    # (post > pre, increased proportion). Matches the IS+BS LogNorm
    # convention (redder/hotter = denser) so a viewer reading both plot
    # types together gets a consistent "more = warmer" mental model.
    [(0.0, "blue"), (0.5, "#d0d0d0"), (1.0, "red")],
    N=256,
)
_PROPORTION_DIFF_CMAP.set_bad("white")

# Legacy whisker-composite per-bp divergent cmaps (lines 1376-1381 of
# 20251202_..._pixelbin.ipynb). Retained for reference; superseded by
# the Q20 uniform cmap.
_WHISKER_DIVERGENT_CMAPS_LEGACY: dict[str, str] = {
    "L_whiskers_1": "BrBG",
    "L_whiskers_2": "coolwarm",
    "L_whiskers_3": "bwr",
    "R_whiskers_1": "BrBG",
    "R_whiskers_2": "coolwarm",
    "R_whiskers_3": "bwr",
}

_PROPORTION_DIFF_DEFAULT_CMAP_LEGACY = "coolwarm"
_PROPORTION_DIFF_VMAX_PERCENTILE = 99.0


def _split_pre_post_dates(
    dates: list[dt.date], animal_info: AnimalInfo,
) -> tuple[list[dt.date], list[dt.date]]:
    """Split a date list into (pre_dates, post_dates).

    pre_dates: rel_day <= 0 (includes stroke_date itself per AnimalInfo
    convention — stroke_date is the LAST PRE-STROKE SESSION).
    post_dates: rel_day >= 1.
    """
    pre: list[dt.date] = []
    post: list[dt.date] = []
    for d in dates:
        rel = animal_info.day_relative_to_stroke(d)
        if rel <= 0:
            pre.append(d)
        else:
            post.append(d)
    return sorted(pre), sorted(post)


def _compute_proportion_diff(
    animal: str,
    pre_dates: list[dt.date],
    post_dates: list[dt.date],
    bodypart: str,
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> tuple[np.ndarray | None, list[float] | None, int, int]:
    """Compute D = H_post_prop - H_pre_prop for one bodypart.

    Returns ``(D, extent, n_pre_sessions, n_post_sessions)``. Returns
    ``(None, None, 0, 0)`` if either side has no contributing sessions.

    For tone-aligned scope: aggregates frames inside the (0, 8000) ms
    tone window across all trial groups (trial_group="all"). For
    whole-session scope: no window.
    """
    if scope == "tone_aligned":
        tg_arg: str | None = "all"
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        tg_arg = None
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    H_pre, ext_pre, n_pre, _, n_total_pre = compute_animal_aggregated_histogram(
        animal, pre_dates, bodypart, center_mode, resolver,
        trial_group=tg_arg, window_ms=window_ms,
        defaults=defaults, animal_info=animal_info,
    )
    H_post, ext_post, n_post, _, n_total_post = compute_animal_aggregated_histogram(
        animal, post_dates, bodypart, center_mode, resolver,
        trial_group=tg_arg, window_ms=window_ms,
        defaults=defaults, animal_info=animal_info,
    )

    if H_pre is None or H_post is None:
        return None, None, n_pre, n_post
    # Q17 (Phase 7c.2 Addendum #16): denominators are total in-window
    # frame counts, not H_counts.sum(). Same shift applied everywhere
    # downstream — proportion = "tracking_rate × spatial_distribution"
    # composite (sum ≤ 1.0 = passed_frames / total_frames).
    pre_sum = float(n_total_pre)
    post_sum = float(n_total_post)
    if pre_sum == 0.0 or post_sum == 0.0:
        return None, None, n_pre, n_post

    H_pre_prop = H_pre / pre_sum
    H_post_prop = H_post / post_sum
    D = H_post_prop - H_pre_prop

    # Mask cells where both sides had zero counts (no-data) — matches
    # legacy mask_for_plot at line 2298 of the legacy notebook.
    no_data = (H_pre == 0) & (H_post == 0)
    if no_data.any():
        D = np.where(no_data, np.nan, D)

    ext = ext_pre if ext_pre is not None else ext_post
    return D, list(ext) if ext is not None else None, n_pre, n_post


def _render_proportion_diff_panel(
    ax: plt.Axes,
    D: np.ndarray | None,
    extent: list[float] | None,
    bodypart: str,
    center_mode: str,
    *,
    spatial_config: dict[str, Any],
    cmap_name: str | None = None,
    title: str = "",
    shared_vmax: float | None = None,
) -> None:
    """Render one (bodypart, center_mode) proportion-diff D array onto an
    Axes.

    Phase 7c.2 Addendum #19 Q20: cmap = custom red→gray→blue diverging,
    ``set_bad("white")`` for NaN/no-data cells, panel facecolor white.
    The legacy ``cmap_name`` kwarg is retained for backward compat with
    callers that explicitly supply a name (will be passed through
    ``plt.get_cmap`` with the legacy 0.85-grey ``set_bad`` extreme).

    Phase 7c.2 Addendum #15 Q14: ``shared_vmax`` (when supplied) is the
    symmetric colormap saturation point so every panel in the SVG
    shares one diverging color scale (vmin=-shared_vmax,
    vmax=+shared_vmax). When ``shared_vmax`` is None, fall back to the
    legacy per-panel 99th-percentile-of-|D| TwoSlopeNorm.
    """
    # Q20: white panel background — NaN/no-data cells blend in.
    ax.set_facecolor("white")
    if D is None or extent is None:
        ax.text(0.5, 0.5, f"{title}\n(no data)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    finite_abs = np.abs(D[np.isfinite(D)])
    if finite_abs.size == 0:
        ax.text(0.5, 0.5, f"{title}\n(no finite D)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    if shared_vmax is not None:
        vmax = max(float(shared_vmax), 1e-12)
        norm = mcolors.Normalize(vmin=-vmax, vmax=vmax)
    else:
        vmax = float(np.percentile(finite_abs, _PROPORTION_DIFF_VMAX_PERCENTILE))
        vmax = max(vmax, 1e-12)
        norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    if cmap_name is None:
        # Q20 default: red→gray→blue with white-for-bad.
        cmap = _PROPORTION_DIFF_CMAP
    else:
        try:
            cmap = plt.get_cmap(cmap_name).with_extremes(bad="0.85")
        except (ValueError, AttributeError):
            cmap = _PROPORTION_DIFF_CMAP
    D_plot = np.ma.array(D, mask=~np.isfinite(D))
    ax.imshow(
        D_plot.T, origin="lower", extent=extent,
        cmap=cmap, aspect="auto", norm=norm,
    )
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    if per_mode["xlim"]:
        ax.set_xlim(per_mode["xlim"])
    if per_mode["ylim"]:
        ax.set_ylim(per_mode["ylim"])
    ax.invert_yaxis()
    # Q22 Addendum #21: uniform tick + axis-label polish + larger title.
    _apply_q22_panel_polish(ax)
    ax.set_title(title, fontsize=_Q22_PANEL_TITLE_FONTSIZE)
    # Q24 Addendum #24: per-panel colorbars are dropped here; ONE shared
    # colorbar is attached at the figure level by
    # `render_proportion_difference_heatmap` (Q18 shares vmax across all
    # panels in the SVG → one bar correct + reduces clutter). The outer
    # function recovers the imshow artifact via `ax.images[0]` post-hoc.


def _compute_proportion_diff_for_bin(
    animal: str,
    bin_dates: list[dt.date],
    H_pre_pool_prop: np.ndarray,
    extent_pre: list[float],
    bodyparts: list[str],
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
    trial_group: str = "all",
) -> tuple[np.ndarray | None, list[float] | None, int]:
    """Compute D = H_bin_prop - H_pre_pool_prop for one rel_day_bin.

    For single-bp family: per-bp histogram. For composite families
    (whiskers + fiducial bilateral pairs, any family with > 1 bp): pooled
    N-bp pseudo-histogram (matches UOT composite handling per legacy
    'Pool all six whiskers as one part' pattern, generalized in
    Addendum #13).

    ``trial_group`` (Phase 7c.2 Addendum #15 Q16) selects the
    tone-aligned trial-group filter; ignored when scope='whole_session'.

    Returns ``(D, extent, n_sessions_in_bin)``.
    """
    if len(bodyparts) > 1:
        # Composite family: pooled N-bp pseudo-bp.
        H_bin, ext, n_sess, n_total_bin = _aggregate_for_dates_pooled_bodyparts(
            animal, bin_dates, bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
            trial_group=trial_group,
        )
    else:
        if scope == "tone_aligned":
            tg_arg: str | None = trial_group
            window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
        else:
            tg_arg = None
            window_ms = None
        bp = bodyparts[0]
        H_bin, ext, n_sess, _, n_total_bin = compute_animal_aggregated_histogram(
            animal, bin_dates, bp, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
    if H_bin is None or n_total_bin == 0:
        return None, None, n_sess
    # Q17 Addendum #16: denominator = total in-window frames (sum across
    # sessions + bps), not H_bin.sum().
    H_bin_prop = H_bin / float(n_total_bin)
    D = H_bin_prop - H_pre_pool_prop
    no_data = (H_pre_pool_prop == 0) & (H_bin == 0)
    if no_data.any():
        D = np.where(no_data, np.nan, D)
    return D, list(ext) if ext is not None else extent_pre, n_sess


def render_proportion_difference_heatmap(
    animal: str,
    family_entry: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    bin_size_days: int,
    trial_group: str = "all",
    dates: list[dt.date] | None = None,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Render the per-(animal, family, scope, bin_size, trial_group)
    proportion-difference grid-summary SVG per Addendum #11 Q2.B +
    Addendum #15 Q14/Q16.

    Animal-level pre-stroke baseline (pool of all rel_day <= 0 sessions,
    same trial_group filter as the per-bin panels) is fixed; one panel
    per rel_day_bin at the requested ``bin_size_days`` showing
    ``D_bin = H_bin_prop - H_pre_pool_prop``. Both pre-stroke bins
    (within-pre variability) and post-stroke bins (stroke-induced
    departure) get panels.

    ``trial_group`` (Addendum #15 Q16): filter frames to this tone-aligned
    trial group before per-bin aggregation. For tone_aligned scope, the
    driver fans out 3 SVGs per (animal, family, bin_size) — one per
    trial_group ∈ {all, L, R}. For whole_session scope, only 'all' is
    meaningful (no trial-group split).

    Single-bp families: per-bp D per panel.
    Composite families (whiskers + fiducial bilateral pairs, any family
    with > 1 bp): pooled N-bp pseudo-bp per panel (matches UOT composite
    treatment per Addendum #13 generalization).

    Addendum #15 Q14: per-bin D arrays are pre-computed; global
    ``vmax = max(|D|.max() across bins)`` is shared across all panels in
    the SVG; symmetric diverging colormap normalization (vmin=-vmax,
    vmax=+vmax) makes inter-bin diff intensities visually comparable.

    Layout: 4-col grid (analogous to UOT grid summary); rows = ceil(N_bins / 4).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    if dates is None:
        raise ValueError(
            "render_proportion_difference_heatmap requires explicit `dates` "
            "list (the YAML-filtered cohort date set). Driver passes it."
        )

    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    spatial_config = defaults["dlc_spatial"]
    pre_dates, _post_dates = _split_pre_post_dates(dates, animal_info)

    # Compute fixed reference: animal-level pre-stroke pool, proportion-
    # normalized via Q17 total-frame denominator. Apply the same
    # trial_group filter so the per-bin comparison is apples-to-apples.
    if len(bodyparts) > 1:
        H_pre_pool, ext_pre, n_pre_sess, n_total_pre = (
            _aggregate_for_dates_pooled_bodyparts(
                animal, pre_dates, bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
                trial_group=trial_group,
            )
        )
    else:
        if scope == "tone_aligned":
            tg_arg: str | None = trial_group
            window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
        else:
            tg_arg = None
            window_ms = None
        bp = bodyparts[0]
        H_pre_pool, ext_pre, n_pre_sess, _, n_total_pre = (
            compute_animal_aggregated_histogram(
                animal, pre_dates, bp, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
            )
        )

    if H_pre_pool is None or n_total_pre == 0:
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.text(
            0.5, 0.5,
            f"{animal}/{family_entry}/{scope}/bin{bin_size_days}d/tg={trial_group}\n"
            f"empty pre-stroke pool (n_pre={len(pre_dates)})",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    # Q17 Addendum #16: total-frame denominator (not H_pre_pool.sum()).
    H_pre_pool_prop = H_pre_pool / float(n_total_pre)

    # Group ALL dates (pre + post) by rel_day_bin at the requested bin_size.
    bins: dict[str, list[dt.date]] = {}
    from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=animal_info.stroke_date, bin_days=int(bin_size_days),
        )
        bins.setdefault(label, []).append(d)
    bin_labels = sorted(bins.keys(), key=_bin_label_sort_key)

    # Q14: pre-compute all per-bin D arrays first, then derive shared
    # symmetric vmax across the SVG. Each tuple is (bin_label, D, ext, n_sess).
    bin_results: list[tuple[str, np.ndarray | None, list[float] | None, int]] = []
    for bin_label in bin_labels:
        bin_dates = bins[bin_label]
        D, ext, n_sess = _compute_proportion_diff_for_bin(
            animal, bin_dates, H_pre_pool_prop, ext_pre,
            bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
            trial_group=trial_group,
        )
        bin_results.append((bin_label, D, ext, n_sess))
    # Q14 per-SVG vmax (within-file). Q18 supersedes this when driver
    # supplies shared_vmax (bucket-shared across all 3 tg-SVGs in the
    # (family, bin_size, scope) bucket).
    if shared_vmax is None:
        abs_maxes: list[float] = []
        for _label, D, _ext, _n in bin_results:
            if D is None:
                continue
            finite_abs = np.abs(D[np.isfinite(D)])
            if finite_abs.size:
                abs_maxes.append(float(finite_abs.max()))
        local_shared_vmax = max(abs_maxes) if abs_maxes else 1e-12
    else:
        local_shared_vmax = float(shared_vmax)

    bp_for_axis = bodyparts[0]  # reference for spatial_config axis lookup
    n_bins = len(bin_labels)
    ncols = min(4, max(1, n_bins))
    nrows = max(1, int(np.ceil(n_bins / ncols)))
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 5.0, nrows * 4.0),
        constrained_layout=True,
    )
    # Q20 Addendum #19: figure background white (panel background also
    # set to white inside `_render_proportion_diff_panel`).
    fig.patch.set_facecolor("white")
    axes = list(axes_obj.flat) if hasattr(axes_obj, "flat") else [axes_obj]
    for (bin_label, D, ext, n_sess), ax in zip(bin_results, axes, strict=False):
        # Q20 Addendum #19: uniform red→gray→blue cmap with white-for-bad
        # across all families (drops legacy per-bp whisker-composite cmap
        # dispatch + the legacy "coolwarm" default).
        title = f"bin {bin_label}  n_sess={n_sess}"
        _render_proportion_diff_panel(
            ax, D, ext, bp_for_axis, center_mode,
            spatial_config=spatial_config,
            cmap_name=None,  # Q20 default cmap
            title=title,
            shared_vmax=local_shared_vmax,
        )
    for ax in axes[len(bin_labels):]:
        ax.set_axis_off()
    # Q24 Addendum #24: ONE shared colorbar at the figure right, since
    # all panels share the same symmetric Normalize per Q14/Q18. Find
    # the first panel with a rendered imshow and use its mappable.
    shared_im = None
    for ax in axes:
        if ax.images:
            shared_im = ax.images[0]
            break
    if shared_im is not None:
        cbar = fig.colorbar(
            shared_im,
            ax=list(axes_obj.flat) if hasattr(axes_obj, "flat") else [axes_obj],
            shrink=0.6, pad=0.02,
        )
        cbar.set_label(
            "Δ proportion (post − pre)", fontsize=_Q22_AXIS_LABELSIZE,
        )
        _apply_q22_colorbar_polish(cbar)
    # Q22 Addendum #21 title spec: animal | family | bin_size − all_pre_stroke | scope | trial_group.
    bucket_label = "bucket" if shared_vmax is not None else "file"
    fig.suptitle(
        f"{animal} | {family_entry} | bin{int(bin_size_days)}d − all_pre_stroke "
        f"| {scope} | trial_group={trial_group}  "
        f"(n_pre_sess={n_pre_sess}, {bucket_label} |vmax|={local_shared_vmax:.3g})",
        fontsize=_Q22_SUPTITLE_FONTSIZE,
    )
    return fig


def _bin_label_sort_key(label: str) -> tuple[int, int]:
    """Sort key for ``f"{lo}..{hi}"`` rel_day_bin labels — chronological
    by ``lo`` so the grid reads pre→post left-to-right."""
    try:
        lo_str, _hi_str = label.split("..")
        return (int(lo_str), 0)
    except (ValueError, AttributeError):
        return (10**9, 0)


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #10 Q3 — unbalanced_ot plot type (per Q3a Read X
# outcome: balanced sinkhorn from 20251202_..._pixelbin.ipynb line 6937+
# is the displacement-field source. "unbalanced_ot" path-name preserved
# per Q12.B; semantics is balanced-OT displacement-field arrow plot).
# Math + arrow conventions ported verbatim from legacy lines 7340-7515.
# ---------------------------------------------------------------------------

# OT parameters + arrow scale constants ported verbatim from
# 20251202_..._pixelbin.ipynb cell preamble (lines 6087-6098). Per
# Addendum #14 Q3a.B + Q3b: UNBALANCED sinkhorn (not the balanced
# variant at line 6937+ that an earlier draft used).
_OT_REG = 0.02              # entropic regularization
_OT_REG_M = 10.0            # marginal (mass) relaxation penalty
_OT_NUMITERMAX = 500
_OT_STOPTHR = 1e-6
_OT_MIN_MASS = 1e-4         # threshold below which marginal is treated as zero
_OT_EPS = 1e-8              # floor on marginals to stabilize sinkhorn
_ARROW_LW_MIN = 0.1         # legacy ARROW_LW_MIN
_ARROW_LW_MAX = 3.0         # legacy ARROW_LW_MAX
_ARROW_ALPHA_MIN = 0.9      # legacy ARROW_ALPHA_MIN (constant in legacy)
_ARROW_ALPHA_MAX = 0.9      # legacy ARROW_ALPHA_MAX
# Head dimensions scale with histogram cell size dx/dy at render time
# (legacy lines 6175-6178: HEAD_W = 0.1..0.65 × dx).
_ARROW_HEAD_W_MIN_FRAC_DX = 0.1
_ARROW_HEAD_W_MAX_FRAC_DX = 0.65
_ARROW_HEAD_L_MIN_FRAC_DY = 0.1
_ARROW_HEAD_L_MAX_FRAC_DY = 0.65
_OT_ARROW_CMAP = "YlGnBu"
# Q27 Addendum #25/#26: cmaps flipped to match PD red=increase / blue=decrease.
# mass_destroy ≈ "mass leaving from pre positions" ≈ density decrease → Blues.
# mass_create  ≈ "mass arriving at post positions" ≈ density increase → Reds.
# (Pre-Q27: destroy=Reds, create=Blues — opposite convention from PD.)
_OT_MASS_DESTROY_CMAP = "Blues"
_OT_MASS_CREATE_CMAP = "Reds"


def _compute_unbalanced_ot_plan(
    H_pre: np.ndarray,
    H_sess: np.ndarray,
    extent: list[float],
) -> dict[str, Any] | None:
    """Compute the UNBALANCED-OT plan + displacement field + mass-change
    maps for one (pre, sess) histogram pair. Per Addendum #14 Q3a.B
    (Read Y) — ports the legacy ``ot_unb.sinkhorn_unbalanced`` invocation
    at line 6376 + mass-change at 6403-6409 + displacement at 6444-6456
    of ``20251202_..._pixelbin.ipynb``.

    Returns a dict with keys ``{Xg, Yg, dx, dy, Ux, Uy, mag, mass_grid,
    mass_destroy, mass_create}`` or ``None`` if both marginals are
    essentially empty (per legacy MIN_MASS=1e-4 gate).

    Marginals are PROPORTION-normalized before sinkhorn — same
    convention as proportion_differences (Addendum #11 Q2.B). Sinkhorn
    is unbalanced; deviation from input marginals quantified by
    ``mass_destroy = max(a - G.sum(axis=1), 0)`` and
    ``mass_create = max(b - G.sum(axis=0), 0)``.
    """
    try:
        import ot
        from ot import unbalanced as ot_unb
    except ImportError:
        return None

    nx, ny = H_pre.shape
    nxy = nx * ny

    a = H_pre.astype(float).ravel()
    b = H_sess.astype(float).ravel()
    a[a < 0] = 0.0
    b[b < 0] = 0.0
    sum_a = float(a.sum())
    sum_b = float(b.sum())
    if sum_a <= _OT_MIN_MASS and sum_b <= _OT_MIN_MASS:
        return None
    # Normalize to proportions.
    if sum_a > 0:
        a = a / sum_a
    if sum_b > 0:
        b = b / sum_b
    # Clip to EPS floor per legacy lines 6367-6373.
    if a.sum() <= _OT_MIN_MASS:
        a[:] = _OT_EPS
    if b.sum() <= _OT_MIN_MASS:
        b[:] = _OT_EPS
    a = np.clip(a, _OT_EPS, None)
    b = np.clip(b, _OT_EPS, None)

    dx = (extent[1] - extent[0]) / nx
    dy = (extent[3] - extent[2]) / ny
    xs = np.linspace(extent[0] + dx / 2, extent[1] - dx / 2, nx)
    ys = np.linspace(extent[2] + dy / 2, extent[3] - dy / 2, ny)
    Xg, Yg = np.meshgrid(xs, ys, indexing="ij")
    coords_xy = np.column_stack([Xg.ravel(), Yg.ravel()])

    C = ot.dist(coords_xy, coords_xy, metric="euclidean")
    C = C / max(C.max(), 1e-9)

    try:
        G = ot_unb.sinkhorn_unbalanced(
            a, b, C,
            reg=_OT_REG,
            reg_m=_OT_REG_M,
            stopThr=_OT_STOPTHR,
            numItermax=_OT_NUMITERMAX,
            verbose=False,
        )
    except Exception:
        return None

    if G.shape != (nxy, nxy):
        return None

    out_from_pre = G.sum(axis=1)
    into_post = G.sum(axis=0)

    # Mass-change maps (legacy lines 6408-6409).
    mass_destroy = np.maximum(a - out_from_pre, 0.0).reshape(nx, ny)
    mass_create = np.maximum(b - into_post, 0.0).reshape(nx, ny)

    # Displacement field (legacy lines 6443-6456).
    disp = np.zeros_like(coords_xy)
    nz = out_from_pre > 0
    if np.any(nz):
        disp[nz] = (
            (G[nz] @ coords_xy - out_from_pre[nz, None] * coords_xy[nz])
            / out_from_pre[nz, None]
        )
    Ux = disp[:, 0].reshape(nx, ny)
    Uy = disp[:, 1].reshape(nx, ny)
    mag = np.hypot(Ux, Uy)
    mass_grid = out_from_pre.reshape(nx, ny)

    return {
        "Xg": Xg, "Yg": Yg, "dx": float(dx), "dy": float(dy),
        "Ux": Ux, "Uy": Uy, "mag": mag,
        "mass_grid": mass_grid,
        "mass_destroy": mass_destroy,
        "mass_create": mass_create,
    }


def _render_ot_mass_change_panels(
    ax_destroy: plt.Axes,
    ax_create: plt.Axes,
    mass_destroy: np.ndarray,
    mass_create: np.ndarray,
    extent: list[float],
    bodypart: str,
    center_mode: str,
    *,
    spatial_config: dict[str, Any],
    bin_label: str,
    shared_destroy_vmin: float | None = None,
    shared_destroy_vmax: float | None = None,
    shared_create_vmin: float | None = None,
    shared_create_vmax: float | None = None,
    mass_floor_fraction: float = 0.05,
) -> None:
    """Render the 2 mass-change heatmaps onto a pair of Axes —
    ``mass_destroy`` (Blues cmap per Q27) + ``mass_create`` (Reds per
    Q27). Linear imshow per legacy lines 6411-6441. Y-axis inverted to
    match heatmap convention.

    Q18 Addendum #17: ``shared_*_vmax`` (when given) pin the linear vmax
    for each cmap — used by the driver to share color scales across all
    bins × tg in the UOT bucket.

    Q28 Addendum #26: zero-mass bins are NaN-masked before imshow so they
    render via ``set_bad("white")`` instead of the cmap's near-white
    low-intensity tint (Blues / Reds at index 0 is a faint colored shade,
    not white).

    Q29 Addendum #27: ``mass_floor_fraction`` raises the NaN mask threshold
    from strict-zero to ``floor = shared_vmax × mass_floor_fraction``
    (default 0.05 = 5% of bucket vmax). POT's sinkhorn_unbalanced
    returns a dense transport matrix where every bin has tiny-but-nonzero
    mass (~1e-13 to 1e-8) from the regularizer — Q28's strict-zero gate
    let this through and rendered as a faint colored background. Q29
    floors at a fraction of the bucket-shared vmax so only meaningful
    mass-change regions retain visible color. Colorbar ``vmin=floor``
    (instead of bucket_vmin near-zero) so the cbar covers only the
    visually-meaningful range.
    """
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    xl = per_mode["xlim"] if per_mode["xlim"] else (extent[0], extent[1])
    yl = per_mode["ylim"] if per_mode["ylim"] else (extent[2], extent[3])
    for ax, arr, cmap_name, kind, shared_lo, shared_hi in (
        (ax_destroy, mass_destroy, _OT_MASS_DESTROY_CMAP, "destroy",
         shared_destroy_vmin, shared_destroy_vmax),
        (ax_create, mass_create, _OT_MASS_CREATE_CMAP, "create",
         shared_create_vmin, shared_create_vmax),
    ):
        if arr is None or float(arr.sum()) == 0.0:
            ax.text(0.5, 0.5, f"mass {kind}\n(no mass change)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        try:
            # Q28: copy + set_bad("white") so NaN-masked cells render
            # as the white panel background rather than the cmap's
            # near-white low end.
            cmap = plt.get_cmap(cmap_name).copy()
            cmap.set_bad("white")
        except ValueError:
            cmap = plt.get_cmap("viridis").copy()
            cmap.set_bad("white")
        # Q29 Addendum #27: floor = bucket_vmax × mass_floor_fraction.
        # Falls back to per-panel arr.max()-based floor when bucket vmax
        # is missing (e.g., standalone smoke without Pass-1).
        if shared_hi is not None and shared_hi > 0:
            floor = float(shared_hi) * float(mass_floor_fraction)
        else:
            arr_max = float(arr.max()) if arr.size else 0.0
            floor = arr_max * float(mass_floor_fraction) if arr_max > 0 else 0.0
        # Q28+Q29: mask sub-floor (incl. zero) bins → NaN → white bg.
        arr_masked = np.where(
            arr >= floor, arr.astype(float), np.nan,
        ) if floor > 0 else np.where(
            arr > 0, arr.astype(float), np.nan,
        )
        imshow_kwargs: dict[str, Any] = {}
        if shared_hi is not None and shared_hi > 0:
            # Q29: cbar vmin = floor (not bucket smallest-positive) so the
            # color scale only covers the above-floor magnitude range.
            imshow_kwargs["vmin"] = floor if floor > 0 else (
                float(shared_lo) if (shared_lo is not None and shared_lo > 0) else 0.0
            )
            imshow_kwargs["vmax"] = float(shared_hi)
        # Q22 Addendum #21: white facecolor so the NaN-masked white
        # cells from Q28/Q29 blend in (axes facecolor defaults to
        # white but explicit is safer).
        ax.set_facecolor("white")
        ax.imshow(
            arr_masked.T, origin="lower", extent=extent,
            cmap=cmap, aspect="auto", **imshow_kwargs,
        )
        ax.set_xlim(xl)
        ax.set_ylim(yl[1], yl[0])  # inverted Y
        # Q22 Addendum #21: uniform tick + axis-label polish.
        _apply_q22_panel_polish(ax)
        ax.set_title(
            f"bin {bin_label} | mass_{kind}",
            fontsize=_Q22_PANEL_TITLE_FONTSIZE,
        )
        # Q24 Addendum #24: per-panel colorbars dropped. ONE shared
        # colorbar per mass type (destroy / create) attached at the
        # figure level by `render_unbalanced_ot_displacement_field`.
        # Mappable recovered via `ax.images[0]` post-hoc.


def _render_ot_arrows_panel(
    ax: plt.Axes,
    plan: dict[str, Any] | None,
    extent: list[float] | None,
    bodypart: str,
    center_mode: str,
    *,
    spatial_config: dict[str, Any],
    title: str,
    shared_arrow_logmag_lo: float | None = None,
    shared_arrow_logmag_hi: float | None = None,
    arrow_size_factor: float = 1.0,
    threshold_pct50_multiplier: float = 0.1,
) -> None:
    """Render the UNBALANCED-OT displacement-field arrows on one Axes per
    legacy lines 6443-6565: threshold by 50th-pct × ``threshold_pct50_multiplier``
    of mass + mag, log10-scaled linewidth + head + alpha + color,
    ``YlGnBu`` cmap. Head dimensions scale with histogram dx/dy (legacy
    lines 6175-6178).

    Q18 Addendum #17: ``shared_arrow_logmag_lo/hi`` (when both given)
    pin the log10-mass normalization bounds — drives arrow linewidth /
    head dimensions / alpha / color uniformly across all bins × tg in
    the UOT bucket. When None, fall back to per-panel 1st/99th percentile.

    Q21 Addendum #20:
      - ``arrow_size_factor``: scalar multiplier on the legacy-default
        ``head_w_vals``, ``head_l_vals``, ``lw_vals`` arrays. Driver
        passes the value from
        ``defaults['dlc_spatial_tone_aligned']['unbalanced_ot']['arrow_size_factor']``
        (default 0.5 per Priya 2026-05-15). Alpha is unchanged.
      - ``threshold_pct50_multiplier``: multiplier on the 50th-percentile
        of mass + mag for the rendering threshold. Default 0.1 matches
        legacy; tune to 0.25 to suppress more low-magnitude arrows.
    """
    if plan is None or extent is None:
        ax.text(0.5, 0.5, f"{title}\n(no OT data)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    Xg = plan["Xg"]
    Yg = plan["Yg"]
    Ux = plan["Ux"]
    Uy = plan["Uy"]
    mag = plan["mag"]
    mass_grid = plan["mass_grid"]
    dx_cell = plan["dx"]
    dy_cell = plan["dy"]

    if not np.any(mag > 0):
        ax.text(0.5, 0.5, f"{title}\n(no displacement)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return

    mass_pos = mass_grid[mass_grid > 0]
    mag_pos = mag[mag > 0]
    thr_mult = float(threshold_pct50_multiplier)
    mass_thr = float(np.percentile(mass_pos, 50) * thr_mult) if mass_pos.size > 0 else 0.0
    mag_thr = float(np.percentile(mag_pos, 50) * thr_mult) if mag_pos.size > 0 else 0.0
    mask = (mass_grid > mass_thr) & (mag > mag_thr)
    if not np.any(mask):
        ax.text(0.5, 0.5, f"{title}\n(below threshold)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return

    X_plot = Xg[mask]
    Y_plot = Yg[mask]
    U_plot = Ux[mask]
    V_plot = Uy[mask]
    M_plot = mass_grid[mask]

    pos_mass = M_plot[M_plot > 0]
    if pos_mass.size == 0:
        ax.text(0.5, 0.5, f"{title}\n(no positive mass)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    eps_mass = float(np.percentile(pos_mass, 1) * 0.1)
    logM = np.log10(M_plot + eps_mass)
    # Q18 Addendum #17: bucket-shared logmag range when given, else
    # per-panel 1st/99th percentile (legacy / Q14 per-SVG scope).
    if (
        shared_arrow_logmag_lo is not None
        and shared_arrow_logmag_hi is not None
        and shared_arrow_logmag_hi > shared_arrow_logmag_lo
    ):
        lo_m = float(shared_arrow_logmag_lo)
        hi_m = float(shared_arrow_logmag_hi)
    else:
        lo_m = float(np.percentile(logM, 1))
        hi_m = float(np.percentile(logM, 99))
        if hi_m <= lo_m:
            hi_m = lo_m + 1e-6
    frac_m = np.clip((logM - lo_m) / (hi_m - lo_m), 0.0, 1.0)
    lw_vals = _ARROW_LW_MIN + frac_m * (_ARROW_LW_MAX - _ARROW_LW_MIN)
    # Head dimensions scale with histogram cell width/height per legacy.
    head_w_min = _ARROW_HEAD_W_MIN_FRAC_DX * dx_cell
    head_w_max = _ARROW_HEAD_W_MAX_FRAC_DX * dx_cell
    head_l_min = _ARROW_HEAD_L_MIN_FRAC_DY * dy_cell
    head_l_max = _ARROW_HEAD_L_MAX_FRAC_DY * dy_cell
    head_w_vals = head_w_min + frac_m * (head_w_max - head_w_min)
    head_l_vals = head_l_min + frac_m * (head_l_max - head_l_min)
    alphas = _ARROW_ALPHA_MIN + frac_m * (_ARROW_ALPHA_MAX - _ARROW_ALPHA_MIN)

    # Q21 Addendum #20: scale head_w/head_l/lw uniformly by
    # arrow_size_factor (default 0.5 from config; alpha unchanged).
    size_factor = float(arrow_size_factor)
    if size_factor != 1.0:
        head_w_vals = head_w_vals * size_factor
        head_l_vals = head_l_vals * size_factor
        lw_vals = lw_vals * size_factor

    cmap = plt.get_cmap(_OT_ARROW_CMAP)
    norm = mcolors.Normalize(vmin=lo_m, vmax=hi_m)
    for x, y, u, v, lm, lw, hw, hl, al in zip(
        X_plot, Y_plot, U_plot, V_plot, logM, lw_vals, head_w_vals, head_l_vals, alphas,
        strict=False,
    ):
        ax.arrow(
            float(x), float(y), float(u), float(v),
            length_includes_head=True,
            head_width=float(hw),
            head_length=float(hl),
            linewidth=float(lw),
            color=cmap(norm(float(lm))),
            alpha=float(al),
        )

    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    if per_mode["xlim"]:
        ax.set_xlim(per_mode["xlim"])
    else:
        ax.set_xlim(extent[0], extent[1])
    if per_mode["ylim"]:
        ylim_lo, ylim_hi = per_mode["ylim"]
        ax.set_ylim(ylim_hi, ylim_lo)  # inverted Y per legacy line 6539
    else:
        ax.set_ylim(extent[3], extent[2])
    # Q22 Addendum #21: uniform tick + axis-label polish.
    _apply_q22_panel_polish(ax)
    ax.set_title(title, fontsize=_Q22_PANEL_TITLE_FONTSIZE)


def _aggregate_for_dates_pooled_bodyparts(
    animal: str,
    dates: list[dt.date],
    bodyparts: list[str],
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
    trial_group: str = "all",
    nbins_override: int | None = None,
) -> tuple[np.ndarray | None, list[float] | None, int, int]:
    """Sum N per-bp histograms cell-wise (pseudo-pooling) for any
    composite family.

    Returns ``(H_sum, extent, n_sessions, n_total_frames_summed)``. The
    pooling approximates the legacy "Pool all six whiskers as one part"
    pattern (line 2174 of 20251202_..._pixelbin.ipynb cited by
    Addendum #10). The per-bp histograms share the same extent because
    we use the first bp's per_center_mode block as the shared axis
    range. Generalized in Phase 7c.2 Addendum #13 to also serve the
    fiducial bilateral-pair composite families.

    ``n_total_frames_summed`` (Phase 7c.2 Addendum #16 Q17): summed
    in-window frame counts across all (bp, session) tuples that
    contributed to H_sum. Used as the Q17 proportion denominator
    downstream (H_sum / n_total_frames_summed).

    ``trial_group`` (Phase 7c.2 Addendum #15 Q16) selects the
    tone-aligned trial-group filter; ignored when ``scope='whole_session'``
    (where trial_group always collapses to None / all-frames). Default
    'all' preserves the pre-Q16 behavior for PD/UOT callers that have
    not yet been updated.

    ``nbins_override`` (Phase 7c.2 Addendum #15 Q15) forwards a coarser
    histogram resolution down to each per-bp aggregation call. Used by
    the UOT renderer to keep arrow count tractable.
    """
    if scope == "tone_aligned":
        tg_arg: str | None = trial_group
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        tg_arg = None
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    H_total: np.ndarray | None = None
    extent: list[float] | None = None
    n_sess_max = 0
    n_total_summed = 0
    for bp in bodyparts:
        H, ext, n_sess, _, n_total = compute_animal_aggregated_histogram(
            animal, dates, bp, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
            nbins_override=nbins_override,
        )
        if H is None:
            continue
        if H_total is None:
            H_total = H.copy()
            extent = list(ext) if ext is not None else None
        else:
            H_total += H
        n_sess_max = max(n_sess_max, n_sess)
        n_total_summed += int(n_total)
    return H_total, extent, n_sess_max, n_total_summed


def render_unbalanced_ot_displacement_field(
    animal: str,
    family_entry: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    dates: list[dt.date],
    bin_size_days: int | None = None,
    trial_group: str = "all",
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    shared_mass_destroy_vmin: float | None = None,
    shared_mass_destroy_vmax: float | None = None,
    shared_mass_create_vmin: float | None = None,
    shared_mass_create_vmax: float | None = None,
    shared_arrow_logmag_lo: float | None = None,
    shared_arrow_logmag_hi: float | None = None,
) -> plt.Figure:
    """Render the UNBALANCED-OT per-bin grid summary SVG per Addendum #14
    Q3d.B (mirrors proportion_differences per-bin pattern from
    Addendum #11 Q2.B) + Addendum #15 Q15/Q16.

    Algorithm:
      1. ``H_pre_pool`` = animal-level pre-stroke baseline (pooled
         rel_day <= 0 sessions, same trial_group filter), proportion-
         normalized.
      2. Group ALL dates (pre + post) by rel_day_bin at ``bin_size_days``.
         Both pre-stroke bins (within-pre variability) and post-stroke
         bins (stroke-induced departure) get UOT panels per Q2.B
         framing carried into UOT.
      3. For each bin: ``H_bin`` aggregated (per trial_group) →
         unbalanced sinkhorn vs ``H_pre_pool`` → 3 panels (mass_destroy +
         mass_create + arrows).
      4. Grid layout: N rows × 3 cols (N = number of bins; chronological
         pre→post).

    ``trial_group`` (Phase 7c.2 Addendum #15 Q16): per-trial-group fanout
    for tone_aligned scope. Driver emits 3 SVGs per (animal, family,
    bin_size). For whole_session, only 'all' is meaningful.

    Histogram resolution (Phase 7c.2 Addendum #15 Q15): read from
    ``defaults['dlc_spatial_tone_aligned']['unbalanced_ot']['nbins']``
    (default 50, pinned from legacy notebook line 6434). Coarser than the
    heatmap default (80×80) so the arrow rendering stays readable.

    Output filename: ``unbalanced_ot_grid_bin{N}d_{trial_group}.svg`` per
    Addendum #15 Q16 path convention; one SVG per (animal, family, scope,
    bin_size, trial_group).

    Single-bp families: single-bp OT.
    Composite families (whiskers + fiducial bilateral pairs, any family
    with > 1 bp): pooled N-bp pseudo-bp (legacy "Pool all six whiskers
    as one part" at line 2174 of legacy notebook, generalized in
    Addendum #13).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    if bin_size_days is None:
        raise ValueError(
            "render_unbalanced_ot_displacement_field requires explicit "
            "bin_size_days kwarg per Addendum #14 Q3d.B (per-bin grid "
            "summary). Driver passes it."
        )

    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    unb_cfg = tone_config.get("unbalanced_ot") or {}
    unb_nbins = int(unb_cfg.get("nbins") or 20)  # Q21 re-lock (Addendum #23): default 20
    arrow_size_factor = float(unb_cfg.get("arrow_size_factor", 0.5))
    threshold_pct50_multiplier = float(unb_cfg.get("threshold_pct50_multiplier", 0.1))
    # Q29 Addendum #27: mass-panel magnitude floor (5% of bucket vmax by default).
    mass_floor_fraction = float(unb_cfg.get("mass_floor_fraction", 0.05))

    pre_dates, _post_dates = _split_pre_post_dates(dates, animal_info)
    if not pre_dates:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(
            0.5, 0.5,
            f"{animal}/{family_entry}/{scope}/bin{bin_size_days}d/tg={trial_group}\n"
            "UOT skipped (no pre-stroke sessions)",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    # Compute fixed reference: animal-level pre-stroke pool, Q17-normalized
    # via total-frame denominator. Apply same trial_group filter so the
    # per-bin comparison is apples-to-apples.
    tg_arg = trial_group if scope == "tone_aligned" else None
    window_ms = TASK5_TONE_WINDOW_MS if scope == "tone_aligned" else None
    if len(bodyparts) == 1:
        bp_for_axis = bodyparts[0]
        H_pre_pool, ext_pre, n_pre_sess, _, n_total_pre = (
            compute_animal_aggregated_histogram(
                animal, pre_dates, bp_for_axis, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
                nbins_override=unb_nbins,
            )
        )
    else:
        bp_for_axis = bodyparts[0]
        H_pre_pool, ext_pre, n_pre_sess, n_total_pre = (
            _aggregate_for_dates_pooled_bodyparts(
                animal, pre_dates, bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
                trial_group=trial_group, nbins_override=unb_nbins,
            )
        )

    if H_pre_pool is None or n_total_pre == 0:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(
            0.5, 0.5,
            f"{animal}/{family_entry}/{scope}/bin{bin_size_days}d/tg={trial_group}\n"
            f"UOT skipped (empty pre-stroke pool, n_pre={len(pre_dates)})",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    # Q17 Addendum #16: total-frame denominator.
    H_pre_pool_prop = H_pre_pool / float(n_total_pre)

    # Group ALL dates by rel_day_bin at the requested bin_size_days.
    from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
    bins: dict[str, list[dt.date]] = {}
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=animal_info.stroke_date, bin_days=int(bin_size_days),
        )
        bins.setdefault(label, []).append(d)
    bin_labels = sorted(bins.keys(), key=_bin_label_sort_key)

    # Grid: N rows × 3 cols (mass_destroy + mass_create + arrows per bin).
    n_bins = len(bin_labels)
    nrows = max(1, n_bins)
    ncols = 3
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 5.0, nrows * 3.8),
        constrained_layout=True,
    )
    # Normalize axes layout to 2D (nrows, 3).
    if nrows == 1:
        axes = np.array(axes_obj).reshape(1, ncols)
    else:
        axes = axes_obj

    for row_idx, bin_label in enumerate(bin_labels):
        bin_dates = bins[bin_label]
        if len(bodyparts) == 1:
            H_bin, ext_b, n_sess, _, n_total_bin = (
                compute_animal_aggregated_histogram(
                    animal, bin_dates, bp_for_axis, center_mode, resolver,
                    trial_group=tg_arg, window_ms=window_ms,
                    defaults=defaults, animal_info=animal_info,
                    nbins_override=unb_nbins,
                )
            )
        else:
            H_bin, ext_b, n_sess, n_total_bin = (
                _aggregate_for_dates_pooled_bodyparts(
                    animal, bin_dates, bodyparts, center_mode, scope, resolver,
                    defaults=defaults, animal_info=animal_info,
                    trial_group=trial_group, nbins_override=unb_nbins,
                )
            )
        ax_destroy = axes[row_idx, 0]
        ax_create = axes[row_idx, 1]
        ax_arrows = axes[row_idx, 2]
        if H_bin is None or n_total_bin == 0:
            for ax in (ax_destroy, ax_create, ax_arrows):
                ax.text(0.5, 0.5, f"bin {bin_label}\n(no data)",
                        ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
            continue
        ext = ext_pre or ext_b
        # Q17 Addendum #16: total-frame denominator (not H_bin.sum()).
        H_bin_prop = H_bin / float(n_total_bin)
        plan = _compute_unbalanced_ot_plan(H_pre_pool_prop, H_bin_prop, ext)
        if plan is None:
            for ax in (ax_destroy, ax_create, ax_arrows):
                ax.text(0.5, 0.5, f"bin {bin_label}\n(OT solver failed)",
                        ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
            continue
        bin_n_sess_title = f"n_sess={n_sess}"
        _render_ot_mass_change_panels(
            ax_destroy, ax_create,
            plan["mass_destroy"], plan["mass_create"], ext,
            bp_for_axis, center_mode,
            spatial_config=spatial_config,
            bin_label=f"{bin_label} {bin_n_sess_title}",
            shared_destroy_vmin=shared_mass_destroy_vmin,
            shared_destroy_vmax=shared_mass_destroy_vmax,
            shared_create_vmin=shared_mass_create_vmin,
            shared_create_vmax=shared_mass_create_vmax,
            mass_floor_fraction=mass_floor_fraction,
        )
        _render_ot_arrows_panel(
            ax_arrows, plan, ext, bp_for_axis, center_mode,
            spatial_config=spatial_config,
            title=f"bin {bin_label} arrows {bin_n_sess_title}",
            shared_arrow_logmag_lo=shared_arrow_logmag_lo,
            shared_arrow_logmag_hi=shared_arrow_logmag_hi,
            arrow_size_factor=arrow_size_factor,
            threshold_pct50_multiplier=threshold_pct50_multiplier,
        )

    # Q24 Addendum #24: two shared colorbars (mass_destroy + mass_create)
    # at figure right, scoped to their respective grid columns. Arrows
    # column has no colorbar (it's a quiver-style plot; linewidth/head
    # already convey magnitude visually and the Q22 panel labels carry
    # the bin context).
    destroy_axes = list(axes[:, 0]) if axes.ndim == 2 else [axes[0]]
    create_axes = list(axes[:, 1]) if axes.ndim == 2 else [axes[1]]
    destroy_im = next((a.images[0] for a in destroy_axes if a.images), None)
    create_im = next((a.images[0] for a in create_axes if a.images), None)
    if destroy_im is not None:
        cbar_d = fig.colorbar(
            destroy_im, ax=destroy_axes, shrink=0.7, pad=0.02,
        )
        cbar_d.set_label("mass destroyed", fontsize=_Q22_AXIS_LABELSIZE)
        _apply_q22_colorbar_polish(cbar_d)
    if create_im is not None:
        cbar_c = fig.colorbar(
            create_im, ax=create_axes, shrink=0.7, pad=0.02,
        )
        cbar_c.set_label("mass created", fontsize=_Q22_AXIS_LABELSIZE)
        _apply_q22_colorbar_polish(cbar_c)
    # Q22 Addendum #21 title spec: animal | family | UOT | scope | trial_group.
    fig.suptitle(
        f"{animal} | {family_entry} | UOT bin{int(bin_size_days)}d "
        f"| {scope} | trial_group={trial_group}  "
        f"(n_pre_sess={n_pre_sess}, nbins={unb_nbins})",
        fontsize=_Q22_SUPTITLE_FONTSIZE,
    )
    return fig


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #17 Q18 — bucket-shared colormap precompute helpers.
#
# The cohort driver calls these in Pass 1 to derive bucket-shared
# (vmin, vmax) ranges, then re-invokes the per-SVG render_* functions
# in Pass 2 with the shared kwargs filled in. Each helper returns just
# the value arrays needed for range derivation — figures are NOT
# rendered (the driver re-issues the render_* calls).
#
# Memory budget: typical PS46 IS bucket = 21 dates × 3 tgs × 1 bp at
# 100×100 = ~5 MB / bucket. Trivial.
# ---------------------------------------------------------------------------


def precompute_individual_session_h_proportions(
    animal: str,
    family_entry: str,
    scope: Scope,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> list[np.ndarray]:
    """Collect H_proportion arrays across the IS bucket = (family, scope)
    for one animal. Iterates all (date × trial_group [× bp for composite])
    cells. Returns flat list of np.ndarray suitable for range derivation.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    arrays: list[np.ndarray] = []
    for date in dates:
        if len(bodyparts) > 1:
            panels = _compute_composite_panels(
                animal, [date], bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
            for _tg, per_tg in panels.items():
                for _bp, H, _ext, _n_sess, _n_tones, n_total in per_tg:
                    if H is None or n_total == 0:
                        continue
                    arrays.append(H / float(n_total))
        else:
            bp = bodyparts[0]
            panels = _compute_panels_for_session(
                animal, date, bp, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
            for _tg, payload in panels.items():
                H, _ext, _n_tones, n_total = payload
                if H is None or n_total == 0:
                    continue
                arrays.append(H / float(n_total))
    return arrays


def precompute_binned_sessions_h_proportions(
    animal: str,
    family_entry: str,
    scope: Scope,
    bin_size_days: int,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> list[np.ndarray]:
    """Collect H_proportion arrays across the BS bucket = (family, bin_size,
    scope). Iterates all (rel_day_bin × trial_group [× bp]) cells."""
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
    bins: dict[str, list[dt.date]] = {}
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=animal_info.stroke_date, bin_days=int(bin_size_days),
        )
        bins.setdefault(label, []).append(d)
    arrays: list[np.ndarray] = []
    for _label, bin_dates in bins.items():
        if len(bodyparts) > 1:
            panels = _compute_composite_panels(
                animal, bin_dates, bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
            for _tg, per_tg in panels.items():
                for _bp, H, _ext, _n_sess, _n_tones, n_total in per_tg:
                    if H is None or n_total == 0:
                        continue
                    arrays.append(H / float(n_total))
        else:
            bp = bodyparts[0]
            panels = _compute_panels_for_dates(
                animal, bin_dates, bp, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
            for _tg, payload in panels.items():
                H, _ext, _n_sess, _n_tones, n_total = payload
                if H is None or n_total == 0:
                    continue
                arrays.append(H / float(n_total))
    return arrays


def precompute_proportion_diffs(
    animal: str,
    family_entry: str,
    scope: Scope,
    bin_size_days: int,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> list[np.ndarray]:
    """Collect per-bin D = H_bin_prop - H_pre_pool_prop arrays across the
    PD bucket = (family, bin_size, scope). Iterates over (trial_group ×
    rel_day_bin). Used to derive bucket-shared symmetric vmax."""
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    pre_dates, _post_dates = _split_pre_post_dates(dates, animal_info)
    from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label

    arrays: list[np.ndarray] = []
    trial_groups = (
        TASK5_TRIAL_GROUPS_TONE_ALIGNED if scope == "tone_aligned"
        else TASK5_TRIAL_GROUPS_WHOLE_SESSION
    )
    for tg in trial_groups:
        # Compute pre-pool for this tg.
        if len(bodyparts) > 1:
            H_pre_pool, _ext_pre, _n_pre, n_total_pre = (
                _aggregate_for_dates_pooled_bodyparts(
                    animal, pre_dates, bodyparts, center_mode, scope, resolver,
                    defaults=defaults, animal_info=animal_info,
                    trial_group=tg,
                )
            )
        else:
            tg_arg = tg if scope == "tone_aligned" else None
            window_ms = TASK5_TONE_WINDOW_MS if scope == "tone_aligned" else None
            H_pre_pool, _ext_pre, _n_pre, _, n_total_pre = (
                compute_animal_aggregated_histogram(
                    animal, pre_dates, bodyparts[0], center_mode, resolver,
                    trial_group=tg_arg, window_ms=window_ms,
                    defaults=defaults, animal_info=animal_info,
                )
            )
        if H_pre_pool is None or n_total_pre == 0:
            continue
        H_pre_pool_prop = H_pre_pool / float(n_total_pre)
        # Iterate bins.
        bins: dict[str, list[dt.date]] = {}
        for d in dates:
            label = _compute_rel_day_bin_label(
                session_date=d, d0=animal_info.stroke_date,
                bin_days=int(bin_size_days),
            )
            bins.setdefault(label, []).append(d)
        for _label, bin_dates in bins.items():
            D, _ext, _n_sess = _compute_proportion_diff_for_bin(
                animal, bin_dates, H_pre_pool_prop, list(_ext_pre or []),
                bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
                trial_group=tg,
            )
            if D is None:
                continue
            arrays.append(D)
    return arrays


def precompute_unbalanced_ot_plans(
    animal: str,
    family_entry: str,
    scope: Scope,
    bin_size_days: int,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> list[dict[str, Any]]:
    """Collect UOT plan dicts across the UOT bucket = (family, bin_size,
    scope). Iterates (trial_group × rel_day_bin). Used to derive the
    bucket-shared mass_destroy_vmax / mass_create_vmax / arrow_logmag
    ranges in Pass 1."""
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    tone_config = defaults["dlc_spatial_tone_aligned"]
    unb_nbins = int(((tone_config.get("unbalanced_ot") or {}).get("nbins")) or 50)
    pre_dates, _post_dates = _split_pre_post_dates(dates, animal_info)
    from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label

    plans: list[dict[str, Any]] = []
    trial_groups = (
        TASK5_TRIAL_GROUPS_TONE_ALIGNED if scope == "tone_aligned"
        else TASK5_TRIAL_GROUPS_WHOLE_SESSION
    )
    for tg in trial_groups:
        tg_arg = tg if scope == "tone_aligned" else None
        window_ms = TASK5_TONE_WINDOW_MS if scope == "tone_aligned" else None
        # Pre-pool.
        if len(bodyparts) == 1:
            H_pre_pool, ext_pre, _n_pre, _, n_total_pre = (
                compute_animal_aggregated_histogram(
                    animal, pre_dates, bodyparts[0], center_mode, resolver,
                    trial_group=tg_arg, window_ms=window_ms,
                    defaults=defaults, animal_info=animal_info,
                    nbins_override=unb_nbins,
                )
            )
        else:
            H_pre_pool, ext_pre, _n_pre, n_total_pre = (
                _aggregate_for_dates_pooled_bodyparts(
                    animal, pre_dates, bodyparts, center_mode, scope, resolver,
                    defaults=defaults, animal_info=animal_info,
                    trial_group=tg, nbins_override=unb_nbins,
                )
            )
        if H_pre_pool is None or n_total_pre == 0:
            continue
        H_pre_pool_prop = H_pre_pool / float(n_total_pre)
        # Iterate bins.
        bins: dict[str, list[dt.date]] = {}
        for d in dates:
            label = _compute_rel_day_bin_label(
                session_date=d, d0=animal_info.stroke_date,
                bin_days=int(bin_size_days),
            )
            bins.setdefault(label, []).append(d)
        for _label, bin_dates in bins.items():
            if len(bodyparts) == 1:
                H_bin, ext_b, _n_sess, _, n_total_bin = (
                    compute_animal_aggregated_histogram(
                        animal, bin_dates, bodyparts[0], center_mode, resolver,
                        trial_group=tg_arg, window_ms=window_ms,
                        defaults=defaults, animal_info=animal_info,
                        nbins_override=unb_nbins,
                    )
                )
            else:
                H_bin, ext_b, _n_sess, n_total_bin = (
                    _aggregate_for_dates_pooled_bodyparts(
                        animal, bin_dates, bodyparts, center_mode, scope, resolver,
                        defaults=defaults, animal_info=animal_info,
                        trial_group=tg, nbins_override=unb_nbins,
                    )
                )
            if H_bin is None or n_total_bin == 0:
                continue
            ext = ext_pre or ext_b
            H_bin_prop = H_bin / float(n_total_bin)
            plan = _compute_unbalanced_ot_plan(H_pre_pool_prop, H_bin_prop, ext)
            if plan is not None:
                plans.append(plan)
    return plans


def derive_log_norm_range(arrays: list[np.ndarray]) -> tuple[float, float]:
    """Q18 (vmin, vmax) for LogNorm shared across a bucket. ``vmin`` =
    min of strictly-positive finite values; ``vmax`` = max."""
    vmin_candidates: list[float] = []
    vmax_candidates: list[float] = []
    for arr in arrays:
        if arr is None or arr.size == 0:
            continue
        finite_nonzero = arr[np.isfinite(arr) & (arr > 0)]
        if finite_nonzero.size == 0:
            continue
        vmin_candidates.append(float(finite_nonzero.min()))
        vmax_candidates.append(float(arr.max()))
    if not vmax_candidates:
        return 1e-10, 1e-9
    return min(vmin_candidates), max(vmax_candidates)


def derive_symmetric_diff_vmax(arrays: list[np.ndarray]) -> float:
    """Q18 symmetric vmax for PD bucket. ``vmax`` = max(|D|.max()) across
    arrays; per-panel renderer uses (vmin=-vmax, vmax=+vmax)."""
    maxes: list[float] = []
    for arr in arrays:
        if arr is None or arr.size == 0:
            continue
        finite_abs = np.abs(arr[np.isfinite(arr)])
        if finite_abs.size:
            maxes.append(float(finite_abs.max()))
    return max(maxes) if maxes else 1e-12


def derive_uot_bucket_ranges(
    plans: list[dict[str, Any]],
    *,
    threshold_pct50_multiplier: float = 0.1,
) -> tuple[float, float, float, float, float, float]:
    """Q18 UOT bucket-shared ranges: ``(mass_destroy_vmin,
    mass_destroy_vmax, mass_create_vmin, mass_create_vmax,
    arrow_logmag_lo, arrow_logmag_hi)``.

    Mass vmin = smallest strictly-positive mass across bucket (per Q28
    Addendum #26; zero values are NaN-masked at render time and don't
    contribute). vmax = max. Arrow logmag uses 1st/99th percentile of
    log10(mass_grid + eps) across plans (with the mass_thr + mag_thr
    mask applied per `_render_ot_arrows_panel`).

    Q21 Addendum #20: ``threshold_pct50_multiplier`` matches the same
    knob in `_render_ot_arrows_panel` — Pass-1 and Pass-2 must apply
    the same mask so the bucket-shared arrow logmag range corresponds
    to the arrows that actually render. Default 0.1 matches legacy.
    """
    destroy_vmaxes: list[float] = []
    destroy_vmins: list[float] = []
    create_vmaxes: list[float] = []
    create_vmins: list[float] = []
    all_logM: list[np.ndarray] = []
    thr_mult = float(threshold_pct50_multiplier)
    for plan in plans:
        md = plan.get("mass_destroy")
        if md is not None and float(md.sum()) > 0:
            destroy_vmaxes.append(float(np.max(md)))
            pos = md[md > 0]
            if pos.size:
                destroy_vmins.append(float(pos.min()))
        mc = plan.get("mass_create")
        if mc is not None and float(mc.sum()) > 0:
            create_vmaxes.append(float(np.max(mc)))
            pos = mc[mc > 0]
            if pos.size:
                create_vmins.append(float(pos.min()))
        # Arrow logmag bucket aggregation: mirror the _render_ot_arrows_panel
        # threshold logic to pick the same masked subset of arrows.
        mag = plan.get("mag")
        mass_grid = plan.get("mass_grid")
        if mag is None or mass_grid is None:
            continue
        if not np.any(mag > 0):
            continue
        mass_pos = mass_grid[mass_grid > 0]
        mag_pos = mag[mag > 0]
        if mass_pos.size == 0 or mag_pos.size == 0:
            continue
        mass_thr = float(np.percentile(mass_pos, 50) * thr_mult)
        mag_thr = float(np.percentile(mag_pos, 50) * thr_mult)
        mask = (mass_grid > mass_thr) & (mag > mag_thr)
        M_masked = mass_grid[mask]
        pos = M_masked[M_masked > 0]
        if pos.size == 0:
            continue
        eps = float(np.percentile(pos, 1) * 0.1)
        all_logM.append(np.log10(M_masked + eps))
    destroy_vmax = max(destroy_vmaxes) if destroy_vmaxes else 0.0
    create_vmax = max(create_vmaxes) if create_vmaxes else 0.0
    # Q28 Addendum #26: smallest-positive vmin so the cbar low end maps
    # to the smallest real value in the bucket, not 0 (which gets
    # NaN-masked at render time → white).
    destroy_vmin = min(destroy_vmins) if destroy_vmins else 0.0
    create_vmin = min(create_vmins) if create_vmins else 0.0
    if all_logM:
        flat_logM = np.concatenate(all_logM)
        logmag_lo = float(np.percentile(flat_logM, 1))
        logmag_hi = float(np.percentile(flat_logM, 99))
        if logmag_hi <= logmag_lo:
            logmag_hi = logmag_lo + 1e-6
    else:
        logmag_lo, logmag_hi = -10.0, -9.0
    return (
        destroy_vmin, destroy_vmax,
        create_vmin, create_vmax,
        logmag_lo, logmag_hi,
    )


__all__ = [
    "TASK5_TONE_WINDOW_MS",
    "TASK5_TRIAL_GROUPS_TONE_ALIGNED",
    "TASK5_TRIAL_GROUPS_WHOLE_SESSION",
    "compute_animal_aggregated_histogram",
    "derive_log_norm_range",
    "derive_symmetric_diff_vmax",
    "derive_uot_bucket_ranges",
    "precompute_binned_sessions_h_proportions",
    "precompute_individual_session_h_proportions",
    "precompute_proportion_diffs",
    "precompute_unbalanced_ot_plans",
    "render_animal_aggregated_heatmap",
    "render_binned_sessions_heatmap",
    "render_h_counts_panel",
    "render_individual_session_heatmap",
    "render_proportion_difference_heatmap",
    "render_tone_aligned_heatmap_session",
    "render_unbalanced_ot_displacement_field",
    "render_whole_session_heatmap",
]
