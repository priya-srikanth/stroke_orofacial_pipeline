"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_per_trial` (Phase 8a.3)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoints_per_trial import (
    directional_lick_accuracy_per_session,
    first_lick_latency_per_trial,
    latency_variability_per_session,
    switch_cost_per_session,
)
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


# Minimal endpoints params stub for the two endpoints that actually key into it.
ENDPOINTS_PARAMS: dict = {
    "switch_cost": {"same_side_baseline_definition": "immediately_prior_trial"},
}

FS = 1000.0


def _trial(
    trial_idx: int,
    side: str,
    reward_idx: int = 0,
    licks_L: list[int] | None = None,
    licks_R: list[int] | None = None,
) -> TrialRecord:
    """Build a synthetic TrialRecord; licks default empty."""
    return TrialRecord(
        trial_idx=trial_idx,
        reward_side=side,  # type: ignore[arg-type]
        reward_idx=reward_idx,
        tone_idx=None,
        trial_type="rewarded",
        licks_L_indices_in_window=np.asarray(licks_L or [], dtype=int),
        licks_R_indices_in_window=np.asarray(licks_R or [], dtype=int),
        window_seconds=(0.0, 2.0),
        Fs=FS,
    )


# ---------------------------------------------------------------------------
# first_lick_latency_per_trial
# ---------------------------------------------------------------------------


class TestFirstLickLatencyPerTrial:
    def test_empty_trials(self):
        r = first_lick_latency_per_trial([], endpoints_params=ENDPOINTS_PARAMS)
        assert r.per_trial_array.shape == (0,)
        assert math.isnan(r.per_session_aggregate["mean"])
        assert r.per_session_aggregate["n"] == 0
        assert r.provenance["n_trials_input"] == 0
        assert r.provenance["n_trials_used"] == 0

    def test_single_L_trial_with_correct_lick(self):
        # Reward at 0; first L lick at sample 200 → latency = 0.2 s @ Fs=1000.
        trials = [_trial(0, "L", reward_idx=0, licks_L=[200, 500])]
        r = first_lick_latency_per_trial(trials, endpoints_params=ENDPOINTS_PARAMS)
        np.testing.assert_allclose(r.per_trial_array, [0.2])
        assert math.isclose(r.per_session_aggregate["mean"], 0.2)
        assert r.per_session_aggregate["std"] == 0.0
        assert r.per_session_aggregate["n"] == 1
        assert r.per_trial_type_split["L"]["mean"] == pytest.approx(0.2)
        assert r.per_trial_type_split["R"]["n"] == 0

    def test_no_correct_lick_in_window_yields_nan(self):
        # L reward trial, but only R lick present → no correct-side lick.
        trials = [_trial(0, "L", reward_idx=0, licks_R=[100])]
        r = first_lick_latency_per_trial(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert math.isnan(r.per_trial_array[0])
        assert r.per_session_aggregate["n"] == 0

    def test_multi_trial_per_side_split(self):
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),      # 0.1 s
            _trial(1, "L", reward_idx=1_000, licks_L=[1_300]),  # 0.3 s
            _trial(2, "R", reward_idx=5_000, licks_R=[5_500]),  # 0.5 s
        ]
        r = first_lick_latency_per_trial(trials, endpoints_params=ENDPOINTS_PARAMS)
        np.testing.assert_allclose(r.per_trial_array, [0.1, 0.3, 0.5])
        assert r.per_trial_type_split["L"]["mean"] == pytest.approx(0.2)
        assert r.per_trial_type_split["L"]["n"] == 2
        assert r.per_trial_type_split["R"]["mean"] == pytest.approx(0.5)
        assert r.per_trial_type_split["R"]["n"] == 1


# ---------------------------------------------------------------------------
# directional_lick_accuracy_per_session
# ---------------------------------------------------------------------------


