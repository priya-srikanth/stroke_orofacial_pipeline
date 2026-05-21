"""YAML-driven session date enumeration for cohort drivers.

Q67 (Phase 7c.2 Task 7, Addendum #57) — single source of truth for the
3 Phase 7c.2 cohort drivers that previously walked the
``pipeline_outputs/dlc_analysis/spatial_reward_aligned/<bp>/<win>/<animal>/``
NPZ tree to discover session dates and then applied post-hoc YAML range
filtering.

Replaces the legacy filesystem-walk pattern with pure YAML-driven date
iteration. Eliminates the spatial_reward_aligned/ tree dependency that
blocked Cat 1 cleanup (Q5.F category 1 — ~2 GB of cached NPZ files).

Consumers: scripts/phase_7c2/render_heatmaps.py,
scripts/phase_7c2/reemit_cohort.py,
scripts/phase_7c2/reemit_cohort_aggregates.py.
"""
from __future__ import annotations

import datetime

from stroke_orofacial.animals import AnimalInfo, get_animal


def yaml_driven_session_dates(
    animal: str,
    animal_info: AnimalInfo | None = None,
    analysis_context: str = "dlc",
) -> list[datetime.date]:
    """Enumerate session dates for an animal from animals.yaml ranges.

    Pure YAML-driven; no filesystem dependencies. Iterates every date in
    ``[session_start, session_end]`` inclusive and filters out
    exclusions whose ``applies_to`` matches ``analysis_context`` per
    :meth:`stroke_orofacial.animals.Exclusion.applies` prefix-match
    semantics.

    Pattern A multi-half sessions (PS48/2025-03-14 per
    ``configs/session_overrides.yaml`` ``multi_half_sessions:``) are
    naturally included by virtue of being in PS48's YAML range —
    enumeration is by date, and the multi-half merging happens at the
    manifest-construction layer downstream.

    Pattern B secondary-spout sessions (PS51/PS54/PS55 b-half acquisitions
    per ``secondary_spout_sessions:``) do NOT add new dates; they yield
    additional per-date manifest variants. Date enumeration is unaffected.

    Out-of-YAML-range orphan sessions (e.g., PS51/PS54/PS55 ×
    2025-04-16/17/18 per Q1.C correction) are naturally excluded —
    those dates fall before the animal's ``session_start``
    (2025-04-21 for PS51/54/55).

    Parameters
    ----------
    animal : str
        Animal ID, e.g. ``"PS46"``.
    animal_info : AnimalInfo, optional
        Pre-loaded AnimalInfo; if ``None``, loaded via
        :func:`stroke_orofacial.animals.get_animal`.
    analysis_context : str, default ``"dlc"``
        Dotted analysis-context tag for exclusion filtering. Default
        ``"dlc"`` matches all ``dlc.*`` sub-contexts (e.g.
        ``dlc.spatial``, ``dlc.kinematics``). Q67 cohort drivers run
        under the DLC analysis tag.

    Returns
    -------
    list[datetime.date]
        Sorted list of session dates in
        ``[animal_info.session_start, animal_info.session_end]`` for
        which no matching exclusion applies.
    """
    if animal_info is None:
        animal_info = get_animal(animal)

    dates: list[datetime.date] = []
    d = animal_info.session_start
    one_day = datetime.timedelta(days=1)
    while d <= animal_info.session_end:
        excluded, _ = animal_info.is_excluded(
            d, analysis_context=analysis_context,
        )
        if not excluded:
            dates.append(d)
        d += one_day
    return dates
