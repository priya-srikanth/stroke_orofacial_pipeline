"""Tests for stroke_orofacial.spout_behavior.wavesurfer_io."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.wavesurfer_io import (
    _apply_tone_reward_swap,
    calibrate_treadmill,
    find_wavesurfer_file,
    resolve_treadmill_offset,
    smooth_treadmill,
)


class TestCalibrateTreadmill:
    def test_basic_calibration(self):
        signal = np.array([1.5, 2.0, 2.5])
        offset = 1.0
        voltSec_per_rot = 0.5
        mm_per_rot = 10.0
        result = calibrate_treadmill(signal, offset, voltSec_per_rot, mm_per_rot)
        # (signal - offset) * (1/voltSec) * mm_per_rot
        expected = (signal - 1.0) * (1.0 / 0.5) * 10.0
        np.testing.assert_allclose(result, expected)

    def test_zero_offset(self):
        signal = np.array([0.382])
        result = calibrate_treadmill(signal, 0.0, 0.382, 29.25)
        # (0.382 - 0) * (1/0.382) * 29.25 = 1.0 * 29.25
        expected = np.array([29.25])
        np.testing.assert_allclose(result, expected)


class TestSmoothTreadmill:
    def test_output_same_length(self):
        signal = np.random.randn(1000)
        result = smooth_treadmill(signal, Fs=1000.0, sigma_sec=0.01)
        assert result.shape == signal.shape

    def test_smoothing_reduces_variance(self):
        rng = np.random.default_rng(42)
        signal = rng.standard_normal(10000)
        result = smooth_treadmill(signal, Fs=1000.0, sigma_sec=0.05)
        assert np.std(result) < np.std(signal)


class TestResolveTreadmillOffset:
    def test_default_offset(self):
        params = {"offset_in_volts": 1.259}
        offset, applied, source = resolve_treadmill_offset(params)
        assert offset == 1.259
        assert applied is False
        assert source == "defaults.yaml"

    def test_session_override(self):
        params = {"offset_in_volts": 1.259}
        session_params = {"offset_in_volts": 0.0}
        offset, applied, source = resolve_treadmill_offset(params, session_params)
        assert offset == 0.0
        assert applied is True
        assert source == "session_overrides.yaml"

    def test_session_override_without_offset_key(self):
        """Session override exists but doesn't override offset."""
        params = {"offset_in_volts": 1.259}
        session_params = {"smoothing_sigma": 0.2}  # different key
        offset, applied, source = resolve_treadmill_offset(params, session_params)
        assert offset == 1.259
        assert applied is False

    def test_no_session_override(self):
        params = {"offset_in_volts": 1.259}
        offset, applied, source = resolve_treadmill_offset(params, None)
        assert offset == 1.259
        assert applied is False


