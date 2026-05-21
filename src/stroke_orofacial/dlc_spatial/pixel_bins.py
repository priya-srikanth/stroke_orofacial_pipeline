"""Pixel-bin occupancy maps and descriptive statistics.

Ported from cells 5-7, 11-13 of canonical notebook
``20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb``
(latest YYYYMMDD for pixel-bin analysis).

Two binning grids coexist (matching legacy behavior):
  1. **Heatmap grid** (``heatmap_nbins``, default 100): fine-resolution for
     per-session visualization via matplotlib ``hist2d``.
  2. **Stats grid** (``target_bin_size``, default 25 px): coarser grid where
     ``nx = round(span_x / bin_size)``, ``ny = round(span_y / bin_size)``,
     min 5. Used for baseline aggregation and difference comparisons.

Permutation null and inferential stats (cells 8-10) are deferred to Phase 9
per DECISIONS.md "Phase 5 defers permutation/inferential spatial stats to
Phase 9."
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _get_per_center_mode_params(
    config: dict[str, Any], bodypart: str, center_mode: str | None
) -> dict[str, Any]:
    """Look up per-(bodypart, center_mode) plotting parameters.

    Returns a dict with keys ``xlim``, ``ylim``, ``x_range`` — each either a
    ``tuple[float, float]`` or ``None`` if the corresponding entry is missing
    or set to ``null`` in config.

    Added in Phase 4.5-lite: the sub-block
    ``dlc_spatial.bodyparts.{bp}.per_center_mode.{mode}`` now optionally
    includes ``x_range`` as a pre-histogram filter (legacy behavior), in
    addition to ``xlim`` and ``ylim`` which control axis rendering.
    """
    if center_mode is None:
        return {"xlim": None, "ylim": None, "x_range": None}
    bp_cfg = config.get("bodyparts", {}).get(bodypart, {}) or {}
    per_mode = bp_cfg.get("per_center_mode", {}).get(center_mode)
    if per_mode is None or not isinstance(per_mode, dict):
        return {"xlim": None, "ylim": None, "x_range": None}
    xl = per_mode.get("xlim")
    yl = per_mode.get("ylim")
    xr = per_mode.get("x_range")
    return {
        "xlim": tuple(xl) if xl else None,
        "ylim": tuple(yl) if yl else None,
        "x_range": tuple(xr) if xr else None,
    }


def get_masked_xy(
    df: pd.DataFrame,
    bodypart: str,
    likelihood_threshold: float,
    x_range: tuple[float, float] | None = None,
    frame_mask: np.ndarray | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Extract likelihood-gated (x, y) arrays for a bodypart.

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame with ``{bodypart}_{x|y|likelihood}`` columns.
    bodypart : str
        Bodypart name (e.g. ``"nose"``).
    likelihood_threshold : float
        Minimum likelihood for inclusion.
    x_range : tuple or None
        If provided, additionally filter to ``x_range[0] <= x <= x_range[1]``.
    frame_mask : np.ndarray or None
        If provided, boolean mask (same length as df) to AND with the
        likelihood mask. Used by window selectors to restrict to
        event-aligned frames.

    Returns
    -------
    tuple[np.ndarray | None, np.ndarray | None]
        (x, y) arrays of filtered coordinates, or (None, None) if no valid
        points remain.
    """
    xcol = f"{bodypart}_x"
    ycol = f"{bodypart}_y"
    likcol = f"{bodypart}_likelihood"

    if xcol not in df.columns or ycol not in df.columns:
        return None, None

    x = df[xcol].values.astype(np.float64)
    y = df[ycol].values.astype(np.float64)

    m = np.isfinite(x) & np.isfinite(y)
    if likcol in df.columns:
        lik = df[likcol].values.astype(np.float64)
        m &= lik >= likelihood_threshold

    if frame_mask is not None:
        m &= frame_mask

    if x_range is not None:
        m &= (x >= x_range[0]) & (x <= x_range[1])

    if not np.any(m):
        return None, None
    return x[m], y[m]


