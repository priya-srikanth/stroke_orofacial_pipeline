"""Tests for stroke_orofacial.spout_behavior.bare_vs_b.

Phase 8a.10 sub-deliverable B, CG-B1 — shared infrastructure for
the bare-vs-b comparison work. Tests cover:

  - the post-stroke filter (rel_day >= 2)
  - the optional ``animals=`` subset filter (for the PS55 pilot)
  - graceful handling of pre-stroke n_dlc=0 entries
  - SessionPairData dataclass shape
  - PathResolver.bare_vs_b_dir method
"""

from __future__ import annotations

import datetime
import platform
from pathlib import Path

import numpy as np

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.bare_vs_b import (
    COHORT_B_REL_DAY_MIN,
    SessionPairData,
    iter_cohort_b_session_keys,
    iter_cohort_b_sessions,
    list_cohort_b_animals,
)
from stroke_orofacial.spout_behavior.visual_gate import SessionPlotData


_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


def _make_animal_info(
    animal_id: str,
    *,
    stroke_date: datetime.date,
    session_start: datetime.date | None = None,
    session_end: datetime.date | None = None,
) -> AnimalInfo:
    """Build a synthetic AnimalInfo with controlled stroke_date.

    session_start/end default to a 4-month window centered on
    stroke_date — wide enough to span all Cohort B test dates.
    """
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=stroke_date,
        session_start=(
            session_start or stroke_date - datetime.timedelta(days=60)
        ),
        session_end=(
            session_end or stroke_date + datetime.timedelta(days=120)
        ),
    )


def _real_registry() -> dict:
    """Build a snapshot of the real Cohort B registry (19 sessions
    pre-filter) suitable for passing as ``overrides_config``."""
    return {
        "secondary_spout_sessions": {
            "PS51": {
                "2025-04-24": {"bare_ws_subdir_override": "20250424a"},
                "2025-04-25": {"bare_ws_subdir_override": "20250425a"},
                "2025-04-30": {},
                "2025-05-05": {},
            },
            "PS54": {
                "2025-04-24": {"bare_ws_subdir_override": "20250424a"},
                "2025-04-25": {"bare_ws_subdir_override": "20250425a"},
                "2025-04-30": {},
                "2025-05-30": {},
                "2025-06-16": {},
                "2025-06-18": {},
                "2025-06-19": {},
                "2025-06-20": {},
                "2025-06-21": {},
                "2025-06-23": {},
                "2025-06-24": {},
                "2025-06-25": {},
                "2025-06-26": {},
            },
            "PS55": {
                "2025-04-24": {"bare_ws_subdir_override": "20250424a"},
                "2025-04-25": {"bare_ws_subdir_override": "20250425a"},
                "2025-04-28": {},
                "2025-04-30": {},
                "2025-05-30": {},
                "2025-06-01": {},
                "2025-06-05": {},
            },
        },
    }


def _real_animal_info_cache() -> dict[str, AnimalInfo]:
    """Build synthetic AnimalInfo for PS51/PS54/PS55 with stroke dates
    matching the real configs/animals.yaml."""
    return {
        "PS51": _make_animal_info(
            "PS51", stroke_date=datetime.date(2025, 4, 29),
        ),
        "PS54": _make_animal_info(
            "PS54", stroke_date=datetime.date(2025, 4, 30),
        ),
        "PS55": _make_animal_info(
            "PS55", stroke_date=datetime.date(2025, 4, 30),
        ),
    }


class TestCohortBSchemaConstants:
    def test_rel_day_filter_min_is_2(self):
        """Priya 2026-05-13: filter cuts both d0 AND d+1; the d+1
        session is immediate stroke-aftermath, not recovery."""
        assert COHORT_B_REL_DAY_MIN == 2

    def test_list_cohort_b_animals_from_real_registry(self):
        """The real configs/session_overrides.yaml registers 3
        animals in Cohort B: PS51, PS54, PS55."""
        animals = list_cohort_b_animals()
        assert animals == ["PS51", "PS54", "PS55"]


