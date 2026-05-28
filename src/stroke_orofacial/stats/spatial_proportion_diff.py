"""Phase 9.1 Q-lock 12 — Per-animal within-baseline spatial proportion-diff.

Stage 1 of the Q-lock 12 phenotype-pooled proportion-diff heatmap pipeline.
Produces per-``(animal, side, bodypart, post_epoch)`` proportion_diff arrays
D = P(bin | animal, post_epoch) − P(bin | animal, pre), where:

  - The histogram bin grid is the canonical Phase 7c.2 grid from
    :func:`stroke_orofacial.dlc_spatial.pixel_bins.build_histogram` (80×80
    by default, ``dlc_spatial_tone_aligned.default_nbins``).
  - The per-side trial filter is the Phase 7c.2 ``trial_group`` axis
    (``"L"`` or ``"R"`` per
    :data:`stroke_orofacial.dlc_spatial.render_on_demand.TASK5_TRIAL_GROUPS_TONE_ALIGNED`).
  - The Q17 (Phase 7c.2 Addendum #16) total-in-window-frame denominator is
    used for both pre and post proportion normalization (NOT
    ``H_counts.sum()``).
  - Within-animal baseline lock Q12-A: each animal's per-epoch H_post is
    differenced against ITS OWN per-animal pre-stroke pool. Phenotype-
    pooling happens downstream in Stage 2.
  - No-data masking lock Q12-E: cells with ``H_pre==0 & H_post==0`` are set
    to NaN; no magnitude floor (Q12-K).
  - Bodyparts in scope (Q12-B): ``tongue`` + ``jaw``, both with
    ``center_mode="eye_midpoint"``.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from typing import Any

import numpy as np

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_spatial.render_on_demand import (
    TASK5_TONE_WINDOW_MS,
    _split_pre_post_dates,
    compute_animal_aggregated_histogram,
)
from stroke_orofacial.paths import PathResolver

logger = logging.getLogger(__name__)


POST_EPOCHS: tuple[str, str, str] = ("acute", "sub_acute", "chronic")
SIDES: tuple[str, str] = ("L", "R")

# Q12-B bodypart → center_mode mapping. Both bodyparts use the
# ``eye_midpoint`` centering convention (Phase 7c.2
# ``EXPECTED_TONE_ALIGNED_FAMILIES``).
BODYPART_CENTER_MODES: dict[str, str] = {
    "tongue": "eye_midpoint",
    "jaw": "eye_midpoint",
}


def split_post_dates_by_epoch(
    animal_info: AnimalInfo,
    post_dates: Sequence[dt.date],
) -> dict[str, list[dt.date]]:
    """Bin post-stroke dates into acute / sub_acute / chronic.

    Uses :attr:`AnimalInfo.epoch_boundaries`. Dates that fall in the
    transitional gap between ``subacute_max_rel_day + 1`` and
    ``chronic_min_rel_day - 1`` (inclusive) are silently dropped — that
    gap is by design when the YAML stamps a non-contiguous boundary.

    Parameters
    ----------
    animal_info : AnimalInfo
    post_dates : Sequence[datetime.date]
        Dates with ``rel_day >= 1`` (post-stroke). Caller is responsible
        for the pre/post split (e.g. via
        :func:`_split_pre_post_dates`).

    Returns
    -------
    dict[str, list[datetime.date]]
        Keys: ``"acute"``, ``"sub_acute"``, ``"chronic"``. Empty lists
        when no dates fall in that epoch.
    """
    eb = animal_info.epoch_boundaries
    by_epoch: dict[str, list[dt.date]] = {ep: [] for ep in POST_EPOCHS}
    for d in post_dates:
        rel = animal_info.day_relative_to_stroke(d)
        if rel < 1:
            continue
        if rel <= eb.acute_max_rel_day:
            by_epoch["acute"].append(d)
        elif rel <= eb.subacute_max_rel_day:
            by_epoch["sub_acute"].append(d)
        elif rel >= eb.chronic_min_rel_day:
            by_epoch["chronic"].append(d)
    for ep in POST_EPOCHS:
        by_epoch[ep].sort()
    return by_epoch


def compute_proportion_diff_within(
    H_pre_counts: np.ndarray,
    n_total_pre: int,
    H_post_counts: np.ndarray,
    n_total_post: int,
) -> np.ndarray:
    """Pure math: per-animal within-baseline proportion_diff D.

    ``D[i, j] = H_post_counts[i, j] / n_total_post − H_pre_counts[i, j] /
    n_total_pre``, with no-data cells (``H_pre==0 & H_post==0``) set to
    NaN.

    Denominators are total-in-window frame counts per Q17 (Phase 7c.2
    Addendum #16), NOT ``H_counts.sum()``. This makes the proportion a
    ``tracking_rate × spatial_distribution`` composite, where the sum
    over all bins of each ``H_*_prop`` equals
    ``passed_frames / total_in_window_frames`` ≤ 1.0.

    Parameters
    ----------
    H_pre_counts, H_post_counts : np.ndarray
        Same-shape 2D count histograms.
    n_total_pre, n_total_post : int
        Total in-window-frame denominators. Must be strictly positive.

    Returns
    -------
    np.ndarray
        Same-shape float array with the diff values, ``np.nan`` for
        no-data cells.

    Raises
    ------
    ValueError
        If shapes mismatch, or either denominator is non-positive.
    """
    if H_pre_counts.shape != H_post_counts.shape:
        raise ValueError(
            f"H shape mismatch: pre={H_pre_counts.shape}, "
            f"post={H_post_counts.shape}",
        )
    if n_total_pre <= 0 or n_total_post <= 0:
        raise ValueError(
            f"non-positive denominator: n_total_pre={n_total_pre}, "
            f"n_total_post={n_total_post}",
        )
    H_pre_prop = H_pre_counts / float(n_total_pre)
    H_post_prop = H_post_counts / float(n_total_post)
    D = H_post_prop - H_pre_prop
    no_data = (H_pre_counts == 0) & (H_post_counts == 0)
    if no_data.any():
        D = np.where(no_data, np.nan, D)
    return D


def compute_per_animal_pre_pool(
    animal: str,
    bodypart: str,
    side: str,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    pre_dates: Sequence[dt.date] | None = None,
    use_v7_cleaned: bool = True,
) -> dict[str, Any] | None:
    """Compute the per-animal pre-stroke pool histogram for one (bp, side).

    ``side`` ∈ ``{"L", "R"}`` selects the tone-aligned trial group
    (Q12-F). Aggregates frame-level histograms across all pre-stroke
    sessions (``rel_day <= 0``, including the stroke-day session per
    AnimalInfo convention).

    Returns ``None`` when no pre-stroke session contributes (no
    parquets, no tone events for the side, etc.); caller treats this as
    a per-animal skip.

    Parameters
    ----------
    animal, bodypart, side : str
    resolver : PathResolver
    defaults : dict, optional
        Pre-loaded :func:`stroke_orofacial.config_loader.load_defaults` output.
    animal_info : AnimalInfo, optional
    pre_dates : Sequence[datetime.date], optional
        Explicit pre-date list. When ``None``, derived from the animal's
        YAML range via
        :func:`stroke_orofacial.cohort_enumeration.yaml_driven_session_dates`
        (analysis_context ``"dlc.spatial"``) then split via
        :func:`_split_pre_post_dates`.

    Returns
    -------
    dict or None
        ``{"H_pre_counts", "extent", "n_pre_sessions", "n_pre_trials",
        "n_total_pre_frames"}``.
    """
    if bodypart not in BODYPART_CENTER_MODES:
        raise ValueError(
            f"bodypart {bodypart!r} not in Q12-B scope; expected one of "
            f"{tuple(BODYPART_CENTER_MODES)}.",
        )
    if side not in SIDES:
        raise ValueError(f"side {side!r} not in {SIDES}.")
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    if pre_dates is None:
        from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
        all_dates = yaml_driven_session_dates(
            animal, animal_info=animal_info, analysis_context="dlc.spatial",
        )
        pre_dates, _ = _split_pre_post_dates(all_dates, animal_info)
    if not pre_dates:
        logger.warning(
            "compute_per_animal_pre_pool: %s/%s/%s — no pre-stroke "
            "dates available; returning None.",
            animal, bodypart, side,
        )
        return None
    center_mode = BODYPART_CENTER_MODES[bodypart]

    H_pre, extent, n_pre_sessions, n_pre_trials, n_total_pre_frames = (
        compute_animal_aggregated_histogram(
            animal, list(pre_dates), bodypart, center_mode, resolver,
            trial_group=side, window_ms=TASK5_TONE_WINDOW_MS,
            defaults=defaults, animal_info=animal_info,
            use_v7_cleaned=use_v7_cleaned,
        )
    )
    if H_pre is None or n_total_pre_frames == 0:
        logger.warning(
            "compute_per_animal_pre_pool: %s/%s/%s — no pre-stroke "
            "contribution (n_sessions=%d, n_total_frames=%d); "
            "returning None.",
            animal, bodypart, side, n_pre_sessions, n_total_pre_frames,
        )
        return None
    return {
        "H_pre_counts": H_pre,
        "extent": list(extent) if extent is not None else None,
        "n_pre_sessions": int(n_pre_sessions),
        "n_pre_trials": int(n_pre_trials),
        "n_total_pre_frames": int(n_total_pre_frames),
    }


def compute_per_animal_per_epoch_diff(
    animal: str,
    bodypart: str,
    side: str,
    post_epoch: str,
    pre_pool: dict[str, Any],
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    post_dates_by_epoch: dict[str, list[dt.date]] | None = None,
    use_v7_cleaned: bool = True,
) -> dict[str, Any] | None:
    """Compute D = P(post_epoch) − P(pre) for one (animal, bp, side, epoch).

    Differences the per-epoch post histogram against the per-animal pre
    pool (Q12-A within-animal normalization).

    Returns ``None`` when the epoch has no contributing post-stroke
    session (empty epoch dates, all sessions missing parquets, etc.).

    Parameters
    ----------
    pre_pool : dict
        Output of :func:`compute_per_animal_pre_pool`. Must not be None.
    post_dates_by_epoch : dict, optional
        Pre-computed output of :func:`split_post_dates_by_epoch`. When
        ``None``, derived from the animal's YAML range here.

    Returns
    -------
    dict or None
        ``{"D", "extent", "n_post_sessions", "n_post_trials",
        "n_total_post_frames", "n_pre_sessions", "n_pre_trials",
        "n_total_pre_frames"}``.
        The pre-side counts are echoed from ``pre_pool`` so a downstream
        per-panel annotation can read them off this dict alone.
    """
    if post_epoch not in POST_EPOCHS:
        raise ValueError(f"post_epoch {post_epoch!r} not in {POST_EPOCHS}.")
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    if post_dates_by_epoch is None:
        from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
        all_dates = yaml_driven_session_dates(
            animal, animal_info=animal_info, analysis_context="dlc.spatial",
        )
        _, post_dates = _split_pre_post_dates(all_dates, animal_info)
        post_dates_by_epoch = split_post_dates_by_epoch(animal_info, post_dates)

    epoch_dates = post_dates_by_epoch.get(post_epoch, [])
    if not epoch_dates:
        return None

    center_mode = BODYPART_CENTER_MODES[bodypart]
    H_post, extent_post, n_post_sessions, n_post_trials, n_total_post_frames = (
        compute_animal_aggregated_histogram(
            animal, list(epoch_dates), bodypart, center_mode, resolver,
            trial_group=side, window_ms=TASK5_TONE_WINDOW_MS,
            defaults=defaults, animal_info=animal_info,
            use_v7_cleaned=use_v7_cleaned,
        )
    )
    if H_post is None or n_total_post_frames == 0:
        return None

    D = compute_proportion_diff_within(
        pre_pool["H_pre_counts"], pre_pool["n_total_pre_frames"],
        H_post, n_total_post_frames,
    )
    extent = pre_pool["extent"] if pre_pool["extent"] is not None else (
        list(extent_post) if extent_post is not None else None
    )
    return {
        "D": D,
        "extent": extent,
        "n_post_sessions": int(n_post_sessions),
        "n_post_trials": int(n_post_trials),
        "n_total_post_frames": int(n_total_post_frames),
        "n_pre_sessions": int(pre_pool["n_pre_sessions"]),
        "n_pre_trials": int(pre_pool["n_pre_trials"]),
        "n_total_pre_frames": int(pre_pool["n_total_pre_frames"]),
    }


__all__ = [
    "BODYPART_CENTER_MODES",
    "POST_EPOCHS",
    "SIDES",
    "compute_per_animal_per_epoch_diff",
    "compute_per_animal_pre_pool",
    "compute_proportion_diff_within",
    "split_post_dates_by_epoch",
]
