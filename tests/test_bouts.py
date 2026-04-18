"""Tests for stroke_orofacial.spout_behavior.bouts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.bouts import (
    find_grooming_bouts,
    find_peri_reward_periods,
    find_quiet_bouts,
    find_running_bouts,
)


# ---------------------------------------------------------------------------
# Running bouts
# ---------------------------------------------------------------------------


class TestFindRunningBouts:
    def test_no_running(self):
        signal = np.zeros(1000)
        params = {"thresh_speed": 5, "max_gap_duration": 0.3, "min_duration": 2.0}
        result = find_running_bouts(signal, Fs=1000.0, params=params)
        assert not result.any()

    def test_sustained_running(self):
        signal = np.zeros(5000)
        signal[1000:4000] = 10.0  # 3 seconds of running at 1kHz
        params = {"thresh_speed": 5, "max_gap_duration": 0.3, "min_duration": 2.0}
        result = find_running_bouts(signal, Fs=1000.0, params=params)
        assert result[2000]  # middle of running bout
        assert not result[0]  # before
        assert not result[4999]  # after

    def test_short_bout_dropped(self):
        signal = np.zeros(5000)
        signal[1000:1500] = 10.0  # only 0.5 sec
        params = {"thresh_speed": 5, "max_gap_duration": 0.3, "min_duration": 2.0}
        result = find_running_bouts(signal, Fs=1000.0, params=params)
        assert not result.any()

    def test_gap_filling(self):
        signal = np.zeros(10000)
        signal[1000:3000] = 10.0  # 2 sec
        signal[3200:6000] = 10.0  # 2.8 sec, gap of 200ms (< 300ms max_gap)
        params = {"thresh_speed": 5, "max_gap_duration": 0.3, "min_duration": 2.0}
        result = find_running_bouts(signal, Fs=1000.0, params=params)
        # Gap should be filled, creating one continuous bout
        assert result[3100]  # in the gap


# ---------------------------------------------------------------------------
# Grooming bouts
# ---------------------------------------------------------------------------


class TestFindGroomingBouts:
    def test_no_licks_no_grooming(self):
        lick_idx = {"Lick_L": np.array([], dtype=int), "Lick_R": np.array([], dtype=int)}
        params = {
            "duration_widen_conj_before": 0.02,
            "duration_widen_conj_after": 0.02,
            "duration_maxThresh_long": 0.4,
            "duration_widen_bad_before": 5.0,
            "duration_widen_bad_after": 5.0,
            "duration_minThresh_good": 10.0,
        }
        result = find_grooming_bouts(lick_idx, n_samples=10000, Fs=1000.0, params=params)
        assert not result.any()

    def test_bilateral_licking_triggers_grooming(self):
        """Simultaneous L+R licking (grooming) should be detected."""
        n = 50000
        # Create overlapping L and R lick events
        lick_L = np.arange(5000, 5500, 5)  # 100 lick events over 500 samples
        lick_R = np.arange(5010, 5510, 5)  # overlapping R licks
        lick_idx = {"Lick_L": lick_L, "Lick_R": lick_R}
        params = {
            "duration_widen_conj_before": 0.02,
            "duration_widen_conj_after": 0.02,
            "duration_maxThresh_long": 0.4,
            "duration_widen_bad_before": 0.1,  # small buffer for test
            "duration_widen_bad_after": 0.1,
            "duration_minThresh_good": 0.5,
        }
        result = find_grooming_bouts(lick_idx, n_samples=n, Fs=1000.0, params=params)
        assert result[5100]  # inside the bilateral region


# ---------------------------------------------------------------------------
# Peri-reward periods
# ---------------------------------------------------------------------------


class TestFindPeriRewardPeriods:
    def test_single_reward(self):
        reward_idx = {"Reward_L": np.array([1000]), "Reward_R": np.array([], dtype=int)}
        params = {"window_around_reward": [0, 6]}
        result = find_peri_reward_periods(reward_idx, n_samples=10000, Fs=1000.0, params=params)
        # With eps_l=0, window starts just after the reward sample itself
        # (searchsorted side="right" for v-0). Samples 1001..6999 are marked.
        assert result[1001]
        assert result[6999]
        assert not result[7000]
        assert not result[500]

    def test_no_rewards(self):
        reward_idx = {"Reward_L": np.array([], dtype=int), "Reward_R": np.array([], dtype=int)}
        params = {"window_around_reward": [0, 6]}
        result = find_peri_reward_periods(reward_idx, n_samples=5000, Fs=1000.0, params=params)
        assert not result.any()

    def test_bilateral_rewards_consolidated(self):
        reward_idx = {"Reward_L": np.array([1000]), "Reward_R": np.array([2000])}
        params = {"window_around_reward": [0, 1]}  # 1 sec window
        result = find_peri_reward_periods(reward_idx, n_samples=5000, Fs=1000.0, params=params)
        # Two separate windows: [1000, 2000) and [2000, 3000)
        assert result[1500]
        assert result[2500]
        assert not result[500]
        assert not result[3500]


# ---------------------------------------------------------------------------
# Quiet bouts
# ---------------------------------------------------------------------------


class TestFindQuietBouts:
    def test_all_quiet(self):
        """Session with no movement, no licks, no rewards → all quiet."""
        n = 20000
        treadmill = np.zeros(n)
        grooming = np.zeros(n, dtype=bool)
        lick_idx = {"Lick_L": np.array([], dtype=int), "Lick_R": np.array([], dtype=int)}
        reward_idx = {"Reward_L": np.array([], dtype=int), "Reward_R": np.array([], dtype=int)}
        params = {
            "speed_threshold": 1,
            "min_quiet_duration": 10,
            "treadmillSlow_time_buffer": [3, 3],
            "lick_time_buffer": [1, 3],
            "reward_time_buffer": [0.1, 8],
            "groom_time_buffer": [6, 6],
        }
        result = find_quiet_bouts(
            treadmill, grooming, lick_idx, reward_idx,
            n_samples=n, Fs=1000.0, params=params,
        )
        # Most of the session should be quiet (excluding edge buffer effects)
        assert result.sum() > n * 0.5

    def test_running_excludes_quiet(self):
        """Fast treadmill should exclude quiet."""
        n = 20000
        treadmill = np.full(n, 10.0)  # always running
        grooming = np.zeros(n, dtype=bool)
        lick_idx = {"Lick_L": np.array([], dtype=int), "Lick_R": np.array([], dtype=int)}
        reward_idx = {"Reward_L": np.array([], dtype=int), "Reward_R": np.array([], dtype=int)}
        params = {
            "speed_threshold": 1,
            "min_quiet_duration": 10,
            "treadmillSlow_time_buffer": [3, 3],
            "lick_time_buffer": [1, 3],
            "reward_time_buffer": [0.1, 8],
            "groom_time_buffer": [6, 6],
        }
        result = find_quiet_bouts(
            treadmill, grooming, lick_idx, reward_idx,
            n_samples=n, Fs=1000.0, params=params,
        )
        assert not result.any()


# ---------------------------------------------------------------------------
# Integration: parity against session_processing3
# ---------------------------------------------------------------------------

_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)
_SP3 = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3"
)


def _run_full_pipeline(date_str: str) -> dict[str, np.ndarray]:
    """Run wavesurfer → licks → treadmill → all bouts for PS46 on a given date."""
    from stroke_orofacial.spout_behavior.wavesurfer_io import (
        calibrate_treadmill,
        find_wavesurfer_file,
        load_wavesurfer_signals,
        smooth_treadmill,
    )
    from stroke_orofacial.spout_behavior.lick_detection import find_licks_and_rewards

    ws_file = find_wavesurfer_file(_WS_LOCAL / date_str / "PS46")
    signals = load_wavesurfer_signals(ws_file)
    Fs = float(signals["sample_rate_input"])

    # Treadmill
    calibrated = calibrate_treadmill(signals["Treadmill"], 1.2587643276652853, 0.382, 29.25)
    treadmill_smoothed = smooth_treadmill(calibrated, Fs, 0.15)

    # Licks and rewards
    lick_params = {
        "lick_detection": {
            "thresh_upper": 2.5,
            "thresh_lower": 0.5,
            "duration_lockout_falling_edge": [0.001, 0.02],
        },
        "reward_detection": {"thresh": 0.5},
    }
    lr = find_licks_and_rewards(signals, lick_params)
    n_samples = int(lr["n_samples"])
    lick_idx = {"Lick_L": lr["Lick_L"], "Lick_R": lr["Lick_R"]}
    reward_idx = {"Reward_L": lr["Reward_L"], "Reward_R": lr["Reward_R"]}

    # Running bouts
    running_params = {"thresh_speed": 5, "max_gap_duration": 0.3, "min_duration": 2.0}
    running = find_running_bouts(treadmill_smoothed, Fs, running_params)

    # Grooming bouts
    grooming_params = {
        "duration_widen_conj_before": 0.020,
        "duration_widen_conj_after": 0.020,
        "duration_maxThresh_long": 0.400,
        "duration_widen_bad_before": 5.000,
        "duration_widen_bad_after": 5.000,
        "duration_minThresh_good": 10.000,
    }
    grooming = find_grooming_bouts(lick_idx, n_samples, Fs, grooming_params)

    # Quiet bouts
    quiet_params = {
        "speed_threshold": 1,
        "min_quiet_duration": 10,
        "treadmillSlow_time_buffer": [3, 3],
        "lick_time_buffer": [1, 3],
        "reward_time_buffer": [0.1, 8],
        "groom_time_buffer": [6, 6],
    }
    quiet = find_quiet_bouts(
        treadmill_smoothed, grooming, lick_idx, reward_idx, n_samples, Fs, quiet_params
    )

    # Peri-reward
    peri_params = {"window_around_reward": [0, 6]}
    peri_reward = find_peri_reward_periods(reward_idx, n_samples, Fs, peri_params)

    return {
        "treadmill_smoothed": treadmill_smoothed,
        "running_bouts": running,
        "lick_bool_bad": grooming,
        "quiet_bool": quiet,
        "peri_reward_bool": peri_reward,
    }


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists()
    or not (_SP3 / "running_bouts" / "PS46" / "20250307.npz").exists(),
    reason="Wavesurfer data or session_processing3 not available",
)
class TestIntegrationBouts:
    def test_parity_ps46_20250307(self):
        results = _run_full_pipeline("20250307")
        self._check_parity(results, "20250307")

    def _check_parity(self, results: dict, date_str: str) -> None:
        # Treadmill
        ref_tm = np.load(_SP3 / "treadmill_signals_preprocessed" / "PS46" / f"{date_str}.npz")
        np.testing.assert_allclose(
            results["treadmill_smoothed"],
            ref_tm["Treadmill_smoothed"],
            rtol=1e-10,
            err_msg="Treadmill smoothed mismatch",
        )

        # Running bouts
        ref_run = np.load(_SP3 / "running_bouts" / "PS46" / f"{date_str}.npz")
        np.testing.assert_array_equal(
            results["running_bouts"],
            ref_run["running_bouts"],
            err_msg="Running bouts mismatch",
        )

        # Grooming bouts
        ref_groom = np.load(_SP3 / "grooming_bouts" / "PS46" / f"{date_str}.npz")
        np.testing.assert_array_equal(
            results["lick_bool_bad"],
            ref_groom["lick_bool_bad"],
            err_msg="Grooming bouts mismatch",
        )

        # Quiet bouts
        ref_quiet = np.load(_SP3 / "quiet_bouts" / "PS46" / f"{date_str}.npz")
        np.testing.assert_array_equal(
            results["quiet_bool"],
            ref_quiet["quiet_bool"],
            err_msg="Quiet bouts mismatch",
        )

        # Peri-reward
        ref_peri = np.load(_SP3 / "peri_reward_periods" / "PS46" / f"{date_str}.npz")
        np.testing.assert_array_equal(
            results["peri_reward_bool"],
            ref_peri["peri_reward_bool"],
            err_msg="Peri-reward mismatch",
        )
