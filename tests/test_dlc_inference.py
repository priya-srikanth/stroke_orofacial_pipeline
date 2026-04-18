"""Tests for stroke_orofacial.dlc_inference_o2.

No GPU integration tests — inference requires O2. These tests verify
script generation, YAML structure, SBATCH content, and rename logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stroke_orofacial.dlc_inference_o2.runner import generate_inference_script
from stroke_orofacial.dlc_inference_o2.batch import (
    discover_camera_dates,
    discover_videos,
    write_selection_yaml,
)
from stroke_orofacial.dlc_inference_o2.o2_job import generate_sbatch_script, o2_paths
from stroke_orofacial.dlc_inference_o2.transfer import (
    build_copy_to_microscope_command,
    build_rename_command,
    build_stage_videos_command,
    rename_snapshots_local,
)


class TestGenerateInferenceScript:
    def test_contains_deeplabcut_calls(self):
        script = generate_inference_script()
        assert "deeplabcut.analyze_videos" in script
        assert "deeplabcut.filterpredictions" in script
        assert "import deeplabcut" in script

    def test_contains_argparse(self):
        script = generate_inference_script()
        assert "--config" in script
        assert "--shuffle" in script
        assert "--batchsize" in script
        assert "--skip_if_exists" in script

    def test_is_valid_python_syntax(self):
        script = generate_inference_script()
        compile(script, "<run_dlc_batch.py>", "exec")


class TestBatch:
    def test_discover_camera_dates(self, tmp_path):
        (tmp_path / "20250307").mkdir()
        (tmp_path / "20250308").mkdir()
        (tmp_path / "readme.txt").touch()
        dates = discover_camera_dates(tmp_path)
        assert dates == ["20250307", "20250308"]

    def test_discover_videos(self, tmp_path):
        vdir = tmp_path / "20250307" / "PS46"
        vdir.mkdir(parents=True)
        (vdir / "video2_2025-03-07T11_50_41.avi").touch()
        (vdir / "video1_2025-03-07T11_50_41.avi").touch()
        vids = discover_videos(tmp_path, "PS46", "20250307")
        assert len(vids) == 1
        assert "video2" in vids[0].name

    def test_write_selection_yaml(self, tmp_path):
        path = tmp_path / "selection.yaml"
        write_selection_yaml(path, {
            "PS46": {"include": "all", "exclude": []},
            "PS51": {"include": ["20250416"], "exclude": ["20250426"]},
        })
        assert path.exists()
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "PS46" in data["animals"]
        assert data["animals"]["PS51"]["include"] == ["20250416"]


class TestO2Job:
    def _config(self):
        return {
            "partition": "gpu",
            "gres": "gpu:1",
            "cpus_per_task": 10,
            "mem": "30G",
            "time": "9:30:00",
            "exclude_nodes": "compute-g-16-[254-255]",
            "conda_module": "conda/miniforge3/24.11.3-0",
            "conda_env": "deeplabcut",
            "shuffle": 5,
            "trainingsetindex": 0,
            "gputouse": 0,
            "batchsize": 1,
            "video_glob": "video2_*.avi",
            "scratch_root": "/n/scratch/users/{username_initial}/{username}",
            "camera_source": "/n/files/.../camera",
            "dlc_config_source": "/n/files/.../DLC_train_config",
            "data1_staging": "/n/data1/.../O2_staging",
            "microscope_dest": "/n/files/.../O2_analysis",
            "transfer_host": "transfer.rc.hms.harvard.edu",
        }

    def test_sbatch_contains_resources(self):
        script = generate_sbatch_script(self._config(), "ps150")
        assert "#SBATCH -p gpu" in script
        assert "--gres=gpu:1" in script
        assert "--mem=30G" in script
        assert "conda activate deeplabcut" in script
        assert "--shuffle 5" in script

    def test_o2_paths_resolved(self):
        p = o2_paths(self._config(), "ps150")
        assert p["scratch"] == "/n/scratch/users/p/ps150"
        assert p["dlc_in"] == "/n/scratch/users/p/ps150/dlc_in"


class TestTransfer:
    def _config(self):
        return {
            "scratch_root": "/n/scratch/users/{username_initial}/{username}",
            "camera_source": "/n/files/.../camera",
            "data1_staging": "/n/data1/.../staging",
            "microscope_dest": "/n/files/.../O2_analysis",
            "transfer_host": "transfer.rc.hms.harvard.edu",
            "snapshot_renames": {
                "snapshot-best-60": "snapshot_060",
                "snapshot_best-60": "snapshot_060",
            },
        }

    def test_stage_command_contains_rsync(self):
        cmd = build_stage_videos_command(self._config(), "ps150", ["PS46"], ["20250307"])
        assert "rsync" in cmd
        assert "PS46" in cmd
        assert "20250307" in cmd

    def test_copy_command_two_stage(self):
        cmd = build_copy_to_microscope_command(self._config(), "ps150", via_data1=True)
        assert "Stage 1" in cmd
        assert "Stage 2" in cmd
        assert "transfer.rc.hms.harvard.edu" in cmd

    def test_rename_command_contains_pattern(self):
        cmd = build_rename_command(self._config(), "ps150")
        assert "snapshot-best-60" in cmd
        assert "snapshot_060" in cmd

    def test_rename_snapshots_local(self, tmp_path):
        (tmp_path / "video_snapshot-best-60_filtered.h5").touch()
        (tmp_path / "video_snapshot_best-60_filtered.csv").touch()
        (tmp_path / "video_snapshot_060_meta.pickle").touch()  # already renamed
        count = rename_snapshots_local(tmp_path)
        assert count == 2
        assert (tmp_path / "video_snapshot_060_filtered.h5").exists()
        assert (tmp_path / "video_snapshot_060_filtered.csv").exists()
        assert (tmp_path / "video_snapshot_060_meta.pickle").exists()
