"""Tests for stroke_orofacial.dlc_kinematics.cleaned_traces_io.

Phase 7e.4 — shared baseline-fill mask loader for spatial routing.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_kinematics.cleaned_traces_io import (
    load_baseline_fill_mask,
)
from stroke_orofacial.paths import PathResolver


@pytest.fixture
def resolver(tmp_path) -> PathResolver:
    """PathResolver pointed at a tmp output_root so tests never touch
    the real pipeline_outputs tree (per CLAUDE.md repo conventions)."""
    return PathResolver(output_root=tmp_path)


def _write_cleaned_trace_parquet(
    resolver: PathResolver, animal: str, date: dt.date,
    bodypart: str, n_frames: int, baseline_fill_indices: list[int],
) -> None:
    """Write a minimal cleaned_traces parquet at the resolver path with
    is_baseline_fill=True at the given frame indices, False elsewhere."""
    is_bf = np.zeros(n_frames, dtype=bool)
    is_bf[baseline_fill_indices] = True
    df = pd.DataFrame({
        "frame_idx": np.arange(n_frames, dtype=np.int64),
        "x_final": np.zeros(n_frames, dtype=np.float64),
        "y_final": np.zeros(n_frames, dtype=np.float64),
        "likelihood_raw": np.full(n_frames, 0.5, dtype=np.float64),
        "is_interp_fill": np.zeros(n_frames, dtype=bool),
        "is_baseline_fill": is_bf,
        "fill_method": np.zeros(n_frames, dtype=np.int8),
    })
    out = resolver.cleaned_trace(bodypart=bodypart, animal=animal, date=date)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(out), index=False)


class TestLoadBaselineFillMask:
    """Phase 7e.4 baseline-fill mask loader contract."""

    ANIMAL = "PS54"
    DATE = dt.date(2025, 5, 6)
    N_FRAMES = 100

    def test_happy_path_returns_mask_aligned_to_n_frames(self, resolver):
        _write_cleaned_trace_parquet(
            resolver, self.ANIMAL, self.DATE, "tongue",
            n_frames=self.N_FRAMES,
            baseline_fill_indices=[0, 1, 2, 50, 99],
        )
        mask = load_baseline_fill_mask(
            "tongue", self.ANIMAL, self.DATE, resolver,
            expected_n_frames=self.N_FRAMES,
        )
        assert mask.shape == (self.N_FRAMES,)
        assert mask.dtype == bool
        assert mask.sum() == 5
        assert mask[0] and mask[1] and mask[2] and mask[50] and mask[99]

    def test_missing_parquet_raises_file_not_found(self, resolver):
        with pytest.raises(FileNotFoundError, match="cleaned_traces parquet"):
            load_baseline_fill_mask(
                "tongue", self.ANIMAL, self.DATE, resolver,
                expected_n_frames=self.N_FRAMES,
            )

    def test_length_mismatch_raises_value_error(self, resolver):
        _write_cleaned_trace_parquet(
            resolver, self.ANIMAL, self.DATE, "tongue",
            n_frames=self.N_FRAMES, baseline_fill_indices=[],
        )
        with pytest.raises(ValueError, match="cleaned_traces length"):
            load_baseline_fill_mask(
                "tongue", self.ANIMAL, self.DATE, resolver,
                expected_n_frames=self.N_FRAMES + 1,
            )

    def test_non_dense_frame_idx_raises_value_error(self, resolver, tmp_path):
        # Build a parquet with a shuffled frame_idx (non-dense) at the
        # resolver path directly so we bypass _write_cleaned_trace_parquet's
        # dense arange().
        n = 50
        df = pd.DataFrame({
            "frame_idx": np.flip(np.arange(n)),  # 49..0 not 0..49
            "x_final": np.zeros(n), "y_final": np.zeros(n),
            "likelihood_raw": np.full(n, 0.5),
            "is_interp_fill": np.zeros(n, dtype=bool),
            "is_baseline_fill": np.zeros(n, dtype=bool),
            "fill_method": np.zeros(n, dtype=np.int8),
        })
        out = resolver.cleaned_trace(
            bodypart="jaw", animal=self.ANIMAL, date=self.DATE,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(str(out), index=False)
        with pytest.raises(ValueError, match="frame_idx is not dense"):
            load_baseline_fill_mask(
                "jaw", self.ANIMAL, self.DATE, resolver,
                expected_n_frames=n,
            )

    def test_all_false_mask_is_no_op_equivalent(self, resolver):
        """When no frames are baseline-fill, the mask is all-False and
        the spatial routing falls through to behave like legacy."""
        _write_cleaned_trace_parquet(
            resolver, self.ANIMAL, self.DATE, "jaw",
            n_frames=self.N_FRAMES, baseline_fill_indices=[],
        )
        mask = load_baseline_fill_mask(
            "jaw", self.ANIMAL, self.DATE, resolver,
            expected_n_frames=self.N_FRAMES,
        )
        assert not mask.any()
