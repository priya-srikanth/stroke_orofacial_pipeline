"""Tests for stroke_orofacial.dlc_spatial.heatmaps."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # non-interactive backend for tests

from stroke_orofacial.dlc_spatial.heatmaps import plot_heatmap, save_heatmap_png


def _make_dlc_df(n: int = 1000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "nose_x": rng.normal(0, 10, n).astype(np.float32),
        "nose_y": rng.normal(0, 10, n).astype(np.float32),
        "nose_likelihood": np.full(n, 0.95, dtype=np.float32),
    })


class TestPlotHeatmap:
    def test_returns_figure(self):
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        fig = plot_heatmap(df, "nose", config, x_limits=(-50, 50), y_limits=(-50, 50))
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_empty_bodypart_still_returns_figure(self):
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"tongue": {"likelihood_threshold": 0.80}}}
        fig = plot_heatmap(df, "tongue", config, x_limits=(-50, 50), y_limits=(-50, 50))
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)


class TestSaveHeatmapPng:
    def test_saves_file(self, tmp_path):
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        fig = plot_heatmap(df, "nose", config, x_limits=(-50, 50), y_limits=(-50, 50))
        out = tmp_path / "test_heatmap.png"
        save_heatmap_png(fig, out, dpi=72)
        assert out.exists()
        assert out.stat().st_size > 1000  # non-trivial PNG
