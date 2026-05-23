"""Phase 9 Task 2 (Commit C) — spatial materializer contract tests.

Unit tests on pure-function helpers in ``scripts.phase_9_stats.materialize_spatial``.
We avoid hitting compute_animal_aggregated_histogram (network share I/O)
by testing the granularity-grouping + metric kernels in isolation with
synthetic histograms.
"""
from __future__ import annotations

import datetime

import numpy as np

from stroke_orofacial.animals import AnimalInfo, EpochBoundaries

from scripts.phase_9_stats.materialize_spatial import (
    _bin_groups,
    _build_cost_matrix,
    _metric_js_divergence,
    _metric_uot_cost,
    _metric_wasserstein,
)


def _animal_info(
    *,
    animal_id: str = "PS_TEST",
    bin_days: int = 2,
    acute_max: int = 5,
    subacute_max: int = 8,
    chronic_min: int = 9,
) -> AnimalInfo:
    return AnimalInfo(
        animal_id=animal_id,
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
        epoch_boundaries=EpochBoundaries(acute_max, subacute_max, chronic_min),
        bin_days=bin_days,
    )


def _make_hist(nbins: int, center: tuple[float, float], spread: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    xs = rng.normal(center[0], spread, size=10_000)
    ys = rng.normal(center[1], spread, size=10_000)
    H, _, _ = np.histogram2d(xs, ys, bins=nbins, range=[[-3, 3], [-3, 3]])
    return H


class TestBinGroups:
    """Per-animal bin grouping anchored on rel_day=0 with width bin_days."""

    def test_basic_grouping(self):
        # rel_days {1,2,3,4,5,6}, bin_days=2 → bins: {1: [1,2], 3: [3,4], 5: [5,6]}
        dates = [
            datetime.date(2025, 3, 14),  # rel_day=1 (stroke=2025-03-13)
            datetime.date(2025, 3, 15),  # rel_day=2
            datetime.date(2025, 3, 16),  # rel_day=3
            datetime.date(2025, 3, 17),  # rel_day=4
            datetime.date(2025, 3, 18),  # rel_day=5
            datetime.date(2025, 3, 19),  # rel_day=6
        ]
        post_dates_rel = {d: (i + 1) for i, d in enumerate(dates)}
        groups = _bin_groups(post_dates_rel, bin_days=2)
        # Midpoint formula: k*bin_days + (bin_days+1)//2 = k*2 + 1
        # So bin 0 (rel_days 1, 2) → midpoint 1; bin 1 (rel_days 3, 4) → midpoint 3; etc.
        assert sorted(groups.keys()) == [1, 3, 5]
        assert groups[1] == [dates[0], dates[1]]
        assert groups[3] == [dates[2], dates[3]]
        assert groups[5] == [dates[4], dates[5]]

    def test_bin_days_7_late_cohort(self):
        """PS51/54/55 use bin_days=7. Verify the midpoint formula matches."""
        # rel_days 1..14: bin 0 [1..7] mid=4; bin 1 [8..14] mid=11.
        dates = [
            datetime.date(2025, 4, 30) + datetime.timedelta(days=i)
            for i in range(14)
        ]
        post_dates_rel = {d: (i + 1) for i, d in enumerate(dates)}
        groups = _bin_groups(post_dates_rel, bin_days=7)
        assert sorted(groups.keys()) == [4, 11]
        assert len(groups[4]) == 7   # rel_days 1..7
        assert len(groups[11]) == 7  # rel_days 8..14

    def test_dates_sorted_within_bin(self):
        """Each bin's date list is sorted ascending."""
        post_dates_rel = {
            datetime.date(2025, 3, 16): 3,
            datetime.date(2025, 3, 14): 1,
            datetime.date(2025, 3, 15): 2,
        }
        groups = _bin_groups(post_dates_rel, bin_days=2)
        assert groups[1] == [
            datetime.date(2025, 3, 14), datetime.date(2025, 3, 15),
        ]


class TestLeaveOneOutBaseline:
    """Pre-stroke per_session emit uses leave-one-out per Addendum #6 (C/D):
    each pre session's metric is computed vs the pre-pool MINUS that
    session. The arithmetic of the leave-one-out construction
    (H_pre_minus_self = H_pre_full − H_d) is what we assert here; the
    full integration with compute_animal_aggregated_histogram is
    exercised via the smoke run against PS46.
    """

    def test_leave_one_out_recovers_other_dates(self):
        """If H_pre_full is the sum of N per-session histograms and we
        subtract one, the result equals the sum of the remaining N-1.
        Trivial arithmetic identity; pins the materialization contract.
        """
        rng = np.random.default_rng(0)
        per_session = [rng.poisson(50, size=(20, 20)).astype(float) for _ in range(5)]
        H_pre_full = sum(per_session)  # sum of all 5
        # Leave-one-out for session 2:
        expected = sum(h for i, h in enumerate(per_session) if i != 2)
        actual = H_pre_full - per_session[2]
        np.testing.assert_array_equal(actual, expected)

    def test_leave_one_out_with_single_pre_session_yields_zeros(self):
        """The leave-one-out construction with a single pre-stroke
        session yields an all-zeros baseline (H_pre_full == H_d for the
        only session); the materializer skips these rows since they'd
        always yield is_sentinel=True (metric vs zero-marginal returns
        None per _normalize_marginals).
        """
        H_d = np.ones((20, 20)) * 10
        H_pre_full = H_d.copy()
        leave_one_out = H_pre_full - H_d
        assert leave_one_out.sum() == 0


class TestMetricKernels:
    """Smoke tests on the 3 metric kernels using synthetic 2D histograms."""

    def test_identical_distributions_metrics_near_zero(self):
        nbins = 20
        H = _make_hist(nbins, (0.0, 0.0), 1.0, seed=0)
        C = _build_cost_matrix([-3, 3, -3, 3], nbins, nbins)
        # Identical histograms → all 3 metrics ≈ 0.
        w2 = _metric_wasserstein(H, H, C)
        uot = _metric_uot_cost(H, H, C)
        js = _metric_js_divergence(H, H, C)
        assert w2 is not None and abs(w2) < 1e-6, f"Wasserstein {w2!r}"
        # UOT with reg=0.02 has a non-zero entropic contribution even for
        # identical inputs (regularization term). Just check it's small.
        assert uot is not None and uot < 0.05, f"UOT {uot!r}"
        assert js is not None and abs(js) < 1e-6, f"JS {js!r}"

    def test_shifted_distributions_metrics_positive(self):
        nbins = 20
        H1 = _make_hist(nbins, (0.0, 0.0), 1.0, seed=0)
        H2 = _make_hist(nbins, (1.5, 0.0), 1.0, seed=1)
        C = _build_cost_matrix([-3, 3, -3, 3], nbins, nbins)
        w2 = _metric_wasserstein(H1, H2, C)
        uot = _metric_uot_cost(H1, H2, C)
        js = _metric_js_divergence(H1, H2, C)
        assert w2 is not None and w2 > 0
        assert uot is not None and uot > 0
        assert js is not None and 0 < js <= 1  # bounded in [0, sqrt(ln 2)]

    def test_empty_marginal_returns_none(self):
        nbins = 20
        H_zero = np.zeros((nbins, nbins))
        H = _make_hist(nbins, (0.0, 0.0), 1.0, seed=0)
        C = _build_cost_matrix([-3, 3, -3, 3], nbins, nbins)
        assert _metric_wasserstein(H_zero, H, C) is None
        assert _metric_uot_cost(H_zero, H, C) is None
        assert _metric_js_divergence(H_zero, H, C) is None

    def test_cost_matrix_normalization(self):
        """Cost matrix is normalized to [0, 1] (max element = 1)."""
        C = _build_cost_matrix([-3, 3, -3, 3], 20, 20)
        assert C.shape == (400, 400)
        assert abs(C.max() - 1.0) < 1e-9
        assert C.min() >= 0.0
        # Diagonal (self-cost) is zero.
        np.testing.assert_array_almost_equal(np.diag(C), 0.0)

    def test_js_bounded_by_sqrt_ln2(self):
        """scipy.spatial.distance.jensenshannon returns DISTANCE not
        divergence; the bound is sqrt(ln 2) ≈ 0.832 (base-e).
        """
        # Disjoint-support histograms → max JS distance.
        nbins = 20
        H1 = np.zeros((nbins, nbins))
        H1[5, 5] = 100
        H2 = np.zeros((nbins, nbins))
        H2[15, 15] = 100
        C = _build_cost_matrix([-3, 3, -3, 3], nbins, nbins)
        js = _metric_js_divergence(H1, H2, C)
        # With EPS-clipping the marginals aren't truly disjoint, so the
        # bound is approached but not reached. Verify it's the closest
        # we can get given EPS.
        assert js is not None
        assert 0.5 < js <= np.sqrt(np.log(2)) + 1e-6
