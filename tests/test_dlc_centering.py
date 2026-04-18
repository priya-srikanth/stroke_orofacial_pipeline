"""Tests for stroke_orofacial.dlc_io.centering."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_io.centering import (
    CenterMode,
    apply_centering,
    compute_center,
)


def _make_synthetic_dlc(n: int = 100) -> pd.DataFrame:
    """Create a synthetic DLC DataFrame with 13 bodyparts."""
    rng = np.random.default_rng(42)
    cols = {}
    bodyparts = [
        "nose", "jaw", "tongue",
        "L_whiskers_1", "L_whiskers_2", "L_whiskers_3",
        "R_whiskers_1", "R_whiskers_2", "R_whiskers_3",
        "L_eye", "R_eye", "L_spout", "R_spout",
    ]
    for bp in bodyparts:
        cols[f"{bp}_x"] = (rng.standard_normal(n) * 10 + 100).astype(np.float32)
        cols[f"{bp}_y"] = (rng.standard_normal(n) * 10 + 200).astype(np.float32)
        cols[f"{bp}_likelihood"] = np.full(n, 0.95, dtype=np.float32)
    return pd.DataFrame(cols)


class TestComputeCenter:
    def test_nose_mode(self):
        df = _make_synthetic_dlc()
        cx, cy, mode = compute_center(df, "nose", likelihood_threshold=0.7)
        assert mode == "nose"
        assert np.isfinite(cx) and np.isfinite(cy)
        # Center should be near the median of nose coords
        np.testing.assert_allclose(cx, df["nose_x"].median(), atol=0.01)

    def test_spout_midpoint_mode(self):
        df = _make_synthetic_dlc()
        cx, cy, mode = compute_center(df, "spout_midpoint", likelihood_threshold=0.7)
        assert mode == "spout_midpoint"
        expected_cx = 0.5 * (df["L_spout_x"].median() + df["R_spout_x"].median())
        np.testing.assert_allclose(cx, expected_cx, atol=0.01)

    def test_eye_midpoint_mode(self):
        df = _make_synthetic_dlc()
        cx, cy, mode = compute_center(df, "eye_midpoint", likelihood_threshold=0.7)
        assert mode == "eye_midpoint"
        expected_cx = 0.5 * (df["L_eye_x"].median() + df["R_eye_x"].median())
        np.testing.assert_allclose(cx, expected_cx, atol=0.01)

    def test_enum_and_string_equivalent(self):
        df = _make_synthetic_dlc()
        cx1, cy1, _ = compute_center(df, CenterMode.NOSE, 0.7)
        cx2, cy2, _ = compute_center(df, "nose", 0.7)
        assert cx1 == cx2 and cy1 == cy2

    def test_low_likelihood_raises(self):
        df = _make_synthetic_dlc()
        df["nose_likelihood"] = 0.1  # all below threshold
        with pytest.raises(RuntimeError, match="insufficient valid nose"):
            compute_center(df, "nose", likelihood_threshold=0.5)

    def test_invalid_mode_raises(self):
        df = _make_synthetic_dlc()
        with pytest.raises(ValueError):
            compute_center(df, "invalid_mode", 0.7)


class TestApplyCentering:
    def test_subtracts_from_xy_only(self):
        df = _make_synthetic_dlc(10)
        cx, cy = 100.0, 200.0
        result = apply_centering(df, cx, cy)
        # x columns shifted by -100, y by -200
        np.testing.assert_allclose(
            result["nose_x"].values, df["nose_x"].values - 100.0, atol=1e-4
        )
        np.testing.assert_allclose(
            result["nose_y"].values, df["nose_y"].values - 200.0, atol=1e-4
        )
        # Likelihood unchanged
        np.testing.assert_array_equal(result["nose_likelihood"], df["nose_likelihood"])

    def test_preserves_float32(self):
        df = _make_synthetic_dlc(10)
        result = apply_centering(df, 100.0, 200.0)
        assert all(dt == np.float32 for dt in result.dtypes)

    def test_preserves_shape(self):
        df = _make_synthetic_dlc(50)
        result = apply_centering(df, 0.0, 0.0)
        assert result.shape == df.shape
