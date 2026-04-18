"""Tests for stroke_orofacial.spout_behavior.lick_detection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.lick_detection import (
    find_licks_and_rewards,
    find_reward_indices,
    find_tone_indices,
    _find_upward_lick_indices,
    _find_downward_lick_indices,
    _clean_lick_indices,
)


def _make_lick_signal(n: int = 1000, lick_at: list[int] | None = None) -> np.ndarray:
    """Create a synthetic lick signal: high at rest (~4V), drops to ~0V on lick."""
    sig = np.full(n, 4.0)
    for idx in (lick_at or []):
        # Simulate a lick: voltage drops below thresh_upper for ~10 samples
        sig[idx : idx + 10] = 0.2
    return sig


class TestFindRewardIndices:
    def test_single_reward(self):
        # Digital signal: 0 then 1 at index 50
        sig = np.zeros(100, dtype=float)
        sig[50:] = 1.0
        signals = {"Reward_L": sig, "Reward_R": np.zeros(100)}
        result = find_reward_indices(signals, thresh=0.5)
        assert len(result["Reward_L"]) == 1
        assert result["Reward_L"][0] == 50
        assert len(result["Reward_R"]) == 0

    def test_multiple_rewards(self):
        sig = np.zeros(200, dtype=float)
        sig[30:60] = 1.0
        sig[100:130] = 1.0
        signals = {"Reward_L": sig, "Reward_R": np.zeros(200)}
        result = find_reward_indices(signals, thresh=0.5)
        assert len(result["Reward_L"]) == 2
        np.testing.assert_array_equal(result["Reward_L"], [30, 100])


class TestFindToneIndices:
    def test_single_tone(self):
        sig = np.zeros(100, dtype=float)
        sig[70:] = 1.0
        signals = {"Tone_L": sig, "Tone_R": np.zeros(100)}
        result = find_tone_indices(signals, thresh=0.5)
        assert len(result["Tone_L"]) == 1
        assert result["Tone_L"][0] == 70
        assert len(result["Tone_R"]) == 0

    def test_uses_same_algorithm_as_rewards(self):
        """Tone detection is identical to reward detection — same rising edge."""
        sig = np.zeros(200, dtype=float)
        sig[30:60] = 1.0
        sig[100:130] = 1.0
        signals_r = {"Reward_L": sig, "Reward_R": np.zeros(200)}
        signals_t = {"Tone_L": sig, "Tone_R": np.zeros(200)}
        rewards = find_reward_indices(signals_r, thresh=0.5)
        tones = find_tone_indices(signals_t, thresh=0.5)
        np.testing.assert_array_equal(rewards["Reward_L"], tones["Tone_L"])


class TestUpwardLickIndices:
    def test_detects_lick_onset(self):
        sig = _make_lick_signal(200, lick_at=[50])
        signals = {"Lick_L": sig, "Lick_R": np.full(200, 4.0)}
        result = _find_upward_lick_indices(signals, thresh_upper=2.5)
        assert len(result["Lick_L"]) == 1
        assert result["Lick_L"][0] == 50
        assert len(result["Lick_R"]) == 0

    def test_no_licks(self):
        sig = np.full(200, 4.0)
        signals = {"Lick_L": sig, "Lick_R": sig.copy()}
        result = _find_upward_lick_indices(signals, thresh_upper=2.5)
        assert len(result["Lick_L"]) == 0


class TestDownwardLickIndices:
    def test_detects_lick_offset(self):
        sig = _make_lick_signal(200, lick_at=[50])
        signals = {"Lick_L": sig, "Lick_R": np.full(200, 4.0)}
        result = _find_downward_lick_indices(signals, thresh_lower=0.5)
        # Signal starts at 4.0 (>0.5), so diff detects a rising at index 0.
        # Lick offset = signal rises above 0.5 again at index 60.
        assert 60 in result["Lick_L"]


class TestCleanLickIndices:
    def test_removes_events_in_lockout(self):
        up = {"Lick_L": np.array([10, 50, 52, 100]), "Lick_R": np.array([])}
        down = {"Lick_L": np.array([51]), "Lick_R": np.array([])}
        # Lockout: [51 + 0, 51 + 5) = [51, 56) → index 52 in up_idx is at position 2
        cleaned = _clean_lick_indices(up, down, lockout_samples=(0, 5))
        # 52 falls within [51, 56) so should be removed
        assert 52 not in cleaned["Lick_L"]
        assert 10 in cleaned["Lick_L"]
        assert 50 in cleaned["Lick_L"]
        assert 100 in cleaned["Lick_L"]

    def test_no_downward_events_no_change(self):
        up = {"Lick_L": np.array([10, 50, 100]), "Lick_R": np.array([])}
        down = {"Lick_L": np.array([], dtype=int), "Lick_R": np.array([], dtype=int)}
        cleaned = _clean_lick_indices(up, down, lockout_samples=(1, 20))
        np.testing.assert_array_equal(cleaned["Lick_L"], up["Lick_L"])


class TestFindLicksAndRewards:
    def test_end_to_end_synthetic(self):
        """Full pipeline on synthetic signals."""
        n = 1000
        Fs = 1000.0
        lick_sig_L = _make_lick_signal(n, lick_at=[100, 500])
        lick_sig_R = _make_lick_signal(n, lick_at=[300])
        reward_L = np.zeros(n)
        reward_L[200:250] = 1.0
        reward_R = np.zeros(n)

        tone_L = np.zeros(n)
        tone_L[150:200] = 1.0
        tone_R = np.zeros(n)

        signals = {
            "Lick_L": lick_sig_L,
            "Lick_R": lick_sig_R,
            "Reward_L": reward_L,
            "Reward_R": reward_R,
            "Tone_L": tone_L,
            "Tone_R": tone_R,
            "sample_rate_input": Fs,
        }
        params = {
            "lick_detection": {
                "thresh_upper": 2.5,
                "thresh_lower": 0.5,
                "duration_lockout_falling_edge": [0.001, 0.02],
            },
            "reward_detection": {"thresh": 0.5},
        }
        result = find_licks_and_rewards(signals, params)

        assert len(result["Lick_L"]) == 2
        assert len(result["Lick_R"]) == 1
        assert len(result["Reward_L"]) == 1
        assert len(result["Reward_R"]) == 0
        assert len(result["Tone_L"]) == 1
        assert len(result["Tone_R"]) == 0
        assert result["Fs"] == Fs
        assert result["n_samples"] == n


# ---- Integration test (requires real data) ----

_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)
_SP3 = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/analysis/session_processing3"
)


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists() or not (_SP3 / "licks_and_rewards" / "PS46" / "20250307.npz").exists(),
    reason="Wavesurfer data or session_processing3 not available",
)
class TestIntegrationLickDetection:
    def test_parity_ps46_20250307(self):
        """Lick/reward detection must match session_processing3 outputs exactly."""
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            find_wavesurfer_file,
            load_wavesurfer_signals,
        )

        ws_file = find_wavesurfer_file(_WS_LOCAL / "20250307" / "PS46")
        signals = load_wavesurfer_signals(ws_file)

        params = {
            "lick_detection": {
                "thresh_upper": 2.5,
                "thresh_lower": 0.5,
                "duration_lockout_falling_edge": [0.001, 0.02],
            },
            "reward_detection": {"thresh": 0.5},
        }
        result = find_licks_and_rewards(signals, params)

        # Load reference
        ref = dict(np.load(_SP3 / "licks_and_rewards" / "PS46" / "20250307.npz"))

        for key in ("Lick_L", "Lick_R", "Reward_L", "Reward_R"):
            np.testing.assert_array_equal(
                result[key], ref[key],
                err_msg=f"Mismatch in {key} vs session_processing3"
            )
        assert result["Fs"] == float(ref["Fs"])
        assert result["n_samples"] == int(ref["n_samples"])
