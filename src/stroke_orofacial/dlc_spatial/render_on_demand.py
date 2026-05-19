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
import logging
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

logger = logging.getLogger(__name__)


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


def _ws_cam_frame_bounds(
    manifest: SessionManifest,
    resolver: PathResolver,
    n_cam_frames: int,
) -> tuple[int, int]:
    """Q19 Addendum #41 / Q49: derive ``[cam_lo, cam_hi]`` cam-frame
    bounds for the wavesurfer-covered session window from the Phase 3
    alignment template.

    Phase 4 centered parquets retain every DLC/camera frame — including
    pre-WS-start and post-WS-end frames — so the whole_session render
    scope must clamp to the cam-frame range that the wavesurfer
    recording actually covers. The alignment template's
    ``sig_camIdx__idx_ws`` is a LUT (length n_ws; index = WS sample,
    value = cam-frame the interp1d maps to); its finite min/max define
    the cam-frame coverage. Bounds are clamped to
    ``[0, n_cam_frames - 1]`` (the LUT can extrapolate negative or
    past-end cam-frame values for WS edges outside cam coverage).

    Falls back to ``(0, n_cam_frames - 1)`` (no-op filter) if the LUT
    has no finite entries (degenerate alignment) — caller logs the row
    counts so a malformed template surfaces in the per-animal summary.
    """
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
    lut = np.asarray(aln["sig_camIdx__idx_ws"], dtype=float)
    if n_cam_frames <= 0:
        return 0, 0
    finite = np.isfinite(lut)
    if not finite.any():
        return 0, n_cam_frames - 1
    valid = lut[finite]
    lo = int(np.clip(np.floor(valid.min()), 0, n_cam_frames - 1))
    hi = int(np.clip(np.ceil(valid.max()), 0, n_cam_frames - 1))
    if hi < lo:
        return 0, n_cam_frames - 1
    return lo, hi


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
    # Q19 Addendum #41 / Q49 (2026-05-17): WS-session-time cam-frame
    # filter for the whole_session scope; see ``_ws_cam_frame_bounds``.
    ws_lo, ws_hi = _ws_cam_frame_bounds(manifest, resolver, len(df))
    df = df.iloc[ws_lo : ws_hi + 1]

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
    # Q51 Addendum #43 (2026-05-18): session-drop audit. Track skips
    # so the cohort-driver log surfaces silent likelihood-filter drops
    # for downstream skip_audit.csv aggregation (Q51.C, Task 6).
    n_sessions_skipped = 0
    skipped_dates: list[dt.date] = []
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
            # Q19 Addendum #41 / Q49 (2026-05-17): restrict to WS-session-
            # time cam frames. The centered parquet retains every cam
            # frame including pre-WS-start and post-WS-end; whole_session
            # scope must clamp to the cam-frame range that the
            # wavesurfer recording actually covers per the Phase 3
            # alignment template. Both the H_counts histogram and the
            # Q17 universal proportion denominator now use the
            # WS-bounded df.
            ws_lo, ws_hi = _ws_cam_frame_bounds(manifest, resolver, len(df))
            df = df.iloc[ws_lo : ws_hi + 1]
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
        if hist is None:
            # No (bp, session) detections passed the likelihood +
            # x_range filter (e.g., PS50 L_eye on 2025-03-24, where all
            # in-window frames had likelihood < 0.8). Session still
            # contributes to the Q17 proportion denominator
            # ``n_total_frames_aggregated`` (Addendum #16: total in-
            # window frames, pre-likelihood filter); H_counts numerator
            # picks up zero counts from this session.
            n_sessions_skipped += 1
            skipped_dates.append(date)
            # Q51.A Addendum #43: per-skip WARNING for the cohort-driver
            # log → drives the Task 6 skip_audit.csv aggregation.
            logger.warning(
                "compute_animal_aggregated_histogram: skipping %s/%s "
                "(bodypart=%s, center_mode=%s, trial_group=%s): "
                "build_histogram returned None (zero frames passed "
                "likelihood threshold %.2f).",
                animal, date.isoformat(), bodypart, center_mode,
                str(trial_group) if trial_group is not None else "whole_session",
                lik_thr,
            )
            continue
        if H_total is None:
            H_total = hist["H_counts"].copy()
            extent = list(hist["extent"])
        else:
            H_total += hist["H_counts"]

    # Q51.B Addendum #43: per-(animal, bp, center_mode) session-drop
    # summary at end of aggregation. Emitted only when at least one
    # skip occurred (silent otherwise).
    if n_sessions_skipped > 0:
        logger.info(
            "compute_animal_aggregated_histogram: %s aggregation for "
            "(bp=%s, center_mode=%s, trial_group=%s) complete. "
            "Sessions: contributed=%d, skipped=%d, total=%d. "
            "Skipped sessions: %s",
            animal, bodypart, center_mode,
            str(trial_group) if trial_group is not None else "whole_session",
            n_sessions_contributing, n_sessions_skipped,
            n_sessions_contributing + n_sessions_skipped,
            [d.isoformat() for d in skipped_dates],
        )

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
_COMPOSITE_ALPHA: float = 1.0  # Q55.C Addendum #46: revert to alpha=1.0 (legacy Cell 11 was 0.8 — tune down to 0.8 in follow-on if multi-layer overlap pixels too dense; Q48's 0.5 was the speculation that drove washout chain).

