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

    Raises
    ------
    FileNotFoundError
        If the DLC output directory does not exist or no DLC files are found.
    """
    # Resolve DLC paths
    dlc_dir = resolver.dlc_output_dir(animal)
    if not dlc_dir.exists():
        raise FileNotFoundError(
            f"DLC output directory not found: {dlc_dir}\n"
            f"Is the MICROSCOPE server mounted?"
        )

    # Discover DLC files
    dlc_h5_files, dlc_csv_files = _discover_dlc_files(dlc_dir, date)
    if not dlc_h5_files and not dlc_csv_files:
        raise FileNotFoundError(
            f"No filtered DLC files found for {animal} on {date} in {dlc_dir}.\n"
            f"Looked for: video2_{date.strftime('%Y-%m-%d')}T*_filtered.{{h5,csv}}"
        )

    # Resolve alignment template (optional — may not exist for every session)
    alignment_path = resolver.alignment_template(animal, date)
    alignment_template = alignment_path if alignment_path.exists() else None

    # Compute stroke-relative metadata
    day_rel = animal_info.day_relative_to_stroke(date)
    phase = animal_info.phase(date)

    # Check exclusions
    excluded, exclusion_reason = animal_info.is_excluded(date, analysis_type)

    session_id = f"{animal}_{date.strftime('%Y%m%d')}"

    return SessionManifest(
        session_id=session_id,
        animal=animal,
        date=date,
        day_relative_to_stroke=day_rel,
        phase=phase,
        wavesurfer_file=None,  # populated in Phase 2
        video_files=[],  # populated in Phase 2
        dlc_h5_files=dlc_h5_files,
        dlc_csv_files=dlc_csv_files,
        alignment_template=alignment_template,
        excluded=excluded,
        exclusion_reason=exclusion_reason,
    )
