"""Tests for stroke_orofacial.animals."""

from __future__ import annotations

import datetime
import textwrap
from pathlib import Path

import pytest

from stroke_orofacial.animals import (
    AnimalInfo,
    Exclusion,
    load_animals,
    get_animal,
    EpochBoundaries,
)


@pytest.fixture()
def animals_yaml(tmp_path: Path) -> Path:
    """Write a test animals.yaml and return its path."""
    cfg = tmp_path / "animals.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            PS46:
              stroke_date: 2025-03-13
              sessions:
                start: 2025-03-07
                end: 2025-04-06
              exclusions: []
              recovery_phenotype: null
              epoch_boundaries:
                acute_max_rel_day: 5
                subacute_max_rel_day: 8
                chronic_min_rel_day: 9
              sex: F
              date_of_birth: 2024-12-03
              genotype: "C57BL/6J"
              stroke_laser_power_mW: 2.2
              bin_days: 2
              analysis_params:
                break_thr_trialmax: 12000.0
                break_thr_alllicks: 9000.0
              kinematics_baselines:
                tongue:
                  x0: 0.0
                  y0: -110.0
                jaw:
                  x0: 0.0
                  y0: 310.0

            PS54:
              stroke_date: 2025-04-30
              sessions:
                start: 2025-04-16
                end: 2025-07-09
              exclusions:
                - date: 2025-04-26
                  reason: "excluded in tongue-kinematics analysis"
                  applies_to: [dlc.kinematics.tongue]
              recovery_phenotype: null
              epoch_boundaries:
                acute_max_rel_day: 17
                subacute_max_rel_day: 39
                chronic_min_rel_day: 40
              kinematics_baselines:
                tongue:
                  x0: 0.0
                  y0: -110.0
                jaw:
                  x0: 12.0
                  y0: 290.0

            PS_PLACEHOLDER:
              stroke_date: null
              sessions:
                start: null
                end: null
              exclusions: []
              recovery_phenotype: null
        """)
    )
    return cfg


class TestLoadAnimals:
    def test_loads_two_animals(self, animals_yaml):
        animals = load_animals(animals_yaml)
        assert set(animals.keys()) == {"PS46", "PS54"}

    def test_skips_null_stroke_date(self, animals_yaml):
        animals = load_animals(animals_yaml)
        assert "PS_PLACEHOLDER" not in animals

    def test_ps46_fields(self, animals_yaml):
        animals = load_animals(animals_yaml)
        ps46 = animals["PS46"]
        assert ps46.stroke_date == datetime.date(2025, 3, 13)
        assert ps46.session_start == datetime.date(2025, 3, 7)
        assert ps46.session_end == datetime.date(2025, 4, 6)
        assert ps46.exclusions == []
        assert ps46.analysis_params["break_thr_trialmax"] == 12000.0

    def test_ps54_exclusion(self, animals_yaml):
        animals = load_animals(animals_yaml)
        ps54 = animals["PS54"]
        assert len(ps54.exclusions) == 1
        exc = ps54.exclusions[0]
        assert exc.date == datetime.date(2025, 4, 26)
        assert exc.applies_to == ["dlc.kinematics.tongue"]

    def test_ps46_cohort_metadata(self, animals_yaml):
        """PS46 has all 4 cohort metadata fields populated in the fixture."""
        animals = load_animals(animals_yaml)
        ps46 = animals["PS46"]
        assert ps46.sex == "F"
        assert ps46.date_of_birth == datetime.date(2024, 12, 3)
        assert ps46.genotype == "C57BL/6J"
        assert ps46.stroke_laser_power_mW == 2.2

    def test_ps54_cohort_metadata_missing_defaults_to_none(self, animals_yaml):
        """Animals without cohort metadata in yaml should load with None
        defaults — this keeps old yaml files loadable without migration."""
        animals = load_animals(animals_yaml)
        ps54 = animals["PS54"]
        assert ps54.sex is None
        assert ps54.date_of_birth is None
        assert ps54.genotype is None
        assert ps54.stroke_laser_power_mW is None

    def test_invalid_sex_raises(self, tmp_path):
        """sex must be 'M', 'F', or unset — anything else should fail fast."""
        cfg = tmp_path / "bad_sex.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  sex: "unknown"
            """)
        )
        with pytest.raises(ValueError, match="sex must be"):
            load_animals(cfg)


class TestGetAnimal:
    def test_found(self, animals_yaml):
        info = get_animal("PS46", animals_yaml)
        assert info.animal_id == "PS46"

    def test_not_found(self, animals_yaml):
        with pytest.raises(KeyError, match="PS99"):
            get_animal("PS99", animals_yaml)