class TestDirectionalLickAccuracy:
    def test_empty_trials(self):
        r = directional_lick_accuracy_per_session([], endpoints_params=ENDPOINTS_PARAMS)
        assert math.isnan(r.per_session_aggregate["fraction_correct_on_L_trials"])
        assert math.isnan(r.per_session_aggregate["fraction_correct_on_R_trials"])
        assert r.per_trial_type_split["L"]["n_trials"] == 0
        assert r.per_trial_type_split["R"]["n_trials"] == 0

    def test_all_correct(self):
        # 2 L trials with more-correct-than-incorrect licks; 2 R trials same.
        trials = [
            _trial(0, "L", licks_L=[100, 200], licks_R=[]),
            _trial(1, "L", licks_L=[150], licks_R=[]),
            _trial(2, "R", licks_L=[], licks_R=[100, 200]),
            _trial(3, "R", licks_L=[], licks_R=[150]),
        ]
        r = directional_lick_accuracy_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert r.per_session_aggregate["fraction_correct_on_L_trials"] == 1.0
        assert r.per_session_aggregate["fraction_correct_on_R_trials"] == 1.0
        assert r.per_trial_type_split["L"]["counts_correct"] == [2, 1]
        assert r.per_trial_type_split["L"]["counts_incorrect"] == [0, 0]

    def test_all_incorrect(self):
        # L trials with only R-side licks → all incorrect (correct_count == 0).
        trials = [
            _trial(0, "L", licks_L=[], licks_R=[100]),
            _trial(1, "L", licks_L=[], licks_R=[200]),
        ]
        r = directional_lick_accuracy_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert r.per_session_aggregate["fraction_correct_on_L_trials"] == 0.0
        assert math.isnan(r.per_session_aggregate["fraction_correct_on_R_trials"])
        assert r.per_trial_type_split["L"]["counts_correct"] == [0, 0]
        assert r.per_trial_type_split["L"]["counts_incorrect"] == [1, 1]

    def test_mixed(self):
        trials = [
            _trial(0, "L", licks_L=[100, 200], licks_R=[]),    # correct
            _trial(1, "L", licks_L=[], licks_R=[100]),         # incorrect
            _trial(2, "L", licks_L=[100], licks_R=[100]),      # correct (1>=1, 1>=1)
            _trial(3, "L", licks_L=[], licks_R=[]),             # incorrect (correct=0)
        ]
        r = directional_lick_accuracy_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        # 2 of 4 correct → 0.5.
        assert r.per_session_aggregate["fraction_correct_on_L_trials"] == 0.5

    def test_single_side_only_other_side_is_nan(self):
        trials = [_trial(0, "R", licks_R=[100])]
        r = directional_lick_accuracy_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert math.isnan(r.per_session_aggregate["fraction_correct_on_L_trials"])
        assert r.per_session_aggregate["fraction_correct_on_R_trials"] == 1.0


# ---------------------------------------------------------------------------
# switch_cost_per_session
# ---------------------------------------------------------------------------


class TestSwitchCost:
    def test_empty_trials(self):
        r = switch_cost_per_session([], endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert math.isnan(agg["switch_cost_s"])
        assert agg["n_same_side_trials"] == 0
        assert agg["n_switch_trials"] == 0

    def test_single_trial_no_prior(self):
        trials = [_trial(0, "L", licks_L=[100])]
        r = switch_cost_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert math.isnan(r.per_session_aggregate["switch_cost_s"])
        assert r.per_session_aggregate["n_same_side_trials"] == 0

    def test_all_same_side_trials(self):
        # LLL: trials 1, 2 are same-side; no switches.
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),       # lat 0.1
            _trial(1, "L", reward_idx=1_000, licks_L=[1_200]), # lat 0.2
            _trial(2, "L", reward_idx=2_000, licks_L=[2_300]), # lat 0.3
        ]
        r = switch_cost_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        # Both trial 1 and 2 are same-side → mean_same = mean(0.2, 0.3) = 0.25.
        assert agg["mean_latency_same_side_s"] == pytest.approx(0.25)
        assert math.isnan(agg["mean_latency_switch_s"])
        assert math.isnan(agg["switch_cost_s"])
        assert agg["n_same_side_trials"] == 2
        assert agg["n_switch_trials"] == 0

    def test_all_alternating_trials(self):
        # LRLR: every non-first trial is a switch.
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),
            _trial(1, "R", reward_idx=1_000, licks_R=[1_200]),
            _trial(2, "L", reward_idx=2_000, licks_L=[2_300]),
            _trial(3, "R", reward_idx=3_000, licks_R=[3_400]),
        ]
        r = switch_cost_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert agg["n_switch_trials"] == 3
        assert agg["n_same_side_trials"] == 0
        assert math.isnan(agg["mean_latency_same_side_s"])

    def test_mixed_contrast_hand_computed(self):
        # Sequence: LL RL (trial1 same-side lat 0.2; trial2 switch lat 0.3;
        # trial3 switch lat 0.4). Cost = mean([0.3, 0.4]) - mean([0.2]) = 0.15.
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),
            _trial(1, "L", reward_idx=1_000, licks_L=[1_200]),
            _trial(2, "R", reward_idx=2_000, licks_R=[2_300]),
            _trial(3, "L", reward_idx=3_000, licks_L=[3_400]),
        ]
        r = switch_cost_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert agg["mean_latency_same_side_s"] == pytest.approx(0.2)
        assert agg["mean_latency_switch_s"] == pytest.approx(0.35)
        assert agg["switch_cost_s"] == pytest.approx(0.15)

    def test_nan_latency_excluded(self):
        # Trial 1 (switch) has no correct-side lick → NaN latency → excluded.
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),
            _trial(1, "R", reward_idx=1_000, licks_R=[]),  # NaN
            _trial(2, "R", reward_idx=2_000, licks_R=[2_300]),
        ]
        r = switch_cost_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        # Trial 1 (switch) excluded; trial 2 (same-side-continuation) kept.
        assert r.per_session_aggregate["n_same_side_trials"] == 1
        assert r.per_session_aggregate["n_switch_trials"] == 0

    def test_unsupported_baseline_raises(self):
        params = {"switch_cost": {"same_side_baseline_definition": "n_back_average"}}
        with pytest.raises(NotImplementedError, match="n_back_average"):
            switch_cost_per_session([], endpoints_params=params)


