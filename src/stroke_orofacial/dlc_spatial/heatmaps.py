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
import pandas as pd

from stroke_orofacial.dlc_spatial.pixel_bins import (
    _get_per_center_mode_params,
    get_masked_xy,
)


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

    x, y = get_masked_xy(df, bodypart, lik_thr, x_range=x_range, frame_mask=frame_mask)

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
