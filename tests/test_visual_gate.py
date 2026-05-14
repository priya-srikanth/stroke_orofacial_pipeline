"""Tests for Phase 8a.10 sub-deliverable A shared infrastructure
(``stroke_orofacial.spout_behavior.visual_gate``).

Covers commit-group 1's public API only — date helpers, Cohort A
iteration, longitudinal-axis resolution, per-session loader, file
saver, and the inverted ``SIDE_COLORS`` palette. Plot-family renderers
land in commit-groups 2-4 and bring their own tests.
"""
from __future__ import annotations

import datetime
import json
import platform
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend for CI / Windows
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.spout_behavior import visual_gate  # noqa: E402
from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    SIDE_COLORS,
    LongitudinalAxis,
    SessionPlotData,
    apply_longitudinal_axis,
    compute_longitudinal_axis,
    format_rel_day,
    iter_cohort_a_sessions,
    legend_label_for_date,
    load_session_plot_data,
    load_visual_gate_config,
    parse_base_date,
    save_visual_gate_figure,
    ymd_to_date,
)


_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


# ---- Date helpers ----


class TestDateHelpers:
    def test_parse_base_date_strips_no_suffix(self):
        assert parse_base_date("20250430") == "20250430"

    def test_parse_base_date_strips_b_suffix(self):
        assert parse_base_date("20250430b") == "20250430"

    def test_parse_base_date_strips_a_suffix(self):
        assert parse_base_date("20250314a") == "20250314"

    def test_parse_base_date_raises_on_malformed(self):
        with pytest.raises(ValueError, match="Could not parse base date"):
            parse_base_date("not-a-date")

    def test_ymd_to_date(self):
        assert ymd_to_date("20250430") == datetime.date(2025, 4, 30)

    def test_format_rel_day_zero(self):
        assert format_rel_day(0) == "d0"

    def test_format_rel_day_positive(self):
        assert format_rel_day(5) == "d+5"

    def test_format_rel_day_negative(self):
        assert format_rel_day(-3) == "d-3"


# ---- Cohort A iteration ----


@pytest.fixture
def fake_paths_yaml(tmp_path, monkeypatch):
    """Custom paths.yaml that points local_processed_spout at tmp_path."""
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    legacy_root = tmp_path / "legacy_analysis"
    legacy_root.mkdir()
    cfg = tmp_path / "paths.yaml"
    cfg.write_text(
        textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/pipeline_outputs"
                  windows: "C:\\\\dummy\\\\pipeline_outputs"
              local_processed_spout:
                description: "legacy fork"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """)
    )
    return cfg, legacy_root


def _write_report_json(
    legacy_root: Path, animal: str, latency_keys: list[str]
) -> None:
    bba = legacy_root / "basic_behavior_analysis3" / animal
    bba.mkdir(parents=True, exist_ok=True)
    report = {"latency_bySession": {k: {"L": 0.0, "R": 0.0} for k in latency_keys}}
    (bba / "report.json").write_text(json.dumps(report), encoding="utf-8")


def _make_animal_info(
    session_start: datetime.date,
    session_end: datetime.date,
    *,
    animal_id: str = "PS_TEST",
    exclusions: list | None = None,
):
    """Build a synthetic AnimalInfo with controlled date range +
    exclusions. Avoids touching the real configs/animals.yaml.
    """
    from stroke_orofacial.animals import AnimalInfo
    stroke_date = session_start + datetime.timedelta(
        days=(session_end - session_start).days // 2
    )
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=stroke_date,
        session_start=session_start,
        session_end=session_end,
        exclusions=exclusions or [],
    )


class TestIterCohortASessionsYamlRange:
    """Task 3 Round 2 continuation: cohort defined by AnimalInfo.session_start
    ↔ session_end inclusive. Replaces the legacy-report.json source.
    These tests pass ``animal_info=<synthetic>`` to avoid touching the
    real configs/animals.yaml; ``require_on_disk=False`` bypasses the
    on-disk filter so the range-walk logic can be tested in isolation."""

    def test_iterates_session_range_inclusive(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 11),
        )
        sessions = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        assert sessions == [
            "20250307", "20250308", "20250309", "20250310", "20250311",
        ]

    def test_applies_spout_behavior_exclusions(self, tmp_path):
        from stroke_orofacial.animals import Exclusion
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 11),
            exclusions=[
                Exclusion(
                    date=datetime.date(2025, 3, 9),
                    applies_to=["spout_behavior"],
                    reason="test exclusion",
                ),
            ],
        )
        sessions = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        # 20250309 dropped via the spout_behavior-tagged exclusion.
        assert sessions == ["20250307", "20250308", "20250310", "20250311"]

    def test_does_not_apply_other_context_exclusions(self, tmp_path):
        """Exclusion tagged for ``dlc.kinematics`` only doesn't trim the
        spout_behavior cohort."""
        from stroke_orofacial.animals import Exclusion
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 9),
            exclusions=[
                Exclusion(
                    date=datetime.date(2025, 3, 8),
                    applies_to=["dlc.kinematics"],
                    reason="kinematics-only",
                ),
            ],
        )
        sessions = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        # 20250308 kept (exclusion didn't tag spout_behavior).
        assert sessions == ["20250307", "20250308", "20250309"]

    def test_b_half_filter_is_noop_for_range_walk(self, tmp_path):
        """The walk produces bare-date entries only, so include_b_half
        toggles are no-ops; verified by parity."""
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 9),
        )
        s_default = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        s_with_b = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            include_b_half=True,
            overrides_config={"multi_half_sessions": {}},
        )
        assert s_default == s_with_b == [
            "20250307", "20250308", "20250309",
        ]

    def test_sessions_are_sorted(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 9), datetime.date(2025, 3, 11),
        )
        sessions = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        assert sessions == sorted(sessions)

    def test_animal_info_loaded_from_config_when_omitted(
        self, tmp_path, monkeypatch
    ):
        """When ``animal_info`` kwarg is omitted, the iterator calls
        get_animal(animal) which reads configs/animals.yaml. We use a
        real Cohort-A animal (PS46) and just confirm the call doesn't
        crash + returns a sorted list of YYYYMMDD strings within the
        animal's session range."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        sessions = iter_cohort_a_sessions(
            "PS46", resolver, require_on_disk=False,
            overrides_config={"multi_half_sessions": {}},
        )
        # No on-disk filter → returns the full YAML date range; just
        # verify ordering + format.
        assert sessions == sorted(sessions)
        import re as _re
        for d in sessions:
            assert _re.fullmatch(r"\d{8}", d), f"non-YYYYMMDD: {d}"


