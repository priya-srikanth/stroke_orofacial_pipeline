"""Load alignment templates and discover camera CSV files.

Alignment templates are NPZ files produced by the alignment pipeline
(legacy or new) that map between wavesurfer sample indices and camera
frame indices via a sync signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def load_alignment_template(path: Path | str) -> dict[str, Any]:
    """Load an existing alignment template NPZ file.

    Parameters
    ----------
    path : Path or str
        Path to the ``.npz`` file.

    Returns
    -------
    dict[str, Any]
        All arrays from the NPZ, keyed by name.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Alignment template not found: {path}")
    return dict(np.load(path, allow_pickle=True))


def pick_camera_csv(session_dir: Path, cam_idx: int = 2) -> Path:
    """Find the timestamp CSV for a given camera in a session directory.

    Matches ``timestamp{cam_idx}_*.csv`` and picks the latest lexicographically
    (timestamps in the filename make this safe).

    Parameters
    ----------
    session_dir : Path
        Camera session directory, e.g.
        ``/Volumes/.../camera/20250307/PS46``.
    cam_idx : int
        Camera index (1-4). Default 2 (DLC camera).

    Returns
    -------
    Path
        The discovered CSV file.

    Raises
    ------
    FileNotFoundError
        If the directory doesn't exist or no matching CSV is found.
    """
    if not session_dir.exists():
        raise FileNotFoundError(f"Camera session directory not found: {session_dir}")

    hits = sorted(session_dir.glob(f"timestamp{cam_idx}_*.csv"))
    if not hits:
        raise FileNotFoundError(
            f"No timestamp CSV found for cam{cam_idx} in {session_dir}. "
            f"Looked for: timestamp{cam_idx}_*.csv"
        )
    # If multiple, pick the latest (timestamps in filename make lexicographic sort safe)
    return hits[-1]


def load_camera_csv(path: Path | str) -> pd.DataFrame:
    """Load a camera timestamp CSV (no header, 3 columns).

    Parameters
    ----------
    path : Path or str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Columns indexed by position (0, 1, 2).
    """
    return pd.read_csv(path, header=None)


def discover_video_files(session_dir: Path, cam_idx: int = 2) -> list[Path]:
    """Find video .avi files for a given camera in a session directory.

    Matches ``video{cam_idx}_*.avi``.

    Parameters
    ----------
    session_dir : Path
        Camera session directory.
    cam_idx : int
        Camera index. Default 2.

    Returns
    -------
    list[Path]
        Sorted list of matching video files (usually 1).
    """
    if not session_dir.exists():
        return []
    return sorted(session_dir.glob(f"video{cam_idx}_*.avi"))
