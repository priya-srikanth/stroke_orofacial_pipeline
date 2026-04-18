"""Tests for stroke_orofacial.dlc_io.parquet."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_io.parquet import (
    _param_sig,
    read_centered_parquet,
    write_centered_parquet,
)


class TestParamSig:
    def test_nose_hash(self):
        sig = _param_sig("nose", 0.7)
        assert sig == "c23dc714"  # matches legacy

    def test_spout_midpoint_hash(self):
        sig = _param_sig("spout_midpoint", 0.7)
        assert sig == "2a6efb6a"

    def test_eye_midpoint_hash(self):
        sig = _param_sig("eye_midpoint", 0.7)
        assert sig == "b13af51c"

    def test_different_threshold_different_hash(self):
        sig1 = _param_sig("nose", 0.7)
        sig2 = _param_sig("nose", 0.5)
        assert sig1 != sig2


class TestWriteAndReadParquet:
    def test_roundtrip(self, tmp_path):
        df = pd.DataFrame({
            "nose_x": np.array([1.0, 2.0], dtype=np.float32),
            "nose_y": np.array([3.0, 4.0], dtype=np.float32),
        })
        path = tmp_path / "test.parquet"
        written = write_centered_parquet(df, path)
        assert written is True
        assert path.exists()

        loaded = read_centered_parquet(path)
        pd.testing.assert_frame_equal(loaded, df)

    def test_skip_existing(self, tmp_path):
        df = pd.DataFrame({"a": [1.0]})
        path = tmp_path / "test.parquet"
        write_centered_parquet(df, path)
        written_again = write_centered_parquet(df, path)
        assert written_again is False  # skipped

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_centered_parquet(tmp_path / "nonexistent.parquet")


# ---- Integration: parity against legacy parquets ----

_DLC_DIR = Path("/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46")
_V2 = Path("/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/dlc_analysis")


@pytest.mark.skipif(
    not _DLC_DIR.exists() or not _V2.exists(),
    reason="DLC data or stroke_orofacial_pipeline_outputs not available",
)
class TestIntegrationParity:
    @pytest.mark.parametrize("mode,legacy_dir,expected_hash", [
        ("nose", "_dlc_cache_centered_nose", "c23dc714"),
        ("spout_midpoint", "_dlc_cache_centered_spout_midpoint", "2a6efb6a"),
        ("eye_midpoint", "_dlc_cache_centered_eye_midpoint", "b13af51c"),
    ])
    def test_parity_ps46_20250307(self, mode, legacy_dir, expected_hash):
        from stroke_orofacial.dlc_io.loaders import discover_dlc_filtered_files, read_dlc

        # Source frame count
        h5_files = discover_dlc_filtered_files(_DLC_DIR, "20250307")
        source_n = read_dlc(h5_files[0]).shape[0]

        # New parquet
        new_dir = _V2 / f"centered_{mode}" / "PS46"
        new_files = sorted(new_dir.glob(f"*2025-03-07T*_filtered.h5.intermediate.{expected_hash}.parquet"))
        assert len(new_files) >= 1, f"No new parquet found for {mode}"
        new_df = pd.read_parquet(new_files[0])

        # Legacy parquet
        leg_dir = _DLC_DIR / legacy_dir
        leg_files = sorted(leg_dir.glob(f"*2025-03-07T*_filtered.h5.intermediate.*.parquet"))
        assert len(leg_files) >= 1, f"No legacy parquet found for {mode}"
        legacy_df = pd.read_parquet(leg_files[0])

        # Frame count assertions (Amendment 3)
        assert new_df.shape[0] == source_n, (
            f"New frame count {new_df.shape[0]} != source {source_n}"
        )
        assert new_df.shape[0] == legacy_df.shape[0], (
            f"New frame count {new_df.shape[0]} != legacy {legacy_df.shape[0]}"
        )

        # Schema match
        assert list(new_df.columns) == list(legacy_df.columns)
        assert all(new_df.dtypes == legacy_df.dtypes)

        # Value match
        pd.testing.assert_frame_equal(new_df, legacy_df, check_dtype=True, atol=1e-6)