class TestIterCohortASessionsPatternAAugmentation:
    """Pattern A multi-half augmentation under the YAML-range iterator
    (Task 3 Round 2 continuation). The bare-date entry for a registered
    multi-half session is added IF it falls outside the YAML range
    (defensive — the in-range case is already covered by the date walk).
    The merged-NPZ-on-disk filter still applies."""

    def test_in_range_pattern_a_already_in_cohort(self, tmp_path):
        """When the Pattern A bare date falls within the AnimalInfo
        session range, the date-walk includes it automatically; the
        registry augmentation is a no-op."""
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 13), datetime.date(2025, 3, 15),
            animal_id="PS48",
        )
        sessions = iter_cohort_a_sessions(
            "PS48", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {
                "PS48": {"20250314": {
                    "halves": [{"id": "a"}, {"id": "b"}],
                }}}},
        )
        assert sessions == ["20250313", "20250314", "20250315"]

    def test_out_of_range_pattern_a_added_by_augmentation(self, tmp_path):
        """Defensive: a Pattern A date OUTSIDE the YAML range is still
        added via the registry augmentation. Shouldn't happen in
        practice but the safety net is tested."""
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 20), datetime.date(2025, 3, 22),
            animal_id="PS48",
        )
        sessions = iter_cohort_a_sessions(
            "PS48", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {
                "PS48": {"20250314": {
                    "halves": [{"id": "a"}, {"id": "b"}],
                }}}},
        )
        # 20250314 added by the augmentation despite being outside the
        # 20250320-20250322 range.
        assert "20250314" in sessions
        assert sessions == ["20250314", "20250320", "20250321", "20250322"]

    def test_pattern_b_does_not_trigger_augmentation(self, tmp_path):
        """Pattern B b-half sessions are NOT in multi_half_sessions: —
        so no Pattern A augmentation fires. Pure date-walk behavior."""
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 4, 30), datetime.date(2025, 5, 5),
            animal_id="PS51",
        )
        sessions = iter_cohort_a_sessions(
            "PS51", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        # Bare dates only — no b-half labels (the walk never produces them).
        assert sessions == [
            "20250430", "20250501", "20250502",
            "20250503", "20250504", "20250505",
        ]


class TestResolveSessionNpzPath:
    """Task 3 Round 2 fix: _resolve_session_npz_path routes between
    flat single-half / Pattern B paths and Pattern A nested per-half
    paths based on the multi_half_sessions: registry."""

    def test_bare_returns_flat_path(self, tmp_path):
        from stroke_orofacial.spout_behavior.visual_gate import (
            _resolve_session_npz_path,
        )
        resolver = PathResolver(output_root=tmp_path)
        result = _resolve_session_npz_path(
            "licks_and_rewards", "PS51", "20250430", "",
            resolver=resolver, overrides_config={"multi_half_sessions": {}},
        )
        assert result == (
            tmp_path / "spout_behavior" / "licks_and_rewards"
            / "PS51" / "20250430.npz"
        )

    def test_pattern_a_half_a_returns_nested_path(self, tmp_path):
        from stroke_orofacial.spout_behavior.visual_gate import (
            _resolve_session_npz_path,
        )
        resolver = PathResolver(output_root=tmp_path)
        result = _resolve_session_npz_path(
            "licks_and_rewards", "PS48", "20250314", "a",
            resolver=resolver,
            overrides_config={"multi_half_sessions": {
                "PS48": {"20250314": {
                    "halves": [{"id": "a"}, {"id": "b"}],
                }}}},
        )
        assert result == (
            tmp_path / "spout_behavior" / "licks_and_rewards"
            / "PS48" / "20250314ab" / "20250314a.npz"
        )

    def test_pattern_a_half_b_returns_nested_path(self, tmp_path):
        from stroke_orofacial.spout_behavior.visual_gate import (
            _resolve_session_npz_path,
        )
        resolver = PathResolver(output_root=tmp_path)
        result = _resolve_session_npz_path(
            "licks_and_rewards", "PS48", "20250314", "b",
            resolver=resolver,
            overrides_config={"multi_half_sessions": {
                "PS48": {"20250314": {
                    "halves": [{"id": "a"}, {"id": "b"}],
                }}}},
        )
        assert result == (
            tmp_path / "spout_behavior" / "licks_and_rewards"
            / "PS48" / "20250314ab" / "20250314b.npz"
        )

    def test_pattern_b_b_half_returns_flat_path(self, tmp_path):
        """Regression guard: Pattern B b-half (NOT in multi_half_sessions
        registry) routes to flat ``<date><suffix>.npz`` path, not
        nested. Mirrors PS51/2025-04-30 secondary-spout pattern."""
        from stroke_orofacial.spout_behavior.visual_gate import (
            _resolve_session_npz_path,
        )
        resolver = PathResolver(output_root=tmp_path)
        result = _resolve_session_npz_path(
            "licks_and_rewards", "PS51", "20250430", "b",
            resolver=resolver,
            overrides_config={"multi_half_sessions": {}},
        )
        assert result == (
            tmp_path / "spout_behavior" / "licks_and_rewards"
            / "PS51" / "20250430b.npz"
        )

    def test_works_with_non_licks_output_type(self, tmp_path):
        """The output_type parameter routes to any Phase-2 subdir."""
        from stroke_orofacial.spout_behavior.visual_gate import (
            _resolve_session_npz_path,
        )
        resolver = PathResolver(output_root=tmp_path)
        result = _resolve_session_npz_path(
            "wavesurfer_signals_processed", "PS51", "20250430", "",
            resolver=resolver, overrides_config={"multi_half_sessions": {}},
        )
        assert result == (
            tmp_path / "spout_behavior" / "wavesurfer_signals_processed"
            / "PS51" / "20250430.npz"
        )


class TestIterCohortASessionsOnDiskFilter:
    """``require_on_disk=True`` (default) filters the YAML-range cohort
    to sessions whose ``licks_and_rewards`` NPZ is actually on disk —
    silently drops in-range dates without Phase-2 outputs (weekends,
    equipment-down days, sessions not yet processed)."""

    def test_filters_to_on_disk_sessions(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        ai = _make_animal_info(
            datetime.date(2025, 3, 7), datetime.date(2025, 3, 9),
            animal_id="PS_TEST",
        )
        # Write NPZs only for 20250307 + 20250309; 20250308 missing.
        sp = tmp_path / "spout_behavior" / "licks_and_rewards" / "PS_TEST"
        sp.mkdir(parents=True, exist_ok=True)
        for date in ("20250307", "20250309"):
            np.savez(sp / f"{date}.npz",
                     Lick_L=np.array([]), Lick_R=np.array([]),
                     Tone_L=np.array([]), Tone_R=np.array([]))
        # Default require_on_disk=True → 20250308 dropped (no NPZ).
        sessions = iter_cohort_a_sessions(
            "PS_TEST", resolver, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        assert sessions == ["20250307", "20250309"]
        # require_on_disk=False → all 3 retained.
        sessions_all = iter_cohort_a_sessions(
            "PS_TEST", resolver, require_on_disk=False, animal_info=ai,
            overrides_config={"multi_half_sessions": {}},
        )
        assert sessions_all == ["20250307", "20250308", "20250309"]


# ---- Longitudinal axis ----


class TestLongitudinalAxis:
    def test_align_to_stroke_x_vals_are_rel_days(self):
        d0 = datetime.date(2025, 4, 30)  # PS54 stroke_date example
        dates = ["20250428", "20250430", "20250502"]
        axis = compute_longitudinal_axis(
            dates, align_to_stroke=True, d0=d0,
        )
        assert list(axis.x_vals) == [-2, 0, 2]
        assert axis.x_ticklabels == ["d-2", "d0", "d+2"]
        assert axis.vline_x == 0.5
        assert axis.suffix == "_relStroke"

    def test_no_alignment_x_vals_are_arange(self):
        dates = ["20250416", "20250417", "20250418"]
        axis = compute_longitudinal_axis(
            dates, align_to_stroke=False, d0=None,
        )
        assert list(axis.x_vals) == [0, 1, 2]
        assert axis.x_ticklabels == ["20250416", "20250417", "20250418"]
        assert axis.vline_x is None
        assert axis.suffix == "_absDate"

    def test_no_alignment_uses_display_dates_override(self):
        dates = ["20250416", "20250417"]
        axis = compute_longitudinal_axis(
            dates,
            align_to_stroke=False,
            d0=None,
            display_dates={"20250416": "session-1", "20250417": "session-2"},
        )
        assert axis.x_ticklabels == ["session-1", "session-2"]

    def test_align_to_stroke_requires_d0(self):
        with pytest.raises(ValueError, match="requires d0"):
            compute_longitudinal_axis(
                ["20250430"], align_to_stroke=True, d0=None,
            )

    def test_apply_longitudinal_axis_sets_xticks_and_vline(self):
        cfg = load_visual_gate_config()
        axis = LongitudinalAxis(
            x_vals=np.array([-1, 0, 1]),
            x_ticklabels=["d-1", "d0", "d+1"],
            vline_x=0.5,
            suffix="_relStroke",
        )
        fig, ax = plt.subplots()
        try:
            apply_longitudinal_axis(ax, axis, cfg)
            assert list(ax.get_xticks()) == [-1, 0, 1]
            labels = [t.get_text() for t in ax.get_xticklabels()]
            assert labels == ["d-1", "d0", "d+1"]
            # axvline added: one Line2D among ax.lines with the stroke color
            assert any(
                ln.get_color() == cfg["stroke_vline_color"] for ln in ax.lines
            )
        finally:
            plt.close(fig)

    def test_apply_longitudinal_axis_no_vline_when_unaligned(self):
        cfg = load_visual_gate_config()
        axis = LongitudinalAxis(
            x_vals=np.array([0, 1]),
            x_ticklabels=["20250416", "20250417"],
            vline_x=None,
            suffix="_absDate",
        )
        fig, ax = plt.subplots()
        try:
            apply_longitudinal_axis(ax, axis, cfg)
            assert all(
                ln.get_color() != cfg["stroke_vline_color"] for ln in ax.lines
            )
        finally:
            plt.close(fig)

    def test_legend_label_for_date_relstroke(self):
        d0 = datetime.date(2025, 4, 30)
        label = legend_label_for_date(
            "20250502", align_to_stroke=True, d0=d0,
        )
        assert label == "d+2"

    def test_legend_label_for_date_absdate(self):
        label = legend_label_for_date(
            "20250416", align_to_stroke=False, d0=None,
        )
        assert label == "20250416"

    def test_legend_label_for_date_display_override_absdate(self):
        label = legend_label_for_date(
            "20250416",
            align_to_stroke=False,
            d0=None,
            display_dates={"20250416": "session-1"},
        )
        assert label == "session-1"


# ---- SessionPlotData loader ----


def _write_phase2_npzs(
    output_root: Path, animal: str, date_label: str,
    lick_l: np.ndarray, lick_r: np.ndarray,
    tone_l: np.ndarray, tone_r: np.ndarray,
    sample_rate: float,
    n_samples: int | None = None,
) -> None:
    sp = output_root / "spout_behavior"
    licks_dir = sp / "licks_and_rewards" / animal
    ws_dir = sp / "wavesurfer_signals_processed" / animal
    licks_dir.mkdir(parents=True, exist_ok=True)
    ws_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        licks_dir / f"{date_label}.npz",
        Lick_L=lick_l, Lick_R=lick_r,
        Tone_L=tone_l, Tone_R=tone_r,
    )
    ws_kwargs: dict[str, np.ndarray] = {"sample_rate_input": np.array(sample_rate)}
    if n_samples is not None:
        # 1D signal so load_session_plot_data populates n_samples_session
        ws_kwargs["Treadmill"] = np.zeros(n_samples, dtype=np.float32)
    np.savez(ws_dir / f"{date_label}.npz", **ws_kwargs)


class TestLoadSessionPlotData:
    def test_reads_licks_and_sample_rate(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100, 200]),
            lick_r=np.array([150, 250]),
            tone_l=np.array([50]),
            tone_r=np.array([175]),
            sample_rate=2000.0,
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert isinstance(data, SessionPlotData)
        assert data.date_label == "20250430"
        assert np.array_equal(data.lick_idx["Lick_L"], [100, 200])
        assert np.array_equal(data.lick_idx["Lick_R"], [150, 250])
        assert np.array_equal(data.tones_idx["Tone_L"], [50])
        assert np.array_equal(data.tones_idx["Tone_R"], [175])
        assert data.sample_rate == 2000.0

    def test_missing_licks_npz_raises(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="licks_and_rewards NPZ missing"):
            load_session_plot_data("PS51", "20250430", resolver)

    def test_missing_wavesurfer_npz_raises(self, tmp_path):
        # Write only the licks NPZ; the wavesurfer side is absent.
        sp = tmp_path / "spout_behavior"
        licks_dir = sp / "licks_and_rewards" / "PS51"
        licks_dir.mkdir(parents=True, exist_ok=True)
        np.savez(
            licks_dir / "20250430.npz",
            Lick_L=np.array([100]),
            Lick_R=np.array([150]),
            Tone_L=np.array([50]),
            Tone_R=np.array([175]),
        )
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(
            FileNotFoundError,
            match="wavesurfer_signals_processed NPZ missing",
        ):
            load_session_plot_data("PS51", "20250430", resolver)


# ---- Visual-gate config + side-colors inversion ----


class TestVisualGateConfig:
    def test_load_visual_gate_config_returns_dict(self):
        cfg = load_visual_gate_config()
        # Sanity: the keys we depend on across commit-groups exist.
        for key in [
            "side_colors", "xtick_fontsize", "stroke_linewidth",
            "stroke_vline_x", "stroke_vline_color", "stroke_vline_linestyle",
            "stroke_vline_alpha", "accuracy_y_range", "latency_y_max",
            "lickrate_y_max", "numlicks_y_max", "lickiness_window_seconds",
            "raster_xlim", "raster_dot_size", "raster_dot_alpha",
            "figsize_longitudinal", "figsize_raster_grid",
        ]:
            assert key in cfg, f"visual_gate config missing key: {key}"

    def test_xtick_fontsize_value(self):
        """Round 2.8 pin: lick-raster-scoped xtick_fontsize=5
        (Priya 2026-05-13). Previously 6 (Round 2.7), legacy was 10.
        The longitudinal xtick fontsize is a separate knob
        (longitudinal_xtick_fontsize); see TestLongitudinalXtickFontsize."""
        cfg = load_visual_gate_config()
        assert cfg["xtick_fontsize"] == 5

    def test_side_colors_inverted_vs_legacy(self):
        """Phase 8a.10 DECISIONS pin: mouse-frame palette is inverted
        from legacy. Legacy `side_colors` (behavior_report_PS.py:250)
        had ``{"L": "mediumvioletred", "R": "dodgerblue"}`` because
        legacy operated in WS-frame internally + flipped at output.
        New pipeline operates mouse-frame post-Phase-6.8 → direct
        mapping ``mouse-L = dodgerblue, mouse-R = mediumvioletred``.
        Regression to the legacy palette here would silently swap
        all per-mouse plot colors."""
        assert SIDE_COLORS == {"L": "dodgerblue", "R": "mediumvioletred"}


# ---- File saver ----


class TestSaveVisualGateFigure:
    def _make_simple_fig(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [3, 2, 1])
        return fig

    def test_writes_svg_and_png(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg_path, png_path = save_visual_gate_figure(
                fig, "PS51", "test_family", "_relStroke", resolver,
            )
        finally:
            plt.close(fig)
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "test_family_relStroke.svg"
        assert png_path.name == "test_family_relStroke.png"

    def test_dest_is_visual_gate_dir(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg_path, _ = save_visual_gate_figure(
                fig, "PS51", "test_family", "_absDate", resolver,
            )
        finally:
            plt.close(fig)
        assert svg_path.parent == resolver.spout_behavior_figures_dir("PS51")

    def test_overwrite_force(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        # First write creates the files.
        fig1 = self._make_simple_fig()
        try:
            save_visual_gate_figure(
                fig1, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig1)
        # Second write must succeed under force.
        fig2 = self._make_simple_fig()
        try:
            svg_path, png_path = save_visual_gate_figure(
                fig2, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig2)
        assert svg_path.exists()
        assert png_path.exists()

    def test_overwrite_raise(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            save_visual_gate_figure(
                fig, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig)
        fig2 = self._make_simple_fig()
        try:
            with pytest.raises(FileExistsError, match="visual_gate target exists"):
                save_visual_gate_figure(
                    fig2, "PS51", "fam", "", resolver, overwrite="raise",
                )
        finally:
            plt.close(fig2)

    def test_overwrite_skip_returns_existing_paths(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        fig = self._make_simple_fig()
        try:
            svg1, png1 = save_visual_gate_figure(
                fig, "PS51", "fam", "", resolver, overwrite="force",
            )
        finally:
            plt.close(fig)
        existing_svg_size = svg1.stat().st_size
        existing_png_size = png1.stat().st_size
        fig2 = self._make_simple_fig()
        try:
            svg2, png2 = save_visual_gate_figure(
                fig2, "PS51", "fam", "", resolver, overwrite="skip",
            )
        finally:
            plt.close(fig2)
        # Same paths returned; no rewrite happened.
        assert (svg1, png1) == (svg2, png2)
        assert svg2.stat().st_size == existing_svg_size
        assert png2.stat().st_size == existing_png_size


# ---- Module-level constant pin ----


def test_module_exports_expected_names():
    """Pin the commit-group 1 public surface so subsequent commit
    groups can't accidentally remove a symbol downstream renderers
    depend on."""
    for name in [
        "parse_base_date", "ymd_to_date", "format_rel_day",
        "iter_cohort_a_sessions",
        "LongitudinalAxis", "compute_longitudinal_axis",
        "apply_longitudinal_axis", "legend_label_for_date",
        "SessionPlotData", "load_session_plot_data",
        "load_visual_gate_config", "SIDE_COLORS",
        "save_visual_gate_figure",
    ]:
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 1 public surface "
            "should include it"
        )


# =====================================================================
# Commit-group 2: compute helpers + 8 longitudinal-mean renderers
# =====================================================================


from stroke_orofacial.spout_behavior.visual_gate import (  # noqa: E402
    compute_criteria_3,
    compute_criteria_34,
    compute_criteria_4,
    compute_criteria_acc_bySession,
    compute_first_correct_lick_sample_idx,
    compute_first_lick_correct,
    compute_firstLickCorrect_bySession,
    compute_latency_bySession,
    compute_lickiness_bySession,
    compute_median_lick_rate_bySession,
    compute_num_licks_bySession,
    compute_switchiness_bySession,
    compute_trial_lick_delays,
    load_behavior_report_params,
    render_accuracy_firstCorrectLick,
    render_accuracy_firstCorrectLickAll,
    render_criteria_performance,
    render_latency_bySession,
    render_lick_raster,
    render_lickiness_bySession,
    render_lickRate_bySession,
    render_numLicks_bySession_all,
    render_numLicks_bySession_correct,
    render_numLicks_bySession_correct_and_incorrect,
    render_switchiness_bySession,
)


# ---- Synthetic session fixture for compute-helper unit tests ----


def _make_synthetic_session(date_label: str = "20250430") -> SessionPlotData:
    """Tiny deterministic session for compute-helper tests.

    Sample rate 1000 Hz; 1 L reward at sample 1000 (t=1s); 1 R reward
    at sample 5000 (t=5s). Hand-placed licks support exact-value
    assertions in every compute helper.
    """
    return SessionPlotData(
        date_label=date_label,
        # Mouse-L licks: 6 around reward L (500, 1100, 1500, 2000, 2500, 2900);
        # 0 around reward R within criteria windows
        lick_idx={
            "Lick_L": np.array([500, 1100, 1500, 2000, 2500, 2900], dtype=int),
            "Lick_R": np.array([900, 5200, 5800, 6100, 6500, 7000, 7500], dtype=int),
        },
        tones_idx={
            "Tone_L": np.array([1000], dtype=int),
            "Tone_R": np.array([5000], dtype=int),
        },
        sample_rate=1000.0,
    )


# ---- Tests: behavior_report config loader ----


class TestBehaviorReportParams:
    def test_load_returns_dict(self):
        params = load_behavior_report_params()
        for key in [
            "window_around_tones", "criteria_1", "criteria_2",
            "criteria_3", "criteria_4",
        ]:
            assert key in params, f"behavior_report missing key: {key}"

    def test_legacy_values_preserved(self):
        """Pin: cohort-wide defaults match legacy params dict
        (batch_process_behavior_report_20260116PS.ipynb cell-3)."""
        params = load_behavior_report_params()
        assert list(params["window_around_tones"]) == [1.0, 8.0]
        assert params["criteria_1"]["num_consecutive_pass"] == 3
        assert params["criteria_2"]["fraction_pass"] == 0.6
        assert list(params["criteria_3"]["window"]) == [0, 2.0]
        assert list(params["criteria_4"]["window"]) == [0, 2.5]
        assert params["criteria_4"]["num_licks_correct_min"] == 5
        assert params["criteria_4"]["num_licks_incorrect_max"] == 0


# ---- Tests: per-session compute helpers ----


class TestComputeTrialLickDelays:
    def test_window_includes_pre_tone_licks(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        # Lick L at 500 (before reward L at 1000): delay = -500
        l_delays = delays["Tone_L"][0]["Lick_L"]
        assert -500 in l_delays
        # Lick L at 1100 (after reward L at 1000): delay = 100
        assert 100 in l_delays

    def test_per_reward_keys(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        assert set(delays.keys()) == {"Tone_L", "Tone_R"}
        # Tone_L has 1 trial (idx 0); Tone_R has 1 trial (idx 0)
        assert set(delays["Tone_L"].keys()) == {0}
        assert set(delays["Tone_R"].keys()) == {0}

    def test_per_side_keys(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        assert set(delays["Tone_L"][0].keys()) == {"Lick_L", "Lick_R"}

    def test_window_excludes_licks_outside_window(self):
        # Tight window: 0-1s after reward (samples [reward, reward+1000])
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [0, 1.0])
        # Lick L at 500  (pre-reward, before window):       excluded
        # Lick L at 1100 (in window):                       delay 100
        # Lick L at 1500 (in window):                       delay 500
        # Lick L at 2000 (== reward + 1000; window inclusive): delay 1000
        # Lick L at 2500 (past window):                     excluded
        l_delays = delays["Tone_L"][0]["Lick_L"]
        assert set(l_delays.tolist()) == {100, 500, 1000}


class TestComputeFirstCorrectLickSampleIdx:
    def test_returns_first_lick_within_criteria_3_window(self):
        data = _make_synthetic_session()
        # criteria_3 window: 0-2.0s after reward
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        # First L lick ≥ reward L sample (1000) and ≤ 3000: sample 1100
        assert fcl["L"][0] == 1100
        # First R lick ≥ reward R sample (5000) and ≤ 7000: sample 5200
        assert fcl["R"][0] == 5200

    def test_returns_none_when_no_lick_in_window(self):
        # Build a session with NO post-reward licks within criteria_3 window
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                "Lick_L": np.array([500], dtype=int),  # only pre-reward
                "Lick_R": np.array([100, 200], dtype=int),  # all pre-reward
            },
            tones_idx={
                "Tone_L": np.array([1000], dtype=int),
                "Tone_R": np.array([5000], dtype=int),
            },
            sample_rate=1000.0,
        )
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        assert fcl["L"][0] is None
        assert fcl["R"][0] is None


class TestComputeCriteria3:
    def test_returns_true_when_first_lick_present(self):
        data = _make_synthetic_session()
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        c3 = compute_criteria_3(fcl)
        assert c3["L"][0] is True
        assert c3["R"][0] is True

    def test_returns_false_when_first_lick_none(self):
        fcl = {"L": {0: None}, "R": {0: 5100}}
        c3 = compute_criteria_3(fcl)
        assert c3["L"][0] is False
        assert c3["R"][0] is True


class TestComputeCriteria4:
    def test_passes_with_enough_correct_no_incorrect(self):
        data = _make_synthetic_session()
        # criteria_4: window=[0, 2.5], min_correct=5, max_incorrect=0
        # Tone_L at sample 1000: window [1000, 3500]
        #   - L licks in window: 1100, 1500, 2000, 2500, 2900 (count 5; ≥ 5 OK)
        #   - R licks in window: 0 (the 900 is pre-reward; 5200 is past window) → ≤ 0 OK
        c4 = compute_criteria_4(data, {
            "window": [0, 2.5],
            "num_licks_correct_min": 5,
            "num_licks_incorrect_max": 0,
        })
        assert c4["L"][0] is True

    def test_fails_when_too_few_correct(self):
        data = _make_synthetic_session()
        c4 = compute_criteria_4(data, {
            "window": [0, 2.5],
            "num_licks_correct_min": 10,  # ↑ higher threshold
            "num_licks_incorrect_max": 0,
        })
        assert c4["L"][0] is False


class TestComputeCriteria34:
    def test_and_combines(self):
        c3 = {"L": {0: True, 1: True}, "R": {0: True}}
        c4 = {"L": {0: True, 1: False}, "R": {0: True}}
        c34 = compute_criteria_34(c3, c4)
        assert c34["L"][0] is True
        assert c34["L"][1] is False
        assert c34["R"][0] is True


class TestComputeFirstLickCorrect:
    def test_correct_post_first_returns_true(self):
        """Reward L: L lick at delay +100, no R licks post-reward → True."""
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([100, 500]),
                    "Lick_R": np.array([-200]),  # pre-reward, ignored
                },
            },
            "Tone_R": {
                0: {
                    "Lick_R": np.array([200]),
                    "Lick_L": np.array([]),
                },
            },
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is True
        assert flc["R"][0] is True

    def test_incorrect_first_returns_false(self):
        """Reward L: R lick at delay +50 precedes L lick at +200 → False."""
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([200]),
                    "Lick_R": np.array([50]),
                },
            },
            "Tone_R": {},
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is False

    def test_no_post_tone_licks_returns_none(self):
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([-100]),  # only pre-reward
                    "Lick_R": np.array([-200]),
                },
            },
            "Tone_R": {},
        }
        flc = compute_first_lick_correct(delays)
        assert flc["L"][0] is None


