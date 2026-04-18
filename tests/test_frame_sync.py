"""Tests for stroke_orofacial.alignment.frame_sync."""

from __future__ import annotations

import numpy as np
import pytest

from stroke_orofacial.alignment.frame_sync import (
    _align_edge_sequences,
    _find_rising_edges,
    _normalize_minmax_robust,
    _safe_interp1d,
    make_alignment_template,
)


class TestNormalizeMinmaxRobust:
    def test_basic(self):
        x = np.array([0.0, 5.0, 10.0])
        result = _normalize_minmax_robust(x, p_lo=0, p_hi=100)
        np.testing.assert_allclose(result, [0.0, 0.5, 1.0])

    def test_constant_signal(self):
        x = np.full(100, 3.0)
        result = _normalize_minmax_robust(x)
        assert np.all(result == 0.0)

    def test_robust_percentiles(self):
        rng = np.random.default_rng(42)
        x = rng.standard_normal(1000)
        result = _normalize_minmax_robust(x, p_lo=5, p_hi=95)
        # Most values should be in [0, 1], but outliers may exceed
        assert result.shape == x.shape
        assert np.isfinite(result).all()


class TestFindRisingEdges:
    def test_single_edge(self):
        sig = np.zeros(100)
        sig[50:] = 1.0
        edges = _find_rising_edges(sig, thr=0.5)
        assert len(edges) == 1
        assert edges[0] == 50

    def test_multiple_edges(self):
        sig = np.zeros(200)
        sig[30:60] = 1.0
        sig[100:130] = 1.0
        edges = _find_rising_edges(sig, thr=0.5)
        assert len(edges) == 2
        np.testing.assert_array_equal(edges, [30, 100])

    def test_no_edges(self):
        sig = np.zeros(100)
        edges = _find_rising_edges(sig, thr=0.5)
        assert len(edges) == 0


class TestAlignEdgeSequences:
    def test_identical_sequences(self):
        """Identical sequences should produce a monotonic mapping."""
        n = 200
        s = np.linspace(0, 1, n)
        matches = _align_edge_sequences(s, s, window=10, p=0.1)
        assert len(matches) > 0
        # Mapping should be monotonically increasing
        keys = sorted(matches.keys())
        vals = [matches[k] for k in keys]
        assert all(v2 > v1 for v1, v2 in zip(vals, vals[1:]))

    def test_shifted_sequences(self):
        """Similar sequences should produce matches."""
        n = 200
        s1 = np.linspace(0, 1, n)
        s2 = np.linspace(0, 1, n + 5)[:n]
        matches = _align_edge_sequences(s1, s2, window=10, p=0.1)
        assert len(matches) > 10  # should match a reasonable number

    def test_too_few_edges_raises(self):
        s = np.array([0.0, 0.5, 1.0])
        with pytest.raises(ValueError, match="Not enough edges"):
            _align_edge_sequences(s, s, window=20, p=0.1)


class TestSafeInterp1d:
    def test_basic_interpolation(self):
        x = np.array([0.0, 1.0, 2.0])
        y = np.array([0.0, 10.0, 20.0])
        xq = np.array([0.5, 1.5])
        result = _safe_interp1d(x, y, xq)
        np.testing.assert_allclose(result, [5.0, 15.0])

    def test_out_of_bounds_nan(self):
        x = np.array([0.0, 1.0])
        y = np.array([0.0, 10.0])
        xq = np.array([-1.0, 0.5, 2.0])
        result = _safe_interp1d(x, y, xq)
        assert np.isnan(result[0])
        assert np.isnan(result[2])
        np.testing.assert_allclose(result[1], 5.0)

    def test_handles_nan_inputs(self):
        x = np.array([0.0, np.nan, 1.0, 2.0])
        y = np.array([0.0, 5.0, 10.0, 20.0])
        xq = np.array([0.5, 1.5])
        result = _safe_interp1d(x, y, xq)
        assert np.isfinite(result).all()


