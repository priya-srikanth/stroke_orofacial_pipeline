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


# ---------------------------------------------------------------------------
# Whiskers composite (Addendum #10 Q1) — Pattern B layered overlay.
# Ports the legacy render at lines 676-738 of
# 20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb: sequential
# ``ax.hist2d`` over PART_DRAW_ORDER with cmap + alpha=0.8 + LogNorm +
# density=True, then per-part colorbars stacked vertically on the right.
# Our port works at the imshow level (since we already have H_counts
# arrays from compute_animal_aggregated_histogram) and renders the
# colormap key as a compact figure-right legend instead of 6 colorbars
# per panel (cleaner with the 3-panel trial-group layout).
# ---------------------------------------------------------------------------

# Per-whisker cmap dict from legacy lines 582-587 / 830-835 / 1394-1399 of
# 20251202_..._pixelbin.ipynb. L/R whiskers share cmap per index.
_WHISKER_CMAPS: dict[str, str] = {
    "L_whiskers_1": "plasma",
    "L_whiskers_2": "inferno",
    "L_whiskers_3": "viridis",
    "R_whiskers_1": "plasma",
    "R_whiskers_2": "inferno",
    "R_whiskers_3": "viridis",
}

_WHISKER_ALPHA: float = 0.5  # Slight softening vs legacy 0.8 for 6-way overlay readability.


def _compute_whiskers_panels(
    animal: str,
    dates: list[dt.date],
    bodyparts: list[str],
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int]]]:
    """Per-trial-group + per-whisker histogram compute.

    Returns ``{tg: [(bp, H_counts, extent, n_sessions, n_tones), ...]}`` —
    one entry per (trial_group, whisker_bp). For whole_session scope the
    only trial_group key is ``"all"`` and ``n_tones`` is 0.
    """
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int]]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        per_tg: list[tuple[str, np.ndarray | None, list[float] | None, int, int]] = []
        for bp in bodyparts:
            H, ext, n_sess, n_tones = compute_animal_aggregated_histogram(
                animal, dates, bp, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
            )
            per_tg.append((
                bp, H, ext, int(n_sess),
                int(n_tones) if window_ms is not None else 0,
            ))
        panels[tg] = per_tg
    return panels


def _render_whiskers_panel_axis(
    ax: plt.Axes,
    whisker_panels: list[tuple[str, np.ndarray | None, list[float] | None, int, int]],
    spatial_config: dict[str, Any],
    *,
    panel_title: str,
) -> None:
    """Render 6 sequential layered ``imshow`` plots on one axes — one per
    whisker, each with its own cmap + LogNorm + alpha. Mirrors the
    legacy ``ax.hist2d`` loop at lines 676-697 of 20251202_..._pixelbin.ipynb,
    adapted to consume precomputed ``H_counts`` arrays (vs hist2d which
    consumes raw xy).
    """
    extent_first: list[float] | None = None
    n_layered = 0
    for bp, H, ext, _n_sess, _n_tones in whisker_panels:
        if H is None or float(H.sum()) == 0.0:
            continue
        if extent_first is None:
            extent_first = ext
        H_prop = H / float(H.sum())
        finite_nonzero = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_nonzero.size == 0:
            continue
        vmin = float(finite_nonzero.min())
        vmax = float(H_prop.max())
        try:
            cmap = plt.get_cmap(_WHISKER_CMAPS.get(bp, "viridis"))
        except ValueError:
            cmap = plt.get_cmap("viridis")
        ax.imshow(
            H_prop.T,
            origin="lower",
            extent=ext,
            cmap=cmap,
            alpha=_WHISKER_ALPHA,
            aspect="auto",
            norm=mcolors.LogNorm(vmin=max(vmin, 1e-10), vmax=vmax),
        )
        n_layered += 1

    if extent_first is None:
        # No data for any whisker — placeholder.
        ax.text(
            0.5, 0.5, f"{panel_title}\n(no whisker data)",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return

    # All 6 whiskers share eye_midpoint center_mode + similar xlim/ylim;
    # use the first whisker's per_center_mode block as the panel axis
    # range. Empirically the 6 per_center_mode entries differ by ~10s of
    # px (each whisker pad has a slightly different baseline), but the
    # spread is contained — the union of all 6 xlim/ylim would be wider
    # than any single bp's range and lose detail. Sticking with the
    # first-bp range gives a usable shared scale; if needed we can
    # union later.
    per_mode = _get_per_center_mode_params(spatial_config, "L_whiskers_1", "eye_midpoint")
    if per_mode["xlim"]:
        ax.set_xlim(per_mode["xlim"])
    else:
        ax.set_xlim(extent_first[0], extent_first[1])
    if per_mode["ylim"]:
        ax.set_ylim(per_mode["ylim"])
    else:
        ax.set_ylim(extent_first[2], extent_first[3])
    ax.invert_yaxis()
    ax.set_title(panel_title, fontsize=8)
    ax.tick_params(labelsize=6)


def _attach_whiskers_legend(fig: plt.Figure) -> None:
    """Add a compact figure-right legend listing the 6 whiskers + their
    colormap names. Cheaper than 6 colorbars per panel — clean
    identification of which color belongs to which whisker."""
    lines = [f"{bp} → {cmap}" for bp, cmap in _WHISKER_CMAPS.items()]
    fig.text(
        0.99, 0.5, "Whiskers (cmap key)\n\n" + "\n".join(lines),
        ha="right", va="center", fontsize=7,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8, "edgecolor": "0.7"},
    )


