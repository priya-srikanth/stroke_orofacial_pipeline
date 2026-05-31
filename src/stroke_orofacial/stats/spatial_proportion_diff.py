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
from dataclasses import dataclass
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

# Q12-B bodypart → center_mode mapping. Tongue uses ``spout_midpoint``
# centering per Addendum #3 (2026-05-28) — biologically meaningful for
# reach-to-spout licking analysis; matches the ``tongue_spout_midpoint``
# family in Phase 7c.2 ``EXPECTED_TONE_ALIGNED_FAMILIES``. Jaw stays
# ``eye_midpoint`` (its only canonical centering).
BODYPART_CENTER_MODES: dict[str, str] = {
    "tongue": "spout_midpoint",
    "jaw": "eye_midpoint",
}


# ---------------------------------------------------------------------------
# Chore whisker-nose (Addendum #2): per-bodypart pooling recipes.
#
# Each LOGICAL bodypart maps to a recipe describing how to build its pooled
# spatial distribution per output side. The pooled histogram for one
# (animal, dates, output_side) sums :func:`compute_animal_aggregated_histogram`
# over every (landmark, trial_group) pair:
#   - ``landmarks``: which DLC bodypart columns feed the distribution
#     (e.g. the 3 whisker landmarks per anatomical side; both bilateral
#     spout/eye landmarks; the single tongue/jaw/nose landmark).
#   - ``trial_groups``: which tone trial-groups (cue sides) to pool frames
#     over. Anatomical-split + no-split recipes pool BOTH cue sides; the
#     cue-split recipes (tongue/jaw/nose) use the single output cue side.
#   - ``grid``: explicit shared (x_limits, y_limits) bin grid so all pooled
#     landmarks histogram on identical bins (load-bearing for whiskers,
#     whose per-landmark config extents differ). None = use per-bp config
#     (single-landmark recipes only).
#
# tongue/jaw recipes reproduce the legacy single-bodypart, cue-split,
# v7-cleaned behavior exactly (1 landmark × 1 trial_group, no grid
# override) so existing Q12 output is byte-identical.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpatialBodypartRecipe:
    """How to build a logical bodypart's pooled spatial distribution.

    Attributes
    ----------
    name : str
        Logical bodypart name (``"tongue"``, ``"whisker"``, ``"spout"`` …).
    center_mode : str
        Centering frame (``"spout_midpoint"`` or ``"eye_midpoint"``).
    use_v7_cleaned : bool
        ``True`` for tongue/jaw (v7/v3.4 cleaned-trace substrate); ``False``
        for whisker/nose/spout/eye (raw DLC — path A; no cleaned-traces
        parquets exist).
    side_split : str
        ``"cue"`` (split by tone trial-group; tongue/jaw/nose),
        ``"anatomical"`` (split by landmark side; whisker), or ``"none"``
        (single pooled distribution; spout/eye).
    output_sides : tuple[str, ...]
        Side keys this recipe emits — ``("L", "R")`` for split recipes,
        ``("both",)`` for no-split.
    landmarks_by_side : dict[str, tuple[str, ...]]
        DLC landmark columns to pool, per output side.
    trial_groups_by_side : dict[str, tuple[str, ...]]
        Tone trial-groups (cue sides) to pool frames over, per output side.
    grid : tuple[tuple[float, float], tuple[float, float]] | None
        Explicit ``((x_lo, x_hi), (y_lo, y_hi))`` shared bin grid, or None
        to use each landmark's per-bp config extent.
    """

    name: str
    center_mode: str
    use_v7_cleaned: bool
    side_split: str
    output_sides: tuple[str, ...]
    landmarks_by_side: dict[str, tuple[str, ...]]
    trial_groups_by_side: dict[str, tuple[str, ...]]
    grid: tuple[tuple[float, float], tuple[float, float]] | None


# Shared bin grids (Addendum #2). Whisker = Q37 unified bilateral range on
# L_whiskers_1; nose/spout/eye from configs/defaults.yaml per_center_mode.
_WHISKER_GRID = ((-200.0, 200.0), (50.0, 360.0))
_NOSE_GRID = ((-100.0, 95.0), (100.0, 330.0))
_SPOUT_GRID = ((-100.0, 100.0), (-20.0, 20.0))
_EYE_GRID = ((-160.0, 160.0), (-20.0, 20.0))

