"""Tests for stroke_orofacial.spout_behavior.spout_close_vs_std.

Phase 8a.10 sub-deliverable B. Covers:

  - CG-B1 shared infrastructure: post-stroke filter (rel_day >= 2),
    optional ``animals=`` subset (PS55 pilot), n_dlc=0 graceful
    handling, SessionPairData shape, PathResolver.spout_close_vs_std_dir.
  - CG-B3 cohort renderer (Addendum #1 2026-05-13 cohort-only design):
    render_animal_summary_spout_close_vs_std produces a 3×2 grid with the
    expected output path + structural pins (denominator semantics,
    raster divider).

CG-B2's per-session renderers were superseded by Addendum #1
(removed; commit history retained at d757294).
"""

from __future__ import annotations

import datetime
import platform
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.spout_close_vs_std import (
    COHORT_B_REL_DAY_MIN,
    SessionPairData,
    iter_cohort_b_session_keys,
    iter_cohort_b_sessions,
    list_cohort_b_animals,
    render_animal_per_trial_spout_close_vs_std,
    render_animal_summary_spout_close_vs_std,
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


class TestPathResolverSpoutCloseVsStdDir:
    def test_no_animal_returns_cohort_dir(self, tmp_path):
        """Addendum #1 (2026-05-13): ``spout_close_vs_std_dir(animal=None)``
        returns the cohort/ subdir, where the per-animal summary
        outputs land (``<animal>_summary.{svg,png}``)."""
        resolver = PathResolver(output_root=tmp_path)
        d = resolver.spout_close_vs_std_dir()
        assert d.name == "cohort"
        assert d.parent.name == "spout_close_vs_std"
        assert d.parent.parent.name == "spout_behavior_figures"

    def test_per_animal_returns_legacy_per_session_dir(self, tmp_path):
        """`spout_close_vs_std_dir('PS55')` returns the legacy CG-B2
        per-animal nested dir. CG-B3 keeps this resolver branch so
        the orchestrator can target it for orphan cleanup
        (CG-B2's per-session pilot outputs are superseded by
        Addendum #1)."""
        resolver = PathResolver(output_root=tmp_path)
        d = resolver.spout_close_vs_std_dir("PS55")
        assert d.name == "PS55"
        assert d.parent.name == "spout_close_vs_std"


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


# ---- CG-B3 — cohort summary renderer ----


def _make_session(
    date_label: str,
    *,
    lick_l: np.ndarray | None = None,
    lick_r: np.ndarray | None = None,
    reward_l: np.ndarray | None = None,
    reward_r: np.ndarray | None = None,
    sample_rate: float = 2000.0,
    n_samples: int = 60000,
) -> SessionPlotData:
    """Synthesize a SessionPlotData payload for direct renderer
    testing (avoids the NPZ-on-disk round-trip)."""
    return SessionPlotData(
        date_label=date_label,
        lick_idx={
            "Lick_L": (
                lick_l if lick_l is not None
                else np.array([1100, 1500, 2000, 5100, 5400], dtype=int)
            ),
            "Lick_R": (
                lick_r if lick_r is not None
                else np.array([5200, 5500, 5800, 6200, 6600], dtype=int)
            ),
        },
        rewards_idx={
            "Reward_L": (
                reward_l if reward_l is not None
                else np.array([1000, 2000], dtype=int)
            ),
            "Reward_R": (
                reward_r if reward_r is not None
                else np.array([5000, 6000], dtype=int)
            ),
        },
        sample_rate=sample_rate,
        n_samples_session=n_samples,
    )


@pytest.fixture
def synth_pairs_3_sessions() -> list[SessionPairData]:
    """3 synthetic SessionPairData rows for a single animal —
    mirrors the PS55 pilot scope (3 post-stroke sessions)."""
    pairs: list[SessionPairData] = []
    for i, iso in enumerate(("2025-05-30", "2025-06-01", "2025-06-05")):
        date = datetime.date.fromisoformat(iso)
        # Synthesize slight per-session variation so per-session dots
        # are visually distinguishable in the figure.
        bare = _make_session(
            date.strftime("%Y%m%d"),
            lick_l=np.array([1100 + 50 * i, 1500], dtype=int),
            lick_r=np.array([5200 + 50 * i], dtype=int),
        )
        b = _make_session(
            date.strftime("%Y%m%d"),
            lick_l=np.array([1080 + 50 * i, 1200, 2050], dtype=int),
            lick_r=np.array([5150 + 50 * i, 5400], dtype=int),
        )
        pairs.append(SessionPairData(
            animal="PS55", date=date, bare=bare, b=b,
        ))
    return pairs


class TestRenderAnimalSummarySpoutCloseVsStd:
    def test_returns_expected_cohort_paths(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: outputs land at
        ``spout_close_vs_std/cohort/<animal>_summary.{svg,png}``."""
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists() and png.stat().st_size > 0
        assert svg.name == "PS55_summary.svg"
        assert png.name == "PS55_summary.png"
        assert svg.parent.name == "cohort"
        assert svg.parent.parent.name == "spout_close_vs_std"

    def test_raises_when_no_sessions(self, tmp_path):
        """Empty session list → ValueError (no grid to build)."""
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(ValueError, match="no post-stroke Cohort B"):
            render_animal_summary_spout_close_vs_std(
                "PS55", sessions=[], resolver=resolver,
            )

    def test_layout_is_4_rows_2_cols(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Addendum #3 Tweak 3 pin: figure has 8 axes (4 rows × 2
        cols). R2's 3-row layout (6 axes) was split into 4 rows by
        separating mean correct licks from mean incorrect licks."""
        import re
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        axes_groups = re.findall(r'<g id="axes_\d+">', text)
        assert len(axes_groups) == 8, (
            f"4×2 grid should produce 8 axes; got {len(axes_groups)}"
        )

    def test_row_1_uses_treat_none_as_zero_denominator(
        self, tmp_path,
    ):
        """Addendum #1 PIN: Row 1 uses ``treat_none_as_zero=True``
        semantics (denominator = ALL trials).

        Synthetic case: 4 cue-L trials, only 1 has a post-reward
        L-lick (correct). Under treat_none_as_zero=True the accuracy
        is 1/4 = 0.25. Under the excludeNone variant it would be 1/1
        = 1.0 (the legacy non-All sibling). The cohort renderer
        must compute the addendum-mandated 0.25 value.
        """
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            _half_accuracy_firstCorrectLickAll_per_side,
        )
        # 4 L-reward trials at samples 1000, 5000, 9000, 13000.
        # Only the first has a post-reward L-lick (within window).
        session = _make_session(
            "20250530",
            lick_l=np.array([1100], dtype=int),  # only post-reward of trial 0
            lick_r=np.array([], dtype=int),
            reward_l=np.array([1000, 5000, 9000, 13000], dtype=int),
            reward_r=np.array([], dtype=int),
        )
        acc = _half_accuracy_firstCorrectLickAll_per_side(
            session, [1.0, 8.0],
        )
        # 1 correct / 4 trials = 0.25 (treat_none_as_zero=True).
        assert abs(acc["L"] - 0.25) < 1e-9, (
            f"expected 0.25 (all-trials denominator); got {acc['L']}"
        )

    def test_row_3_raster_carries_visual_gate_polish(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: Row 3's pooled raster inherits visual_gate's dot
        polish (alpha=0.6 + thin reward marker 0.5)."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        assert "fill-opacity: 0.6" in text, (
            "Row 3 dots not rendered at alpha=0.6"
        )
        assert "stroke-width: 0.5" in text, (
            "Row 3 reward marker not at linewidth 0.5"
        )

    def test_loads_sessions_when_none_passed(self, tmp_path, monkeypatch):
        """If ``sessions=None``, the renderer calls iter_cohort_b_sessions
        for the animal. Patch the iterator to return a controlled
        list and verify the renderer composes correctly."""
        resolver = PathResolver(output_root=tmp_path)
        # Build 2 synthetic pairs via the same helper.
        pairs = [
            SessionPairData(
                animal="PS55",
                date=datetime.date(2025, 5, 30),
                bare=_make_session("20250530"),
                b=_make_session("20250530"),
            ),
            SessionPairData(
                animal="PS55",
                date=datetime.date(2025, 6, 1),
                bare=_make_session("20250601"),
                b=_make_session("20250601"),
            ),
        ]
        from stroke_orofacial.spout_behavior import spout_close_vs_std as mod

        def fake_iter(*args, **kwargs):
            for p in pairs:
                yield p

        monkeypatch.setattr(mod, "iter_cohort_b_sessions", fake_iter)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", resolver=resolver,
        )
        assert svg.exists()
        # Suptitle includes n=2.
        text = svg.read_text(encoding="utf-8")
        # matplotlib renders text as paths; assert "2" glyph (= DejaVuSans-32)
        # appears (true for any n>0 multi-digit; weak pin).
        assert "DejaVuSans" in text  # text rendering happened


