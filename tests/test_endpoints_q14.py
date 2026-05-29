"""Tests for Q-lock 14 per-session endpoints #6 + #7."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.endpoints_q14 import (
    accuracy_difference_index_per_session,
    licks_per_bout_per_session,
)
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord

_BOUT_PARAMS = {"max_ili_ms": 300, "min_bout_licks": 2}


def _trial(tone_side, licks_L, licks_R, *, trial_idx=0, Fs=1000.0):
    return TrialRecord(
        trial_idx=trial_idx,
        tone_side=tone_side,
        tone_idx=0,
        reward_idx=None,
        trial_type="unrewarded",
        licks_L_indices_in_window=np.asarray(licks_L, dtype=np.int64),
        licks_R_indices_in_window=np.asarray(licks_R, dtype=np.int64),
        window_seconds=(0.0, 2.5),
        Fs=Fs,
    )


class TestAccuracyDifferenceIndex:
    def test_known_values(self):
        # 2 L-cued trials: correct(L)=3+2=5, incorrect(R)=1+0=1 -> (5-1)/6
        trials = [
            _trial("L", [1, 2, 3], [4], trial_idx=0),
            _trial("L", [5, 6], [], trial_idx=1),
        ]
        res = accuracy_difference_index_per_session(trials, endpoints_params={})
        assert res.per_session_aggregate[
            "accuracy_difference_index_on_L_trials"
        ] == pytest.approx((5 - 1) / 6)
        # no R-cued trials -> NaN
        assert math.isnan(
            res.per_session_aggregate["accuracy_difference_index_on_R_trials"]
        )

    def test_bounds_and_signs(self):
        # all correct -> +1 ; all incorrect -> -1
        all_correct = [_trial("R", [], [1, 2, 3])]
        all_incorrect = [_trial("R", [1, 2, 3], [])]
        assert accuracy_difference_index_per_session(
            all_correct, endpoints_params={}
        ).per_session_aggregate["accuracy_difference_index_on_R_trials"] == 1.0
        assert accuracy_difference_index_per_session(
            all_incorrect, endpoints_params={}
        ).per_session_aggregate["accuracy_difference_index_on_R_trials"] == -1.0

    def test_balanced_is_zero_not_nan(self):
        trials = [_trial("L", [1, 2], [3, 4])]
        v = accuracy_difference_index_per_session(
            trials, endpoints_params={}
        ).per_session_aggregate["accuracy_difference_index_on_L_trials"]
        assert v == 0.0

    def test_no_licks_is_nan(self):
        trials = [_trial("L", [], [])]
        v = accuracy_difference_index_per_session(
            trials, endpoints_params={}
        ).per_session_aggregate["accuracy_difference_index_on_L_trials"]
        assert math.isnan(v)

    def test_provenance(self):
        res = accuracy_difference_index_per_session(
            [_trial("L", [1], [])], endpoints_params={"x": 1}
        )
        assert res.provenance["endpoint_name"] == "accuracy_difference_index_per_session"
        assert res.per_trial_type_split["L"]["n_correct"] == 1


class TestLicksPerBout:
    def test_single_bout_per_trial(self):
        # Fs=1000 -> 300 ms = 300 samples. ILIs of 100 stay within bout.
        # Two L-cued trials, each a contiguous bout of 3 licks -> sizes [3,3].
        trials = [
            _trial("L", [100, 200, 300], [], trial_idx=0),
            _trial("L", [100, 200, 300], [], trial_idx=1),
        ]
        res = licks_per_bout_per_session(trials, endpoints_params=_BOUT_PARAMS)
        assert res.per_session_aggregate[
            "median_licks_per_bout_on_L_trials"
        ] == pytest.approx(3.0)
        assert res.per_trial_type_split["L"]["n_bouts"] == 2
        assert math.isnan(
            res.per_session_aggregate["median_licks_per_bout_on_R_trials"]
        )

    def test_gap_splits_and_drops_singletons(self):
        # ILI 400 ms > 300 ms threshold -> splits into two size-1 runs -> both
        # dropped (< min_bout_licks=2) -> no bouts.
        trials = [_trial("R", [], [100, 500], trial_idx=0)]
        res = licks_per_bout_per_session(trials, endpoints_params=_BOUT_PARAMS)
        assert res.per_trial_type_split["R"]["n_bouts"] == 0
        assert math.isnan(
            res.per_session_aggregate["median_licks_per_bout_on_R_trials"]
        )

    def test_merges_both_spouts_within_trial(self):
        # L and R licks interleaved within 300-sample ILI -> one merged bout of 4.
        trials = [_trial("L", [100, 300], [200, 400], trial_idx=0)]
        res = licks_per_bout_per_session(trials, endpoints_params=_BOUT_PARAMS)
        assert res.per_session_aggregate[
            "median_licks_per_bout_on_L_trials"
        ] == pytest.approx(4.0)

    def test_median_across_bouts(self):
        # three L-cued bouts of sizes 2, 3, 5 -> median 3.
        trials = [
            _trial("L", [100, 200], [], trial_idx=0),
            _trial("L", [100, 200, 300], [], trial_idx=1),
            _trial("L", [100, 200, 300, 400, 500], [], trial_idx=2),
        ]
        res = licks_per_bout_per_session(trials, endpoints_params=_BOUT_PARAMS)
        assert res.per_session_aggregate[
            "median_licks_per_bout_on_L_trials"
        ] == pytest.approx(3.0)