def build_histogram(
    df: pd.DataFrame,
    bodypart: str,
    config: dict[str, Any],
    *,
    center_mode: str | None = None,
    x_limits: tuple[float, float] | None = None,
    y_limits: tuple[float, float] | None = None,
    x_range: tuple[float, float] | None = None,
    nbins: int | None = None,
    window: Any | None = None,
    n_total_frames: int | None = None,
) -> dict[str, Any] | None:
    """Build a fine-resolution 2D histogram for visualization.

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame.
    bodypart : str
        Bodypart name.
    config : dict
        The ``dlc_spatial`` section from defaults.yaml.
    center_mode : str, optional
        Centering mode used for *df* (e.g. ``"eye_midpoint"``). When given,
        the function reads ``config.bodyparts.{bp}.per_center_mode.{mode}``
        and uses its ``xlim``, ``ylim``, and ``x_range`` values — unless an
        explicit kwarg overrides. Added in Phase 4.5-lite; prior behavior
        (no config consumption) is preserved when center_mode is None.
    x_limits, y_limits : tuple, optional
        Explicit axis range override. If None, falls back to the config's
        per-(bodypart, center_mode) block, then to ``(-200, 200)`` /
        ``(50, 550)`` as ultimate fallbacks.
    x_range : tuple, optional
        Pre-histogram x filter override. If None, falls back to per-(bodypart,
        center_mode).x_range, then to the legacy top-level
        ``config.apply_x_range`` / ``config.x_range`` fallback (deprecated).
    nbins : int, optional
        Number of bins per axis. Defaults to ``config["heatmap_nbins"]``.
    window : WindowSelector, optional
        Frame selection window. Default None = whole session (all frames).
    n_total_frames : int, optional
        Q17 (Phase 7c.2 Addendum #16) normalization denominator. When given,
        ``H_proportion = H_counts / n_total_frames`` — yields a "tracking
        rate × spatial distribution" composite whose sum equals
        ``n_passed / n_total ≤ 1.0``. When None (legacy), falls back to
        ``H_proportion = H_counts / H_counts.sum()`` (sums to 1.0; pure
        spatial-distribution-of-passed-frames probability).

        Task 5 callers MUST pass this explicitly (tone_aligned scope:
        ``window.n_selected``; whole_session scope: ``len(df)``). Pre-Q17
        callers (legacy NPZ reader scripts, notebook 12 first-emit) keep
        the None default and retain legacy semantics.

    Returns
    -------
    dict or None
        ``{"H_counts", "H_proportion", "xedges", "yedges", "extent",
        "n_total_frames"}`` or None if no valid points. ``n_total_frames``
        echoes the kwarg back so downstream aggregators can sum properly
        (the in-window total over all aggregated sessions).
    """
    bp_config = config.get("bodyparts", {}).get(bodypart, {})
    lik_thr = bp_config.get("likelihood_threshold", 0.80)
    if nbins is None:
        nbins = int(config.get("heatmap_nbins", 100))

    per_mode = _get_per_center_mode_params(config, bodypart, center_mode)
    if x_limits is None:
        x_limits = per_mode["xlim"] or (-200, 200)
    if y_limits is None:
        y_limits = per_mode["ylim"] or (50, 550)
    if x_range is None:
        x_range = per_mode["x_range"]
        # Legacy fallback: top-level apply_x_range / x_range (deprecated,
        # kept for pre-4.5-lite config compatibility).
        if x_range is None and config.get("apply_x_range", False):
            x_range = tuple(config.get("x_range", [-200, 200]))

    # Apply window mask if provided
    frame_mask = None
    if window is not None:
        frame_mask = window.select_frames(df)

    x, y = get_masked_xy(df, bodypart, lik_thr, x_range=x_range, frame_mask=frame_mask)
    if x is None:
        return None

    H_counts, xedges, yedges = np.histogram2d(
        x, y, bins=nbins, range=[list(x_limits), list(y_limits)]
    )
    if n_total_frames is not None:
        # Q17 Addendum #16: total-frame denominator (pre-likelihood filter).
        denom = float(n_total_frames)
        H_proportion = H_counts / denom if denom > 0 else H_counts
    else:
        # Legacy: passed-count denominator (post-filter).
        denom = float(H_counts.sum())
        H_proportion = H_counts / denom if denom > 0 else H_counts

    return {
        "H_counts": H_counts,
        "H_proportion": H_proportion,
        "xedges": xedges,
        "yedges": yedges,
        "extent": [x_limits[0], x_limits[1], y_limits[0], y_limits[1]],
        "n_total_frames": int(n_total_frames) if n_total_frames is not None else None,
    }


