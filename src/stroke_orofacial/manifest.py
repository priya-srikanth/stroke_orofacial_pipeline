"""Session manifest: single source of truth for what belongs to a session.

Every analysis module takes a ``SessionManifest`` as its input contract,
not raw paths. This is the single biggest win for code clarity.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver

# Regex to extract the date from DLC filenames like:
#   video2_2025-03-07T12_11_32DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5
_DLC_DATE_RE = re.compile(r"video2_(\d{4}-\d{2}-\d{2})T")

# Phase 7-pre-multi-half: defensive-check threshold for the
# "Pattern A undeclared" trip wire. Sessions where >=2 filtered DLC H5
# files match the date glob AND no `multi_half_sessions:` entry covers
# (animal, date) raise :class:`MultiHalfNotDeclaredError`. Pattern B
# sessions (n_dlc=1 + n_ws=2 + n_cam=2) do NOT fire the check by design.
# See docs/phase-7-pre/multi_half_scan_results.md "Task 1 verdict".
_PATTERN_A_N_DLC_MIN = 2


class MultiHalfNotDeclaredError(RuntimeError):
    """Raised when on-disk signals indicate Pattern A multi-half but no
    ``multi_half_sessions:{animal}:{date}`` entry exists in
    ``configs/session_overrides.yaml``.

    Trigger: ``n_dlc >= 2`` (>=2 filtered DLC H5 files match the date
    glob in ``O2_analysis/{ANIMAL}/``) AND the YAML registry has no
    entry for the (animal, date) pair. The error message embeds an
    auto-detected YAML stub the user can copy-paste into
    ``session_overrides.yaml`` after review.

    Pattern B (n_dlc=1 + n_ws=2 + n_cam=2; the 19 PS51/PS54/PS55
    sessions identified in the Task 1 cohort scan) does NOT trip this
    error — the existing single-half discovery path is the canonical
    behavior for those by design (the unlabeled-half / bare ``{DATE}``
    WS subdir is the analyzed half; half-b is exploratory and silently
    discarded).
    """


@dataclass
class HalfSpec:
    """Per-half acquisition record for multi-half sessions
    (Phase 7-pre-multi-half).

    Populated by :func:`build_manifest` when ``multi_half_sessions:``
    in ``configs/session_overrides.yaml`` covers the (animal, date)
    pair. Carries the per-half subdir names and acquisition timestamp
    needed for downstream Phase 2/3/4 per-half processing, plus
    discovered file paths.

    Attributes
    ----------
    id : str
        Half identifier letter, sorted in acquisition order
        (``"a"``, ``"b"``, ...).
    ws_subdir : str
        Per-half wavesurfer subdir name under ``{ws_root}/`` (e.g.
        ``"20250314a"``). Resolved via
        :meth:`stroke_orofacial.paths.PathResolver.wavesurfer_dir`'s
        ``half_subdir=`` kwarg.
    cam_subdir : str
        Per-half camera subdir name under ``{cam_root}/`` (typically
        equal to ``ws_subdir`` but tracked separately because they
        could diverge in principle, and Pattern A on-disk evidence
        already shows the cross-half timestamp asymmetry between WS
        and camera filenames — the SUBDIR names match for PS48
        20250314 but file-level timestamps do not).
    file_timestamp : str
        Acquisition timestamp embedded in DLC + .avi filenames, format
        ``"YYYY-MM-DDTHH_MM_SS"`` (e.g. ``"2025-03-14T12_31_07"``).
        Used by per-half discovery globs for DLC + camera files. The
        timestamp comes from the .avi filename; the timestamp CSV
        filenames may be off by ~1 second on some halves
        (observed PS48 20250314 half-b: csv at ``T13_09_28``, avi at
        ``T13_09_29``), so camera-side globs use the ``HH_MM`` prefix
        loosely rather than the full ``HH_MM_SS`` string.
    wavesurfer_file : Path or None
        Per-half wavesurfer .h5 file. Populated by
        :func:`build_manifest` when ``ws_subdir/{ANIMAL}/`` contains
        exactly one matching .h5 file. None if the subdir or file is
        missing — downstream Phase 2 per-half loop raises with a
        phase-scoped error.
    dlc_h5_file : Path or None
        Per-half filtered DLC H5. Discovered via
        ``video2_{file_timestamp}*_filtered.h5`` glob at the flat
        ``O2_analysis/{ANIMAL}/`` level (DLC inference output is NOT
        organized by per-half subdir — timestamps embedded in
        filenames are the discriminator). None if the glob returns
        zero matches; an error is raised on >=2 matches.
    dlc_csv_file : Path or None
        Per-half filtered DLC CSV; same discovery semantics as
        ``dlc_h5_file``.
    video_files : list[Path]
        Per-half video .avi files (cam1-cam4; usually 4 per half).
        Discovered via loose ``video*_{HH_MM_PREFIX}*.avi`` glob
        under ``cam_subdir/{ANIMAL}/`` so the off-by-1-second between
        timestamp CSV and video filename (see ``file_timestamp`` note)
        doesn't drop matches.
    timestamp_csv_files : list[Path]
        Per-half timestamp CSV files; same discovery semantics as
        ``video_files``.
    alignment_template : Path or None
        Per-half alignment template .npz, populated by Phase 3 per-half
        output (Phase 7-pre-multi-half Task 5). Layout convention:
        ``{alignment_templates}/cam2/{ANIMAL}/{DATE}{halves_concat_label}/{DATE}{half_id}.npz``.
        Left None at :func:`build_manifest` time; Phase 3 wiring
        populates it after the per-half template is emitted.
    """

    id: str
    ws_subdir: str
    cam_subdir: str
    file_timestamp: str
    wavesurfer_file: Path | None = None
    dlc_h5_file: Path | None = None
    dlc_csv_file: Path | None = None
    video_files: list[Path] = field(default_factory=list)
    timestamp_csv_files: list[Path] = field(default_factory=list)
    alignment_template: Path | None = None


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
    halves : list[HalfSpec] or None
        Per-half acquisition records for multi-half sessions
        (Phase 7-pre-multi-half). ``None`` for single-half sessions —
        every existing single-half code path runs unchanged when
        ``halves is None``. When non-None, the parent-level
        ``wavesurfer_file`` / ``video_files`` / ``dlc_h5_files`` /
        ``dlc_csv_files`` are intentionally LEFT EMPTY/None and
        downstream consumers must read per-half data from
        ``halves[i]``. The ``alignment_template`` field still resolves
        to the parent-level merged path (populated by Phase 3 once
        the merge is run); per-half templates live in
        ``halves[i].alignment_template``.
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
    # Phase 7-pre-multi-half: per-half acquisition records for
    # Pattern A multi-half sessions. None preserves single-half
    # behavior; populated only when session_overrides.yaml has a
    # multi_half_sessions:{animal}:{date} entry.
    halves: list[HalfSpec] | None = None


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


# Match a full HH_MM_SS file timestamp; capture the HH_MM prefix.
# Anchored to the full string so non-canonical inputs degrade gracefully
# (the helper returns the input verbatim and the caller's glob still fires).
_FILE_TIMESTAMP_HH_MM_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}_\d{2})_\d{2}$"
)


def _file_timestamp_minute_prefix(file_timestamp: str) -> str:
    """Return the ``YYYY-MM-DDTHH_MM`` prefix of a canonical
    ``YYYY-MM-DDTHH_MM_SS`` file timestamp.

    Strips the trailing ``_SS`` segment so camera-side globs match both
    the .avi (e.g. ``T13_09_29.avi``) and the timestamp CSV (e.g.
    ``T13_09_28.csv``) when those differ by ~1 second within the same
    half. Observed on PS48 20250314 half-b — see HalfSpec docstring.

    For inputs that don't match the canonical full-timestamp shape
    (already-minute-precision strings, malformed inputs, etc.) the
    function returns the input verbatim so callers glob a stricter
    match rather than a wrong-precision one.
    """
    m = _FILE_TIMESTAMP_HH_MM_RE.match(file_timestamp)
    if m is None:
        return file_timestamp
    return m.group(1)


def _discover_half_files(
    spec: HalfSpec,
    date: datetime.date,
    animal: str,
    resolver: PathResolver,
) -> None:
    """Populate file-discovery fields on a HalfSpec in place.

    Looks up per-half WS file (exactly one .h5 inside
    ``{ws_root}/{spec.ws_subdir}/{ANIMAL}/``), filtered DLC H5 + CSV
    (single match each at the flat ``O2_analysis/{ANIMAL}/`` level
    via ``video2_{spec.file_timestamp}*_filtered.h5`` / ``.csv``),
    and per-half video + timestamp CSV files (all matches via loose
    ``HH_MM`` prefix glob under
    ``{cam_root}/{spec.cam_subdir}/{ANIMAL}/``).

    Failure modes are tolerant: a missing WS dir / DLC mount /
    camera mount leaves the corresponding fields as ``None`` /
    empty list. Downstream Phase 2/3/4 per-half loops raise with
    phase-scoped errors when their specific input is missing.

    Multi-match on DLC globs (>=2 filtered H5 for a single
    ``file_timestamp``) is treated as a configuration bug — the
    timestamp uniquely identifies one acquisition and one DLC run —
    and raised loud as ``RuntimeError``.

    Parameters
    ----------
    spec : HalfSpec
        Mutated in place; per-half discovery results are written to
        ``wavesurfer_file``, ``dlc_h5_file``, ``dlc_csv_file``,
        ``video_files``, ``timestamp_csv_files``.
    date, animal, resolver
        Context for the (animal, date) being resolved.
    """
    # Per-half WS discovery: existing find_wavesurfer_file inside the
    # half-specific subdir resolved via half_subdir kwarg.
    try:
        from stroke_orofacial.spout_behavior.wavesurfer_io import find_wavesurfer_file
        ws_dir = resolver.wavesurfer_dir(date, animal, half_subdir=spec.ws_subdir)
        if ws_dir.exists():
            spec.wavesurfer_file = find_wavesurfer_file(ws_dir)
    except (FileNotFoundError, ValueError):
        pass  # WS data not available for this half — leave None

    # Per-half DLC discovery: glob at the flat O2_analysis/{ANIMAL}/ level
    # using the full HH_MM_SS file_timestamp string. The DLC inference
    # filename embeds the .avi acquisition timestamp verbatim, so the
    # glob is exact at the seconds level.
    try:
        dlc_dir = resolver.dlc_output_dir(animal)
        if dlc_dir.exists():
            h5_pattern = f"video2_{spec.file_timestamp}*_filtered.h5"
            csv_pattern = f"video2_{spec.file_timestamp}*_filtered.csv"
            h5_matches = sorted(dlc_dir.glob(h5_pattern))
            csv_matches = sorted(dlc_dir.glob(csv_pattern))
            if len(h5_matches) > 1:
                raise RuntimeError(
                    f"Multiple filtered DLC H5 files match per-half "
                    f"timestamp {spec.file_timestamp!r} for {animal}: "
                    f"{[p.name for p in h5_matches]}. The timestamp must "
                    "uniquely identify one acquisition."
                )
            if len(csv_matches) > 1:
                raise RuntimeError(
                    f"Multiple filtered DLC CSV files match per-half "
                    f"timestamp {spec.file_timestamp!r} for {animal}: "
                    f"{[p.name for p in csv_matches]}."
                )
            spec.dlc_h5_file = h5_matches[0] if h5_matches else None
            spec.dlc_csv_file = csv_matches[0] if csv_matches else None
    except (FileNotFoundError, ValueError):
        pass  # DLC mount unavailable

    # Per-half camera discovery: loose HH_MM-prefix glob to handle the
    # ~1-second timestamp asymmetry between .avi and timestamp CSV
    # filenames within the same half.
    try:
        cam_dir = resolver.camera_dir(date, animal, half_subdir=spec.cam_subdir)
        if cam_dir.exists():
            prefix = _file_timestamp_minute_prefix(spec.file_timestamp)
            spec.video_files = sorted(cam_dir.glob(f"video*_{prefix}*.avi"))
            spec.timestamp_csv_files = sorted(
                cam_dir.glob(f"timestamp*_{prefix}*.csv")
            )
    except (FileNotFoundError, ValueError):
        pass  # camera mount unavailable


def _build_half_specs(
    animal: str,
    date_str: str,
    overrides_config: dict[str, Any],
    date: datetime.date,
    resolver: PathResolver,
) -> list[HalfSpec] | None:
    """Read ``multi_half_sessions:{animal}:{date_str}`` from the overrides
    config, and return populated :class:`HalfSpec` instances or ``None``
    when no entry exists.

    Each HalfSpec has its file-discovery fields populated by
    :func:`_discover_half_files`. The returned list preserves the
    YAML-supplied half order (typically alphabetical by id letter).

    Returns
    -------
    list[HalfSpec] or None
        ``None`` when no ``multi_half_sessions:`` entry covers
        ``(animal, date_str)``. Otherwise a list with one entry per
        declared half.

    Raises
    ------
    KeyError
        If a YAML entry is malformed (missing required half fields
        ``id`` / ``ws_subdir`` / ``cam_subdir`` / ``file_timestamp``).
    """
    multi_half = overrides_config.get("multi_half_sessions", {}) or {}
    animal_entry = multi_half.get(animal, {}) or {}
    session_entry = animal_entry.get(date_str)
    if not session_entry:
        return None

    raw_halves = session_entry.get("halves", []) or []
    specs: list[HalfSpec] = []
    for raw in raw_halves:
        # Use explicit dict access so missing fields raise KeyError —
        # the registry shape is the contract; silent fallback would
        # mask configuration bugs.
        spec = HalfSpec(
            id=raw["id"],
            ws_subdir=raw["ws_subdir"],
            cam_subdir=raw["cam_subdir"],
            file_timestamp=raw["file_timestamp"],
        )
        _discover_half_files(spec, date, animal, resolver)
        specs.append(spec)
    return specs


def _format_pattern_a_yaml_stub(
    animal: str,
    date_str: str,
    dlc_h5_files: list[Path],
) -> str:
    """Return a YAML-fragment string for a Pattern A undeclared session.

    Used to embed actionable instructions in
    :class:`MultiHalfNotDeclaredError` messages: the user can copy the
    block into ``configs/session_overrides.yaml`` after manual review,
    rather than having to look up ``ws_subdir`` / ``cam_subdir`` / the
    per-half timestamp by hand.
    """
    # Extract HH_MM_SS-shaped acquisition timestamps from filenames like
    # ``video2_2025-03-14T12_31_07DLC_...``. Assumes the date-prefix is
    # consistent across both halves; sorts by timestamp so the first
    # timestamp lands as half "a".
    ts_by_file = []
    for p in dlc_h5_files:
        m = re.search(r"video2_(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2})", p.name)
        if m:
            ts_by_file.append((m.group(1), p.name))
    ts_by_file.sort()

    lines: list[str] = [
        f"  {animal}:",
        f'    "{date_str}":',
        "      halves:",
    ]
    letters = ["a", "b", "c", "d", "e"]
    for i, (ts, _name) in enumerate(ts_by_file):
        letter = letters[i] if i < len(letters) else f"h{i}"
        # Auto-detect ws_subdir / cam_subdir best-effort: assume they
        # follow the {DATE}{letter} convention (Pattern A on disk for
        # PS48 20250314 / PS55 20250424). The user MUST review and
        # adjust if the on-disk layout differs.
        lines.append(f"        - id: {letter}")
        lines.append(f'          ws_subdir: "{date_str}{letter}"  # auto-suggested; verify on disk')
        lines.append(f'          cam_subdir: "{date_str}{letter}"  # auto-suggested; verify on disk')
        lines.append(f'          file_timestamp: "{ts}"')
    lines.append('      reason: "auto-detected by build_manifest defensive check"')
    return "\n".join(lines)


def build_manifest(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    animal_info: AnimalInfo,
    analysis_context: str | None = None,
    *,
    overrides_config: dict[str, Any] | None = None,
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
    analysis_context : str or None
        Dotted hierarchical tag naming the analysis that will consume
        this manifest — e.g. ``"spout_behavior"``, ``"dlc.spatial"``,
        ``"dlc.kinematics.tongue"``. Threaded into
        :meth:`AnimalInfo.is_excluded` to populate ``excluded`` and
        ``exclusion_reason`` on the returned manifest using
        prefix-match semantics on the exclusion entries' ``applies_to``
        tags. If None, ``excluded`` is always False — callers should
        pass an explicit context.

    overrides_config : dict, optional
        Pre-loaded ``configs/session_overrides.yaml`` dict. When None,
        loaded fresh from disk. Threaded through to support the
        Phase 7-pre-multi-half ``multi_half_sessions:`` lookup —
        ``halves`` is populated when an entry covers ``(animal, date)``,
        else single-half discovery proceeds. Tests may pass an
        in-memory dict to avoid touching the on-disk YAML.

    Returns
    -------
    SessionManifest
        Always returned. Discoverable inputs (DLC files, wavesurfer file,
        video files, alignment template) are populated when present and
        left empty/None when not. Phase orchestrators that require a
        specific input check for it themselves and raise with a clear,
        phase-scoped error message.

        For multi-half sessions (``halves is not None``), the
        parent-level ``wavesurfer_file`` / ``video_files`` /
        ``dlc_h5_files`` / ``dlc_csv_files`` are intentionally left
        empty/None — per-half data lives in ``halves[i]``.
        ``alignment_template`` continues to point at the parent-level
        merged file path (populated by Phase 3 once the merge is run);
        per-half templates live in ``halves[i].alignment_template``.

    Raises
    ------
    MultiHalfNotDeclaredError
        When on-disk DLC inference produced ``>=2`` filtered H5 files
        matching ``video2_{date}T*_filtered.h5`` (Pattern A signal) but
        no ``multi_half_sessions:`` entry covers ``(animal, date)``,
        AND the session is not excluded. The error message embeds an
        auto-detected YAML stub to copy-paste into
        ``configs/session_overrides.yaml`` after manual review. Skipped
        when the session is excluded for ``analysis_context`` (the
        exclusion gate takes precedence).
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

    # Resolve alignment template (optional — may not exist for every session).
    # For Pattern A multi-half sessions the parent-level merged file lives at
    # the same path as a single-half template; per-half templates live in
    # halves[i].alignment_template (populated by Phase 3 output, not here).
    alignment_path = resolver.alignment_template(animal, date)
    alignment_template = alignment_path if alignment_path.exists() else None

    # Compute stroke-relative metadata
    day_rel = animal_info.day_relative_to_stroke(date)
    phase = animal_info.phase(date)

    # Check exclusions
    excluded, exclusion_reason = animal_info.is_excluded(date, analysis_context)

    session_id = f"{animal}_{date.strftime('%Y%m%d')}"
    date_str = date.strftime("%Y%m%d")

    # Phase 7-pre-multi-half: lookup multi_half_sessions registry to decide
    # between single-half and per-half discovery. Lazy-load the overrides
    # config; tests may pre-load and pass in to avoid touching disk.
    if overrides_config is None:
        from stroke_orofacial.config_loader import load_session_overrides
        overrides_config = load_session_overrides()
    halves = _build_half_specs(animal, date_str, overrides_config, date, resolver)

    # Defensive check: Pattern A signal (n_dlc >= 2) without a YAML entry
    # is a configuration bug — fail loud with an actionable stub. Skipped
    # for excluded sessions because exclusion overrides any silent-discard
    # concern. Pattern B sessions never trip this (n_dlc=1).
    if (
        halves is None
        and not excluded
        and len(dlc_h5_files) >= _PATTERN_A_N_DLC_MIN
    ):
        stub = _format_pattern_a_yaml_stub(animal, date_str, dlc_h5_files)
        raise MultiHalfNotDeclaredError(
            f"Pattern A multi-half signal: {animal}/{date_str} has "
            f"{len(dlc_h5_files)} filtered DLC H5 files matching the date "
            f"glob but no multi_half_sessions:{animal}:{date_str} entry "
            f"in configs/session_overrides.yaml. Add the following stub "
            f"after manual review of the on-disk per-half subdirs:\n\n"
            f"multi_half_sessions:\n{stub}"
        )

    # Discover parent-level wavesurfer + video files for single-half sessions
    # only. For multi-half (halves is not None), per-half data lives in
    # halves[i]; the parent-level fields are intentionally empty/None to
    # prevent downstream consumers from accidentally treating the bare
    # {DATE} subdir as canonical (it doesn't exist for Pattern A multi-half
    # — only the per-half {DATE}{half_id} subdirs do).
    wavesurfer_file: Path | None = None
    video_files: list[Path] = []
    if halves is None:
        try:
            from stroke_orofacial.spout_behavior.wavesurfer_io import (
                find_wavesurfer_file,
            )
            ws_dir = resolver.wavesurfer_dir(date, animal)
            if ws_dir.exists():
                wavesurfer_file = find_wavesurfer_file(ws_dir)
        except (FileNotFoundError, ValueError):
            pass  # wavesurfer data not available for this session

        try:
            from stroke_orofacial.alignment.templates import discover_video_files
            cam_dir = resolver.camera_dir(date, animal)
            video_files = discover_video_files(cam_dir, cam_idx=2)
        except (FileNotFoundError, RuntimeError):
            pass  # camera data not available
    else:
        # Multi-half: clear parent-level DLC results too. Per-half DLC
        # files live in halves[i].dlc_h5_file / .dlc_csv_file. The
        # parent-level lists matter only for single-half manifests.
        dlc_h5_files = []
        dlc_csv_files = []

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
        halves=halves,
    )
