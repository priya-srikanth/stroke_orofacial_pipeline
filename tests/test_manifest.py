"""Tests for stroke_orofacial.manifest."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stroke_orofacial.animals import AnimalInfo, Exclusion
from stroke_orofacial.manifest import (
    build_manifest,
    _discover_dlc_files,
)
from stroke_orofacial.paths import PathResolver


@pytest.fixture()
def mock_dlc_dir(tmp_path: Path) -> Path:
    """Create a fake DLC directory with files for 2025-03-07."""
    dlc_dir = tmp_path / "PS46"
    dlc_dir.mkdir()
    # Create filtered DLC files matching the real naming pattern
    base = "video2_2025-03-07T12_11_32DLC_Resnet50_video2Jan26shuffle5_snapshot_060"
    (dlc_dir / f"{base}_filtered.h5").touch()
    (dlc_dir / f"{base}_filtered.csv").touch()
    # Also create unfiltered files (should not be picked up)
    (dlc_dir / f"{base}.h5").touch()
    (dlc_dir / f"{base}.csv").touch()
    return dlc_dir


@pytest.fixture()
def mock_alignment_dir(tmp_path: Path) -> Path:
    """Create a fake alignment template directory."""
    tmpl_dir = tmp_path / "alignment_templates" / "cam2" / "PS46"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "20250307.npz").touch()
    return tmp_path / "alignment_templates"


@pytest.fixture()
def ps46_info() -> AnimalInfo:
    return AnimalInfo(
        animal_id="PS46",
        stroke_date=datetime.date(2025, 3, 13),
        session_start=datetime.date(2025, 3, 7),
        session_end=datetime.date(2025, 4, 6),
    )


@pytest.fixture()
def mock_resolver(tmp_path, mock_dlc_dir, mock_alignment_dir) -> MagicMock:
    """Create a mock PathResolver that points to tmp_path fixtures."""
    resolver = MagicMock(spec=PathResolver)
    resolver.dlc_output_dir.return_value = mock_dlc_dir
    resolver.alignment_template.return_value = (
        mock_alignment_dir / "cam2" / "PS46" / "20250307.npz"
    )
    return resolver


class TestDiscoverDlcFiles:
    def test_finds_filtered_files(self, mock_dlc_dir):
        h5s, csvs = _discover_dlc_files(mock_dlc_dir, datetime.date(2025, 3, 7))
        assert len(h5s) == 1
        assert len(csvs) == 1
        assert "_filtered.h5" in h5s[0].name
        assert "_filtered.csv" in csvs[0].name

    def test_no_files_for_missing_date(self, mock_dlc_dir):
        h5s, csvs = _discover_dlc_files(mock_dlc_dir, datetime.date(2025, 1, 1))
        assert h5s == []
        assert csvs == []


class TestBuildManifest:
    def test_basic_manifest(self, mock_resolver, ps46_info):
        manifest = build_manifest(
            "PS46",
            datetime.date(2025, 3, 7),
            mock_resolver,
            ps46_info,
        )
        assert manifest.session_id == "PS46_20250307"
        assert manifest.animal == "PS46"
        assert manifest.date == datetime.date(2025, 3, 7)
        assert manifest.day_relative_to_stroke == -6
        assert manifest.phase == "baseline"
        assert len(manifest.dlc_h5_files) == 1
        assert len(manifest.dlc_csv_files) == 1
        assert manifest.alignment_template is not None
        assert manifest.excluded is False
        assert manifest.wavesurfer_file is None
        assert manifest.video_files == []

    def test_post_stroke_phase(self, mock_resolver, tmp_path):
        """A date after stroke should have phase='post_stroke'."""
        # Create DLC files for 2025-03-20
        dlc_dir = mock_resolver.dlc_output_dir.return_value
        base = "video2_2025-03-20T10_00_00DLC_Resnet50_video2Jan26shuffle5_snapshot_060"
        (dlc_dir / f"{base}_filtered.h5").touch()
        (dlc_dir / f"{base}_filtered.csv").touch()
        # Point alignment template to a non-existent file
        mock_resolver.alignment_template.return_value = tmp_path / "nonexistent.npz"

        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
        )
        manifest = build_manifest("PS46", datetime.date(2025, 3, 20), mock_resolver, info)
        assert manifest.phase == "post_stroke"
        assert manifest.day_relative_to_stroke == 7
        assert manifest.alignment_template is None  # non-existent

    def test_excluded_session_top_level_scope(self, mock_resolver):
        """An exclusion scoped to [dlc, spout_behavior] fires for any
        analysis_context under either of those namespaces."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 3, 7),
                    "bad frames",
                    ["dlc", "spout_behavior"],
                ),
            ],
        )
        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.spatial",
        )
        assert manifest.excluded is True
        assert manifest.exclusion_reason == "bad frames"

    def test_analysis_specific_exclusion(self, mock_resolver):
        """Bodypart-scoped exclusion: prefix-match means
        [dlc.kinematics.tongue] hits dlc.kinematics.tongue but not
        dlc.kinematics.jaw."""
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
            exclusions=[
                Exclusion(
                    datetime.date(2025, 3, 7),
                    "tongue issue",
                    ["dlc.kinematics.tongue"],
                ),
            ],
        )
        # Excluded for tongue kinematics
        m = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.kinematics.tongue",
        )
        assert m.excluded is True
        # Not excluded for jaw kinematics
        m = build_manifest(
            "PS46", datetime.date(2025, 3, 7), mock_resolver, info,
            analysis_context="dlc.kinematics.jaw",
        )
        assert m.excluded is False

    def test_missing_dlc_dir_yields_empty_lists(self, ps46_info, tmp_path):
        """When DLC dir is missing, build_manifest emits a manifest with
        empty dlc_h5_files / dlc_csv_files (no raise).

        DLC is symmetric with wavesurfer/video: discoverable-if-present,
        empty-if-not. The "I need DLC" assertion belongs to each
        DLC-consuming orchestrator, not to manifest construction.
        """
        resolver = MagicMock(spec=PathResolver)
        resolver.dlc_output_dir.return_value = Path("/nonexistent/path")
        # Alignment template path is constructed but won't exist
        resolver.alignment_template.return_value = tmp_path / "no_template.npz"

        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), resolver, ps46_info
        )
        assert manifest.session_id == "PS46_20250307"
        assert manifest.animal == "PS46"
        assert manifest.dlc_h5_files == []
        assert manifest.dlc_csv_files == []
        assert manifest.alignment_template is None

    def test_no_dlc_files_yields_empty_lists(self, mock_resolver, ps46_info):
        """When DLC dir exists but no filtered files match the date,
        build_manifest emits empty lists (no raise)."""
        # Date with no matching files in mock_dlc_dir
        manifest = build_manifest(
            "PS46", datetime.date(2025, 1, 1), mock_resolver, ps46_info,
        )
        assert manifest.session_id == "PS46_20250101"
        assert manifest.dlc_h5_files == []
        assert manifest.dlc_csv_files == []


# ---- Integration test (requires real mount) ----

_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")


@pytest.mark.skipif(
    not _MOUNT.exists(),
    reason="MICROSCOPE server not mounted",
)
class TestIntegrationManifest:
    def test_ps46_baseline_session(self, monkeypatch):
        """Build a manifest for PS46 on 2025-03-07 (baseline, day -6)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        info = AnimalInfo(
            animal_id="PS46",
            stroke_date=datetime.date(2025, 3, 13),
            session_start=datetime.date(2025, 3, 7),
            session_end=datetime.date(2025, 4, 6),
        )
        manifest = build_manifest("PS46", datetime.date(2025, 3, 7), resolver, info)

        assert manifest.session_id == "PS46_20250307"
        assert manifest.phase == "baseline"
        assert manifest.day_relative_to_stroke == -6
        assert len(manifest.dlc_h5_files) >= 1
        assert len(manifest.dlc_csv_files) >= 1
        # All discovered files should actually exist
        for f in manifest.dlc_h5_files + manifest.dlc_csv_files:
            assert f.exists(), f"Expected {f} to exist"
        # Alignment template should exist for this date
        assert manifest.alignment_template is not None
        assert manifest.alignment_template.exists()
