"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_within_session` (Phase 8a.4)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoints_within_session import (
    within_session_change,
    within_session_learning_curve,
)
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


ENDPOINTS_PARAMS = {
    "within_session_learning_curve": {"n_bins": 5},
    "within_session_change": {"detrend_method": "linear"},
}


def _make_trials(n: int, metric_values: list[float]) -> list[TrialRecord]:
    """Build N trials carrying a synthetic per-trial metric via licks_L count hack.

    We don't actually use a derived metric here; the metric_extractor is the
    full coupling. trials just need to exist and carry their trial_idx.
    """
    assert len(metric_values) == n
    return [
        TrialRecord(
            trial_idx=i,
            reward_side="L",
            reward_idx=i * 1000,
            tone_idx=None,
            trial_type="rewarded",
            licks_L_indices_in_window=np.array([], dtype=int),
            licks_R_indices_in_window=np.array([], dtype=int),
            window_seconds=(0.0, 2.0),
            Fs=1000.0,
        )
        for i in range(n)
    ]


def _metric_from_list(values: list[float]):
    """Return a metric_extractor that maps trial_idx -> values[trial_idx]."""
    def extractor(t: TrialRecord) -> float:
        return values[t.trial_idx]
    return extractor


# ---------------------------------------------------------------------------
# within_session_learning_curve
# ---------------------------------------------------------------------------


class TestWithinSessionLearningCurve:
    def test_empty_trials(self):
        r = within_session_learning_curve(
            [], metric_extractor=lambda t: 0.0, endpoints_params=ENDPOINTS_PARAMS
        )
        agg = r.per_session_aggregate
        assert len(agg["per_bin_means"]) == 5
        assert all(math.isnan(v) for v in agg["per_bin_means"])
        assert math.isnan(agg["early_vs_late_diff"])
        assert math.isnan(agg["linear_slope_per_trial"])
        assert agg["n_trials_valid"] == 0

    def test_flat_metric_zero_slope(self):
        vals = [0.5] * 20
        trials = _make_trials(20, vals)
        r = within_session_learning_curve(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        agg = r.per_session_aggregate
        assert agg["per_bin_means"] == pytest.approx([0.5] * 5)
        assert agg["early_vs_late_diff"] == 0.0
        assert agg["linear_slope_per_trial"] == pytest.approx(0.0)

    def test_monotonic_increasing_positive_slope(self):
        # 20 trials, metric = i / 19 → 0 .. 1 inclusive.
        vals = [i / 19.0 for i in range(20)]
        trials = _make_trials(20, vals)
        r = within_session_learning_curve(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        agg = r.per_session_aggregate
        bin_means = agg["per_bin_means"]
        # Monotonic: bin means strictly increasing.
        assert all(bin_means[i] < bin_means[i + 1] for i in range(4))
        assert agg["early_vs_late_diff"] > 0.5  # last_bin - first_bin ≈ 0.842
        assert agg["linear_slope_per_trial"] == pytest.approx(1.0 / 19.0)
        assert agg["n_trials_valid"] == 20

    def test_n_bins_exceeds_n_trials(self):
        # 3 trials into 5 bins → first 3 bins populated, last 2 empty → NaN.
        params = {"within_session_learning_curve": {"n_bins": 5},
                  "within_session_change": {"detrend_method": "linear"}}
        vals = [1.0, 2.0, 3.0]
        trials = _make_trials(3, vals)
        r = within_session_learning_curve(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=params,
        )
        bin_means = r.per_session_aggregate["per_bin_means"]
        assert len(bin_means) == 5
        # np.array_split(range(3), 5) -> [[0],[1],[2],[],[]]
        assert bin_means[0] == 1.0
        assert bin_means[1] == 2.0
        assert bin_means[2] == 3.0
        assert math.isnan(bin_means[3])
        assert math.isnan(bin_means[4])

    def test_nan_metric_dropped_in_bin_mean(self):
        # Trials 0..4 have metric [1, NaN, 3, NaN, 5].
        vals = [1.0, float("nan"), 3.0, float("nan"), 5.0]
        trials = _make_trials(5, vals)
        params = {"within_session_learning_curve": {"n_bins": 1},
                  "within_session_change": {"detrend_method": "linear"}}
        r = within_session_learning_curve(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=params,
        )
        # Single bin covers everything; mean over non-NaN values = (1+3+5)/3 = 3.
        assert r.per_session_aggregate["per_bin_means"][0] == pytest.approx(3.0)
        assert r.per_session_aggregate["n_trials_valid"] == 3

    def test_all_nan_bin_yields_nan_mean(self):
        # 2 trials, both NaN, 1 bin.
        vals = [float("nan"), float("nan")]
        trials = _make_trials(2, vals)
        params = {"within_session_learning_curve": {"n_bins": 1},
                  "within_session_change": {"detrend_method": "linear"}}
        r = within_session_learning_curve(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=params,
        )
        assert math.isnan(r.per_session_aggregate["per_bin_means"][0])


# ---------------------------------------------------------------------------
# within_session_change
# ---------------------------------------------------------------------------


class TestWithinSessionChange:
    def test_empty_trials(self):
        r = within_session_change(
            [], metric_extractor=lambda t: 0.0, endpoints_params=ENDPOINTS_PARAMS
        )
        assert math.isnan(r.per_session_aggregate["slope_per_trial"])
        assert r.per_session_aggregate["n_trials_valid"] == 0
        assert r.per_session_aggregate["detrend_method"] == "linear"

    def test_flat_metric_slope_zero(self):
        vals = [0.5] * 10
        trials = _make_trials(10, vals)
        r = within_session_change(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        assert r.per_session_aggregate["slope_per_trial"] == pytest.approx(0.0)

    def test_monotonic_positive_slope(self):
        # metric = 2 * trial_idx → slope = 2 per trial.
        vals = [2.0 * i for i in range(10)]
        trials = _make_trials(10, vals)
        r = within_session_change(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        assert r.per_session_aggregate["slope_per_trial"] == pytest.approx(2.0)

    def test_single_trial_slope_nan(self):
        vals = [5.0]
        trials = _make_trials(1, vals)
        r = within_session_change(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        assert math.isnan(r.per_session_aggregate["slope_per_trial"])

    def test_decreasing_negative_slope(self):
        vals = [1.0 - 0.1 * i for i in range(10)]
        trials = _make_trials(10, vals)
        r = within_session_change(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        assert r.per_session_aggregate["slope_per_trial"] == pytest.approx(-0.1)

    def test_unsupported_method_raises(self):
        params = {"within_session_learning_curve": {"n_bins": 5},
                  "within_session_change": {"detrend_method": "theil_sen"}}
        trials = _make_trials(3, [1.0, 2.0, 3.0])
        with pytest.raises(NotImplementedError, match="theil_sen"):
            within_session_change(
                trials, metric_extractor=_metric_from_list([1.0, 2.0, 3.0]),
                endpoints_params=params,
            )

    def test_nan_metric_dropped_from_slope(self):
        # Metric: [0, NaN, 2, NaN, 4] — non-NaN at indices 0, 2, 4 with values 0, 2, 4
        # → perfect line with slope 1 per trial (in trial-ordinal space).
        vals = [0.0, float("nan"), 2.0, float("nan"), 4.0]
        trials = _make_trials(5, vals)
        r = within_session_change(
            trials, metric_extractor=_metric_from_list(vals),
            endpoints_params=ENDPOINTS_PARAMS,
        )
        assert r.per_session_aggregate["slope_per_trial"] == pytest.approx(1.0)
        assert r.per_session_aggregate["n_trials_valid"] == 3
