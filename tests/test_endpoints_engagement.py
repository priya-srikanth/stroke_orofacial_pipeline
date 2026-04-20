"""Tests for :mod:`stroke_orofacial.spout_behavior.endpoints_engagement` (Phase 8a.6)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoints_engagement import (
    inter_trial_interval_distribution,
    reward_trial_count_per_session,
)


V2_PARAMS = {
    "engagement": {
        "compute_reward_trial_count_per_session": True,
        "compute_inter_trial_interval_distribution": True,
    }
}

FS = 1000.0


# ---------------------------------------------------------------------------
# reward_trial_count_per_session
# ---------------------------------------------------------------------------


class TestRewardTrialCountPerSession:
    def test_empty(self):
        reward_idx = {
            "Reward_L": np.array([], dtype=int),
            "Reward_R": np.array([], dtype=int),
        }
        r = reward_trial_count_per_session(reward_idx, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate == {"L": 0, "R": 0, "total": 0}
        assert r.per_trial_array is None
        assert r.per_trial_type_split is None

    def test_known_counts(self):
        reward_idx = {
            "Reward_L": np.array([0, 1000, 2000]),
            "Reward_R": np.array([500, 1500]),
        }
        r = reward_trial_count_per_session(reward_idx, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate == {"L": 3, "R": 2, "total": 5}

    def test_single_side_only(self):
        reward_idx = {
            "Reward_L": np.array([], dtype=int),
            "Reward_R": np.array([0, 500, 1000, 1500, 2000]),
        }
        r = reward_trial_count_per_session(reward_idx, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate == {"L": 0, "R": 5, "total": 5}

    def test_missing_key_treated_as_empty(self):
        # Defensive: missing "Reward_L" treated as empty per .get() semantics.
        reward_idx = {"Reward_R": np.array([0])}
        r = reward_trial_count_per_session(reward_idx, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate == {"L": 0, "R": 1, "total": 1}


# ---------------------------------------------------------------------------
# inter_trial_interval_distribution
# ---------------------------------------------------------------------------


class TestInterTrialIntervalDistribution:
    def test_all_empty(self):
        reward_idx = {
            "Reward_L": np.array([], dtype=int),
            "Reward_R": np.array([], dtype=int),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        agg = r.per_session_aggregate
        assert agg["n"] == 0
        assert math.isnan(agg["mean_s"])
        assert math.isnan(agg["median_s"])
        assert math.isnan(agg["std_s"])

    def test_single_event_per_side_no_itis(self):
        reward_idx = {
            "Reward_L": np.array([100]),
            "Reward_R": np.array([200]),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        assert r.per_session_aggregate["n"] == 0
        assert r.per_trial_type_split["L"]["n"] == 0
        assert r.per_trial_type_split["R"]["n"] == 0

    def test_known_L_side_stats(self):
        # L rewards at 100, 1000, 2500, 4000 @ Fs=1000 → diffs 900, 1500, 1500
        # → ITIs 0.9 s, 1.5 s, 1.5 s → mean 1.3, median 1.5, std sqrt(0.08) ≈ 0.2828.
        reward_idx = {
            "Reward_L": np.array([100, 1000, 2500, 4000]),
            "Reward_R": np.array([], dtype=int),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        L_stats = r.per_trial_type_split["L"]
        assert L_stats["n"] == 3
        assert L_stats["mean_s"] == pytest.approx(1.3)
        assert L_stats["median_s"] == pytest.approx(1.5)
        assert L_stats["std_s"] == pytest.approx(math.sqrt(0.08))
        # R has no events → all NaN/n=0.
        assert r.per_trial_type_split["R"]["n"] == 0

    def test_cross_side_independence(self):
        # L events produce one ITI; R events produce a different ITI; stats separate.
        reward_idx = {
            "Reward_L": np.array([0, 2000]),   # ITI = 2.0 s
            "Reward_R": np.array([1000, 1500]),  # ITI = 0.5 s
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        assert r.per_trial_type_split["L"]["mean_s"] == pytest.approx(2.0)
        assert r.per_trial_type_split["R"]["mean_s"] == pytest.approx(0.5)
        # Combined-sides: 2 ITIs = [2.0, 0.5] → mean 1.25.
        assert r.per_session_aggregate["n"] == 2
        assert r.per_session_aggregate["mean_s"] == pytest.approx(1.25)

    def test_single_iti_std_is_nan(self):
        # Only 2 events → 1 ITI → std requires n>=2 → NaN.
        reward_idx = {
            "Reward_L": np.array([0, 1000]),
            "Reward_R": np.array([], dtype=int),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        assert r.per_trial_type_split["L"]["n"] == 1
        assert math.isnan(r.per_trial_type_split["L"]["std_s"])
        assert r.per_trial_type_split["L"]["mean_s"] == pytest.approx(1.0)

    def test_unsorted_input_sorted_defensively(self):
        # Builder tolerates unsorted reward indices (Phase 2 always sorts, but
        # this primitive re-sorts to preserve the summary's correctness).
        reward_idx = {
            "Reward_L": np.array([2000, 0, 1000]),
            "Reward_R": np.array([], dtype=int),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        # After sort: diffs = [1000, 1000] → ITIs [1.0, 1.0] → mean 1.0, std 0.
        assert r.per_trial_type_split["L"]["mean_s"] == pytest.approx(1.0)
        assert r.per_trial_type_split["L"]["std_s"] == pytest.approx(0.0)

    def test_non_unit_Fs(self):
        # Fs=250 Hz: rewards at [0, 250, 750] → diffs [250, 500] samples →
        # ITIs [1.0, 2.0] s.
        reward_idx = {
            "Reward_L": np.array([0, 250, 750]),
            "Reward_R": np.array([], dtype=int),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=250.0, endpoints_v2_params=V2_PARAMS)
        assert r.per_trial_type_split["L"]["mean_s"] == pytest.approx(1.5)
        assert r.provenance["Fs"] == 250.0

    def test_provenance_reports_used_count(self):
        reward_idx = {
            "Reward_L": np.array([0, 1000, 2000]),
            "Reward_R": np.array([500]),
        }
        r = inter_trial_interval_distribution(reward_idx, Fs=FS, endpoints_v2_params=V2_PARAMS)
        # 3 L + 1 R = 4 events total. 2 L-side ITIs + 0 R-side ITIs = 2 used.
        assert r.provenance["n_trials_input"] == 4
        assert r.provenance["n_trials_used"] == 2