_BOTH_CUE_SIDES: tuple[str, str] = ("L", "R")

SPATIAL_BODYPART_RECIPES: dict[str, SpatialBodypartRecipe] = {
    # Legacy cue-split single-landmark recipes (byte-identical to pre-chore).
    "tongue": SpatialBodypartRecipe(
        name="tongue", center_mode="spout_midpoint", use_v7_cleaned=True,
        side_split="cue", output_sides=("L", "R"),
        landmarks_by_side={"L": ("tongue",), "R": ("tongue",)},
        trial_groups_by_side={"L": ("L",), "R": ("R",)},
        grid=None,
    ),
    "jaw": SpatialBodypartRecipe(
        name="jaw", center_mode="eye_midpoint", use_v7_cleaned=True,
        side_split="cue", output_sides=("L", "R"),
        landmarks_by_side={"L": ("jaw",), "R": ("jaw",)},
        trial_groups_by_side={"L": ("L",), "R": ("R",)},
        grid=None,
    ),
    # Whisker: anatomical L/R split, 3 landmarks pooled per side, frames
    # pooled across both cue sides, raw DLC, shared bilateral grid. The
    # ``"both"`` output side pools all 6 landmarks into one bilateral
    # distribution — used for the proportion_diff HEATMAP ("plot all
    # whiskers together"; L whiskers sit at +x, R at -x in the eye-centered
    # frame, so one map shows both sides spatially separated). The ``"L"`` /
    # ``"R"`` sides (3 landmarks each) drive the per-side W-2 STATISTICS
    # ("run statistics differently for L and R"). Addendum #2.
    "whisker": SpatialBodypartRecipe(
        name="whisker", center_mode="eye_midpoint", use_v7_cleaned=False,
        side_split="anatomical", output_sides=("L", "R", "both"),
        landmarks_by_side={
            "L": ("L_whiskers_1", "L_whiskers_2", "L_whiskers_3"),
            "R": ("R_whiskers_1", "R_whiskers_2", "R_whiskers_3"),
            "both": ("L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
                     "R_whiskers_1", "R_whiskers_2", "R_whiskers_3"),
        },
        trial_groups_by_side={
            "L": _BOTH_CUE_SIDES, "R": _BOTH_CUE_SIDES,
            "both": _BOTH_CUE_SIDES,
        },
        grid=_WHISKER_GRID,
    ),
    # Nose: single midline landmark, cue-split (ipsi/contra trials), raw DLC.
    "nose": SpatialBodypartRecipe(
        name="nose", center_mode="eye_midpoint", use_v7_cleaned=False,
        side_split="cue", output_sides=("L", "R"),
        landmarks_by_side={"L": ("nose",), "R": ("nose",)},
        trial_groups_by_side={"L": ("L",), "R": ("R",)},
        grid=_NOSE_GRID,
    ),
    # Spout: both bilateral landmarks pooled, all trials, no split, raw DLC.
    "spout": SpatialBodypartRecipe(
        name="spout", center_mode="spout_midpoint", use_v7_cleaned=False,
        side_split="none", output_sides=("both",),
        landmarks_by_side={"both": ("L_spout", "R_spout")},
        trial_groups_by_side={"both": _BOTH_CUE_SIDES},
        grid=_SPOUT_GRID,
    ),
    # Eye: both bilateral landmarks pooled, all trials, no split, raw DLC.
    "eye": SpatialBodypartRecipe(
        name="eye", center_mode="eye_midpoint", use_v7_cleaned=False,
        side_split="none", output_sides=("both",),
        landmarks_by_side={"both": ("L_eye", "R_eye")},
        trial_groups_by_side={"both": _BOTH_CUE_SIDES},
        grid=_EYE_GRID,
    ),
}


def get_spatial_recipe(bodypart: str) -> SpatialBodypartRecipe:
    """Look up a bodypart's pooling recipe.

    Raises
    ------
    ValueError
        If ``bodypart`` is not a registered logical bodypart.
    """
    try:
        return SPATIAL_BODYPART_RECIPES[bodypart]
    except KeyError:
        raise ValueError(
            f"bodypart {bodypart!r} has no spatial recipe; expected one of "
            f"{tuple(SPATIAL_BODYPART_RECIPES)}.",
        ) from None


