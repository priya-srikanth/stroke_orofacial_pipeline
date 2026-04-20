"""Tests for :mod:`stroke_orofacial.spout_behavior.lick_bouts` (Phase 8a.2)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.lick_bouts import LickBout, find_lick_bouts


# Default synthetic-fixture parameters. Fs=1000 Hz → 1 sample == 1 ms, so
# max_ili_ms == max_ili_samples. Keeps hand-computed expected values obvious.
DEFAULT_PARAMS = {"max_ili_ms": 300.0, "min_bout_licks": 2}
FS = 1000.0


class TestEmptyAndDegenerate:
    def test_empty_input_returns_empty_list(self):
        result = find_lick_bouts(np.array([], dtype=int), FS, DEFAULT_PARAMS)
        assert result == []

    def test_single_lick_below_min_returns_empty(self):
        # min_bout_licks=2 default; single lick can never form a bout.
        result = find_lick_bouts(np.array([500]), FS, DEFAULT_PARAMS)
        assert result == []

    def test_rejects_non_1d_input(self):
        with pytest.raises(ValueError, match="1-D"):
            find_lick_bouts(np.array([[0, 1], [2, 3]]), FS, DEFAULT_PARAMS)


class TestTwoLickBouts:
    def test_two_licks_within_max_ili_one_bout(self):
        # Licks 100 ms apart; below the 300 ms threshold → one bout of 2.
        result = find_lick_bouts(np.array([0, 100]), FS, DEFAULT_PARAMS)
        assert len(result) == 1
        bout = result[0]
        assert bout.start_idx == 0
        assert bout.end_idx == 100
        assert bout.n_licks == 2
        # Span 100 samples / (2-1 = 1 intervals) / 1000 Hz = 0.1 s.
        assert math.isclose(bout.mean_ili_s, 0.1)

    def test_two_licks_exceeding_max_ili_no_bout(self):
        # Gap 400 ms exceeds 300 ms threshold → split; each side has n=1 < 2.
        result = find_lick_bouts(np.array([0, 400]), FS, DEFAULT_PARAMS)
        assert result == []

    def test_gap_exactly_at_threshold_boundary_inclusive(self):
        # Documented inclusive semantics: ILI == max_ili_samples stays in bout.
        # max_ili_ms=300 @ Fs=1000 → max_ili_samples = 300 (exact).
        result = find_lick_bouts(np.array([0, 300]), FS, DEFAULT_PARAMS)
        assert len(result) == 1
        assert result[0].n_licks == 2

    def test_gap_one_sample_over_threshold_excluded(self):
        # Boundary check on the other side: 301 ms > 300 ms threshold → split.
        result = find_lick_bouts(np.array([0, 301]), FS, DEFAULT_PARAMS)
        assert result == []


class TestMultiBoutSequences:
    def test_multi_bout_sequence_with_gaps(self):
        # Two runs of 3 licks each, separated by an 800 ms gap.
        # Intra-bout ILI 100 ms stays below threshold; gap above splits.
        licks = np.array([0, 100, 200, 1000, 1100, 1200])
        result = find_lick_bouts(licks, FS, DEFAULT_PARAMS)
        assert len(result) == 2
        assert result[0] == LickBout(
            start_idx=0, end_idx=200, n_licks=3, mean_ili_s=0.1
        )
        assert result[1] == LickBout(
            start_idx=1000, end_idx=1200, n_licks=3, mean_ili_s=0.1
        )

    def test_single_lick_singleton_between_bouts_dropped(self):
        # A lone lick in the middle (too big a gap on each side) is dropped;
        # the surviving bouts on either side must still both be reported.
        licks = np.array([0, 100, 200, 2000, 5000, 5100, 5200])
        result = find_lick_bouts(licks, FS, DEFAULT_PARAMS)
        assert len(result) == 2
        assert [b.n_licks for b in result] == [3, 3]
        assert [b.start_idx for b in result] == [0, 5000]

    def test_bout_with_three_plus_licks_reports_correct_mean_ili(self):
        # 4 licks at 0, 50, 200, 250 → 3 intervals of 50, 150, 50.
        # Mean via endpoint-span formula: (250 - 0) / 3 = 83.33 samples → 0.0833 s.
        licks = np.array([0, 50, 200, 250])
        result = find_lick_bouts(licks, FS, DEFAULT_PARAMS)
        assert len(result) == 1
        assert result[0].n_licks == 4
        assert math.isclose(result[0].mean_ili_s, 250 / 3 / FS)


class TestMinBoutLicksParam:
    def test_min_bout_licks_three_drops_two_lick_bouts(self):
        params = {"max_ili_ms": 300.0, "min_bout_licks": 3}
        # First run has 3 licks (kept); second run has 2 licks (dropped).
        licks = np.array([0, 100, 200, 1000, 1100])
        result = find_lick_bouts(licks, FS, params)
        assert len(result) == 1
        assert result[0].n_licks == 3

    def test_min_bout_licks_one_admits_singletons_with_nan_ili(self):
        # Explicit guard-path test: n_licks=1 yields NaN mean_ili_s (documented).
        params = {"max_ili_ms": 300.0, "min_bout_licks": 1}
        result = find_lick_bouts(np.array([500]), FS, params)
        assert len(result) == 1
        assert result[0].n_licks == 1
        assert math.isnan(result[0].mean_ili_s)


class TestFsScaling:
    def test_non_unit_sample_rate_scales_gap_threshold(self):
        # At Fs=250 Hz, max_ili_ms=300 → max_ili_samples = round(300*250/1000) = 75.
        # Two licks 80 samples apart: 80 > 75 → no bout.
        params = {"max_ili_ms": 300.0, "min_bout_licks": 2}
        result = find_lick_bouts(np.array([0, 80]), Fs=250.0, params=params)
        assert result == []
        # Two licks 60 samples apart: 60 < 75 → one bout.
        result = find_lick_bouts(np.array([0, 60]), Fs=250.0, params=params)
        assert len(result) == 1
        # Mean ILI = 60 samples / 1 interval / 250 Hz = 0.24 s.
        assert math.isclose(result[0].mean_ili_s, 0.24)
