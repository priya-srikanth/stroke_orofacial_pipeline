"""Tests for stroke_orofacial.stats.recovery_epochs.

Phase 9 Task 2 prerequisite (Cowork 2026-05-23 scoping decision):
``assign_epoch_label`` + ``assign_epoch_labels_to_inputs_df`` land with
Commit A so emitted parquets carry a populated ``epoch_label`` column
from day 1.
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries, load_animals
from stroke_orofacial.stats.recovery_epochs import (
    assign_epoch_label,
    assign_epoch_labels_to_inputs_df,
    cohort_phenotype_summary,
)


def _animal(
    *,
    animal_id: str = "PS99",
    acute_max: int = 5,
    subacute_max: int = 10,
    chronic_min: int = 11,
) -> AnimalInfo:
    """Build a minimal AnimalInfo for boundary-only tests."""
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=datetime.date(2025, 1, 1),
        session_start=datetime.date(2025, 1, 1),
        session_end=datetime.date(2025, 1, 2),
        epoch_boundaries=EpochBoundaries(acute_max, subacute_max, chronic_min),
    )


class TestAssignEpochLabel:
    """Pin the boundary-condition behavior of assign_epoch_label."""

    def test_negative_rel_day_is_pre(self):
        a = _animal()
        assert assign_epoch_label(-5, a) == "pre"

    def test_zero_rel_day_is_pre(self):
        """rel_day=0 is the LAST PRE-STROKE session per the project
        convention; the stroke is induced after that day's session."""
        a = _animal()
        assert assign_epoch_label(0, a) == "pre"

    def test_acute_lower_bound(self):
        """First post-stroke day = first acute day."""
        a = _animal()
        assert assign_epoch_label(1, a) == "acute"

    def test_acute_upper_bound(self):
        a = _animal(acute_max=5)
        assert assign_epoch_label(5, a) == "acute"

    def test_subacute_lower_bound(self):
        a = _animal(acute_max=5, subacute_max=10)
        assert assign_epoch_label(6, a) == "sub_acute"

    def test_subacute_upper_bound(self):
        a = _animal(acute_max=5, subacute_max=10)
        assert assign_epoch_label(10, a) == "sub_acute"

    def test_chronic_lower_bound(self):
        a = _animal(acute_max=5, subacute_max=10, chronic_min=11)
        assert assign_epoch_label(11, a) == "chronic"

    def test_chronic_extends_to_infinity(self):
        """No upper bound on chronic."""
        a = _animal(acute_max=5, subacute_max=10, chronic_min=11)
        assert assign_epoch_label(9999, a) == "chronic"

    def test_transitional_gap_returns_none(self):
        """When chronic_min > subacute_max + 1, rel_day in the open
        interval (subacute_max, chronic_min) is uncategorized."""
        a = _animal(acute_max=5, subacute_max=10, chronic_min=15)
        assert assign_epoch_label(11, a) is None
        assert assign_epoch_label(14, a) is None
        # Boundary days still labeled.
        assert assign_epoch_label(10, a) == "sub_acute"
        assert assign_epoch_label(15, a) == "chronic"

    def test_sentinel_chronic_yields_subacute_for_all_post(self):
        """Forward-compat per kickoff line 190: animals that never reach
        a chronic plateau use chronic_min=9999. Every observed
        post-stroke session falls in [subacute_max+1, 9998] (the
        transitional-gap range) — but for the typical case
        subacute_max=9998, every observed post-stroke day is sub_acute.
        """
        # Set subacute_max=9998 so days 6..9998 are sub_acute (no gap).
        a = _animal(acute_max=5, subacute_max=9998, chronic_min=9999)
        assert assign_epoch_label(50, a) == "sub_acute"
        assert assign_epoch_label(500, a) == "sub_acute"
        assert assign_epoch_label(9998, a) == "sub_acute"
        # rel_day == 9999 still chronic by definition; just unreachable
        # in real cohorts.
        assert assign_epoch_label(9999, a) == "chronic"

    def test_real_cohort_ps54_boundaries(self):
        """PS54: severe phenotype, acute 1..17, subacute 18..39,
        chronic >=40 (kickoff 2026-05-23)."""
        animals = load_animals()
        ps54 = animals["PS54"]
        assert assign_epoch_label(0, ps54) == "pre"
        assert assign_epoch_label(1, ps54) == "acute"
        assert assign_epoch_label(17, ps54) == "acute"
        assert assign_epoch_label(18, ps54) == "sub_acute"
        assert assign_epoch_label(39, ps54) == "sub_acute"
        assert assign_epoch_label(40, ps54) == "chronic"

    def test_real_cohort_ps55_boundaries_diverge_from_ps54(self):
        """PS55 shares severe phenotype with PS54 but boundaries are
        shifted +10d (laser power 5.0 vs 3.0 mW). This pins the
        per-animal-not-per-phenotype consumer contract."""
        animals = load_animals()
        ps54 = animals["PS54"]
        ps55 = animals["PS55"]
        # Acute boundary IS shared at d+17.
        assert assign_epoch_label(17, ps54) == "acute"
        assert assign_epoch_label(17, ps55) == "acute"
        # rel_day 18..39 is sub_acute for PS54, also sub_acute for PS55
        # (PS55's subacute_max=49). The difference shows at rel_day 40+:
        # chronic for PS54, sub_acute for PS55.
        assert assign_epoch_label(40, ps54) == "chronic"
        assert assign_epoch_label(40, ps55) == "sub_acute"
        assert assign_epoch_label(49, ps55) == "sub_acute"
        assert assign_epoch_label(50, ps55) == "chronic"