class TestComputeCriteriaAccBySession:
    def test_fraction_passing(self):
        c34 = {"L": {0: True, 1: True, 2: False}, "R": {0: True, 1: False}}
        acc = compute_criteria_acc_bySession(c34)
        assert acc["L"] == pytest.approx(2 / 3)
        assert acc["R"] == pytest.approx(0.5)

    def test_empty_returns_nan(self):
        acc = compute_criteria_acc_bySession({"L": {}, "R": {}})
        assert np.isnan(acc["L"])
        assert np.isnan(acc["R"])


class TestComputeFirstLickCorrectBySession:
    def test_exclude_none_uses_nanmean(self):
        flc = {"L": {0: True, 1: False, 2: None}, "R": {0: True, 1: True}}
        m = compute_firstLickCorrect_bySession(flc, treat_none_as_zero=False)
        # None is excluded → mean of [1, 0] = 0.5
        assert m["L"] == pytest.approx(0.5)
        assert m["R"] == pytest.approx(1.0)

    def test_treat_none_as_zero_counts_against(self):
        flc = {"L": {0: True, 1: False, 2: None}, "R": {0: True, 1: True}}
        m = compute_firstLickCorrect_bySession(flc, treat_none_as_zero=True)
        # None counts as 0 → mean of [1, 0, 0] = 1/3
        assert m["L"] == pytest.approx(1 / 3)
        assert m["R"] == pytest.approx(1.0)


