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
              analysis_params:
                break_thr_trialmax: 12000.0
                break_thr_alllicks: 9000.0

            PS54:
              stroke_date: 2025-04-30
              sessions:
                start: 2025-04-16
                end: 2025-07-09
              exclusions:
                - date: 2025-04-26
                  reason: "excluded in tongue analysis"
                  applies_to: [tongue]
              recovery_phenotype: null

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
        assert exc.applies_to == ["tongue"]


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
        )
        assert info.phase(datetime.date(2025, 3, 13)) == "baseline"

    def test_phase_after_stroke(self):
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
        )
        assert info.phase(datetime.date(2025, 3, 14)) == "post_stroke"
        assert info.phase(datetime.date(2025, 3, 20)) == "post_stroke"

    def test_is_excluded_universal(self):
        info = AnimalInfo(
            animal_id="T",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 1),
            exclusions=[
                Exclusion(datetime.date(2025, 1, 5), "bad session", ["all"]),
            ],
        )
        excluded, reason = info.is_excluded(datetime.date(2025, 1, 5))
        assert excluded is True
        assert reason == "bad session"

    def test_is_excluded_analysis_specific(self):
        info = AnimalInfo(
            animal_id="T",
            stroke_date=datetime.date(2025, 1, 1),
            session_start=datetime.date(2025, 1, 1),
            session_end=datetime.date(2025, 1, 1),
            exclusions=[
                Exclusion(datetime.date(2025, 1, 5), "tongue issue", ["tongue"]),
            ],
        )
        # Excluded for tongue analysis
        excluded, _ = info.is_excluded(datetime.date(2025, 1, 5), "tongue")
        assert excluded is True
        # Not excluded for jaw analysis
        excluded, _ = info.is_excluded(datetime.date(2025, 1, 5), "jaw")
        assert excluded is False
        # Not excluded when no analysis type specified (only universal applies)
        excluded, _ = info.is_excluded(datetime.date(2025, 1, 5))
        assert excluded is False


class TestExclusion:
    def test_applies_all(self):
        exc = Exclusion(datetime.date(2025, 1, 1), "reason", ["all"])
        assert exc.applies("tongue") is True
        assert exc.applies("jaw") is True
        assert exc.applies(None) is True

    def test_applies_specific(self):
        exc = Exclusion(datetime.date(2025, 1, 1), "reason", ["tongue"])
        assert exc.applies("tongue") is True
        assert exc.applies("jaw") is False
        assert exc.applies(None) is False
