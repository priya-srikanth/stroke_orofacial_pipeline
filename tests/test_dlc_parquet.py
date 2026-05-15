"""Tests for stroke_orofacial.dlc_io.parquet."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from stroke_orofacial.dlc_io.parquet import (
    _param_sig,
    build_centered_parquet,
    read_centered_parquet,
    write_centered_parquet,
)
from stroke_orofacial.manifest import SessionManifest
from stroke_orofacial.paths import PathResolver


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


class TestBuildCenteredParquetRaisesOnEmptyDlc:
    """Phase 4 is the first DLC-required orchestrator (per Phase 6.7
    architectural decision). build_centered_parquet must raise a clear
    error if the manifest has no DLC files."""

    def test_raises_when_manifest_has_no_dlc(self, tmp_path):
        resolver = MagicMock(spec=PathResolver)
        resolver.pipeline_outputs.return_value = tmp_path
        manifest = SessionManifest(
            session_id="PS46_20250101",
            animal="PS46",
            date=datetime.date(2025, 1, 1),
            day_relative_to_stroke=-71,
            phase="baseline",
            wavesurfer_file=None,
            dlc_h5_files=[],
            dlc_csv_files=[],
        )
        with pytest.raises(FileNotFoundError, match="dlc_h5_files"):
            build_centered_parquet(manifest, "nose", resolver, params={})


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
        leg_files = sorted(leg_dir.glob("*2025-03-07T*_filtered.h5.intermediate.*.parquet"))
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


_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")


@pytest.mark.skipif(
    not _MOUNT.exists() or not _DLC_DIR.exists(),
    reason="MICROSCOPE mount or DLC data not available",
)
class TestBuildCenteredParquetWithManifest:
    """Closes the test-coverage gap noted in the 6.7 plan: there was
    previously NO test exercising the build_centered_parquet orchestrator
    end-to-end. Adds one for the manifest-first path."""

    def test_skip_path_via_manifest(self, monkeypatch):
        """build_centered_parquet(manifest, 'nose', resolver) succeeds on
        an existing parquet (skip path). Outputs already exist on
        MICROSCOPE — the integration-parity tests above wrote them."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.manifest import build_manifest

        resolver = PathResolver()
        animal_info = get_animal("PS46")
        manifest = build_manifest("PS46", datetime.date(2025, 3, 7), resolver, animal_info)
        assert len(manifest.dlc_h5_files) >= 1

        result = build_centered_parquet(
            manifest, "nose", resolver, overwrite="skip",
        )
        # Skip path returns the existing parquet path (not None)
        assert result is not None
        assert result.exists()
        assert result.name.endswith(".c23dc714.parquet")
