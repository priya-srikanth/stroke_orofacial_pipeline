"""Tests for stroke_orofacial._writeguard.

Layer 2 of the three-layer guard system added after the 2026-05-05
alignment-template overwrite incident. Verifies the deny list catches
all legacy source-data roots (Windows UNC + Mac POSIX) AND lets
legitimate write targets through (pipeline_outputs/, tmp_path/, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stroke_orofacial._writeguard import (
    WriteGuardError,
    assert_safe_write_path,
    is_safe_write_path,
)


# ---------- Legacy paths must raise ----------


class TestLegacyMicroscopeWindowsUNCRaises:
    """The path-shape that triggered the 2026-05-05 incident — Windows
    UNC paths under the live MICROSCOPE share."""

    def test_alignment_template_merged_path_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250314.npz"
        )
        with pytest.raises(WriteGuardError, match="legacy"):
            assert_safe_write_path(path)

    def test_alignment_template_per_half_path_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250314ab"
            r"\20250314a.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_dlc_inference_h5_path_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\O2_analysis\PS48"
            r"\video2_2025-03-14T12_31_07DLC_filtered.h5"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_dlc_train_config_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\DLC_train_config\config.yaml"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_session_processing3_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\facerhythm_stroke_biomarker_exp\analysis\session_processing3"
            r"\licks_and_rewards\PS48\20250314.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_basic_behavior_analysis3_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\facerhythm_stroke_biomarker_exp\analysis\basic_behavior_analysis3"
            r"\PS48\report.json"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_raw_wavesurfer_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\facerhythm_stroke_biomarker_exp\wavesurfer\20250314a\PS48"
            r"\stroke_0001.h5"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_rich_camera_tree_raises(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Rich"
            r"\data\2pRAM\facerhythm_stroke_biomarker_exp\camera"
            r"\20250314a\PS48\video2_2025-03-14T12_31_07.avi"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)


class TestLegacyMacPosixRaises:
    """Mac mounts of the same trees plus Mac-local legacy data roots
    and legacy GitHub repos (CLAUDE.md ground rules 1 + 2)."""

    def test_volumes_microscope_deeplabcut_raises(self):
        path = (
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis"
            "/alignment_templates/cam2/PS48/20250314.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_volumes_microscope_session_processing3_raises(self):
        path = (
            "/Volumes/Neurobio/MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp"
            "/analysis/session_processing3/licks_and_rewards/PS48/20250314.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_volumes_microscope_wavesurfer_raises(self):
        path = (
            "/Volumes/Neurobio/MICROSCOPE/Priya/facerhythm_stroke_biomarker_exp"
            "/wavesurfer/20250314a/PS48/stroke_0001.h5"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_volumes_rich_camera_raises(self):
        path = "/Volumes/Neurobio/MICROSCOPE/Rich/data/2pRAM/something.avi"
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_mac_local_legacy_data_root_raises(self):
        path = (
            "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp"
            "/analysis/session_processing3/foo.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_mac_local_legacy_wavesurfer_raises(self):
        path = (
            "/Users/Priya2/Documents/data/facerhythm_stroke_biomarker_exp"
            "/wavesurfer/20250314a/PS48/stroke_0001.h5"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_legacy_github_repo_priya_raises(self):
        path = (
            "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya"
            "/analysis/some_notebook.ipynb"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_legacy_github_repo_rich_raises(self):
        path = (
            "/Users/Priya2/Github/facerhythm_stroke_biomarker_exp"
            "/make_alignment_templates_20251216.py"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)


class TestCaseInsensitiveMatching:
    """Filesystems on Windows + macOS are case-insensitive in practice;
    a deny root must catch upper- and lower-cased variants."""

    def test_uppercased_unc_raises(self):
        path = (
            r"\\RESEARCH.FILES.MED.HARVARD.EDU\Neurobio\MICROSCOPE\Priya"
            r"\DEEPLABCUT\O2_analysis\alignment_templates\cam2\PS48\20250314.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)

    def test_mixed_case_volumes_raises(self):
        path = (
            "/Volumes/Neurobio/Microscope/Priya/DeepLabCut/foo.npz"
        )
        with pytest.raises(WriteGuardError):
            assert_safe_write_path(path)


# ---------- Safe paths must NOT raise ----------


class TestPipelineOutputsAllowed:
    """The new pipeline writes here. Every entry under
    stroke_orofacial_pipeline_outputs/ must be allowed."""

    def test_windows_pipeline_outputs_root_allowed(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\stroke_orofacial_pipeline_outputs\spout_behavior"
            r"\licks_and_rewards\PS48\20250314.npz"
        )
        assert is_safe_write_path(path)
        assert_safe_write_path(path)  # would raise; doesn't

    def test_pipeline_outputs_dlc_analysis_allowed(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\stroke_orofacial_pipeline_outputs\dlc_analysis"
            r"\centered_spout_midpoint\PS48\foo.parquet"
        )
        assert is_safe_write_path(path)

    def test_mac_pipeline_outputs_allowed(self):
        path = (
            "/Volumes/Neurobio/MICROSCOPE/Priya"
            "/stroke_orofacial_pipeline_outputs/dlc_analysis/foo.parquet"
        )
        assert is_safe_write_path(path)

    def test_pipeline_outputs_per_half_subdir_allowed(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\stroke_orofacial_pipeline_outputs\spout_behavior"
            r"\licks_and_rewards\PS48\20250314ab\20250314a.npz"
        )
        assert is_safe_write_path(path)


class TestTmpPathAllowed:
    """Tests using tmp_path must always be allowed — that's the whole
    point of the test sandbox."""

    def test_tmp_path_root_allowed(self, tmp_path: Path):
        path = tmp_path / "synthetic.npz"
        assert is_safe_write_path(path)

    def test_tmp_path_nested_allowed(self, tmp_path: Path):
        path = tmp_path / "outputs" / "spout_behavior" / "PS48" / "20250314.npz"
        assert is_safe_write_path(path)

    def test_tmp_path_with_legacy_lookalike_segments_allowed(
        self, tmp_path: Path,
    ):
        """A test fixture might create a sub-tree named DeepLabCut/
        under tmp_path (e.g. for resolver tests). The writeguard must
        allow tmp_path-rooted paths even if internal segments share
        names with legacy roots."""
        path = (
            tmp_path / "DeepLabCut" / "O2_analysis"
            / "alignment_templates" / "cam2" / "PS48" / "20250314.npz"
        )
        assert is_safe_write_path(path)


class TestNonLegacyAbsolutePathsAllowed:
    def test_unrelated_unc_allowed(self):
        # A different MICROSCOPE share user (not Priya) — out of scope.
        path = r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\OtherUser\foo.npz"
        assert is_safe_write_path(path)

    def test_unrelated_volumes_allowed(self):
        path = "/Volumes/SomeOtherDisk/foo.npz"
        assert is_safe_write_path(path)

    def test_relative_path_allowed(self):
        # Relative paths can't logically resolve under a deny root
        # at write time; the resolver tells the writer where it goes.
        # The writeguard returns silently rather than guessing.
        assert is_safe_write_path("relative/thing.npz")

    def test_empty_path_allowed(self):
        # Empty input = no path = nothing to guard against. Caller's
        # own validation will catch this if it matters.
        assert is_safe_write_path("")


# ---------- Sibling boundary cases ----------


class TestSiblingBoundaries:
    """Deny roots must NOT accidentally match siblings whose path
    string is a prefix of the deny root."""

    def test_sibling_dir_named_partial_match_allowed(self):
        # "DeepLabCut_other" should NOT be caught by "DeepLabCut" deny.
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut_other\foo.npz"
        )
        assert is_safe_write_path(path)

    def test_pipeline_outputs_sibling_to_deeplabcut_allowed(self):
        # Confirming that pipeline_outputs/ at the same level as
        # DeepLabCut/ is unambiguously NOT under DeepLabCut/.
        deny_root_neighbor = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\stroke_orofacial_pipeline_outputs\foo.npz"
        )
        assert is_safe_write_path(deny_root_neighbor)


# ---------- API surface ----------


class TestApiSurface:
    def test_assert_returns_none_on_safe_path(self, tmp_path: Path):
        # Explicit None return; verifies the function doesn't accidentally
        # return a truthy value or path object.
        result = assert_safe_write_path(tmp_path / "x.npz")
        assert result is None

    def test_is_safe_returns_true_on_safe(self, tmp_path: Path):
        assert is_safe_write_path(tmp_path / "x.npz") is True

    def test_is_safe_returns_false_on_unsafe(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\foo.npz"
        )
        assert is_safe_write_path(path) is False

    def test_error_message_includes_candidate_and_deny(self):
        path = (
            r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
            r"\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250314.npz"
        )
        with pytest.raises(WriteGuardError) as excinfo:
            assert_safe_write_path(path)
        msg = str(excinfo.value)
        # candidate appears verbatim
        assert "20250314.npz" in msg
        # deny root identifying segment appears
        assert "DeepLabCut" in msg or "deeplabcut" in msg.lower()
        # actionable phrasing — points the user at the new pipeline tree
        assert "stroke_orofacial_pipeline_outputs" in msg

    def test_accepts_str_or_pathlike(self, tmp_path: Path):
        # Both str and Path inputs are valid
        assert_safe_write_path(str(tmp_path / "x.npz"))
        assert_safe_write_path(tmp_path / "x.npz")
