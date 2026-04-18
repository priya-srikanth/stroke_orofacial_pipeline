"""Difference proportion maps and descriptive statistics.

Ported from cell 12 (subtraction maps) of ``20251117_DLC_analysis_nose.ipynb``
and cell 7 of ``20251202_DLC_analysis_all_bodyparts_stats_pixelbin.ipynb``.

Computes per-bin subtraction: ``post - baseline`` in counts or proportion
mode. Used for across-day comparisons (post-stroke day N minus baseline mean).

Permutation significance testing is deferred to Phase 9 per DECISIONS.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np


def compute_difference_map(
    H_post: np.ndarray,
    H_baseline: np.ndarray,
    mode: Literal["counts", "proportion"] = "proportion",
) -> np.ndarray:
    """Compute per-bin difference between a post-stroke and baseline histogram.

    Parameters
    ----------
    H_post : np.ndarray
        Post-stroke session histogram (counts or proportion).
    H_baseline : np.ndarray
        Baseline aggregate histogram (same shape, same mode).
    mode : str
        ``"counts"`` for raw count difference, ``"proportion"`` for
        proportion difference. Both compute ``H_post - H_baseline``.

    Returns
    -------
    np.ndarray
        Difference map (same shape). Positive = increased occupancy
        post-stroke, negative = decreased.
    """
    if H_post.shape != H_baseline.shape:
        raise ValueError(
            f"Shape mismatch: post={H_post.shape}, baseline={H_baseline.shape}"
        )
    return H_post - H_baseline


def plot_difference_map(
    diff: np.ndarray,
    extent: list[float] | np.ndarray,
    bodypart: str,
    *,
    title: str = "",
    cmap: str = "RdBu_r",
    figsize: tuple[float, float] = (8, 6),
    vmax: float | None = None,
) -> plt.Figure:
    """Plot a difference map as a diverging-colormap image.

    Parameters
    ----------
    diff : np.ndarray
        Difference map from ``compute_difference_map()``.
    extent : list or array
        ``[x_min, x_max, y_min, y_max]`` for imshow.
    bodypart : str
        Bodypart name (for labels).
    title : str
        Plot title.
    cmap : str
        Diverging colormap (default ``"RdBu_r"``).
    figsize : tuple
        Figure size.
    vmax : float or None
        Symmetric color scale ``[-vmax, vmax]``. If None, auto from data.

    Returns
    -------
    plt.Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if vmax is None:
        vmax = float(np.nanmax(np.abs(diff))) or 1.0

    im = ax.imshow(
        diff.T,  # transpose for (x, y) -> (row=y, col=x) convention
        extent=extent,
        origin="lower",
        cmap=cmap,
        vmin=-vmax,
        vmax=vmax,
        aspect="auto",
    )
    plt.colorbar(im, ax=ax, label="Δ occupancy")
    ax.set_xlabel(f"{bodypart}_x (centered)")
    ax.set_ylabel(f"{bodypart}_y (centered)")
    ax.set_title(title or f"{bodypart} Δ (post − baseline)")

    return fig


def save_difference_map_png(
    fig: plt.Figure,
    path: Path,
    dpi: int = 200,
) -> None:
    """Save a difference map figure to PNG."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