class TestAnimalInfoMethods:
    def test_day_relative_to_stroke(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.day_relative_to_stroke(datetime.date(2025, 3, 7)) == -6
        assert info.day_relative_to_stroke(datetime.date(2025, 3, 13)) == 0
        assert info.day_relative_to_stroke(datetime.date(2025, 3, 20)) == 7

    def test_phase_before_stroke(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.phase(datetime.date(2025, 3, 7)) == "baseline"

    def test_phase_on_stroke_date_is_baseline(self):
        """stroke_date is the last pre-stroke session; the stroke happens
        after that day's session, so the session itself is baseline."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.phase(datetime.date(2025, 3, 13)) == "baseline"

    def test_phase_after_stroke(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.phase(datetime.date(2025, 3, 14)) == "post_stroke"
        assert info.phase(datetime.date(2025, 3, 20)) == "post_stroke"

    def test_is_excluded_top_level_scope(self):
        """An exclusion scoped to [dlc, spout_behavior] fires for any
        analysis_context under either namespace — the Phase 7-pre
        replacement for the legacy ["all"] sentinel semantics."""
        info = AnimalInfo(
            animal_id="T",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 1),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 1, 5),
                    "bad session",
                    ["dlc", "spout_behavior"],
                ),
            ],
        )
        # dlc.kinematics.tongue is under dlc namespace
        excluded, reason = info.is_excluded(
            datetime.date(2025, 1, 5), "dlc.kinematics.tongue"
        )
        assert excluded is True
        assert reason == "bad session"
        # spout_behavior is top-level
        excluded, reason = info.is_excluded(
            datetime.date(2025, 1, 5), "spout_behavior"
        )
        assert excluded is True
        # alignment is NOT in the scope (neither dlc nor spout_behavior prefix)
        excluded, _ = info.is_excluded(datetime.date(2025, 1, 5), "alignment")
        assert excluded is False

    def test_is_excluded_bodypart_specific(self):
        """Bodypart-scoped exclusion with dotted tag — prefix-match
        distinguishes sibling bodyparts under the same phase prefix."""
        info = AnimalInfo(
            animal_id="T",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 1),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 1, 5),
                    "tongue issue",
                    ["dlc.kinematics.tongue"],
                ),
            ],
        )
        excluded, _ = info.is_excluded(
            datetime.date(2025, 1, 5), "dlc.kinematics.tongue"
        )
        assert excluded is True
        excluded, _ = info.is_excluded(
            datetime.date(2025, 1, 5), "dlc.kinematics.jaw"
        )
        assert excluded is False
        # None context — no match (callers must pass an explicit context)
        excluded, _ = info.is_excluded(datetime.date(2025, 1, 5))
        assert excluded is False


class TestAgeHelpers:
    def test_age_at_date_returns_days(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            date_of_birth=datetime.date(2024, 12, 3),
        )
        # 2024-12-03 → 2025-03-07 is exactly 94 days.
        assert info.age_at_date(datetime.date(2025, 3, 7)) == 94

    def test_age_at_stroke(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            date_of_birth=datetime.date(2024, 12, 3),
        )
        # 2024-12-03 → 2025-03-13 = 100 days.
        assert info.age_at_stroke() == 100

    def test_age_at_date_none_when_dob_missing(self):
        """Callers should treat None as a missing covariate — never
        substitute a default age value."""
        info = AnimalInfo(
            animal_id="PS54",
            stroke_date=datetime.date(2025, 4, 30),
            session_start=datetime.date(2025, 4, 16),
            session_end=datetime.date(2025, 7, 9),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.age_at_date(datetime.date(2025, 5, 1)) is None
        assert info.age_at_stroke() is None


class TestExclusionApplies:
    """Phase 7-pre prefix-match semantics on dotted analysis-context tags."""

    def test_exact_match(self):
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["spout_behavior"])
        assert exc.applies("spout_behavior") is True

    def test_prefix_match_one_level(self):
        """[dlc] matches any dlc.* context."""
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["dlc"])
        assert exc.applies("dlc.spatial") is True
        assert exc.applies("dlc.kinematics.tongue") is True
        assert exc.applies("dlc.io") is True

    def test_prefix_match_multi_level(self):
        """[dlc.kinematics] matches dlc.kinematics.* but not dlc.spatial."""
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["dlc.kinematics"])
        assert exc.applies("dlc.kinematics") is True
        assert exc.applies("dlc.kinematics.tongue") is True
        assert exc.applies("dlc.kinematics.face_velocity") is True
        assert exc.applies("dlc.spatial") is False
        assert exc.applies("dlc") is False  # tag is longer than context

    def test_sibling_no_match(self):
        """[dlc.kinematics.tongue] must not match [dlc.kinematics.jaw]."""
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["dlc.kinematics.tongue"])
        assert exc.applies("dlc.kinematics.tongue") is True
        assert exc.applies("dlc.kinematics.jaw") is False

    def test_segment_boundary_strict(self):
        """[dlc] matches dlc and dlc.* but NOT dlc_spatial or dlcx.

        Prefix-match is on dot-separated segments, not raw string prefix.
        """
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["dlc"])
        assert exc.applies("dlc") is True
        assert exc.applies("dlc.spatial") is True
        assert exc.applies("dlc_spatial") is False  # underscore, not dot
        assert exc.applies("dlcx") is False  # no boundary

    def test_none_context_never_matches(self):
        """Passing analysis_context=None always returns False — the
        schema requires an explicit context to match anything."""
        exc = Exclusion(datetime.date(2025, 1, 1), "r", ["dlc", "spout_behavior"])
        assert exc.applies(None) is False

    def test_multiple_tags_any_match(self):
        """A context matches if ANY tag in applies_to is a prefix."""
        exc = Exclusion(
            datetime.date(2025, 1, 1), "r",
            ["dlc.kinematics.tongue", "spout_behavior"],
        )
        assert exc.applies("dlc.kinematics.tongue") is True
        assert exc.applies("spout_behavior") is True
        assert exc.applies("dlc.kinematics.jaw") is False
        assert exc.applies("alignment") is False


class TestExclusionLoaderValidation:
    """The post-Phase-7-pre loader rejects the legacy [all] sentinel and
    enforces explicit applies_to scoping."""

    def test_all_sentinel_rejected(self, tmp_path):
        cfg = tmp_path / "legacy_all.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions:
                    - date: 2025-01-01
                      reason: "test"
                      applies_to: [all]
            """)
        )
        with pytest.raises(ValueError, match="'all' sentinel is deprecated"):
            load_animals(cfg)

    def test_missing_applies_to_rejected(self, tmp_path):
        cfg = tmp_path / "no_applies_to.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions:
                    - date: 2025-01-01
                      reason: "test"
            """)
        )
        with pytest.raises(ValueError, match="'applies_to' is required"):
            load_animals(cfg)

    def test_empty_applies_to_rejected(self, tmp_path):
        cfg = tmp_path / "empty_applies_to.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions:
                    - date: 2025-01-01
                      reason: "test"
                      applies_to: []
            """)
        )
        with pytest.raises(ValueError, match="must not be empty"):
            load_animals(cfg)

    def test_non_list_applies_to_rejected(self, tmp_path):
        """applies_to: 42 (non-string-non-list) must fail fast."""
        cfg = tmp_path / "bad_applies_to.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions:
                    - date: 2025-01-01
                      reason: "test"
                      applies_to: 42
            """)
        )
        with pytest.raises(ValueError, match="must be a list of strings"):
            load_animals(cfg)

    def test_string_applies_to_is_normalized(self, tmp_path):
        """applies_to: 'dlc' (scalar string) loads as ['dlc']. Common
        YAML typo — accept without forcing the user to type brackets."""
        cfg = tmp_path / "string_applies_to.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions:
                    - date: 2025-01-01
                      reason: "test"
                      applies_to: "dlc"
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        animals = load_animals(cfg)
        assert animals["PS99"].exclusions[0].applies_to == ["dlc"]


class TestWavesurferSidesMatchMouseSides:
    """Per task #17: controls whether the wavesurfer Lick_L/Reward_L
    channels correspond directly to the mouse's L side (true) or are
    mirrored (false). Default is False — fail-conservative for the
    current PS46–PS55 cohort acquired on the mirrored rig."""

    def test_default_false_when_key_absent(self, animals_yaml):
        """Absent key → False (fail-conservative). The fixture's PS46
        has no wavesurfer_sides_match_mouse_sides entry, so it must
        default to False, matching the current cohort's rig orientation."""
        animals = load_animals(animals_yaml)
        assert animals["PS46"].wavesurfer_sides_match_mouse_sides is False
        assert animals["PS54"].wavesurfer_sides_match_mouse_sides is False

    def test_explicit_false_loads_as_false(self, tmp_path):
        cfg = tmp_path / "explicit_false.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  wavesurfer_sides_match_mouse_sides: false
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        animals = load_animals(cfg)
        assert animals["PS99"].wavesurfer_sides_match_mouse_sides is False

    def test_explicit_true_loads_as_true(self, tmp_path):
        """When a future cohort is acquired on a matched-orientation
        rig, the yaml flag flips and the output-boundary translation
        becomes a no-op."""
        cfg = tmp_path / "explicit_true.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  wavesurfer_sides_match_mouse_sides: true
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        animals = load_animals(cfg)
        assert animals["PS99"].wavesurfer_sides_match_mouse_sides is True

    def test_invalid_type_raises(self, tmp_path):
        """Non-bool values (e.g. the string "false", or an int) must
        fail fast — YAML parses actual booleans as bools, so a string
        almost certainly means the author typo'd the value."""
        cfg = tmp_path / "invalid_type.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  wavesurfer_sides_match_mouse_sides: "false"
            """)
        )
        with pytest.raises(
            ValueError, match="wavesurfer_sides_match_mouse_sides"
        ):
            load_animals(cfg)


class TestStrokeLaterality:
    """Task 3 Round 2.8 (added 2026-05-13): per-animal mouse-frame
    hemisphere of the stroke. Scaffolding for the future pub-figures
    phase via :meth:`AnimalInfo.mouse_side_to_ipsi_contra`. Default
    "L" matches all 8 current cohort animals."""

    def test_animal_info_stroke_laterality_default_L(self):
        """Direct AnimalInfo(...) construction without stroke_laterality
        defaults to "L"."""
        info = AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 2),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        assert info.stroke_laterality == "L"

    def test_animal_info_stroke_laterality_explicit_R(self):
        """Explicit stroke_laterality="R" is preserved through
        construction (forward-compat for future R-hemisphere strokes)."""
        info = AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 2),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            stroke_laterality="R",
        )
        assert info.stroke_laterality == "R"

    def test_animal_info_invalid_stroke_laterality_raises(self, tmp_path):
        """Loader rejects values outside {'L', 'R'} at load time."""
        cfg = tmp_path / "invalid_laterality.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  stroke_laterality: X
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        with pytest.raises(ValueError, match="stroke_laterality"):
            load_animals(cfg)

    def test_mouse_side_to_ipsi_contra_default_animal(self):
        """L-hemisphere stroke (current cohort default): mouse-L is
        ipsi, mouse-R is contra."""
        info = AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 2),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            stroke_laterality="L",
        )
        assert info.mouse_side_to_ipsi_contra("L") == "ipsi"
        assert info.mouse_side_to_ipsi_contra("R") == "contra"

    def test_mouse_side_to_ipsi_contra_right_stroke(self):
        """R-hemisphere stroke: ipsi/contra mapping is inverted."""
        info = AnimalInfo(
            animal_id="PS99",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 2),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            stroke_laterality="R",
        )
        assert info.mouse_side_to_ipsi_contra("L") == "contra"
        assert info.mouse_side_to_ipsi_contra("R") == "ipsi"

    def test_load_animals_yaml_includes_stroke_laterality(self):
        """The real configs/animals.yaml at repo root has
        stroke_laterality populated as "L" for every active animal
        (placeholder entries with null stroke_date are skipped by
        the loader)."""
        animals = load_animals()
        assert len(animals) == 8, (
            f"expected 8 active animals in configs/animals.yaml; "
            f"got {len(animals)}: {sorted(animals)}"
        )
        for animal_id, info in animals.items():
            assert info.stroke_laterality == "L", (
                f"animal {animal_id} has stroke_laterality="
                f"{info.stroke_laterality!r}, expected 'L'"
            )


class TestKinematicsBaselines:
    """Phase 7a.1 (added 2026-04-22): per-animal per-bodypart (x0, y0)
    baselines are required at load time for every animal, consumed by
    the Phase 7a interpolation module via
    :meth:`AnimalInfo.get_kinematics_baseline`. Seed values in
    configs/animals.yaml come from the PR #79 baseline-seed probe,
    scope-filtered re-analysis section."""

    def test_loaded_for_all_animals(self):
        """Every animal in the real configs/animals.yaml parses with
        both bodyparts present and finite-float x0/y0."""
        animals = load_animals()
        assert len(animals) == 8
        for animal_id, info in animals.items():
            kb = info.kinematics_baselines
            assert set(kb.keys()) == {"tongue", "jaw"}, (
                f"{animal_id} missing a bodypart: {sorted(kb)}"
            )
            for bp in ("tongue", "jaw"):
                for key in ("x0", "y0"):
                    v = kb[bp][key]
                    assert isinstance(v, float)
                    # NaN check — math.isnan would also work; comparing
                    # to itself is equivalent for finiteness.
                    assert v == v, f"{animal_id} {bp}.{key} is NaN"
                    assert abs(v) < 1e6, (
                        f"{animal_id} {bp}.{key} out of plausible range: {v!r}"
                    )

    def test_tongue_uniform_across_cohort(self):
        """All 8 animals carry tongue (x0, y0) = (0.0, -110.0). This is
        the scope-filtered-re-analysis outcome — every in-scope PS46–PS55
        legacy v5p3 NPZ carries Y0 = -110."""
        animals = load_animals()
        for animal_id, info in animals.items():
            tongue = info.get_kinematics_baseline("tongue")
            assert tongue == {"x0": 0.0, "y0": -110.0}, (
                f"{animal_id} tongue baseline drift: {tongue}"
            )

    def test_jaw_per_animal_groups(self):
        """Jaw baselines split into three groups per the seed table:
        PS46–PS50 at (0, 310), PS51/PS54 at (12, 290), PS55 at (0, 290)."""
        animals = load_animals()
        expected_jaw = {
            "PS46": {"x0": 0.0, "y0": 310.0},
            "PS47": {"x0": 0.0, "y0": 310.0},
            "PS48": {"x0": 0.0, "y0": 310.0},
            "PS49": {"x0": 0.0, "y0": 310.0},
            "PS50": {"x0": 0.0, "y0": 310.0},
            "PS51": {"x0": 12.0, "y0": 290.0},
            "PS54": {"x0": 12.0, "y0": 290.0},
            "PS55": {"x0": 0.0, "y0": 290.0},
        }
        for animal_id, expected in expected_jaw.items():
            got = animals[animal_id].get_kinematics_baseline("jaw")
            assert got == expected, f"{animal_id} jaw: {got} != {expected}"

    def test_missing_block_raises(self, tmp_path):
        """An animal without a kinematics_baselines: block fails load
        with a ValueError that names the animal — no silent default."""
        cfg = tmp_path / "no_kinematics.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions: []
            """)
        )
        with pytest.raises(
            ValueError,
            match=r"PS99.*kinematics_baselines block is required",
        ):
            load_animals(cfg)

    def test_missing_bodypart_raises(self, tmp_path):
        """A block with only tongue: (jaw missing) fails — both bodyparts
        are mandatory, so a partial entry cannot silently pass."""
        cfg = tmp_path / "missing_jaw.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions: []
                  kinematics_baselines:
                    tongue:
                      x0: 0.0
                      y0: -110.0
            """)
        )
        with pytest.raises(
            ValueError, match=r"PS99.*missing kinematics_baselines bodypart"
        ):
            load_animals(cfg)

    def test_unknown_bodypart_raises(self, tmp_path):
        """Unknown bodypart keys (typos) fail at load time rather than
        silently parsing into an unused dict entry."""
        cfg = tmp_path / "unknown_bodypart.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions: []
                  kinematics_baselines:
                    tongue:
                      x0: 0.0
                      y0: -110.0
                    jaw:
                      x0: 0.0
                      y0: 310.0
                    whisker:
                      x0: 0.0
                      y0: 0.0
            """)
        )
        with pytest.raises(
            ValueError, match=r"PS99.*unknown kinematics_baselines bodypart"
        ):
            load_animals(cfg)

    def test_missing_x0_raises(self, tmp_path):
        """Partial per-bodypart dicts (e.g. tongue with only y0) fail
        load — every bodypart must carry both x0 and y0."""
        cfg = tmp_path / "missing_x0.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  exclusions: []
                  kinematics_baselines:
                    tongue:
                      y0: -110.0
                    jaw:
                      x0: 0.0
                      y0: 310.0
            """)
        )
        with pytest.raises(ValueError, match=r"PS99.*tongue.*missing.*'x0'"):
            load_animals(cfg)

    def test_get_kinematics_baseline_unknown_bodypart_raises(self):
        """Querying get_kinematics_baseline('whisker') on a configured
        animal raises KeyError with the configured bodyparts listed."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
            kinematics_baselines={
                "tongue": {"x0": 0.0, "y0": -110.0},
                "jaw": {"x0": 0.0, "y0": 310.0},
            },
        )
        with pytest.raises(KeyError, match="whisker"):
            info.get_kinematics_baseline("whisker")
        # Sanity: configured bodyparts return cleanly.
        assert info.get_kinematics_baseline("tongue") == {"x0": 0.0, "y0": -110.0}
        assert info.get_kinematics_baseline("jaw") == {"x0": 0.0, "y0": 310.0}


