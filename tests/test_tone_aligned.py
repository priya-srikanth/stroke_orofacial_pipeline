"""Tests for stroke_orofacial.dlc_spatial.tone_aligned."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stroke_orofacial.dlc_spatial.tone_aligned import (
    load_tone_events,
    ws_samples_to_frame_indices,
)
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
    stamp_side_convention,
)


def _write_stamped_tones_npz(
    path: Path,
    *,
    tone_L: np.ndarray,
    tone_R: np.ndarray,
    wavesurfer_matches: bool = False,
) -> None:
    """Test helper: write a minimal Phase-2-shaped tones NPZ with the
    mouse-frame side-convention stamp. Mirrors what
    ``_save_npz_with_side_convention`` writes in production, but only the
    fields ``load_tone_events`` reads.
    """
    payload: dict = {
        "Tone_L": np.asarray(tone_L),
        "Tone_R": np.asarray(tone_R),
    }
    stamp_side_convention(payload, wavesurfer_matches)
    np.savez(path, **payload)


class TestLoadToneEvents:
    """Phase 6.8a: the Phase 2 NPZ must carry the side-convention stamp
    or load_tone_events raises. The four "happy path" tests below use
    stamped fixtures; the rejection paths are in TestLoadToneEventsStamp
    below."""

    def test_all_group(self, tmp_path):
        path = tmp_path / "test.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10, 30], tone_R=[20, 40],
        )
        result = load_tone_events(path, "all")
        np.testing.assert_array_equal(result, [10, 20, 30, 40])

    def test_l_group(self, tmp_path):
        path = tmp_path / "test.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10, 30], tone_R=[20, 40],
        )
        result = load_tone_events(path, "L")
        np.testing.assert_array_equal(result, [10, 30])

    def test_r_group(self, tmp_path):
        path = tmp_path / "test.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10, 30], tone_R=[20, 40],
        )
        result = load_tone_events(path, "R")
        np.testing.assert_array_equal(result, [20, 40])

    def test_empty_side(self, tmp_path):
        path = tmp_path / "test.npz"
        _write_stamped_tones_npz(
            path,
            tone_L=np.array([10]),
            tone_R=np.array([], dtype=int),
        )
        result = load_tone_events(path, "all")
        np.testing.assert_array_equal(result, [10])


class TestLoadToneEventsStamp:
    """Phase 6.8a stamp-verification paths — each exercises one specific
    rejection branch so a regression that silently drops the check (e.g.
    during a refactor) fails loudly."""

    def test_rejects_unstamped_npz(self, tmp_path):
        """Pre-task-#17 NPZ (no stamp at all) must raise — reading it as
        mouse-frame would silently swap L/R on the mirrored rig."""
        path = tmp_path / "unstamped.npz"
        np.savez(
            path,
            Tone_L=np.array([10, 30]),
            Tone_R=np.array([20, 40]),
        )
        with pytest.raises(ValueError, match=SIDE_CONVENTION_VERSION_KEY):
            load_tone_events(path, "all")

    def test_rejects_missing_match_key(self, tmp_path):
        """Version key present but match key absent = malformed stamp."""
        path = tmp_path / "half_stamped.npz"
        np.savez(
            path,
            Tone_L=np.array([10]),
            Tone_R=np.array([20]),
            **{SIDE_CONVENTION_VERSION_KEY: np.int32(SIDE_CONVENTION_VERSION)},
        )
        with pytest.raises(ValueError, match=SIDE_CONVENTION_MATCH_KEY):
            load_tone_events(path, "all")

    def test_rejects_version_mismatch(self, tmp_path):
        """A stamp with an older version must be rejected so a convention
        change is caught at load rather than silently mis-interpreted."""
        path = tmp_path / "old_version.npz"
        bad_version = SIDE_CONVENTION_VERSION - 1
        np.savez(
            path,
            Tone_L=np.array([10]),
            Tone_R=np.array([20]),
            **{
                SIDE_CONVENTION_VERSION_KEY: np.int32(bad_version),
                SIDE_CONVENTION_MATCH_KEY: np.bool_(False),
            },
        )
        with pytest.raises(ValueError, match="side_convention_version"):
            load_tone_events(path, "all")

    def test_rejects_flag_mismatch(self, tmp_path):
        """Caller passes a rig-match value that disagrees with the NPZ's
        stamp — typically means the yaml was edited after the NPZ was
        emitted. Must raise rather than silently pick one or the other."""
        path = tmp_path / "matches_true.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10], tone_R=[20],
            wavesurfer_matches=True,
        )
        with pytest.raises(ValueError, match="wavesurfer_sides_match_mouse_sides"):
            load_tone_events(
                path, "all", wavesurfer_sides_match_mouse_sides=False,
            )

    def test_accepts_matching_flag(self, tmp_path):
        """Caller's flag matches the NPZ's stamp → no raise, returns
        the expected tone-onset indices."""
        path = tmp_path / "matches_false.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10, 30], tone_R=[20, 40],
            wavesurfer_matches=False,
        )
        result = load_tone_events(
            path, "all", wavesurfer_sides_match_mouse_sides=False,
        )
        np.testing.assert_array_equal(result, [10, 20, 30, 40])

    def test_flag_none_skips_cross_check(self, tmp_path):
        """Caller passes None → stamp presence still required, but its
        bool value is not cross-checked. The legacy happy-path tests
        above rely on this behavior."""
        path = tmp_path / "stamped_true.npz"
        _write_stamped_tones_npz(
            path, tone_L=[10], tone_R=[20],
            wavesurfer_matches=True,
        )
        # Does not raise even though the NPZ is stamped True and we pass None.
        result = load_tone_events(path, "all")
        np.testing.assert_array_equal(result, [10, 20])


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
class TestIntegrationToneAligned:
    """Integration tests via the by_animal_date wrapper. The wrapper builds
    the manifest internally; the manifest-first primary signature is
    exercised in TestIntegrationToneAlignedWithManifest below."""

    def test_smoke_ps46_20250307(self, monkeypatch):
        """End-to-end smoke test: tone-aligned analysis produces results."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis_by_animal_date,
        )
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        defaults = load_defaults()

        result = build_tone_aligned_analysis_by_animal_date(
            "PS46", "20250307", "tongue", "nose", "all",
            (-500, 5000), resolver,
            defaults["dlc_spatial"], defaults["dlc_spatial_tone_aligned"],
        )
        assert result is not None
        assert result["n_tones"] > 0
        assert result["n_selected_frames"] > 0
        assert result["histogram"] is not None
        assert result["histogram"]["H_counts"].sum() > 0

    def test_trial_groups_differ(self, monkeypatch):
        """L, R, all trial groups should produce different tone counts."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis_by_animal_date,
        )
        from stroke_orofacial.paths import PathResolver

        resolver = PathResolver()
        defaults = load_defaults()

        counts = {}
        for tg in ("all", "L", "R"):
            r = build_tone_aligned_analysis_by_animal_date(
                "PS46", "20250307", "tongue", "nose", tg,
                (-500, 5000), resolver,
                defaults["dlc_spatial"], defaults["dlc_spatial_tone_aligned"],
            )
            counts[tg] = r["n_tones"] if r else 0

        assert counts["all"] == counts["L"] + counts["R"]
        assert counts["L"] > 0
        assert counts["R"] > 0


@pytest.mark.skipif(
    not _MOUNT.exists() or not (_V2 / "spout_behavior").exists(),
    reason="MICROSCOPE or stroke_orofacial_pipeline_outputs not available",
)
class TestIntegrationToneAlignedWithManifest:
    """Exercise the manifest-first primary signature on real data."""

    def test_smoke_with_manifest(self, monkeypatch):
        """Build manifest explicitly, pass to build_tone_aligned_analysis(...)."""
        import datetime
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.config_loader import load_defaults
        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis,
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

        result = build_tone_aligned_analysis(
            manifest, "tongue", "nose", "all", (-500, 5000),
            resolver, defaults["dlc_spatial"],
            defaults["dlc_spatial_tone_aligned"],
        )
        assert result is not None
        assert result["n_tones"] > 0
        assert result["histogram"]["H_counts"].sum() > 0


class TestEmitCacheParameterPlumbing:
    """Phase 7c.2 Task 2.5 (Addendum #3 Q2.B): the new ``emit_cache``
    parameter defaults to False (no NPZ written). The by_animal_date
    wrapper forwards the kwarg to the primary entry point."""

    def test_primary_signature_has_emit_cache_default_false(self):
        import inspect
        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis,
        )
        sig = inspect.signature(build_tone_aligned_analysis)
        assert "emit_cache" in sig.parameters
        assert sig.parameters["emit_cache"].default is False

    def test_wrapper_signature_has_emit_cache_default_false(self):
        import inspect
        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis_by_animal_date,
        )
        sig = inspect.signature(build_tone_aligned_analysis_by_animal_date)
        assert "emit_cache" in sig.parameters
        assert sig.parameters["emit_cache"].default is False

    @pytest.mark.parametrize("emit_cache_value", [False, True])
    def test_wrapper_forwards_emit_cache(self, emit_cache_value):
        """``build_tone_aligned_analysis_by_animal_date(emit_cache=...)``
        forwards the kwarg verbatim to the primary entry point."""
        import datetime
        from unittest.mock import MagicMock, patch

        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return None  # short-circuit; we only check kwarg forwarding

        info = MagicMock()
        info.wavesurfer_sides_match_mouse_sides = False
        info.session_start = datetime.date(2026, 1, 1)
        info.session_end = datetime.date(2026, 1, 31)
        info.stroke_date = datetime.date(2026, 1, 15)
        info.exclusions = []

        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis_by_animal_date,
        )

        with patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.get_animal",
            return_value=info,
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_manifest",
            return_value=MagicMock(),
        ), patch(
            "stroke_orofacial.dlc_spatial.tone_aligned.build_tone_aligned_analysis",
            side_effect=_capture,
        ):
            build_tone_aligned_analysis_by_animal_date(
                "PS99", "20260115", "tongue", "spout_midpoint", "all",
                (-500.0, 5000.0), MagicMock(),
                spatial_config={}, tone_config={},
                emit_cache=emit_cache_value,
            )

        assert captured["emit_cache"] is emit_cache_value


class TestBuildToneAlignedAnalysisRaisesOnEmptyDlc:
    """Phase 6 is DLC-required (per Phase 6.7 architectural decision).
    build_tone_aligned_analysis must raise on empty manifest.dlc_h5_files."""

    def test_raises_when_manifest_has_no_dlc(self, tmp_path):
        import datetime
        from unittest.mock import MagicMock

        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis,
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
            build_tone_aligned_analysis(
                manifest, "tongue", "nose", "all", (-500, 5000),
                resolver, spatial_config={}, tone_config={},
            )
class TestBuildToneAlignedAnalysisRaisesOnMissingPrerequisites:
    """Phase 6.8a follow-up: the silent ``return None`` path for the
    missing Phase 4 centered parquet now raises FileNotFoundError with
    a message naming the exact missing upstream artefact, so runner
    logs distinguish prerequisite-miss from other failure modes
    instead of lumping every silent skip into a single ``n_err`` count.
    The licks-NPZ and alignment-template paths share the raise pattern
    and are pinned by the docstring + inline code; separate tests would
    require monkeypatching past read_centered_parquet and
    load_tone_events with no commensurate diagnostic value."""

    def test_raises_when_centered_parquet_missing(self, tmp_path):
        import datetime
        from unittest.mock import MagicMock

        from stroke_orofacial.dlc_spatial.tone_aligned import (
            build_tone_aligned_analysis,
        )
        from stroke_orofacial.manifest import SessionManifest
        from stroke_orofacial.paths import PathResolver

        # Touch a fake DLC h5 so dlc_h5_files[0] resolves. The parquet
        # existence check fires before any read, so file contents are
        # immaterial.
        dlc_dir = tmp_path / "dlc_fake"
        dlc_dir.mkdir()
        fake_h5 = dlc_dir / "PS46_20250101_cam2DLC.h5"
        fake_h5.write_bytes(b"")

        resolver = MagicMock(spec=PathResolver)
        resolver.pipeline_outputs.return_value = tmp_path
        manifest = SessionManifest(
            session_id="PS46_20250101",
            animal="PS46",
            date=datetime.date(2025, 1, 1),
            day_relative_to_stroke=-71,
            phase="baseline",
            dlc_h5_files=[fake_h5],
            dlc_csv_files=[],
        )
        with pytest.raises(FileNotFoundError, match="Phase 4 centered parquet"):
            build_tone_aligned_analysis(
                manifest, "tongue", "nose", "all", (-500, 5000),
                resolver, spatial_config={}, tone_config={},
            )