# Q39 / Q47 / Q53 (Addenda #35, #45) — SUPERSEDED for Pattern B by Q55
# Addendum #46 (Priya 2026-05-19). The 6 categorical hex anchors below
# were a Phase-7c.2 speculation to make whiskers swatches L/R-distinct;
# they drove the iterative washout chain Q39 → Q47 → Q30 → Q48 → Q53.
# Q55 reverts Pattern B cmap selection to legacy: config-driven
# ``dlc_spatial.bodyparts.{bp}.cmap`` (plasma/inferno/viridis × L+R
# for whiskers per legacy Cell 11). The constant is retained ONLY as
# historical documentation; ``_resolve_layer_cmap`` no longer consults
# it.
_WHISKER_LAYER_COLORS: dict[str, str] = {
    "L_whiskers_1": "#d62728",
    "L_whiskers_2": "#ff7f0e",
    "L_whiskers_3": "#bcbd22",
    "R_whiskers_1": "#1f77b4",
    "R_whiskers_2": "#17becf",
    "R_whiskers_3": "#9467bd",
}


def _get_bodypart_cmap(spatial_config: dict[str, Any], bp: str) -> str:
    """Look up the per-bp cmap from ``dlc_spatial.bodyparts.{bp}.cmap``.
    Returns a fallback when missing (so callers stay robust against
    incomplete configs)."""
    cmap = (spatial_config.get("bodyparts", {}).get(bp, {}) or {}).get("cmap")
    return str(cmap) if cmap else _COMPOSITE_FALLBACK_CMAP


def _resolve_layer_cmap(spatial_config: dict[str, Any], bp: str):
    """Q55 Addendum #46 (2026-05-19): config-driven cmap lookup for
    Pattern B composite layers. Reverts Q39 / Q47 / Q53 dispatch chain;
    each bp's cmap comes verbatim from
    ``dlc_spatial.bodyparts.{bp}.cmap`` in defaults.yaml. Legacy Cell
    11 of ``20251202_..._pixelbin.ipynb`` is the design target:
    plasma/inferno/viridis for whiskers (L+R share by index),
    Reds_r/Blues_r for fiducial pairs (dark low-end after Q55.A
    revert), gist_ncar/gnuplot2/jet for nose/jaw/tongue.
    """
    name = _get_bodypart_cmap(spatial_config, bp)
    try:
        return plt.get_cmap(name)
    except ValueError:
        return plt.get_cmap(_COMPOSITE_FALLBACK_CMAP)


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

    # Q48 verdict (Addendum #43): Pattern B layered overlay uses
    # nbins=100 (config: dlc_spatial_tone_aligned.pattern_b_nbins),
    # reverting from default_nbins=80 to legacy + heatmap_nbins
    # convention. Applied as nbins_override here; Pattern A pooled +
    # single-bp callers in PD/UOT keep default_nbins=80 unchanged.
    tone_cfg = defaults.get("dlc_spatial_tone_aligned", {}) or {}
    pattern_b_nbins = int(tone_cfg.get("pattern_b_nbins", 100))
    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]]] = {}
    for tg in trial_groups:
        tg_arg = tg if window_ms is not None else None
        per_tg: list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]] = []
        for bp in bodyparts:
            H, ext, n_sess, n_tones, n_total = compute_animal_aggregated_histogram(
                animal, dates, bp, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
                nbins_override=pattern_b_nbins,
            )
            per_tg.append((
                bp, H, ext, int(n_sess),
                int(n_tones) if window_ms is not None else 0,
                int(n_total),
            ))
        panels[tg] = per_tg
    return panels


_PATTERN_B_LEGACY_VMIN: float = 1e-6
_PATTERN_B_VMAX_PERCENTILE: float = 99.0


def _derive_pattern_b_per_bp_norms(
    panels_flat: list[tuple[str, np.ndarray | None, Any, Any, Any, int]],
) -> dict[str, tuple[float, float]]:
    """Q48 verdict (Addendum #43): per-bp LogNorm bounds for Pattern B
    layered overlays. Legacy convention: ``vmin = 1e-6`` (matches Cell
    13 ``VMIN_LOG_PROP``); ``vmax = max-across-panels of np.percentile(
    H_prop[H_prop > 0], 99)`` per bp. The vmax-aggregation step gives
    panels within one SVG a SHARED-per-bp scale so stacked colorbars
    (n_bps<3) and visual comparability across trial groups are
    preserved; Q14 cross-SVG sharing is intentionally dropped per
    Q48 verdict item 3.

    ``panels_flat`` is a flat list of ``(bp, H_counts, extent, n_sess,
    n_tones, n_total_frames)`` tuples — caller flattens across whatever
    panel dimension applies (trial groups for IS/BS-per-bin,
    bin×trial-group for BS-grid).
    """
    per_bp_max_99: dict[str, float] = {}
    for bp, H, _ext, _n_sess, _n_tones, n_total in panels_flat:
        if H is None or n_total == 0:
            continue
        H_prop = H / float(n_total)
        finite_pos = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_pos.size == 0:
            continue
        pct = float(np.percentile(finite_pos, _PATTERN_B_VMAX_PERCENTILE))
        prev = per_bp_max_99.get(bp, 0.0)
        per_bp_max_99[bp] = max(prev, pct)
    floor = _PATTERN_B_LEGACY_VMIN * 10.0
    return {bp: (_PATTERN_B_LEGACY_VMIN, max(v, floor)) for bp, v in per_bp_max_99.items()}


