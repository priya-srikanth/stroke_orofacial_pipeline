"""Tests for stroke_orofacial.alignment.templates and SessionManifest integration."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.alignment.templates import (
    discover_video_files,
    load_alignment_template,
    pick_camera_csv,
)


class TestPickCameraCsv:
    def test_finds_csv(self, tmp_path):
        (tmp_path / "timestamp2_2025-03-07T11_50_40.csv").touch()
        result = pick_camera_csv(tmp_path, cam_idx=2)
        assert result.name == "timestamp2_2025-03-07T11_50_40.csv"

    def test_picks_latest(self, tmp_path):
        (tmp_path / "timestamp2_2025-03-07T11_50_40.csv").touch()
        (tmp_path / "timestamp2_2025-03-07T12_00_00.csv").touch()
        result = pick_camera_csv(tmp_path, cam_idx=2)
        assert result.name == "timestamp2_2025-03-07T12_00_00.csv"

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            pick_camera_csv(tmp_path / "nonexistent", cam_idx=2)

    def test_no_match_raises(self, tmp_path):
        (tmp_path / "timestamp1_something.csv").touch()
        with pytest.raises(FileNotFoundError, match="cam3"):
            pick_camera_csv(tmp_path, cam_idx=3)


class TestDiscoverVideoFiles:
    def test_finds_videos(self, tmp_path):
        (tmp_path / "video2_2025-03-07T11_50_41.avi").touch()
        result = discover_video_files(tmp_path, cam_idx=2)
        assert len(result) == 1
        assert result[0].name == "video2_2025-03-07T11_50_41.avi"

    def test_empty_for_missing_dir(self, tmp_path):
        result = discover_video_files(tmp_path / "nonexistent", cam_idx=2)
        assert result == []

    def test_filters_by_cam_idx(self, tmp_path):
        (tmp_path / "video1_foo.avi").touch()
        (tmp_path / "video2_foo.avi").touch()
        result = discover_video_files(tmp_path, cam_idx=2)
        assert len(result) == 1
        assert "video2" in result[0].name


class TestLoadAlignmentTemplate:
    def test_loads_npz(self, tmp_path):
        path = tmp_path / "test.npz"
        np.savez(path, slope=4.0, intercept=-100.0)
        result = load_alignment_template(path)
        assert float(result["slope"]) == 4.0

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_alignment_template(tmp_path / "nonexistent.npz")


# ---- Integration: SessionManifest populates wavesurfer_file and video_files ----

_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")
_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)
_CAMERA = Path(
    "/Volumes/Neurobio/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera"
)


@pytest.mark.skipif(
    not _MOUNT.exists()
    or not (_WS_LOCAL / "20250307" / "PS46").exists()
    or not (_CAMERA / "20250307" / "PS46").exists(),
    reason="MICROSCOPE mount, wavesurfer data, or camera data not available",
)
class TestSessionManifestIntegration:
    def test_manifest_populates_ws_and_video(self, monkeypatch):
        """build_manifest returns wavesurfer_file and video_files (amendment 3)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import AnimalInfo, EpochBoundaries
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            epoch_boundaries=EpochBoundaries(1, 4, 5),
        )
        manifest = build_manifest("PS46", datetime.date(2025, 3, 7), resolver, info)

        # wavesurfer_file should be populated and exist
        assert manifest.wavesurfer_file is not None
        assert manifest.wavesurfer_file.exists()
        assert manifest.wavesurfer_file.suffix == ".h5"

        # video_files should be populated with at least one .avi
        assert len(manifest.video_files) >= 1
        for vf in manifest.video_files:
            assert vf.exists()
            assert vf.suffix == ".avi"
            assert "video2" in vf.name
