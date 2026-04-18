"""Time-base converters and AlignmentResult dataclass.

Implements the §4.4 time-base contract from DESIGN.md:
  - session_time (seconds, float, starts at 0 = wavesurfer session start)
  - ws_samples -> session_time: divide by Fs (1000 Hz)
  - video_frame_index -> session_time: via alignment template interpolation
  - dlc_frame_index -> session_time: equals video_frame_index by construction
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import numpy as np

from stroke_orofacial.alignment.frame_sync import make_alignment_template
from stroke_orofacial.alignment.templates import (
    load_alignment_template,
    load_camera_csv,
    pick_camera_csv,
)
from stroke_orofacial.paths import PathResolver


@dataclass
class AlignmentResult:
    """Essential alignment data for downstream use.

    Contains the sample-by-sample mappings between wavesurfer sample indices
    and camera frame indices, plus the affine fit parameters for diagnostics.

    Attributes
    ----------
    sig_camIdx__idx_ws : np.ndarray
        Camera frame index (float) for each WS sample index. Shape (N_ws,).
    sig_wsIdx__idx_cam : np.ndarray
        WS sample index (float) for each camera frame index. Shape (N_cam,).
    slope_ws_per_camFrame : float
        WS samples per camera frame (≈ Fs_ws / fps_cam ≈ 4.0).
    intercept_ws_samples : float
        WS sample offset at camera frame 0.
    Fs_ws : float
        Wavesurfer sampling rate (Hz).
    source : str
        "loaded" if from existing template, "computed" if freshly computed.
    """

    sig_camIdx__idx_ws: np.ndarray
    sig_wsIdx__idx_cam: np.ndarray
    slope_ws_per_camFrame: float
    intercept_ws_samples: float
    Fs_ws: float
    source: str = "loaded"


def ws_sample_to_session_time(sample_idx: int | np.ndarray, Fs: float = 1000.0) -> float | np.ndarray:
    """Convert wavesurfer sample index to session time in seconds.

    Parameters
    ----------
    sample_idx : int or array
        Sample index (0-based).
    Fs : float
        Wavesurfer sampling rate (default 1000 Hz).

    Returns
    -------
    float or array
        Session time in seconds.
    """
    return np.asarray(sample_idx, dtype=np.float64) / Fs


def frame_to_session_time(
    frame_idx: int | np.ndarray,
    alignment: AlignmentResult,
) -> float | np.ndarray:
    """Convert video/DLC frame index to session time in seconds.

    Uses the alignment template's ws_idx mapping, then divides by Fs.

    Parameters
    ----------
    frame_idx : int or array
        Camera/DLC frame index.
    alignment : AlignmentResult
        Loaded or computed alignment.

    Returns
    -------
    float or array
        Session time in seconds. NaN for out-of-range frames.
    """
    frame_idx = np.asarray(frame_idx, dtype=np.int64)
    ws_idx = alignment.sig_wsIdx__idx_cam
    # Clip to valid range, mark out-of-bounds as NaN
    result = np.full(frame_idx.shape, np.nan, dtype=np.float64)
    valid = (frame_idx >= 0) & (frame_idx < len(ws_idx))
    result[valid] = ws_idx[frame_idx[valid]] / alignment.Fs_ws
    return result


def session_time_to_frame(
    session_time_s: float | np.ndarray,
    alignment: AlignmentResult,
) -> float | np.ndarray:
    """Convert session time (seconds) to camera/DLC frame index.

    Parameters
    ----------
    session_time_s : float or array
        Session time in seconds.
    alignment : AlignmentResult
        Loaded or computed alignment.

    Returns
    -------
    float or array
        Frame index (float, may be fractional). NaN for out-of-range times.
    """
    session_time_s = np.asarray(session_time_s, dtype=np.float64)
    ws_sample = session_time_s * alignment.Fs_ws
    cam_idx = alignment.sig_camIdx__idx_ws
    # Clip to valid range
    result = np.full(session_time_s.shape, np.nan, dtype=np.float64)
    ws_int = np.round(ws_sample).astype(np.int64)
    valid = (ws_int >= 0) & (ws_int < len(cam_idx))
    result[valid] = cam_idx[ws_int[valid]]
    return result


def load_or_compute_alignment(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    ws_signals: dict[str, np.ndarray] | None = None,
    force_recompute: bool = False,
) -> AlignmentResult:
    """Load an existing alignment template, or compute one if missing.

    Default behavior: load from ``alignment_templates/cam2/{animal}/{YYYYMMDD}.npz``.
    If the template doesn't exist (or ``force_recompute=True``), compute fresh
    from wavesurfer sync signal + camera CSV.

    Parameters
    ----------
    animal : str
        Animal ID.
    date : datetime.date
        Session date.
    resolver : PathResolver
        Configured path resolver.
    params : dict
        The ``alignment`` section from defaults.yaml.
    ws_signals : dict, optional
        Pre-loaded wavesurfer signals. If None and recompute is needed,
        loads from the processed wavesurfer NPZ in stroke_orofacial_pipeline_outputs.
    force_recompute : bool
        If True, always recompute even if an existing template exists.

    Returns
    -------
    AlignmentResult
    """
    cam_idx = int(params.get("cam_idx", 2))
    cam_name = f"cam{cam_idx}"

    # Try loading existing template
    existing_path = resolver.alignment_template(animal, date, cam=cam_name)
    if not force_recompute and existing_path.exists():
        tmpl = load_alignment_template(existing_path)
        return AlignmentResult(
            sig_camIdx__idx_ws=tmpl["sig_camIdx__idx_ws"],
            sig_wsIdx__idx_cam=tmpl["sig_wsIdx__idx_cam"],
            slope_ws_per_camFrame=float(tmpl["slope_ws_per_camFrame"]),
            intercept_ws_samples=float(tmpl["intercept_ws_samples"]),
            Fs_ws=float(tmpl["Fs_ws_input"]),
            source="loaded",
        )

    # Need to compute — get wavesurfer signals
    if ws_signals is None:
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            find_wavesurfer_file,
            load_wavesurfer_signals,
        )
        ws_dir = resolver.wavesurfer_dir(date, animal)
        ws_file = find_wavesurfer_file(ws_dir)
        ws_signals = load_wavesurfer_signals(ws_file)

    # Get camera CSV
    cam_dir = resolver.camera_dir(date, animal)
    csv_path = pick_camera_csv(cam_dir, cam_idx=cam_idx)
    cam_csv = load_camera_csv(csv_path)

    # Compute alignment
    tmpl = make_alignment_template(ws_signals, cam_csv, params)

    return AlignmentResult(
        sig_camIdx__idx_ws=tmpl["sig_camIdx__idx_ws"],
        sig_wsIdx__idx_cam=tmpl["sig_wsIdx__idx_cam"],
        slope_ws_per_camFrame=float(tmpl["slope_ws_per_camFrame"]),
        intercept_ws_samples=float(tmpl["intercept_ws_samples"]),
        Fs_ws=float(tmpl["Fs_ws_input"]),
        source="computed",
    )
