"""Phase 9.1 Q-lock 12 Addendum #5 — W-2 stats module tests.

Unit tests for
:mod:`stroke_orofacial.stats.spatial_wasserstein` and the
phenotype-pooled W-2 aggregator in
:mod:`stroke_orofacial.stats.aggregators`.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.stats.aggregators import (
    aggregate_phenotype_pooled_wasserstein,
)
from stroke_orofacial.stats.spatial_wasserstein import (
    _bin_centers_2d,
    compute_per_animal_wasserstein2,
    compute_wasserstein2_2d,
)


def _make_ai(animal_id: str, phenotype: str | None = "mild") -> AnimalInfo:
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


# ---------------------------------------------------------------------------
# _bin_centers_2d
# ---------------------------------------------------------------------------


class TestBinCenters2D:
    def test_4x4_grid_centers(self) -> None:
        # extent [0, 4, 0, 4] with nx=ny=4 → bin width 1.0;
        # bin centers at 0.5, 1.5, 2.5, 3.5 in each axis.
        centers = _bin_centers_2d([0.0, 4.0, 0.0, 4.0], 4, 4)
        assert centers.shape == (16, 2)
        # First bin center is (0.5, 0.5).
        np.testing.assert_allclose(centers[0], [0.5, 0.5])
        # Last bin center is (3.5, 3.5).
        np.testing.assert_allclose(centers[-1], [3.5, 3.5])
        # Row-major over (i, j): bin index 5 = (i=1, j=1) → (1.5, 1.5).
        np.testing.assert_allclose(centers[5], [1.5, 1.5])


# ---------------------------------------------------------------------------
# compute_wasserstein2_2d
# ---------------------------------------------------------------------------


class TestComputeWasserstein22D:
    def test_identical_distributions_yield_zero(self) -> None:
        H = np.array([[10, 0], [0, 5]], dtype=np.float64)
        w2 = compute_wasserstein2_2d(H, H, [0.0, 2.0, 0.0, 2.0])
        np.testing.assert_allclose(w2, 0.0, atol=1e-9)

    def test_two_deltas_distance_d_apart(self) -> None:
        """Two single-bin (delta) distributions separated by distance d
        on a 4×4 grid should produce W-2 = d (the only transport plan
        moves all mass between the two bins)."""
        # Bin centers on a [0,4]×[0,4] grid with 4 bins per side =
        # 0.5, 1.5, 2.5, 3.5. Place delta at (0.5, 0.5) and at
        # (2.5, 0.5) → distance d = 2.0 pixels.
        H_pre = np.zeros((4, 4))
        H_pre[0, 0] = 1.0
        H_post = np.zeros((4, 4))
        H_post[2, 0] = 1.0
        w2 = compute_wasserstein2_2d(H_pre, H_post, [0.0, 4.0, 0.0, 4.0])
        np.testing.assert_allclose(w2, 2.0, atol=1e-9)

    def test_two_deltas_diagonal_distance(self) -> None:
        """Diagonal separation: (0.5, 0.5) → (2.5, 2.5) →
        W-2 = sqrt(2² + 2²) = 2√2."""
        H_pre = np.zeros((4, 4))
        H_pre[0, 0] = 1.0
        H_post = np.zeros((4, 4))
        H_post[2, 2] = 1.0
        w2 = compute_wasserstein2_2d(H_pre, H_post, [0.0, 4.0, 0.0, 4.0])
        np.testing.assert_allclose(w2, 2.0 * np.sqrt(2.0), atol=1e-9)

    def test_nan_when_either_side_empty(self) -> None:
        H_zero = np.zeros((4, 4))
        H_nonzero = np.zeros((4, 4))
        H_nonzero[1, 1] = 1.0
        assert np.isnan(compute_wasserstein2_2d(
            H_zero, H_nonzero, [0.0, 4.0, 0.0, 4.0],
        ))
        assert np.isnan(compute_wasserstein2_2d(
            H_nonzero, H_zero, [0.0, 4.0, 0.0, 4.0],
        ))

    def test_shape_mismatch_raises(self) -> None:
        H_pre = np.zeros((4, 4))
        H_post = np.zeros((4, 3))
        with pytest.raises(ValueError, match="shape mismatch"):
            compute_wasserstein2_2d(H_pre, H_post, [0.0, 4.0, 0.0, 4.0])

    def test_renormalization_independence(self) -> None:
        """Scaling H_pre uniformly should not change W-2 — the function
        renormalizes each side to sum to 1 before solving."""
        H_pre = np.zeros((4, 4))
        H_pre[0, 0] = 1.0
        H_post = np.zeros((4, 4))
        H_post[2, 0] = 1.0
        w2_1 = compute_wasserstein2_2d(
            H_pre, H_post, [0.0, 4.0, 0.0, 4.0],
        )
        w2_2 = compute_wasserstein2_2d(
            H_pre * 1000, H_post * 7, [0.0, 4.0, 0.0, 4.0],
        )
        np.testing.assert_allclose(w2_1, w2_2, atol=1e-9)


# ---------------------------------------------------------------------------
# compute_per_animal_wasserstein2 wrapper
# ---------------------------------------------------------------------------


class TestComputePerAnimalWasserstein2:
    def test_nan_when_h_post_none(self) -> None:
        pre_pool = {
            "H_pre_counts": np.zeros((4, 4)) + 1.0,
            "n_total_pre_frames": 100,
            "n_pre_sessions": 1, "n_pre_trials": 10,
            "extent": [0.0, 4.0, 0.0, 4.0],
        }
        w2 = compute_per_animal_wasserstein2(
            pre_pool=pre_pool, H_post_counts=None,
            extent=[0.0, 4.0, 0.0, 4.0],
        )
        assert np.isnan(w2)

    def test_forwards_to_pure_math(self) -> None:
        H_pre = np.zeros((4, 4))
        H_pre[0, 0] = 1.0
        H_post = np.zeros((4, 4))
        H_post[2, 0] = 1.0
        pre_pool = {
            "H_pre_counts": H_pre, "n_total_pre_frames": 1,
            "extent": [0.0, 4.0, 0.0, 4.0],
        }
        w2 = compute_per_animal_wasserstein2(
            pre_pool=pre_pool, H_post_counts=H_post,
            extent=[0.0, 4.0, 0.0, 4.0],
        )
        np.testing.assert_allclose(w2, 2.0, atol=1e-9)


# ---------------------------------------------------------------------------
# aggregate_phenotype_pooled_wasserstein
# ---------------------------------------------------------------------------


class TestAggregatePhenotypePooledWasserstein:
    def test_mean_and_sem_across_phenotype(self) -> None:
        animals = {
            "A": _make_ai("A", "mild"),
            "B": _make_ai("B", "mild"),
            "C": _make_ai("C", "mild"),
        }
        recs = [
            {"animal": "A", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 1.0},
            {"animal": "B", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 2.0},
            {"animal": "C", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 3.0},
        ]
        out = aggregate_phenotype_pooled_wasserstein(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        np.testing.assert_allclose(pooled["w2_mean"], 2.0)
        # std(ddof=1) of [1,2,3] = 1.0; SEM = 1.0 / sqrt(3).
        np.testing.assert_allclose(pooled["w2_sem"], 1.0 / np.sqrt(3))
        assert pooled["n_animals"] == 3
        assert pooled["contributing_animals"] == ["A", "B", "C"]
        assert pooled["w2_per_animal"] == {"A": 1.0, "B": 2.0, "C": 3.0}

    def test_n1_sem_is_nan(self) -> None:
        animals = {"A": _make_ai("A", "moderate")}
        recs = [{"animal": "A", "side": "L", "bodypart": "tongue",
                 "post_epoch": "acute", "w2": 5.5}]
        out = aggregate_phenotype_pooled_wasserstein(recs, animals)
        pooled = out[("moderate", "L", "tongue", "acute")]
        np.testing.assert_allclose(pooled["w2_mean"], 5.5)
        assert np.isnan(pooled["w2_sem"])
        assert pooled["n_animals"] == 1

    def test_nan_w2_dropped_from_pool(self) -> None:
        animals = {
            "A": _make_ai("A", "mild"), "B": _make_ai("B", "mild"),
        }
        recs = [
            {"animal": "A", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 1.0},
            {"animal": "B", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": float("nan")},
        ]
        out = aggregate_phenotype_pooled_wasserstein(recs, animals)
        pooled = out[("mild", "L", "tongue", "acute")]
        assert pooled["n_animals"] == 1
        assert pooled["contributing_animals"] == ["A"]
        np.testing.assert_allclose(pooled["w2_mean"], 1.0)

    def test_missing_phenotype_dropped(self) -> None:
        animals = {
            "A": _make_ai("A", "mild"), "X": _make_ai("X", None),
        }
        recs = [
            {"animal": "A", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 1.0},
            {"animal": "X", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 99.0},
        ]
        out = aggregate_phenotype_pooled_wasserstein(recs, animals)
        assert list(out.keys()) == [("mild", "L", "tongue", "acute")]

    def test_phenotypes_pool_separately(self) -> None:
        animals = {
            "A": _make_ai("A", "mild"),
            "B": _make_ai("B", "severe"),
        }
        recs = [
            {"animal": "A", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 1.0},
            {"animal": "B", "side": "L", "bodypart": "tongue",
             "post_epoch": "acute", "w2": 9.0},
        ]
        out = aggregate_phenotype_pooled_wasserstein(recs, animals)
        np.testing.assert_allclose(
            out[("mild", "L", "tongue", "acute")]["w2_mean"], 1.0,
        )
        np.testing.assert_allclose(
            out[("severe", "L", "tongue", "acute")]["w2_mean"], 9.0,
        )

    def test_missing_required_key_raises(self) -> None:
        animals = {"A": _make_ai("A", "mild")}
        recs = [{"animal": "A", "side": "L", "bodypart": "tongue"}]
        with pytest.raises(ValueError, match="missing keys"):
            aggregate_phenotype_pooled_wasserstein(recs, animals)

    def test_empty_input(self) -> None:
        out = aggregate_phenotype_pooled_wasserstein([], {})
        assert out == {}
