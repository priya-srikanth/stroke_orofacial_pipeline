"""Tests for stroke_orofacial.paths.PathResolver."""

from __future__ import annotations

import datetime
import platform
import textwrap
from pathlib import Path

import pytest

from stroke_orofacial.paths import PathResolver

# For tests that build YAML mounts from real on-disk tmp_path values,
# we must use the HOST platform's key so PathResolver._make_path picks
# the right PurePath subclass (PureWindowsPath for Windows tmp paths
# like "C:/Users/...", PurePosixPath for Mac/Linux tmp paths).
# Forcing platform_key='mac' on a Windows host loses the drive root
# (PurePosixPath drops "C:" → drive-relative path → .exists() fails).
_HOST_KEY = "windows" if platform.system() == "Windows" else "mac"


@pytest.fixture()
def mac_paths_yaml(tmp_path: Path) -> Path:
    """Write a minimal paths.yaml and return its path."""
    cfg = tmp_path / "paths.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            logical_roots:
              microscope_server:
                description: "test server"
                mounts:
                  mac: "/Volumes/Neurobio/MICROSCOPE/Priya"
                  windows: "\\\\\\\\server\\\\share\\\\Priya"
              local_processed_spout:
                description: "local data"
                mounts:
                  mac: "/Users/testuser/data/analysis"
                  windows: null
        """)
    )
    return cfg


class TestPlatformDetection:
    def test_mac_auto_detect(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.delenv("STROKE_PIPELINE_MACHINE", raising=False)
        resolver = PathResolver(mac_paths_yaml)
        assert resolver.platform_key == "mac"

    def test_windows_auto_detect(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.delenv("STROKE_PIPELINE_MACHINE", raising=False)
        resolver = PathResolver(mac_paths_yaml)
        assert resolver.platform_key == "windows"

    def test_env_var_override(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "windows")
        resolver = PathResolver(mac_paths_yaml)
        assert resolver.platform_key == "windows"

    def test_env_var_invalid(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "linux")
        with pytest.raises(ValueError, match="must be 'mac' or 'windows'"):
            PathResolver(mac_paths_yaml)

    def test_unsupported_platform(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.delenv("STROKE_PIPELINE_MACHINE", raising=False)
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            PathResolver(mac_paths_yaml)


class TestRootResolution:
    def test_root_mac(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(mac_paths_yaml)
        assert resolver.root("microscope_server") == Path(
            "/Volumes/Neurobio/MICROSCOPE/Priya"
        )

    def test_root_unknown_name(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(mac_paths_yaml)
        with pytest.raises(KeyError, match="Unknown logical root"):
            resolver.root("nonexistent")

    def test_root_null_mount(self, monkeypatch, mac_paths_yaml):
        """local_processed_spout has windows mount = null."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "windows")
        resolver = PathResolver(mac_paths_yaml)
        with pytest.raises(RuntimeError, match="no mount defined"):
            resolver.root("local_processed_spout")


class TestConvenienceMethods:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, mac_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        self.resolver = PathResolver(mac_paths_yaml)

    def test_dlc_output_dir(self):
        result = self.resolver.dlc_output_dir("PS46")
        # Compare via .as_posix() so the test is platform-independent:
        # on Windows, `Path("/Volumes/...")` is a WindowsPath and would never
        # equal a PurePosixPath even though the string content matches.
        # as_posix() always emits forward-slash normalized form on both platforms.
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46"
        )

    def test_alignment_templates_dir(self):
        result = self.resolver.alignment_templates_dir("cam2")
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2"
        )

    def test_alignment_template_legacy_read(self):
        """Phase 7-pre-multi-half: renamed from alignment_template after the
        2026-05-05 incident. Same path semantics — points at the live
        MICROSCOPE legacy tree — but the _legacy_read suffix signals that
        this resolver is for READS only. Writes go via alignment_template_new
        / alignment_template_per_half_new.
        """
        result = self.resolver.alignment_template_legacy_read(
            "PS46", datetime.date(2025, 3, 7), cam="cam2"
        )
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/PS46/20250307.npz"
        )

    def test_session_processing_out(self):
        result = self.resolver.session_processing_out("v2")
        assert result.as_posix() == (
            "/Users/testuser/data/analysis/session_processing_v2"
        )


class TestListMounts:
    """Test list-of-paths fallback behavior for mounts."""

    @pytest.fixture()
    def list_mount_yaml(self, tmp_path: Path) -> Path:
        """paths.yaml with a list mount for wavesurfer_raw."""
        # Create two candidate dirs; only the second exists
        candidate_a = tmp_path / "primary_mount" / "wavesurfer"
        candidate_b = tmp_path / "fallback_mount" / "wavesurfer"
        candidate_b.mkdir(parents=True)
        # Don't create candidate_a — it should be skipped

        # Write mount under the HOST platform's key (see _HOST_KEY note at top).
        # Use .as_posix() so Windows backslashes (C:\Users\...) don't trigger
        # the YAML \U Unicode-escape parser inside a double-quoted scalar.
        # Windows accepts forward-slash paths natively, so Path() resolves fine.
        cfg = tmp_path / "paths.yaml"
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  wavesurfer_raw:
                    description: "test list mount"
                    mounts:
                      {_HOST_KEY}:
                        - "{candidate_a.as_posix()}"
                        - "{candidate_b.as_posix()}"
            """)
        )
        return cfg

    def test_list_mount_uses_first_existing(self, monkeypatch, list_mount_yaml, tmp_path):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(list_mount_yaml)
        result = resolver.root("wavesurfer_raw")
        expected = tmp_path / "fallback_mount" / "wavesurfer"
        assert result == expected

    def test_list_mount_prefers_first_if_both_exist(self, monkeypatch, tmp_path):
        candidate_a = tmp_path / "primary" / "ws"
        candidate_b = tmp_path / "fallback" / "ws"
        candidate_a.mkdir(parents=True)
        candidate_b.mkdir(parents=True)

        cfg = tmp_path / "paths.yaml"
        # Host-platform key + .as_posix() — see list_mount_yaml fixture / _HOST_KEY.
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  wavesurfer_raw:
                    description: "both exist"
                    mounts:
                      {_HOST_KEY}:
                        - "{candidate_a.as_posix()}"
                        - "{candidate_b.as_posix()}"
            """)
        )
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(cfg)
        assert resolver.root("wavesurfer_raw") == candidate_a

    def test_list_mount_none_exist_raises(self, monkeypatch, tmp_path):
        cfg = tmp_path / "paths.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                logical_roots:
                  wavesurfer_raw:
                    description: "none exist"
                    mounts:
                      mac:
                        - "/nonexistent/path/a"
                        - "/nonexistent/path/b"
            """)
        )
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(cfg)
        with pytest.raises(FileNotFoundError, match="not found at any of"):
            resolver.root("wavesurfer_raw")

    def test_single_string_mount_no_existence_check(self, monkeypatch, tmp_path):
        """Single-string mounts don't check existence (backward compat)."""
        cfg = tmp_path / "paths.yaml"
        cfg.write_text(
            textwrap.dedent("""\
                logical_roots:
                  some_root:
                    description: "single string"
                    mounts:
                      mac: "/nonexistent/single/path"
            """)
        )
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(cfg)
        # Should NOT raise — single string mounts are returned directly
        result = resolver.root("some_root")
        assert result == Path("/nonexistent/single/path")


