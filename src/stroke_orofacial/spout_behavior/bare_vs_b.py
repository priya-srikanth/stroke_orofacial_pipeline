"""Phase 8a.10 sub-deliverable B — bare-vs-b comparison.

Scope: post-stroke comparison of bare-half (single-spout) vs b-half
(secondary-spout) session conditions for the 14 Pattern B sessions
across PS51, PS54, PS55. Five endpoints (per kickoff 2026-05-13):

  1. First-lick accuracy (per-session bar + cohort recovery curve)
  2. Correct/incorrect licks per side (faceted bar + cohort curve)
  3. Lick raster (side-by-side; no cohort aggregation)
  4. First-lick latency (side-by-side distributions + cohort curve)
  5. Reward acquisition rate over time (NEW; cohort curve)

This commit-group (CG-B1) ships only the shared infrastructure:
the :class:`SessionPairData` dataclass and the
:func:`iter_cohort_b_sessions` generator. Per-session renderers
(CG-B2) and per-animal cohort recovery curves (CG-B3) follow in
later commits.

Cohort B (Pattern B) registry lives in
``configs/session_overrides.yaml`` under ``secondary_spout_sessions:``.
This module reads that registry, filters to post-stroke sessions
(:meth:`AnimalInfo.day_relative_to_stroke` ``>= 2``; cuts both d0
and d+1 — Priya 2026-05-13), and pairs each survivor's bare half
with its b half via :func:`load_session_plot_data` (extended for
this phase to accept a ``half_suffix`` kwarg).

Filter convention note: ``rel_day >= 2`` (NOT ``>= 1``). The d+1
session is the immediate stroke-aftermath day and is excluded
alongside d0. Filter intent is "strictly post first post-stroke
day". DECISIONS-entry deferred to phase wrap.

Forward-pointer to Phase 8a.10.1
--------------------------------
Endpoint 5 ("reward acquisition rate over time") currently plots
tone-cue acquisition rate, not reward-acquisition rate, due to the
deferred Tone↔Reward swap (Phase 8a.10.1). Renderer code is
faithful; underlying data is mis-labeled until 8a.10.1's re-emit.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.visual_gate import (
    SessionPlotData,
    load_session_plot_data,
)


# Post-stroke filter cutoff. Priya 2026-05-13: rel_day >= 2 — drops
# both d0 (e.g. PS54/2025-04-30) AND d+1 (e.g. PS51/2025-04-30).
# Treat d+1 as immediate stroke-aftermath, not recovery. Cuts the
# cohort from 19 (pre-filter) to 14 (post-filter).
COHORT_B_REL_DAY_MIN = 2


@dataclass
class SessionPairData:
    """Per-session bare-vs-b paired inputs.

    Attributes
    ----------
    animal : str
        e.g. ``"PS55"``.
    date : datetime.date
        Session date.
    bare : SessionPlotData
        Bare-half Phase-2 + Phase-1 inputs (single-spout
        condition; read with ``half_suffix=""``).
    b : SessionPlotData
        B-half Phase-2 + Phase-1 inputs (secondary-spout
        condition; read with ``half_suffix="b"`` from
        ``licks_and_rewards/<animal>/<YYYYMMDD>b.npz``).
    """

    animal: str
    date: datetime.date
    bare: SessionPlotData
    b: SessionPlotData


def _iso_to_yyyymmdd(iso: str) -> str:
    """Convert ``"YYYY-MM-DD"`` (registry key form) → ``"YYYYMMDD"``."""
    return iso.replace("-", "")


def _iso_to_date(iso: str) -> datetime.date:
    return datetime.date.fromisoformat(iso)


def iter_cohort_b_session_keys(
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
    *,
    animals: list[str] | None = None,
    require_on_disk: bool = True,
    animal_info_cache: dict[str, AnimalInfo] | None = None,
) -> Iterator[tuple[str, datetime.date]]:
    """Yield (animal, date) keys for the filtered Cohort B.

    Same filter logic as :func:`iter_cohort_b_sessions` but does NOT
    load NPZs — pure registry walk + filter. Use this for tests that
    probe the iteration order/filter without needing on-disk data,
    or for orchestrator code that just needs to count or enumerate
    the cohort.

    Parameters mirror :func:`iter_cohort_b_sessions`; see that
    function's docstring.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    secondary = overrides_config.get("secondary_spout_sessions", {}) or {}

    if animals is None:
        target_animals = sorted(secondary.keys())
    else:
        target_animals = [a for a in animals if a in secondary]

    if animal_info_cache is None:
        animal_info_cache = {}

    sp_root = resolver.pipeline_outputs("spout_behavior")

    for animal in target_animals:
        if animal not in animal_info_cache:
            animal_info_cache[animal] = get_animal(animal)
        info = animal_info_cache[animal]

        iso_dates = sorted(secondary[animal].keys())
        for iso in iso_dates:
            date = _iso_to_date(iso)
            if info.day_relative_to_stroke(date) < COHORT_B_REL_DAY_MIN:
                continue

            date_str = _iso_to_yyyymmdd(iso)
            if require_on_disk:
                # b-half existence gate. Both bare and b NPZs are
                # under licks_and_rewards/<animal>/. For Pattern B
                # (which all Cohort B entries are by construction),
                # bare is at <date_str>.npz and b is at <date_str>b.npz.
                bare_npz = sp_root / "licks_and_rewards" / animal / f"{date_str}.npz"
                b_npz = sp_root / "licks_and_rewards" / animal / f"{date_str}b.npz"
                if not bare_npz.exists() or not b_npz.exists():
                    continue

            yield animal, date