class TestAssignEpochLabelsToInputsDF:
    """Pin the DataFrame-batch helper consumed by Task 2 materialize."""

    def test_basic_join(self):
        df = pd.DataFrame({
            "animal": ["PS99", "PS99", "PS99"],
            "rel_day": [-1, 3, 8],
        })
        animals = {"PS99": _animal(acute_max=5, subacute_max=10, chronic_min=11)}
        out = assign_epoch_labels_to_inputs_df(df, animals)
        assert list(out["epoch_label"]) == ["pre", "acute", "sub_acute"]

    def test_multi_animal_uses_per_animal_boundaries(self):
        """Two animals with DIFFERENT boundaries → same rel_day yields
        DIFFERENT epoch labels (the Priya verification reminder #1
        invariant restated at the DataFrame level)."""
        df = pd.DataFrame({
            "animal": ["A", "B"],
            "rel_day": [40, 40],
        })
        animals = {
            "A": _animal(animal_id="A", acute_max=17, subacute_max=39, chronic_min=40),
            "B": _animal(animal_id="B", acute_max=17, subacute_max=49, chronic_min=50),
        }
        out = assign_epoch_labels_to_inputs_df(df, animals)
        assert out["epoch_label"].tolist() == ["chronic", "sub_acute"]

    def test_input_not_mutated(self):
        df = pd.DataFrame({"animal": ["PS99"], "rel_day": [3]})
        animals = {"PS99": _animal()}
        _ = assign_epoch_labels_to_inputs_df(df, animals)
        assert "epoch_label" not in df.columns

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"animal": ["PS99"]})  # missing rel_day
        with pytest.raises(ValueError, match="rel_day"):
            assign_epoch_labels_to_inputs_df(df, {"PS99": _animal()})

    def test_missing_animal_raises(self):
        df = pd.DataFrame({"animal": ["PS_MISSING"], "rel_day": [1]})
        with pytest.raises(KeyError, match="PS_MISSING"):
            assign_epoch_labels_to_inputs_df(df, {"PS99": _animal()})

    def test_real_cohort_distribution(self):
        """Smoke test on real cohort: emit one row per (animal, rel_day
        sample) and verify the resulting epoch_label distribution
        matches per-animal boundaries."""
        animals = load_animals()
        rows = []
        for aid, a in animals.items():
            for rel_day in (-1, 0, 1, 50):
                rows.append({"animal": aid, "rel_day": rel_day})
        df = pd.DataFrame(rows)
        out = assign_epoch_labels_to_inputs_df(df, animals)
        # rel_day = -1 → all pre.
        pre_rows = out[out["rel_day"] == -1]
        assert (pre_rows["epoch_label"] == "pre").all()
        # rel_day = 1 → all acute (every animal has acute_max >= 1).
        acute_rows = out[out["rel_day"] == 1]
        assert (acute_rows["epoch_label"] == "acute").all()
        # rel_day = 50: PS46-PS50 (acute_max=1 or 5; subacute_max <= 14;
        # chronic_min from 5-9), so 50 is chronic. PS51 chronic_min=31 so
        # 50 is chronic. PS54 chronic_min=40 so 50 is chronic. PS55
        # chronic_min=50 so 50 is chronic. All chronic.
        far_rows = out[out["rel_day"] == 50]
        assert (far_rows["epoch_label"] == "chronic").all()


