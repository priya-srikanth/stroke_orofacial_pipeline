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
) -> tuple[np.ndarray | None, list[float] | None, int, int]:
    """Compute-only variant of :func:`render_animal_aggregated_heatmap`.

    Returns ``(H_total, extent, n_sessions_contributing, n_total_tones)``
    so a caller can cache the histogram + render multiple SVG layouts
    (per-animal panel + cohort tile-grid subplot) from one compute pass.

    Returns ``(None, None, 0, 0)`` when no session contributes data
    (no parquets, no tone events for the trial_group, etc.).
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
        else:
            window = None

        hist = build_histogram(
            df, bodypart, config_for_hist,
            center_mode=center_mode,
            x_range=bp_x_range,
            nbins=nbins,
            window=window,
        )
        n_sessions_contributing += 1
        if H_total is None:
            H_total = hist["H_counts"].copy()
            extent = list(hist["extent"])
        else:
            H_total += hist["H_counts"]

    return H_total, extent, n_sessions_contributing, n_total_tones


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
) -> plt.Figure | plt.Axes:
    """Public render-only variant.

    When ``ax`` is None, returns a new Figure (single-panel layout). When
    ``ax`` is provided, renders into the existing Axes (subplot layout)
    and returns the Axes. Empty-data path (``H_counts is None``) renders
    a "no data" placeholder.
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

    total = float(H_counts.sum())
    H_prop = H_counts / total
    try:
        cmap = plt.get_cmap(cmap_name)
    except ValueError:
        cmap = plt.get_cmap("viridis")
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
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    ax.invert_yaxis()
    if standalone:
        ax.set_xlabel(f"{bodypart}_x (centered)")
        ax.set_ylabel(f"{bodypart}_y (centered)")
        ax.set_title(title)
    else:
        ax.set_title(title, fontsize=8)
        ax.tick_params(labelsize=6)

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
    H_total, extent, n_sessions, n_tones = compute_animal_aggregated_histogram(
        animal, dates, bodypart, center_mode, resolver,
        trial_group=trial_group, window_ms=window_ms,
        defaults=defaults, animal_info=animal_info,
    )
    if window_ms is not None:
        win_label = f"[{int(window_ms[0])}, {int(window_ms[1])}] ms"
        title = (
            f"{animal}  {bodypart}/{center_mode}  tg={trial_group}  "
            f"win={win_label}  n_sessions={n_sessions}  "
            f"n_tones={n_tones}"
        )
    else:
        title = (
            f"{animal}  {bodypart}/{center_mode}  WHOLE SESSION pooled  "
            f"n_sessions={n_sessions}"
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
) -> dict[str, tuple[np.ndarray | None, list[float] | None, int]]:
    """Compute per-trial-group histograms for a single (animal, date) cell.

    Returns ``{tg: (H_counts, extent, n_tones)}`` for every trial group in
    the scope-specific panel set. Missing-data panels (no tone events for
    a trial_group) map to ``(None, None, 0)``.
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    panels: dict[str, tuple[np.ndarray | None, list[float] | None, int]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        H, ext, _n_sess, n_tones = compute_animal_aggregated_histogram(
            animal, [date], bodypart, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
        panels[tg] = (H, ext, int(n_tones) if window_ms is not None else 0)
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
) -> dict[str, tuple[np.ndarray | None, list[float] | None, int, int]]:
    """Compute per-trial-group aggregated histograms for a date set
    (e.g., one rel_day_bin's sessions). Returns
    ``{tg: (H_counts, extent, n_sessions, n_tones)}``.
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
        H, ext, n_sess, n_tones = compute_animal_aggregated_histogram(
            animal, dates, bodypart, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
        panels[tg] = (H, ext, int(n_sess), int(n_tones) if window_ms is not None else 0)
    return panels


def _assemble_panel_figure(
    panels: dict[str, tuple],
    bodypart: str,
    center_mode: str,
    scope: Scope,
    suptitle: str,
    *,
    defaults: dict[str, Any],
) -> plt.Figure:
    """Render the per-trial-group panels as one Figure.

    Tone-aligned scope: 1×3 grid (all, L, R). Whole-session scope: 1×1.
    Each panel's title carries n_sessions / n_tones depending on the
    panel payload shape (3-tuple for single-session, 4-tuple for
    bin-aggregated).
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
        if len(payload) == 3:
            H, ext, n_tones = payload
            panel_title = (
                f"tg={tg} n_tones={n_tones}"
                if scope == "tone_aligned"
                else "whole session"
            )
        else:
            H, ext, n_sess, n_tones = payload
            if scope == "tone_aligned":
                panel_title = f"tg={tg} n_sess={n_sess} n_tones={n_tones}"
            else:
                panel_title = f"whole session n_sess={n_sess}"
        render_h_counts_panel(
            H, ext, bodypart, center_mode,
            title=panel_title, defaults=defaults, ax=ax,
        )
    fig.suptitle(suptitle, fontsize=12)
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
) -> plt.Figure:
    """Render the per-session heatmap figure for one (animal, family,
    date, scope) cell.

    Tone-aligned: 1×3 panel grid (all, L, R) using the
    (0, 8000) ms window. Whole-session: 1×1 panel (all only; no
    trial-group split).

    Raises ``NotImplementedError`` for ``whiskers_eye_midpoint`` until
    the legacy composite is ported (Addendum #9 Issue 2).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    if len(bodyparts) > 1:
        # Whiskers composite — pending Addendum #9 Issue 2 legacy port.
        raise NotImplementedError(
            f"family_entry={family_entry!r}: composite render (multi-bodypart "
            "family) pending legacy port per Phase 7c.2 Addendum #9 Issue 2."
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_session(
        animal, date, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
    )
    suptitle = (
        f"{animal}/{date.isoformat()}  {family_entry}  {scope}  "
        f"individual_session"
    )
    return _assemble_panel_figure(
        panels, bp, center_mode, scope, suptitle, defaults=defaults,
    )


def render_binned_sessions_heatmap(
    animal: str,
    family_entry: str,
    rel_day_bin_label: str,
    dates_in_bin: list[dt.date],
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure:
    """Render the per-(rel_day_bin) heatmap figure for one (animal,
    family, rel_day_bin, scope) cell.

    Aggregates frames across all ``dates_in_bin`` for the bin (single
    bin per call; cohort driver groups sessions by bin using
    ``_compute_rel_day_bin_label`` from ``_day_binned`` module).

    Panel layout same as :func:`render_individual_session_heatmap`.
    Raises ``NotImplementedError`` for ``whiskers_eye_midpoint``.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    if len(bodyparts) > 1:
        raise NotImplementedError(
            f"family_entry={family_entry!r}: composite render (multi-bodypart "
            "family) pending legacy port per Phase 7c.2 Addendum #9 Issue 2."
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_dates(
        animal, dates_in_bin, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
    )
    suptitle = (
        f"{animal}  {family_entry}  {scope}  binned_sessions  "
        f"rel_day_bin={rel_day_bin_label}  n_dates_in_bin={len(dates_in_bin)}"
    )
    return _assemble_panel_figure(
        panels, bp, center_mode, scope, suptitle, defaults=defaults,
    )


__all__ = [
    "TASK5_TONE_WINDOW_MS",
    "TASK5_TRIAL_GROUPS_TONE_ALIGNED",
    "TASK5_TRIAL_GROUPS_WHOLE_SESSION",
    "compute_animal_aggregated_histogram",
    "render_animal_aggregated_heatmap",
    "render_binned_sessions_heatmap",
    "render_h_counts_panel",
    "render_individual_session_heatmap",
    "render_tone_aligned_heatmap_session",
    "render_whole_session_heatmap",
]
