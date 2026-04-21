"""Tests for stroke_orofacial.dlc_spatial.reward_aligned."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.dlc_spatial.reward_aligned import (
    load_reward_events,
    ws_samples_to_frame_indices,
)


class TestLoadRewardEvents:
    def test_all_group(self, tmp_path):
        path = tmp_path / "test.npz"
        np.savez(path, Reward_L=np.array([10, 30]), Reward_R=np.array([20, 40]))
        result = load_reward_events(path, "all")
        np.testing.assert_array_equal(result, [10, 20, 30, 40])

    def test_l_group(self, tmp_path):
        path = tmp_path / "test.npz"
        np.savez(path, Reward_L=np.array([10, 30]), Reward_R=np.array([20, 40]))
        result = load_reward_events(path, "L")
        np.testing.assert_array_equal(result, [10, 30])

    def test_r_group(self, tmp_path):
        path = tmp_path / "test.npz"
        np.savez(path, Reward_L=np.array([10, 30]), Reward_R=np.array([20, 40]))
        result = load_reward_events(path, "R")
        np.testing.assert_array_equal(result, [20, 40])

    def test_empty_side(self, tmp_path):
        path = tmp_path / "test.npz"
        np.savez(path, Reward_L=np.array([10]), Reward_R=np.array([], dtype=int))
        result = load_reward_events(path, "all")
        np.testing.assert_array_equal(result, [10])


class TestWsSamplesToFrameIndices:
    def test_basic(self):
        lut = np.arange(100, dtype=float) / 4.0
        ws = np.array([0, 4, 8])
        result = ws_samples_to_frame_indices(ws, lut, n_cam_frames=30)
        np.testing.assert_array_equal(result, [0, 1, 2])


# ---- Integration (requires real data) ----

_WS_LOCAL = Path(
    "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp/wavesurfer"
)
_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")
_V2 = Path("/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs")


@pytest.mark.skipif(
    not _MOUNT.exists() or not (_V2 / "spout_behavior").exists(),
    reason="MICROSCOPE or stroke_orofacial_pipeline_outputs not available",
)
class TestIntegrationRewardAligned:
    """Integration tests via the by_animal_date wrapper. The wrapper builds
    the manifest internally; the manifest-first primary signature is
    exercised in TestIntegrationRewardAlignedWithManifest below."""

    def test_smoke_ps46_20250307(self, monkeypatch):
        """End-to-end smoke test: reward-aligned analysis produces results."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.reward_aligned import (
            build_reward_aligned_analysis_by_animal_date,
        )
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        defaults = load_defaults()

        result = build_reward_aligned_analysis_by_animal_date(
            "PS46", "20250307", "tongue", "nose", "all",
            (-500, 5000), resolver,
            defaults["dlc_spatial"], defaults["dlc_spatial_reward_aligned"],
        )
        assert result is not None
        assert result["n_rewards"] > 0
        assert result["n_selected_frames"] > 0
        assert result["histogram"] is not None
        assert result["histogram"]["H_counts"].sum() > 0

    def test_trial_groups_differ(self, monkeypatch):
        """L, R, all trial groups should produce different reward counts."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.reward_aligned import (
            build_reward_aligned_analysis_by_animal_date,
        )
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        defaults = load_defaults()

        counts = {}
        for tg in ("all", "L", "R"):
            r = build_reward_aligned_analysis_by_animal_date(
                "PS46", "20250307", "tongue", "nose", tg,
                (-500, 5000), resolver,
                defaults["dlc_spatial"], defaults["dlc_spatial_reward_aligned"],
            )
            counts[tg] = r["n_rewards"] if r else 0

        assert counts["all"] == counts["L"] + counts["R"]
        assert counts["L"] > 0
        assert counts["R"] > 0


@pytest.mark.skipif(
    not _MOUNT.exists() or not (_V2 / "spout_behavior").exists(),
    reason="MICROSCOPE or stroke_orofacial_pipeline_outputs not available",
)
class TestIntegrationRewardAlignedWithManifest:
    """Exercise the manifest-first primary signature on real data."""

    def test_smoke_with_manifest(self, monkeypatch):
        """Build manifest explicitly, pass to build_reward_aligned_analysis(...)."""
        import datetime
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.reward_aligned import (
            build_reward_aligned_analysis,
        )
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        defaults = load_defaults()
        animal_info = get_animal("PS46")
        manifest = build_manifest(
            "PS46", datetime.date(2025, 3, 7), resolver, animal_info
        )
        assert len(manifest.dlc_h5_files) > 0
        assert manifest.alignment_template is not None

        result = build_reward_aligned_analysis(
            manifest, "tongue", "nose", "all", (-500, 5000),
            resolver, defaults["dlc_spatial"],
            defaults["dlc_spatial_reward_aligned"],
        )
        assert result is not None
        assert result["n_rewards"] > 0
        assert result["histogram"]["H_counts"].sum() > 0


class TestBuildRewardAlignedAnalysisRaisesOnEmptyDlc:
    """Phase 6 is DLC-required (per Phase 6.7 architectural decision).
    build_reward_aligned_analysis must raise on empty manifest.dlc_h5_files."""

    def test_raises_when_manifest_has_no_dlc(self, tmp_path):
        import datetime
        from unittest.mock import MagicMock

        from stroke_orofacial.dlc_spatial.reward_aligned import (
            build_reward_aligned_analysis,
        )
        from stroke_orofacial.manifest import SessionManifest
        from stroke_orofacial.paths import PathResolver

        resolver = MagicMock(spec=PathResolver)
        resolver.pipeline_outputs.return_value = tmp_path
        manifest = SessionManifest(
            session_id="PS46_20250101",
            animal="PS46",
            date=datetime.date(2025, 1, 1),
            day_relative_to_stroke=-71,
            phase="baseline",
            dlc_h5_files=[],
            dlc_csv_files=[],
        )
        with pytest.raises(FileNotFoundError, match="dlc_h5_files"):
            build_reward_aligned_analysis(
                manifest, "tongue", "nose", "all", (-500, 5000),
                resolver, spatial_config={}, reward_config={},
            )
