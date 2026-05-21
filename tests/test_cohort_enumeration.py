"""Tests for :mod:`stroke_orofacial.cohort_enumeration` (Q67, Phase 7c.2
Task 7 Addendum #57).

The function under test replaces the legacy filesystem-walk enumeration
pattern in the 3 Phase 7c.2 cohort drivers with pure YAML-driven date
iteration. Tests assert:

1. Phase D output dates ⊆ YAML enumeration for each of the 8 cohort
   animals (parity check; YAML is the superset because recording-day
   gaps mean Phase D's filesystem walk emitted on a subset of in-range
   dates).
2. Exclusions whose ``applies_to`` covers ``dlc`` are filtered out.
3. PS48/2025-03-14 (Pattern A multi-half) is included by virtue of
   being in PS48's YAML range.
4. ``session_start`` and ``session_end`` are both inclusive.
5. start > end yields an empty list.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from stroke_orofacial.animals import AnimalInfo, Exclusion, get_animal
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.paths import PathResolver


COHORT = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
_PHASE_D_SVG_PATTERN = re.compile(r"^(\d{8})\.svg$")


def _phase_d_dates_for_animal(animal: str) -> set[dt.date]:
    """Ground truth: enumerate Phase D's actual per-animal date set from
    the canonical ``tone_aligned_heatmaps/<animal>/<family>/individual_session/<date>.svg``
    output tree. Returns the union across all family entries.
    """
    resolver = PathResolver()
    animal_root = (
        resolver.pipeline_outputs("dlc_kinematics")
        / "tone_aligned_heatmaps"
        / animal
    )
    if not animal_root.exists():
        return set()
    out: set[dt.date] = set()
    for family_dir in animal_root.iterdir():
        if not family_dir.is_dir():
            continue
        is_dir = family_dir / "individual_session"
        if not is_dir.exists():
            continue
        for svg in is_dir.iterdir():
            m = _PHASE_D_SVG_PATTERN.match(svg.name)
            if not m:
                continue
            ds = m.group(1)
            out.add(dt.date(int(ds[0:4]), int(ds[4:6]), int(ds[6:8])))
    return out


@pytest.mark.parametrize("animal", COHORT)
def test_phase_d_dates_subset_of_yaml_enumeration(animal):
    """Parity check: every date Phase D actually emitted for is in the
    YAML enumeration. YAML may legitimately include extra in-range dates
    that Phase D's filesystem walk skipped (no upstream DLC inference
    output on non-recording days) — those are recorded in
    ``dates_only_in_yaml`` but don't fail the test.
    """
    phase_d_dates = _phase_d_dates_for_animal(animal)
    if not phase_d_dates:
        pytest.skip(
            f"{animal}: no Phase D output dir on disk (test requires the "
            f"production output tree to be reachable)."
        )
    yaml_dates = set(yaml_driven_session_dates(animal))

    in_phase_d_only = phase_d_dates - yaml_dates
    in_yaml_only = yaml_dates - phase_d_dates

    assert not in_phase_d_only, (
        f"{animal}: Phase D emitted for {len(in_phase_d_only)} date(s) "
        f"OUTSIDE the YAML enumeration. This is a bug — every Phase D "
        f"date must be in [session_start, session_end] and not "
        f"excluded.\n"
        f"Phase D only: {sorted(in_phase_d_only)}\n"
        f"YAML enumeration: {len(yaml_dates)} dates "
        f"({sorted(yaml_dates)[0]} … {sorted(yaml_dates)[-1]}).\n"
    )
    # Inform but don't fail on YAML-only dates (non-recording days within range).
    if in_yaml_only:
        print(
            f"\n{animal}: YAML enumeration ({len(yaml_dates)}) is superset "
            f"of Phase D output ({len(phase_d_dates)}). "
            f"{len(in_yaml_only)} date(s) only in YAML — these are non-"
            f"recording days in range:\n  {sorted(in_yaml_only)}"
        )


def _synthetic_animal(
    animal_id: str,
    start: dt.date,
    end: dt.date,
    exclusions: list[Exclusion] | None = None,
) -> AnimalInfo:
    """Construct a minimal AnimalInfo for unit tests."""
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=start,  # arbitrary; not exercised by enumeration
        session_start=start,
        session_end=end,
        exclusions=exclusions or [],
        kinematics_baselines={
            "tongue": {"x0": 0.0, "y0": 0.0},
            "jaw": {"x0": 0.0, "y0": 0.0},
        },
    )


def test_excluded_sessions_skipped():
    """A synthetic animal with a mid-range exclusion whose applies_to
    covers ``dlc`` should NOT include the excluded date in the
    enumeration result."""
    excluded_date = dt.date(2025, 4, 16)
    info = _synthetic_animal(
        "PSX",
        start=dt.date(2025, 4, 14),
        end=dt.date(2025, 4, 18),
        exclusions=[
            Exclusion(
                date=excluded_date,
                reason="test exclusion",
                applies_to=["dlc"],
            ),
        ],
    )
    dates = yaml_driven_session_dates(
        "PSX", animal_info=info, analysis_context="dlc",
    )
    assert excluded_date not in dates, (
        f"Excluded date {excluded_date} should NOT be in YAML "
        f"enumeration, but got: {dates}"
    )
    # Other dates in range should still be present.
    assert dt.date(2025, 4, 14) in dates
    assert dt.date(2025, 4, 15) in dates
    assert dt.date(2025, 4, 17) in dates
    assert dt.date(2025, 4, 18) in dates
    assert len(dates) == 4


def test_ps48_pattern_a_inclusion():
    """PS48/2025-03-14 (the Pattern A multi-half session) is in PS48's
    YAML range and should be included naturally (no special-case
    branching needed)."""
    dates = yaml_driven_session_dates("PS48")
    assert dt.date(2025, 3, 14) in dates, (
        f"PS48 enumeration must include the Pattern A multi-half "
        f"session 2025-03-14. Got {len(dates)} dates: "
        f"{dates[:3]} ... {dates[-3:]}"
    )


def test_boundary_inclusivity():
    """Both ``session_start`` and ``session_end`` must be inclusive."""
    start = dt.date(2025, 5, 1)
    end = dt.date(2025, 5, 3)
    info = _synthetic_animal("PSX", start=start, end=end)
    dates = yaml_driven_session_dates("PSX", animal_info=info)
    assert dates == [
        dt.date(2025, 5, 1),
        dt.date(2025, 5, 2),
        dt.date(2025, 5, 3),
    ]


def test_empty_range_when_start_after_end():
    """A pathological AnimalInfo with start > end yields an empty list
    (no exception). Defensive against typos in animals.yaml."""
    info = _synthetic_animal(
        "PSX",
        start=dt.date(2025, 5, 5),
        end=dt.date(2025, 5, 1),
    )
    dates = yaml_driven_session_dates("PSX", animal_info=info)
    assert dates == []


def test_analysis_context_scoping():
    """An exclusion whose applies_to does NOT cover the caller's
    analysis_context should be ignored. Verifies the prefix-match
    semantics from :meth:`Exclusion.applies`."""
    excluded_date = dt.date(2025, 4, 16)
    info = _synthetic_animal(
        "PSX",
        start=dt.date(2025, 4, 14),
        end=dt.date(2025, 4, 18),
        exclusions=[
            Exclusion(
                date=excluded_date,
                reason="spout-only test exclusion",
                applies_to=["spout_behavior"],  # NOT dlc
            ),
        ],
    )
    # Default analysis_context="dlc" → exclusion does not apply.
    dates = yaml_driven_session_dates("PSX", animal_info=info)
    assert excluded_date in dates, (
        f"Exclusion scoped to spout_behavior should NOT filter out "
        f"{excluded_date} when analysis_context='dlc'. Got: {dates}"
    )