def _render_composite_panel_axis(
    ax: plt.Axes,
    composite_panels: list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]],
    spatial_config: dict[str, Any],
    *,
    family_bodyparts: list[str],
    family_center_mode: str,
    panel_title: str,
    per_bp_norms: dict[str, tuple[float, float]] | None = None,
) -> None:
    """Render N sequential layered ``imshow`` plots on one axes — one per
    bodypart in the composite family, each with its own cmap + LogNorm +
    alpha. Mirrors the legacy ``ax.hist2d`` loop in Cell 11 of
    20251202_..._pixelbin.ipynb, adapted to consume precomputed
    ``H_counts`` arrays (vs hist2d which consumes raw xy).

    Q17 Addendum #16: H_proportion normalization uses ``n_total_frames``
    (per-bp total in-window frames) instead of ``H.sum()`` (legacy).

    Q55 Addendum #46 (2026-05-19) — Pattern B full legacy port. After
    iterating speculative fixes for whiskers washout (Q39 / Q47 / Q30 /
    Q48 / Q53), the convention reverts to the internally-consistent
    legacy Cell 11 baseline:
      - ``cmap.set_bad((1.0, 1.0, 1.0, 0.0))`` transparent NaN (Q48
        item 5 SUPERSEDED). LogNorm masks non-positive bins → those
        bins render fully transparent → layers don't compound against
        an opaque-white background.
      - ``alpha=_COMPOSITE_ALPHA=1.0`` (Q48 item 1 SUPERSEDED). With
        transparent NaN, multi-layer compositing no longer accumulates
        white pixels; alpha=1.0 maximizes saturation. Legacy Cell 11
        used 0.8; we start at 1.0 and tune down only if visual review
        shows multi-layer-overlap pixels too dense.
      - Cmaps come from ``dlc_spatial.bodyparts.{bp}.cmap`` verbatim
        (Q55.A) — plasma/inferno/viridis × L+R for whiskers; Reds_r /
        Blues_r for fiducial pairs (dark low-end so sparse bins
        remain visible after the cmap reverse); gist_ncar/gnuplot2/
        jet for nose/jaw/tongue. The Q47 white-to-categorical-hex
        construction is gone — see ``_resolve_layer_cmap``.
      - Q53 collapse REMOVED: whiskers render as 6 separate per-bp
        layers (one per L_whiskers_1..3 + R_whiskers_1..3), restoring
        the per-bp colorbar density resolution that the 2-side sum
        flattened away.

    Q52 (Addendum #44) RETAINED: ``per_bp_norms[bp] = (vmin, vmax)``
    is the bucket-shared per-bp LogNorm range (vmin=1e-6 /
    vmax=99th-pct of bucket-pooled positive H_proportion). Falls back
    to figure-local 99th-pct when missing.

    Floor mask DROPPED (Q32 / Q48 item 2, unchanged from Addendum #43).
    """
    ax.set_facecolor("white")
    extent_first: list[float] | None = None
    n_layered = 0
    for bp, H, ext, _n_sess, _n_tones, n_total in composite_panels:
        if H is None or n_total == 0:
            continue
        if extent_first is None:
            extent_first = ext
        H_prop = H / float(n_total)
        finite_pos = H_prop[np.isfinite(H_prop) & (H_prop > 0)]
        if finite_pos.size == 0:
            continue
        # Q52 (Addendum #44): per-bp LogNorm range. Prefer
        # bucket-aggregated norms; fall back to this panel's own
        # 99th-pct when missing for the bp.
        if per_bp_norms and bp in per_bp_norms:
            norm_vmin, norm_vmax = per_bp_norms[bp]
        else:
            norm_vmin = _PATTERN_B_LEGACY_VMIN
            norm_vmax = max(
                float(np.percentile(finite_pos, _PATTERN_B_VMAX_PERCENTILE)),
                _PATTERN_B_LEGACY_VMIN * 10.0,
            )
        cmap = _resolve_layer_cmap(spatial_config, bp).copy()
        # Q55.B Addendum #46: transparent NaN (revert Q48 item 5). With
        # LogNorm masking non-positive bins → rendered via set_bad →
        # transparent (matches legacy Cell 11 default; legacy did not
        # call set_bad explicitly because matplotlib sequential cmaps
        # default to transparent ``bad``).
        cmap.set_bad((1.0, 1.0, 1.0, 0.0))
        ax.imshow(
            H_prop.T,
            origin="lower",
            extent=ext,
            cmap=cmap,
            alpha=_COMPOSITE_ALPHA,
            aspect="auto",
            norm=mcolors.LogNorm(vmin=norm_vmin, vmax=norm_vmax),
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
    per_bp_norms: dict[str, tuple[float, float]] | None,
) -> None:
    """Pattern B composite legend / colorbar block on figure right.

    Q55.D Addendum #46 (2026-05-19): per-layer stacked vertical
    colorbars for ALL Pattern B families (revert Q30 swatch legend).
    Each layer's colorbar shows its own bucket-shared (1e-6, 99th-pct)
    LogNorm range. Matches the legacy Cell 11 convention from
    20251202_..._pixelbin.ipynb (which used horizontal cbars; we use
    vertical to fit within the Q31 right-edge band).

    Layout: each bp gets a thin vertical strip on the figure right;
    strips stack top-to-bottom in ``family_bodyparts`` order. Inter-
    strip spacing is tight so 6+ colorbars (whiskers) still fit
    without label overlap.

    Q52 (Addendum #44) RETAINED: ``per_bp_norms[bp] = (vmin, vmax)``
    is the bucket-shared scale; the colorbar reflects the same
    bucket-wide range that the layered imshow uses.
    """
    n_bps = len(family_bodyparts)
    if n_bps == 0:
        return
    if not per_bp_norms:
        return
    # Allocate stacked vertical axes at the figure right (one strip per
    # bp). Geometry tuned for n_bps up to ~9 within the
    # ``fig.subplots_adjust(right=0.85)`` reserved band.
    cbar_left = 0.88
    cbar_width = 0.012
    total_height = 0.72
    # Q55.D Addendum #46: tighter spacing than the Q31 (0.04) value so
    # 6 whiskers colorbars + label fit without overflow. Scales with
    # n_bps so wider families don't blow past the figure top edge.
    spacing = 0.012 if n_bps >= 4 else 0.025
    block_height = max(
        0.02,
        (total_height - spacing * (n_bps - 1)) / n_bps,
    )
    base_bottom = 0.5 - total_height / 2.0
    for i, bp in enumerate(family_bodyparts):
        norm_pair = per_bp_norms.get(bp)
        if norm_pair is None:
            continue
        vmin_bp, vmax_bp = norm_pair
        norm = mcolors.LogNorm(vmin=max(float(vmin_bp), 1e-10), vmax=float(vmax_bp))
        cmap = _resolve_layer_cmap(spatial_config, bp).copy()
        # Q55.B: same transparent-NaN convention as the layered render
        # path; the swatch in the colorbar is the cmap's positive
        # range only.
        cmap.set_bad((1.0, 1.0, 1.0, 0.0))
        # Top → bottom in family_bodyparts order.
        bottom = base_bottom + (n_bps - 1 - i) * (block_height + spacing)
        cax = fig.add_axes([cbar_left, bottom, cbar_width, block_height])
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(bp, fontsize=_Q22_AXIS_LABELSIZE - 3)
        cbar.ax.tick_params(labelsize=_Q22_TICK_LABELSIZE - 3)


