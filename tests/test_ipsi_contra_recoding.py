"""Tests for ipsi/contra coordinate recoding (Phase 9.1 Q-lock 14 Stage 1)."""
from __future__ import annotations

import dataclasses
import math

import pytest

from stroke_orofacial.animals import AnimalInfo, load_animals
from stroke_orofacial.ipsi_contra_recoding import (
    animal_cue_side_to_ipsi_contra,
    animal_signed_value_to_ipsi_contra,
    cue_side_to_ipsi_contra,
    is_sham,
    signed_value_to_ipsi_contra,
)


@pytest.fixture(scope="module")
def left_animal() -> AnimalInfo:
    """A real left-stroke cohort animal (PS46) — all 8 are L-stroke."""
    return load_animals()["PS46"]


@pytest.fixture(scope="module")
def right_animal(left_animal: AnimalInfo) -> AnimalInfo:
    """A synthetic right-stroke animal (no R-stroke animal exists in the cohort yet)."""
    return dataclasses.replace(left_animal, stroke_laterality="R")


class TestCueSideToIpsiContra:
    @pytest.mark.parametrize(
        ("cue_side", "stroke_laterality", "expected"),
        [
            ("L", "L", "ipsi"),    # cue matches lesion -> ipsi
            ("R", "L", "contra"),  # left-stroke: R-cue is contra
            ("L", "R", "contra"),  # right-stroke: L-cue is contra
            ("R", "R", "ipsi"),
        ],
    )
    def test_all_four_combinations(self, cue_side, stroke_laterality, expected):
        assert cue_side_to_ipsi_contra(cue_side, stroke_laterality) == expected

    @pytest.mark.parametrize("bad", ["left", "l", "", "sham", "X", None])
    def test_invalid_cue_side_raises(self, bad):
        with pytest.raises(ValueError, match="cue_side"):
            cue_side_to_ipsi_contra(bad, "L")

    @pytest.mark.parametrize("bad", ["left", "sham", "", None])
    def test_invalid_laterality_raises(self, bad):
        with pytest.raises(ValueError, match="stroke_laterality"):
            cue_side_to_ipsi_contra("L", bad)

    def test_matches_canonical_animalinfo_implementation(self, left_animal, right_animal):
        # The module function must agree with the canonical AnimalInfo method
        # for every (cue, laterality) pair — single source of truth invariant.
        for animal in (left_animal, right_animal):
            for cue in ("L", "R"):
                assert (
                    cue_side_to_ipsi_contra(cue, animal.stroke_laterality)
                    == animal.mouse_side_to_ipsi_contra(cue)
                )


class TestSignedValueToIpsiContra:
    def test_left_stroke_passes_through(self):
        assert signed_value_to_ipsi_contra(5.0, "L") == 5.0
        assert signed_value_to_ipsi_contra(-3.2, "L") == -3.2
        assert signed_value_to_ipsi_contra(0.0, "L") == 0.0

    def test_right_stroke_flips_sign(self):
        assert signed_value_to_ipsi_contra(5.0, "R") == -5.0
        assert signed_value_to_ipsi_contra(-3.2, "R") == 3.2

    def test_nan_passes_through_both_lateralities(self):
        assert math.isnan(signed_value_to_ipsi_contra(float("nan"), "L"))
        assert math.isnan(signed_value_to_ipsi_contra(float("nan"), "R"))

    def test_flip_is_its_own_inverse(self):
        # round-trip identity: recode + un-recode (same laterality) == original
        for v in (5.0, -3.2, 0.0, 123.456):
            for lat in ("L", "R"):
                out = signed_value_to_ipsi_contra(
                    signed_value_to_ipsi_contra(v, lat), lat
                )
                assert out == v

    @pytest.mark.parametrize("bad", ["left", "sham", "", None])
    def test_invalid_laterality_raises(self, bad):
        with pytest.raises(ValueError, match="stroke_laterality"):
            signed_value_to_ipsi_contra(1.0, bad)


class TestAnimalWrappers:
    def test_animal_cue_side_delegates(self, left_animal, right_animal):
        assert animal_cue_side_to_ipsi_contra(left_animal, "L") == "ipsi"
        assert animal_cue_side_to_ipsi_contra(left_animal, "R") == "contra"
        assert animal_cue_side_to_ipsi_contra(right_animal, "L") == "contra"
        assert animal_cue_side_to_ipsi_contra(right_animal, "R") == "ipsi"

    def test_animal_signed_value_delegates(self, left_animal, right_animal):
        assert animal_signed_value_to_ipsi_contra(left_animal, 5.0) == 5.0
        assert animal_signed_value_to_ipsi_contra(right_animal, 5.0) == -5.0


class TestIsSham:
    def test_all_current_cohort_is_not_sham(self):
        # Stage 0 audit: all 8 animals are L-stroke; none sham (not representable).
        animals = load_animals()
        assert len(animals) >= 8
        assert not any(is_sham(a) for a in animals.values())

    def test_forward_hook_reads_future_attribute(self, left_animal):
        # is_sham picks up a future is_sham_control attribute if one is added.
        future = dataclasses.replace(left_animal)
        object.__setattr__(future, "is_sham_control", True)
        assert is_sham(future) is True