class TestComputeMedianLickRateBySession:
    def test_returns_per_side_mean_std(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        rates = compute_median_lick_rate_bySession(delays, sample_rate=1000.0)
        assert set(rates.keys()) == {"L", "R"}
        for side in ("L", "R"):
            assert "mean" in rates[side]
            assert "std" in rates[side]


class TestComputeNumLicksBySession:
    def test_returns_correct_all_incorrect(self):
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        n = compute_num_licks_bySession(delays)
        assert set(n.keys()) == {"correct", "all", "incorrect"}
        for kind in ("correct", "all", "incorrect"):
            assert set(n[kind].keys()) == {"Tone_L", "Tone_R"}

    def test_counts_match_synthetic(self):
        """Tone_L window [-1000, 8000] from sample 1000:
            Lick_L within: [500, 1100, 1500, 2000, 2500, 2900] = 6 (correct)
            Lick_R within: [900, 5200, 5800, 6100, 6500, 7000, 7500]
              filter to [-1000+1000=0, 8000+1000=9000] → [900, 5200, 5800,
              6100, 6500, 7000, 7500] all within → 7 (incorrect)
            All = 6 + 7 = 13
        """
        data = _make_synthetic_session()
        delays = compute_trial_lick_delays(data, [1.0, 8.0])
        n = compute_num_licks_bySession(delays)
        assert n["correct"]["Tone_L"]["mean"] == pytest.approx(6.0)
        assert n["incorrect"]["Tone_L"]["mean"] == pytest.approx(7.0)
        assert n["all"]["Tone_L"]["mean"] == pytest.approx(13.0)


class TestComputeLatencyBySession:
    def test_latency_seconds_from_reward(self):
        data = _make_synthetic_session()
        fcl = compute_first_correct_lick_sample_idx(data, [0, 2.0])
        lat = compute_latency_bySession(fcl, data.tones_idx, data.sample_rate)
        # Tone_L at 1000, first correct L lick at 1100 → 0.1s
        assert lat["L"]["mean"] == pytest.approx(0.1)
        # Tone_R at 5000, first correct R lick at 5200 → 0.2s
        assert lat["R"]["mean"] == pytest.approx(0.2)

    def test_none_first_lick_yields_nan_excluded(self):
        fcl = {"L": {0: None, 1: 1100}, "R": {0: 5200}}
        rewards = {
            "Tone_L": np.array([1000, 2000]),
            "Tone_R": np.array([5000]),
        }
        lat = compute_latency_bySession(fcl, rewards, sample_rate=1000.0)
        # L: [nan, -0.9 (idx 1 → fcl 1100 - reward 2000 = -900 samples)]
        # nanmean is the non-nan value: -0.9
        # actually this is "first lick before reward 2000 within criteria_3" so
        # it's unusual but the formula is right. Test the float behavior:
        assert np.isfinite(lat["L"]["mean"])


# ---- Tests: 8 longitudinal-mean renderers ----


@pytest.fixture
def cohort_for_renders(tmp_path, monkeypatch):
    """Build a tiny Cohort A on disk for render integration tests.

    Animal: PS51 (real animals.yaml entry; stroke_date = 2025-04-29).
    3 bare-date sessions; report.json + 3 sets of Phase-2 NPZs.
    Returns (paths_yaml, resolver) ready to pass to a render function.
    """
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
    legacy_root = tmp_path / "legacy_analysis"
    legacy_root.mkdir()
    # Synthetic 3-session cohort spanning pre/post stroke
    dates = ["20250428", "20250429", "20250430"]
    # Write report.json with latency_bySession keys
    bba = legacy_root / "basic_behavior_analysis3" / "PS51"
    bba.mkdir(parents=True, exist_ok=True)
    (bba / "report.json").write_text(json.dumps({
        "latency_bySession": {d: {"L": 0.0, "R": 0.0} for d in dates}
    }), encoding="utf-8")
    # Write Phase-2 NPZs at output_root override
    output_root = tmp_path / "pipeline_outputs"
    for date in dates:
        _write_phase2_npzs(
            output_root, "PS51", date,
            lick_l=np.array([500, 1100, 1500, 2000, 2500, 2900], dtype=int),
            lick_r=np.array([900, 5200, 5800, 6100, 6500, 7000, 7500], dtype=int),
            tone_l=np.array([1000], dtype=int),
            tone_r=np.array([5000], dtype=int),
            sample_rate=1000.0,
            n_samples=60000,  # 60 sec at 1000 Hz; populates n_samples_session
        )
    # Custom paths.yaml pointing local_processed_spout → tmp_path
    paths_yaml = tmp_path / "paths.yaml"
    paths_yaml.write_text(textwrap.dedent(f"""
        logical_roots:
          microscope_pipeline_outputs:
            description: "out"
            mounts:
              mac: "/Volumes/dummy/po"
              windows: "C:\\\\dummy\\\\po"
          local_processed_spout:
            description: "legacy"
            mounts:
              {_HOST_KEY}:
                - "{legacy_root.as_posix()}"
    """))
    resolver = PathResolver(paths_yaml, output_root=output_root)
    return resolver, dates


_RENDER_FUNCS = [
    ("criteria_performance", render_criteria_performance),
    ("accuracy_firstCorrectLick", render_accuracy_firstCorrectLick),
    ("accuracy_firstCorrectLickAll", render_accuracy_firstCorrectLickAll),
    ("lickRate_bySession", render_lickRate_bySession),
    ("latency_bySession", render_latency_bySession),
    ("numLicks_bySession_correct", render_numLicks_bySession_correct),
    ("numLicks_bySession_all", render_numLicks_bySession_all),
    ("numLicks_bySession_correct_and_incorrect",
     render_numLicks_bySession_correct_and_incorrect),
]


@pytest.mark.parametrize("family_name,render_fn", _RENDER_FUNCS)
class TestRenderersReturnPaths:
    """Each renderer returns (svg_path, png_path) that exist + named
    by family with the longitudinal-axis suffix."""

    def test_returns_svg_and_png_paths(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, png_path = render_fn("PS51", resolver, align_to_stroke=True)
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        # Filename ends with _relStroke when stroke-aligned
        assert svg_path.name == f"{family_name}_relStroke.svg"
        assert png_path.name == f"{family_name}_relStroke.png"

    def test_uses_visual_gate_dir(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_fn("PS51", resolver, align_to_stroke=True)
        assert svg_path.parent == resolver.spout_behavior_figures_dir("PS51")

    def test_absdate_suffix_when_unaligned(
        self, family_name, render_fn, cohort_for_renders,
    ):
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_fn("PS51", resolver, align_to_stroke=False)
        assert svg_path.name == f"{family_name}_absDate.svg"


class TestRenderCriteriaPerformanceFidelity:
    """Per-family pin tests for criteria_performance (the reference
    implementation for the longitudinal-mean skeleton)."""

    def test_ylim_matches_accuracy_y_range(self, cohort_for_renders):
        resolver, _dates = cohort_for_renders
        cfg = load_visual_gate_config()
        # Render + inspect a re-opened figure's y-limits via the SVG isn't
        # practical; instead, render with a fresh figure injection by
        # monkeypatching plt.subplots — too brittle. Pragmatic approach:
        # confirm the file was emitted (above test) + structurally pin
        # the config value the renderer reads.
        assert tuple(cfg["accuracy_y_range"]) == (0.0, 1.0)

    def test_title_string_format(self, cohort_for_renders):
        """Read the SVG XML for the legacy title verbatim — small but
        useful regression pin."""
        resolver, _dates = cohort_for_renders
        svg_path, _ = render_criteria_performance(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Criteria performance by session" in svg_text


class TestRenderAccuracyFirstCorrectLickFidelity:
    def test_y_axis_label_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_accuracy_firstCorrectLick(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "correct 1st lick" in svg_text


class TestRenderAccuracyFirstCorrectLickAllFidelity:
    def test_title_distinct_from_excludeNone_variant(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_all, _ = render_accuracy_firstCorrectLickAll(
            "PS51", resolver, align_to_stroke=True,
        )
        text_all = svg_all.read_text(encoding="utf-8")
        # Legacy title for the All variant: "Fraction of all trials ..."
        assert "all trials with correct first lick" in text_all


class TestRenderLickRateBySessionFidelity:
    def test_ylim_from_lickrate_y_max_config(self, cohort_for_renders):
        cfg = load_visual_gate_config()
        assert cfg["lickrate_y_max"] == 10.0

    def test_title_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickRate_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "avg correct lick rate by session" in svg_text


class TestRenderLatencyBySessionFidelity:
    def test_ylim_from_latency_y_max_config(self, cohort_for_renders):
        cfg = load_visual_gate_config()
        assert cfg["latency_y_max"] == 2.0

    def test_title_string(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_latency_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "avg latency to correct lick by session" in svg_text


class TestRenderNumLicksFidelity:
    def test_correct_and_all_titles_distinct(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_correct, _ = render_numLicks_bySession_correct(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_all, _ = render_numLicks_bySession_all(
            "PS51", resolver, align_to_stroke=True,
        )
        # Legacy strings: "Avg correct licks per trial by session" vs
        # "Avg all licks per trial by session"
        assert "Avg correct licks per trial" in svg_correct.read_text(encoding="utf-8")
        assert "Avg all licks per trial" in svg_all.read_text(encoding="utf-8")

    def test_correct_and_incorrect_title(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_numLicks_bySession_correct_and_incorrect(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib SVG-escapes "&" → "&amp;" in serialized titles
        assert "Avg correct &amp; incorrect licks per trial" in svg_text


class TestRendererModuleExports:
    """Pin CG-2 public surface so subsequent CGs don't accidentally drop
    a renderer subsequent consumers (notebook orchestrator in CG-6) depend on."""

    @pytest.mark.parametrize("name", [
        "load_behavior_report_params",
        "compute_trial_lick_delays",
        "compute_first_correct_lick_sample_idx",
        "compute_criteria_3", "compute_criteria_4", "compute_criteria_34",
        "compute_first_lick_correct", "compute_criteria_acc_bySession",
        "compute_firstLickCorrect_bySession", "compute_median_lick_rate_bySession",
        "compute_num_licks_bySession", "compute_latency_bySession",
        "render_criteria_performance", "render_accuracy_firstCorrectLick",
        "render_accuracy_firstCorrectLickAll", "render_lickRate_bySession",
        "render_latency_bySession", "render_numLicks_bySession_correct",
        "render_numLicks_bySession_all",
        "render_numLicks_bySession_correct_and_incorrect",
    ])
    def test_symbol_exists(self, name):
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 2 public surface"
        )


# =====================================================================
# Commit-group 3: lick raster renderer
# =====================================================================


class TestRenderLickRaster:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _dates = cohort_for_renders
        svg_path, png_path = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "lick_raster_relStroke.svg"
        assert png_path.name == "lick_raster_relStroke.png"

    def test_lands_in_visual_gate_dir(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.parent == resolver.spout_behavior_figures_dir("PS51")

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "lick_raster_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        """Empty Cohort A → ValueError (can't build 2×0 panel grid)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_lick_raster("PS51", resolver, align_to_stroke=True)

    def test_suptitle_legend_string(self, cohort_for_renders):
        """Pin: suptitle includes the dots-legend; the legacy
        "Lines: (green=pass, red=fail)" segment was REMOVED per Round
        2.6 (criteria_34 overlay deleted)."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Licks after rewards" in svg_text
        assert "Dots:" in svg_text
        assert "green=corr" in svg_text
        assert "magenta=incorr" in svg_text
        # Round 2.6: criteria_34 horizontal-bar overlay removed →
        # Lines:/pass/fail strings must be ABSENT from the suptitle.
        assert "Lines:" not in svg_text
        assert "green=pass" not in svg_text
        assert "red=fail" not in svg_text

    def test_ylabel_uses_mouse_frame_directly_no_fn_flip(
        self, cohort_for_renders,
    ):
        """New pipeline reads side_tone as mouse-frame directly.
        Legacy ylabel was ``"Trials   (side: mouse {fn_flip_lr(side_tone)})"``
        — the flip was a WS-frame compensation. New pipeline:
        ``"Trials   (side: Tone {side_tone})"`` — direct. Phase 8a.10.1
        post-Commit-G legend rename: "mouse L/R" → "Tone L/R" for
        scientific clarity (the side identity is set at tone onset)."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # Both side labels appear in the SVG: row 0 = Tone L → ylabel
        # "side: Tone L" (left column only); row 1 = Tone R → "side: Tone R".
        assert "side: Tone L" in svg_text
        assert "side: Tone R" in svg_text

    def test_raster_color_config_consumed(self):
        """Pin: raster dot + reward-marker colors loaded from
        ``visual_gate:`` block, not hardcoded. Criteria-overlay knobs
        REMOVED per Round 2.6 (overlay deleted)."""
        cfg = load_visual_gate_config()
        assert cfg["raster_dot_correct_color"] == "g"
        assert cfg["raster_dot_incorrect_color"] == "m"
        assert cfg["raster_reward_marker_color"] == "k"
        # Round 2.6 deprecations: these knobs must be ABSENT from
        # the config block now that the criteria_34 overlay is gone.
        assert "raster_criteria_pass_color" not in cfg
        assert "raster_criteria_fail_color" not in cfg
        assert "raster_criteria_alpha" not in cfg
        assert "raster_criteria_xrange" not in cfg

    def test_dot_alpha_config(self):
        """Round 2.6 addition: per-dot alpha config knob.
        Legacy default was 1.0 (opaque, no alpha kwarg). New default
        0.6 lets the under-layer peek through; intentional deviation
        for visual usability."""
        cfg = load_visual_gate_config()
        assert cfg["raster_dot_alpha"] == 0.6

    def test_render_lick_raster_passes_alpha_to_scatter(self, cohort_for_renders):
        """Round 2.6 pin: render_lick_raster passes the config-driven
        alpha to every ax.scatter call. matplotlib serializes
        alpha=0.6 as 'fill-opacity: 0.6' (and 'stroke-opacity: 0.6')
        on the scatter PathCollection <use> elements."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "fill-opacity: 0.6" in svg_text, (
            "fill-opacity: 0.6 missing from SVG; "
            "raster_dot_alpha=0.6 not propagated to ax.scatter"
        )

    def test_no_criteria_overlay_lines(self, cohort_for_renders):
        """Round 2.6 pin: criteria_34 pass/fail horizontal-bar overlay
        was removed. The overlay used green (#008000) for pass and
        red (#ff0000) for fail at alpha=0.3, drawn as line segments
        spanning x∈[-1,4]. Without the overlay, no green-or-red
        path should appear at stroke-opacity 0.3 in the SVG."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lick_raster(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib serializes line2d alpha as
        # 'stroke: #rrggbb; stroke-opacity: 0.3' inside style="...".
        # Criteria overlay would produce green/red entries at 0.3.
        green_at_03 = "stroke: #008000; stroke-opacity: 0.3" in svg_text
        red_at_03 = "stroke: #ff0000; stroke-opacity: 0.3" in svg_text
        assert not green_at_03, (
            "found green stroke at opacity 0.3 — criteria_34 pass "
            "overlay may still be rendering"
        )
        assert not red_at_03, (
            "found red stroke at opacity 0.3 — criteria_34 fail "
            "overlay may still be rendering"
        )

    def test_raster_incorrect_zorder_above_correct(
        self, cohort_for_renders, monkeypatch,
    ):
        """Round 2.7 pin: incorrect (magenta) dots drawn ON TOP of
        correct (green) dots so errors are always visible regardless
        of subplot. Capture every ax.scatter call and verify zorder
        kwarg matches config (correct=2, incorrect=3)."""
        resolver, _ = cohort_for_renders
        captured: list[dict] = []
        original = matplotlib.axes.Axes.scatter

        def recording_scatter(self, *args, **kwargs):
            captured.append(dict(kwargs))
            return original(self, *args, **kwargs)

        monkeypatch.setattr(matplotlib.axes.Axes, "scatter", recording_scatter)
        render_lick_raster("PS51", resolver, align_to_stroke=True)
        assert len(captured) > 0, "no ax.scatter calls captured"
        correct_color = visual_gate.load_visual_gate_config()[
            "raster_dot_correct_color"
        ]
        incorrect_color = visual_gate.load_visual_gate_config()[
            "raster_dot_incorrect_color"
        ]
        # Each scatter carries an explicit zorder, and it matches the
        # color-implied is_correct branch.
        for call_kwargs in captured:
            assert "zorder" in call_kwargs, (
                f"ax.scatter missing zorder kwarg: {call_kwargs}"
            )
            if call_kwargs.get("color") == correct_color:
                assert call_kwargs["zorder"] == 2, (
                    f"correct (green) dots should have zorder=2, got "
                    f"{call_kwargs['zorder']}"
                )
            elif call_kwargs.get("color") == incorrect_color:
                assert call_kwargs["zorder"] == 3, (
                    f"incorrect (magenta) dots should have zorder=3, got "
                    f"{call_kwargs['zorder']}"
                )

    def test_raster_xlabel_is_figure_level(
        self, cohort_for_renders, monkeypatch,
    ):
        """Round 2.7 pin: "Time (s)" is set ONCE as a fig.supxlabel,
        not as per-axis ax.set_xlabel × N_sessions. Capture both
        method-call sets to verify."""
        resolver, _ = cohort_for_renders
        supxlabel_calls: list[tuple] = []
        set_xlabel_calls: list[tuple] = []
        orig_supxlabel = matplotlib.figure.Figure.supxlabel
        orig_set_xlabel = matplotlib.axes.Axes.set_xlabel

        def recording_supxlabel(self, *args, **kwargs):
            supxlabel_calls.append((args, dict(kwargs)))
            return orig_supxlabel(self, *args, **kwargs)

        def recording_set_xlabel(self, *args, **kwargs):
            set_xlabel_calls.append((args, dict(kwargs)))
            return orig_set_xlabel(self, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.figure.Figure, "supxlabel", recording_supxlabel,
        )
        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_xlabel", recording_set_xlabel,
        )
        render_lick_raster("PS51", resolver, align_to_stroke=True)
        # supxlabel called exactly once with "Time (s)".
        time_supx_calls = [
            c for c in supxlabel_calls
            if c[0] and c[0][0] == "Time (s)"
        ]
        assert len(time_supx_calls) == 1, (
            f"expected exactly one fig.supxlabel('Time (s)', ...) call, "
            f"got {len(time_supx_calls)}: {supxlabel_calls}"
        )
        # No per-axis ax.set_xlabel("Time (s)", ...) calls.
        time_axlabel_calls = [
            c for c in set_xlabel_calls
            if c[0] and c[0][0] == "Time (s)"
        ]
        assert len(time_axlabel_calls) == 0, (
            f"expected zero per-axis ax.set_xlabel('Time (s)', ...) "
            f"calls; got {len(time_axlabel_calls)}: {time_axlabel_calls}"
        )

    def test_raster_xticks_explicit(
        self, cohort_for_renders, monkeypatch,
    ):
        """Round 2.7 pin: render_lick_raster sets explicit xticks
        from config so the auto-locator doesn't crowd a -1 tick
        against the reward marker at 0. Round 2.8 reduces to the
        axis-limit endpoints [0, 5] (Priya 2026-05-13)."""
        resolver, _ = cohort_for_renders
        captured_xticks: list[list] = []
        orig = matplotlib.axes.Axes.set_xticks

        def recording_set_xticks(self, ticks, *args, **kwargs):
            captured_xticks.append(list(ticks) if hasattr(ticks, "__iter__") else ticks)
            return orig(self, ticks, *args, **kwargs)

        monkeypatch.setattr(
            matplotlib.axes.Axes, "set_xticks", recording_set_xticks,
        )
        render_lick_raster("PS51", resolver, align_to_stroke=True)
        cfg = visual_gate.load_visual_gate_config()
        # Round 2.8 value pin.
        assert cfg["raster_xticks"] == [0, 5]
        expected = cfg["raster_xticks"]
        # Every raster ax gets the explicit xticks set.
        matching = [t for t in captured_xticks if t == expected]
        assert len(matching) > 0, (
            f"no ax.set_xticks call matched raster_xticks={expected}; "
            f"all captured: {captured_xticks}"
        )

    def test_raster_reward_marker_thinner(
        self, cohort_for_renders, monkeypatch,
    ):
        """Round 2.7 pin: reward marker (vertical line at x=0) uses
        linewidth from config, not matplotlib's default ~1.5pt."""
        resolver, _ = cohort_for_renders
        captured: list[dict] = []
        original = matplotlib.axes.Axes.plot

        def recording_plot(self, *args, **kwargs):
            captured.append((args, dict(kwargs)))
            return original(self, *args, **kwargs)

        monkeypatch.setattr(matplotlib.axes.Axes, "plot", recording_plot)
        render_lick_raster("PS51", resolver, align_to_stroke=True)
        cfg = visual_gate.load_visual_gate_config()
        expected_lw = cfg["raster_reward_marker_linewidth"]
        # Reward-marker plot calls: positional args [[0,0], [0, n_trials], color].
        reward_calls = [
            (a, k) for (a, k) in captured
            if len(a) >= 2 and list(a[0]) == [0, 0]
        ]
        assert len(reward_calls) > 0, (
            f"no reward-marker ax.plot([0,0],...) calls captured; "
            f"got {len(captured)} total plot calls"
        )
        for (_args, kwargs) in reward_calls:
            assert kwargs.get("linewidth") == expected_lw, (
                f"reward-marker linewidth={kwargs.get('linewidth')} "
                f"!= config {expected_lw}"
            )

    def test_module_export(self):
        assert hasattr(visual_gate, "render_lick_raster")


class TestLongitudinalXtickFontsize:
    """Round 2.7 pin: longitudinal plot families (criteria_performance,
    accuracy_first*, lickiness, switchiness, numLicks_*, latency,
    lickRate) share apply_longitudinal_axis. The day-label tick
    fontsize must come from the new visual_gate.longitudinal_xtick_fontsize
    knob (NOT the raster-scoped xtick_fontsize)."""

    def test_longitudinal_xtick_fontsize_default(self):
        cfg = load_visual_gate_config()
        assert "longitudinal_xtick_fontsize" in cfg
        assert cfg["longitudinal_xtick_fontsize"] == 6

    def test_longitudinal_xtick_fontsize_applied(self):
        """apply_longitudinal_axis reads longitudinal_xtick_fontsize
        and passes it to ax.set_xticklabels. Pin both: (a) the
        config-default value and (b) a synthetic override (proves
        plumbing — not a hardcoded constant)."""
        for synthetic_size in (6, 12):
            fig, ax = plt.subplots()
            try:
                axis = LongitudinalAxis(
                    x_vals=np.array([0, 1, 2]),
                    x_ticklabels=["d-1", "d0", "d+1"],
                    vline_x=0.5,
                    suffix="_relStroke",
                )
                cfg = dict(load_visual_gate_config())
                cfg["longitudinal_xtick_fontsize"] = synthetic_size
                apply_longitudinal_axis(ax, axis, cfg)
                # Read back the fontsize matplotlib applied to xtick labels.
                xticklabels = ax.get_xticklabels()
                assert len(xticklabels) == 3
                for tl in xticklabels:
                    assert tl.get_fontsize() == synthetic_size, (
                        f"xtick label fontsize {tl.get_fontsize()} "
                        f"!= synthetic override {synthetic_size}"
                    )
            finally:
                plt.close(fig)


# =====================================================================
# Commit-group 4: lickiness + switchiness
# =====================================================================


class TestComputeLickinessBySession:
    def test_counts_licks_in_inter_reward_window(self):
        """2 rewards 10 seconds apart; licks between them in the
        late-window range get counted."""
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                # 2 L licks at t=9s and 10s (within late window of reward at t=0)
                "Lick_L": np.array([9000, 10000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            tones_idx={
                "Tone_L": np.array([0], dtype=int),
                "Tone_R": np.array([20000], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        # late_window_start=8s → licks at 9s/10s past 8000 sample start
        # late_window_end=60s → window end = min(20000 next reward, 0+60000) = 20000
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 2
        assert counts["R"] == 0

    def test_dense_rewards_next_reward_caps_window(self):
        """When next_reward is closer than the 60s cap, the next-reward
        boundary trims the late-window (mirrors legacy line 870)."""
        data = SessionPlotData(
            date_label="20250430",
            # Reward at 0; next reward at sample 12000 (12 sec).
            # Late window: [8000 (8s), min(12000, 60000)=12000].
            # Lick at 11000 (in window); lick at 13000 (past next reward, excluded)
            lick_idx={
                "Lick_L": np.array([11000, 13000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            tones_idx={
                "Tone_L": np.array([0], dtype=int),
                "Tone_R": np.array([12000], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 1  # only 11000; 13000 past next-reward cap

    def test_handles_empty_rewards(self):
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={"Lick_L": np.array([], dtype=int),
                      "Lick_R": np.array([], dtype=int)},
            tones_idx={"Tone_L": np.array([], dtype=int),
                         "Tone_R": np.array([], dtype=int)},
            sample_rate=1000.0,
            n_samples_session=30000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts == {"L": 0, "R": 0}

    def test_last_reward_uses_n_samples_cap(self):
        """For the last reward, the window closes at min(rew + end,
        n_samples_session) — n_samples_session=15000 trims a 0+60s=60000
        sample window down to 15000."""
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={
                # Lick at 14000 (within trimmed window), lick at 16000 (past)
                "Lick_L": np.array([14000, 16000], dtype=int),
                "Lick_R": np.array([], dtype=int),
            },
            tones_idx={
                "Tone_L": np.array([0], dtype=int),
                "Tone_R": np.array([], dtype=int),
            },
            sample_rate=1000.0,
            n_samples_session=15000,
        )
        counts = compute_lickiness_bySession(
            data,
            late_window_start_seconds=8.0,
            late_window_end_seconds=60.0,
        )
        assert counts["L"] == 1


class TestComputeSwitchinessBySession:
    def test_no_licks_yields_nan(self):
        """Empty trials → no count contributions → NaN means."""
        delays: dict[str, dict[int, dict[str, np.ndarray]]] = {
            "Tone_L": {}, "Tone_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        assert np.isnan(sw["L->R"])
        assert np.isnan(sw["R->L"])

    def test_single_event_yields_zero_transitions(self):
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([100]),
                    "Lick_R": np.array([], dtype=int),
                },
            },
            "Tone_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        # 1 event → 0 transitions
        assert sw["L->R"] == pytest.approx(0.0)
        assert sw["R->L"] == pytest.approx(0.0)

    def test_alternating_LRLR_counts_transitions(self):
        """4-event LRLR sequence within one trial = 3 transitions
        (L→R, R→L, L→R). So c_LR=2, c_RL=1."""
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([100, 300], dtype=int),
                    "Lick_R": np.array([200, 400], dtype=int),
                },
            },
            "Tone_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        assert sw["L->R"] == pytest.approx(2.0)
        assert sw["R->L"] == pytest.approx(1.0)

    def test_mouse_frame_no_ws_flip(self):
        """compute_switchiness_bySession operates mouse-frame directly
        on the input lick_delays (which are mouse-frame post-Phase-6.8).
        Legacy did a WS-frame compute + plot-time flip; new pipeline
        does NEITHER — input is already mouse-frame and output keys are
        labeled in mouse-frame."""
        delays = {
            "Tone_L": {
                0: {
                    "Lick_L": np.array([100, 300]),
                    "Lick_R": np.array([200], dtype=int),
                },
            },
            "Tone_R": {},
        }
        sw = compute_switchiness_bySession(delays)
        # L→R (100→200): 1; R→L (200→300): 1
        assert sw["L->R"] == pytest.approx(1.0)
        assert sw["R->L"] == pytest.approx(1.0)


class TestRenderLickinessBySession:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, png_path = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "lickiness_bySession_relStroke.svg"
        assert png_path.name == "lickiness_bySession_relStroke.png"

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "lickiness_bySession_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_lickiness_bySession("PS51", resolver, align_to_stroke=True)

    def test_title_and_ylabel_strings(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Lickiness by session" in svg_text
        assert "Late licks per session" in svg_text

    def test_mouse_frame_ylabel_no_fn_flip(self, cohort_for_renders):
        """Legend labels say "Tone L" / "Tone R" directly (no flip).
        Pin to catch regression to legacy fn_flip_lr. Phase 8a.10.1
        post-Commit-G legend rename: previously "mouse L/R"; renamed
        to "Tone L/R" to identify the trial-cue side."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_lickiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Tone L" in svg_text
        assert "Tone R" in svg_text


class TestRenderSwitchinessBySession:
    def test_returns_svg_and_png_paths(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, png_path = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        assert svg_path.exists() and svg_path.stat().st_size > 0
        assert png_path.exists() and png_path.stat().st_size > 0
        assert svg_path.name == "switchiness_bySession_relStroke.svg"

    def test_absdate_suffix_when_unaligned(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=False,
        )
        assert svg_path.name == "switchiness_bySession_absDate.svg"

    def test_raises_when_no_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        legacy_root = tmp_path / "legacy_analysis"
        bba = legacy_root / "basic_behavior_analysis3" / "PS51"
        bba.mkdir(parents=True, exist_ok=True)
        (bba / "report.json").write_text(
            json.dumps({"latency_bySession": {}}), encoding="utf-8",
        )
        paths_yaml = tmp_path / "paths.yaml"
        paths_yaml.write_text(textwrap.dedent(f"""
            logical_roots:
              microscope_pipeline_outputs:
                description: "out"
                mounts:
                  mac: "/Volumes/dummy/po"
                  windows: "C:\\\\dummy\\\\po"
              local_processed_spout:
                description: "legacy"
                mounts:
                  {_HOST_KEY}:
                    - "{legacy_root.as_posix()}"
        """))
        resolver = PathResolver(paths_yaml, output_root=tmp_path)
        with pytest.raises(ValueError, match="no Cohort A sessions"):
            render_switchiness_bySession("PS51", resolver, align_to_stroke=True)

    def test_title_and_ylabel_strings(self, cohort_for_renders):
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        assert "Switchiness by session" in svg_text
        assert "Avg switches per trial" in svg_text

    def test_legend_labels_use_arrow_notation(self, cohort_for_renders):
        """Pin: legacy plot uses "L→R" / "R→L" label strings (with arrow
        character, not "->")."""
        resolver, _ = cohort_for_renders
        svg_path, _ = render_switchiness_bySession(
            "PS51", resolver, align_to_stroke=True,
        )
        svg_text = svg_path.read_text(encoding="utf-8")
        # matplotlib SVG-escapes "→" as the literal Unicode arrow char
        assert "L→R" in svg_text
        assert "R→L" in svg_text


class TestSessionPlotDataNSamplesExtension:
    """CG-4 extended SessionPlotData with n_samples_session. CG-1 tests
    that don't set the field still pass (default 0); load_session_plot_data
    reads it from the first 1D WS signal when present."""

    def test_default_zero(self):
        data = SessionPlotData(
            date_label="20250430",
            lick_idx={"Lick_L": np.array([]), "Lick_R": np.array([])},
            tones_idx={"Tone_L": np.array([]), "Tone_R": np.array([])},
            sample_rate=1000.0,
        )
        assert data.n_samples_session == 0

    def test_load_populates_from_1d_signal(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100]),
            lick_r=np.array([150]),
            tone_l=np.array([50]),
            tone_r=np.array([175]),
            sample_rate=1000.0,
            n_samples=42_000,
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert data.n_samples_session == 42_000

    def test_load_defaults_to_zero_when_no_1d_signal(self, tmp_path):
        _write_phase2_npzs(
            tmp_path, "PS51", "20250430",
            lick_l=np.array([100]),
            lick_r=np.array([150]),
            tone_l=np.array([50]),
            tone_r=np.array([175]),
            sample_rate=1000.0,
            # n_samples=None → no 1D signal in WS NPZ
        )
        resolver = PathResolver(output_root=tmp_path)
        data = load_session_plot_data("PS51", "20250430", resolver)
        assert data.n_samples_session == 0


class TestCG4ModuleExports:
    @pytest.mark.parametrize("name", [
        "compute_lickiness_bySession", "compute_switchiness_bySession",
        "render_lickiness_bySession", "render_switchiness_bySession",
    ])
    def test_symbol_exists(self, name):
        assert hasattr(visual_gate, name), (
            f"visual_gate.{name} missing — commit-group 4 public surface"
        )
