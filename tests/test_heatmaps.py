"""Tests for stroke_orofacial.dlc_spatial.heatmaps."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # non-interactive backend for tests

from stroke_orofacial.dlc_spatial.heatmaps import (
    plot_heatmap,
    save_heatmap_npz,
    save_heatmap_png,
)
from stroke_orofacial.dlc_spatial.pixel_bins import build_histogram


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


class TestSaveHeatmapNpz:
    """save_heatmap_npz wraps build_histogram and writes the dict to NPZ.

    Per DECISIONS.md "2026-04-19 Save fine-grid heatmap NPZ" — saves the
    fine-grid array alongside the PNG so future figure tweaks and Phase 9
    fine-resolution stats don't have to recompute from parquet.
    """

    def test_saves_file_with_expected_keys(self, tmp_path):
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 100,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        out = tmp_path / "test_heatmap.npz"
        ok = save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=100,
        )
        assert ok is True
        assert out.exists()

        loaded = np.load(out)
        for key in (
            "H_counts", "H_proportion", "xedges", "yedges",
            "x_limits", "y_limits", "nbins",
        ):
            assert key in loaded.files, f"missing key {key} in NPZ"

        # Bin shapes are nbins x nbins (counts) and nbins+1 (edges)
        assert loaded["H_counts"].shape == (100, 100)
        assert loaded["xedges"].shape == (101,)
        assert loaded["yedges"].shape == (101,)
        assert int(loaded["nbins"]) == 100

    def test_matches_build_histogram_directly(self, tmp_path):
        """Parity guard: NPZ contents equal what build_histogram returns
        when called with the same args. The new helper is a thin wrapper —
        any drift means the helper is computing differently than the
        existing PNG-producing pipeline reads."""
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 100,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        out = tmp_path / "test_heatmap.npz"
        save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=100,
        )
        loaded = np.load(out)

        direct = build_histogram(
            df, "nose", config,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=100,
        )
        np.testing.assert_array_equal(loaded["H_counts"], direct["H_counts"])
        np.testing.assert_array_equal(loaded["H_proportion"], direct["H_proportion"])
        np.testing.assert_array_equal(loaded["xedges"], direct["xedges"])
        np.testing.assert_array_equal(loaded["yedges"], direct["yedges"])

    def test_returns_false_when_no_valid_points(self, tmp_path):
        """Empty / all-low-likelihood data: build_histogram returns None;
        save_heatmap_npz returns False without writing a file."""
        df = _make_dlc_df()
        df["nose_likelihood"] = 0.0  # all below threshold
        config = {
            "heatmap_nbins": 50,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        out = tmp_path / "test_empty.npz"
        ok = save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50),
        )
        assert ok is False
        assert not out.exists()

    def test_nbins_param_changes_resolution(self, tmp_path):
        """nbins is exposed as an explicit per-call parameter (Priya 2026-04-20)."""
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 100,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        out_50 = tmp_path / "n50.npz"
        out_200 = tmp_path / "n200.npz"
        save_heatmap_npz(df, "nose", config, out_50,
                         x_limits=(-50, 50), y_limits=(-50, 50), nbins=50)
        save_heatmap_npz(df, "nose", config, out_200,
                         x_limits=(-50, 50), y_limits=(-50, 50), nbins=200)

        n50 = np.load(out_50)
        n200 = np.load(out_200)
        assert n50["H_counts"].shape == (50, 50)
        assert n200["H_counts"].shape == (200, 200)
        assert int(n50["nbins"]) == 50
        assert int(n200["nbins"]) == 200


# ---------------------------------------------------------------------------
# Phase 7e.4 — cleaned-traces routing on plot_heatmap + save_heatmap_npz.
# Default kwargs (mask=None, drop=False) preserve pre-7e.4 behavior; new
# kwargs apply the baseline-fill mask + lik-gate skip; NPZ schema gains
# two boolean stamps (applied_cleaned_traces_mask, dropped_likelihood_gate).
# ---------------------------------------------------------------------------


class TestSaveHeatmapNpzCleanedTracesStamps:
    """NPZ schema gains the two routing-stamp keys regardless of which
    path the caller took. Default-False stamps preserve pre-7e.4 NPZ
    semantics; default-True stamps appear when caller opts in."""

    def _df_and_config(self):
        from tests.test_heatmaps import _make_dlc_df  # use module-local fixture
        df = _make_dlc_df()
        config = {"bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        return df, config

    def test_default_stamps_are_false_false(self, tmp_path):
        df, config = self._df_and_config()
        out = tmp_path / "default.npz"
        ok = save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
        )
        assert ok
        npz = np.load(out)
        assert bool(npz["applied_cleaned_traces_mask"]) is False
        assert bool(npz["dropped_likelihood_gate"]) is False

    def test_baseline_mask_stamp_records_true(self, tmp_path):
        df, config = self._df_and_config()
        mask = np.zeros(len(df), dtype=bool)
        mask[:200] = True
        out = tmp_path / "with_mask.npz"
        ok = save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
            baseline_fill_mask=mask,
        )
        assert ok
        npz = np.load(out)
        assert bool(npz["applied_cleaned_traces_mask"]) is True
        assert bool(npz["dropped_likelihood_gate"]) is False
        # Spatial-impact sanity: ≤ pre-mask count.
        legacy_out = tmp_path / "legacy.npz"
        save_heatmap_npz(df, "nose", config, legacy_out,
                          x_limits=(-50, 50), y_limits=(-50, 50), nbins=40)
        legacy_npz = np.load(legacy_out)
        assert int(npz["H_counts"].sum()) <= int(legacy_npz["H_counts"].sum())

    def test_drop_lik_gate_stamp_records_true(self, tmp_path):
        df, config = self._df_and_config()
        df.loc[:299, "nose_likelihood"] = 0.4  # below threshold
        out = tmp_path / "drop_gate.npz"
        ok = save_heatmap_npz(
            df, "nose", config, out,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
            drop_likelihood_gate=True,
        )
        assert ok
        npz = np.load(out)
        assert bool(npz["applied_cleaned_traces_mask"]) is False
        assert bool(npz["dropped_likelihood_gate"]) is True
