"""Session manifest: single source of truth for what belongs to a session.

Every analysis module takes a ``SessionManifest`` as its input contract,
not raw paths. This is the single biggest win for code clarity.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver

# Regex to extract the date from DLC filenames like:
#   video2_2025-03-07T12_11_32DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5
_DLC_DATE_RE = re.compile(r"video2_(\d{4}-\d{2}-\d{2})T")


@dataclass
class SessionManifest:
    """Per-session manifest containing all resolved paths and metadata.

    Attributes
    ----------
    session_id : str
        Canonical identifier: ``"{animal}_{YYYYMMDD}"``.
    animal : str
        e.g. "PS46".
    date : datetime.date
        Session date.
    day_relative_to_stroke : int
        Days relative to stroke (negative = pre-stroke).
    phase : str
        "baseline" or "post_stroke".
    wavesurfer_file : Path or None
        Path to the wavesurfer .h5 file. None until Phase 2.
    video_files : list[Path]
        Paths to raw video files. Empty until Phase 2.
    dlc_h5_files : list[Path]
        Paths to DLC .h5 output files (filtered).
    dlc_csv_files : list[Path]
        Paths to DLC .csv output files (filtered).
    alignment_template : Path or None
        Path to the alignment template .npz file, or None if not found.
    excluded : bool
        Whether this session is excluded from analysis.
    exclusion_reason : str or None
        Reason for exclusion, if excluded.
    wavesurfer_sides_match_mouse_sides : bool
        Copy of the per-animal flag from
        :class:`stroke_orofacial.animals.AnimalInfo`. Propagates the rig
        convention through the manifest so every downstream emitter has
        it without re-loading the animals config. Default ``False``
        (fail-conservative for the current PS46–PS55 cohort). See
        DECISIONS.md 2026-04-20 "Wavesurfer L/R ↔ mouse-frame
        boundary-layer translation" and
        :mod:`stroke_orofacial.lr_convention`.
    """

    session_id: str
    animal: str
    date: datetime.date
    day_relative_to_stroke: int
    phase: Literal["baseline", "post_stroke"]
    wavesurfer_file: Path | None = None
    video_files: list[Path] = field(default_factory=list)
    dlc_h5_files: list[Path] = field(default_factory=list)
    dlc_csv_files: list[Path] = field(default_factory=list)
    alignment_template: Path | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    # Task #17: rig-orientation flag propagated from AnimalInfo at
    # build_manifest() time so emitters can translate wavesurfer-frame
    # labels to mouse-frame at output boundaries without re-loading the
    # animals config.
    wavesurfer_sides_match_mouse_sides: bool = False


def _discover_dlc_files(
    dlc_dir: Path, date: datetime.date
) -> tuple[list[Path], list[Path]]:
    """Find filtered DLC .h5 and .csv files for a given date in dlc_dir.

    Looks for files matching the pattern:
        video2_{YYYY-MM-DD}T*_filtered.h5
        video2_{YYYY-MM-DD}T*_filtered.csv

    Parameters
    ----------
    dlc_dir : Path
        The animal's DLC output directory.
    date : datetime.date
        The session date to search for.

    Returns
    -------
    tuple[list[Path], list[Path]]
        (h5_files, csv_files), each sorted by name.
    """
    date_str = date.strftime("%Y-%m-%d")
    h5_pattern = f"video2_{date_str}T*_filtered.h5"
    csv_pattern = f"video2_{date_str}T*_filtered.csv"

    h5_files = sorted(dlc_dir.glob(h5_pattern))
    csv_files = sorted(dlc_dir.glob(csv_pattern))
    return h5_files, csv_files


def build_manifest(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    animal_info: AnimalInfo,
    analysis_type: str | None = None,
) -> SessionManifest:
    """Build a SessionManifest for one animal + date.

    Parameters
    ----------
    animal : str
        Animal ID (e.g. "PS46").
    date : datetime.date
        Session date.
    resolver : PathResolver
        Configured path resolver.
    animal_info : AnimalInfo
        Animal metadata (from animals.yaml).
    analysis_type : str or None
        If provided, exclusions are filtered to those that apply to this
        analysis type (e.g. "tongue", "jaw"). If None, only universal
        exclusions are checked.

    Returns
    -------
    SessionManifest
        Always returned. Discoverable inputs (DLC files, wavesurfer file,
        video files, alignment template) are populated when present and
        left empty/None when not. Phase orchestrators that require a
        specific input check for it themselves and raise with a clear,
        phase-scoped error message.
    """
    # Discover DLC files (optional — DLC inference may not have run yet
    # for this session, or the DLC output mount may be unavailable). DLC
    # is treated symmetrically with wavesurfer and video: discover if
    # present, else emit empty lists. The "I need DLC" assertion lives
    # in each DLC-consuming orchestrator (Phase 3+) so that DLC-free
    # workflows (Phase 2 spout behavior; pre-DLC behavior analysis;
    # video-failed sessions where wavesurfer is still clean) can build
    # and use a manifest without hitting a hard failure here.
    dlc_h5_files: list[Path] = []
    dlc_csv_files: list[Path] = []
    try:
        dlc_dir = resolver.dlc_output_dir(animal)
        if dlc_dir.exists():
            dlc_h5_files, dlc_csv_files = _discover_dlc_files(dlc_dir, date)
    except (FileNotFoundError, ValueError):
        pass  # DLC outputs not available — leave lists empty

    # Resolve alignment template (optional — may not exist for every session)
    alignment_path = resolver.alignment_template(animal, date)
    alignment_template = alignment_path if alignment_path.exists() else None

    # Compute stroke-relative metadata
    day_rel = animal_info.day_relative_to_stroke(date)
    phase = animal_info.phase(date)

    # Check exclusions
    excluded, exclusion_reason = animal_info.is_excluded(date, analysis_type)

    session_id = f"{animal}_{date.strftime('%Y%m%d')}"

    # Discover wavesurfer file (optional — may not exist if data isn't local)
    wavesurfer_file = None
    try:
        from stroke_orofacial.spout_behavior.wavesurfer_io import find_wavesurfer_file
        ws_dir = resolver.wavesurfer_dir(date, animal)
        if ws_dir.exists():
            wavesurfer_file = find_wavesurfer_file(ws_dir)
    except (FileNotFoundError, ValueError):
        pass  # wavesurfer data not available for this session

    # Discover video files (optional — camera data may not be mounted)
    video_files: list[Path] = []
    try:
        from stroke_orofacial.alignment.templates import discover_video_files
        cam_dir = resolver.camera_dir(date, animal)
        video_files = discover_video_files(cam_dir, cam_idx=2)
    except (FileNotFoundError, RuntimeError):
        pass  # camera data not available

    return SessionManifest(
        session_id=session_id,
        animal=animal,
        date=date,
        day_relative_to_stroke=day_rel,
        phase=phase,
        wavesurfer_file=wavesurfer_file,
        video_files=video_files,
        dlc_h5_files=dlc_h5_files,
        dlc_csv_files=dlc_csv_files,
        alignment_template=alignment_template,
        excluded=excluded,
        exclusion_reason=exclusion_reason,
        wavesurfer_sides_match_mouse_sides=(
            animal_info.wavesurfer_sides_match_mouse_sides
        ),
    )