class TestCohortMembershipPin:
    """Forward-compatibility canary: any cohort expansion that adds a
    new AnimalInfo MUST update this module's exports if needed. This
    test is intentionally cheap and lives here (not in test_animals.py)
    so a failure points at the recovery_epochs consumer first."""

    def test_every_cohort_animal_has_epoch_boundaries(self):
        animals = load_animals()
        for aid, a in animals.items():
            assert a.epoch_boundaries is not None, (
                f"Animal {aid} has no epoch_boundaries — Task 2 "
                f"materialization will fail at assign_epoch_label."
            )


class TestCohortPhenotypeSummary:
    """Pin the cohort_phenotype_summary output schema + content."""

    def test_returns_one_row_per_animal_sorted_by_id(self):
        a1 = _animal(animal_id="PS47", acute_max=1, subacute_max=4, chronic_min=5)
        a2 = _animal(animal_id="PS46", acute_max=5, subacute_max=8, chronic_min=9)
        df = cohort_phenotype_summary({"PS47": a1, "PS46": a2})
        assert list(df["animal"]) == ["PS46", "PS47"]

    def test_schema_has_expected_columns(self):
        a = _animal()
        df = cohort_phenotype_summary({"PS99": a})
        expected = {
            "animal", "recovery_phenotype", "acute_max_rel_day",
            "subacute_max_rel_day", "chronic_min_rel_day",
            "transitional_gap_days",
        }
        assert set(df.columns) == expected

    def test_transitional_gap_zero_when_contiguous(self):
        """chronic_min = subacute_max + 1 → no gap."""
        a = _animal(acute_max=5, subacute_max=10, chronic_min=11)
        df = cohort_phenotype_summary({"PS99": a})
        assert df["transitional_gap_days"].iloc[0] == 0

    def test_transitional_gap_positive_when_skip(self):
        """chronic_min = subacute_max + 5 → 4-day gap (exclusive on both)."""
        a = _animal(acute_max=5, subacute_max=10, chronic_min=15)
        df = cohort_phenotype_summary({"PS99": a})
        assert df["transitional_gap_days"].iloc[0] == 4

    def test_recovery_phenotype_passed_through_when_none(self):
        a = _animal()  # default helper doesn't stamp recovery_phenotype
        df = cohort_phenotype_summary({"PS99": a})
        assert pd.isna(df["recovery_phenotype"].iloc[0])

    def test_real_cohort_phenotype_counts(self):
        """Lock the 2026-05-23 cohort phenotype distribution.

        Per Phase 9 Task 1.5 stamping in configs/animals.yaml:
        mild = 4 (PS47-PS50), moderate = 1 (PS46), moderate-severe = 1
        (PS51), severe = 2 (PS54, PS55).
        """
        df = cohort_phenotype_summary(load_animals())
        counts = df["recovery_phenotype"].value_counts(dropna=False).to_dict()
        assert counts == {
            "mild": 4, "moderate": 1, "moderate-severe": 1, "severe": 2,
        }

    def test_real_cohort_severe_boundaries_diverge(self):
        """PS54 and PS55 both 'severe' but boundaries differ — guard
        against phenotype-pooling consumers that assume identical
        boundaries within tier."""
        df = cohort_phenotype_summary(load_animals())
        severe = df[df["recovery_phenotype"] == "severe"].sort_values("animal")
        ps54, ps55 = severe.iloc[0], severe.iloc[1]
        assert ps54["animal"] == "PS54"
        assert ps55["animal"] == "PS55"
        # PS55 is +10d shifted vs PS54 per the higher-laser-power yaml stamp.
        assert ps55["chronic_min_rel_day"] - ps54["chronic_min_rel_day"] == 10
