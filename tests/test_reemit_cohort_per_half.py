"""Per-half cohort-planning tests for the v7/jaw re-emit drivers.

Chore ``substrate-routing-and-secondary-spout-per-half-fix`` (2026-05-31)
removed the per-DATE ``secondary_spout_sessions:`` skip from the four cohort
re-emit drivers. The skip wrongly dropped the BARE half of Pattern B dates
(a normal primary-spout DLC session) along with the b half. These tests pin
the post-fix planner behavior:

- the planner now enumerates ALL ``dlc`` dates (incl. secondary-spout bare
  dates) — no per-date drop;
- excluded dates (e.g. PS55 2025-04-28, hard-excluded in animals.yaml) stay
  absent — dropped upstream by the ``dlc`` exclusion filter, not by a
  secondary-spout skip;
- the plan for a non-Pattern-B animal is byte-identical to the bare
  ``yaml_driven_session_dates`` enumeration (the unaffected-session safety
  property — removing the skip changed nothing for non-Pattern-B sessions).

The drivers are scripts, so they are loaded by file path via importlib.
"""
from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates

_REPO_ROOT = Path(__file__).resolve().parents[1]

_DRIVER_PATHS = {
    "tongue_pertrial": _REPO_ROOT
    / "scripts" / "phase_7e" / "reemit_tongue_pertrial_cohort.py",
    "jaw_pertrial": _REPO_ROOT
    / "scripts" / "phase_7f" / "reemit_jaw_pertrial_cohort.py",
}


def _load_driver(name: str) -> ModuleType:
    """Import a re-emit driver script by file path."""
    path = _DRIVER_PATHS[name]
    spec = importlib.util.spec_from_file_location(f"_driver_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=sorted(_DRIVER_PATHS))
def driver(request):
    return _load_driver(request.param)


# PS51 mod-severe secondary-spout BARE dates with DLC (must now be planned).
_PS51_SECONDARY_BARE = [datetime.date(2025, 4, 30), datetime.date(2025, 5, 5)]


class TestPerHalfPlanner:
    def test_secondary_spout_bare_dates_now_planned(self, driver):
        """The bare half of PS51 secondary-spout dates is enumerated — the
        per-date skip is gone."""
        plan = driver._iter_planned_sessions(("PS51",))
        planned_dates = {d for (_a, d) in plan}
        for d in _PS51_SECONDARY_BARE:
            assert d in planned_dates, (
                f"PS51 {d} (secondary-spout bare half) missing from plan — "
                f"per-date skip not fully removed in {driver.__name__}"
            )

    def test_ps55_0428_absent_from_plan(self, driver):
        """PS55 2025-04-28 is hard-excluded (animals.yaml dlc exclusion) and
        must NOT appear, even though the secondary-spout skip is gone."""
        plan = driver._iter_planned_sessions(("PS55",))
        assert ("PS55", datetime.date(2025, 4, 28)) not in plan

    def test_plan_equals_unfiltered_dlc_enumeration(self, driver):
        """UNAFFECTED-SESSION SAFETY: the planner now returns exactly the
        ``yaml_driven_session_dates`` enumeration with no extra filtering, for
        a non-Pattern-B animal (PS46) AND for a Pattern-B animal (PS51). This
        is the byte-identical-on-unaffected-sessions guarantee."""
        for animal in ("PS46", "PS51"):
            plan = driver._iter_planned_sessions((animal,))
            expected = [
                (animal, d)
                for d in yaml_driven_session_dates(animal, analysis_context="dlc")
            ]
            assert plan == expected
