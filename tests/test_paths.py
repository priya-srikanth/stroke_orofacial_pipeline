"""Tests for stroke_orofacial.paths.PathResolver."""

from __future__ import annotations

import datetime
import os
import textwrap
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from stroke_orofacial.paths import PathResolver


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
        expected = PurePosixPath(
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/PS46"
        )
        assert result == expected

    def test_alignment_templates_dir(self):
        result = self.resolver.alignment_templates_dir("cam2")
        assert result == PurePosixPath(
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2"
        )

    def test_alignment_template(self):
        result = self.resolver.alignment_template(
            "PS46", datetime.date(2025, 3, 7), cam="cam2"
        )
        assert result == PurePosixPath(
            "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis/alignment_templates/cam2/PS46/20250307.npz"
        )

    def test_session_processing_out(self):
        result = self.resolver.session_processing_out("v2")
        assert result == PurePosixPath(
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

        cfg = tmp_path / "paths.yaml"
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  wavesurfer_raw:
                    description: "test list mount"
                    mounts:
                      mac:
                        - "{candidate_a}"
                        - "{candidate_b}"
                      windows: "\\\\\\\\server\\\\wavesurfer"
            """)
        )
        return cfg

    def test_list_mount_uses_first_existing(self, monkeypatch, list_mount_yaml, tmp_path):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
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
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  wavesurfer_raw:
                    description: "both exist"
                    mounts:
                      mac:
                        - "{candidate_a}"
                        - "{candidate_b}"
            """)
        )
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
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
        cfg.write_text(
            textwrap.dedent(f"""\
                logical_roots:
                  microscope_pipeline_outputs:
                    description: "outputs"
                    mounts:
                      mac: "/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2"
                  wavesurfer_raw:
                    description: "raw ws"
                    mounts:
                      mac:
                        - "{ws_dir}"
            """)
        )
        return cfg

    def test_pipeline_outputs(self, monkeypatch, full_paths_yaml):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.pipeline_outputs("spout_behavior")
        assert result == PurePosixPath(
            "/Volumes/Neurobio/MICROSCOPE/Priya/pipeline_outputs_v2/spout_behavior"
        )

    def test_wavesurfer_dir(self, monkeypatch, full_paths_yaml, tmp_path):
        monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
        resolver = PathResolver(full_paths_yaml)
        result = resolver.wavesurfer_dir(datetime.date(2025, 3, 7), "PS46")
        ws_dir = tmp_path / "wavesurfer"
        assert result == ws_dir / "20250307" / "PS46"


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
