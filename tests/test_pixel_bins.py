"""Tests for stroke_orofacial.dlc_spatial.pixel_bins."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_spatial.pixel_bins import (
    _get_per_center_mode_params,
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

    def test_q17_total_frames_normalization(self):
        """Phase 7c.2 Addendum #16 Q17: when ``n_total_frames`` is given,
        H_proportion = H_counts / n_total_frames (sum ≤ 1.0 = passed/total).
        When omitted, legacy normalization preserved (H/H.sum() sums to 1)."""
        df = _make_dlc_df()
        config = {"heatmap_nbins": 50, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        # Q17 path: n_total_frames > H_counts.sum() → H_proportion sums to < 1.0
        n_total = 2 * len(df)  # synthesized: total includes 2x as many "frames"
        result_q17 = build_histogram(
            df, "nose", config,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=50,
            n_total_frames=n_total,
        )
        assert result_q17 is not None
        passed = float(result_q17["H_counts"].sum())
        expected_sum = passed / n_total
        assert result_q17["H_proportion"].sum() == pytest.approx(expected_sum, abs=1e-6)
        assert result_q17["H_proportion"].sum() <= 1.0
        assert result_q17["n_total_frames"] == n_total

        # Legacy path: no n_total_frames → H_proportion sums to 1.0
        result_legacy = build_histogram(
            df, "nose", config,
            x_limits=(-50, 50), y_limits=(-50, 50), nbins=50,
        )
        assert result_legacy["H_proportion"].sum() == pytest.approx(1.0, abs=1e-6)
        assert result_legacy["n_total_frames"] is None


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


class TestGetPerCenterModeParams:
    """Phase 4.5-lite: per-(bodypart, center_mode) plotting parameters."""

    def test_returns_xlim_ylim_and_x_range(self):
        config = {
            "bodyparts": {
                "jaw": {
                    "per_center_mode": {
                        "eye_midpoint": {
                            "xlim": [-80, 80],
                            "ylim": [195, 520],
                            "x_range": [-80, 80],
                        }
                    }
                }
            }
        }
        p = _get_per_center_mode_params(config, "jaw", "eye_midpoint")
        assert p["xlim"] == (-80, 80)
        assert p["ylim"] == (195, 520)
        assert p["x_range"] == (-80, 80)

    def test_missing_x_range_returns_none(self):
        config = {"bodyparts": {"nose": {"per_center_mode": {
            "eye_midpoint": {"xlim": [-100, 95], "ylim": [100, 330]}
        }}}}
        p = _get_per_center_mode_params(config, "nose", "eye_midpoint")
        assert p["xlim"] == (-100, 95)
        assert p["x_range"] is None

    def test_none_center_mode_returns_all_none(self):
        config = {"bodyparts": {}}
        p = _get_per_center_mode_params(config, "jaw", None)
        assert p == {"xlim": None, "ylim": None, "x_range": None}

    def test_missing_bodypart_returns_all_none(self):
        config = {"bodyparts": {}}
        p = _get_per_center_mode_params(config, "ghost", "eye_midpoint")
        assert p == {"xlim": None, "ylim": None, "x_range": None}

    def test_null_per_mode_returns_all_none(self):
        """Bodyparts where per_center_mode.{mode} is explicitly null."""
        config = {"bodyparts": {"L_whiskers_2": {
            "per_center_mode": {"nose": None}
        }}}
        p = _get_per_center_mode_params(config, "L_whiskers_2", "nose")
        assert p == {"xlim": None, "ylim": None, "x_range": None}


class TestBuildHistogramCenterMode:
    """Phase 4.5-lite: build_histogram consumes per_center_mode when center_mode given."""

    def test_reads_xlim_ylim_from_config(self):
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 20,
            "bodyparts": {
                "nose": {
                    "likelihood_threshold": 0.80,
                    "per_center_mode": {
                        "eye_midpoint": {"xlim": [-30, 30], "ylim": [-30, 30]}
                    },
                }
            },
        }
        result = build_histogram(df, "nose", config, center_mode="eye_midpoint")
        assert result is not None
        assert result["extent"] == [-30, 30, -30, 30]

    def test_reads_x_range_from_config(self):
        df = _make_dlc_df()
        # Put some nose points outside a tight x_range to verify the filter.
        df.loc[:99, "nose_x"] = 500.0  # 100 points well outside x_range=(-50, 50)
        config = {
            "heatmap_nbins": 20,
            "bodyparts": {
                "nose": {
                    "likelihood_threshold": 0.80,
                    "per_center_mode": {
                        "eye_midpoint": {
                            "xlim": [-50, 50], "ylim": [-50, 50],
                            "x_range": [-50, 50],
                        }
                    },
                }
            },
        }
        result = build_histogram(df, "nose", config, center_mode="eye_midpoint")
        assert result is not None
        # Total counts should be len(df) - 100 (filtered out-of-range)
        assert result["H_counts"].sum() == len(df) - 100

    def test_explicit_kwargs_override_config(self):
        """x_limits kwarg wins over config per_center_mode."""
        df = _make_dlc_df()
        config = {
            "heatmap_nbins": 20,
            "bodyparts": {"nose": {
                "likelihood_threshold": 0.80,
                "per_center_mode": {"eye_midpoint": {
                    "xlim": [-30, 30], "ylim": [-30, 30]
                }},
            }},
        }
        result = build_histogram(
            df, "nose", config,
            center_mode="eye_midpoint",
            x_limits=(-100, 100), y_limits=(-100, 100),
        )
        assert result["extent"] == [-100, 100, -100, 100]

    def test_no_center_mode_uses_fallback_defaults(self):
        """Backward compat: when center_mode is None, use hardcoded defaults."""
        df = _make_dlc_df()
        config = {"heatmap_nbins": 20, "bodyparts": {"nose": {"likelihood_threshold": 0.80}}}
        result = build_histogram(df, "nose", config)
        # Hardcoded fallback defaults kick in.
        assert result is not None
        assert result["extent"] == [-200, 200, 50, 550]


class TestBuildStatsGridCenterMode:
    def test_x_range_applied(self):
        df = _make_dlc_df()
        df.loc[:99, "nose_x"] = 500.0
        config = {
            "target_bin_size_x": 5.0, "target_bin_size_y": 5.0,
            "bodyparts": {"nose": {
                "likelihood_threshold": 0.80,
                "per_center_mode": {"eye_midpoint": {"x_range": [-50, 50]}},
            }},
        }
        g = build_stats_grid(df, "nose", config, center_mode="eye_midpoint")
        assert g is not None
        # Filtered out-of-range → the remaining 900 points fall within x∈[-50, 50]
        assert g["H_counts"].sum() == len(df) - 100


# ---------------------------------------------------------------------------
# Phase 7e.4 — cleaned-traces routing kwargs on get_masked_xy /
# build_histogram / build_stats_grid. Default behavior (mask=None,
# drop=False) must remain byte-identical to pre-7e.4; new kwargs must
# AND `~baseline_fill_mask` into the row selector and skip the lik gate
# when drop_likelihood_gate=True.
# ---------------------------------------------------------------------------


def _make_dlc_df_with_lowlik(n: int = 1000, low_lik_frac: float = 0.3) -> pd.DataFrame:
    """Synthetic DLC DataFrame where `low_lik_frac` of frames have
    likelihood 0.4 (below the default 0.80 gate). Used to exercise
    drop_likelihood_gate."""
    df = _make_dlc_df(n=n)
    n_low = int(n * low_lik_frac)
    df.loc[:n_low - 1, "nose_likelihood"] = 0.4
    return df


class TestGetMaskedXYCleanedTracesRouting:
    """Phase 7e.4 — baseline_fill_mask + drop_likelihood_gate kwargs."""

    def test_default_behavior_byte_identical_legacy(self):
        """mask=None + drop=False must produce the same (x, y) as pre-7e.4."""
        df = _make_dlc_df()
        x_legacy, y_legacy = get_masked_xy(df, "nose", 0.80)
        x_new, y_new = get_masked_xy(
            df, "nose", 0.80,
            baseline_fill_mask=None, drop_likelihood_gate=False,
        )
        np.testing.assert_array_equal(x_legacy, x_new)
        np.testing.assert_array_equal(y_legacy, y_new)

    def test_baseline_fill_mask_excludes_marked_rows(self):
        """Frames where baseline_fill_mask=True are excluded from the output."""
        df = _make_dlc_df()
        mask = np.zeros(len(df), dtype=bool)
        mask[:300] = True  # mark first 300 as baseline-fill placeholders
        x, y = get_masked_xy(df, "nose", 0.80, baseline_fill_mask=mask)
        assert x is not None
        assert len(x) == len(df) - 300

    def test_drop_likelihood_gate_admits_below_threshold(self):
        """drop_likelihood_gate=True keeps frames where lik < threshold."""
        df = _make_dlc_df_with_lowlik(n=1000, low_lik_frac=0.3)
        x_gated, _ = get_masked_xy(df, "nose", 0.80)
        x_open, _ = get_masked_xy(df, "nose", 0.80, drop_likelihood_gate=True)
        assert len(x_gated) == 700  # 30% dropped by lik gate
        assert len(x_open) == 1000  # all frames admitted

    def test_combined_R3_variant_baseline_AND_drop_gate(self):
        """F-P-1 R3: drop lik gate AND exclude baseline-fill."""
        df = _make_dlc_df_with_lowlik(n=1000, low_lik_frac=0.3)
        mask = np.zeros(len(df), dtype=bool)
        mask[:300] = True  # overlap fully with the low-lik 30%
        x, _ = get_masked_xy(
            df, "nose", 0.80,
            baseline_fill_mask=mask, drop_likelihood_gate=True,
        )
        assert x is not None
        # baseline-fill exclusion overrides the lik admission for those rows;
        # 300 baseline-marked dropped → 700 remain
        assert len(x) == 700

    def test_baseline_mask_length_mismatch_raises(self):
        df = _make_dlc_df()
        mask = np.zeros(len(df) - 5, dtype=bool)  # off by 5
        with pytest.raises(ValueError, match="baseline_fill_mask length"):
            get_masked_xy(df, "nose", 0.80, baseline_fill_mask=mask)


class TestBuildHistogramCleanedTracesRouting:
    """Phase 7e.4 — passthrough on build_histogram."""

    def _config(self):
        return {
            "heatmap_nbins": 40,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }

    def test_default_byte_identical_legacy(self):
        df = _make_dlc_df()
        cfg = self._config()
        h_legacy = build_histogram(df, "nose", cfg,
                                    x_limits=(-50, 50), y_limits=(-50, 50), nbins=40)
        h_new = build_histogram(df, "nose", cfg,
                                 x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
                                 baseline_fill_mask=None, drop_likelihood_gate=False)
        np.testing.assert_array_equal(h_legacy["H_counts"], h_new["H_counts"])

    def test_baseline_mask_shrinks_count(self):
        df = _make_dlc_df()
        cfg = self._config()
        mask = np.zeros(len(df), dtype=bool)
        mask[:300] = True
        h = build_histogram(df, "nose", cfg,
                             x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
                             baseline_fill_mask=mask)
        assert h is not None
        assert int(h["H_counts"].sum()) == len(df) - 300

    def test_drop_lik_gate_expands_count(self):
        df = _make_dlc_df_with_lowlik(n=1000, low_lik_frac=0.3)
        cfg = self._config()
        h_gated = build_histogram(df, "nose", cfg,
                                   x_limits=(-50, 50), y_limits=(-50, 50), nbins=40)
        h_open = build_histogram(df, "nose", cfg,
                                  x_limits=(-50, 50), y_limits=(-50, 50), nbins=40,
                                  drop_likelihood_gate=True)
        assert int(h_open["H_counts"].sum()) > int(h_gated["H_counts"].sum())
        assert int(h_open["H_counts"].sum()) == len(df)


class TestBuildStatsGridCleanedTracesRouting:
    """Phase 7e.4 — passthrough on build_stats_grid."""

    def test_baseline_mask_passthrough(self):
        df = _make_dlc_df()
        config = {
            "target_bin_size_x": 5.0, "target_bin_size_y": 5.0,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        mask = np.zeros(len(df), dtype=bool)
        mask[:300] = True
        g = build_stats_grid(df, "nose", config, baseline_fill_mask=mask)
        assert g is not None
        assert int(g["H_counts"].sum()) == len(df) - 300

    def test_drop_lik_gate_passthrough(self):
        df = _make_dlc_df_with_lowlik(n=1000, low_lik_frac=0.3)
        config = {
            "target_bin_size_x": 5.0, "target_bin_size_y": 5.0,
            "bodyparts": {"nose": {"likelihood_threshold": 0.80}},
        }
        g_gated = build_stats_grid(df, "nose", config)
        g_open = build_stats_grid(df, "nose", config, drop_likelihood_gate=True)
        assert int(g_open["H_counts"].sum()) > int(g_gated["H_counts"].sum())
