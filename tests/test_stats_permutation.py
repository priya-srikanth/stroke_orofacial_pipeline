"""Tests for stroke_orofacial.stats.permutation.

Synthetic-data tests with known ground-truth shifts. Permutation tests
use seeded RNG so results are reproducible.
"""
from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.stats.permutation import (
    bootstrap_ci,
    mean_difference,
    paired_permutation_null,
    permutation_p_value,
    unpaired_permutation_null,
)


class TestMeanDifference:

    def test_basic(self):
        assert mean_difference(np.array([2.0, 4.0]), np.array([1.0, 1.0])) == pytest.approx(2.0)


class TestPairedPermutationNull:

    def test_returns_correct_length(self):
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1, 20)
        y = rng.normal(0, 1, 20)
        null = paired_permutation_null(x, y, n_perm=500, random_state=42)
        assert null.shape == (500,)

    def test_null_centered_near_zero_under_exchangeability(self):
        """If x and y come from the same distribution, the null of
        mean(x) - mean(y) is centered near 0."""
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1, 50)
        y = rng.normal(0, 1, 50)
        null = paired_permutation_null(x, y, n_perm=2000, random_state=1)
        assert abs(np.mean(null)) < 0.2

    def test_unequal_length_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            paired_permutation_null(np.array([1.0]), np.array([1.0, 2.0]))

    def test_zero_n_perm_raises(self):
        with pytest.raises(ValueError, match="n_perm"):
            paired_permutation_null(np.array([1.0]), np.array([2.0]), n_perm=0)

    def test_reproducible_with_seed(self):
        x = np.arange(10, dtype=float)
        y = np.arange(10, dtype=float) + 1
        null1 = paired_permutation_null(x, y, n_perm=100, random_state=42)
        null2 = paired_permutation_null(x, y, n_perm=100, random_state=42)
        np.testing.assert_allclose(null1, null2)

    def test_detects_known_shift(self):
        """y = x + 3 → observed mean_diff = -3; null under exchangeability
        is centered near 0; observed should be very extreme."""
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.5, 30)
        y = x + 3
        observed = mean_difference(x, y)  # = -3
        null = paired_permutation_null(x, y, n_perm=2000, random_state=1)
        p = permutation_p_value(observed, null, alternative="two-sided")
        assert p < 0.005  # strong rejection


class TestUnpairedPermutationNull:

    def test_returns_correct_length(self):
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1, 15)
        y = rng.normal(0, 1, 25)
        null = unpaired_permutation_null(x, y, n_perm=500, random_state=42)
        assert null.shape == (500,)

    def test_null_centered_near_zero_under_exchangeability(self):
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1, 50)
        y = rng.normal(0, 1, 50)
        null = unpaired_permutation_null(x, y, n_perm=2000, random_state=2)
        assert abs(np.mean(null)) < 0.2

    def test_handles_unequal_sample_sizes(self):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        null = unpaired_permutation_null(x, y, n_perm=200, random_state=0)
        assert null.shape == (200,)

    def test_detects_shifted_groups(self):
        rng = np.random.default_rng(0)
        x = rng.normal(0, 0.5, 40)
        y = rng.normal(5.0, 0.5, 40)
        observed = mean_difference(x, y)  # ≈ -5
        null = unpaired_permutation_null(x, y, n_perm=2000, random_state=3)
        p = permutation_p_value(observed, null)
        assert p < 0.005


class TestPermutationPValue:

    def test_two_sided_basic(self):
        null = np.array([0.0, 0.0, 0.0, 1.0, -1.0])
        # observed = 2: more extreme than all 5 → p = (0 + 1) / 6 = 1/6
        p = permutation_p_value(2.0, null, alternative="two-sided")
        assert p == pytest.approx(1 / 6)

    def test_one_sided_greater(self):
        null = np.array([-1.0, 0.0, 1.0, 2.0, 3.0])
        # observed = 2.5: 1 value (3) >= 2.5 → p = (1 + 1) / 6 = 2/6
        p = permutation_p_value(2.5, null, alternative="greater")
        assert p == pytest.approx(2 / 6)

    def test_one_sided_less(self):
        null = np.array([-3.0, -2.0, -1.0, 0.0, 1.0])
        # observed = -2.5: 1 value (-3) <= -2.5 → p = (1 + 1) / 6 = 2/6
        p = permutation_p_value(-2.5, null, alternative="less")
        assert p == pytest.approx(2 / 6)

    def test_p_value_strictly_positive(self):
        """Add-1 convention: no observed value yields p = 0."""
        null = np.array([0.0, 0.0, 0.0])
        p = permutation_p_value(100.0, null, alternative="two-sided")
        assert p > 0
        assert p == pytest.approx(1 / 4)

    def test_empty_null_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            permutation_p_value(0.0, np.array([]))

    def test_invalid_alternative_raises(self):
        with pytest.raises(ValueError, match="alternative"):
            permutation_p_value(0.0, np.array([0.0]), alternative="bogus")


class TestBootstrapCI:

    def test_mean_ci_contains_true_value(self):
        rng = np.random.default_rng(0)
        x = rng.normal(loc=5.0, scale=1.0, size=200)
        lo, hi = bootstrap_ci(x, ci=0.95, n_boot=2000, random_state=1)
        assert lo < 5.0 < hi

    def test_median_ci_via_custom_statistic(self):
        rng = np.random.default_rng(0)
        x = rng.normal(0.0, 1.0, 100)
        lo, hi = bootstrap_ci(
            x, statistic=lambda a: float(np.median(a)),
            ci=0.95, n_boot=2000, random_state=2,
        )
        assert lo < 0.0 < hi

    def test_ci_width_narrows_with_more_data(self):
        rng = np.random.default_rng(0)
        small_x = rng.normal(0, 1, 20)
        large_x = rng.normal(0, 1, 500)
        lo_s, hi_s = bootstrap_ci(small_x, n_boot=1000, random_state=3)
        lo_l, hi_l = bootstrap_ci(large_x, n_boot=1000, random_state=3)
        assert (hi_l - lo_l) < (hi_s - lo_s)

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            bootstrap_ci(np.array([]))

    def test_invalid_ci_raises(self):
        with pytest.raises(ValueError, match="ci"):
            bootstrap_ci(np.array([1.0, 2.0]), ci=0.0)
        with pytest.raises(ValueError, match="ci"):
            bootstrap_ci(np.array([1.0, 2.0]), ci=1.0)

    def test_percentile_method(self):
        """Percentile (less accurate) is a valid alternative method."""
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1, 100)
        lo, hi = bootstrap_ci(
            x, ci=0.95, n_boot=500, random_state=4, method="percentile",
        )
        assert lo < hi
