"""Tests for stroke_orofacial.dlc_spatial.heatmaps."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd

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


class TestPlotHeatmapCenterMode:
    """Phase 4.5-lite: plot_heatmap consumes per_center_mode + x_range."""

    def test_center_mode_sets_axis_limits(self):
        import matplotlib.pyplot as plt
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 50,
            "bodyparts": {"nose": {
                "likelihood_threshold": 0.80,
                "per_center_mode": {
                    "eye_midpoint": {"xlim": [-40, 40], "ylim": [-40, 40]},
                },
            }},
        }
        fig = plot_heatmap(df, "nose", config, center_mode="eye_midpoint")
        ax = fig.axes[0]
        assert ax.get_xlim() == (-40, 40)
        # y-axis inverted per camera-view convention: get_ylim returns (high, low).
        assert ax.get_ylim() == (40, -40)
        plt.close(fig)

    def test_y_axis_inverted_by_default(self):
        """Camera-view convention: higher y = lower on plot."""
        import matplotlib.pyplot as plt
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        fig = plot_heatmap(df, "nose", config, x_limits=(-50, 50), y_limits=(-50, 50))
        ax = fig.axes[0]
        y_lo, y_hi = ax.get_ylim()
        assert y_lo > y_hi, "y-axis should be inverted for camera-view convention"
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