def _assemble_whiskers_figure(
    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int]]],
    scope: Scope,
    suptitle: str,
    *,
    defaults: dict[str, Any],
) -> plt.Figure:
    """Render the whiskers composite figure — 1×3 grid (tone_aligned) /
    1×1 (whole_session), each panel layering 6 whiskers via
    :func:`_render_whiskers_panel_axis`. Per-trial-group panel title
    includes session count + tone-event count when tone-aligned.
    """
    spatial_config = defaults["dlc_spatial"]
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
        whisker_panels = panels.get(tg, [])
        if not whisker_panels:
            ax.set_axis_off()
            continue
        # Summarize sessions + tones across whiskers (same values per whisker
        # within a tg, modulo missing data; use first non-empty for title).
        n_sess = 0
        n_tones = 0
        for _bp, H, _ext, ns, nt in whisker_panels:
            if H is not None and float(H.sum()) > 0:
                n_sess = max(n_sess, ns)
                n_tones = max(n_tones, nt)
        if scope == "tone_aligned":
            panel_title = f"tg={tg}  n_sess={n_sess}  n_tones={n_tones}"
        else:
            panel_title = f"whole session  n_sess={n_sess}"
        _render_whiskers_panel_axis(
            ax, whisker_panels, spatial_config, panel_title=panel_title,
        )
    _attach_whiskers_legend(fig)
    fig.suptitle(suptitle, fontsize=11)
    # Make room for the right-edge legend.
    fig.subplots_adjust(right=0.83)
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
    suptitle = (
        f"{animal}/{date.isoformat()}  {family_entry}  {scope}  "
        f"individual_session"
    )
    if len(bodyparts) > 1:
        # Whiskers composite — Addendum #10 Q1 Pattern B layered overlay.
        whisker_panels = _compute_whiskers_panels(
            animal, [date], bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        return _assemble_whiskers_figure(
            whisker_panels, scope, suptitle, defaults=defaults,
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_session(
        animal, date, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
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
    suptitle = (
        f"{animal}  {family_entry}  {scope}  binned_sessions  "
        f"rel_day_bin={rel_day_bin_label}  n_dates_in_bin={len(dates_in_bin)}"
    )
    if len(bodyparts) > 1:
        # Whiskers composite — Addendum #10 Q1 Pattern B layered overlay.
        whisker_panels = _compute_whiskers_panels(
            animal, dates_in_bin, bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        return _assemble_whiskers_figure(
            whisker_panels, scope, suptitle, defaults=defaults,
        )
    bp = bodyparts[0]

    panels = _compute_panels_for_dates(
        animal, dates_in_bin, bp, center_mode, scope, resolver,
        defaults=defaults, animal_info=animal_info,
    )
    return _assemble_panel_figure(
        panels, bp, center_mode, scope, suptitle, defaults=defaults,
    )


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #10 Q2 — proportion_differences plot type.
# Math per legacy 20260111_DLC_analysis_build-parquet_tongue.ipynb cells
# 2270-2360: D = H_post_prop - H_pre_prop. Divergent cmap with
# TwoSlopeNorm centered on 0. Animal-level baseline = pool of all
# pre-stroke sessions (rel_day <= 0).
# ---------------------------------------------------------------------------

# Divergent cmaps per legacy lines 1376-1381 of
# 20251202_..._pixelbin.ipynb. Used for whisker-composite proportion-diff.
_WHISKER_DIVERGENT_CMAPS: dict[str, str] = {
    "L_whiskers_1": "BrBG",
    "L_whiskers_2": "coolwarm",
    "L_whiskers_3": "bwr",
    "R_whiskers_1": "BrBG",
    "R_whiskers_2": "coolwarm",
    "R_whiskers_3": "bwr",
}

_PROPORTION_DIFF_DEFAULT_CMAP = "coolwarm"
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

    H_pre, ext_pre, n_pre, _ = compute_animal_aggregated_histogram(
        animal, pre_dates, bodypart, center_mode, resolver,
        trial_group=tg_arg, window_ms=window_ms,
        defaults=defaults, animal_info=animal_info,
    )
    H_post, ext_post, n_post, _ = compute_animal_aggregated_histogram(
        animal, post_dates, bodypart, center_mode, resolver,
        trial_group=tg_arg, window_ms=window_ms,
        defaults=defaults, animal_info=animal_info,
    )

    if H_pre is None or H_post is None:
        return None, None, n_pre, n_post
    pre_sum = float(H_pre.sum())
    post_sum = float(H_post.sum())
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
    cmap_name: str = _PROPORTION_DIFF_DEFAULT_CMAP,
    title: str = "",
) -> None:
    """Render one (bodypart, center_mode) proportion-diff D array onto an
    Axes. Uses ``TwoSlopeNorm(vcenter=0)`` with vmax = 99th-percentile of
    |D| (legacy convention). Diverging cmap default ``coolwarm``."""
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
    vmax = float(np.percentile(finite_abs, _PROPORTION_DIFF_VMAX_PERCENTILE))
    vmax = max(vmax, 1e-12)
    norm = mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    try:
        cmap = plt.get_cmap(cmap_name).with_extremes(bad="0.85")
    except (ValueError, AttributeError):
        cmap = plt.get_cmap("coolwarm")
    D_plot = np.ma.array(D, mask=~np.isfinite(D))
    im = ax.imshow(
        D_plot.T, origin="lower", extent=extent,
        cmap=cmap, aspect="auto", norm=norm,
    )
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    if per_mode["xlim"]:
        ax.set_xlim(per_mode["xlim"])
    if per_mode["ylim"]:
        ax.set_ylim(per_mode["ylim"])
    ax.invert_yaxis()
    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=6)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Δ proportion (post − pre)", fontsize=7)
    cbar.ax.tick_params(labelsize=6)


def render_proportion_difference_heatmap(
    animal: str,
    family_entry: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    dates: list[dt.date] | None = None,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure:
    """Render the per-(animal, family, scope) proportion-difference SVG.

    Math: ``D = H_post_prop - H_pre_prop`` where pre = all rel_day <= 0
    sessions pooled (animal-level baseline per Addendum #10 Q2a), post =
    all rel_day >= 1 sessions pooled. Both as proportion-normalized
    histograms. Divergent cmap centered on 0 (``TwoSlopeNorm``).

    Non-whiskers families: 1×1 panel.
    Whiskers family: 2×3 subplot grid with per-whisker divergent cmap
    (BrBG / coolwarm / bwr cycle per whisker index; legacy lines
    1376-1381 of 20251202_..._pixelbin.ipynb).

    ``dates`` is the YAML-filtered in-range date list. If None, the
    caller must provide it (driver always passes it).
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
    pre_dates, post_dates = _split_pre_post_dates(dates, animal_info)

    suptitle = (
        f"{animal}  {family_entry}  {scope}  proportion_differences  "
        f"post − pre  (n_pre={len(pre_dates)}, n_post={len(post_dates)})"
    )

    if len(bodyparts) == 1:
        bp = bodyparts[0]
        D, ext, n_pre, n_post = _compute_proportion_diff(
            animal, pre_dates, post_dates, bp, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
        title = f"{bp}/{center_mode}  n_pre_sess={n_pre} n_post_sess={n_post}"
        _render_proportion_diff_panel(
            ax, D, ext, bp, center_mode,
            spatial_config=spatial_config,
            cmap_name=_PROPORTION_DIFF_DEFAULT_CMAP,
            title=title,
        )
        fig.suptitle(suptitle, fontsize=11)
        return fig

    # Whiskers composite — 2×3 grid, per-whisker divergent cmap.
    nrows, ncols = 2, 3
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 5.0, nrows * 4.0),
        constrained_layout=True,
    )
    axes = list(axes_obj.flat)
    for bp, ax in zip(bodyparts, axes, strict=False):
        D, ext, n_pre, n_post = _compute_proportion_diff(
            animal, pre_dates, post_dates, bp, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        cmap_name = _WHISKER_DIVERGENT_CMAPS.get(bp, _PROPORTION_DIFF_DEFAULT_CMAP)
        title = f"{bp}  n_pre_sess={n_pre} n_post_sess={n_post}"
        _render_proportion_diff_panel(
            ax, D, ext, bp, center_mode,
            spatial_config=spatial_config,
            cmap_name=cmap_name, title=title,
        )
    # Hide any trailing axes if bodyparts < 6.
    for ax in axes[len(bodyparts):]:
        ax.set_axis_off()
    fig.suptitle(suptitle, fontsize=12)
    return fig


# ---------------------------------------------------------------------------
# Phase 7c.2 Addendum #10 Q3 — unbalanced_ot plot type (per Q3a Read X
# outcome: balanced sinkhorn from 20251202_..._pixelbin.ipynb line 6937+
# is the displacement-field source. "unbalanced_ot" path-name preserved
# per Q12.B; semantics is balanced-OT displacement-field arrow plot).
# Math + arrow conventions ported verbatim from legacy lines 7340-7515.
# ---------------------------------------------------------------------------

# OT parameters per legacy line 7158 + arrow scale constants from the same
# cell (approximate; legacy defines them in an earlier sub-cell that uses
# session-pixel-size-dependent scaling — we use fixed defaults matching
# legacy "px-grid" magnitudes).
_OT_REG = 0.02
_OT_NUMITERMAX = 500
_OT_STOPTHR = 1e-6
_ARROW_LW_MIN = 0.4
_ARROW_LW_MAX = 2.5
_ARROW_HEAD_W_MIN = 3.0
_ARROW_HEAD_W_MAX = 10.0
_ARROW_HEAD_L_MIN = 4.0
_ARROW_HEAD_L_MAX = 14.0
_ARROW_ALPHA_MIN = 0.55
_ARROW_ALPHA_MAX = 0.95
_OT_ARROW_CMAP = "YlGnBu"


def _compute_displacement_field(
    H_pre: np.ndarray,
    H_sess: np.ndarray,
    extent: list[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """Compute the balanced-OT displacement field for one (pre, sess)
    histogram pair. Returns ``(Xg, Yg, Ux, Uy, move_grid, conditional_mass)``
    or ``None`` if degenerate (zero mass either side, or all-zero
    displacements). Mirrors legacy lines 7340-7404.
    """
    try:
        import ot  # POT
    except ImportError:
        return None

    nx, ny = H_pre.shape
    nxy = nx * ny

    a = H_pre.astype(float).ravel()
    b = H_sess.astype(float).ravel()
    sum_a = a.sum()
    sum_b = b.sum()
    if sum_a <= 0 or sum_b <= 0:
        return None
    a = a / sum_a
    b = b / sum_b

    dx = (extent[1] - extent[0]) / nx
    dy = (extent[3] - extent[2]) / ny
    xs = np.linspace(extent[0] + dx / 2, extent[1] - dx / 2, nx)
    ys = np.linspace(extent[2] + dy / 2, extent[3] - dy / 2, ny)
    Xg, Yg = np.meshgrid(xs, ys, indexing="ij")
    coords_xy = np.column_stack([Xg.ravel(), Yg.ravel()])

    C = ot.dist(coords_xy, coords_xy, metric="euclidean")
    C = C / max(C.max(), 1e-9)

    try:
        G = ot.sinkhorn(
            a, b, C,
            reg=_OT_REG,
            numItermax=_OT_NUMITERMAX,
            stopThr=_OT_STOPTHR,
            verbose=False,
        )
    except Exception:
        return None

    if G.shape != (nxy, nxy):
        return None

    out_from_pre = G.sum(axis=1)
    disp = np.zeros_like(coords_xy)
    nz = out_from_pre > 0
    if not np.any(nz):
        return None
    disp[nz] = (
        (G[nz] @ coords_xy - out_from_pre[nz, None] * coords_xy[nz])
        / out_from_pre[nz, None]
    )
    Ux = disp[:, 0].reshape(nx, ny)
    Uy = disp[:, 1].reshape(nx, ny)
    mag = np.hypot(Ux, Uy)
    if not np.any(mag > 0):
        return None
    mass_grid_base = out_from_pre.reshape(nx, ny)
    move_grid = mass_grid_base * mag
    return Xg, Yg, Ux, Uy, move_grid, mass_grid_base


def _render_ot_arrows_panel(
    ax: plt.Axes,
    payload: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None,
    extent: list[float] | None,
    bodypart: str,
    center_mode: str,
    *,
    spatial_config: dict[str, Any],
    title: str,
) -> None:
    """Render the balanced-OT displacement-field arrows on one Axes per
    legacy lines 7405-7503: threshold by 50th percentile × 0.1 of moved
    mass, log10-scale linewidth + head + alpha + color, ``YlGnBu`` cmap.
    """
    if payload is None or extent is None:
        ax.text(0.5, 0.5, f"{title}\n(no OT data)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    Xg, Yg, Ux, Uy, move_grid, _mass_base = payload

    move_pos = move_grid[move_grid > 0]
    if move_pos.size == 0:
        ax.text(0.5, 0.5, f"{title}\n(no movement)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    move_thr = float(np.percentile(move_pos, 50) * 0.1)
    mask = move_grid > move_thr
    if not np.any(mask):
        ax.text(0.5, 0.5, f"{title}\n(below threshold)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return

    X_plot = Xg[mask]
    Y_plot = Yg[mask]
    U_plot = Ux[mask]
    V_plot = Uy[mask]
    M_plot = move_grid[mask]

    pos_mass = M_plot[M_plot > 0]
    if pos_mass.size == 0:
        ax.text(0.5, 0.5, f"{title}\n(no positive mass)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    eps_mass = float(np.percentile(pos_mass, 1) * 0.1)
    logM = np.log10(M_plot + eps_mass)
    lo_m = float(np.percentile(logM, 1))
    hi_m = float(np.percentile(logM, 99))
    if hi_m <= lo_m:
        hi_m = lo_m + 1e-6
    frac_m = np.clip((logM - lo_m) / (hi_m - lo_m), 0.0, 1.0)
    lw_vals = _ARROW_LW_MIN + frac_m * (_ARROW_LW_MAX - _ARROW_LW_MIN)
    head_w_vals = _ARROW_HEAD_W_MIN + frac_m * (_ARROW_HEAD_W_MAX - _ARROW_HEAD_W_MIN)
    head_l_vals = _ARROW_HEAD_L_MIN + frac_m * (_ARROW_HEAD_L_MAX - _ARROW_HEAD_L_MIN)
    alphas = _ARROW_ALPHA_MIN + frac_m * (_ARROW_ALPHA_MAX - _ARROW_ALPHA_MIN)

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
        # Inverted Y to match heatmap convention (legacy line 7490).
        ylim_lo, ylim_hi = per_mode["ylim"]
        ax.set_ylim(ylim_hi, ylim_lo)
    else:
        ax.set_ylim(extent[3], extent[2])
    ax.set_title(title, fontsize=8)
    ax.tick_params(labelsize=6)


def _aggregate_for_dates_pooled_whiskers(
    animal: str,
    dates: list[dt.date],
    bodyparts: list[str],
    center_mode: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any],
    animal_info: AnimalInfo,
) -> tuple[np.ndarray | None, list[float] | None, int]:
    """Sum the 6-whisker per-bp histograms cell-wise (pseudo-pooling).

    Returns ``(H_sum, extent, n_sessions)``. The pooling approximates the
    legacy "Pool all six whiskers as one part" pattern (line 2174 of
    20251202_..._pixelbin.ipynb cited by Addendum #10). The per-whisker
    histograms share the same extent because we use the first whisker's
    per_center_mode block as the shared axis range. Per Q3a, we use
    balanced OT downstream.
    """
    if scope == "tone_aligned":
        tg_arg: str | None = "all"
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        tg_arg = None
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    H_total: np.ndarray | None = None
    extent: list[float] | None = None
    n_sess_max = 0
    for bp in bodyparts:
        H, ext, n_sess, _ = compute_animal_aggregated_histogram(
            animal, dates, bp, center_mode, resolver,
            trial_group=tg_arg, window_ms=window_ms,
            defaults=defaults, animal_info=animal_info,
        )
        if H is None:
            continue
        if H_total is None:
            H_total = H.copy()
            extent = list(ext) if ext is not None else None
        else:
            H_total += H
        n_sess_max = max(n_sess_max, n_sess)
    return H_total, extent, n_sess_max


def render_unbalanced_ot_displacement_field(
    animal: str,
    family_entry: str,
    scope: Scope,
    resolver: PathResolver,
    *,
    dates: list[dt.date],
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> plt.Figure:
    """Render the balanced-OT displacement-field grid-summary SVG per
    Addendum #10 Q3 / Q3a Read X outcome.

    Algorithm (legacy line 6937+):
      1. H_pre = animal-level pre-stroke baseline (pooled rel_day <= 0).
      2. For each rel_day_bin with at least one post-stroke session:
         a. H_sess = aggregated histogram across bin's sessions.
         b. ``G = ot.sinkhorn(H_pre_prop, H_sess_prop, C, reg=0.02)``.
         c. Compute displacement field + moved-mass thresholded arrows.
      3. Tile per-bin arrow panels into one grid-summary SVG.

    Per Q3d: per-rel_day_bin (NOT per-session) for compute tractability
    while preserving "multiple days per file" Q3c semantic. CC choice;
    Priya re-tunable.

    Non-whiskers families: single-bodypart OT.
    Whiskers family: pooled-6-whisker pseudo-bodypart (legacy "Pool all
    six whiskers as one part" pattern at line 2174 of legacy notebook).
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    spatial_config = defaults["dlc_spatial"]

    pre_dates, post_dates = _split_pre_post_dates(dates, animal_info)
    if not pre_dates or not post_dates:
        # Cannot compute OT — return placeholder figure.
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5,
                f"{animal}/{family_entry}/{scope}\n"
                f"OT skipped (n_pre={len(pre_dates)}, n_post={len(post_dates)})",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    # Group post-dates by rel_day_bin (matches Q3c grid-summary semantic).
    post_by_bin: dict[str, list[dt.date]] = {}
    for d in post_dates:
        from stroke_orofacial.dlc_kinematics._day_binned import _compute_rel_day_bin_label
        label = _compute_rel_day_bin_label(d, animal_info.stroke_date, animal_info.bin_days)
        post_by_bin.setdefault(label, []).append(d)
    bin_labels = sorted(post_by_bin.keys())

    # Compute baseline H_pre (single per family).
    if len(bodyparts) == 1:
        bp_for_axis = bodyparts[0]
        H_pre, ext_pre, n_pre_sess = compute_animal_aggregated_histogram(
            animal, pre_dates, bp_for_axis, center_mode, resolver,
            trial_group=("all" if scope == "tone_aligned" else None),
            window_ms=(TASK5_TONE_WINDOW_MS if scope == "tone_aligned" else None),
            defaults=defaults, animal_info=animal_info,
        )[:3]
    else:
        bp_for_axis = bodyparts[0]  # first whisker as shared-axis reference
        H_pre, ext_pre, n_pre_sess = _aggregate_for_dates_pooled_whiskers(
            animal, pre_dates, bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )

    if H_pre is None or float(H_pre.sum()) == 0.0:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5,
                f"{animal}/{family_entry}/{scope}\nOT skipped (empty pre)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig

    n_bins = len(bin_labels)
    ncols = min(4, max(1, n_bins))
    nrows = max(1, int(np.ceil(n_bins / ncols)))
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 5.5, nrows * 4.5),
        constrained_layout=True,
    )
    axes = list(axes_obj.flat) if hasattr(axes_obj, "flat") else [axes_obj]

    for bin_label, ax in zip(bin_labels, axes, strict=False):
        bin_dates = post_by_bin[bin_label]
        if len(bodyparts) == 1:
            H_sess, ext_s, n_sess = compute_animal_aggregated_histogram(
                animal, bin_dates, bodyparts[0], center_mode, resolver,
                trial_group=("all" if scope == "tone_aligned" else None),
                window_ms=(TASK5_TONE_WINDOW_MS if scope == "tone_aligned" else None),
                defaults=defaults, animal_info=animal_info,
            )[:3]
        else:
            H_sess, ext_s, n_sess = _aggregate_for_dates_pooled_whiskers(
                animal, bin_dates, bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
        if H_sess is None or float(H_sess.sum()) == 0.0:
            ax.text(0.5, 0.5, f"bin {bin_label}\n(no data)",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
        ext = ext_pre or ext_s
        payload = _compute_displacement_field(H_pre, H_sess, ext)
        title = f"bin {bin_label}  n_sess={n_sess}"
        _render_ot_arrows_panel(
            ax, payload, ext, bp_for_axis, center_mode,
            spatial_config=spatial_config, title=title,
        )
    # Hide trailing empty axes.
    for ax in axes[len(bin_labels):]:
        ax.set_axis_off()
    fig.suptitle(
        f"{animal}  {family_entry}  {scope}  unbalanced_ot displacement field "
        f"(pre-stroke baseline, n_pre_sess={n_pre_sess}; per rel_day_bin)",
        fontsize=11,
    )
    return fig


__all__ = [
    "TASK5_TONE_WINDOW_MS",
    "TASK5_TRIAL_GROUPS_TONE_ALIGNED",
    "TASK5_TRIAL_GROUPS_WHOLE_SESSION",
    "compute_animal_aggregated_histogram",
    "render_animal_aggregated_heatmap",
    "render_binned_sessions_heatmap",
    "render_h_counts_panel",
    "render_individual_session_heatmap",
    "render_proportion_difference_heatmap",
    "render_tone_aligned_heatmap_session",
    "render_unbalanced_ot_displacement_field",
    "render_whole_session_heatmap",
]
