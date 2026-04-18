"""Tests for stroke_orofacial.dlc_spatial.pixel_bins."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_spatial.pixel_bins import (
    build_baseline_histogram,
    build_histogram,
    build_stats_grid,
    get_masked_xy,
)


def _make_dlc_df(n: int = 1000) -> pd.DataFrame:
    """Synthetic DLC DataFrame with nose centered near (0, 0)."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "nose_x": rng.normal(0, 10, n).astype(np.float32),
        "nose_y": rng.normal(0, 10, n).astype(np.float32),
        "nose_likelihood": np.full(n, 0.95, dtype=np.float32),
        "jaw_x": rng.normal(0, 20, n).astype(np.float32),
        "jaw_y": rng.normal(50, 20, n).astype(np.float32),
        "jaw_likelihood": np.full(n, 0.90, dtype=np.float32),
    })


class TestGetMaskedXY:
    def test_basic(self):
        df = _make_dlc_df()
        x, y = get_masked_xy(df, "nose", 0.80)
        assert x is not None
        assert len(x) == len(df)

    def test_high_threshold_filters(self):
        df = _make_dlc_df()
        df.loc[:499, "nose_likelihood"] = 0.3  # half below threshold
        x, y = get_masked_xy(df, "nose", 0.80)
        assert len(x) == 500

    def test_missing_bodypart(self):
        df = _make_dlc_df()
        x, y = get_masked_xy(df, "tongue", 0.80)
        assert x is None

    def test_x_range_filter(self):
        df = _make_dlc_df()
        x, y = get_masked_xy(df, "nose", 0.80, x_range=(-5, 5))
        assert x is not None
        assert all(x >= -5) and all(x <= 5)


class TestBuildHistogram:
    def test_shape(self):
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        result = build_histogram(df, "nose", config, x_limits=(-50, 50), y_limits=(-50, 50), nbins=50)
        assert result is not None
        assert result["H_counts"].shape == (50, 50)
        assert result["H_proportion"].sum() == pytest.approx(1.0, abs=1e-6)

    def test_no_data_returns_none(self):
        df = _make_dlc_df()
        config = {"bodyparts": {"tongue": {"likelihood_threshold": 0.80}}}
        result = build_histogram(df, "tongue", config, x_limits=(-50, 50), y_limits=(-50, 50))
        assert result is None


class TestBuildStatsGrid:
    def test_grid_dimensions(self):
        df = _make_dlc_df(5000)
        config = {
            "target_bin_size_x": 5.0,
            "target_bin_size_y": 5.0,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        result = build_stats_grid(df, "nose", config)
        assert result is not None
        assert result["nx"] >= 5
        assert result["ny"] >= 5
        assert result["H_counts"].shape == (result["nx"], result["ny"])

    def test_dx_dy_match_target(self):
        df = _make_dlc_df(5000)
        config = {
            "target_bin_size_x": 10.0,
            "target_bin_size_y": 10.0,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        result = build_stats_grid(df, "nose", config)
        assert result is not None
        # dx should be close to target (not exact due to rounding)
        assert 5.0 < result["dx"] < 20.0


class TestBuildBaselineHistogram:
    def test_aggregates(self):
        df = _make_dlc_df(5000)
        config = {
            "target_bin_size_x": 10.0,
            "target_bin_size_y": 10.0,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        g1 = build_stats_grid(df, "nose", config)
        g2 = build_stats_grid(df, "nose", config)
        baseline = build_baseline_histogram([g1, g2])
        assert baseline["H_pre_counts"].shape == g1["H_counts"].shape
        # Double the counts (same data twice)
        np.testing.assert_allclose(baseline["H_pre_counts"], g1["H_counts"] * 2)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            build_baseline_histogram([])
