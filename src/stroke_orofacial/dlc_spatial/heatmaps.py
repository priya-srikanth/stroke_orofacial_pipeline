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

from stroke_orofacial.dlc_spatial.pixel_bins import get_masked_xy


def plot_heatmap(
    df: pd.DataFrame,
    bodypart: str,
    config: dict[str, Any],
    *,
    x_limits: tuple[float, float] = (-200, 200),
    y_limits: tuple[float, float] = (50, 550),
    title: str = "",
    figsize: tuple[float, float] = (8, 6),
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
    x_limits, y_limits : tuple
        Histogram range.
    title : str
        Plot title.
    figsize : tuple
        Figure size.

    Returns
    -------
    plt.Figure
        The rendered figure (caller is responsible for saving/closing).
    """
    bp_config = config.get("bodyparts", {}).get(bodypart, {})
    lik_thr = bp_config.get("likelihood_threshold", 0.80)
    cmap_name = bp_config.get("cmap", "viridis")
    nbins = int(config.get("heatmap_nbins", 100))

    x_range_filter = None
    if config.get("apply_x_range", False):
        x_range_filter = tuple(config.get("x_range", [-200, 200]))

    x, y = get_masked_xy(df, bodypart, lik_thr, x_range=x_range_filter)

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