class TestNewConvenienceMethods:
    """Test pipeline_outputs() and wavesurfer_dir()."""

    @pytest.fixture()
    def full_paths_yaml(self, tmp_path: Path) -> Path:
        cfg = tmp_path / "paths.yaml"
        ws_dir = tmp_path / "wavesurfer"
        ws_dir.mkdir()
        cam_dir = tmp_path / "camera"
        cam_dir.mkdir()
        # microscope_pipeline_outputs uses a static /Volumes path so we keep it
        # under the "mac" key — the tests that read it force platform_key='mac'.
        # wavesurfer_raw and camera_raw use real on-disk tmp_path mounts so
        # they MUST go under the HOST platform's key (see _HOST_KEY note at
        # top of file). Mixed platform keys is fine because each test only
        # touches one root. .as_posix() avoids Windows \U escape parsing
        # inside double-quoted YAML.
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  microscope_pipeline_outputs:
                    description: "outputs"
                    mounts:
                      mac: "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
                  wavesurfer_raw:
                    description: "raw ws"
                    mounts:
                      {_HOST_KEY}:
                        - "{ws_dir.as_posix()}"
                  camera_raw:
                    description: "raw camera"
                    mounts:
                      {_HOST_KEY}:
                        - "{cam_dir.as_posix()}"
            """)
        )
        return cfg

    def test_pipeline_outputs(self, monkeypatch, full_paths_yaml):
        # Uses the static /Volumes mac mount; safe to force mac key.
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.pipeline_outputs("spout_behavior")
        # See note in TestConvenienceMethods.test_dlc_output_dir.
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/spout_behavior"
        )

    def test_spout_behavior_figures_dir(self, monkeypatch, full_paths_yaml):
        """Phase 8a.10 Task 3 Round 2 continuation rename: per-mouse
        figures output nests under
        `pipeline_outputs("spout_behavior")/spout_behavior_figures/<animal>/`.
        Replaces the prior `visual_gate_dir`."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.spout_behavior_figures_dir("PS51")
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/"
            "spout_behavior/spout_behavior_figures/PS51"
        )

    def test_spout_behavior_figures_dir_respects_output_root_override(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        result = resolver.spout_behavior_figures_dir("PS46")
        assert result == (
            tmp_path / "spout_behavior" / "spout_behavior_figures" / "PS46"
        )

    def test_spout_behavior_figures_summary_dir(self, monkeypatch, full_paths_yaml):
        """Phase 8a.10 Task 3 Round 2 continuation: cohort-summary
        nests under a SINGLE shared
        `spout_behavior_figures/summary/` (not per-grid subdirs)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.spout_behavior_figures_summary_dir()
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/"
            "spout_behavior/spout_behavior_figures/summary"
        )

    def test_spout_behavior_figures_summary_dir_respects_output_root_override(
        self, tmp_path,
    ):
        resolver = PathResolver(output_root=tmp_path)
        result = resolver.spout_behavior_figures_summary_dir()
        assert result == (
            tmp_path / "spout_behavior" / "spout_behavior_figures" / "summary"
        )

    def test_visual_gate_dir_removed(self):
        """Confirm the old method name was removed (no backward compat)."""
        assert not hasattr(PathResolver, "visual_gate_dir")
        assert not hasattr(PathResolver, "visual_gate_summary_dir")

    def test_wavesurfer_dir(self, monkeypatch, full_paths_yaml, tmp_path):
        # Uses the real on-disk tmp_path mount, so must run under host key.
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.wavesurfer_dir(datetime.date(2025, 3, 7), "PS46")
        ws_dir = tmp_path / "wavesurfer"
        assert result == ws_dir / "20250307" / "PS46"

    def test_wavesurfer_dir_default_half_subdir_is_date_str(
        self, monkeypatch, full_paths_yaml, tmp_path
    ):
        """Phase 7-pre-multi-half: half_subdir=None preserves backwards-compat
        behavior (subdir = date_str). Verifies the existing single-half code
        path is unchanged when the kwarg is omitted.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.wavesurfer_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir=None
        )
        assert result == tmp_path / "wavesurfer" / "20250314" / "PS48"

    def test_wavesurfer_dir_with_half_subdir_overrides_date_str(
        self, monkeypatch, full_paths_yaml, tmp_path
    ):
        """Phase 7-pre-multi-half: half_subdir replaces the date_str segment.

        For PS48 20250314 (Pattern A), half-a's WS files live under
        ``{ws_root}/20250314a/PS48/`` — passing ``half_subdir="20250314a"``
        resolves there. The kwarg is *the* mechanism by which the per-half
        discovery in build_manifest finds half-specific WS data.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result_a = resolver.wavesurfer_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir="20250314a"
        )
        result_b = resolver.wavesurfer_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir="20250314b"
        )
        assert result_a == tmp_path / "wavesurfer" / "20250314a" / "PS48"
        assert result_b == tmp_path / "wavesurfer" / "20250314b" / "PS48"

    def test_camera_dir_default_half_subdir_is_date_str(
        self, monkeypatch, full_paths_yaml, tmp_path
    ):
        """Phase 7-pre-multi-half: camera_dir half_subdir mirrors wavesurfer_dir."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.camera_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir=None
        )
        assert result == tmp_path / "camera" / "20250314" / "PS48"

    def test_camera_dir_with_half_subdir_overrides_date_str(
        self, monkeypatch, full_paths_yaml, tmp_path
    ):
        """Phase 7-pre-multi-half: camera-side per-half subdir resolution.

        Camera root mirrors WS root structure (date-then-half-suffix at the
        top level, animal one level deeper). Same kwarg semantics.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result_a = resolver.camera_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir="20250314a"
        )
        result_b = resolver.camera_dir(
            datetime.date(2025, 3, 14), "PS48", half_subdir="20250314b"
        )
        assert result_a == tmp_path / "camera" / "20250314a" / "PS48"
        assert result_b == tmp_path / "camera" / "20250314b" / "PS48"

    # ---- Phase 7-pre-secondary-spout Task 3b: subdir_override kwarg ----

    def test_wavesurfer_dir_uses_subdir_override_when_set(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """Pattern B b-half / asymmetric-bare case: subdir_override
        replaces the date_str segment. Same internal effect as
        half_subdir but documented as the Pattern B caller-intent."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result_b = resolver.wavesurfer_dir(
            datetime.date(2025, 4, 30), "PS51",
            subdir_override="20250430b",
        )
        result_bare_override = resolver.wavesurfer_dir(
            datetime.date(2025, 4, 24), "PS55",
            subdir_override="20250424a",  # asymmetric-bare for PS55/2025-04-24
        )
        assert result_b == tmp_path / "wavesurfer" / "20250430b" / "PS51"
        assert result_bare_override == (
            tmp_path / "wavesurfer" / "20250424a" / "PS55"
        )

    def test_wavesurfer_dir_falls_back_to_date_strftime_when_none(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """Regression: subdir_override=None preserves byte-identical
        pre-PR behavior (subdir = date.strftime('%Y%m%d')). Every
        existing non-Pattern-B call hits this branch."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.wavesurfer_dir(
            datetime.date(2025, 4, 30), "PS51", subdir_override=None,
        )
        assert result == tmp_path / "wavesurfer" / "20250430" / "PS51"

    def test_camera_dir_uses_subdir_override_when_set(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """camera_dir mirrors wavesurfer_dir's subdir_override
        semantics."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.camera_dir(
            datetime.date(2025, 5, 30), "PS54",
            subdir_override="20250530b",
        )
        assert result == tmp_path / "camera" / "20250530b" / "PS54"

    def test_camera_dir_falls_back_to_date_strftime_when_none(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.camera_dir(
            datetime.date(2025, 5, 30), "PS54", subdir_override=None,
        )
        assert result == tmp_path / "camera" / "20250530" / "PS54"

    def test_wavesurfer_dir_rejects_both_kwargs(
        self, monkeypatch, full_paths_yaml,
    ):
        """half_subdir and subdir_override are mutually exclusive —
        passing both raises. Pattern A and Pattern B intents must not
        mix at the same call site."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        with pytest.raises(ValueError, match="mutually exclusive"):
            resolver.wavesurfer_dir(
                datetime.date(2025, 3, 14), "PS48",
                half_subdir="20250314a",
                subdir_override="20250314a",
            )

    def test_camera_dir_rejects_both_kwargs(
        self, monkeypatch, full_paths_yaml,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        with pytest.raises(ValueError, match="mutually exclusive"):
            resolver.camera_dir(
                datetime.date(2025, 3, 14), "PS48",
                half_subdir="20250314a",
                subdir_override="20250314a",
            )

    # ---- Phase 7-pre-secondary-spout Task 3c: per-session output
    # resolvers session_suffix kwarg threading ----

    def test_alignment_template_legacy_read_session_suffix(
        self, monkeypatch,
    ):
        """Per-session output resolver: session_suffix kwarg appends
        to date_str. session_suffix=None preserves pre-PR (regression).

        Uses the default PathResolver config (not full_paths_yaml)
        because alignment_template_legacy_read routes through the
        microscope_server logical root which the test-fixture YAML
        doesn't override."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        date = datetime.date(2025, 4, 30)
        bare = resolver.alignment_template_legacy_read(
            "PS51", date, session_suffix=None,
        )
        b = resolver.alignment_template_legacy_read(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.npz"
        assert b.name == "20250430b.npz"
        # Parent dirs identical (only filename carries the suffix here)
        assert bare.parent == b.parent

    def test_alignment_template_new_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.alignment_template_new("PS51", date)
        b = resolver.alignment_template_new(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.npz"
        assert b.name == "20250430b.npz"

    def test_interpolated_trace_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.interpolated_trace(
            "tongue", "PS51", date,
        )
        b = resolver.interpolated_trace(
            "tongue", "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.parquet"
        assert b.name == "20250430b.parquet"

    def test_tongue_pertrial_angle_parquet_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_pertrial_angle_parquet("PS51", date)
        b = resolver.tongue_pertrial_angle_parquet(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.parquet"
        assert b.name == "20250430b.parquet"

    def test_tongue_pertrial_licking_dynamics_traces_parquet_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
            "PS51", date,
        )
        b = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.parquet"
        assert b.name == "20250430b.parquet"

    def test_tongue_pertrial_endpoints_json_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_pertrial_endpoints_json("PS51", date)
        b = resolver.tongue_pertrial_endpoints_json(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.json"
        assert b.name == "20250430b.json"

    def test_tongue_angle_within_session_dir_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """Directory-pattern resolver (date_str is the dir name, not a
        filename) — session_suffix appends to the dir name."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_angle_within_session_dir("PS51", date)
        b = resolver.tongue_angle_within_session_dir(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430"
        assert b.name == "20250430b"

    def test_jaw_pertrial_endpoints_json_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.jaw_pertrial_endpoints_json("PS51", date)
        b = resolver.jaw_pertrial_endpoints_json(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.json"
        assert b.name == "20250430b.json"

    def test_tongue_jaw_mismatch_candidate_trials_parquet_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
            "PS51", date,
        )
        b = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.parquet"
        assert b.name == "20250430b.parquet"

    def test_tongue_jaw_mismatch_within_session_dir_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """Directory-pattern resolver — session_suffix appends to the
        dir name."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.tongue_jaw_mismatch_within_session_dir(
            "PS51", date,
        )
        b = resolver.tongue_jaw_mismatch_within_session_dir(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430"
        assert b.name == "20250430b"

    def test_alignment_template_per_half_new_rejects_session_suffix(
        self, monkeypatch, full_paths_yaml, tmp_path,
    ):
        """Pattern A multi-half-aware resolver MUST NOT accept a
        session_suffix kwarg — mixing Pattern A's halves_concat_label
        / half_id with Pattern B's session_suffix is a category error.
        Verifies the kickoff's Pattern-A/Pattern-B isolation rule."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml, output_root=tmp_path)
        date = datetime.date(2025, 3, 14)
        # Existing Pattern A call works
        out = resolver.alignment_template_per_half_new(
            "PS48", date, halves_concat_label="ab", half_id="a",
        )
        assert out.name == "20250314a.npz"
        # Passing session_suffix raises TypeError (unexpected kwarg)
        with pytest.raises(TypeError, match="session_suffix"):
            resolver.alignment_template_per_half_new(
                "PS48", date, halves_concat_label="ab", half_id="a",
                session_suffix="b",
            )

    def test_wavesurfer_dir_rejects_session_suffix(
        self, monkeypatch, full_paths_yaml,
    ):
        """Input-path resolver `wavesurfer_dir` already has
        `subdir_override` as its Pattern B kwarg; a `session_suffix`
        kwarg would be redundant/confusing. Must raise TypeError."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        with pytest.raises(TypeError, match="session_suffix"):
            resolver.wavesurfer_dir(
                datetime.date(2025, 4, 30), "PS51",
                session_suffix="b",
            )

    def test_camera_dir_rejects_session_suffix(
        self, monkeypatch, full_paths_yaml,
    ):
        """Same as wavesurfer_dir — camera_dir uses subdir_override."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        with pytest.raises(TypeError, match="session_suffix"):
            resolver.camera_dir(
                datetime.date(2025, 4, 30), "PS51",
                session_suffix="b",
            )

    def test_alignment_template_per_half_new_layout(self, tmp_path: Path):
        """Phase 7-pre-multi-half Decision 3 + 2026-05-05 incident response:
        per-half new-pipeline templates land under pipeline_outputs(
        "dlc_analysis") in the per-(animal, date) subdir alongside the
        parent-level merged template. The _new suffix signals that
        these paths route through pipeline_outputs (safe) instead of
        the live MICROSCOPE legacy tree (unsafe — incident class).
        """
        resolver = PathResolver(output_root=tmp_path / "outputs")
        result_a = resolver.alignment_template_per_half_new(
            "PS48", datetime.date(2025, 3, 14),
            halves_concat_label="ab", half_id="a",
        )
        result_b = resolver.alignment_template_per_half_new(
            "PS48", datetime.date(2025, 3, 14),
            halves_concat_label="ab", half_id="b",
        )
        # Path now routes through pipeline_outputs/dlc_analysis/
        # alignment_templates/, not the legacy O2_analysis tree.
        assert tmp_path in result_a.parents
        assert "dlc_analysis" in result_a.as_posix()
        assert "alignment_templates" in result_a.as_posix()
        assert "O2_analysis" not in result_a.as_posix()
        # Subdir is {date_str}{halves_concat_label}; filename is
        # {date_str}{half_id}.npz. Parent of subdir is animal dir.
        assert result_a.parent.name == "20250314ab"
        assert result_a.name == "20250314a.npz"
        assert result_b.parent.name == "20250314ab"
        assert result_b.name == "20250314b.npz"

    def test_alignment_template_per_half_new_three_halves(self, tmp_path: Path):
        """halves_concat_label generalizes to N halves (e.g., 'abc' for 3)."""
        resolver = PathResolver(output_root=tmp_path / "outputs")
        result = resolver.alignment_template_per_half_new(
            "PS99", datetime.date(2025, 5, 1),
            halves_concat_label="abc", half_id="c",
        )
        assert result.parent.name == "20250501abc"
        assert result.name == "20250501c.npz"

    def test_alignment_template_new_merged_path(self, tmp_path: Path):
        """The new merged-template resolver lives under pipeline_outputs/
        at the parent level (mirror of the legacy parent-level layout
        but in the safe tree)."""
        resolver = PathResolver(output_root=tmp_path / "outputs")
        result = resolver.alignment_template_new(
            "PS48", datetime.date(2025, 3, 14), cam="cam2",
        )
        assert tmp_path in result.parents
        assert "dlc_analysis" in result.as_posix()
        assert "alignment_templates" in result.as_posix()
        assert "O2_analysis" not in result.as_posix()
        assert result.parent.name == "PS48"
        assert result.name == "20250314.npz"

    def test_alignment_template_new_honors_output_root(self, tmp_path: Path):
        """output_root=tmp_path redirects alignment_template_new because
        the latter routes through pipeline_outputs(). Verifies the
        Phase 7-pre-multi-half 2026-05-05 incident response: previously
        the alignment_template resolver routed through microscope_server
        and was NOT redirected by output_root, which was the root cause."""
        # No env-var override needed; default detection handles it.
        resolver = PathResolver(output_root=tmp_path / "outputs")
        result = resolver.alignment_template_new(
            "PS48", datetime.date(2025, 3, 14), cam="cam2",
        )
        # Result lands under tmp_path, NOT under MICROSCOPE.
        assert tmp_path in result.parents
        assert "MICROSCOPE" not in result.as_posix()

    def test_alignment_template_per_half_new_honors_output_root(
        self, tmp_path: Path,
    ):
        """Same output_root invariant for the per-half writer. This is
        the test that would have caught the 2026-05-05 incident before
        it fired."""
        resolver = PathResolver(output_root=tmp_path / "outputs")
        result = resolver.alignment_template_per_half_new(
            "PS48", datetime.date(2025, 3, 14),
            halves_concat_label="ab", half_id="a",
        )
        assert tmp_path in result.parents
        assert "MICROSCOPE" not in result.as_posix()

    # ---- Phase 7-pre-alignment-templates Task 5:
    #      alignment_template_for_reading prefer-new + legacy-fallback ----
    #
    # These tests use monkeypatch.setattr to override the two underlying
    # resolver methods so both candidate paths land in the test sandbox.
    # alignment_template_legacy_read routes through "microscope_server"
    # (not pipeline_outputs), so output_root=tmp_path alone wouldn't
    # redirect the legacy path — and in a real machine config the legacy
    # path may already exist on disk, polluting the test.

    @staticmethod
    def _setup_for_reading_fixture(monkeypatch, tmp_path: Path):
        """Build a resolver whose new + legacy template paths both
        live under tmp_path (independent of the real MICROSCOPE mount)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path / "new_tree")
        new_path = (
            tmp_path / "new_tree" / "dlc_analysis" / "alignment_templates"
            / "cam2" / "PS46" / "20250307.npz"
        )
        legacy_path = (
            tmp_path / "legacy_tree" / "alignment_templates"
            / "cam2" / "PS46" / "20250307.npz"
        )
        monkeypatch.setattr(
            resolver, "alignment_template_new",
            lambda animal, date, cam="cam2", session_suffix=None: new_path,
        )
        monkeypatch.setattr(
            resolver, "alignment_template_legacy_read",
            lambda animal, date, cam="cam2", session_suffix=None: legacy_path,
        )
        return resolver, new_path, legacy_path

    def test_alignment_template_for_reading_prefers_new_tree(
        self, monkeypatch, tmp_path: Path,
    ):
        """When BOTH the new-tree and legacy-tree paths exist, the new
        path wins. Phase 7-pre-alignment-templates F-P-7 cutover
        invariant: after cohort emit, the new tree is authoritative
        for every session that has a new-tree template.
        """
        resolver, new_path, legacy_path = self._setup_for_reading_fixture(
            monkeypatch, tmp_path,
        )
        new_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(b"new")
        legacy_path.write_bytes(b"legacy")

        result = resolver.alignment_template_for_reading(
            "PS46", datetime.date(2025, 3, 7),
        )
        assert result == new_path
        assert result.read_bytes() == b"new"

    def test_alignment_template_for_reading_falls_back_to_legacy(
        self, monkeypatch, tmp_path: Path,
    ):
        """When ONLY the legacy-tree path exists, the resolver falls
        back to legacy. Permanent safety net per Addendum #1 L3 for
        sessions the new pipeline can't emit equivalents for
        (missing/ambiguous raw inputs, hand-emitted incident-response
        templates, archival pre-cohort baseline sessions).
        """
        resolver, new_path, legacy_path = self._setup_for_reading_fixture(
            monkeypatch, tmp_path,
        )
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_bytes(b"legacy")
        assert not new_path.exists()

        result = resolver.alignment_template_for_reading(
            "PS46", datetime.date(2025, 3, 7),
        )
        assert result == legacy_path

    def test_alignment_template_for_reading_raises_if_neither(
        self, monkeypatch, tmp_path: Path,
    ):
        """When neither path exists, raise FileNotFoundError with a
        message that names BOTH candidate paths so the caller can
        debug whether the YAML cohort entry, the WS data, or the
        emit driver is missing.
        """
        resolver, new_path, legacy_path = self._setup_for_reading_fixture(
            monkeypatch, tmp_path,
        )
        assert not new_path.exists()
        assert not legacy_path.exists()

        with pytest.raises(FileNotFoundError) as excinfo:
            resolver.alignment_template_for_reading(
                "PS46", datetime.date(2025, 3, 7),
            )
        msg = str(excinfo.value)
        assert "PS46" in msg
        assert "2025-03-07" in msg
        # Both paths named in the error message
        assert str(new_path) in msg
        assert str(legacy_path) in msg


class TestOutputRootOverride:
    """Task #20: ``output_root=`` kwarg on PathResolver.__init__ overrides the
    ``microscope_pipeline_outputs`` logical root without touching other roots.
    Used by integration tests that write via ``process_session(...,
    overwrite="force")`` to keep those writes inside ``tmp_path`` instead of
    contaminating the real production output tree.
    """

    def test_default_preserves_real_config_derived_path(self, monkeypatch):
        """Omitting the kwarg leaves pipeline_outputs() byte-identical to
        the pre-task-#20 behavior."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()  # no output_root
        result = resolver.pipeline_outputs("spout_behavior")
        # Real config resolves microscope_pipeline_outputs to the MICROSCOPE path
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
            "/spout_behavior"
        )
        assert resolver._output_root_override is None

    def test_override_redirects_pipeline_outputs_only(self, monkeypatch, tmp_path):
        """output_root=tmp_path redirects pipeline_outputs() to tmp_path.
        All other roots (wavesurfer_raw, camera_raw, microscope_server, ...)
        continue to resolve from the real config.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(output_root=tmp_path)
        # pipeline_outputs() now returns tmp_path-rooted paths
        assert resolver.pipeline_outputs("spout_behavior") == tmp_path / "spout_behavior"
        assert resolver.pipeline_outputs("dlc_analysis") == tmp_path / "dlc_analysis"
        # Other convenience methods unaffected — they resolve from their own
        # logical roots (microscope_server, wavesurfer_raw, camera_raw).
        # On the real config those remain real paths even under override.
        # alignment_template_legacy_read intentionally routes through
        # microscope_server even with an output_root override — that's
        # the read-only legacy path. (alignment_template_new IS
        # overridden by output_root; covered separately in
        # TestNewConvenienceMethods.test_alignment_template_new_honors_output_root.)
        alignment = resolver.alignment_template_legacy_read(
            "PS46", datetime.date(2025, 3, 7),
        )
        assert "stroke_orofacial_pipeline_outputs" not in alignment.as_posix()
        assert "DeepLabCut" in alignment.as_posix()
        assert resolver._output_root_override == tmp_path


class TestDefaultConfig:
    def test_loads_repo_config(self, monkeypatch):
        """PathResolver() with no args loads configs/paths.yaml from the repo."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        # Should not raise; microscope_server should be resolvable
        path = resolver.root("microscope_server")
        assert "MICROSCOPE" in str(path) or "Neurobio" in str(path)


class TestInterpolatedTrace:
    """Phase 7a.2: ``interpolated_trace(bodypart, animal, date, *, variant)``
    returns
    ``<output_root>/dlc_analysis/interpolated_traces/<bodypart>/<animal>/<YYYYMMDD>.<ext>``.
    Mirrors ``pipeline_outputs()``'s ``output_root`` test-override hook so
    tests never write to the real pipeline outputs tree."""

    def test_parquet_path(self, monkeypatch, tmp_path):
        """Default variant='parquet' returns a path ending in .parquet."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.interpolated_trace(
            "tongue", "PS46", datetime.date(2025, 3, 7)
        )
        expected = (
            tmp_path
            / "dlc_analysis"
            / "interpolated_traces"
            / "tongue"
            / "PS46"
            / "20250307.parquet"
        )
        assert path == expected
        # Parent directory should be created eagerly.
        assert path.parent.exists() and path.parent.is_dir()

    def test_qc_npz_variant(self, monkeypatch, tmp_path):
        """variant='qc_npz' returns a path ending in .qc.npz."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.interpolated_trace(
            "jaw", "PS51", datetime.date(2025, 4, 30), variant="qc_npz"
        )
        expected = (
            tmp_path
            / "dlc_analysis"
            / "interpolated_traces"
            / "jaw"
            / "PS51"
            / "20250430.qc.npz"
        )
        assert path == expected
        assert path.parent.exists()

    def test_invalid_variant_raises(self, monkeypatch, tmp_path):
        """Unknown variant keyword raises KeyError — guards against typos."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        with pytest.raises(KeyError):
            resolver.interpolated_trace(
                "tongue", "PS46", datetime.date(2025, 3, 7), variant="foo"
            )


class TestTonguePertrialPaths:
    """Phase 7a.3 V3 resolver helpers.

    Three OUTPUT resolvers (angle parquet, licking-dynamics traces parquet,
    endpoints JSON) emit ``%Y%m%d`` filenames matching 7a.2's
    ``interpolated_trace`` convention.

    One INPUT resolver (centered_spout_midpoint) globs
    ``video2_{YYYY-MM-DD}T*.parquet`` (ISO-format date with hyphens —
    upstream filename convention) and asserts exactly-one match.
    """

    def test_tongue_pertrial_angle_parquet_path(self, monkeypatch, tmp_path):
        """Output uses %Y%m%d (matches 7a.2 interpolated_trace).

        Path layout post-Phase-7d:
        ``dlc_kinematics/per_frame/tongue/<animal>/<date>.parquet`` (was
        ``dlc_kinematics/features/tongue/...`` pre-7d).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_angle_parquet(
            "PS50", datetime.date(2025, 3, 19)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "per_frame"
            / "tongue"
            / "PS50"
            / "20250319.parquet"
        )
        assert path == expected
        assert path.parent.exists() and path.parent.is_dir()

    def test_tongue_pertrial_licking_dynamics_traces_parquet_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_licking_dynamics_traces_parquet(
            "PS46", datetime.date(2025, 5, 1)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "licking_dynamics"
            / "traces"
            / "PS46"
            / "20250501.parquet"
        )
        assert path == expected
        assert path.parent.exists()

    def test_tongue_pertrial_endpoints_json_path(self, monkeypatch, tmp_path):
        """Per-(animal, date) per-trial tongue endpoints JSON path.

        Path layout post-Phase-7d:
        ``dlc_kinematics/per_trial/tongue/<animal>/<date>.json`` (was
        ``dlc_kinematics/endpoints/<animal>/<date>.json`` pre-7d —
        top-level, tongue-implicit).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_endpoints_json(
            "PS54", datetime.date(2025, 6, 7)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "per_trial"
            / "tongue"
            / "PS54"
            / "20250607.json"
        )
        assert path == expected
        assert path.parent.exists()

    def test_tongue_pertrial_endpoints_dir_path(self, monkeypatch, tmp_path):
        """New Phase 7d (Addendum #2) directory resolver: per-animal dir of
        per-trial tongue endpoints JSONs. Symmetric with
        :meth:`tongue_pertrial_endpoints_json`. Used by callers that need
        to enumerate every session date for an animal by globbing ``*.json``.

        Discharges 2 pre-7d PathResolver-bypass call sites in
        ``compute_pre_stroke_median_ili_ms`` (tongue_pertrial.py) and
        ``_enumerate_session_dates`` (tongue_angle_cohort.py). Does NOT
        create the directory eagerly (caller decides).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_endpoints_dir("PS46")
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "per_trial"
            / "tongue"
            / "PS46"
        )
        assert path == expected
        # No eager mkdir — directory should NOT exist until a writer
        # (tongue_pertrial_endpoints_json) creates it via its parent mkdir.
        assert not path.exists()

    def test_tongue_pertrial_endpoints_dir_matches_json_parent(
        self, monkeypatch, tmp_path,
    ):
        """The directory resolver must return the same path as the parent
        of the per-(animal, date) JSON resolver for the same animal. This
        invariant guards against drift between the two methods: if one is
        renamed/moved, the other must follow.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        animal = "PS46"
        dir_path = resolver.tongue_pertrial_endpoints_dir(animal)
        json_path = resolver.tongue_pertrial_endpoints_json(
            animal, datetime.date(2025, 3, 7),
        )
        assert dir_path == json_path.parent

    def test_tongue_jaw_mismatch_candidate_trials_dir_path(
        self, monkeypatch, tmp_path,
    ):
        """Phase 7d Task 6 (Addendum #4) — new directory resolver for
        Phase 7a.5 candidate-trials parquets. Symmetric with
        :meth:`tongue_jaw_mismatch_candidate_trials_parquet` (the
        per-(animal, date) file resolver). Discharges 2 PathResolver-
        bypass call sites in ``dlc_kinematics/tongue_jaw_mismatch.py``.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_jaw_mismatch_candidate_trials_dir("PS46")
        expected = (
            tmp_path / "dlc_kinematics" / "tongue_jaw_mismatch"
            / "candidate_trials" / "PS46"
        )
        assert path == expected
        assert not path.exists()

    def test_tongue_jaw_mismatch_candidate_trials_dir_matches_file_parent(
        self, monkeypatch, tmp_path,
    ):
        """Invariant: the directory resolver returns the parent of the
        file resolver for the same animal + any date. Guards against
        drift between the two methods.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        dir_path = resolver.tongue_jaw_mismatch_candidate_trials_dir("PS46")
        file_path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
            "PS46", datetime.date(2025, 3, 7),
        )
        assert dir_path == file_path.parent

    def test_interpolated_trace_dir_path(self, monkeypatch, tmp_path):
        """Phase 7d Task 6 (Addendum #4) — new directory resolver for Phase
        7a.2 interpolated traces. Symmetric with :meth:`interpolated_trace`
        (the per-(animal, date) file resolver). Discharges 1 PathResolver-
        bypass call site in ``dlc_kinematics/mean_sem_visual.py`` that
        manually constructed
        ``pipeline_outputs("dlc_analysis") / "interpolated_traces" / bodypart / animal``.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.interpolated_trace_dir("tongue", "PS46")
        expected = (
            tmp_path / "dlc_analysis" / "interpolated_traces"
            / "tongue" / "PS46"
        )
        assert path == expected
        # Read-only dir resolver — does NOT create the directory eagerly
        # (the file resolver above handles eager parent mkdir when writing).
        assert not path.exists()

    def test_interpolated_trace_dir_path_matches_file_parent(
        self, monkeypatch, tmp_path,
    ):
        """Invariant: the directory resolver returns the parent of the
        file resolver for the same ``(bodypart, animal)`` plus any date.
        Guards against drift between the two methods.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        dir_path = resolver.interpolated_trace_dir("tongue", "PS46")
        file_path = resolver.interpolated_trace(
            "tongue", "PS46", datetime.date(2025, 3, 7),
        )
        assert dir_path == file_path.parent
        # The file resolver creates the parent eagerly, so after the call
        # the directory does exist on disk — but only because of the file
        # resolver's mkdir, not the dir resolver itself.
        assert dir_path.exists()

    def test_spout_licks_and_rewards_npz_path(self, monkeypatch, tmp_path):
        """Phase 7d Task 6 (Addendum #4) — new file resolver for Phase 2
        licks NPZ. Discharges 6 PathResolver-bypass call sites (3 direct +
        3 captured-root indirect) that manually constructed
        ``pipeline_outputs("spout_behavior") / "licks_and_rewards" / animal
        / f"{date_str}.npz"``.

        The ``licks_and_rewards`` directory name is PRESERVED per Phase
        8a.10.1 Decision 8 E.B.1 (rename-cost-without-benefit). Read-only
        resolver — does NOT create the parent directory eagerly.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.spout_licks_and_rewards_npz(
            "PS50", datetime.date(2025, 3, 19),
        )
        expected = (
            tmp_path / "spout_behavior" / "licks_and_rewards"
            / "PS50" / "20250319.npz"
        )
        assert path == expected
        # Read-only resolver — parent dir is NOT created eagerly. The Phase
        # 2 emission code writes NPZs and creates the tree as needed.
        assert not path.exists()
        assert not path.parent.exists()

    def test_spout_licks_and_rewards_npz_session_suffix(
        self, monkeypatch, tmp_path,
    ):
        """``session_suffix=`` appends to the date string (matches the
        existing :meth:`tongue_pertrial_endpoints_json` /
        :meth:`interpolated_trace` convention). ``None`` or ``""`` yields
        the bare-half filename; ``"b"`` yields the Pattern B b-half
        sibling. Added in Phase 7d Task 6 step 5 to discharge 2
        audit-missed sibling sites in ``spout_close_vs_std.py``.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        date = datetime.date(2025, 4, 30)
        bare = resolver.spout_licks_and_rewards_npz("PS51", date)
        b = resolver.spout_licks_and_rewards_npz(
            "PS51", date, session_suffix="b",
        )
        assert bare.name == "20250430.npz"
        assert b.name == "20250430b.npz"
        assert bare.parent == b.parent

    def test_spatial_tone_aligned_npz_path(self, monkeypatch, tmp_path):
        """Phase 7d Task 6 (Addendum #4) — new file resolver for Phase 6
        opt-in tone-aligned spatial heatmap NPZ cache. Discharges 1
        PathResolver-bypass call site in
        ``dlc_spatial/tone_aligned.py`` that manually constructed the
        parametric ``spatial_tone_aligned/<bodypart>_<center_mode>/
        trials-<trial_group>_<win_tag>/<animal>/heatmap_<date>.npz``
        path.

        Dormant in production per Phase 7c.2 Addendum #3 Q2.B — the
        cohort driver never sets ``emit_cache=True``; this resolver
        exists for notebook-12 / one-off inspection use.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.spatial_tone_aligned_npz(
            bodypart="jaw",
            center_mode="spout_midpoint",
            trial_group="tone",
            window_ms=(-500, 0),
            animal="PS50",
            date=datetime.date(2025, 3, 19),
        )
        expected = (
            tmp_path / "dlc_analysis" / "spatial_tone_aligned"
            / "jaw_spout_midpoint" / "trials-tone_-500to0ms" / "PS50"
            / "heatmap_20250319.npz"
        )
        assert path == expected
        # Read-only resolver — does NOT create the parent directory eagerly.
        # The opt-in cache write path creates the tree as needed.
        assert not path.exists()
        assert not path.parent.exists()

    # -----------------------------------------------------------------
    # Phase 7e.4 (Addendum #3) — cleaned_trace parallel paths.
    # Six paired-with-legacy resolvers landing under dlc_kinematics/.
    # Each test asserts:
    #   - path matches the kickoff Addendum #3 §10 table exactly
    #   - directory carries the _cleaned_trace token (Q-lock 15.1)
    #   - filename carries the _cleaned_trace token (Q-lock 15.2)
    #   - no eager directory creation (matches the existing read-only
    #     resolver pattern)
    # -----------------------------------------------------------------

    def test_tone_aligned_heatmap_npz_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tone_aligned_heatmap_npz_cleaned_trace(
            bodypart="tongue",
            center_mode="spout_midpoint",
            trial_group="all",
            window_ms=(0, 8000),
            animal="PS54",
            date=datetime.date(2025, 5, 6),
        )
        expected = (
            tmp_path / "dlc_kinematics"
            / "tone_aligned_heatmaps_cleaned_trace"
            / "tongue_spout_midpoint" / "trials-all_0to8000ms" / "PS54"
            / "heatmap_20250506_cleaned_trace.npz"
        )
        assert path == expected
        # Q-lock 15.1 + 15.2 marker tokens present at both levels.
        assert "_cleaned_trace" in path.parent.parent.parent.parent.name
        assert path.name.endswith("_cleaned_trace.npz")
        assert not path.exists()

    def test_whole_session_heatmap_npz_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.whole_session_heatmap_npz_cleaned_trace(
            bodypart="jaw",
            center_mode="eye_midpoint",
            animal="PS47",
            date=datetime.date(2025, 3, 19),
        )
        expected = (
            tmp_path / "dlc_kinematics"
            / "whole_session_heatmaps_cleaned_trace"
            / "jaw_eye_midpoint" / "PS47"
            / "heatmap_20250319_cleaned_trace.npz"
        )
        assert path == expected
        assert path.name.endswith("_cleaned_trace.npz")

    def test_individual_session_heatmap_png_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.individual_session_heatmap_png_cleaned_trace(
            family_entry="tongue_spout_midpoint",
            scope="tone_aligned",
            animal="PS51",
            date=datetime.date(2025, 5, 6),
        )
        expected = (
            tmp_path / "dlc_kinematics"
            / "individual_session_heatmaps_cleaned_trace"
            / "tongue_spout_midpoint_tone_aligned" / "PS51"
            / "heatmap_20250506_cleaned_trace.png"
        )
        assert path == expected
        assert path.name.endswith("_cleaned_trace.png")

    def test_binned_sessions_heatmap_png_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.binned_sessions_heatmap_png_cleaned_trace(
            family_entry="jaw_eye_midpoint",
            scope="whole_session",
            bin_size_days=10,
            animal="PS54",
            rel_day_bin_label="d+10_to_d+19",
        )
        expected = (
            tmp_path / "dlc_kinematics"
            / "binned_sessions_heatmaps_cleaned_trace"
            / "jaw_eye_midpoint_whole_session_10d" / "PS54"
            / "heatmap_d+10_to_d+19_cleaned_trace.png"
        )
        assert path == expected
        assert path.name.endswith("_cleaned_trace.png")

    def test_proportion_diff_heatmap_png_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        """Q-lock 12 (Phase 9.1 phenotype-pooled proportion_diff)
        consumes this path; locking it here pins the contract."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.proportion_diff_heatmap_png_cleaned_trace(
            family_entry="tongue_spout_midpoint",
            scope="tone_aligned",
            bin_size_days=10,
            animal="PS54",
            rel_day_bin_label="d+10_to_d+19",
        )
        expected = (
            tmp_path / "dlc_kinematics"
            / "proportion_diff_cleaned_trace"
            / "tongue_spout_midpoint_tone_aligned_10d" / "PS54"
            / "diff_d+10_to_d+19_cleaned_trace.png"
        )
        assert path == expected
        assert "proportion_diff_cleaned_trace" in str(path)
        assert path.name.endswith("_cleaned_trace.png")

    def test_phase_9_stats_spatial_cleaned_trace_path(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.phase_9_stats_spatial_cleaned_trace()
        expected = tmp_path / "phase_9_stats" / "spatial_cleaned_trace"
        assert path == expected

    def test_dlc_centered_parquet_dir_path(self, monkeypatch, tmp_path):
        """Phase 7d Task 6 (Addendum #4) — new directory resolver for Phase 4
        centered DLC parquets, parametric on ``center_mode``. Discharges 5
        PathResolver-bypass call sites that manually constructed
        ``pipeline_outputs("dlc_analysis") / f"centered_{center_mode}" / animal``.

        Does NOT create the directory eagerly (caller decides; Phase 4 write
        code creates as needed).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.dlc_centered_parquet_dir("spout_midpoint", "PS50")
        expected = (
            tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS50"
        )
        assert path == expected
        assert not path.exists()
        # Parametric in center_mode: a different mode resolves to a sibling dir.
        other = resolver.dlc_centered_parquet_dir("nose", "PS50")
        assert other == tmp_path / "dlc_analysis" / "centered_nose" / "PS50"
        assert other.parent == path.parent.parent / "centered_nose"

    def test_dlc_centered_spout_midpoint_parquet_globs_and_returns_unique_match(
        self, monkeypatch, tmp_path,
    ):
        """Resolver globs `video2_{YYYY-MM-DD}T*.parquet` (ISO-format date)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        target_dir = (
            tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55"
        )
        target_dir.mkdir(parents=True)
        fake_parquet = (
            target_dir
            / (
                "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5"
                "_snapshot_060_filtered.h5.intermediate.deadbeef.parquet"
            )
        )
        fake_parquet.touch()
        # Decoy: a parquet for a different date should be ignored.
        decoy = (
            target_dir
            / (
                "video2_2025-05-01T08_00_00DLC_Resnet50_video2Jan26shuffle5"
                "_snapshot_060_filtered.h5.intermediate.deadbeef.parquet"
            )
        )
        decoy.touch()
        resolved = resolver.dlc_centered_spout_midpoint_parquet(
            "PS55", datetime.date(2025, 4, 30)
        )
        assert resolved == fake_parquet

    def test_dlc_centered_spout_midpoint_parquet_raises_on_zero_matches(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        target_dir = (
            tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55"
        )
        target_dir.mkdir(parents=True)
        with pytest.raises(
            FileNotFoundError,
            match="No centered_spout_midpoint parquet",
        ):
            resolver.dlc_centered_spout_midpoint_parquet(
                "PS55", datetime.date(2025, 4, 30)
            )

    def test_dlc_centered_spout_midpoint_parquet_raises_on_multiple_matches(
        self, monkeypatch, tmp_path,
    ):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        target_dir = (
            tmp_path / "dlc_analysis" / "centered_spout_midpoint" / "PS55"
        )
        target_dir.mkdir(parents=True)
        # Two param-sig versions of the same date — upstream re-emit smell.
        (
            target_dir
            / (
                "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5"
                "_snapshot_060_filtered.h5.intermediate.deadbeef.parquet"
            )
        ).touch()
        (
            target_dir
            / (
                "video2_2025-04-30T12_00_00DLC_Resnet50_video2Jan26shuffle5"
                "_snapshot_060_filtered.h5.intermediate.cafef00d.parquet"
            )
        ).touch()
        with pytest.raises(
            RuntimeError,
            match="Multiple centered_spout_midpoint parquets",
        ):
            resolver.dlc_centered_spout_midpoint_parquet(
                "PS55", datetime.date(2025, 4, 30)
            )


class TestPhase7a4Paths:
    """Phase 7a.4 resolver helpers.

    Two resolvers covered (third resolver retired in
    Phase 7a.4-orientation-and-paths-cleanup, 2026-05-03):

    - ``tongue_pertrial_licking_dynamics_day_binned_parquet`` — file
      resolver, eager parent mkdir matching the 7a.3 V3 file-resolver
      convention. Filename uses the legacy ``f"{lo}..{hi}"`` rel_day_bin
      label literal (NTFS-legal; preserved for traceability).
    - ``tongue_angle_dir`` — directory resolver, no eager mkdir
      (renderer creates). Renamed from ``tongue_visual_qc_dir`` and
      moved out of the ``figures_qc/`` subtree by 7a.4-orientation-
      and-paths-cleanup once the visual gate locked PASS.

    The previously-existing ``tongue_visual_comparison_dir`` resolver
    was deleted by 7a.4-orientation-and-paths-cleanup along with the
    ``render_comparison_grid`` renderer it served.
    """

    def test_tongue_pertrial_licking_dynamics_day_binned_parquet_path(
        self, monkeypatch, tmp_path,
    ):
        """Day-binned parquet: legacy `..` label literal preserved."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_licking_dynamics_day_binned_parquet(
            "PS54", "1..7"
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "licking_dynamics"
            / "day_binned"
            / "PS54"
            / "1..7.parquet"
        )
        assert path == expected
        assert path.parent.exists() and path.parent.is_dir()

    def test_tongue_pertrial_licking_dynamics_day_binned_parquet_pre_bin(
        self, monkeypatch, tmp_path,
    ):
        """Pre-stroke bin label `-1..0` survives the resolver round-trip."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_licking_dynamics_day_binned_parquet(
            "PS46", "-1..0"
        )
        assert path.name == "-1..0.parquet"
        assert path.parent.name == "PS46"

    def test_tongue_angle_within_session_dir_path(self, monkeypatch, tmp_path):
        """Angle/phase per-session PNG directory: no eager mkdir
        (renderer creates).

        Naming history:
          - Pre-7a.4-paths-cleanup: ``test_tongue_visual_qc_dir_path``
            → ``figures_qc/tongue/...``
          - 7a.4-paths-cleanup (2026-05-03):
            ``test_tongue_angle_dir_path`` →
            ``tongue_angle/{animal}/{date}/``.
          - Phase 7a.4-cross-session-angle Addendum #17 (2026-05-04):
            renamed to ``test_tongue_angle_within_session_dir_path`` →
            ``tongue_angle/within_session/{animal}/{date}/`` for
            symmetry with the cross-session sibling.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_angle_within_session_dir(
            "PS50", datetime.date(2025, 3, 19)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "tongue_angle"
            / "within_session"
            / "PS50"
            / "20250319"
        )
        assert path == expected
        assert not path.exists()


class TestPhase7a5Paths:
    """Phase 7a.5 resolver helpers (tongue-jaw mismatch + jaw per-trial).

    Four new resolvers added for the mismatch classifier + plotter port and
    the standalone jaw per-trial features module (hybrid B1.5 sub-variant —
    two modules, single phase):

    - ``jaw_pertrial_endpoints_json`` — file resolver, eager parent mkdir
      matching the 7a.3 V3 ``tongue_pertrial_endpoints_json`` convention.
    - ``tongue_jaw_mismatch_candidate_trials_parquet`` — file resolver,
      eager parent mkdir.
    - ``tongue_jaw_mismatch_within_session_dir`` — directory resolver, no
      eager mkdir (renderer creates). Renamed from
      ``tongue_jaw_mismatch_qc_dir`` in Phase 7a.4-orientation-and-paths-
      cleanup (2026-05-03); path renamed from ``figures_qc/`` to
      ``within_session/`` for symmetry with the ``cross_session/`` sibling.
    - ``tongue_jaw_mismatch_cross_session_dir`` — directory resolver, no
      eager mkdir (renderer creates). Per-mouse only (no date dimension).
    """

    def test_jaw_pertrial_endpoints_json_path(self, monkeypatch, tmp_path):
        """Per-trial jaw scalars JSON: %Y%m%d filename + eager parent mkdir.

        Path layout post-Phase-7d:
        ``dlc_kinematics/per_trial/jaw/<animal>/<date>.json`` (was
        ``dlc_kinematics/jaw_pertrial/endpoints/<animal>/<date>.json``
        pre-7d — symmetric with the tongue sibling at
        ``per_trial/tongue/``).
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.jaw_pertrial_endpoints_json(
            "PS46", datetime.date(2025, 3, 7)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "per_trial"
            / "jaw"
            / "PS46"
            / "20250307.json"
        )
        assert path == expected
        assert path.parent.exists() and path.parent.is_dir()
        assert not path.exists()  # only parent is created, not the file itself

    def test_tongue_jaw_mismatch_candidate_trials_parquet_path(
        self, monkeypatch, tmp_path,
    ):
        """Candidate-trials parquet: per-session %Y%m%d + eager parent mkdir."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
            "PS50", datetime.date(2025, 3, 19)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "tongue_jaw_mismatch"
            / "candidate_trials"
            / "PS50"
            / "20250319.parquet"
        )
        assert path == expected
        assert path.parent.exists() and path.parent.is_dir()
        assert not path.exists()

    def test_tongue_jaw_mismatch_within_session_dir_path(
        self, monkeypatch, tmp_path,
    ):
        """Within-session figures directory: no eager mkdir (renderer creates).

        Renamed from ``test_tongue_jaw_mismatch_qc_dir_path`` in
        Phase 7a.4-orientation-and-paths-cleanup (2026-05-03);
        path renamed ``figures_qc/`` → ``within_session/``.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_jaw_mismatch_within_session_dir(
            "PS54", datetime.date(2025, 6, 7)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "tongue_jaw_mismatch"
            / "within_session"
            / "PS54"
            / "20250607"
        )
        assert path == expected
        assert not path.exists()
        # Ancestor up to <outputs>/dlc_kinematics must also remain uncreated
        # (no implicit mkdir at any level for directory resolvers).
        assert not (
            tmp_path / "dlc_kinematics" / "tongue_jaw_mismatch"
        ).exists()

    def test_tongue_jaw_mismatch_cross_session_dir_path(
        self, monkeypatch, tmp_path,
    ):
        """Cross-session figures directory: per-mouse only (no date), no eager mkdir."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_jaw_mismatch_cross_session_dir("PS55")
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "tongue_jaw_mismatch"
            / "cross_session"
            / "PS55"
        )
        assert path == expected
        # Round-trip: callers must retain control over directory creation.
        # Resolver returns the path only; nothing on disk should exist yet.
        assert not path.exists()
        assert not path.parent.exists()
        # Caller-driven mkdir succeeds (sanity-check the round-trip).
        path.mkdir(parents=True)
        assert path.exists() and path.is_dir()

    def test_tongue_angle_cross_session_dir_path(
        self, monkeypatch, tmp_path,
    ):
        """Phase 7a.4-cross-session-angle Addendum #17 (2026-05-04):
        per-mouse cross-session figure output directory at
        ``dlc_kinematics/tongue_angle/cross_session/{animal}/`` —
        renamed from the initial ``tongue_angle_cohort/{animal}/``
        layout for symmetry with the within_session sibling and the
        tongue_jaw_mismatch ``within_session/`` + ``cross_session/``
        layout.
        """
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_angle_cross_session_dir("PS46")
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "tongue_angle"
            / "cross_session"
            / "PS46"
        )
        assert path == expected
        # No eager mkdir — caller (the cohort renderer) creates the dir.
        assert not path.exists()
        # Note: parent ``dlc_kinematics/tongue_angle/`` may exist if a
        # within_session/ sibling has been created by another test
        # (legitimately co-located now). Don't assert non-existence
        # of grandparent.
        # Caller-driven mkdir round-trips.
        path.mkdir(parents=True)
        assert path.exists() and path.is_dir()


# ---- Phase 7c.2 Addendum #9 — Task 5 heatmap path resolvers ----


class TestTask5HeatmapPathResolvers:
    """8 new path resolvers per Addendum #9 Q12.B. Both tone_aligned and
    whole_session variants for each of 4 plot types (individual_session,
    binned_sessions, proportion_differences, unbalanced_ot)."""

    @pytest.fixture()
    def resolver(self, tmp_path):
        return PathResolver(output_root=tmp_path)

    def test_tone_aligned_individual_session_path(self, resolver, tmp_path):
        import datetime
        p = resolver.tone_aligned_heatmap_individual_session_path(
            "PS46", "tongue_eye_midpoint", datetime.date(2025, 3, 7),
        )
        assert p == (
            tmp_path / "dlc_kinematics" / "tone_aligned_heatmaps" / "PS46"
            / "tongue_eye_midpoint" / "individual_session" / "20250307.svg"
        )
        assert p.parent.exists()  # mkdir eager

    def test_tone_aligned_individual_session_path_session_suffix(self, resolver, tmp_path):
        import datetime
        p = resolver.tone_aligned_heatmap_individual_session_path(
            "PS54", "tongue_spout_midpoint", datetime.date(2025, 6, 20),
            session_suffix="b",
        )
        assert p.name == "20250620b.svg"

    def test_tone_aligned_binned_sessions_path(self, resolver, tmp_path):
        # Q36 Addendum #34: binned_sessions emits ONE grid SVG per
        # (bin_size, trial_group). Filename
        # `binned_sessions_grid_bin{N}d_{tg}.svg`.
        p_all = resolver.tone_aligned_heatmap_binned_sessions_path(
            "PS46", "jaw_eye_midpoint", 2, "all",
        )
        assert p_all == (
            tmp_path / "dlc_kinematics" / "tone_aligned_heatmaps" / "PS46"
            / "jaw_eye_midpoint" / "binned_sessions"
            / "binned_sessions_grid_bin2d_all.svg"
        )
        p_L = resolver.tone_aligned_heatmap_binned_sessions_path(
            "PS46", "jaw_eye_midpoint", 7, "L",
        )
        assert p_L.name == "binned_sessions_grid_bin7d_L.svg"
        assert p_all.parent.exists()

    def test_tone_aligned_proportion_differences_path(self, resolver, tmp_path):
        # Addendum #11 Q2.B + Addendum #15 Q16: filename
        # bin{N}d_{trial_group}.svg per (bin_size, trial_group).
        p_all_2 = resolver.tone_aligned_heatmap_proportion_differences_path(
            "PS46", "nose_eye_midpoint", 2, "all",
        )
        assert p_all_2 == (
            tmp_path / "dlc_kinematics" / "tone_aligned_heatmaps" / "PS46"
            / "nose_eye_midpoint" / "proportion_differences" / "bin2d_all.svg"
        )
        p_L_7 = resolver.tone_aligned_heatmap_proportion_differences_path(
            "PS46", "nose_eye_midpoint", 7, "L",
        )
        assert p_L_7.name == "bin7d_L.svg"
        p_R_2 = resolver.tone_aligned_heatmap_proportion_differences_path(
            "PS46", "nose_eye_midpoint", 2, "R",
        )
        assert p_R_2.name == "bin2d_R.svg"
        assert p_all_2.parent.exists()

    def test_tone_aligned_unbalanced_ot_path(self, resolver, tmp_path):
        # Addendum #14 Q3d.B + Addendum #15 Q16: per-bin + per-trial-group fanout.
        p_all_2 = resolver.tone_aligned_heatmap_unbalanced_ot_path(
            "PS46", "whiskers_eye_midpoint", 2, "all",
        )
        assert p_all_2 == (
            tmp_path / "dlc_kinematics" / "tone_aligned_heatmaps" / "PS46"
            / "whiskers_eye_midpoint" / "unbalanced_ot"
            / "unbalanced_ot_grid_bin2d_all.svg"
        )
        p_L_7 = resolver.tone_aligned_heatmap_unbalanced_ot_path(
            "PS46", "whiskers_eye_midpoint", 7, "L",
        )
        assert p_L_7.name == "unbalanced_ot_grid_bin7d_L.svg"
        p_R_2 = resolver.tone_aligned_heatmap_unbalanced_ot_path(
            "PS46", "whiskers_eye_midpoint", 2, "R",
        )
        assert p_R_2.name == "unbalanced_ot_grid_bin2d_R.svg"

    def test_whole_session_individual_session_path(self, resolver, tmp_path):
        import datetime
        p = resolver.whole_session_heatmap_individual_session_path(
            "PS50", "tongue_spout_midpoint", datetime.date(2025, 3, 25),
        )
        assert p == (
            tmp_path / "dlc_kinematics" / "whole_session_heatmaps" / "PS50"
            / "tongue_spout_midpoint" / "individual_session" / "20250325.svg"
        )
        assert p.parent.exists()

    def test_whole_session_binned_sessions_path(self, resolver, tmp_path):
        # Q36 Addendum #34: whole_session has no trial-group fanout per
        # Q16; filename `binned_sessions_grid_bin{N}d.svg` (no _tg suffix).
        p = resolver.whole_session_heatmap_binned_sessions_path(
            "PS51", "whiskers_eye_midpoint", 7,
        )
        assert p == (
            tmp_path / "dlc_kinematics" / "whole_session_heatmaps" / "PS51"
            / "whiskers_eye_midpoint" / "binned_sessions"
            / "binned_sessions_grid_bin7d.svg"
        )

    def test_whole_session_proportion_differences_path(self, resolver, tmp_path):
        # Addendum #11 Q2.B.
        p7 = resolver.whole_session_heatmap_proportion_differences_path(
            "PS54", "jaw_eye_midpoint", 7,
        )
        assert p7.name == "bin7d.svg"
        assert p7.parent.name == "proportion_differences"
        p2 = resolver.whole_session_heatmap_proportion_differences_path(
            "PS54", "jaw_eye_midpoint", 2,
        )
        assert p2.name == "bin2d.svg"

    def test_whole_session_unbalanced_ot_path(self, resolver, tmp_path):
        # Addendum #14 Q3d.B: bin-fanout filename.
        p2 = resolver.whole_session_heatmap_unbalanced_ot_path(
            "PS55", "tongue_eye_midpoint", 2,
        )
        assert p2.name == "unbalanced_ot_grid_bin2d.svg"
        assert p2.parent.name == "unbalanced_ot"
        p7 = resolver.whole_session_heatmap_unbalanced_ot_path(
            "PS55", "tongue_eye_midpoint", 7,
        )
        assert p7.name == "unbalanced_ot_grid_bin7d.svg"


# ---- Integration test (requires real mount) ----

_MOUNT = Path("/Volumes/Neurobio/MICROSCOPE/Priya")


@pytest.mark.skipif(
    not _MOUNT.exists(),
    reason="MICROSCOPE server not mounted at /Volumes/Neurobio/MICROSCOPE/Priya",
)
class TestIntegrationMount:
    def test_dlc_output_dir_exists(self, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        dlc_dir = resolver.dlc_output_dir("PS46")
        assert dlc_dir.exists(), f"Expected {dlc_dir} to exist on mounted server"

    def test_alignment_templates_exist(self, monkeypatch):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver()
        tmpl_dir = resolver.alignment_templates_dir("cam2")
        assert tmpl_dir.exists(), f"Expected {tmpl_dir} to exist"