class TestFindWavesurferFile:
    def test_single_h5(self, tmp_path):
        (tmp_path / "sham_0001.h5").touch()
        result = find_wavesurfer_file(tmp_path)
        assert result.name == "sham_0001.h5"

    def test_excludes_khz(self, tmp_path):
        (tmp_path / "sham_0001.h5").touch()
        (tmp_path / "sham_0001_20kHz.h5").touch()
        result = find_wavesurfer_file(tmp_path)
        assert result.name == "sham_0001.h5"

    def test_no_h5_raises(self, tmp_path):
        (tmp_path / "readme.txt").touch()
        with pytest.raises(FileNotFoundError, match="No wavesurfer .h5 files"):
            find_wavesurfer_file(tmp_path)

    def test_multiple_h5_raises(self, tmp_path):
        (tmp_path / "sham_0001.h5").touch()
        (tmp_path / "sham_0002.h5").touch()
        with pytest.raises(ValueError, match="Multiple wavesurfer .h5 files"):
            find_wavesurfer_file(tmp_path)

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="directory not found"):
            find_wavesurfer_file(tmp_path / "nonexistent")

    def test_varied_filename(self, tmp_path):
        """Wavesurfer filenames vary — glob should find any *.h5."""
        (tmp_path / "stroke_0001.h5").touch()
        result = find_wavesurfer_file(tmp_path)
        assert result.name == "stroke_0001.h5"

    # ---- Phase 7-pre-alignment-templates Addendum #3 L9: preferred_filename ----

    def test_with_override_returns_named_file(self, tmp_path):
        """When session dir has multiple h5s + preferred_filename is set
        to one of them, that exact file is returned without invoking the
        glob-disambig logic.
        """
        (tmp_path / "stroke_0001.h5").touch()
        (tmp_path / "stroke_0002.h5").touch()
        result = find_wavesurfer_file(
            tmp_path, preferred_filename="stroke_0002.h5",
        )
        assert result.name == "stroke_0002.h5"
        assert result == tmp_path / "stroke_0002.h5"

    def test_with_override_none_falls_through_to_glob(self, tmp_path):
        """When preferred_filename=None (default), existing
        single-h5 glob-disambig behavior is preserved (back-compat).
        """
        (tmp_path / "stroke_0001.h5").touch()
        result = find_wavesurfer_file(tmp_path, preferred_filename=None)
        assert result.name == "stroke_0001.h5"
        # Sanity: same as no-kwarg call (back-compat preserved)
        assert find_wavesurfer_file(tmp_path) == result

    def test_with_override_missing_raises(self, tmp_path):
        """When preferred_filename is set but the named file doesn't
        exist on disk, raise FileNotFoundError that names BOTH the
        configured filename AND the actual *.h5 files present — so the
        caller can fix the YAML vs disk mismatch.
        """
        (tmp_path / "stroke_0001.h5").touch()
        (tmp_path / "stroke_0002.h5").touch()
        with pytest.raises(FileNotFoundError) as excinfo:
            find_wavesurfer_file(
                tmp_path, preferred_filename="stroke_0099.h5",
            )
        msg = str(excinfo.value)
        # configured filename
        assert "stroke_0099.h5" in msg
        # actual disk contents
        assert "stroke_0001.h5" in msg
        assert "stroke_0002.h5" in msg
        # pointer to the YAML fix location
        assert "wavesurfer_file_overrides" in msg


# ---- Phase 8a.10.1 Tone↔Reward swap fix ----


def _make_pulses(n_samples: int, starts: list[int], width: int) -> np.ndarray:
    """Build a bool array with rectangular pulses at given start indices."""
    arr = np.zeros(n_samples, dtype=bool)
    for s in starts:
        arr[s : s + width] = True
    return arr


