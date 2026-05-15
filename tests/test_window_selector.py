"""Tests for stroke_orofacial.dlc_spatial.window_selector."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_spatial.window_selector import (
    EventAlignedWindow,
    ToneAlignedWindow,
    WholeSessionWindow,
    _ws_to_cam_frames,
)


class TestWholeSessionWindow:
    def test_selects_all_frames(self):
        df = pd.DataFrame({"a": range(100)})
        w = WholeSessionWindow()
        mask = w.select_frames(df)
        assert mask.shape == (100,)
        assert mask.all()

    def test_label(self):
        assert WholeSessionWindow().label == "whole"


class TestEventAlignedWindow:
    def test_single_event(self):
        w = EventAlignedWindow(
            event_frame_indices=np.array([50]),
            pre_frames=10, post_frames=20, n_frames=100,
        )
        mask = w.select_frames(pd.DataFrame({"a": range(100)}))
        assert mask[40]   # 50 - 10
        assert mask[50]   # center
        assert mask[70]   # 50 + 20
        assert not mask[39]
        assert not mask[71]

    def test_deduplication(self):
        """Overlapping event windows should not double-count frames."""
        w = EventAlignedWindow(
            event_frame_indices=np.array([50, 55]),
            pre_frames=5, post_frames=5, n_frames=100,
        )
        mask = w.select_frames(pd.DataFrame({"a": range(100)}))
        # Frames 45-60 covered by the two overlapping windows
        assert mask[45]
        assert mask[55]
        assert mask[60]
        assert not mask[44]
        assert not mask[61]
        # n_selected should be unique count, not sum of window sizes
        assert w.n_selected == 16  # 45..60 inclusive

    def test_edge_clamping(self):
        """Events near boundaries should be clamped to valid range."""
        w = EventAlignedWindow(
            event_frame_indices=np.array([2]),
            pre_frames=10, post_frames=5, n_frames=20,
        )
        mask = w.select_frames(pd.DataFrame({"a": range(20)}))
        assert mask[0]  # clamped from 2-10=-8 to 0
        assert mask[7]  # 2+5
        assert not mask[8]

    def test_invalid_event_skipped(self):
        """Events with index -1 should be skipped."""
        w = EventAlignedWindow(
            event_frame_indices=np.array([-1, 50]),
            pre_frames=5, post_frames=5, n_frames=100,
        )
        assert w.n_events == 2
        assert w.n_selected == 11  # only from event at 50

    def test_label(self):
        w = EventAlignedWindow(
            np.array([10]), 5, 5, 100, label_str="test_event"
        )
        assert w.label == "test_event"

    def test_length_mismatch_raises(self):
        w = EventAlignedWindow(np.array([10]), 5, 5, 100)
        with pytest.raises(ValueError, match="length"):
            w.select_frames(pd.DataFrame({"a": range(50)}))


class TestWsToCamFrames:
    def test_basic_conversion(self):
        # LUT: WS sample i maps to camera frame i/4
        lut = np.arange(100, dtype=float) / 4.0
        ws = np.array([0, 4, 8, 12])
        result = _ws_to_cam_frames(ws, lut, n_cam_frames=30)
        np.testing.assert_array_equal(result, [0, 1, 2, 3])

    def test_out_of_range(self):
        lut = np.arange(50, dtype=float)
        ws = np.array([100, -1])  # both out of range
        result = _ws_to_cam_frames(ws, lut, n_cam_frames=50)
        np.testing.assert_array_equal(result, [-1, -1])

    def test_nan_in_lut(self):
        lut = np.array([0.0, np.nan, 2.0, 3.0])
        ws = np.array([0, 1, 2])
        result = _ws_to_cam_frames(ws, lut, n_cam_frames=10)
        assert result[0] == 0
        assert result[1] == -1  # NaN → -1
        assert result[2] == 2


class TestToneAlignedWindow:
    def test_basic(self):
        # Simple LUT: 1:1 mapping (WS sample = frame)
        lut = np.arange(1000, dtype=float)
        reward_ws = np.array([100, 500])
        w = ToneAlignedWindow(
            tone_ws_samples=reward_ws,
            sig_camIdx__idx_ws=lut,
            window_ms=(-100, 500),  # 100ms before to 500ms after
            fps=250.0,
            n_frames=1000,
        )
        # pre_frames = round(100/1000 * 250) = 25
        # post_frames = round(500/1000 * 250) = 125
        mask = w.select_frames(pd.DataFrame({"a": range(1000)}))
        assert mask[100]   # reward center
        assert mask[75]    # 100 - 25
        assert mask[225]   # 100 + 125
        assert w.n_events == 2
        assert w.label == "reward_-100_500ms"
