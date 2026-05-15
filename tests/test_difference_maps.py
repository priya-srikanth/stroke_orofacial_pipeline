"""Tests for stroke_orofacial.dlc_spatial.difference_maps."""

from __future__ import annotations


import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from stroke_orofacial.dlc_spatial.difference_maps import (
    compute_difference_map,
    plot_difference_map,
    save_difference_map_png,
)


class TestComputeDifferenceMap:
    def test_basic_subtraction(self):
        post = np.array([[10, 20], [30, 40]], dtype=np.float64)
        base = np.array([[5, 10], [15, 20]], dtype=np.float64)
        diff = compute_difference_map(post, base, mode="counts")
        np.testing.assert_array_equal(diff, [[5, 10], [15, 20]])

    def test_proportion_mode(self):
        post = np.array([[0.3, 0.2], [0.1, 0.4]], dtype=np.float64)
        base = np.array([[0.25, 0.25], [0.25, 0.25]], dtype=np.float64)
        diff = compute_difference_map(post, base, mode="proportion")
        np.testing.assert_allclose(diff, [[0.05, -0.05], [-0.15, 0.15]])

    def test_shape_mismatch_raises(self):
        post = np.zeros((3, 3))
        base = np.zeros((4, 4))
        with pytest.raises(ValueError, match="Shape mismatch"):
            compute_difference_map(post, base)


class TestPlotDifferenceMap:
    def test_returns_figure(self):
        diff = np.random.randn(10, 10)
        extent = [-50, 50, -50, 50]
        fig = plot_difference_map(diff, extent, "nose", title="test")
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)


class TestSaveDifferenceMapPng:
    def test_saves_file(self, tmp_path):
        diff = np.random.randn(10, 10)
        extent = [-50, 50, -50, 50]
        fig = plot_difference_map(diff, extent, "nose")
        out = tmp_path / "test_diff.png"
        save_difference_map_png(fig, out, dpi=72)
        assert out.exists()
        assert out.stat().st_size > 1000