class TestApplyToneRewardSwap:
    """Unit tests for the in-place dict-key swap helper.

    Phase 8a.10.1 Task 1 Commit A. The raw `.h5` channel labels are
    inverted cohort-wide: ``Reward_*`` carries ~200 ms tone TTLs;
    ``Tone_*`` carries ~26 ms reward solenoid pulses. The swap fix
    rebinds the dict keys post-read so consumers see semantically-
    correct content under canonical labels. See Task 0.5 audit at
    `.scratch_phase_8a_10_1/task_0_5_audit_report.md` (271/271 sessions
    swap-confirmed).
    """

    def test_reward_channel_holds_short_pulses_post_swap(self):
        """Post-swap, ``Reward_L`` holds the reward-solenoid short-pulse channel.

        The raw .h5 channel labeled ``Tone_L`` carries the ~26 ms reward
        pulse (per Task 0.5 audit). After the swap, that short-pulse
        content lands at the canonical ``Reward_L`` key.
        """
        n = 1_000_000
        short_pulse = _make_pulses(n, starts=[1000, 5000, 9000], width=26)
        long_pulse = _make_pulses(n, starts=[1000, 5000, 9000], width=200)
        signals = {
            "Reward_L": long_pulse.copy(),  # pre-swap: labeled "Reward" but contains tone TTL
            "Tone_L": short_pulse.copy(),   # pre-swap: labeled "Tone" but contains reward solenoid
            "Reward_R": long_pulse.copy(),
            "Tone_R": short_pulse.copy(),
        }
        _apply_tone_reward_swap(signals)
        np.testing.assert_array_equal(signals["Reward_L"], short_pulse)
        np.testing.assert_array_equal(signals["Reward_R"], short_pulse)

    def test_tone_channel_holds_long_pulses_post_swap(self):
        """Post-swap, ``Tone_L`` holds the auditory-tone long-pulse channel."""
        n = 1_000_000
        short_pulse = _make_pulses(n, starts=[100, 500, 900], width=26)
        long_pulse = _make_pulses(n, starts=[100, 500, 900], width=200)
        signals = {
            "Reward_L": long_pulse.copy(),
            "Tone_L": short_pulse.copy(),
            "Reward_R": long_pulse.copy(),
            "Tone_R": short_pulse.copy(),
        }
        _apply_tone_reward_swap(signals)
        np.testing.assert_array_equal(signals["Tone_L"], long_pulse)
        np.testing.assert_array_equal(signals["Tone_R"], long_pulse)

    def test_swap_compensates_for_label_inversion(self):
        """Identity check: round-trip swap of swapped content is original mapping.

        Documents the swap explicitly. Given content known to be ``A`` at
        the ``Reward_L`` key and ``B`` at the ``Tone_L`` key pre-swap, the
        post-swap state has ``B`` at ``Reward_L`` and ``A`` at ``Tone_L``.
        """
        a = np.array([True, False, True, False], dtype=bool)
        b = np.array([False, True, False, True], dtype=bool)
        signals = {
            "Reward_L": a.copy(), "Tone_L": b.copy(),
            "Reward_R": a.copy(), "Tone_R": b.copy(),
        }
        _apply_tone_reward_swap(signals)
        np.testing.assert_array_equal(signals["Reward_L"], b)
        np.testing.assert_array_equal(signals["Tone_L"], a)
        np.testing.assert_array_equal(signals["Reward_R"], b)
        np.testing.assert_array_equal(signals["Tone_R"], a)

    def test_swap_silent_noop_when_one_side_missing(self):
        """Defensive: partial signals dict — pairs without both halves don't fire.

        Real `.h5` files always have all 4 channels, but the helper is
        called on a plain dict so a malformed input should silently skip
        the absent-pair rather than mutate state.
        """
        only_left = {
            "Reward_L": np.array([True, False], dtype=bool),
            "Tone_L": np.array([False, True], dtype=bool),
            # Reward_R, Tone_R intentionally absent
        }
        _apply_tone_reward_swap(only_left)
        # Left pair swapped:
        np.testing.assert_array_equal(only_left["Reward_L"], [False, True])
        np.testing.assert_array_equal(only_left["Tone_L"], [True, False])
        # Right pair simply absent (no spurious key creation):
        assert "Reward_R" not in only_left
        assert "Tone_R" not in only_left