class TestBinDays:
    """Phase 7a.4 (added 2026-04-30): per-animal day-bin width consumed by
    the Cell 42 day-binned cross-session aggregator. Legacy values:
    PS46-PS50 use 2 days; PS51/PS54/PS55 use 7 days. Default 1 is
    fail-conservative for any future animal joining the cohort."""

    def test_explicit_two_loads(self, animals_yaml):
        """PS46 fixture carries `bin_days: 2` — round-trips as int 2."""
        animals = load_animals(animals_yaml)
        assert animals["PS46"].bin_days == 2
        assert isinstance(animals["PS46"].bin_days, int)

    def test_default_one_when_key_absent(self, animals_yaml):
        """PS54 fixture has no `bin_days` key — defaults to 1."""
        animals = load_animals(animals_yaml)
        assert animals["PS54"].bin_days == 1

    def test_real_yaml_cohort_values(self):
        """Real configs/animals.yaml: PS46-PS50 → 2; PS51/PS54/PS55 → 7."""
        animals = load_animals()
        expected = {
            "PS46": 2, "PS47": 2, "PS48": 2, "PS49": 2, "PS50": 2,
            "PS51": 7, "PS54": 7, "PS55": 7,
        }
        for animal_id, expected_bd in expected.items():
            assert animals[animal_id].bin_days == expected_bd, (
                f"{animal_id} bin_days drift: "
                f"{animals[animal_id].bin_days} != {expected_bd}"
            )

    def test_invalid_bool_raises(self, tmp_path):
        """`bin_days: true` would silently coerce to int 1 (Python's
        bool-is-int) — loader rejects to catch the typo."""
        cfg = tmp_path / "invalid_bool.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  bin_days: true
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        with pytest.raises(ValueError, match="PS99.*bin_days"):
            load_animals(cfg)

    def test_invalid_zero_raises(self, tmp_path):
        """`bin_days: 0` is meaningless (zero-width bins) — rejected."""
        cfg = tmp_path / "invalid_zero.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  epoch_boundaries:
                    acute_max_rel_day: 1
                    subacute_max_rel_day: 4
                    chronic_min_rel_day: 5
                  bin_days: 0
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        with pytest.raises(ValueError, match="PS99.*bin_days"):
            load_animals(cfg)


