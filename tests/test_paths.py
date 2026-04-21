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

    def test_alignment_template(self):
        result = self.resolver.alignment_template(
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
        # microscope_pipeline_outputs uses a static /Volumes path so we keep it
        # under the "mac" key — the tests that read it force platform_key='mac'.
        # wavesurfer_raw uses a real on-disk tmp_path, so it MUST go under the
        # HOST platform's key (see _HOST_KEY note at top of file). Two mounts
        # under potentially-different platform keys is fine because each test
        # only touches one root. .as_posix() avoids Windows \U escape parsing
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

    def test_wavesurfer_dir(self, monkeypatch, full_paths_yaml, tmp_path):
        # Uses the real on-disk tmp_path mount, so must run under host key.
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", _HOST_KEY)
        resolver = PathResolver(full_paths_yaml)
        result = resolver.wavesurfer_dir(datetime.date(2025, 3, 7), "PS46")
        ws_dir = tmp_path / "wavesurfer"
        assert result == ws_dir / "20250307" / "PS46"


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
        alignment = resolver.alignment_template("PS46", datetime.date(2025, 3, 7))
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