class TestIterCohortBSessionKeys:
    """Filter-only tests on iter_cohort_b_session_keys (no NPZ load).
    Uses synthetic AnimalInfo + the real registry shape."""

    def test_yields_14_total_with_real_filter(self, tmp_path):
        """Per the Priya 2026-05-13 amendment: post-filter cohort is
        14 sessions (PS51:1, PS54:10, PS55:3)."""
        resolver = PathResolver(output_root=tmp_path)
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=_real_registry(),
            animal_info_cache=_real_animal_info_cache(),
            require_on_disk=False,
        ))
        assert len(keys) == 14, (
            f"expected 14 post-filter sessions; got {len(keys)}: "
            f"{[(a, d.isoformat()) for a, d in keys]}"
        )

    def test_animals_filter_PS55_yields_3(self, tmp_path):
        """PS55 pilot scope: animals=['PS55'] yields exactly 3
        post-stroke sessions (2025-05-30, 2025-06-01, 2025-06-05)."""
        resolver = PathResolver(output_root=tmp_path)
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=_real_registry(),
            animal_info_cache=_real_animal_info_cache(),
            require_on_disk=False,
            animals=["PS55"],
        ))
        assert keys == [
            ("PS55", datetime.date(2025, 5, 30)),
            ("PS55", datetime.date(2025, 6, 1)),
            ("PS55", datetime.date(2025, 6, 5)),
        ]

    def test_filters_pre_stroke(self, tmp_path):
        """Synthetic AnimalInfo with stroke_date=2025-05-04. The
        rel_day >= 2 filter drops 2025-04-30 (rel_day=-4) and
        includes 2025-05-06 (rel_day=+2)."""
        resolver = PathResolver(output_root=tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS_TEST": {
                    "2025-04-30": {},  # rel_day=-4 -> drop
                    "2025-05-05": {},  # rel_day=+1 -> drop (d+1 cut)
                    "2025-05-06": {},  # rel_day=+2 -> keep
                    "2025-05-10": {},  # rel_day=+6 -> keep
                },
            },
        }
        cache = {
            "PS_TEST": _make_animal_info(
                "PS_TEST", stroke_date=datetime.date(2025, 5, 4),
            ),
        }
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=overrides,
            animal_info_cache=cache,
            require_on_disk=False,
        ))
        assert keys == [
            ("PS_TEST", datetime.date(2025, 5, 6)),
            ("PS_TEST", datetime.date(2025, 5, 10)),
        ]

    def test_filters_d0_and_d_plus_one(self, tmp_path):
        """Explicit pin: d0 and d+1 are BOTH excluded (rel_day < 2)."""
        resolver = PathResolver(output_root=tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                "PS_TEST": {
                    "2025-05-04": {},  # rel_day=0 -> drop
                    "2025-05-05": {},  # rel_day=+1 -> drop
                    "2025-05-06": {},  # rel_day=+2 -> keep
                },
            },
        }
        cache = {
            "PS_TEST": _make_animal_info(
                "PS_TEST", stroke_date=datetime.date(2025, 5, 4),
            ),
        }
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=overrides,
            animal_info_cache=cache,
            require_on_disk=False,
        ))
        assert keys == [("PS_TEST", datetime.date(2025, 5, 6))]

    def test_handles_PS55_2025_04_28_n_dlc_zero(self, tmp_path):
        """The real PS55/2025-04-28 entry is n_dlc=0 (DLC-free; Phase 2
        outputs present). It also happens to be pre-stroke (rel_day=-2
        for PS55's 2025-04-30 stroke), so the filter excludes it. This
        test pins that the iterator's filter is rel_day-based and does
        NOT gate on n_dlc — the same entry with rel_day >= 2 would be
        included transparently. We verify the exclusion side here; the
        inclusion-when-post-stroke case is covered by the keys-yield-14
        test (the filter logic is the same)."""
        resolver = PathResolver(output_root=tmp_path)
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=_real_registry(),
            animal_info_cache=_real_animal_info_cache(),
            require_on_disk=False,
            animals=["PS55"],
        ))
        ps55_dates = [d for (_a, d) in keys]
        assert datetime.date(2025, 4, 28) not in ps55_dates, (
            "PS55/2025-04-28 should be excluded by rel_day filter "
            "(rel_day=-2 < 2)"
        )

    def test_animals_filter_unknown_silently_drops(self, tmp_path):
        """Passing an animal not in the registry yields nothing for
        that animal (no error). Lets callers pass a stable
        ANIMALS list across phases."""
        resolver = PathResolver(output_root=tmp_path)
        keys = list(iter_cohort_b_session_keys(
            resolver,
            overrides_config=_real_registry(),
            animal_info_cache=_real_animal_info_cache(),
            require_on_disk=False,
            animals=["PS_NOT_IN_REGISTRY"],
        ))
        assert keys == []


class TestSessionPairData:
    def test_dataclass_shape(self):
        """SessionPairData carries (animal, date, bare, b) — both
        halves typed as SessionPlotData."""
        bare = SessionPlotData(
            date_label="20250530",
            lick_idx={"Lick_L": np.array([1]), "Lick_R": np.array([2])},
            rewards_idx={"Reward_L": np.array([3]), "Reward_R": np.array([4])},
            sample_rate=2000.0,
            n_samples_session=60000,
        )
        b = SessionPlotData(
            date_label="20250530",
            lick_idx={"Lick_L": np.array([5]), "Lick_R": np.array([6])},
            rewards_idx={"Reward_L": np.array([7]), "Reward_R": np.array([8])},
            sample_rate=2000.0,
            n_samples_session=40000,
        )
        pair = SessionPairData(
            animal="PS55",
            date=datetime.date(2025, 5, 30),
            bare=bare,
            b=b,
        )
        assert pair.animal == "PS55"
        assert pair.date == datetime.date(2025, 5, 30)
        assert pair.bare is bare
        assert pair.b is b
        # bare and b carry distinct SessionPlotData payloads.
        assert pair.bare.n_samples_session != pair.b.n_samples_session