def compute_pooled_recipe_histogram(
    animal: str,
    dates: Sequence[dt.date],
    recipe: SpatialBodypartRecipe,
    output_side: str,
    resolver: PathResolver,
    *,
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    use_v7_cleaned: bool | None = None,
) -> tuple[np.ndarray | None, list[float] | None, int, int, int]:
    """Pool ``compute_animal_aggregated_histogram`` over landmark × trial_group.

    Sums the per-``(landmark, trial_group)`` count histograms cell-wise (the
    same Pattern-A pooling method as
    :func:`~stroke_orofacial.dlc_spatial.render_on_demand._aggregate_for_dates_pooled_bodyparts`),
    returning the same 5-tuple shape as
    :func:`compute_animal_aggregated_histogram`:
    ``(H_total, extent, n_sessions, n_tones, n_total_frames)``.

    Denominator semantics (Addendum #2): ``n_total_frames`` is summed over
    EVERY (landmark, trial_group) call, so it inflates by ``n_landmarks``
    to match the ``n_landmarks``-fold inflation of the summed counts — the
    pooled proportion ``H_total / n_total_frames`` stays a per-landmark-sample
    fraction ≤ 1. ``n_tones`` is landmark-independent, so it is counted ONCE
    per trial_group (summed across the pooled cue sides) rather than per
    landmark.

    Returns ``(None, None, 0, 0, 0)`` when nothing contributes.
    """
    if use_v7_cleaned is None:
        use_v7_cleaned = recipe.use_v7_cleaned
    if output_side not in recipe.landmarks_by_side:
        raise ValueError(
            f"output_side {output_side!r} not valid for recipe "
            f"{recipe.name!r}; expected one of {recipe.output_sides}.",
        )
    landmarks = recipe.landmarks_by_side[output_side]
    trial_groups = recipe.trial_groups_by_side[output_side]
    if recipe.grid is not None:
        x_limits: tuple[float, float] | None = recipe.grid[0]
        y_limits: tuple[float, float] | None = recipe.grid[1]
    else:
        x_limits = y_limits = None

    H_total: np.ndarray | None = None
    extent: list[float] | None = None
    n_sess_max = 0
    n_tones_total = 0
    n_total_summed = 0
    date_list = list(dates)
    for tg in trial_groups:
        tg_n_tones: int | None = None
        for landmark in landmarks:
            H, ext, n_sess, n_tones, n_total = compute_animal_aggregated_histogram(
                animal, date_list, landmark, recipe.center_mode, resolver,
                trial_group=tg, window_ms=TASK5_TONE_WINDOW_MS,
                defaults=defaults, animal_info=animal_info,
                use_v7_cleaned=use_v7_cleaned,
                x_limits=x_limits, y_limits=y_limits,
            )
            n_total_summed += int(n_total)
            n_sess_max = max(n_sess_max, int(n_sess))
            # n_tones is bodypart-independent: record once per trial_group.
            if tg_n_tones is None and int(n_total) > 0:
                tg_n_tones = int(n_tones)
            if H is None:
                continue
            if H_total is None:
                H_total = H.copy()
                extent = list(ext) if ext is not None else None
            else:
                H_total += H
        if tg_n_tones is not None:
            n_tones_total += tg_n_tones
    return H_total, extent, n_sess_max, n_tones_total, n_total_summed


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
    use_v7_cleaned: bool | None = None,
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
    recipe = get_spatial_recipe(bodypart)
    if side not in recipe.output_sides:
        raise ValueError(
            f"side {side!r} not valid for bodypart {bodypart!r}; expected "
            f"one of {recipe.output_sides}.",
        )
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

    H_pre, extent, n_pre_sessions, n_pre_trials, n_total_pre_frames = (
        compute_pooled_recipe_histogram(
            animal, list(pre_dates), recipe, side, resolver,
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
    use_v7_cleaned: bool | None = None,
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
        ``{"D", "extent", "H_post_counts", "n_post_sessions",
        "n_post_trials", "n_total_post_frames", "n_pre_sessions",
        "n_pre_trials", "n_total_pre_frames"}``.
        The pre-side counts are echoed from ``pre_pool`` so a downstream
        per-panel annotation can read them off this dict alone.
        ``H_post_counts`` is also returned so downstream stats (e.g.,
        Addendum #5 W-2) can re-use the post-epoch histogram without
        re-calling :func:`compute_animal_aggregated_histogram`.
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

    recipe = get_spatial_recipe(bodypart)
    H_post, extent_post, n_post_sessions, n_post_trials, n_total_post_frames = (
        compute_pooled_recipe_histogram(
            animal, list(epoch_dates), recipe, side, resolver,
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
        "H_post_counts": H_post,
        "n_post_sessions": int(n_post_sessions),
        "n_post_trials": int(n_post_trials),
        "n_total_post_frames": int(n_total_post_frames),
        "n_pre_sessions": int(pre_pool["n_pre_sessions"]),
        "n_pre_trials": int(pre_pool["n_pre_trials"]),
        "n_total_pre_frames": int(pre_pool["n_total_pre_frames"]),
    }


def compute_per_animal_pre_self_diff(
    animal: str,
    bodypart: str,
    side: str,
    pre_pool: dict[str, Any],
    resolver: PathResolver,
    *,
    pre_dates: list[dt.date],
    defaults: dict[str, Any] | None = None,
    animal_info: AnimalInfo | None = None,
    use_v7_cleaned: bool | None = None,
) -> dict[str, Any] | None:
    """Compute per-animal Pre-self proportion-diff (Q12-O Addendum #7).

    For each pre-stroke session, compute the single-session D against the
    animal's pre-pool: ``D_i = P(session_i) − P(pre_pool)``. Average D
    arrays across the animal's pre sessions (NaN-aware ``np.nanmean``
    along the session axis).

    Per Q-lock 12a Addendum #6 v1 "naive" lock (inherited): each pre
    session is INCLUDED in its own reference pool. The bias toward 0 is
    proportional to ``1/n_pre_sessions`` and is consistent across animals,
    making the resulting D̄ a calibrated "no-shift" reference at the
    same per-animal averaging depth as the post-epoch panels.

    Returns ``None`` when no pre session contributes a histogram
    (missing parquets etc.).

    Returns
    -------
    dict or None
        ``{"D", "extent", "n_pre_sessions_contributing",
        "n_pre_trials", "n_total_pre_frames"}``.
    """
    if defaults is None:
        defaults = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)
    if not pre_dates:
        return None

    recipe = get_spatial_recipe(bodypart)
    H_pre_pool = pre_pool["H_pre_counts"]
    n_total_pre = int(pre_pool["n_total_pre_frames"])

    D_stack: list[np.ndarray] = []
    n_sess_contributed = 0
    for d in pre_dates:
        H_sess, ext_sess, _n_sess, _n_tones, n_total_sess = (
            compute_pooled_recipe_histogram(
                animal, [d], recipe, side, resolver,
                defaults=defaults, animal_info=animal_info,
                use_v7_cleaned=use_v7_cleaned,
            )
        )
        if H_sess is None or n_total_sess == 0:
            continue
        D_i = compute_proportion_diff_within(
            H_pre_pool, n_total_pre, H_sess, int(n_total_sess),
        )
        D_stack.append(D_i)
        n_sess_contributed += 1

    if not D_stack:
        return None

    stack = np.stack(D_stack, axis=0)
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.filterwarnings(
            "ignore", message="Mean of empty slice", category=RuntimeWarning,
        )
        D_mean = np.nanmean(stack, axis=0)

    extent = pre_pool["extent"]
    return {
        "D": D_mean,
        "extent": extent,
        "n_pre_sessions_contributing": int(n_sess_contributed),
        "n_pre_trials": int(pre_pool["n_pre_trials"]),
        "n_total_pre_frames": int(n_total_pre),
    }


__all__ = [
    "BODYPART_CENTER_MODES",
    "POST_EPOCHS",
    "SIDES",
    "SPATIAL_BODYPART_RECIPES",
    "SpatialBodypartRecipe",
    "compute_per_animal_per_epoch_diff",
    "compute_per_animal_pre_pool",
    "compute_per_animal_pre_self_diff",
    "compute_pooled_recipe_histogram",
    "compute_proportion_diff_within",
    "get_spatial_recipe",
    "split_post_dates_by_epoch",
]