# ---- CG-B3 Round 2 polish (Addendum #2, 2026-05-13) ----


class TestCgB3R2Polish:
    """Pins for Addendum #2 tweaks 1 + 4 (preserved through R3).

    Tweak 1 — display labels (Standard / Close / Spout Distance).
    Tweak 4 — shared y-lim across L/R panels per row.

    The R2 per-condition palette (Tweak 2) was replaced by R3's
    per-mouse-side palette + Standard/Close fill convention — see
    :class:`TestCgB3R3Polish` for the new pins. R2's
    inter-session-boundary count (Tweak 3) is superseded by R3's
    darker styling — see TestCgB3R3Polish.test_raster_divider_kwargs."""

    def test_tweak_1_display_labels_replace_bare_b(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: SVG contains "Standard", "Close", "Spout Distance"
        (rendered tick labels + axis title). Raw "bare" / "b" text
        does NOT appear as visible tick-label text."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        assert "Standard" in text, "display label 'Standard' missing"
        assert "Close" in text, "display label 'Close' missing"
        assert "Spout Distance" in text, "axis title 'Spout Distance' missing"
        assert '"bare"' not in text, "raw 'bare' tick-label leaked"
        assert ">bare<" not in text, "raw 'bare' tick-label leaked"

    def test_tweak_4_shared_ylim_rows_1_through_3(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: Rows 1, 2, 3 panels (L, R) each share y-lim. The
        first 6 set_ylim calls correspond to the renderer's
        explicit row-by-row pair. (Row 4 raster has additional
        autoscale-triggered set_ylim calls during text/scatter
        emission so we don't pin Row 4 here — its L/R sync is
        instead exercised via the per-row max-trial-count padding
        in _plot_row_lick_raster and indirectly via the layout
        test.)"""
        import matplotlib
        captured: list[tuple[float, float]] = []
        orig = matplotlib.axes.Axes.set_ylim

        def recording_set_ylim(self, *args, **kwargs):
            if len(args) == 2:
                captured.append((float(args[0]), float(args[1])))
            elif len(args) == 1 and isinstance(args[0], (tuple, list)):
                captured.append((float(args[0][0]), float(args[0][1])))
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_ylim", recording_set_ylim,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        assert len(captured) >= 6, (
            f"expected ≥6 set_ylim calls for Rows 1-3 (each row × 2 "
            f"cols); got {len(captured)}"
        )
        for row_idx, (idx_L, idx_R) in enumerate([
            (0, 1), (2, 3), (4, 5),
        ]):
            assert captured[idx_L] == captured[idx_R], (
                f"Row {row_idx + 1} L/R y-lim mismatch: "
                f"{captured[idx_L]} vs {captured[idx_R]}"
            )


class TestCgB3R3Polish:
    """Pins for Addendum #3 Round 3 tweaks (2-6).

    Tweak 2 — per-mouse-side palette + Standard/Close dot-fill
              convention.
    Tweak 3 — 4-row layout split (correct/incorrect separate rows).
    Tweak 4 — raster day labels outside the right spine.
    Tweak 5 — darker raster session-divider styling.
    Tweak 6 — typography bumps (panel title 14; cohort raster
              xtick 9; cohort raster xlabel 11)."""

    def test_dot_fill_filled_standard_open_close(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Tweak 2 pin: Standard (bare) dots have
        ``markerfacecolor=mouse_side_color``; Close (b) dots have
        ``markerfacecolor="none"``. Verified by SVG element
        signatures: bare dots have a fill-color attribute matching
        the mouse-side color; b dots have fill="none" (or absent
        fill style)."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            SPOUT_DISTANCE_DOT_FILL,
        )
        assert SPOUT_DISTANCE_DOT_FILL["bare"] == "filled"
        assert SPOUT_DISTANCE_DOT_FILL["b"] == "open"

        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # The L-panel mouse-side color (dodgerblue = #1e90ff) and
        # R-panel (mediumvioletred = #c71585) appear as fill on
        # Standard dots and as stroke on Close dots. matplotlib
        # serializes facecolor="none" as CSS-style
        # ``style="fill: none; stroke: ..."``.
        assert "fill: none" in text, (
            "open-fill (Close) dots missing; expected at least one "
            "'fill: none' style entry"
        )

    def test_dot_edgecolor_mouse_side(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Tweak 2 pin: both Standard and Close dots in the L panel
        share edgecolor=dodgerblue; both in R panel share
        mediumvioletred. SIDE_COLORS is the source of truth."""
        from stroke_orofacial.spout_behavior.visual_gate import SIDE_COLORS
        # Pin colors literally (avoid regressing SIDE_COLORS).
        assert SIDE_COLORS["L"] == "dodgerblue"
        assert SIDE_COLORS["R"] == "mediumvioletred"

        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # Mouse-side colors appear as stroke for dots (matplotlib
        # hex form). dodgerblue = #1e90ff; mediumvioletred = #c71585.
        assert "#1e90ff" in text, "L-panel mouse-side color missing"
        assert "#c71585" in text, "R-panel mouse-side color missing"

    def test_mean_line_color_matches_mouse_side(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Tweak 2 pin: mean line color = mouse-side color (NOT
        per-condition). The mean line for both Standard and Close
        within an L panel is dodgerblue; within an R panel is
        mediumvioletred."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            COHORT_MEAN_BAR_LINEWIDTH,
        )
        assert COHORT_MEAN_BAR_LINEWIDTH == 0.75
        # The previous per-condition palette is gone; no
        # SPOUT_DISTANCE_CONDITION_COLORS module export.
        import stroke_orofacial.spout_behavior.spout_close_vs_std as mod
        assert not hasattr(mod, "SPOUT_DISTANCE_CONDITION_COLORS"), (
            "SPOUT_DISTANCE_CONDITION_COLORS should be deleted per "
            "Addendum #3 Tweak 2"
        )

    def test_connector_stays_gray(self):
        """Tweak 2 pin: same-date bare/b connector stays gray
        (spans both conditions; neutrality is intentional)."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            COHORT_CONNECTOR_KWARGS,
        )
        assert COHORT_CONNECTOR_KWARGS["color"] == "gray"

    def test_row_3_incorrect_separate_ylim_from_row_2(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Tweak 3 pin: Row 2 (correct) and Row 3 (incorrect) have
        INDEPENDENT y-axis ranges. They should NOT share — incorrect
        magnitudes are typically much smaller and sharing would
        crush detail. The PS55 synthetic fixture has more correct
        than incorrect licks, so their max-values differ → ylim
        differs."""
        import matplotlib
        captured: list[tuple[float, float]] = []
        orig = matplotlib.axes.Axes.set_ylim

        def recording_set_ylim(self, *args, **kwargs):
            if len(args) == 2:
                captured.append((float(args[0]), float(args[1])))
            elif len(args) == 1 and isinstance(args[0], (tuple, list)):
                captured.append((float(args[0][0]), float(args[0][1])))
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_ylim", recording_set_ylim,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        # row2 = indices (2, 3), row3 = indices (4, 5).
        row2 = captured[2]
        row3 = captured[4]
        # If the synthetic fixture happens to have equal max values
        # for correct and incorrect, this assert is skipped. The
        # standard synth fixture has 5 vs 1 max licks → magnitudes
        # differ → ylim differs.
        if abs(row2[1] - row3[1]) < 1e-9:
            pytest.skip(
                "synthetic fixture has equal correct/incorrect max — "
                "can't assert separate ylim"
            )
        assert row2 != row3, (
            f"Row 2 + Row 3 ylim should be independent; both = {row2}"
        )

    def test_raster_day_labels_outside_right_spine(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Tweak 4 pin: Row 4 raster has one "d+N" text label per
        session-block in EACH half (bare + b). PS55 worked example:
        3 Standard sessions + 3 Close sessions = 6 labels per panel
        × 2 panels (L, R) = 12 day labels total."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            render_animal_summary_spout_close_vs_std as render_fn,
        )
        # Patch ax.text to capture labels.
        import matplotlib
        captured: list[tuple[float, float, str]] = []
        orig = matplotlib.axes.Axes.text

        def recording_text(self, x, y, s, *args, **kwargs):
            captured.append((float(x), float(y) if not hasattr(y, "real") else float(y), str(s)))
            return orig(self, x, y, s, *args, **kwargs)

        import unittest.mock as mock
        with mock.patch.object(
            matplotlib.axes.Axes, "text", recording_text,
        ):
            resolver = PathResolver(output_root=tmp_path)
            render_fn(
                "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
            )
        # Filter to day-label calls (x > 1.0 in axes coords —
        # outside the right spine).
        day_labels = [c for c in captured if c[0] > 1.0 and c[2].startswith("d")]
        # 3 Standard + 3 Close sessions × 2 panels = 12 day labels.
        assert len(day_labels) == 12, (
            f"expected 12 day labels (3 Standard + 3 Close × 2 "
            f"panels); got {len(day_labels)}: {day_labels[:5]}..."
        )
        # Every label is "d+N" or "d-N" or "d0".
        import re
        for _x, _y, s in day_labels:
            assert re.fullmatch(r"d[+\-]?\d+", s), (
                f"day label {s!r} doesn't match 'd[+-]?N' format"
            )

    def test_raster_divider_kwargs(self):
        """Tweak 5 pin: Row 4 inter-session boundary lines render
        at color="gray", linewidth=0.5, alpha=0.8, zorder=1 (darker
        than R2's lightgray/0.3/0.5)."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            RASTER_INTRA_HALF_BOUNDARY_KWARGS,
        )
        assert RASTER_INTRA_HALF_BOUNDARY_KWARGS["color"] == "gray"
        assert RASTER_INTRA_HALF_BOUNDARY_KWARGS["linewidth"] == 0.5
        assert RASTER_INTRA_HALF_BOUNDARY_KWARGS["alpha"] == 0.8
        assert RASTER_INTRA_HALF_BOUNDARY_KWARGS["zorder"] == 1

    def test_raster_divider_renders_in_svg(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Tweak 5 pin: the boundary lines actually render with
        the darker R3 styling. PS55: 3 sessions × 2 halves × 2
        panels → (3-1) × 2 × 2 = 8 boundary lines."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # gray = #808080 in matplotlib SVG hex.
        n_gray = text.count("#808080")
        n_thin = text.count("stroke-width: 0.5")
        n_alpha_08 = text.count("stroke-opacity: 0.8")
        expected = (3 - 1) * 2 * 2
        assert n_gray >= expected, (
            f"expected ≥{expected} gray refs (inter-session boundary "
            f"color); got {n_gray}"
        )
        assert n_alpha_08 >= expected, (
            f"expected ≥{expected} stroke-opacity: 0.8 refs; got "
            f"{n_alpha_08}"
        )
        # Note: stroke-width 0.5 is also used elsewhere (reward
        # marker linewidth 0.5 from CG-B2 polish), so we can't pin
        # an exact count. The presence of >= expected gray + opacity
        # 0.8 entries is the boundary signal.
        _ = n_thin  # informational only

    def test_title_fontsize_14(self):
        """Tweak 6 pin: panel title fontsize = 14 in cohort config.

        Addendum #4 Tweak 1 bumped raster_xtick 9→11 and
        raster_xlabel 11→13; Addendum #4 Tweak 3 added two new
        licking-block knobs."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            load_cohort_config,
        )
        cfg = load_cohort_config()
        # R3 carries:
        assert cfg["panel_title_fontsize"] == 14
        assert cfg["raster_day_label_fontsize"] == 7
        # R4 Tweak 1 bumps + new labelpad knob:
        assert cfg["raster_xtick_fontsize"] == 11
        assert cfg["raster_xlabel_fontsize"] == 13
        assert cfg["raster_xlabel_labelpad"] == 2
        # R4 Tweak 3 new licking-block knobs:
        assert cfg["licking_xtick_fontsize"] == 12
        assert cfg["spout_distance_xlabel_fontsize"] == 13


class TestCgB3R4Polish:
    """Pins for Addendum #4 Round 4 tweaks.

    Tweak 1 — bigger raster xtick/xlabel + tighter labelpad.
    Tweak 2 — day labels rotate 90° → 270° (character bottoms
              plot-adjacent).
    Tweak 3 — bigger licking xtick + Spout Distance xlabel."""

    def test_tweak_1_time_xlabel_is_per_panel_not_supxlabel(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: 'Time (s)' moved from fig.supxlabel to per-panel
        ax.set_xlabel on Row 4 (so labelpad applies). Verify
        supxlabel was NOT called with 'Time (s)' and per-axis
        set_xlabel WAS called with 'Time (s)' twice (L, R panels
        of Row 4)."""
        import matplotlib
        supx_calls: list[tuple] = []
        setx_calls: list[tuple] = []
        orig_supx = matplotlib.figure.Figure.supxlabel
        orig_setx = matplotlib.axes.Axes.set_xlabel

        def recording_supx(self, *args, **kwargs):
            supx_calls.append((args, dict(kwargs)))
            return orig_supx(self, *args, **kwargs)

        def recording_setx(self, *args, **kwargs):
            setx_calls.append((args, dict(kwargs)))
            return orig_setx(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.figure.Figure, "supxlabel", recording_supx,
        )
        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_xlabel", recording_setx,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        time_supx = [
            c for c in supx_calls
            if c[0] and c[0][0] == "Time (s)"
        ]
        assert len(time_supx) == 0, (
            f"Time (s) should NOT be a fig.supxlabel anymore; "
            f"got {len(time_supx)} supxlabel calls"
        )
        time_setx = [
            c for c in setx_calls
            if c[0] and c[0][0] == "Time (s)"
        ]
        assert len(time_setx) == 2, (
            f"Time (s) should be set as per-panel xlabel on Row 4 "
            f"L+R (2 calls); got {len(time_setx)}"
        )
        # Each Time (s) xlabel call carries labelpad from config.
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            load_cohort_config,
        )
        expected_pad = load_cohort_config()["raster_xlabel_labelpad"]
        for _args, kwargs in time_setx:
            assert kwargs.get("labelpad") == expected_pad, (
                f"Time (s) xlabel missing labelpad={expected_pad}; "
                f"got kwargs={kwargs}"
            )

    def test_tweak_2_day_labels_rotation_horizontal(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: day labels use rotation=0 (R6/Addendum #6 horizontal
        flip; supersedes R4 Tweak 2's rotation=270). Horizontal
        labels are readable on dense cohorts like PS54 (20 labels)."""
        import matplotlib
        import unittest.mock as mock
        captured: list[dict] = []
        orig = matplotlib.axes.Axes.text

        def recording_text(self, x, y, s, *args, **kwargs):
            captured.append({
                "x": float(x),
                "s": str(s),
                "rotation": kwargs.get("rotation"),
            })
            return orig(self, x, y, s, *args, **kwargs)

        with mock.patch.object(
            matplotlib.axes.Axes, "text", recording_text,
        ):
            resolver = PathResolver(output_root=tmp_path)
            render_animal_summary_spout_close_vs_std(
                "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
            )
        day_calls = [c for c in captured if c["x"] > 1.0 and c["s"].startswith("d")]
        assert len(day_calls) > 0, "no day-label ax.text calls captured"
        for c in day_calls:
            assert c["rotation"] == 0, (
                f"day label rotation should be 0 (R6 horizontal "
                f"flip; supersedes R4 rotation=270), got "
                f"{c['rotation']} on label {c['s']!r}"
            )

    def test_tweak_3_licking_xtick_fontsize_applied(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: licking-plot panels (Rows 1-3) call
        ax.tick_params(axis='x', labelsize=12) per the new
        licking_xtick_fontsize=12 knob."""
        import matplotlib
        captured: list[dict] = []
        orig = matplotlib.axes.Axes.tick_params

        def recording_tick_params(self, *args, **kwargs):
            captured.append({
                "axis": kwargs.get("axis") or (args[0] if args else None),
                "labelsize": kwargs.get("labelsize"),
            })
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "tick_params", recording_tick_params,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        # Rows 1, 2, 3 panels (6 total) call tick_params with
        # axis='x', labelsize=12. Row 4 raster panels call
        # tick_params with axis='x', labelsize=11 (per R4 Tweak 1).
        licking_calls = [
            c for c in captured
            if c["axis"] == "x" and c["labelsize"] == 12
        ]
        assert len(licking_calls) == 6, (
            f"expected 6 licking-block tick_params calls "
            f"(Rows 1-3 × 2 cols, labelsize=12); got "
            f"{len(licking_calls)}: all captured={captured!r}"
        )
        raster_calls = [
            c for c in captured
            if c["axis"] == "x" and c["labelsize"] == 11
        ]
        assert len(raster_calls) == 2, (
            f"expected 2 raster tick_params calls (Row 4 × 2 cols, "
            f"labelsize=11); got {len(raster_calls)}"
        )

    def test_tweak_3_spout_distance_xlabel_fontsize_13(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: 'Spout Distance' xlabel on Row 3 panels gets
        fontsize=13."""
        import matplotlib
        captured: list[tuple] = []
        orig = matplotlib.axes.Axes.set_xlabel

        def recording_set_xlabel(self, *args, **kwargs):
            captured.append((args, dict(kwargs)))
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_xlabel", recording_set_xlabel,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        sd_calls = [
            c for c in captured
            if c[0] and c[0][0] == "Spout Distance"
        ]
        assert len(sd_calls) == 2, (
            f"expected 2 'Spout Distance' xlabel calls (Row 3 L+R); "
            f"got {len(sd_calls)}"
        )
        for _args, kwargs in sd_calls:
            assert kwargs.get("fontsize") == 13, (
                f"'Spout Distance' fontsize should be 13; got "
                f"{kwargs.get('fontsize')}"
            )


class TestCgB3R5Polish:
    """Pins for Addendum #5 Round 5 raster polish.

    Tweak 1 — raster xticks every integer second [0..5].
    Tweak 2 — day-label vertical centering (rotation_mode="default").
    Tweak 3 — y-axis overhaul (Trials ylabel + numeric yticks +
              earlier-trials-at-bottom + half-labels relocated to
              left spine)."""

    def test_tweak_1_raster_xticks_full_integer_range(self):
        """Pin: cohort raster xticks are at every integer second
        across [0, 5] (was R3-R4 inheriting visual_gate's
        [0, 5] endpoint-only ticks). At least 6 tick values."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            load_cohort_config,
        )
        cfg = load_cohort_config()
        xticks = cfg["raster_xticks"]
        assert len(xticks) >= 6, (
            f"cohort raster_xticks should have ≥6 entries (every "
            f"integer second in window); got {len(xticks)}: {xticks}"
        )
        assert xticks == [0, 1, 2, 3, 4, 5], (
            f"expected [0,1,2,3,4,5]; got {xticks}"
        )

    def test_tweak_2_day_label_anchor_horizontal(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: day labels anchored at ha='left', va='center' with
        rotation=0 (R6/Addendum #6 horizontal flip; supersedes R5's
        rotation_mode='default' centering-for-rotated-text fix —
        with rotation=0, rotation_mode is moot)."""
        import matplotlib
        import unittest.mock as mock
        captured: list[dict] = []
        orig = matplotlib.axes.Axes.text

        def recording_text(self, x, y, s, *args, **kwargs):
            captured.append({
                "x": float(x),
                "s": str(s),
                "rotation": kwargs.get("rotation"),
                "ha": kwargs.get("ha"),
                "va": kwargs.get("va"),
            })
            return orig(self, x, y, s, *args, **kwargs)

        with mock.patch.object(
            matplotlib.axes.Axes, "text", recording_text,
        ):
            resolver = PathResolver(output_root=tmp_path)
            render_animal_summary_spout_close_vs_std(
                "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
            )
        day_calls = [
            c for c in captured
            if c["x"] > 1.0 and c["s"].startswith("d")
        ]
        assert len(day_calls) > 0
        for c in day_calls:
            assert c["rotation"] == 0, (
                f"day label rotation should be 0 (R6); got "
                f"{c['rotation']!r}"
            )
            assert c["ha"] == "left", (
                f"day label ha should be 'left' (text anchored to "
                f"its left edge at x=1.02); got {c['ha']!r}"
            )
            assert c["va"] == "center", (
                f"day label va should be 'center' (vertically "
                f"centered on session block); got {c['va']!r}"
            )

    def test_tweak_3a_row_4_ylabel_is_trials(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: Row 4 ylabel = 'Trials' (R3-R4 used 'Trials
        (Standard top / Close bottom)' before half labels moved
        to the left spine)."""
        import matplotlib
        captured: list[tuple] = []
        orig = matplotlib.axes.Axes.set_ylabel

        def recording_set_ylabel(self, *args, **kwargs):
            captured.append((args, dict(kwargs)))
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_ylabel", recording_set_ylabel,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        trials_calls = [
            c for c in captured if c[0] and c[0][0] == "Trials"
        ]
        assert len(trials_calls) >= 1, (
            f"expected at least 1 'Trials' ylabel call (Row 4 L); "
            f"got {len(trials_calls)}; all={captured}"
        )
        # No stale "Standard top / Close bottom" wording.
        stale_calls = [
            c for c in captured
            if c[0] and "Standard top" in c[0][0]
        ]
        assert len(stale_calls) == 0, (
            f"R3/R4 wording 'Standard top / Close bottom' should be "
            f"gone; got {len(stale_calls)} calls"
        )

    def test_tweak_3b_numeric_yticks_and_3c_not_inverted(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: Row 4 panels have per-session "0" y-tick labels
        (Addendum #7 supersedes R5's cumulative ['0', '<n_total>'])
        and the y-axis is NOT inverted.

        Each session's row range starts with a "0" tick at the
        bottom of that session's block. For the synth fixture
        (3 Standard + 3 Close sessions) = 6 "0" ticks per panel.
        Captures ax.set_yticklabels via monkeypatch and verifies
        all-zero labels with length == n_sessions_total."""
        import matplotlib
        captured_ticklabels: list[list] = []
        orig_setyticks = matplotlib.axes.Axes.set_yticklabels

        def recording_set_yticklabels(self, labels, *args, **kwargs):
            captured_ticklabels.append(
                [str(L) for L in labels] if labels else []
            )
            return orig_setyticks(self, labels, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_yticklabels",
            recording_set_yticklabels,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_summary_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        # Per-session "0" tick labels — 6 per panel for the synth
        # fixture (3 Standard + 3 Close sessions). Both Row 4 panels
        # (L, R) emit this list → 2 matching calls.
        n_sessions_total = 2 * len(synth_pairs_3_sessions)  # bare + b
        zero_marker_calls = [
            labels for labels in captured_ticklabels
            if len(labels) == n_sessions_total
            and all(L == "0" for L in labels)
        ]
        assert len(zero_marker_calls) >= 1, (
            f"expected ≥1 per-session '0' yticklabel call with "
            f"length {n_sessions_total} (R7 Addendum #7); "
            f"got: {captured_ticklabels}"
        )
        # Sanity: no R5 cumulative ['0', '<N>'] form should appear
        # post-R7.
        cumulative_form = [
            labels for labels in captured_ticklabels
            if len(labels) == 2 and labels[0] == "0" and labels[1].isdigit()
            and labels[1] != "0"
        ]
        assert len(cumulative_form) == 0, (
            f"R5 cumulative ['0', '<N>'] form should be superseded "
            f"by R7's per-session form; got {cumulative_form}"
        )
        # No "Standard"/"Close" yticklabel calls (they relocated
        # to the left-spine ax.text outside the axes).
        stale = [
            labels for labels in captured_ticklabels
            if "Standard" in labels or "Close" in labels
        ]
        assert len(stale) == 0, (
            f"Standard/Close should no longer be yticklabels; got "
            f"{stale}"
        )

    def test_tweak_3_half_labels_outside_left_spine(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: Standard/Close half labels relocated to the LEFT
        side outside the spine (x < 0 in axes coords). One label
        per half per Row 4 panel → 2 halves × 2 panels = 4 labels
        with rotation=90 and text in {Standard, Close}."""
        import matplotlib
        import unittest.mock as mock
        captured: list[dict] = []
        orig = matplotlib.axes.Axes.text

        def recording_text(self, x, y, s, *args, **kwargs):
            captured.append({
                "x": float(x),
                "s": str(s),
                "rotation": kwargs.get("rotation"),
            })
            return orig(self, x, y, s, *args, **kwargs)

        with mock.patch.object(
            matplotlib.axes.Axes, "text", recording_text,
        ):
            resolver = PathResolver(output_root=tmp_path)
            render_animal_summary_spout_close_vs_std(
                "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
            )
        # Half-label calls: x<0 (outside left spine), text=
        # "Standard" or "Close".
        half_label_calls = [
            c for c in captured
            if c["x"] < 0 and c["s"] in ("Standard", "Close")
        ]
        assert len(half_label_calls) == 4, (
            f"expected 4 half-label calls (2 halves × 2 panels); "
            f"got {len(half_label_calls)}: {half_label_calls}"
        )
        # All rotated 90° CCW (mirrors the day-label rotated-270°
        # right-spine convention).
        for c in half_label_calls:
            assert c["rotation"] == 90, (
                f"half label rotation should be 90 (CCW; bottom-to-"
                f"top reading); got {c['rotation']} on label "
                f"{c['s']!r}"
            )

    def test_tweak_3_new_config_knobs(self):
        """Pin: R5 raster y-axis knobs + R7 follow-on labelpad knob.

        R7-follow-on tweaks (post-R7 user feedback): raster_ytick_fontsize
        dropped 11→8 (for PS54's 20 stacked '0' markers density);
        raster_ylabel_labelpad added (pushes 'Trials' axis title past
        the rotated half-spine labels)."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            load_cohort_config,
        )
        cfg = load_cohort_config()
        assert cfg["raster_ytick_fontsize"] == 8
        assert cfg["raster_ylabel_fontsize"] == 13
        assert cfg["raster_half_label_fontsize"] == 11
        assert cfg["raster_ylabel_labelpad"] == 20


# ---- Per-trial renderer (post-R7 follow-on, 2026-05-13) ----


class TestRenderAnimalPerTrial:
    """Pins for the companion per-trial renderer
    :func:`render_animal_per_trial_spout_close_vs_std`. Same 2x2
    layout shape as Rows 2+3 of the summary but plots INDIVIDUAL
    trial dots pooled across sessions, instead of per-session means."""

    def test_returns_expected_per_trial_paths(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: outputs land at
        ``spout_close_vs_std/cohort/<animal>_per_trial.{svg,png}``."""
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_animal_per_trial_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists() and png.stat().st_size > 0
        assert svg.name == "PS55_per_trial.svg"
        assert png.name == "PS55_per_trial.png"
        assert svg.parent.name == "cohort"
        assert svg.parent.parent.name == "spout_close_vs_std"

    def test_raises_when_no_sessions(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(ValueError, match="no post-stroke Cohort B"):
            render_animal_per_trial_spout_close_vs_std(
                "PS55", sessions=[], resolver=resolver,
            )

    def test_layout_is_2_rows_2_cols(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: 4 axes_groups (2 rows correct/incorrect × 2 cols L/R)."""
        import re
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_per_trial_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        axes_groups = re.findall(r'<g id="axes_\d+">', text)
        assert len(axes_groups) == 4, (
            f"per-trial 2×2 grid should produce 4 axes; got "
            f"{len(axes_groups)}"
        )

    def test_per_trial_dot_count_pools_across_sessions(
        self, synth_pairs_3_sessions, tmp_path, monkeypatch,
    ):
        """Pin: each scatter call receives one dot per trial pooled
        across sessions (NOT one dot per session-mean). For the synth
        fixture the L-correct count per panel ≈ sum of L trials across
        Standard + Close sessions × {correct, incorrect} × {L, R}."""
        import matplotlib
        captured_scatter_lens: list[int] = []
        orig = matplotlib.axes.Axes.scatter

        def recording_scatter(self, *args, **kwargs):
            # First positional arg is x (array-like).
            if args:
                try:
                    captured_scatter_lens.append(len(args[0]))
                except TypeError:
                    pass
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "scatter", recording_scatter,
        )
        resolver = PathResolver(output_root=tmp_path)
        render_animal_per_trial_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        # Synth fixture: 3 pairs × 2 reward trials per side per pair =
        # 6 trials per side per condition. So per panel × per condition
        # there are 6 dots. Per panel = 2 conditions × 6 = 12 dots
        # across 2 scatter calls (Standard + Close). 4 panels × 2 calls
        # = 8 scatter calls each with len=6.
        per_condition = [n for n in captured_scatter_lens if n == 6]
        assert len(per_condition) >= 8, (
            f"expected ≥8 scatter calls with len=6 (per-trial pooled "
            f"across 3 sessions × 2 trials/side); got: "
            f"{captured_scatter_lens}"
        )

    def test_per_trial_uses_dot_fill_convention(
        self, synth_pairs_3_sessions, tmp_path,
    ):
        """Pin: per-trial scatter respects R3 dot-fill convention
        (Standard filled, Close open). Same as summary's Rows 2-3
        — pools per-trial dots, doesn't drop the convention."""
        from stroke_orofacial.spout_behavior.spout_close_vs_std import (
            SPOUT_DISTANCE_DOT_FILL,
        )
        assert SPOUT_DISTANCE_DOT_FILL["bare"] == "filled"
        assert SPOUT_DISTANCE_DOT_FILL["b"] == "open"

        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_animal_per_trial_spout_close_vs_std(
            "PS55", sessions=synth_pairs_3_sessions, resolver=resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # Open-fill (Close) dots → CSS-style fill: none.
        assert "fill: none" in text, (
            "per-trial Close dots should render with fill: none; "
            "missing from SVG"
        )
        # Mouse-side colors (dodgerblue + mediumvioletred) appear
        # as stroke/fill.
        assert "#1e90ff" in text, "L-panel mouse-side color missing"
        assert "#c71585" in text, "R-panel mouse-side color missing"