class TestPathResolverBareVsBDir:
    def test_no_animal_returns_parent_dir(self, tmp_path):
        """`bare_vs_b_dir()` (no animal) returns the parent dir
        used for CG-B3 cohort recovery curves and as the base for
        per-animal subdirs."""
        resolver = PathResolver(output_root=tmp_path)
        d = resolver.bare_vs_b_dir()
        assert d.name == "bare_vs_b"
        assert d.parent.name == "spout_behavior_figures"

    def test_per_animal_returns_nested(self, tmp_path):
        """`bare_vs_b_dir('PS55')` returns the per-animal nested dir
        used for CG-B2 per-session paired panels."""
        resolver = PathResolver(output_root=tmp_path)
        d = resolver.bare_vs_b_dir("PS55")
        assert d.name == "PS55"
        assert d.parent.name == "bare_vs_b"


class TestIterCohortBSessionsEndToEnd:
    """End-to-end smoke test that the full iter_cohort_b_sessions
    (loads NPZs) works against a single synthetic Cohort B session."""

    def _write_npz_pair(
        self,
        output_root: Path,
        animal: str,
        date_str: str,
        *,
        bare_n_licks: int = 10,
        b_n_licks: int = 5,
    ) -> None:
        """Write synthetic bare + b Phase-2 NPZs for one session."""
        sp = output_root / "spout_behavior"
        licks_dir = sp / "licks_and_rewards" / animal
        ws_dir = sp / "wavesurfer_signals_processed" / animal
        licks_dir.mkdir(parents=True, exist_ok=True)
        ws_dir.mkdir(parents=True, exist_ok=True)
        # bare
        np.savez(
            licks_dir / f"{date_str}.npz",
            Lick_L=np.arange(bare_n_licks, dtype=int),
            Lick_R=np.arange(bare_n_licks, dtype=int),
            Reward_L=np.array([100], dtype=int),
            Reward_R=np.array([200], dtype=int),
        )
        np.savez(
            ws_dir / f"{date_str}.npz",
            sample_rate_input=np.array(2000.0),
            Treadmill=np.zeros(60000, dtype=np.float32),
        )
        # b
        np.savez(
            licks_dir / f"{date_str}b.npz",
            Lick_L=np.arange(b_n_licks, dtype=int),
            Lick_R=np.arange(b_n_licks, dtype=int),
            Reward_L=np.array([300], dtype=int),
            Reward_R=np.array([400], dtype=int),
        )
        np.savez(
            ws_dir / f"{date_str}b.npz",
            sample_rate_input=np.array(2000.0),
            Treadmill=np.zeros(40000, dtype=np.float32),
        )

    def test_loads_synthetic_pair(self, tmp_path):
        """Write one synthetic Cohort B session, iterate, verify
        SessionPairData payload."""
        animal = "PS55"
        date_str = "20250530"
        self._write_npz_pair(tmp_path, animal, date_str)
        resolver = PathResolver(output_root=tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                animal: {"2025-05-30": {}},
            },
        }
        cache = _real_animal_info_cache()
        pairs = list(iter_cohort_b_sessions(
            resolver,
            overrides_config=overrides,
            animal_info_cache=cache,
            require_on_disk=True,
        ))
        assert len(pairs) == 1
        pair = pairs[0]
        assert pair.animal == "PS55"
        assert pair.date == datetime.date(2025, 5, 30)
        assert pair.bare.date_label == "20250530"
        assert pair.b.date_label == "20250530"
        # bare and b carry their own (different) lick arrays.
        assert len(pair.bare.lick_idx["Lick_L"]) == 10
        assert len(pair.b.lick_idx["Lick_L"]) == 5
        # n_samples is per-half (NOT summed).
        assert pair.bare.n_samples_session == 60000
        assert pair.b.n_samples_session == 40000

    def test_skips_session_with_missing_b_npz(self, tmp_path):
        """If the bare NPZ exists but the b NPZ doesn't, the session
        is silently skipped (covers the pre-stroke Pattern B entries
        with no b-half recording)."""
        animal = "PS55"
        date_str = "20250530"
        sp = tmp_path / "spout_behavior"
        (sp / "licks_and_rewards" / animal).mkdir(parents=True, exist_ok=True)
        (sp / "wavesurfer_signals_processed" / animal).mkdir(parents=True, exist_ok=True)
        # bare only
        np.savez(
            sp / "licks_and_rewards" / animal / f"{date_str}.npz",
            Lick_L=np.array([1]), Lick_R=np.array([2]),
            Reward_L=np.array([3]), Reward_R=np.array([4]),
        )
        np.savez(
            sp / "wavesurfer_signals_processed" / animal / f"{date_str}.npz",
            sample_rate_input=np.array(2000.0),
            Treadmill=np.zeros(1000, dtype=np.float32),
        )
        # NO b NPZ written.
        resolver = PathResolver(output_root=tmp_path)
        overrides = {
            "secondary_spout_sessions": {
                animal: {"2025-05-30": {}},
            },
        }
        cache = _real_animal_info_cache()
        pairs = list(iter_cohort_b_sessions(
            resolver,
            overrides_config=overrides,
            animal_info_cache=cache,
            require_on_disk=True,
        ))
        assert pairs == []