def _aggregate_per_tg_norms(
    bucket_per_bp_norms_per_tg: dict[str, dict[str, tuple[float, float]]],
) -> dict[str, tuple[float, float]]:
    """Q52 colorbar-side reduction: collapse ``{tg: {bp: (vmin, vmax)}}``
    into a single ``{bp: (vmin, max-vmax-across-tg)}`` for the
    figure-level stacked colorbars (n_bps<3 path). The composite
    figure shows ONE colorbar per bp shared across all tg panels;
    using the max-vmax-across-tg gives a single conservative scale
    that no panel exceeds.
    """
    out: dict[str, tuple[float, float]] = {}
    for _tg, per_bp in bucket_per_bp_norms_per_tg.items():
        for bp, (vmin, vmax) in per_bp.items():
            prev = out.get(bp)
            if prev is None or vmax > prev[1]:
                out[bp] = (vmin, vmax)
    return out


def _assemble_composite_figure(
    panels: dict[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int]]],
    scope: Scope,
    suptitle: str,
    *,
    family_bodyparts: list[str],
    family_center_mode: str,
    family_label: str,
    defaults: dict[str, Any],
    bucket_per_bp_norms: dict[str, dict[str, tuple[float, float]]] | None = None,
) -> plt.Figure:
    """Render the multi-bp composite figure — 1×3 grid (tone_aligned) /
    1×1 (whole_session), each panel layering N bodyparts via
    :func:`_render_composite_panel_axis`. Per-trial-group panel title
    includes session count + tone-event count when tone-aligned.

    Q48 verdict (Addendum #43, 2026-05-18) → Q52 (Addendum #44):
    per-bp LogNorm bounds prefer the cohort-driver-supplied
    ``bucket_per_bp_norms`` (per-trial-group bucket-wide vmax across
    ALL SVGs in the (animal, family_entry, plot_type, scope,
    trial_group) bucket) when available. When ``bucket_per_bp_norms``
    is ``None`` (single-SVG-bucket cases like Q36 BS-grid, or
    standalone smoke without a driver Pass 1), falls back to
    figure-local aggregation via
    :func:`_derive_pattern_b_per_bp_norms` over the panels in this
    figure — semantically identical to bucket-shared when bucket =
    SVG.

    Q31 Addendum #28: figsize wider for the right-anchored swatch
    legend / stacked colorbar block; manual ``subplots_adjust`` reserves
    room (``constrained_layout=False``).
    """
    spatial_config = defaults["dlc_spatial"]
    if scope == "tone_aligned":
        trial_groups = TASK5_TRIAL_GROUPS_TONE_ALIGNED
        # Q31 Addendum #28: width 18 → 20 to accommodate the right-anchored
        # swatch legend / stacked cbar block.
        figsize = (20.0, 5.0)
    else:
        trial_groups = TASK5_TRIAL_GROUPS_WHOLE_SESSION
        figsize = (10.0, 6.0)

    # Q52 (Addendum #44): prefer driver-supplied bucket norms (per-tg);
    # fall back to figure-local Q48 aggregation when bucket = SVG.
    if bucket_per_bp_norms:
        per_tg_norms = bucket_per_bp_norms
        cbar_norms = _aggregate_per_tg_norms(per_tg_norms)
    else:
        panels_flat: list[tuple[str, np.ndarray | None, Any, Any, Any, int]] = []
        for tg in trial_groups:
            panels_flat.extend(panels.get(tg, []))
        figure_local = _derive_pattern_b_per_bp_norms(panels_flat)
        per_tg_norms = {tg: figure_local for tg in trial_groups}
        cbar_norms = figure_local

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
            per_bp_norms=per_tg_norms.get(tg, {}),
        )
    # Q24 / Q48 / Q52: stacked per-bp colorbars (n_bps<3) or swatch legend
    # (n_bps>=3). Colorbars use the per-tg-max aggregate so a single
    # scale per bp covers the worst-case panel without clipping.
    _attach_composite_colorbars(
        fig, family_bodyparts, spatial_config,
        family_label=family_label,
        per_bp_norms=cbar_norms,
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
    bucket_per_bp_norms: dict[str, dict[str, tuple[float, float]]] | None = None,
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
    bucket-shared LogNorm bounds into Pattern A single-cmap panels.

    Q52 Addendum #44 (2026-05-18): ``bucket_per_bp_norms`` carries the
    Pattern B IS-bucket per-(tg, bp) shared LogNorm bounds from the
    cohort driver's Pass 1 (so SVGs across all dates in the
    (animal, family_entry, IS, scope, trial_group) bucket render
    each layer against the same vmax for cross-SVG comparability).
    When None (standalone smoke or non-cohort callers), the composite
    renderer falls back to figure-local Q48 aggregation.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    # Q22 Addendum #21 title spec: animal | family | date | scope | plot_type.
    is_pattern_b = len(bodyparts) > 1
    scale_tag = " | scale: bucket-shared" if is_pattern_b else ""
    suptitle = (
        f"{animal} | {family_entry} | {date.isoformat()} | {scope} "
        f"| individual_session{scale_tag}"
    )
    if is_pattern_b:
        # Composite family — Pattern B layered overlay (Addenda #10/#13).
        # Q52 (Addendum #44): per-bp LogNorm bounds from the driver
        # Pass 1 bucket precompute when supplied; figure-local
        # aggregation otherwise.
        # Q55 Addendum #46 (2026-05-19): the Q53 L/R-side collapse for
        # whiskers is REVERTED — render 6 separate per-bp layers per
        # legacy Cell 11 of 20251202_..._pixelbin.ipynb.
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
            bucket_per_bp_norms=bucket_per_bp_norms,
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
    is_pattern_b = len(bodyparts) > 1
    scale_tag = " | scale: bucket-shared" if is_pattern_b else ""
    suptitle = (
        f"{animal} | {family_entry} | rel_day_bin={rel_day_bin_label} "
        f"| {scope} | binned_sessions{scale_tag}  "
        f"(n_dates_in_bin={len(dates_in_bin)})"
    )
    if is_pattern_b:
        # Composite family — Pattern B layered overlay (Addenda #10/#13).
        # Q52 (Addendum #44): per-bp norms come from figure-local
        # aggregation (this code path is BS-per-bin, not used by the
        # Phase 7c.2 cohort driver post-Q36; kept for backward-compat
        # smoke runners and ad-hoc callers).
        # Q55 Addendum #46: Q53 whiskers collapse REVERTED — 6 raw
        # per-bp layers per legacy Cell 11.
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


