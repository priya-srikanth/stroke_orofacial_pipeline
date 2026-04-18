"""Video discovery and YAML selection file generation for DLC inference.

Ported from cells 7-8 of canonical notebook
``20251112_DLC_batch_video_analysis_O2.ipynb``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DATE_RE = re.compile(r"^\d{8}b?$")


def discover_camera_dates(camera_dir: Path) -> list[str]:
    """List available date folders under the camera root.

    Parameters
    ----------
    camera_dir : Path
        Camera root directory (e.g. ``/n/files/.../camera/``).

    Returns
    -------
    list[str]
        Sorted list of YYYYMMDD date strings.
    """
    if not camera_dir.exists():
        return []
    return sorted(
        p.name for p in camera_dir.iterdir()
        if p.is_dir() and DATE_RE.match(p.name)
    )


def discover_videos(
    camera_dir: Path,
    animal: str,
    date: str,
    video_glob: str = "video2_*.avi",
) -> list[Path]:
    """Find video files for one animal on one date.

    Parameters
    ----------
    camera_dir : Path
        Camera root directory.
    animal : str
        Animal ID (e.g. ``"PS46"``).
    date : str
        Date string (YYYYMMDD).
    video_glob : str
        Glob pattern for video files. Default ``"video2_*.avi"`` (cam2).

    Returns
    -------
    list[Path]
        Sorted list of matching video files.
    """
    vdir = camera_dir / date / animal
    if not vdir.is_dir():
        return []
    return sorted(vdir.glob(video_glob))


def write_selection_yaml(
    path: Path,
    animals: dict[str, dict[str, Any]],
) -> None:
    """Write a video selection YAML file for ``run_dlc_batch.py``.

    Parameters
    ----------
    path : Path
        Output YAML path.
    animals : dict
        ``{animal_id: {"include": list|"all", "exclude": list}}``.

    Example output::

        animals:
          PS46:
            include: all
            exclude: []
          PS51:
            include: [20250416, 20250417]
            exclude: [20250426]
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"animals": animals}
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
