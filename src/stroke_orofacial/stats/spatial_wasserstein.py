"""Phase 9.1 Q-lock 12 Addendum #5 — Per-animal W-2 stats from spatial histograms.

Companion to :mod:`stroke_orofacial.stats.spatial_proportion_diff`. Same
within-animal baseline pattern (Q12-A), but instead of producing a
per-bin proportion-diff D array per (animal, side, bodypart,
post_epoch), produces a **single Wasserstein-2 distance scalar** per
combination.

W-2 between two 2D pixel-bin histograms ``P_pre`` and ``P_post``:

  - Renormalize each so it sums to 1 (W-2 requires balanced marginals;
    the Q17 ``passed_frames / total_frames`` ratios are NOT comparable
    in raw form across (animal, epoch) so per-side renormalization
    isolates the SPATIAL-shape comparison from the tracking-rate axis).
  - Cost matrix ``C[i, j] = ||c_i - c_j||²`` where ``c_i`` is the
    (x, y) center of bin ``i`` in pixel units.
  - Solve the balanced LP via :func:`ot.emd2` → returns the W-2²
    optimal transport cost.
  - Report ``W-2 = sqrt(W-2²)`` (units: pixels).

Exact OT (not entropic / sinkhorn / sliced) per Priya 2026-05-28
direction for statistical credibility. Per-(animal × bp × side ×
post_epoch) compute time is dominated by the LP solve on the
union-support reduced problem (typically a few hundred bins; ~1-10 s
per pair on the v7-cleaned-trace cohort).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _bin_centers_2d(extent: list[float], nx: int, ny: int) -> np.ndarray:
    """Compute (nx*ny, 2) array of bin-center (x, y) coordinates.

    ``extent = [x_min, x_max, y_min, y_max]`` from
    :func:`stroke_orofacial.dlc_spatial.pixel_bins.build_histogram`.
    Bin (i, j) center is the midpoint of the i-th x-bin and j-th
    y-bin. The returned array is row-major over (i, j) — matching
    ``H_counts.ravel()`` from numpy's ``histogram2d`` (which is
    indexed (x_bin, y_bin)).
    """
    x_min, x_max, y_min, y_max = extent
    x_edges = np.linspace(x_min, x_max, nx + 1)
    y_edges = np.linspace(y_min, y_max, ny + 1)
    x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
    y_centers = 0.5 * (y_edges[:-1] + y_edges[1:])
    Xg, Yg = np.meshgrid(x_centers, y_centers, indexing="ij")
    return np.column_stack([Xg.ravel(), Yg.ravel()])


def compute_wasserstein2_2d(
    H_pre: np.ndarray,
    H_post: np.ndarray,
    extent: list[float],
) -> float:
    """Exact W-2 distance between two 2D pixel-bin histograms.

    Renormalizes each histogram to sum to 1 (isolating the spatial-
    shape comparison from the Q17 tracking-rate axis), restricts to
    the union of bins with nonzero mass on either side (the LP runs
    on the reduced problem so per-call cost is dominated by the
    nonzero-support size, not the 80×80 grid), and solves the exact
    balanced OT via :func:`ot.emd2` with a squared-Euclidean cost
    matrix on bin centers in pixel units.

    Parameters
    ----------
    H_pre, H_post : np.ndarray
        Same-shape ``(nx, ny)`` non-negative count histograms. ``H_pre``
        from per-animal pre-pool; ``H_post`` from the (animal,
        post_epoch) histogram.
    extent : list[float]
        ``[x_min, x_max, y_min, y_max]`` from
        :func:`stroke_orofacial.dlc_spatial.pixel_bins.build_histogram`.

    Returns
    -------
    float
        ``W-2`` distance in pixel units (i.e.
        ``sqrt(ot.emd2(...))`` since the cost matrix is squared-distance).
        Returns ``np.nan`` if either histogram is empty.

    Raises
    ------
    ValueError
        On shape mismatch.
    """
    if H_pre.shape != H_post.shape:
        raise ValueError(
            f"shape mismatch: H_pre {H_pre.shape} vs H_post {H_post.shape}",
        )
    pre_sum = float(H_pre.sum())
    post_sum = float(H_post.sum())
    if pre_sum <= 0 or post_sum <= 0:
        return float("nan")

    nx, ny = H_pre.shape
    P_pre = (H_pre / pre_sum).ravel()
    P_post = (H_post / post_sum).ravel()

    # Reduce to the union of nonzero-mass bins — keeps the OT LP
    # tractable for 80x80 grids by restricting to a few hundred
    # populated bins instead of 6400.
    mask = (P_pre > 0) | (P_post > 0)
    keep_idx = np.where(mask)[0]
    a = P_pre[keep_idx]
    b = P_post[keep_idx]

    # Renormalize after restriction to compensate for any tiny dropped
    # mass (defensive — mask already covers all nonzero bins so this
    # is typically a no-op).
    a = a / a.sum()
    b = b / b.sum()

    centers = _bin_centers_2d(extent, nx, ny)[keep_idx]
    # Squared Euclidean cost — W-2 emerges as sqrt(emd2(a, b, C_sq)).
    diff = centers[:, None, :] - centers[None, :, :]
    C_sq = (diff ** 2).sum(axis=-1)

    import ot  # local import: POT can be slow to import; lazy.
    cost = ot.emd2(a, b, C_sq)
    return float(np.sqrt(max(cost, 0.0)))


def compute_per_animal_wasserstein2(
    *,
    pre_pool: dict[str, Any],
    H_post_counts: np.ndarray,
    extent: list[float] | None,
) -> float:
    """Wrapper: compute W-2 from a Stage 1 pre_pool + per-epoch H_post.

    Convenience caller-thin layer that pulls ``H_pre_counts`` out of
    the Stage 1 ``compute_per_animal_pre_pool`` result and forwards
    to :func:`compute_wasserstein2_2d`.

    Returns ``np.nan`` if ``H_post_counts`` is None or ``extent`` is
    None (per-animal-per-epoch no-contribution case).
    """
    if H_post_counts is None or extent is None:
        return float("nan")
    return compute_wasserstein2_2d(
        pre_pool["H_pre_counts"], H_post_counts, extent,
    )


def compute_per_animal_per_session_w2_long(
    *,
    animal: str,
    pre_pool: dict[str, Any],
    post_dates: list,
    side: str,
    bodypart: str,
    resolver,
    defaults: dict[str, Any] | None = None,
    animal_info=None,
    epoch_label: str | None = None,
) -> list[dict[str, Any]]:
    """Compute per-session W-2 against the animal's pre-pool.

    One W-2 scalar per ``(animal, date)`` for the given (side, bodypart),
    differenced against the per-animal pre-pool. The pre-pool itself
    is computed once by the caller (via Stage 1
    :func:`stroke_orofacial.stats.spatial_proportion_diff.compute_per_animal_pre_pool`)
    and passed in here.

    Pre-epoch sessions (``epoch_label="pre"``) compare each pre session's
    histogram against the FULL pre-pool that INCLUDES that session
    (Q-lock 12a Addendum #6 v1 "naive" lock per Priya 2026-05-28). The
    small bias toward 0 is acceptable as a noise-floor reference; the
    rigorous leave-one-out alternative is deferred.

    Returns a list of dicts (long-form rows). Sessions whose H_post is
    None or zero-mass (no contributing tones / parquets) are skipped
    silently — the caller treats them as missing.
    """
    from stroke_orofacial.stats.spatial_proportion_diff import (
        compute_pooled_recipe_histogram,
        get_spatial_recipe,
    )

    if defaults is None:
        from stroke_orofacial.config_loader import load_defaults
        defaults = load_defaults()
    if animal_info is None:
        from stroke_orofacial.animals import get_animal
        animal_info = get_animal(animal)
    # Recipe-driven (chore whisker-nose Addendum #2): pools landmarks ×
    # trial_groups per side, routes raw vs v7-cleaned per recipe. tongue/jaw
    # resolve to their legacy single-landmark, cue-split, v7-cleaned path.
    recipe = get_spatial_recipe(bodypart)

    rows: list[dict[str, Any]] = []
    for d in post_dates:
        H_post, ext, _n_sess, _n_tones, n_total_post = (
            compute_pooled_recipe_histogram(
                animal, [d], recipe, side, resolver,
                defaults=defaults, animal_info=animal_info,
            )
        )
        if H_post is None or n_total_post == 0:
            continue
        w2 = compute_wasserstein2_2d(
            pre_pool["H_pre_counts"], H_post,
            pre_pool["extent"] if pre_pool["extent"] is not None else ext,
        )
        rows.append({
            "animal": animal,
            "date": d,
            "side": side,
            "bodypart": bodypart,
            "epoch_label": epoch_label,
            "w2": float(w2),
        })
    return rows


__all__ = [
    "compute_per_animal_per_session_w2_long",
    "compute_per_animal_wasserstein2",
    "compute_wasserstein2_2d",
]