def render_binned_sessions_grid(
    animal: str,
    family_entry: str,
    scope: Scope,
    bin_size_days: int,
    trial_group: str,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    shared_vmin: float | None = None,
    shared_vmax: float | None = None,
) -> plt.Figure:
    """Q36 Addendum #34 (Priya 2026-05-17): render binned_sessions as ONE
    grid SVG combining all N_bins for the (animal, family, scope,
    bin_size, trial_group) bucket. Each subplot = one bin_label.
    Supersedes the prior per-bin-label SVG fanout (where each SVG had
    3 trial-group sub-panels for tone_aligned).

    New emit pattern:
      - tone_aligned: 3 SVGs per (animal, family, bin_size) — one per
        trial_group ∈ {all, L, R}. Each SVG has N_bins panels.
      - whole_session: 1 SVG (trial_group='all' only). N_bins panels.

    Parallel structure to proportion_differences + unbalanced_ot grids.
    Q14/Q18 bucket-shared colormap normalization + ONE shared colorbar.

    Single-bp families: each subplot is one bin's H_proportion heatmap.
    Composite families (whiskers, fiducial pairs): each subplot stacks
    N bp layers per the Pattern B convention; the per-bp swatch
    legend / stacked cbar block sits to the right of the entire grid.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    spatial_config = defaults["dlc_spatial"]

    # Group dates by rel_day_bin.
    from stroke_orofacial.dlc_kinematics._day_binned import (
        _compute_rel_day_bin_label,
    )
    bins: dict[str, list[dt.date]] = {}
    for d in dates:
        label = _compute_rel_day_bin_label(
            session_date=d, d0=animal_info.stroke_date, bin_days=int(bin_size_days),
        )
        bins.setdefault(label, []).append(d)
    bin_labels = sorted(bins.keys(), key=_bin_label_sort_key)
    n_bins = len(bin_labels)
    if n_bins == 0:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(
            0.5, 0.5,
            f"{animal}/{family_entry}/{scope}/bin{bin_size_days}d/{trial_group}\n"
            "binned_sessions grid: no bins",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        return fig

    # Q22 suptitle convention.
    # Q52 Addendum #44: tag Pattern B SVGs with "scale: bucket-shared"
    # (the BS-grid SVG IS its own bucket per (animal, family, scope,
    # bin_size, trial_group), so figure-local aggregation = bucket-
    # shared by construction).
    is_pattern_b = len(bodyparts) > 1
    scale_tag = " | scale: bucket-shared" if is_pattern_b else ""
    suptitle = (
        f"{animal} | {family_entry} | binned_sessions bin{int(bin_size_days)}d "
        f"| {scope} | trial_group={trial_group}{scale_tag}"
    )

    # Near-square grid: ceil(sqrt(N)) cols.
    ncols = max(1, int(np.ceil(np.sqrt(n_bins))))
    nrows = int(np.ceil(n_bins / ncols))

    # Window + tg_arg selection per scope.
    if scope == "tone_aligned":
        tg_arg: str | None = trial_group
        window_ms: tuple[float, float] | None = TASK5_TONE_WINDOW_MS
    elif scope == "whole_session":
        tg_arg = None
        window_ms = None
    else:
        raise ValueError(f"scope must be 'tone_aligned' or 'whole_session'; got {scope!r}")

    # Layout: composite families need room for the right-edge cbar/legend.
    if len(bodyparts) > 1:
        figsize = (ncols * 4.5 + 3.0, nrows * 4.0)
        fig, axes_obj = plt.subplots(
            nrows=nrows, ncols=ncols,
            figsize=figsize, constrained_layout=False,
            sharex=True, sharey=True,
        )
    else:
        figsize = (ncols * 4.0, nrows * 3.5)
        fig, axes_obj = plt.subplots(
            nrows=nrows, ncols=ncols,
            figsize=figsize, constrained_layout=True,
            sharex=True, sharey=True,
        )
    axes = (
        np.array([[axes_obj]]) if (nrows == 1 and ncols == 1)
        else np.atleast_2d(axes_obj)
    )
    axes_flat = axes.flatten()

    # Q48 verdict (Addendum #43): Pattern B uses figure-local per-bp
    # LogNorm bounds. Two-pass compute → derive per-bp norms across
    # ALL bins → render. Pattern A keeps the existing one-pass +
    # bucket-shared scale via shared_vmin/shared_vmax.
    # Q55 Addendum #46: Q53 whiskers collapse REVERTED — 6 raw per-bp
    # layers per legacy Cell 11.
    if len(bodyparts) > 1:
        composite_panels_per_bin: list[
            tuple[str, list[tuple[str, np.ndarray | None, list[float] | None, int, int, int]]]
        ] = []
        for bin_label in bin_labels:
            bin_dates = bins[bin_label]
            panels_all_tg = _compute_composite_panels(
                animal, bin_dates, bodyparts, center_mode, scope, resolver,
                defaults=defaults, animal_info=animal_info,
            )
            per_tg = panels_all_tg.get(tg_arg or "all", [])
            composite_panels_per_bin.append((bin_label, per_tg))
        # Aggregate per-bp norms across all bins in this figure.
        all_panels_flat: list[
            tuple[str, np.ndarray | None, Any, Any, Any, int]
        ] = []
        for _label, per_tg in composite_panels_per_bin:
            all_panels_flat.extend(per_tg)
        per_bp_norms = _derive_pattern_b_per_bp_norms(all_panels_flat)
        for i, (bin_label, per_tg) in enumerate(composite_panels_per_bin):
            ax = axes_flat[i]
            panel_title = f"bin {bin_label}  n_dates={len(bins[bin_label])}"
            _render_composite_panel_axis(
                ax, per_tg, spatial_config,
                family_bodyparts=bodyparts,
                family_center_mode=center_mode,
                panel_title=panel_title,
                per_bp_norms=per_bp_norms,
            )
    else:
        bp = bodyparts[0]
        for i, bin_label in enumerate(bin_labels):
            ax = axes_flat[i]
            bin_dates = bins[bin_label]
            panel_title = f"bin {bin_label}  n_dates={len(bin_dates)}"
            H, ext, n_sess, _, n_total = compute_animal_aggregated_histogram(
                animal, bin_dates, bp, center_mode, resolver,
                trial_group=tg_arg, window_ms=window_ms,
                defaults=defaults, animal_info=animal_info,
            )
            render_h_counts_panel(
                H, ext, bp, center_mode,
                title=panel_title, defaults=defaults, ax=ax,
                n_total_frames=int(n_total),
                shared_vmin=shared_vmin, shared_vmax=shared_vmax,
            )
    # Hide unused subplot slots.
    for j in range(n_bins, len(axes_flat)):
        axes_flat[j].set_axis_off()

    if len(bodyparts) > 1:
        # Composite — Q55.D stacked per-layer cbars on figure right.
        _attach_composite_colorbars(
            fig, bodyparts, spatial_config,
            family_label=family_entry,
            per_bp_norms=per_bp_norms,
        )
        # Q31 manual room reservation since constrained_layout was off.
        fig.subplots_adjust(right=0.83)

    fig.suptitle(suptitle, fontsize=_Q22_SUPTITLE_FONTSIZE)
    return fig


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


def _render_ot_mass_change_panel(
    ax: plt.Axes,
    mass_destroy: np.ndarray,
    mass_create: np.ndarray,
    extent: list[float],
    bodypart: str,
    center_mode: str,
    *,
    spatial_config: dict[str, Any],
    bin_label: str,
    shared_mass_change_vmax_abs: float | None = None,
    mass_change_floor_fraction: float = 0.05,
) -> None:
    """Render the COMBINED mass-change heatmap onto one Axes per Q33
    Addendum #30. ``H_mass_change = mass_create − mass_destroy`` →
    diverging cmap (Q25 ``_PROPORTION_DIFF_CMAP``: blue=decreased,
    grey midpoint, red=increased). Symmetric ``vmin=-V, vmax=+V``
    where V is the bucket-shared abs vmax. NaN-mask
    ``|H_mass_change| < V × mass_change_floor_fraction``.

    Supersedes the Q27 Blues-destroy + Reds-create two-panel render.

    Q14/Q18 shared bucket: ``shared_mass_change_vmax_abs`` (when given)
    pins V for the whole UOT bucket. When None, falls back to the
    panel-local max(|H|) (standalone smoke without Pass-1).

    Q28+Q29 carry-over: sub-floor bins → NaN; set_bad("white") on the
    cmap renders them as the white panel background. Axes facecolor
    also white (defensive).
    """
    if mass_destroy is None or mass_create is None:
        ax.text(0.5, 0.5, "(no mass change)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    H_mass_change = mass_create.astype(float) - mass_destroy.astype(float)
    if float(np.abs(H_mass_change).sum()) == 0.0:
        ax.text(0.5, 0.5, "(no net mass change)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    # Q33: diverging cmap (same as Q25 PD) with white-for-NaN.
    cmap = _PROPORTION_DIFF_CMAP
    # Q33: per-bucket symmetric V; fallback to per-panel if not given.
    if shared_mass_change_vmax_abs is not None and shared_mass_change_vmax_abs > 0:
        vmax_abs = float(shared_mass_change_vmax_abs)
    else:
        vmax_abs = float(np.abs(H_mass_change).max())
        if vmax_abs <= 0:
            vmax_abs = 1e-12
    floor = vmax_abs * float(mass_change_floor_fraction)
    H_masked = (
        np.where(np.abs(H_mass_change) >= floor, H_mass_change, np.nan)
        if floor > 0 else H_mass_change.copy()
    )
    # Q22 Addendum #21: white facecolor so NaN cells blend in.
    ax.set_facecolor("white")
    ax.imshow(
        H_masked.T, origin="lower", extent=extent,
        cmap=cmap, aspect="auto",
        vmin=-vmax_abs, vmax=+vmax_abs,
    )
    per_mode = _get_per_center_mode_params(spatial_config, bodypart, center_mode)
    xl = per_mode["xlim"] if per_mode["xlim"] else (extent[0], extent[1])
    yl = per_mode["ylim"] if per_mode["ylim"] else (extent[2], extent[3])
    ax.set_xlim(xl)
    ax.set_ylim(yl[1], yl[0])  # inverted Y
    _apply_q22_panel_polish(ax)
    ax.set_title(
        f"bin {bin_label} | mass change",
        fontsize=_Q22_PANEL_TITLE_FONTSIZE,
    )
    # Q24 / Q33: ONE shared diverging colorbar on the figure level,
    # attached in `render_unbalanced_ot_displacement_field`. The imshow
    # mappable is recovered via `ax.images[0]` post-hoc.


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
    shared_mass_change_vmax_abs: float | None = None,
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
    # Q33 Addendum #30: mass_change_floor_fraction supersedes the
    # deprecated mass_floor_fraction (Q29).
    mass_change_floor_fraction = float(
        unb_cfg.get("mass_change_floor_fraction", 0.05)
    )

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

    # Q33 Addendum #30: grid collapsed to N rows × 2 cols (mass_change |
    # arrows per bin). Combined mass_change = mass_create − mass_destroy,
    # diverging-cmap panel.
    n_bins = len(bin_labels)
    nrows = max(1, n_bins)
    ncols = 2
    fig, axes_obj = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols * 5.0, nrows * 3.8),
        constrained_layout=True,
    )
    # Normalize axes layout to 2D (nrows, 2).
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
        ax_mass_change = axes[row_idx, 0]
        ax_arrows = axes[row_idx, 1]
        if H_bin is None or n_total_bin == 0:
            for ax in (ax_mass_change, ax_arrows):
                ax.text(0.5, 0.5, f"bin {bin_label}\n(no data)",
                        ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
            continue
        ext = ext_pre or ext_b
        # Q17 Addendum #16: total-frame denominator (not H_bin.sum()).
        H_bin_prop = H_bin / float(n_total_bin)
        plan = _compute_unbalanced_ot_plan(H_pre_pool_prop, H_bin_prop, ext)
        if plan is None:
            for ax in (ax_mass_change, ax_arrows):
                ax.text(0.5, 0.5, f"bin {bin_label}\n(OT solver failed)",
                        ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
            continue
        bin_n_sess_title = f"n_sess={n_sess}"
        _render_ot_mass_change_panel(
            ax_mass_change,
            plan["mass_destroy"], plan["mass_create"], ext,
            bp_for_axis, center_mode,
            spatial_config=spatial_config,
            bin_label=f"{bin_label} {bin_n_sess_title}",
            shared_mass_change_vmax_abs=shared_mass_change_vmax_abs,
            mass_change_floor_fraction=mass_change_floor_fraction,
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

    # Q33 Addendum #30: ONE diverging colorbar (mass change), scoped to
    # the mass_change grid column. Arrows column has no colorbar.
    mass_axes = list(axes[:, 0]) if axes.ndim == 2 else [axes[0]]
    mass_im = next((a.images[0] for a in mass_axes if a.images), None)
    if mass_im is not None:
        cbar_m = fig.colorbar(
            mass_im, ax=mass_axes, shrink=0.7, pad=0.02,
        )
        cbar_m.set_label(
            "mass change (created − destroyed)",
            fontsize=_Q22_AXIS_LABELSIZE,
        )
        _apply_q22_colorbar_polish(cbar_m)
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


def precompute_pattern_b_bucket_per_bp_norms_is(
    animal: str,
    family_entry: str,
    scope: Scope,
    dates: list[dt.date],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Q52 Addendum #44 (2026-05-18) — Pattern B IS bucket-shared per-bp
    norms. Pass 1 of the two-pass IS Pattern B render flow.

    The IS Pattern B bucket = ``(animal, family_entry, IS, scope,
    trial_group)`` — same Q14 bucket as Pattern A's IS shared-vmin/
    vmax (Q23 drops bin_size; IS has no bin dimension). For each
    ``trial_group`` independently, this function pools the
    per-(date, bp) H_proportion arrays across all dates in the
    bucket, then derives the per-bp LogNorm vmax as the 99th
    percentile of pooled positive values. ``vmin`` is the legacy
    ``1e-6`` floor (matches Cell 13 ``VMIN_LOG_PROP``).

    Returned dict structure:
        ``{trial_group: {bp: (vmin=1e-6, vmax=99th-pct-bucket)}}``

    Used by the cohort driver as Pass 1 for IS Pattern B; Pass 2 is
    the per-date ``render_individual_session_heatmap(...,
    bucket_per_bp_norms=...)`` call. Single-bp families return ``{}``
    (Pattern A goes through the scalar shared_vmin/shared_vmax path
    instead).

    Supersedes Q48 verdict item 3's figure-local norm scope. BS-grid
    Pattern B (Q36) is already bucket-shared by virtue of one-SVG-
    per-bucket, so this function is IS-only.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    bodyparts, center_mode = _resolve_family_entry(family_entry, defaults)
    if len(bodyparts) <= 1:
        return {}
    # Accumulator: {tg: {bp: list[np.ndarray]}}.
    # Q55 Addendum #46: Q53 collapse REVERTED; whiskers pool per-bp
    # (6 entries) so the bucket norm axis matches the 6-layer render.
    accumulator: dict[str, dict[str, list[np.ndarray]]] = {}
    for date in dates:
        panels = _compute_composite_panels(
            animal, [date], bodyparts, center_mode, scope, resolver,
            defaults=defaults, animal_info=animal_info,
        )
        for tg, per_tg in panels.items():
            tg_acc = accumulator.setdefault(tg, {})
            for bp, H, _ext, _n_sess, _n_tones, n_total in per_tg:
                if H is None or n_total == 0:
                    continue
                tg_acc.setdefault(bp, []).append(H / float(n_total))
    vmin_floor = _PATTERN_B_LEGACY_VMIN
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for tg, bp_arrays in accumulator.items():
        tg_out: dict[str, tuple[float, float]] = {}
        for bp, arrs in bp_arrays.items():
            pooled = np.concatenate([
                a[np.isfinite(a) & (a > 0)].flatten() for a in arrs
            ])
            if pooled.size == 0:
                continue
            vmax = float(np.percentile(pooled, _PATTERN_B_VMAX_PERCENTILE))
            tg_out[bp] = (vmin_floor, max(vmax, vmin_floor * 10.0))
        out[tg] = tg_out
    return out


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


def derive_symmetric_diff_vmax(
    arrays: list[np.ndarray],
    *,
    vmax_percentile: float = 95.0,
) -> float:
    """Q18 symmetric vmax for PD bucket; per-panel renderer uses
    (vmin=-vmax, vmax=+vmax) with the Q25 diverging cmap.

    Q42 Addendum #38 (2026-05-15): switch from ``max(|D|.max())`` to a
    percentile-based vmax across the bucket. The bucket-wide
    `max-absolute` rule was dominated by 1-2 picket-fence DLC mis-
    detection bins per family, compressing the dynamic range of the
    diverging cmap so the bulk of the structure rendered in near-
    midpoint gray. Using a high percentile (default 95th) clips those
    extremes; per-panel imshow auto-saturates anything above vmax,
    which is the desired behavior for outliers.

    ``vmax_percentile`` is sourced from
    ``defaults['dlc_spatial_tone_aligned']['proportion_differences']
    ['vmax_percentile']`` by the cohort driver (Q42). 95.0 is the
    locked default; tune-down (e.g., 90) compresses extremes further
    if PD panels still wash out.
    """
    abs_pieces: list[np.ndarray] = []
    for arr in arrays:
        if arr is None or arr.size == 0:
            continue
        finite_abs = np.abs(arr[np.isfinite(arr)])
        if finite_abs.size:
            abs_pieces.append(finite_abs)
    if not abs_pieces:
        return 1e-12
    abs_concat = np.concatenate(abs_pieces)
    pct = float(vmax_percentile)
    vmax = float(np.percentile(abs_concat, pct))
    return vmax if vmax > 0 else 1e-12


def derive_uot_bucket_ranges(
    plans: list[dict[str, Any]],
    *,
    threshold_pct50_multiplier: float = 0.1,
) -> tuple[float, float, float]:
    """Q18 UOT bucket-shared ranges, updated for Q33 Addendum #30
    collapsed mass_change panel: ``(mass_change_vmax_abs,
    arrow_logmag_lo, arrow_logmag_hi)``.

    ``mass_change_vmax_abs`` = max |create − destroy| across all plans
    in the bucket. Panel imshow uses symmetric ``vmin=-V, vmax=+V``
    around 0 (diverging cmap from Q25 ``_PROPORTION_DIFF_CMAP``).

    Arrow logmag uses 1st/99th percentile of log10(mass_grid + eps)
    across plans (with the mass_thr + mag_thr mask applied per
    `_render_ot_arrows_panel`).

    Q21 Addendum #20: ``threshold_pct50_multiplier`` matches the same
    knob in `_render_ot_arrows_panel` — Pass-1 and Pass-2 must apply
    the same mask so the bucket-shared arrow logmag range corresponds
    to the arrows that actually render. Default 0.1 matches legacy.
    """
    mass_change_vmax_abs_candidates: list[float] = []
    all_logM: list[np.ndarray] = []
    thr_mult = float(threshold_pct50_multiplier)
    for plan in plans:
        md = plan.get("mass_destroy")
        mc = plan.get("mass_create")
        if md is not None and mc is not None:
            H_mass_change = mc.astype(float) - md.astype(float)
            v = float(np.abs(H_mass_change).max()) if H_mass_change.size else 0.0
            if v > 0:
                mass_change_vmax_abs_candidates.append(v)
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
    # Q33 Addendum #30: collapsed bucket vmax_abs for combined mass_change.
    mass_change_vmax_abs = (
        max(mass_change_vmax_abs_candidates)
        if mass_change_vmax_abs_candidates else 0.0
    )
    if all_logM:
        flat_logM = np.concatenate(all_logM)
        logmag_lo = float(np.percentile(flat_logM, 1))
        logmag_hi = float(np.percentile(flat_logM, 99))
        if logmag_hi <= logmag_lo:
            logmag_hi = logmag_lo + 1e-6
    else:
        logmag_lo, logmag_hi = -10.0, -9.0
    return (mass_change_vmax_abs, logmag_lo, logmag_hi)


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
    "render_binned_sessions_grid",
    "render_binned_sessions_heatmap",
    "render_h_counts_panel",
    "render_individual_session_heatmap",
    "render_proportion_difference_heatmap",
    "render_tone_aligned_heatmap_session",
    "render_unbalanced_ot_displacement_field",
    "render_whole_session_heatmap",
]