# ===========================================================================
# Phase 9 Task 1.5 — EpochBoundaries + recovery_phenotype enum
# ===========================================================================


def _bare_yaml_block(
    *,
    animal_id: str = "PS99",
    epoch_lines: str = (
        "  epoch_boundaries:\n"
        "    acute_max_rel_day: 1\n"
        "    subacute_max_rel_day: 4\n"
        "    chronic_min_rel_day: 5\n"
    ),
    extra_lines: str = "",
) -> str:
    """Render a minimal-but-valid one-animal YAML body for loader tests.

    Each test passes its own ``epoch_lines`` (or ``extra_lines`` for things
    like ``recovery_phenotype: "wild"``) to exercise one validation path
    at a time; the other required blocks (kinematics_baselines, sessions)
    are held fixed so they don't interact with the field under test.
    """
    return (
        f"{animal_id}:\n"
        f"  stroke_date: 2025-01-01\n"
        f"  sessions:\n"
        f"    start: 2025-01-01\n"
        f"    end: 2025-01-02\n"
        f"{epoch_lines}"
        f"{extra_lines}"
        f"  kinematics_baselines:\n"
        f"    tongue: {{x0: 0.0, y0: -110.0}}\n"
        f"    jaw:    {{x0: 0.0, y0: 290.0}}\n"
    )


