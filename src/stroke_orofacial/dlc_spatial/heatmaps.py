"""2D-KDE heatmaps and scatter plots per (animal, session, bodypart, center_mode).

Ported from cells 10-11 of ``20251117_DLC_analysis_nose.ipynb`` and
``20251117_DLC_analysis_jaw.ipynb`` (siblings, consolidated into one
parameterized module), plus cell 5 of
``20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb``.

Per DESIGN.md §5, the 2KSD variant is exploratory and deferred to Phase 9.

Per DECISIONS.md "Phase 5+ downstream analyses": axis limits, colormaps,
and DPI are per-(bodypart, center_mode), loaded from config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stroke_orofacial.dlc_spatial.pixel_bins import (
    _get_per_center_mode_params,
    build_histogram,
    get_masked_xy,
)
from stroke_orofacial.lr_convention import stamp_side_convention


def plot_heatmap(
    df: pd.DataFrame,
    bodypart: str,
    config: dict[str, Any],
    *,
    center_mode: str | None = None,
    x_limits: tuple[float, float] | None = None,
    y_limits: tuple[float, float] | None = None,
    x_range: tuple[float, float] | None = None,
    title: str = "",
    figsize: tuple[float, float] = (8, 6),
    window: Any | None = None,
    baseline_fill_mask: np.ndarray | None = None,
    drop_likelihood_gate: bool = False,
) -> plt.Figure:
    """Render a 2D histogram heatmap for one bodypart in one session.

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame.
    bodypart : str
        Bodypart name.
    config : dict
        The ``dlc_spatial`` section from defaults.yaml.
    center_mode : str, optional
        Centering mode used for *df*. When given, the function reads
        ``config.bodyparts.{bp}.per_center_mode.{mode}`` and uses its
        ``xlim``, ``ylim``, ``x_range`` — unless an explicit kwarg overrides.
        Added in Phase 4.5-lite; prior behavior (no config consumption,
        used hardcoded defaults which produced blank plots on centered
        data) is preserved when center_mode is None but strongly
        discouraged.
    x_limits, y_limits : tuple, optional
        Explicit axis range override. If None, falls back to the config's
        per-(bodypart, center_mode) block, then to ``(-200, 200)`` /
        ``(50, 550)`` as ultimate fallbacks.
    x_range : tuple, optional
        Pre-histogram x filter override. Falls back to per-(bodypart,
        center_mode).x_range then legacy top-level fallback.
    title : str
        Plot title.
    figsize : tuple
        Figure size.
    window : WindowSelector, optional
        Frame selection window. Default None = whole session.

    Returns
    -------
    plt.Figure
        The rendered figure (caller is responsible for saving/closing).
    """
    bp_config = config.get("bodyparts", {}).get(bodypart, {})
    lik_thr = bp_config.get("likelihood_threshold", 0.80)
    cmap_name = bp_config.get("cmap", "viridis")
    nbins = int(config.get("heatmap_nbins", 100))

    per_mode = _get_per_center_mode_params(config, bodypart, center_mode)
    if x_limits is None:
        x_limits = per_mode["xlim"] or (-200, 200)
    if y_limits is None:
        y_limits = per_mode["ylim"] or (50, 550)
    if x_range is None:
        x_range = per_mode["x_range"]
        if x_range is None and config.get("apply_x_range", False):
            x_range = tuple(config.get("x_range", [-200, 200]))

    frame_mask = None
    if window is not None:
        frame_mask = window.select_frames(df)

    x, y = get_masked_xy(
        df, bodypart, lik_thr,
        x_range=x_range, frame_mask=frame_mask,
        baseline_fill_mask=baseline_fill_mask,
        drop_likelihood_gate=drop_likelihood_gate,
    )

    fig, ax = plt.subplots(figsize=figsize)

    if x is not None and len(x) > 0:
        try:
            cmap = plt.get_cmap(cmap_name)
        except ValueError:
            cmap = plt.get_cmap("viridis")

        ax.hist2d(
            x, y,
            bins=nbins,
            range=[list(x_limits), list(y_limits)],
            cmap=cmap,
            alpha=0.8,
            norm=mcolors.LogNorm(),
            density=True,
        )

    ax.set_xlabel(f"{bodypart}_x (centered)")
    ax.set_ylabel(f"{bodypart}_y (centered)")
    ax.set_title(title or f"{bodypart} heatmap")
    ax.set_xlim(x_limits)
    ax.set_ylim(y_limits)
    ax.invert_yaxis()  # camera-view convention: higher y = lower on plot

    return fig


def save_heatmap_png(
    fig: plt.Figure,
    path: Path,
    dpi: int = 200,
) -> None:
    """Save a heatmap figure to PNG.

    Parameters
    ----------
    fig : plt.Figure
        The figure to save.
    path : Path
        Output path (parent dirs created automatically).
    dpi : int
        Resolution.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_heatmap_npz(
    df: pd.DataFrame,
    bodypart: str,
    config: dict[str, Any],
    path: Path,
    *,
    center_mode: str | None = None,
    nbins: int = 100,
    x_limits: tuple[float, float] | None = None,
    y_limits: tuple[float, float] | None = None,
    x_range: tuple[float, float] | None = None,
    window: Any | None = None,
    wavesurfer_sides_match_mouse_sides: bool | None = None,
    trial_group: str | None = None,
    window_ms: tuple[float, float] | None = None,
    baseline_fill_mask: np.ndarray | None = None,
    drop_likelihood_gate: bool = False,
) -> bool:
    """Save the fine-grid heatmap histogram array as NPZ alongside the PNG.

    Wraps ``build_histogram`` and writes the resulting dict to disk so future
    figure tweaks (different colormaps, axis limits, normalization) and
    Phase 9 fine-resolution spatial stats don't have to recompute from
    parquet. Per DECISIONS.md "2026-04-19 Save fine-grid heatmap NPZ".

    The default ``nbins=100`` matches ``plot_heatmap``'s internal default
    (``config["heatmap_nbins"]``) that produced the existing PNG outputs,
    so adding NPZs alongside existing PNGs leaves the PNG content
    unchanged. Pass a different ``nbins`` to explore alternative
    resolutions per Priya 2026-04-20.

    Base NPZ keys (matches ``build_histogram`` return + adds ``x_limits`` /
    ``y_limits`` / ``nbins`` for self-description):

      - ``H_counts`` — raw 2D histogram counts (nbins × nbins)
      - ``H_proportion`` — normalized so total = 1
      - ``xedges``, ``yedges`` — bin edges
      - ``x_limits``, ``y_limits`` — axis range used for binning
      - ``nbins`` — bin count per axis

    Optional Phase 6.8a keys (present only when the corresponding kwarg
    is supplied — callers that don't care about L/R can omit them and
    the saved NPZ matches the pre-6.8a schema):

      - ``wavesurfer_sides_match_mouse_sides`` + ``side_convention_version``
        — stamped via :func:`stroke_orofacial.lr_convention.stamp_side_convention`
        when ``wavesurfer_sides_match_mouse_sides`` is not None.
      - ``trial_group`` — string scalar (``"all"`` / ``"L"`` / ``"R"``) so the
        NPZ is self-describing without its filename.
      - ``window_ms`` — 2-element float array ``[pre_ms, post_ms]`` so
        Phase 6 NPZs are self-describing without their filename slug.

    Parameters
    ----------
    df : pd.DataFrame
        Centered DLC DataFrame.
    bodypart : str
        Bodypart name.
    config : dict
        The ``dlc_spatial`` section from defaults.yaml (passed through to
        ``build_histogram`` for likelihood / per-(bodypart, center_mode)
        axis-limit lookup).
    path : Path
        Destination NPZ path. Parent dirs created automatically.
    center_mode : str, optional
        Centering mode. Forwarded to ``build_histogram``.
    nbins : int
        Bins per axis. Default 100 matches the existing PNG-producing
        histogram resolution.
    x_limits, y_limits, x_range, window : same as ``build_histogram``.
    wavesurfer_sides_match_mouse_sides : bool, optional
        Per-animal rig-orientation flag. When provided, the NPZ is
        stamped with this value + :data:`SIDE_CONVENTION_VERSION` so
        downstream consumers can tell whether the ``H_counts`` /
        ``H_proportion`` were computed under a L↔R-mirrored rig. Pass
        ``None`` (default) for Phase 5 whole-session outputs where
        L/R stratification doesn't apply; pass the animal's actual
        flag for Phase 6 reward-aligned outputs where ``trial_group``
        was consulted to build the ``window``.
    trial_group : str, optional
        ``"all"`` / ``"L"`` / ``"R"`` (mouse-frame). Saved as a
        ``numpy`` string scalar when provided.
    window_ms : tuple[float, float], optional
        ``(pre_ms, post_ms)`` — saved as a 2-element float array when
        provided.

    Returns
    -------
    bool
        True if NPZ was written, False if ``build_histogram`` returned None
        (no valid points after masking).
    """
    hist = build_histogram(
        df, bodypart, config,
        center_mode=center_mode,
        x_limits=x_limits,
        y_limits=y_limits,
        x_range=x_range,
        nbins=nbins,
        window=window,
        baseline_fill_mask=baseline_fill_mask,
        drop_likelihood_gate=drop_likelihood_gate,
    )
    if hist is None:
        return False

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    extent = hist["extent"]
    payload: dict[str, Any] = {
        "H_counts": hist["H_counts"],
        "H_proportion": hist["H_proportion"],
        "xedges": hist["xedges"],
        "yedges": hist["yedges"],
        "x_limits": np.asarray([extent[0], extent[1]], dtype=np.float64),
        "y_limits": np.asarray([extent[2], extent[3]], dtype=np.float64),
        "nbins": int(nbins),
        # Phase 7e.4: stamp the cleaned-traces routing decision so
        # downstream NPZ consumers (Phase 9 stats, audit comparators)
        # can tell which filter pipeline produced the H_counts. Bool
        # scalars; default-False values match pre-7e.4 NPZ semantics.
        "applied_cleaned_traces_mask": np.bool_(baseline_fill_mask is not None),
        "dropped_likelihood_gate": np.bool_(drop_likelihood_gate),
    }

    # Phase 6.8a: optional self-describing scalars. Added conditionally
    # so Phase 5 whole-session callers that don't pass them still write
    # a pre-6.8a-shape NPZ (backward-compat for any stats code already
    # reading existing outputs).
    if trial_group is not None:
        # np.savez coerces Python strings to numpy unicode scalars.
        payload["trial_group"] = np.asarray(trial_group)
    if window_ms is not None:
        payload["window_ms"] = np.asarray(
            [float(window_ms[0]), float(window_ms[1])], dtype=np.float64,
        )
    if wavesurfer_sides_match_mouse_sides is not None:
        # stamp_side_convention mutates payload in place and rejects
        # non-bool / collision-with-existing-key; piggy-backs on the
        # same validation Phase 2 uses for its NPZs.
        stamp_side_convention(payload, wavesurfer_sides_match_mouse_sides)

    np.savez(str(path), **payload)
    return True
