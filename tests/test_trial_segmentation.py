"""Tests for :mod:`stroke_orofacial.spout_behavior.trial_segmentation` (Phase 8a.3).

Phase 8a.10.1 Q-A.β + Q-B.α (locked 2026-05-14): TrialRecord rewritten
to the two-anchor model. ``tone_idx: int`` is the always-present trial
anchor (was None placeholder); ``reward_idx: int | None`` is the
optional paired reward-delivery sample (was required int). Side field
renamed ``reward_side → tone_side``. ``build_per_trial_records`` now
walks Tone_L/Tone_R events as the anchor and pairs Reward_L/Reward_R
within a 50ms ε-window (per the synchronous-event property in the
prior diagnostic — synchronous TTLs land at the same sample idx, so
the ε margin is purely defensive against acquisition jitter).
"""
from __future__ import annotations

import numpy as np

from stroke_orofacial.spout_behavior.trial_segmentation import (
    build_per_trial_records,
)


def _empty_licks_and_rewards(Fs: float = 1000.0) -> dict[str, np.ndarray]:
    return {
        "Lick_L": np.array([], dtype=int),
        "Lick_R": np.array([], dtype=int),
        "Tone_L": np.array([], dtype=int),
        "Tone_R": np.array([], dtype=int),
        "Reward_L": np.array([], dtype=int),
        "Reward_R": np.array([], dtype=int),
        "Fs": Fs,
    }


class TestBuildPerTrialRecords:
    def test_empty_tones_returns_empty_list(self):
        out = build_per_trial_records(
            _empty_licks_and_rewards(), window_seconds=(0.0, 2.0)
        )
        assert out == []

    def test_single_L_tone_trial_with_paired_reward_and_licks(self):
        lr = _empty_licks_and_rewards()
        # Synchronous tone + reward TTLs (per prior diagnostic): same
        # sample idx for both. Q-A.β: tone_idx is the anchor.
        lr["Tone_L"] = np.array([10_000])
        lr["Reward_L"] = np.array([10_000])
        # Licks in window [10000, 12000): one L at 10500, one R at 11000.
        lr["Lick_L"] = np.array([10_500])
        lr["Lick_R"] = np.array([11_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        r = out[0]
        assert r.trial_idx == 0
        assert r.tone_side == "L"
        assert r.tone_idx == 10_000
        assert r.reward_idx == 10_000  # paired synchronously
        assert r.trial_type == "rewarded"
        np.testing.assert_array_equal(r.licks_L_indices_in_window, [10_500])
        np.testing.assert_array_equal(r.licks_R_indices_in_window, [11_000])
        assert r.Fs == 1000.0
        assert r.window_seconds == (0.0, 2.0)

    def test_withhold_trial_has_reward_idx_none_and_trial_type_unrewarded(self):
        """Q-A.β withhold-trial signature: tone fires, reward withheld
        on every trial of that side (per PS55/20250428 prior diagnostic
        for the R side). reward_idx is None, trial_type unrewarded."""
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([10_000])
        # Reward_L intentionally empty: no reward fired this trial.
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        r = out[0]
        assert r.tone_idx == 10_000
        assert r.reward_idx is None
        assert r.trial_type == "unrewarded"

    def test_reward_outside_pairing_window_yields_unrewarded(self):
        """Pairing window is 50ms (50 samples at Fs=1000); a reward
        landing later than the window is NOT paired with the tone."""
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([10_000])
        lr["Reward_L"] = np.array([10_100])  # 100 samples (100 ms) post — outside ε
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        assert out[0].reward_idx is None
        assert out[0].trial_type == "unrewarded"

    def test_window_is_right_exclusive(self):
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([0])
        lr["Reward_L"] = np.array([0])
        # window (0, 2.0) @ Fs=1000 → [0, 2000). Lick at 2000 falls outside.
        lr["Lick_L"] = np.array([1_999, 2_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 1
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_999])

    def test_window_is_left_inclusive(self):
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([1_000])
        lr["Reward_L"] = np.array([1_000])
        # window [1000, 3000). Lick at exactly 1000 (offset 0) included.
        lr["Lick_L"] = np.array([1_000, 999])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_000])

    def test_multiple_trials_sorted_by_tone_idx(self):
        # Interleave L and R tones out of order — builder must sort.
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([5_000, 15_000])
        lr["Tone_R"] = np.array([10_000])
        lr["Reward_L"] = np.array([5_000, 15_000])
        lr["Reward_R"] = np.array([10_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 3
        assert [r.trial_idx for r in out] == [0, 1, 2]
        assert [r.tone_idx for r in out] == [5_000, 10_000, 15_000]
        assert [r.tone_side for r in out] == ["L", "R", "L"]
        assert all(r.trial_type == "rewarded" for r in out)

    def test_per_trial_lick_slicing_independence(self):
        # Licks far from any tone window excluded; within-window licks included.
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([0, 10_000])
        lr["Reward_L"] = np.array([0, 10_000])
        lr["Lick_L"] = np.array([500, 5_000, 10_500, 20_000])
        out = build_per_trial_records(lr, window_seconds=(0.0, 2.0))
        assert len(out) == 2
        # Trial 0 window [0, 2000): only 500.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [500])
        # Trial 1 window [10000, 12000): only 10500.
        np.testing.assert_array_equal(out[1].licks_L_indices_in_window, [10_500])

    def test_negative_window_start_reaches_pre_tone(self):
        # window_seconds[0] < 0 → look backward from tone-onset.
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([5_000])
        lr["Reward_L"] = np.array([5_000])
        lr["Lick_L"] = np.array([4_500, 5_500])
        out = build_per_trial_records(lr, window_seconds=(-1.0, 2.0))
        # window: [4000, 7000) → both licks included.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [4_500, 5_500])

    def test_non_unit_Fs(self):
        lr = _empty_licks_and_rewards(Fs=250.0)
        lr["Tone_L"] = np.array([1_000])
        lr["Reward_L"] = np.array([1_000])
        lr["Lick_L"] = np.array([1_100])  # 100 samples post-tone @ Fs=250 = 0.4 s
        out = build_per_trial_records(lr, window_seconds=(0.0, 1.0))
        # window @ Fs=250 = [1000, 1250). 1100 in range.
        np.testing.assert_array_equal(out[0].licks_L_indices_in_window, [1_100])
        assert out[0].Fs == 250.0


class TestTrialRecordIsFrozen:
    def test_cannot_mutate_fields(self):
        lr = _empty_licks_and_rewards()
        lr["Tone_L"] = np.array([0])
        lr["Reward_L"] = np.array([0])
        r = build_per_trial_records(lr, window_seconds=(0.0, 1.0))[0]
        import dataclasses
        # Frozen dataclass: attribute assignment raises FrozenInstanceError.
        try:
            r.trial_idx = 99  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            return
        raise AssertionError("Expected FrozenInstanceError on frozen dataclass")