def build_stats_grid(
    df: pd.DataFrame,
    bodypart: str,
    config: dict[str, Any],
    *,
    center_mode: str | None = None,
    x_range: tuple[float, float] | None = None,
    window: Any | None = None,
) -> dict[str, Any] | None:
    """Build a coarser histogram grid for occupancy statistics.

    The grid size is determined by ``target_bin_size_{x,y}`` (default 25 px)
    applied to the data extent: ``nx = round(span / bin_size)``, min 5.

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame.
    bodypart : str
        Bodypart name.
    config : dict
        The ``dlc_spatial`` section from defaults.yaml.
    center_mode : str, optional
        When provided, reads ``config.bodyparts.{bp}.per_center_mode.{mode}.x_range``
        as the pre-histogram x filter. Added in Phase 4.5-lite.
    x_range : tuple, optional
        Explicit pre-histogram x filter override. Falls back to
        per-(bodypart, center_mode).x_range, then to legacy top-level
        ``config.apply_x_range`` / ``config.x_range``.
    window : WindowSelector, optional
        Frame selection window. Default None = whole session.

    Returns
    -------
    dict or None
        ``{"H_counts", "H_proportion", "nx", "ny", "dx", "dy",
        "GLOBAL_EXTENT", "HIST_RANGE"}`` or None if no valid points.
    """
    bp_config = config.get("bodyparts", {}).get(bodypart, {})
    lik_thr = bp_config.get("likelihood_threshold", 0.80)
    target_dx = float(config.get("target_bin_size_x", 25.0))
    target_dy = float(config.get("target_bin_size_y", 25.0))

    per_mode = _get_per_center_mode_params(config, bodypart, center_mode)
    if x_range is None:
        x_range = per_mode["x_range"]
        if x_range is None and config.get("apply_x_range", False):
            x_range = tuple(config.get("x_range", [-200, 200]))

    frame_mask = None
    if window is not None:
        frame_mask = window.select_frames(df)

    x, y = get_masked_xy(df, bodypart, lik_thr, x_range=x_range, frame_mask=frame_mask)
    if x is None:
        return None

    x_min, x_max = float(x.min()), float(x.max())
    y_min, y_max = float(y.min()), float(y.max())
    span_x = max(x_max - x_min, 1e-6)
    span_y = max(y_max - y_min, 1e-6)

    nx = max(int(round(span_x / target_dx)), 5)
    ny = max(int(round(span_y / target_dy)), 5)

    dx = span_x / nx
    dy = span_y / ny

    H_counts, xedges, yedges = np.histogram2d(
        x, y, bins=[nx, ny], range=[[x_min, x_max], [y_min, y_max]]
    )
    total = H_counts.sum()
    H_proportion = H_counts / total if total > 0 else H_counts

    return {
        "H_counts": H_counts,
        "H_proportion": H_proportion,
        "nx": nx,
        "ny": ny,
        "dx": dx,
        "dy": dy,
        "GLOBAL_EXTENT": np.array([x_min, x_max, y_min, y_max]),
        "HIST_RANGE": np.array([[x_min, x_max], [y_min, y_max]]),
    }


def build_baseline_histogram(
    session_grids: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate pre-stroke session grids into a baseline reference.

    Parameters
    ----------
    session_grids : list[dict]
        List of ``build_stats_grid()`` outputs for baseline sessions.
        All must have the same ``(nx, ny)`` and ``HIST_RANGE``.

    Returns
    -------
    dict
        ``{"H_pre_counts", "H_pre_prop", "P_pre_cond", "P_pre_full",
        "nx", "ny", "GLOBAL_EXTENT", "HIST_RANGE", "dx", "dy"}``
    """
    if not session_grids:
        raise ValueError("No baseline sessions provided")

    nx = session_grids[0]["nx"]
    ny = session_grids[0]["ny"]
    extent = session_grids[0]["GLOBAL_EXTENT"]
    hist_range = session_grids[0]["HIST_RANGE"]
    dx = session_grids[0]["dx"]
    dy = session_grids[0]["dy"]

    # Sum counts across sessions
    H_pre_counts = np.zeros((nx, ny), dtype=np.float64)
    for g in session_grids:
        H_pre_counts += g["H_counts"]

    total = H_pre_counts.sum()
    H_pre_prop = H_pre_counts / total if total > 0 else H_pre_counts

    # Conditional probability: P(bin | occupied) per bin
    P_pre_cond = H_pre_prop.copy()

    # Full distribution flattened
    P_pre_full = H_pre_prop.ravel()

    return {
        "H_pre_counts": H_pre_counts,
        "H_pre_prop": H_pre_prop,
        "P_pre_cond": P_pre_cond,
        "P_pre_full": P_pre_full,
        "nx": nx,
        "ny": ny,
        "GLOBAL_EXTENT": extent,
        "HIST_RANGE": hist_range,
        "dx": dx,
        "dy": dy,
    }
