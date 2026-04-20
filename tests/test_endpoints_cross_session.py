"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_cross_session` (Phase 8a.5)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoints_cross_session import (
    inter_session_persistence,
)


V2_PARAMS = {"inter_session_persistence": {"lag": 1}}


class TestInterSessionPersistence:
    def test_empty_sequence(self):
        r = inter_session_persistence(
            np.array([], dtype=float), endpoints_v2_params=V2_PARAMS
        )
        assert math.isnan(r.per_session_aggregate["lag_k_autocorr"])
        assert r.per_session_aggregate["n_pairs"] == 0
        assert r.per_session_aggregate["lag_k"] == 1

    def test_shorter_than_lag(self):
        # 1-element sequence with lag=1 → no pairs possible.
        r = inter_session_persistence(np.array([5.0]), endpoints_v2_params=V2_PARAMS)
        assert math.isnan(r.per_session_aggregate["lag_k_autocorr"])
        assert r.per_session_aggregate["n_pairs"] == 0

    def test_constant_sequence_zero_variance(self):
        r = inter_session_persistence(
            np.array([3.0, 3.0, 3.0, 3.0, 3.0]), endpoints_v2_params=V2_PARAMS
        )
        # Pearson r is undefined when either side has zero variance.
        assert math.isnan(r.per_session_aggregate["lag_k_autocorr"])
        assert r.per_session_aggregate["n_pairs"] == 4

    def test_monotonic_strong_positive_autocorr(self):
        r = inter_session_persistence(
            np.arange(10, dtype=float), endpoints_v2_params=V2_PARAMS
        )
        # Monotonic sequences have very high lag-1 autocorrelation.
        assert r.per_session_aggregate["lag_k_autocorr"] > 0.95
        assert r.per_session_aggregate["n_pairs"] == 9

    def test_strictly_periodic_lag1_negative(self):
        # [1,2,1,2,1,2]: lag-1 pairs = (1,2), (2,1), (1,2), (2,1), (1,2).
        # All pair products sum to negative covariance ≈ -1.
        r = inter_session_persistence(
            np.array([1.0, 2.0, 1.0, 2.0, 1.0, 2.0]), endpoints_v2_params=V2_PARAMS
        )
        assert r.per_session_aggregate["lag_k_autocorr"] == pytest.approx(-1.0)

    def test_custom_lag(self):
        # lag=2 on [1,2,1,2,1,2,1,2]: pairs (1,1),(2,2),... → perfect + autocorr.
        params = {"inter_session_persistence": {"lag": 2}}
        seq = np.array([1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0])
        r = inter_session_persistence(seq, endpoints_v2_params=params)
        assert r.per_session_aggregate["lag_k"] == 2
        assert r.per_session_aggregate["lag_k_autocorr"] == pytest.approx(1.0)
        assert r.per_session_aggregate["n_pairs"] == 6

    def test_nan_pairs_dropped(self):
        # [1, 2, NaN, 4, 5]: lag-1 pairs (1,2), (2,NaN)DROP, (NaN,4)DROP, (4,5).
        # 2 surviving pairs → perfect positive correlation (x=[1,4], y=[2,5]).
        seq = np.array([1.0, 2.0, float("nan"), 4.0, 5.0])
        r = inter_session_persistence(seq, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate["n_pairs"] == 2
        assert r.per_session_aggregate["lag_k_autocorr"] == pytest.approx(1.0)

    def test_all_nan_pairs_dropped_nan_result(self):
        seq = np.array([float("nan"), float("nan"), float("nan")])
        r = inter_session_persistence(seq, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate["n_pairs"] == 0
        assert math.isnan(r.per_session_aggregate["lag_k_autocorr"])

    def test_rejects_non_1d(self):
        with pytest.raises(ValueError, match="1-D"):
            inter_session_persistence(
                np.array([[1, 2], [3, 4]], dtype=float),
                endpoints_v2_params=V2_PARAMS,
            )

    def test_rejects_lag_zero_or_negative(self):
        for bad_lag in (0, -1):
            params = {"inter_session_persistence": {"lag": bad_lag}}
            with pytest.raises(ValueError, match="must be >= 1"):
                inter_session_persistence(
                    np.array([1.0, 2.0, 3.0]), endpoints_v2_params=params
                )

    def test_provenance_captures_inputs(self):
        r = inter_session_persistence(
            np.array([1.0, 2.0, 3.0, 4.0]), endpoints_v2_params=V2_PARAMS
        )
        assert r.provenance["endpoint_name"] == "inter_session_persistence"
        assert r.provenance["n_trials_input"] == 4
        assert r.provenance["n_trials_used"] == 3
        assert r.provenance["config_snapshot"]["inter_session_persistence"]["lag"] == 1
