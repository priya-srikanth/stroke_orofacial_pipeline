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

    def test_visual_gate_dir(self, monkeypatch, full_paths_yaml):
        """Phase 8a.10 commit-group 1: per-mouse visual-gate output dir
        nests under `pipeline_outputs("spout_behavior")/visual_gate/<animal>/`."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.visual_gate_dir("PS51")
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/"
            "spout_behavior/visual_gate/PS51"
        )

    def test_visual_gate_dir_respects_output_root_override(self, tmp_path):
        """Phase 8a.10 commit-group 1: PathResolver(output_root=tmp_path)
        scopes visual_gate writes to tmp_path (test-hook contract from
        docs/testing-conventions.md)."""
        resolver = PathResolver(output_root=tmp_path)
        result = resolver.visual_gate_dir("PS46")
        assert result == tmp_path / "spout_behavior" / "visual_gate" / "PS46"

    def test_visual_gate_summary_dir(self, monkeypatch, full_paths_yaml):
        """Phase 8a.10 commit-group 5: cohort-summary dir nests under
        pipeline_outputs("spout_behavior")/<name>/."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.visual_gate_summary_dir("summary_PS46_PS47")
        assert result.as_posix() == (
            "/Volumes/Neurobio/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/"
            "spout_behavior/summary_PS46_PS47"
        )

    def test_visual_gate_summary_dir_respects_output_root_override(self, tmp_path):
        resolver = PathResolver(output_root=tmp_path)
        result = resolver.visual_gate_summary_dir("summary_PS51_PS54_PS55")
        assert result == tmp_path / "spout_behavior" / "summary_PS51_PS54_PS55"

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
        """Output uses %Y%m%d (matches 7a.2 interpolated_trace)."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_angle_parquet(
            "PS50", datetime.date(2025, 3, 19)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "features"
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
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.tongue_pertrial_endpoints_json(
            "PS54", datetime.date(2025, 6, 7)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "endpoints"
            / "PS54"
            / "20250607.json"
        )
        assert path == expected
        assert path.parent.exists()

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
        """Per-trial jaw scalars JSON: %Y%m%d filename + eager parent mkdir."""
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(output_root=tmp_path)
        path = resolver.jaw_pertrial_endpoints_json(
            "PS46", datetime.date(2025, 3, 7)
        )
        expected = (
            tmp_path
            / "dlc_kinematics"
            / "jaw_pertrial"
            / "endpoints"
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