class TestMakeAlignmentTemplate:
    def _make_synthetic_data(self, n_ws=10000, n_cam=2500, Fs=1000.0, fps=250.0):
        """Create synthetic wavesurfer + camera data with a known sync signal.

        Sync signal: square wave at ~18 Hz (every ~55 samples at 1kHz,
        every ~14 frames at 250 fps).
        """
        import pandas as pd

        # WS sync: square wave
        ws_sync = np.zeros(n_ws)
        period_ws = int(Fs / 18)  # ~55 samples
        for i in range(0, n_ws, period_ws):
            ws_sync[i : i + period_ws // 2] = 1.0

        # Camera sync: same square wave but at camera rate
        cam_sync = np.zeros(n_cam)
        period_cam = int(fps / 18)  # ~14 frames
        for i in range(0, n_cam, period_cam):
            cam_sync[i : i + period_cam // 2] = 1.0

        # Camera time: frame tick counters (arbitrary offset)
        cam_time = np.arange(n_cam, dtype=np.float64) + 1e8

        ws_signals = {
            "Sync_signal": ws_sync,
            "sample_rate_input": Fs,
        }
        cam_csv = pd.DataFrame({0: cam_time, 1: np.zeros(n_cam), 2: cam_sync})
        return ws_signals, cam_csv

    def test_produces_expected_keys(self):
        ws_signals, cam_csv = self._make_synthetic_data()
        params = {
            "csv_idx_sync": 2,
            "csv_idx_time": 0,
            "key_sync": "Sync_signal",
            "fps_cam": 250.0,
            "window": 10,
            "p": 0.1,
            "min_matched_edges": 5,
            "edge_threshold": 0.5,
        }
        result = make_alignment_template(ws_signals, cam_csv, params)

        expected_keys = {
            "Fs_ws_input", "slope_ws_per_camFrame", "intercept_ws_samples",
            "slope_wsTime_per_camTime", "intercept_wsTime",
            "slope", "intercept",
            "idxCam_edges", "idxWS_edges",
            "camEdge_time", "wsEdge_time",
            "camEdge_time_norm01", "wsEdge_time_norm01",
            "matched_camEdge_i", "matched_wsEdge_i",
            "sig_camTimes__idx_cam", "sig_wsTimes__idx_ws",
            "sig_camTimesCommon__idx_cam", "sig_wsTimesCommon__idx_ws",
            "sig_camIdx__idx_ws", "sig_wsIdx__idx_cam",
            "expected_ws_samples_per_camFrame",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_slope_reasonable(self):
        ws_signals, cam_csv = self._make_synthetic_data()
        params = {
            "csv_idx_sync": 2,
            "csv_idx_time": 0,
            "key_sync": "Sync_signal",
            "fps_cam": 250.0,
            "window": 10,
            "p": 0.1,
            "min_matched_edges": 5,
            "edge_threshold": 0.5,
        }
        result = make_alignment_template(ws_signals, cam_csv, params)
        # Slope should be positive and in a reasonable range
        # (synthetic data may not perfectly match real-world patterns)
        slope = result["slope_ws_per_camFrame"]
        assert slope > 0
        assert 2.0 < slope < 8.0  # Fs/fps=4.0 is the ideal

    def test_missing_sync_key_raises(self):
        import pandas as pd

        ws_signals = {"Other_signal": np.zeros(100), "sample_rate_input": 1000.0}
        cam_csv = pd.DataFrame({0: np.arange(25), 1: np.zeros(25), 2: np.zeros(25)})
        params = {
            "csv_idx_sync": 2, "csv_idx_time": 0, "key_sync": "Sync_signal",
            "fps_cam": 250.0, "window": 5, "p": 0.1, "min_matched_edges": 5,
        }
        with pytest.raises(KeyError, match="Sync_signal"):
            make_alignment_template(ws_signals, cam_csv, params)
