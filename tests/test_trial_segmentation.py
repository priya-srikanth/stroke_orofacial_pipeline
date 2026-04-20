"""Tests for :mod:`stroke_orofacial.spout_behavior.trial_segmentation` (Phase 8a.3)."""
from __future__ import annotations

import numpy as np

from stroke_orofacial.spout_behavior.trial_segmentation import (
    build_per_trial_records,
)


def _empty_licks_and_rewards(Fs: float = 1000.0) -> dict[str, np.ndarray]:
    return {
        "Lick_L": np.array([], dtype=int),
        "Lick_R": np.array([], dtype=int),
        "Reward_L": np.array([], dtype=int),
        "Reward_R": np.array([], dtype=int),
        "Fs": Fs,
    }


class TestBuildPerTrialRecords:
    def test_empty_rewards_returns_empty_list(self):
        out = build_per_trial_records(
            _empty_licks_and_rewards(), window_seconds=(0.0, 2.0)
        )
        assert out == []

    def test_single_L_reward_trial_with_licks(self):
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([10_000])
        # Licks in window [10000, 12000): one L at 10500, one R at 11000.
        lr["Lick_L"] = np.array([10_500])
        lr["Lick_R"] = np.array([11_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        r = out[0]
        assert r.trial_idx == 0
        assert r.reward_side == "L"
        assert r.reward_idx == 10_000
        assert r.tone_idx is None
        assert r.trial_type == "rewarded"
        np.testing.assert_array_equal(r.licks_L_indices_in_window, [10_500])
        np.testing.assert_array_equal(r.licks_R_indices_in_window, [11_000])
        assert r.Fs == 1000.0
        assert r.window_seconds == (0.0, 2.0)

    def test_window_is_right_exclusive(self):
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([0])
        # window (0, 2.0) @ Fs=1000 → [0, 2000). Lick at 2000 falls outside.
        lr["Lick_L"] = np.array([1_999, 2_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_999])

    def test_window_is_left_inclusive(self):
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([1_000])
        # window [1000, 3000). Lick at exactly 1000 (offset 0) included.
        lr["Lick_L"] = np.array([1_000, 999])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_000])

    def test_multiple_trials_sorted_by_reward_idx(self):
        # Interleave L and R rewards out of order — builder must sort.
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([5_000, 15_000])
        lr["Reward_R"] = np.array([10_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 3
        assert [r.trial_idx for r in out] == [0, 1, 2]
        assert [r.reward_idx for r in out] == [5_000, 10_000, 15_000]
        assert [r.reward_side for r in out] == ["L", "R", "L"]

    def test_per_trial_lick_slicing_independence(self):
        # Licks far from any reward window excluded; within-window licks included.
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([0, 10_000])
        lr["Lick_L"] = np.array([500, 5_000, 10_500, 20_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 2
        # Trial 0 window [0, 2000): only 500.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [500])
        # Trial 1 window [10000, 12000): only 10500.
        np.testing.assert_array_equal(out[1].licks_L_indices_in_window, [10_500])

    def test_negative_window_start_reaches_pre_reward(self):
        # window_seconds[0] < 0 → look backward from reward.
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([5_000])
        lr["Lick_L"] = np.array([4_500, 5_500])
        out = build_per_trial_records(lr, window_seconds=(-1.0, 2.0))
        # window: [4000, 7000) → both licks included.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [4_500, 5_500])

    def test_non_unit_Fs(self):
        lr = _empty_licks_and_rewards(Fs=250.0)
        lr["Reward_L"] = np.array([1_000])
        lr["Lick_L"] = np.array([1_100])  # 100 samples post-reward @ Fs=250 = 0.4 s
        out = build_per_trial_records(lr, window_seconds=(0.0, 1.0))
        # window @ Fs=250 = [1000, 1250). 1100 in range.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_100])
        assert out[0].Fs == 250.0


class TestTrialRecordIsFrozen:
    def test_cannot_mutate_fields(self):
        lr = _empty_licks_and_rewards()
        lr["Reward_L"] = np.array([0])
        r = build_per_trial_records(lr, window_seconds=(0.0, 1.0))[0]
        import dataclasses
        # Frozen dataclass: attribute assignment raises FrozenInstanceError.
        try:
            r.trial_idx = 99  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            return
        raise AssertionError("Expected FrozenInstanceError on frozen dataclass")
