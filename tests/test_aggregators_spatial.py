"""Phase 9.1 Q-lock 12 Stage 2 — phenotype-pooled spatial aggregator tests.

Unit tests for
:func:`stroke_orofacial.stats.aggregators.aggregate_phenotype_pooled_spatial_diff`:
NaN-aware mean across animals, phenotype bucketing, shape/extent
consistency checks, edge cases.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.stats.aggregators import (
    aggregate_phenotype_pooled_spatial_diff,
)


def _make_ai(
    animal_id: str, phenotype: str | None = "mild",
) -> AnimalInfo:
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=dt.date(2025, 3, 10),
        session_start=dt.date(2024, 1, 1),
        session_end=dt.date(2026, 12, 31),
        epoch_boundaries=EpochBoundaries(
            acute_max_rel_day=7, subacute_max_rel_day=14, chronic_min_rel_day=21,
        ),
        recovery_phenotype=phenotype,
    )


def _rec(
    animal: str,
    side: str,
    bp: str,
    ep: str,
    D: np.ndarray | None,
    *,
    extent: list[float] | None = None,
    n_pre_trials: int = 100,
    n_post_trials: int = 80,
) -> dict[str, object]:
    if extent is None:
        extent = [-200.0, 200.0, 50.0, 550.0]
    return {
        "animal": animal,
        "side": side,
        "bodypart": bp,
        "post_epoch": ep,
        "D": D,
        "extent": extent,
        "n_pre_trials": n_pre_trials,
        "n_post_trials": n_post_trials,
    }


class TestAggregatePhenotypePooledSpatialDiff:
    def test_mean_across_animals_within_phenotype(self) -> None:
        """Hand-computed mean: 2 animals in same phenotype, simple D arrays."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        D_A = np.array([[0.10, 0.20], [-0.05, 0.00]])
        D_B = np.array([[0.30, 0.40], [-0.15, 0.10]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_A),
            _rec("PS_B", "L", "tongue", "acute", D_B),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        assert ("mild", "L", "tongue", "acute") in out
        pooled = out[("mild", "L", "tongue", "acute")]
        np.testing.assert_allclose(
            pooled["D_mean"],
            (D_A + D_B) / 2,
            atol=1e-12,
        )
        assert pooled["n_animals"] == 2
        assert pooled["contributing_animals"] == ["PS_A", "PS_B"]
        np.testing.assert_array_equal(
            pooled["n_contributing_animals_per_cell"],
            np.full(D_A.shape, 2, dtype=np.int64),
        )

    def test_nanmean_skips_nan_cells(self) -> None:
        """A cell that's NaN in one animal but finite in another averages
        only over the finite contributions."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        D_A = np.array([[0.10, np.nan], [-0.05, 0.00]])
        D_B = np.array([[0.30, 0.40], [np.nan, 0.10]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_A),
            _rec("PS_B", "L", "tongue", "acute", D_B),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        # Cell (0, 0): both finite → mean.
        np.testing.assert_allclose(pooled["D_mean"][0, 0], (0.10 + 0.30) / 2)
        # Cell (0, 1): only B finite → just B's value.
        np.testing.assert_allclose(pooled["D_mean"][0, 1], 0.40)
        # Cell (1, 0): only A finite → just A's value.
        np.testing.assert_allclose(pooled["D_mean"][1, 0], -0.05)
        # Cell (1, 1): both finite → mean.
        np.testing.assert_allclose(pooled["D_mean"][1, 1], (0.00 + 0.10) / 2)
        # n_contributing matches.
        np.testing.assert_array_equal(
            pooled["n_contributing_animals_per_cell"],
            np.array([[2, 1], [1, 2]]),
        )

    def test_all_nan_cell_stays_nan(self) -> None:
        """A cell where every animal is NaN → pooled cell remains NaN."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        D_A = np.array([[np.nan, 0.10]])
        D_B = np.array([[np.nan, 0.20]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_A),
            _rec("PS_B", "L", "tongue", "acute", D_B),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        assert np.isnan(pooled["D_mean"][0, 0])
        assert np.isfinite(pooled["D_mean"][0, 1])
        assert pooled["n_contributing_animals_per_cell"][0, 0] == 0
        assert pooled["n_contributing_animals_per_cell"][0, 1] == 2

    def test_phenotypes_pool_separately(self) -> None:
        """Animals with different phenotypes pool independently."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
            "PS_C": _make_ai("PS_C", "severe"),
        }
        D_mild_A = np.array([[0.10]])
        D_mild_B = np.array([[0.20]])
        D_sev_C = np.array([[0.90]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_mild_A),
            _rec("PS_B", "L", "tongue", "acute", D_mild_B),
            _rec("PS_C", "L", "tongue", "acute", D_sev_C),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        np.testing.assert_allclose(
            out[("mild", "L", "tongue", "acute")]["D_mean"], [[0.15]],
        )
        np.testing.assert_allclose(
            out[("severe", "L", "tongue", "acute")]["D_mean"], [[0.90]],
        )
        # n=1 phenotype tier is still aggregated (matches the q13b spec
        # for moderate / moderate-severe singletons).
        assert out[("severe", "L", "tongue", "acute")]["n_animals"] == 1

    def test_d_none_records_dropped(self) -> None:
        """Stage 1 returning None (empty epoch, missing parquets, etc.) is
        treated as no contribution — phenotype mean ignores it."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        D_A = np.array([[0.10]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_A),
            _rec("PS_B", "L", "tongue", "acute", None),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        np.testing.assert_allclose(pooled["D_mean"], D_A)
        assert pooled["contributing_animals"] == ["PS_A"]

    def test_animal_missing_phenotype_dropped(self) -> None:
        """Animals with recovery_phenotype=None are skipped, with no error."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_X": _make_ai("PS_X", None),  # phenotype not yet stamped
        }
        recs = [
            _rec("PS_A", "L", "tongue", "acute", np.array([[0.10]])),
            _rec("PS_X", "L", "tongue", "acute", np.array([[0.99]])),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        assert list(out.keys()) == [("mild", "L", "tongue", "acute")]
        assert out[("mild", "L", "tongue", "acute")]["contributing_animals"] == [
            "PS_A",
        ]

    def test_animal_not_in_map_dropped(self) -> None:
        """Records for animals not present in the animals map are skipped."""
        animals = {"PS_A": _make_ai("PS_A", "mild")}
        recs = [
            _rec("PS_A", "L", "tongue", "acute", np.array([[0.10]])),
            _rec("PS_UNK", "L", "tongue", "acute", np.array([[0.99]])),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        assert out[("mild", "L", "tongue", "acute")]["contributing_animals"] == [
            "PS_A",
        ]

    def test_shape_mismatch_within_phenotype_raises(self) -> None:
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        recs = [
            _rec("PS_A", "L", "tongue", "acute", np.zeros((5, 5))),
            _rec("PS_B", "L", "tongue", "acute", np.zeros((5, 4))),
        ]
        with pytest.raises(ValueError, match="shape mismatch"):
            aggregate_phenotype_pooled_spatial_diff(recs, animals)

    def test_extent_mismatch_within_phenotype_raises(self) -> None:
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        recs = [
            _rec("PS_A", "L", "tongue", "acute", np.zeros((2, 2)),
                 extent=[-200.0, 200.0, 50.0, 550.0]),
            _rec("PS_B", "L", "tongue", "acute", np.zeros((2, 2)),
                 extent=[-150.0, 150.0, 60.0, 540.0]),
        ]
        with pytest.raises(ValueError, match="extent mismatch"):
            aggregate_phenotype_pooled_spatial_diff(recs, animals)

    def test_per_animal_trial_counts_preserved(self) -> None:
        """Per-panel annotation needs the pre/post trial counts per animal."""
        animals = {
            "PS_A": _make_ai("PS_A", "mild"),
            "PS_B": _make_ai("PS_B", "mild"),
        }
        recs = [
            _rec("PS_A", "L", "tongue", "acute", np.array([[0.1]]),
                 n_pre_trials=150, n_post_trials=120),
            _rec("PS_B", "L", "tongue", "acute", np.array([[0.2]]),
                 n_pre_trials=80, n_post_trials=60),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        assert pooled["n_pre_trials_per_animal"] == {"PS_A": 150, "PS_B": 80}
        assert pooled["n_post_trials_per_animal"] == {"PS_A": 120, "PS_B": 60}

    def test_empty_input_yields_empty_output(self) -> None:
        out = aggregate_phenotype_pooled_spatial_diff([], {})
        assert out == {}

    def test_missing_required_key_raises(self) -> None:
        animals = {"PS_A": _make_ai("PS_A", "mild")}
        recs = [{
            "animal": "PS_A", "side": "L", "bodypart": "tongue",
            # missing: post_epoch, D, extent, n_pre_trials, n_post_trials
        }]
        with pytest.raises(ValueError, match="missing keys"):
            aggregate_phenotype_pooled_spatial_diff(recs, animals)

    def test_multiple_sides_and_epochs_keep_separate(self) -> None:
        """Cross-product over (side, bp, epoch) all preserved in the output."""
        animals = {"PS_A": _make_ai("PS_A", "mild")}
        D_LA = np.array([[0.10]])
        D_RA = np.array([[0.20]])
        D_Lj = np.array([[0.30]])
        D_Lc = np.array([[0.40]])
        recs = [
            _rec("PS_A", "L", "tongue", "acute", D_LA),
            _rec("PS_A", "R", "tongue", "acute", D_RA),
            _rec("PS_A", "L", "jaw", "acute", D_Lj),
            _rec("PS_A", "L", "tongue", "chronic", D_Lc),
        ]
        out = aggregate_phenotype_pooled_spatial_diff(recs, animals)
        assert set(out.keys()) == {
            ("mild", "L", "tongue", "acute"),
            ("mild", "R", "tongue", "acute"),
            ("mild", "L", "jaw", "acute"),
            ("mild", "L", "tongue", "chronic"),
        }
