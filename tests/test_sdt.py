"""Tests for SDT d' + criterion c (Phase 9.1 Q-lock 14 metrics #8/#9)."""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm

from stroke_orofacial.spout_behavior.sdt import (
    compute_session_sdt,
    first_lick_side,
)
from stroke_orofacial.spout_behavior.trial_segmentation import TrialRecord


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


class TestFirstLickSide:
    def test_left_earlier(self):
        assert first_lick_side(_trial("L", [100, 200], [150])) == "L"

    def test_right_earlier(self):
        assert first_lick_side(_trial("L", [200], [150])) == "R"

    def test_only_one_side(self):
        assert first_lick_side(_trial("R", [], [10])) == "R"
        assert first_lick_side(_trial("R", [10], [])) == "L"

    def test_no_licks(self):
        assert first_lick_side(_trial("L", [], [])) is None

    def test_exact_tie_left_wins(self):
        assert first_lick_side(_trial("L", [100], [100])) == "L"


class TestComputeSessionSDT:
    def test_clean_known_values_left_stroke(self):
        # L-stroke: ipsi=L, contra=R. contra-cued = R-cued trials.
        # H = P(first lick R | R-cued) = 8/10; FA = P(first lick R | L-cued) = 2/10.
        trials = []
        for i in range(8):
            trials.append(_trial("R", [], [10], trial_idx=i))      # R-cued, first lick R (hit)
        for i in range(2):
            trials.append(_trial("R", [10], [], trial_idx=8 + i))  # R-cued, first lick L (miss)
        for i in range(2):
            trials.append(_trial("L", [], [10], trial_idx=10 + i)) # L-cued, first lick R (FA)
        for i in range(8):
            trials.append(_trial("L", [10], [], trial_idx=12 + i)) # L-cued, first lick L (correct rej)

        res = compute_session_sdt(trials, "L")
        assert res.status == "ok"
        assert res.hit_rate == pytest.approx(0.8)
        assert res.false_alarm_rate == pytest.approx(0.2)
        expected_d = norm.ppf(0.8) - norm.ppf(0.2)
        expected_c = -(norm.ppf(0.8) + norm.ppf(0.2)) / 2
        assert res.d_prime == pytest.approx(expected_d)
        assert res.criterion_c == pytest.approx(expected_c)
        assert res.criterion_c == pytest.approx(0.0, abs=1e-9)  # symmetric -> c=0

    def test_positive_c_means_ipsi_bias(self):
        # Bias toward ipsi (L) => fewer contra (R) responses => both rates low
        # => z(H)+z(FA) < 0 => c > 0. H=0.5, FA=0.1.
        trials = []
        for i in range(5):
            trials.append(_trial("R", [], [10], trial_idx=i))       # hit
        for i in range(5):
            trials.append(_trial("R", [10], [], trial_idx=5 + i))   # miss  -> H=0.5
        trials.append(_trial("L", [], [10], trial_idx=10))          # FA
        for i in range(9):
            trials.append(_trial("L", [10], [], trial_idx=11 + i))  # corr rej -> FA=0.1
        res = compute_session_sdt(trials, "L")
        assert res.status == "ok"
        assert res.criterion_c > 0

    def test_edge_correction_extremes(self):
        # H = 1.0 (10/10), FA = 0.0 (0/10) -> corrected to 0.95 and 0.05.
        trials = [_trial("R", [], [10], trial_idx=i) for i in range(10)]
        trials += [_trial("L", [10], [], trial_idx=10 + i) for i in range(10)]
        res = compute_session_sdt(trials, "L")
        assert res.status == "ok"
        assert res.hit_rate == pytest.approx(0.95)
        assert res.false_alarm_rate == pytest.approx(0.05)
        assert res.d_prime == pytest.approx(norm.ppf(0.95) - norm.ppf(0.05))

    def test_no_response_trials_stay_in_denominator(self):
        # 10 R-cued: 5 first-lick-R, 5 no-lick. H = 5/10 = 0.5 (no-lick not a hit).
        trials = [_trial("R", [], [10], trial_idx=i) for i in range(5)]
        trials += [_trial("R", [], [], trial_idx=5 + i) for i in range(5)]
        trials += [_trial("L", [10], [], trial_idx=10 + i) for i in range(10)]
        res = compute_session_sdt(trials, "L")
        assert res.n_contra_cued == 10
        assert res.hit_rate == pytest.approx(0.5)

    def test_missing_cue_side(self):
        trials = [_trial("R", [], [10], trial_idx=i) for i in range(5)]  # no L-cued
        res = compute_session_sdt(trials, "L")
        assert res.status == "missing_cue_side"
        assert math.isnan(res.d_prime)
        assert math.isnan(res.criterion_c)

    def test_sham_guard(self):
        trials = [_trial("R", [], [10]), _trial("L", [10], [])]
        res = compute_session_sdt(trials, "sham")
        assert res.status == "sham_animal"
        assert math.isnan(res.d_prime)

    def test_right_stroke_mirror(self):
        # R-stroke: ipsi=R, contra=L. A pattern that gave H=0.8 for L-stroke
        # with R-responses should give the same d' when sides are mirrored.
        trials = []
        for i in range(8):
            trials.append(_trial("L", [10], [], trial_idx=i))       # contra-cued(L), first lick L=contra
        for i in range(2):
            trials.append(_trial("L", [], [10], trial_idx=8 + i))
        for i in range(2):
            trials.append(_trial("R", [10], [], trial_idx=10 + i))
        for i in range(8):
            trials.append(_trial("R", [], [10], trial_idx=12 + i))
        res = compute_session_sdt(trials, "R")
        assert res.status == "ok"
        assert res.hit_rate == pytest.approx(0.8)
        assert res.false_alarm_rate == pytest.approx(0.2)