class TestEpochBoundariesDataclass:
    """Dataclass-level constraint enforcement on EpochBoundaries.

    Validates the Phase 9 lock 2026-05-23 schema directly via
    ``EpochBoundaries(...)`` (no YAML / loader involvement) so the
    dataclass remains usable by Phase 9 test code that builds synthetic
    boundaries.
    """

    def test_valid_construction(self):
        from stroke_orofacial.animals import EpochBoundaries
        eb = EpochBoundaries(
            acute_max_rel_day=5,
            subacute_max_rel_day=8,
            chronic_min_rel_day=9,
        )
        assert eb.acute_max_rel_day == 5
        assert eb.subacute_max_rel_day == 8
        assert eb.chronic_min_rel_day == 9

    def test_frozen_dataclass(self):
        """``frozen=True`` so an EpochBoundaries instance can't be mutated
        after construction — protects downstream consumers from accidental
        in-place edits."""
        from dataclasses import FrozenInstanceError
        from stroke_orofacial.animals import EpochBoundaries
        eb = EpochBoundaries(1, 4, 5)
        with pytest.raises(FrozenInstanceError):
            eb.acute_max_rel_day = 99  # type: ignore[misc]

    def test_acute_max_zero_raises(self):
        """acute_max_rel_day < 1 yields a 0-or-negative-width acute window
        (acute = [1, acute_max] inclusive). Loader catches the typo."""
        from stroke_orofacial.animals import (
            EpochBoundaries, ConfigValidationError,
        )
        with pytest.raises(ConfigValidationError, match="acute_max_rel_day"):
            EpochBoundaries(
                acute_max_rel_day=0,
                subacute_max_rel_day=4,
                chronic_min_rel_day=5,
            )

    def test_subacute_lte_acute_raises(self):
        """subacute_max == acute_max means a zero-day sub-acute window;
        loader rejects so the sub-acute partition is always non-empty."""
        from stroke_orofacial.animals import (
            EpochBoundaries, ConfigValidationError,
        )
        with pytest.raises(
            ConfigValidationError, match="subacute_max_rel_day",
        ):
            EpochBoundaries(
                acute_max_rel_day=5,
                subacute_max_rel_day=5,
                chronic_min_rel_day=6,
            )

    def test_subacute_lt_acute_raises(self):
        from stroke_orofacial.animals import (
            EpochBoundaries, ConfigValidationError,
        )
        with pytest.raises(
            ConfigValidationError, match="subacute_max_rel_day",
        ):
            EpochBoundaries(
                acute_max_rel_day=5,
                subacute_max_rel_day=3,
                chronic_min_rel_day=10,
            )

    def test_chronic_lte_subacute_raises(self):
        """chronic_min == subacute_max would mean rel_day=chronic_min is
        in BOTH the sub-acute and chronic windows; loader rejects so the
        chronic partition starts strictly after sub-acute ends."""
        from stroke_orofacial.animals import (
            EpochBoundaries, ConfigValidationError,
        )
        with pytest.raises(ConfigValidationError, match="chronic_min_rel_day"):
            EpochBoundaries(
                acute_max_rel_day=5,
                subacute_max_rel_day=10,
                chronic_min_rel_day=10,
            )

    def test_chronic_transitional_gap_allowed(self):
        """chronic_min > subacute_max + 1 declares a transitional gap;
        rel_day in (subacute_max, chronic_min) is uncategorized at
        assign-time. Schema accepts the gap shape."""
        from stroke_orofacial.animals import EpochBoundaries
        eb = EpochBoundaries(
            acute_max_rel_day=5,
            subacute_max_rel_day=10,
            chronic_min_rel_day=15,
        )
        assert eb.subacute_max_rel_day == 10
        assert eb.chronic_min_rel_day == 15

    def test_sentinel_chronic_9999_validates(self):
        """Forward-compat per kickoff line 190: animals that never reach a
        chronic plateau within their dataset get chronic_min_rel_day=9999
        (or any value beyond max observed rel_day). No current cohort
        animal uses this — synthetic test only."""
        from stroke_orofacial.animals import EpochBoundaries
        eb = EpochBoundaries(
            acute_max_rel_day=17,
            subacute_max_rel_day=49,
            chronic_min_rel_day=9999,
        )
        assert eb.chronic_min_rel_day == 9999

    def test_bool_rejected_as_int(self):
        """Python's bool-is-int subtype would let ``True`` silently coerce
        to 1; dataclass __post_init__ rejects to catch the typo."""
        from stroke_orofacial.animals import (
            EpochBoundaries, ConfigValidationError,
        )
        with pytest.raises(ConfigValidationError, match="must be int"):
            EpochBoundaries(
                acute_max_rel_day=True,  # type: ignore[arg-type]
                subacute_max_rel_day=4,
                chronic_min_rel_day=5,
            )

    def test_config_validation_error_is_value_error(self):
        """ConfigValidationError subclasses ValueError so existing callers
        that catch ValueError from load_animals still work."""
        from stroke_orofacial.animals import ConfigValidationError
        assert issubclass(ConfigValidationError, ValueError)