# ---------------------------------------------------------------------------
# latency_variability_per_session
# ---------------------------------------------------------------------------


class TestLatencyVariability:
    def test_empty_trials(self):
        r = latency_variability_per_session([], endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert agg["n"] == 0
        assert math.isnan(agg["std_s"])
        assert math.isnan(agg["cv"])
        assert math.isnan(agg["iqr_s"])

    def test_constant_latencies(self):
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[500]),
            _trial(1, "L", reward_idx=1_000, licks_L=[1_500]),
            _trial(2, "L", reward_idx=2_000, licks_L=[2_500]),
        ]
        # All latencies 0.5 → std 0, CV 0, IQR 0.
        r = latency_variability_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert agg["std_s"] == 0.0
        assert agg["cv"] == 0.0
        assert agg["iqr_s"] == 0.0
        assert agg["n"] == 3

    def test_known_latencies_hand_computed(self):
        # Latencies [0.1, 0.2, 0.3, 0.4, 0.5] → mean 0.3, std sqrt(0.02) ≈ 0.1414,
        # CV ≈ 0.4714, IQR (Q75-Q25) = 0.4-0.2 = 0.2.
        trials = [
            _trial(i, "L", reward_idx=i * 1_000, licks_L=[i * 1_000 + (i + 1) * 100])
            for i in range(5)
        ]
        r = latency_variability_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        assert agg["std_s"] == pytest.approx(np.sqrt(0.02))
        assert agg["cv"] == pytest.approx(np.sqrt(0.02) / 0.3)
        assert agg["iqr_s"] == pytest.approx(0.2)
        assert agg["n"] == 5

    def test_single_trial_iqr_is_nan(self):
        trials = [_trial(0, "L", reward_idx=0, licks_L=[100])]
        r = latency_variability_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        agg = r.per_session_aggregate
        # n=1 → std=0, CV defined (std/mean=0), IQR=NaN (n<2).
        assert agg["n"] == 1
        assert agg["std_s"] == 0.0
        assert agg["cv"] == 0.0
        assert math.isnan(agg["iqr_s"])

    def test_per_side_split_counts(self):
        trials = [
            _trial(0, "L", reward_idx=0, licks_L=[100]),
            _trial(1, "R", reward_idx=1_000, licks_R=[1_200]),
            _trial(2, "R", reward_idx=2_000, licks_R=[2_400]),
        ]
        r = latency_variability_per_session(trials, endpoints_params=ENDPOINTS_PARAMS)
        assert r.per_trial_type_split["L"]["n"] == 1
        assert r.per_trial_type_split["R"]["n"] == 2