def iter_cohort_b_sessions(
    resolver: PathResolver,
    overrides_config: dict[str, Any] | None = None,
    *,
    animals: list[str] | None = None,
    require_on_disk: bool = True,
    animal_info_cache: dict[str, AnimalInfo] | None = None,
) -> Iterator[SessionPairData]:
    """Yield bare-vs-b paired session data for the filtered Cohort B.

    Walks the ``secondary_spout_sessions:`` registry in
    ``configs/session_overrides.yaml``. For each ``(animal, iso_date)``
    entry whose ``rel_day >= COHORT_B_REL_DAY_MIN`` (= 2), loads the
    bare-half and b-half Phase-2 NPZs and yields a
    :class:`SessionPairData` carrying both.

    Skip rules (silent):
      - Pre-filter rel_day < 2 (i.e. baseline, d0, or d+1) — these
        Pattern B entries exist in the registry but pre-stroke
        comparisons aren't part of sub-deliverable B's scope.
      - The b-half NPZ doesn't exist on disk (``require_on_disk=True``)
        — e.g. pre-stroke Pattern B sessions whose b half was never
        recorded.

    Parameters
    ----------
    resolver : PathResolver
        For Phase-2 NPZ path resolution.
    overrides_config : dict, optional
        Pre-loaded ``session_overrides.yaml`` mapping (the dict, not
        the file path). ``None`` loads via
        :func:`stroke_orofacial.config_loader.load_session_overrides`.
    animals : list of str, optional
        Restrict to a subset of the cohort. Default ``None`` walks all
        registered animals. Used for the PS55 pilot
        (``animals=["PS55"]`` yields exactly 3 SessionPairData).
    require_on_disk : bool, default True
        Skip sessions whose b-half NPZ doesn't exist on disk. Set
        ``False`` for tests that probe the registry without populating
        the filesystem.
    animal_info_cache : dict, optional
        Optional pre-loaded ``{animal: AnimalInfo}`` map; the loader
        otherwise calls :func:`get_animal` once per animal. Pass when
        testing with synthetic AnimalInfo records (e.g.
        ``stroke_date`` overrides).

    Yields
    ------
    SessionPairData
        Sorted by (animal_id, date) ascending. ``bare`` and ``b``
        fields come from :func:`load_session_plot_data` with
        ``half_suffix=""`` and ``half_suffix="b"`` respectively.
    """
    for animal, date in iter_cohort_b_session_keys(
        resolver, overrides_config,
        animals=animals,
        require_on_disk=require_on_disk,
        animal_info_cache=animal_info_cache,
    ):
        date_str = date.strftime("%Y%m%d")
        bare = load_session_plot_data(
            animal, date_str, resolver,
            overrides_config=overrides_config,
        )
        b = load_session_plot_data(
            animal, date_str, resolver,
            overrides_config=overrides_config,
            half_suffix="b",
        )
        yield SessionPairData(
            animal=animal, date=date, bare=bare, b=b,
        )


def list_cohort_b_animals(
    overrides_config: dict[str, Any] | None = None,
) -> list[str]:
    """Return sorted Cohort B animal IDs from the registry.

    Convenience helper for the orchestrator notebook to default
    ``ANIMALS_BARE_VS_B`` to all registered animals.
    """
    if overrides_config is None:
        overrides_config = load_session_overrides()
    secondary = overrides_config.get("secondary_spout_sessions", {}) or {}
    return sorted(secondary.keys())


__all__ = [
    "COHORT_B_REL_DAY_MIN",
    "SessionPairData",
    "iter_cohort_b_session_keys",
    "iter_cohort_b_sessions",
    "list_cohort_b_animals",
]