class TestEpochBoundariesLoaderValidation:
    """YAML-level loader validation — every cohort animal must have a
    well-formed epoch_boundaries block."""

    def test_missing_block_raises(self, tmp_path):
        cfg = tmp_path / "no_epoch.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                PS99:
                  stroke_date: 2025-01-01
                  sessions:
                    start: 2025-01-01
                    end: 2025-01-02
                  kinematics_baselines:
                    tongue: {x0: 0.0, y0: -110.0}
                    jaw:    {x0: 0.0, y0: 290.0}
            """)
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(
            ConfigValidationError,
            match=r"PS99.*epoch_boundaries block is required",
        ):
            load_animals(cfg)

    def test_missing_required_key_raises(self, tmp_path):
        cfg = tmp_path / "missing_key.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                epoch_lines=(
                    "  epoch_boundaries:\n"
                    "    acute_max_rel_day: 1\n"
                    "    chronic_min_rel_day: 5\n"
                ),
            ))
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(
            ConfigValidationError, match="subacute_max_rel_day",
        ):
            load_animals(cfg)

    def test_unknown_key_raises(self, tmp_path):
        cfg = tmp_path / "unknown_key.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                epoch_lines=(
                    "  epoch_boundaries:\n"
                    "    acute_max_rel_day: 1\n"
                    "    subacute_max_rel_day: 4\n"
                    "    chronic_min_rel_day: 5\n"
                    "    acute_min_rel_day: 1\n"  # typo'd extra key
                ),
            ))
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(ConfigValidationError, match="unknown"):
            load_animals(cfg)

    def test_bool_value_raises(self, tmp_path):
        cfg = tmp_path / "bool_value.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                epoch_lines=(
                    "  epoch_boundaries:\n"
                    "    acute_max_rel_day: true\n"
                    "    subacute_max_rel_day: 4\n"
                    "    chronic_min_rel_day: 5\n"
                ),
            ))
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(ConfigValidationError, match="must be int"):
            load_animals(cfg)

    def test_yaml_chronic_lte_subacute_raises(self, tmp_path):
        cfg = tmp_path / "chronic_lte_subacute.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                epoch_lines=(
                    "  epoch_boundaries:\n"
                    "    acute_max_rel_day: 5\n"
                    "    subacute_max_rel_day: 10\n"
                    "    chronic_min_rel_day: 10\n"
                ),
            ))
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(ConfigValidationError, match="chronic_min_rel_day"):
            load_animals(cfg)


class TestRecoveryPhenotypeEnum:
    """Phase 9 Task 1.5: recovery_phenotype tightened to the 4-tier enum.
    Loader raises ConfigValidationError on non-null values outside the enum.
    """

    def test_null_loads(self, animals_yaml):
        """The animals_yaml fixture has ``recovery_phenotype: null`` for
        PS46/PS54 — both load with ``recovery_phenotype is None``."""
        animals = load_animals(animals_yaml)
        assert animals["PS46"].recovery_phenotype is None
        assert animals["PS54"].recovery_phenotype is None

    @pytest.mark.parametrize(
        "phenotype",
        ["mild", "moderate", "moderate-severe", "severe"],
    )
    def test_all_four_valid_tiers_load(self, tmp_path, phenotype):
        cfg = tmp_path / f"phenotype_{phenotype}.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                extra_lines=f'  recovery_phenotype: "{phenotype}"\n',
            ))
        )
        animals = load_animals(cfg)
        assert animals["PS99"].recovery_phenotype == phenotype

    def test_wild_typo_raises_naming_value_and_valid_set(self, tmp_path):
        """Priya verification reminder #3: error message must NAME the bad
        value (``"wild"``) AND list the valid enum so the user can
        self-correct without digging into source."""
        cfg = tmp_path / "wild.yaml"
        cfg.write_text(
            textwrap.dedent(_bare_yaml_block(
                extra_lines='  recovery_phenotype: "wild"\n',
            ))
        )
        from stroke_orofacial.animals import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            load_animals(cfg)
        msg = str(exc_info.value)
        assert "'wild'" in msg, (
            "Error must quote the bad value verbatim so the user sees the "
            f"exact typo; got: {msg!r}"
        )
        for tier in ("mild", "moderate", "moderate-severe", "severe"):
            assert tier in msg, (
                f"Error must list the full valid enum; missing tier "
                f"{tier!r} from message: {msg!r}"
            )


class TestRealCohortEpochBoundariesRoundtrip:
    """Schema-roundtrip checks against the REAL configs/animals.yaml. These
    bind the loader contract to the 2026-05-23 stamped cohort values. Any
    drift in the YAML triggers a loud failure here so the cohort table in
    the kickoff stays in sync with what the loader actually produces.
    """

    # Cohort reference table — kickoff §"AnimalInfo.epoch_boundaries +
    # recovery_phenotype schema extensions" lines 207-244.
    # Epoch boundaries re-derived 2026-06-08 from the combined recovery-index
    # criterion (docs/epoch_criteria.md). recovery_phenotype (4-tier YAML field)
    # is UNCHANGED. Previous boundaries: PS47 (1,4,5), PS48 (1,4,5),
    # PS49 (1,4,5), PS51 (6,30,31), PS54 (17,39,40), PS55 (17,49,50).
    EXPECTED: dict[str, tuple[str, tuple[int, int, int]]] = {
        "PS46": ("moderate",         (5, 8, 9)),
        "PS47": ("mild",             (1, 2, 3)),
        "PS48": ("mild",             (1, 2, 3)),
        "PS49": ("mild",             (1, 5, 6)),
        "PS50": ("mild",             (1, 4, 5)),
        "PS51": ("moderate-severe",  (6, 31, 32)),
        "PS54": ("severe",           (19, 38, 39)),
        "PS55": ("severe",           (19, 50, 51)),
    }

    def test_all_eight_animals_load_with_expected_values(self):
        animals = load_animals()
        assert set(animals) == set(self.EXPECTED), (
            f"Cohort drift: loaded animals {sorted(animals)} != "
            f"expected {sorted(self.EXPECTED)}. If a 9th animal is being "
            f"added, update the kickoff cohort reference table AND the "
            f"EXPECTED dict in this test (and TestCohortPhenotype"
            f"Distribution) — the loud failure is intentional per Priya "
            f"verification reminder #2."
        )
        for animal_id, (expected_pheno, expected_bounds) in self.EXPECTED.items():
            a = animals[animal_id]
            assert a.recovery_phenotype == expected_pheno, (
                f"{animal_id} recovery_phenotype drift: "
                f"{a.recovery_phenotype!r} != {expected_pheno!r}"
            )
            eb = a.epoch_boundaries
            actual_bounds = (
                eb.acute_max_rel_day,
                eb.subacute_max_rel_day,
                eb.chronic_min_rel_day,
            )
            assert actual_bounds == expected_bounds, (
                f"{animal_id} epoch_boundaries drift: "
                f"{actual_bounds} != {expected_bounds}"
            )

    def test_ps54_ps55_share_phenotype_diverge_boundaries(self):
        """Priya verification reminder #1: PS54 and PS55 both carry
        ``recovery_phenotype="severe"`` but have DIFFERENT epoch_boundaries
        (PS55's subacute_max_rel_day + chronic_min_rel_day are +12d
        relative to PS54 because PS55 received higher laser power and
        recovered more slowly). Phase 9.1 phenotype-pooled consumers MUST
        look up per-animal boundaries — phenotype-level pooling would
        silently smear a recovery-window divergence. This test
        breaks loudly if the YAML ever collapses to identical boundaries.

        Post 2026-06-08 re-derivation: acute is shared at d+19 (was d+17);
        the sub-acute + chronic divergence widened from +10d to +12d
        (PS54 38/39 vs PS55 50/51).
        """
        animals = load_animals()
        ps54 = animals["PS54"]
        ps55 = animals["PS55"]
        assert ps54.recovery_phenotype == ps55.recovery_phenotype == "severe"
        # Acute boundary IS shared (both d+19) — only sub-acute + chronic
        # differ by +12d for PS55.
        assert ps54.epoch_boundaries.acute_max_rel_day == \
            ps55.epoch_boundaries.acute_max_rel_day
        assert (
            ps55.epoch_boundaries.subacute_max_rel_day
            - ps54.epoch_boundaries.subacute_max_rel_day
        ) == 12, "PS55 subacute_max should be PS54's + 12d"
        assert (
            ps55.epoch_boundaries.chronic_min_rel_day
            - ps54.epoch_boundaries.chronic_min_rel_day
        ) == 12, "PS55 chronic_min should be PS54's + 12d"


class TestCohortPhenotypeDistribution:
    """Phase 9.1 phenotype-pooled figures depend on knowing the per-tier
    count. This test pins the 2026-05-23 distribution so adding a 9th
    cohort animal with a different phenotype fails LOUDLY rather than
    silently shifting the per-tier counts. Per Priya verification reminder
    #2: cohort expansion must trigger an explicit DECISIONS bump rather
    than silent drift."""

    EXPECTED_DISTRIBUTION = {
        "mild": 4,
        "moderate": 1,
        "moderate-severe": 1,
        "severe": 2,
    }

    def test_distribution_pinned(self):
        from collections import Counter
        animals = load_animals()
        distribution = dict(
            Counter(a.recovery_phenotype for a in animals.values()),
        )
        assert distribution == self.EXPECTED_DISTRIBUTION, (
            f"Cohort phenotype distribution drift: {distribution} != "
            f"{self.EXPECTED_DISTRIBUTION}. If a new cohort animal is "
            f"being added, update this expected dict in the same commit "
            f"as the YAML stamping, AND add a DECISIONS entry explaining "
            f"the per-tier-count change (Phase 9.1 phenotype-pooled "
            f"figures consume these counts)."
        )

    def test_per_tier_animal_ids(self):
        """Per-tier membership pin — name the animals in each tier so a
        re-stamp (e.g. PS50 promoted from mild to moderate) breaks loudly.
        """
        from collections import defaultdict
        animals = load_animals()
        by_tier: dict[str | None, list[str]] = defaultdict(list)
        for aid, a in animals.items():
            by_tier[a.recovery_phenotype].append(aid)
        expected = {
            "mild":            ["PS47", "PS48", "PS49", "PS50"],
            "moderate":        ["PS46"],
            "moderate-severe": ["PS51"],
            "severe":          ["PS54", "PS55"],
        }
        for tier, expected_ids in expected.items():
            assert sorted(by_tier[tier]) == expected_ids, (
                f"Tier {tier!r} membership drift: "
                f"{sorted(by_tier[tier])} != {expected_ids}"
            )
