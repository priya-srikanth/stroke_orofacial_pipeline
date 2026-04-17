"""Tests for stroke_orofacial.spout_behavior.wavesurfer_io."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.spout_behavior.wavesurfer_io import (
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