class TestLoadWavesurferSignalsSwapFlag:
    """Verify the loader's ``tone_reward_swap_enabled`` kwarg gates the swap.

    Monkey-patches ``pywavesurfer.ws.loadDataFile`` so the loader runs
    against synthetic raw-channel content. The flag must apply the swap
    when True (default) and skip it when False (kill-switch).
    """

    @staticmethod
    def _fake_loaddata(signals_payload: dict) -> dict:
        """Build a fake pywavesurfer.ws.loadDataFile return value."""
        # Names + active mask: 1 analog ("Treadmill"), digital names per
        # signals_payload's digital keys (anything matching Lick_*/Reward_*
        # /Tone_*). Bit-pack the digital channels into a single uint8
        # column per the real .h5 layout.
        analog_names = np.array(["Treadmill"], dtype="S20")
        digital_names_list = [k for k in signals_payload if k != "Treadmill"]
        digital_names = np.array(
            [n.encode() for n in digital_names_list], dtype="S20",
        )
        treadmill = signals_payload["Treadmill"]
        n_samples = treadmill.shape[0]
        # Pack the digital channels into bits column idx+1 (per the real
        # layout's offset). Column 0 stays unused (legacy convention).
        bits = np.zeros((n_samples, 8), dtype=bool)
        for i, name in enumerate(digital_names_list):
            bits[:, i + 1] = signals_payload[name]
        raw_bits = np.packbits(bits, axis=1)[:, 0:1]  # 1 byte per sample, shape (n_samples, 1)
        return {
            "header": {
                "AcquisitionSampleRate": np.array([1000.0]),
                "AIChannelNames": analog_names,
                "IsAIChannelActive": np.array([[True]]),
                "DIChannelNames": digital_names,
            },
            "sweep_0001": {
                "analogScans": np.array([treadmill]),
                "digitalScans": np.array([raw_bits.flatten()]),
            },
        }

    def test_swap_enabled_true_applies_swap(self, monkeypatch, tmp_path):
        from stroke_orofacial.spout_behavior import wavesurfer_io
        n = 64
        short = _make_pulses(n, starts=[8, 32], width=4)
        long = _make_pulses(n, starts=[8, 32], width=12)
        payload = {
            "Treadmill": np.zeros(n, dtype=float),
            "Reward_L": long,   # pre-fix: "Reward" label holds tone TTL
            "Reward_R": long,
            "Tone_L": short,    # pre-fix: "Tone" label holds reward solenoid
            "Tone_R": short,
        }
        monkeypatch.setattr(
            wavesurfer_io.pywavesurfer.ws, "loadDataFile",
            lambda _path: self._fake_loaddata(payload),
        )
        # Default flag True (post-fix behavior): swap is applied.
        fake_h5 = tmp_path / "fake.h5"
        fake_h5.touch()
        signals = wavesurfer_io.load_wavesurfer_signals(fake_h5)
        np.testing.assert_array_equal(signals["Reward_L"], short)
        np.testing.assert_array_equal(signals["Tone_L"], long)

    def test_swap_disabled_when_flag_false(self, monkeypatch, tmp_path):
        """Kill-switch: ``tone_reward_swap_enabled=False`` skips the swap.

        For hypothetical future correctly-labeled cohorts. Reading the
        same fixture with the flag off must return the un-swapped raw
        channel mapping (so ``Reward_L`` still holds the long-pulse
        content that was at that key in the simulated raw `.h5`).
        """
        from stroke_orofacial.spout_behavior import wavesurfer_io
        n = 64
        short = _make_pulses(n, starts=[8, 32], width=4)
        long = _make_pulses(n, starts=[8, 32], width=12)
        payload = {
            "Treadmill": np.zeros(n, dtype=float),
            "Reward_L": long,
            "Reward_R": long,
            "Tone_L": short,
            "Tone_R": short,
        }
        monkeypatch.setattr(
            wavesurfer_io.pywavesurfer.ws, "loadDataFile",
            lambda _path: self._fake_loaddata(payload),
        )
        fake_h5 = tmp_path / "fake.h5"
        fake_h5.touch()
        signals = wavesurfer_io.load_wavesurfer_signals(
            fake_h5, tone_reward_swap_enabled=False,
        )
        # No swap: raw mapping preserved.
        np.testing.assert_array_equal(signals["Reward_L"], long)
        np.testing.assert_array_equal(signals["Tone_L"], short)


# ---- Integration test (requires real wavesurfer data) ----

_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)


@pytest.mark.skipif(
    not (_WS_LOCAL / "20250307" / "PS46").exists(),
    reason="Wavesurfer data not available locally",
)
class TestIntegrationWavesurfer:
    def test_load_ps46_20250307(self):
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            load_wavesurfer_signals,
        )

        ws_dir = _WS_LOCAL / "20250307" / "PS46"
        ws_file = find_wavesurfer_file(ws_dir)
        signals = load_wavesurfer_signals(ws_file)

        # Check expected channels exist
        assert "Lick_L" in signals
        assert "Lick_R" in signals
        assert "Treadmill" in signals
        assert "Reward_L" in signals
        assert "Reward_R" in signals
        assert "sample_rate_input" in signals
        assert float(signals["sample_rate_input"]) == 1000.0

        # Check signal shape consistency
        n = signals["Lick_L"].shape[0]
        assert n == 3_610_000  # 60.17 min at 1 kHz
        assert signals["Treadmill"].shape[0] == n

    def test_calibrate_and_smooth_real(self):
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            load_wavesurfer_signals,
        )

        ws_dir = _WS_LOCAL / "20250307" / "PS46"
        ws_file = find_wavesurfer_file(ws_dir)
        signals = load_wavesurfer_signals(ws_file)

        Fs = float(signals["sample_rate_input"])
        raw = signals["Treadmill"]
        calibrated = calibrate_treadmill(raw, 1.2587643276652853, 0.382, 29.25)
        smoothed = smooth_treadmill(calibrated, Fs, 0.15)

        assert smoothed.shape == raw.shape
        assert np.isfinite(smoothed).all()
