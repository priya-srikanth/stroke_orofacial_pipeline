"""Phase 9.1 Q-lock 12 Stage 1 — Per-animal proportion-diff stats tests.

Unit tests for :mod:`stroke_orofacial.stats.spatial_proportion_diff`:
- :func:`compute_proportion_diff_within` math layer: hand-computed
  expected D arrays on synthetic histograms, no-data masking, Q17
  total-frame denominator semantics, error paths.
- :func:`split_post_dates_by_epoch` date categorization using a
  synthetic AnimalInfo with stamped epoch boundaries.
- 2-animal × 2-epoch fixture pinned to verify within-animal
  normalization (each animal's D is independent; no cohort-aggregate
  baseline contamination).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
from stroke_orofacial.stats.spatial_proportion_diff import (
    BODYPART_CENTER_MODES,
    POST_EPOCHS,
    SIDES,
    compute_proportion_diff_within,
    split_post_dates_by_epoch,
)


# ---------------------------------------------------------------------------
# Pure-math: compute_proportion_diff_within
# ---------------------------------------------------------------------------


class TestComputeProportionDiffWithin:
    def test_hand_computed_2x2_within_animal_diff(self) -> None:
        """Hand-computed expected D for a 2×2 synthetic single-animal case.

        Pre: H_pre_counts = [[40, 30], [20, 10]], n_total_pre = 200
            → P_pre  = [[0.20, 0.15], [0.10, 0.05]]
        Post: H_post_counts = [[20, 30], [40, 60]], n_total_post = 300
            → P_post = [[2/30, 0.10], [4/30, 0.20]]
        D = P_post - P_pre
          = [[2/30 - 0.20, 0.10 - 0.15],
             [4/30 - 0.10, 0.20 - 0.05]]
          = [[-0.13333..., -0.05], [0.03333..., 0.15]]
        """
        H_pre = np.array([[40, 30], [20, 10]], dtype=np.float64)
        H_post = np.array([[20, 30], [40, 60]], dtype=np.float64)
        D = compute_proportion_diff_within(H_pre, 200, H_post, 300)
        expected = np.array(
            [
                [20 / 300 - 40 / 200, 30 / 300 - 30 / 200],
                [40 / 300 - 20 / 200, 60 / 300 - 10 / 200],
            ],
            dtype=np.float64,
        )
        np.testing.assert_allclose(D, expected, atol=1e-12)

    def test_q17_denominator_differs_from_h_counts_sum(self) -> None:
        """Q17 lock: denominator is total-in-window-frames, NOT H_counts.sum().

        H_counts.sum() <= n_total because not every in-window frame
        passes the bodypart's likelihood + x_range filter. If we
        accidentally divided by H.sum() the diff would be inflated.
        """
        H_pre = np.array([[10, 10]], dtype=np.float64)
        H_post = np.array([[10, 10]], dtype=np.float64)
        # H.sum() = 20 for both; if we used H.sum() denominators, D = 0.
        # With distinct total-frame denominators (n_pre=100, n_post=200)
        # the diff is real: P_pre=0.10 vs P_post=0.05 each.
        D = compute_proportion_diff_within(H_pre, 100, H_post, 200)
        expected = np.array([[10 / 200 - 10 / 100, 10 / 200 - 10 / 100]])
        np.testing.assert_allclose(D, expected, atol=1e-12)
        # And the result is non-zero — confirming Q17 != H.sum() behavior.
        assert not np.allclose(D, 0.0)

    def test_no_data_cells_set_to_nan(self) -> None:
        """Cells with H_pre==0 AND H_post==0 must become NaN."""
        H_pre = np.array([[0, 5], [3, 0]], dtype=np.float64)
        H_post = np.array([[0, 4], [2, 8]], dtype=np.float64)
        D = compute_proportion_diff_within(H_pre, 50, H_post, 100)
        # Top-left cell: pre==0 AND post==0 → NaN
        assert np.isnan(D[0, 0])
        # Bottom-right cell: pre==0 but post!=0 → finite real diff
        assert np.isfinite(D[1, 1])
        np.testing.assert_allclose(D[1, 1], 8 / 100 - 0 / 50)
        # Other cells finite
        assert np.isfinite(D[0, 1])
        assert np.isfinite(D[1, 0])

    def test_pre_zero_post_positive_is_not_masked(self) -> None:
        """No-change vs no-data distinction: pre==0 alone is signal, not no-data.

        Per Q12-E lock: only (H_pre==0)&(H_post==0) is no-data. A bin
        that newly appears post-stroke (pre==0, post>0) is a real
        positive diff signal and must remain finite.
        """
        H_pre = np.array([[0]], dtype=np.float64)
        H_post = np.array([[5]], dtype=np.float64)
        D = compute_proportion_diff_within(H_pre, 100, H_post, 100)
        assert np.isfinite(D[0, 0])
        np.testing.assert_allclose(D[0, 0], 5 / 100 - 0 / 100)

    def test_no_magnitude_floor_q12_k(self) -> None:
        """Q12-K lock: tiny diff values pass through (no magnitude floor)."""
        H_pre = np.array([[1]], dtype=np.float64)
        H_post = np.array([[1]], dtype=np.float64)
        # Tiny but non-zero diff: 1/10001 - 1/10000 ≈ -1e-8
        D = compute_proportion_diff_within(H_pre, 10000, H_post, 10001)
        assert np.isfinite(D[0, 0])
        assert abs(D[0, 0]) > 0  # not silenced by a floor

    def test_shape_mismatch_raises(self) -> None:
        H_pre = np.zeros((5, 5))
        H_post = np.zeros((5, 4))
        with pytest.raises(ValueError, match="shape mismatch"):
            compute_proportion_diff_within(H_pre, 10, H_post, 10)

    @pytest.mark.parametrize("n_pre,n_post", [(0, 10), (10, 0), (-1, 10), (10, -1)])
    def test_nonpositive_denominator_raises(
        self, n_pre: int, n_post: int,
    ) -> None:
        H = np.array([[1]], dtype=np.float64)
        with pytest.raises(ValueError, match="non-positive denominator"):
            compute_proportion_diff_within(H, n_pre, H, n_post)


# ---------------------------------------------------------------------------
# Within-animal independence: 2-animal × 2-epoch fixture
# ---------------------------------------------------------------------------


class TestWithinAnimalNormalizationIndependence:
    """Q12-A lock: each animal's D is computed against ITS OWN pre-pool.

    Animal-A and Animal-B may have totally different pre-stroke spatial
    distributions; that variability must NOT leak into either animal's
    D via a shared cohort-aggregate baseline. Direct unit test:
    construct two synthetic animals with different pre distributions
    and verify each animal's D matches the hand-computed D against ITS
    OWN pre.
    """

    def test_two_animals_two_epochs_within_baseline(self) -> None:
        H_pre_A = np.array([[80, 20]], dtype=np.float64)  # P_pre_A = [0.8, 0.2]
        H_pre_B = np.array([[20, 80]], dtype=np.float64)  # P_pre_B = [0.2, 0.8]
        n_pre = 100
        # Acute: both animals shift the same fraction post-stroke
        H_acute_A = np.array([[60, 40]], dtype=np.float64)  # P=[0.6, 0.4]
        H_acute_B = np.array([[40, 60]], dtype=np.float64)  # P=[0.4, 0.6]
        # Sub_acute: different shift magnitudes
        H_sub_A = np.array([[70, 30]], dtype=np.float64)
        H_sub_B = np.array([[30, 70]], dtype=np.float64)
        n_post = 100

        D_A_acute = compute_proportion_diff_within(
            H_pre_A, n_pre, H_acute_A, n_post,
        )
        D_A_sub = compute_proportion_diff_within(
            H_pre_A, n_pre, H_sub_A, n_post,
        )
        D_B_acute = compute_proportion_diff_within(
            H_pre_B, n_pre, H_acute_B, n_post,
        )
        D_B_sub = compute_proportion_diff_within(
            H_pre_B, n_pre, H_sub_B, n_post,
        )

        np.testing.assert_allclose(D_A_acute, [[-0.2, 0.2]], atol=1e-12)
        np.testing.assert_allclose(D_A_sub, [[-0.1, 0.1]], atol=1e-12)
        np.testing.assert_allclose(D_B_acute, [[0.2, -0.2]], atol=1e-12)
        np.testing.assert_allclose(D_B_sub, [[0.1, -0.1]], atol=1e-12)

        # Sanity: a cohort-aggregate-baseline approach would have used
        # H_pre_pooled = (80+20)/2 = 50 for bin 0; that would produce
        # D_A_acute[0] = 0.60 - 0.50 = 0.10, which DOES NOT MATCH the
        # within-animal value -0.20 above. The discrepancy is the
        # exact bug Q12-A prevents.
        H_pre_cohort = (H_pre_A + H_pre_B) / 2
        D_A_acute_wrong = compute_proportion_diff_within(
            H_pre_cohort, n_pre, H_acute_A, n_post,
        )
        # Confirm the within-animal D[0] != cohort-pool D[0] under
        # asymmetric pre distributions — i.e., Q12-A actually matters.
        assert not np.allclose(D_A_acute, D_A_acute_wrong)


# ---------------------------------------------------------------------------
# split_post_dates_by_epoch
# ---------------------------------------------------------------------------


def _make_synthetic_animal_info(
    stroke_date: dt.date = dt.date(2025, 3, 10),
    acute_max: int = 7,
    subacute_max: int = 14,
    chronic_min: int = 21,
) -> AnimalInfo:
    """Construct a minimal AnimalInfo for date-splitting tests.

    Only ``stroke_date`` and ``epoch_boundaries`` are exercised here;
    the other fields are populated with reasonable defaults via
    keyword args.
    """
    eb = EpochBoundaries(
        acute_max_rel_day=acute_max,
        subacute_max_rel_day=subacute_max,
        chronic_min_rel_day=chronic_min,
    )
    return AnimalInfo(
        animal_id="PS_TEST",
        stroke_date=stroke_date,
        session_start=dt.date(2024, 1, 1),
        session_end=dt.date(2026, 12, 31),
        epoch_boundaries=eb,
        exclusions=[],
        recovery_phenotype=None,
        analysis_params={},
        sex=None,
        date_of_birth=None,
        genotype=None,
        stroke_laser_power_mW=None,
        stroke_laterality="L",
        wavesurfer_sides_match_mouse_sides=False,
        kinematics_baselines={},
    )


class TestSplitPostDatesByEpoch:
    def test_canonical_epoch_assignment(self) -> None:
        ai = _make_synthetic_animal_info(
            stroke_date=dt.date(2025, 3, 10),
            acute_max=7, subacute_max=14, chronic_min=21,
        )
        post_dates = [
            dt.date(2025, 3, 11),  # rel +1, acute
            dt.date(2025, 3, 17),  # rel +7, acute (boundary inclusive)
            dt.date(2025, 3, 18),  # rel +8, sub_acute (boundary inclusive)
            dt.date(2025, 3, 24),  # rel +14, sub_acute (boundary inclusive)
            dt.date(2025, 3, 31),  # rel +21, chronic (boundary inclusive)
            dt.date(2025, 4, 30),  # rel +51, chronic
        ]
        by_epoch = split_post_dates_by_epoch(ai, post_dates)
        assert by_epoch["acute"] == [
            dt.date(2025, 3, 11), dt.date(2025, 3, 17),
        ]
        assert by_epoch["sub_acute"] == [
            dt.date(2025, 3, 18), dt.date(2025, 3, 24),
        ]
        assert by_epoch["chronic"] == [
            dt.date(2025, 3, 31), dt.date(2025, 4, 30),
        ]

    def test_transitional_gap_drops_dates(self) -> None:
        """When chronic_min > subacute_max + 1, dates in the gap are dropped."""
        ai = _make_synthetic_animal_info(
            stroke_date=dt.date(2025, 3, 10),
            acute_max=7, subacute_max=14, chronic_min=21,
        )
        # Date at rel +17: after sub_acute (14), before chronic (21).
        gap_date = dt.date(2025, 3, 27)
        by_epoch = split_post_dates_by_epoch(ai, [gap_date])
        assert gap_date not in by_epoch["acute"]
        assert gap_date not in by_epoch["sub_acute"]
        assert gap_date not in by_epoch["chronic"]

    def test_pre_stroke_dates_ignored(self) -> None:
        """rel_day < 1 dates are silently filtered (caller's pre/post split)."""
        ai = _make_synthetic_animal_info(stroke_date=dt.date(2025, 3, 10))
        # Pass a pre-stroke date defensively; should be ignored.
        by_epoch = split_post_dates_by_epoch(ai, [dt.date(2025, 3, 5)])
        assert by_epoch["acute"] == []
        assert by_epoch["sub_acute"] == []
        assert by_epoch["chronic"] == []

    def test_returned_lists_are_sorted(self) -> None:
        ai = _make_synthetic_animal_info(stroke_date=dt.date(2025, 3, 10))
        unsorted = [
            dt.date(2025, 3, 31),  # chronic
            dt.date(2025, 3, 11),  # acute
            dt.date(2025, 3, 13),  # acute
        ]
        by_epoch = split_post_dates_by_epoch(ai, unsorted)
        assert by_epoch["acute"] == [
            dt.date(2025, 3, 11), dt.date(2025, 3, 13),
        ]

    def test_never_recovered_sentinel_chronic(self) -> None:
        """chronic_min = 9999 sentinel → no date ever assigned chronic."""
        ai = _make_synthetic_animal_info(
            stroke_date=dt.date(2025, 3, 10),
            acute_max=7, subacute_max=999, chronic_min=9999,
        )
        post_dates = [
            dt.date(2025, 3, 11),   # acute
            dt.date(2025, 4, 10),   # sub_acute (rel +31)
            dt.date(2026, 4, 10),   # sub_acute (rel +396)
        ]
        by_epoch = split_post_dates_by_epoch(ai, post_dates)
        assert by_epoch["chronic"] == []
        assert len(by_epoch["acute"]) + len(by_epoch["sub_acute"]) == 3


# ---------------------------------------------------------------------------
# Module constants sanity (lock against accidental edits)
# ---------------------------------------------------------------------------


def test_post_epochs_order() -> None:
    assert POST_EPOCHS == ("acute", "sub_acute", "chronic")


def test_sides_order() -> None:
    assert SIDES == ("L", "R")


def test_bodypart_center_modes_q12_b() -> None:
    """Q12-B Addendum #3 lock: tongue=spout_midpoint, jaw=eye_midpoint."""
    assert BODYPART_CENTER_MODES == {
        "tongue": "spout_midpoint",
        "jaw": "eye_midpoint",
    }
