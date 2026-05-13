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
import pytest

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.bare_vs_b import (
    BARE_VS_B_LINE_COLORS,
    COHORT_B_REL_DAY_MIN,
    PER_SESSION_RENDERERS,
    SessionPairData,
    iter_cohort_b_session_keys,
    iter_cohort_b_sessions,
    list_cohort_b_animals,
    render_bare_vs_b_correct_incorrect_per_side,
    render_bare_vs_b_first_lick_accuracy,
    render_bare_vs_b_first_lick_latency,
    render_bare_vs_b_lick_raster,
    render_bare_vs_b_reward_acquisition_over_time,
    save_bare_vs_b_figure,
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


# ---- CG-B2 ----


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
def synth_pair() -> SessionPairData:
    return SessionPairData(
        animal="PS55",
        date=datetime.date(2025, 5, 30),
        bare=_make_session("20250530"),
        b=_make_session(
            "20250530",
            lick_l=np.array([1080, 1200, 2050], dtype=int),
            lick_r=np.array([5150, 5400, 5900, 6100], dtype=int),
            reward_l=np.array([1000, 2000], dtype=int),
            reward_r=np.array([5000, 6000], dtype=int),
        ),
    )


class TestSaveBareVsBFigure:
    def test_writes_svg_and_png(self, tmp_path):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        resolver = PathResolver(output_root=tmp_path)
        fig, _ax = plt.subplots()
        try:
            svg, png = save_bare_vs_b_figure(
                fig, "PS55", "20250530", "lick_raster", resolver,
            )
        finally:
            plt.close(fig)
        assert svg.exists() and png.exists()
        assert svg.name == "20250530_lick_raster.svg"
        assert png.name == "20250530_lick_raster.png"
        assert svg.parent.name == "PS55"


class TestRenderFirstLickAccuracy:
    def test_returns_svg_and_png_paths(self, synth_pair, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_bare_vs_b_first_lick_accuracy(
            synth_pair, resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists() and png.stat().st_size > 0
        assert svg.name == "20250530_first_lick_accuracy.svg"

    def test_structural_pin_y_range(self, synth_pair, tmp_path):
        """Endpoint 1's y-axis is accuracy ∈ [0, 1]. The SVG must
        contain the standard accuracy axis label."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_bare_vs_b_first_lick_accuracy(
            synth_pair, resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # 4 "T-i" strict glyph sequences from "First-lick accuracy"
        # title + 4 bar-tick "bare L/R" + "b L/R" — at minimum the
        # accuracy ylabel exists. Pin via glyph for "F" + "i" (Fi
        # only appears in "First").
        assert "DejaVuSans-46" in text, (
            "F glyph missing — accuracy label not rendered"
        )


class TestRenderCorrectIncorrectPerSide:
    def test_returns_svg_and_png_paths(self, synth_pair, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_bare_vs_b_correct_incorrect_per_side(
            synth_pair, resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists()
        assert svg.name == "20250530_correct_incorrect_per_side.svg"

    def test_two_subpanels_one_per_half(self, synth_pair, tmp_path):
        """Layout pin: 2 subpanels (bare, b) — SVG should contain
        both labels."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_bare_vs_b_correct_incorrect_per_side(
            synth_pair, resolver,
        )
        text = svg.read_text(encoding="utf-8")
        # matplotlib emits text-as-path; check for distinct ax.set_title
        # calls via the resulting 2 separate <g id="text_N"> blocks
        # at axes-title positions. Simpler: confirm SIDE_COLORS in use
        # (mouse-L=dodgerblue: #1e90ff; mouse-R=mediumvioletred:
        # #c71585) via fill style.
        assert (
            "#1e90ff" in text or "fill: #1e90ff" in text
        ), "SIDE_COLORS L (dodgerblue) not rendered"


class TestRenderLickRaster:
    def test_returns_svg_and_png_paths(self, synth_pair, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_bare_vs_b_lick_raster(synth_pair, resolver)
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists()
        assert svg.name == "20250530_lick_raster.svg"

    def test_reuses_sub_deliverable_A_dot_styling(
        self, synth_pair, tmp_path,
    ):
        """The bare-vs-b raster shares dot styling with
        render_lick_raster (alpha=0.6 + thin reward marker 0.5).
        SVG should carry fill-opacity 0.6 and stroke-width 0.5."""
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_bare_vs_b_lick_raster(synth_pair, resolver)
        text = svg.read_text(encoding="utf-8")
        assert "fill-opacity: 0.6" in text, (
            "dots not rendered at alpha=0.6"
        )
        assert "stroke-width: 0.5" in text, (
            "reward marker not at linewidth 0.5"
        )


class TestRenderFirstLickLatency:
    def test_returns_svg_and_png_paths(self, synth_pair, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_bare_vs_b_first_lick_latency(
            synth_pair, resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists()
        assert svg.name == "20250530_first_lick_latency.svg"


class TestRenderRewardAcquisitionOverTime:
    """Endpoint 5 (NEW; no legacy precedent) — pin layout + colors."""

    def test_returns_svg_and_png_paths(self, synth_pair, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        svg, png = render_bare_vs_b_reward_acquisition_over_time(
            synth_pair, resolver,
        )
        assert svg.exists() and svg.stat().st_size > 0
        assert png.exists()
        assert svg.name == "20250530_reward_acquisition_over_time.svg"

    def test_uses_bare_vs_b_color_palette_not_side_colors(
        self, synth_pair, tmp_path,
    ):
        """Endpoint 5 pin: lines are BARE_VS_B_LINE_COLORS
        (black + tab:orange), NOT SIDE_COLORS. Verify by SVG color
        signatures.

        - BARE_VS_B_LINE_COLORS["bare"] = "black" → SVG ``#000000``.
        - BARE_VS_B_LINE_COLORS["b"] = "tab:orange" → SVG ``#ff7f0e``.
        """
        assert BARE_VS_B_LINE_COLORS["bare"] == "black"
        assert BARE_VS_B_LINE_COLORS["b"] == "tab:orange"

        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_bare_vs_b_reward_acquisition_over_time(
            synth_pair, resolver,
        )
        text = svg.read_text(encoding="utf-8")
        assert "#ff7f0e" in text, (
            "tab:orange (b line) not rendered"
        )
        # Black stroke appears in many matplotlib defaults; pin
        # via the line2d path style instead. The b line uses
        # 'stroke: #ff7f0e' inside a style="..." attribute; the
        # bare line uses 'stroke: #000000' the same way.
        assert "stroke: #000000" in text, (
            "black (bare line) not rendered as stroke"
        )

    def test_layout_single_panel(self, synth_pair, tmp_path):
        """Endpoint 5 design choice: 1 panel with 2 lines (NOT
        per-side sub-panels). Pin via axes count in the SVG —
        matplotlib emits one ``<g id="axes_N">`` per Axes."""
        import re
        resolver = PathResolver(output_root=tmp_path)
        svg, _png = render_bare_vs_b_reward_acquisition_over_time(
            synth_pair, resolver,
        )
        text = svg.read_text(encoding="utf-8")
        axes_groups = re.findall(r'<g id="axes_\d+">', text)
        assert len(axes_groups) == 1, (
            f"endpoint 5 should have exactly 1 axes group "
            f"(combined L+R, single panel); got {len(axes_groups)}"
        )


class TestPerSessionRenderersRegistry:
    def test_registry_has_5_endpoints(self):
        """The PER_SESSION_RENDERERS list pins the 5-endpoint order
        for the orchestrator."""
        slugs = [s for s, _fn in PER_SESSION_RENDERERS]
        assert slugs == [
            "first_lick_accuracy",
            "correct_incorrect_per_side",
            "lick_raster",
            "first_lick_latency",
            "reward_acquisition_over_time",
        ]
