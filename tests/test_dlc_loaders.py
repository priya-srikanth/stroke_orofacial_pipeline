"""Tests for stroke_orofacial.dlc_io.loaders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.dlc_io.loaders import discover_dlc_filtered_files, read_dlc


class TestDiscoverDlcFilteredFiles:
    def test_finds_filtered_h5(self, tmp_path):
        (tmp_path / "video2_2025-03-07T11_50_41DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5").touch()
        (tmp_path / "video2_2025-03-07T11_50_41DLC_Resnet50_video2Jan26shuffle5_snapshot_060.h5").touch()
        result = discover_dlc_filtered_files(tmp_path, "20250307")
        assert len(result) == 1
        assert "_filtered.h5" in result[0].name

    def test_no_match(self, tmp_path):
        (tmp_path / "video2_2025-03-08T_filtered.h5").touch()
        result = discover_dlc_filtered_files(tmp_path, "20250307")
        assert result == []


class TestReadDlc:
    def test_reads_csv_fallback(self, tmp_path):
        """Read a synthetic DLC CSV with 3-level header."""
        # Build a minimal DLC CSV: scorer/bodypart/coord header
        header = [
            "scorer,scorer,scorer",
            "nose,nose,nose",
            "x,y,likelihood",
        ]
        rows = ["1.0,2.0,0.95", "3.0,4.0,0.90"]
        csv_path = tmp_path / "test_filtered.csv"
        csv_path.write_text("\n".join(header + rows))

        df = read_dlc(csv_path)
        assert "nose_x" in df.columns
        assert "nose_y" in df.columns
        assert "nose_likelihood" in df.columns
        assert df["nose_x"].dtype == np.float32
        assert len(df) == 2

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_dlc(tmp_path / "nonexistent.h5")


# ---- Integration (requires real DLC data) ----

_DLC_DIR = Path("/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46")


@pytest.mark.skipif(
    not _DLC_DIR.exists(),
    reason="DLC data not available on MICROSCOPE",
)
class TestIntegrationDlcLoader:
    def test_read_real_h5(self):
        files = discover_dlc_filtered_files(_DLC_DIR, "20250307")
        assert len(files) >= 1
        df = read_dlc(files[0])
        assert df.shape[1] == 39
        assert all(dt == np.float32 for dt in df.dtypes)
        assert df.shape[0] > 900000  # ~931K frames expected
        assert "nose_x" in df.columns
        assert "tongue_likelihood" in df.columns
