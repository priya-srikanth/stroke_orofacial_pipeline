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
from stroke_orofacial.animals import get_animal
from stroke_orofacial.manifest import SessionManifest, build_manifest
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
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    ws_signals: dict[str, np.ndarray] | None = None,
    force_recompute: bool = False,
) -> AlignmentResult:
    """Load an existing alignment template, or compute one if missing.

    Primary entry point — consumes a ``SessionManifest`` produced by
    ``build_manifest()``. Phase 3 alignment is DLC-agnostic by design: it
    relates wavesurfer samples to camera frames, and camera frames exist
    whether or not DLC inference has run. The DLC guard belongs in
    Phase 4 (parquet builder), not here.

    Default behavior: load from ``manifest.alignment_template`` (cam2 only)
    or ``alignment_templates/{cam_name}/{animal}/{YYYYMMDD}.npz`` for other
    cams. If the template doesn't exist (or ``force_recompute=True``),
    compute fresh from ``manifest.wavesurfer_file`` + camera CSV.

    For callers that prefer the legacy (animal, date) entry point, see
    ``load_or_compute_alignment_by_animal_date()`` below.

    Parameters
    ----------
    manifest : SessionManifest
        Per-session manifest. ``wavesurfer_file`` (and, for cam2,
        ``video_files``) must be populated when ``force_recompute=True`` or
        the existing template is missing.
    resolver : PathResolver
        Configured path resolver. Used for the alignment-template path
        when ``cam_idx != 2`` (manifest only tracks cam2's template), and
        as a fallback for the camera directory when the manifest's
        ``video_files`` is empty.
    params : dict
        The ``alignment`` section from defaults.yaml.
    ws_signals : dict, optional
        Pre-loaded wavesurfer signals. If None and recompute is needed,
        loads from ``manifest.wavesurfer_file``.
    force_recompute : bool
        If True, always recompute even if an existing template exists.

    Returns
    -------
    AlignmentResult

    Raises
    ------
    FileNotFoundError
        If recomputation is needed but the required wavesurfer or camera
        CSV inputs are missing from the manifest and unavailable via the
        resolver.
    """
    cam_idx = int(params.get("cam_idx", 2))
    cam_name = f"cam{cam_idx}"
    animal = manifest.animal
    date = manifest.date

    # Existing-template path: prefer the manifest's cam2 entry; fall back
    # to the resolver for other cams (manifest only tracks cam2) or when
    # the manifest didn't see the template at build time but it now exists.
    if cam_idx == 2 and manifest.alignment_template is not None:
        existing_path = manifest.alignment_template
    else:
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
        if manifest.wavesurfer_file is None:
            raise FileNotFoundError(
                f"{manifest.session_id}: manifest.wavesurfer_file is None. "
                f"Phase 3 alignment requires wavesurfer + camera CSV to "
                f"recompute. Provide ws_signals explicitly, ensure the "
                f"wavesurfer mount is available, or rerun build_manifest()."
            )
        from stroke_orofacial.spout_behavior.wavesurfer_io import (
            load_wavesurfer_signals,
        )
        ws_signals = load_wavesurfer_signals(manifest.wavesurfer_file)

    # Get camera CSV. For cam2, prefer the directory the manifest already
    # discovered for video_files; fall back to the resolver for other cams
    # or when the manifest has no videos discovered.
    if cam_idx == 2 and manifest.video_files:
        cam_dir = manifest.video_files[0].parent
    else:
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


def load_or_compute_alignment_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    ws_signals: dict[str, np.ndarray] | None = None,
    force_recompute: bool = False,
) -> AlignmentResult:
    """Convenience wrapper: builds a SessionManifest then calls load_or_compute_alignment().

    Equivalent to::

        animal_info = get_animal(animal)
        manifest = build_manifest(
            animal, date, resolver, animal_info,
            analysis_context="alignment",
        )
        return load_or_compute_alignment(manifest, resolver, params, ...)

    Phase 3 alignment is DLC-agnostic; ``build_manifest()`` treats DLC
    files as optional, so this wrapper works for sessions where DLC
    inference hasn't run yet. The ``analysis_context="alignment"``
    argument scopes exclusion checks: sessions with
    ``applies_to: [dlc]`` exclusions (e.g., "missing camera data") also
    block alignment since the wavesurfer↔camera mapping needs the camera
    timestamp CSVs — mark those sessions with ``applies_to: [dlc,
    alignment]`` or ``applies_to: [alignment]`` as appropriate.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="alignment",
    )
    return load_or_compute_alignment(
        manifest, resolver, params,
        ws_signals=ws_signals, force_recompute=force_recompute,
    )


# ---------------------------------------------------------------------------
# Phase 7-pre-multi-half: per-half Phase 3 alignment + merge orchestration.
# ---------------------------------------------------------------------------


def _compute_per_half_alignment_template(
    half_spec: Any,
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    cam_idx: int = 2,
) -> dict[str, Any]:
    """Compute a single-half alignment template dict from a HalfSpec.

    Loads the per-half wavesurfer signals (``half_spec.wavesurfer_file``)
    and per-half camera CSV (discovered under
    ``{cam_root}/{half_spec.cam_subdir}/{ANIMAL}/`` via
    :func:`pick_camera_csv`), then runs :func:`make_alignment_template`
    with the supplied alignment params. Returns the full template dict
    — same schema as legacy NPZ output, suitable for direct save via
    ``np.savez_compressed``.

    Used by :func:`compute_and_merge_alignment_multi_half` to produce
    the per-half NPZs that feed the cell-16-port merge function.

    Raises
    ------
    FileNotFoundError
        If ``half_spec.wavesurfer_file`` is None or missing, or if
        the per-half camera dir doesn't contain a discoverable CSV.
    """
    if half_spec.wavesurfer_file is None:
        raise FileNotFoundError(
            f"half {half_spec.id!r}: wavesurfer_file is None. build_manifest() "
            f"did not locate a .h5 in {{ws_root}}/{half_spec.ws_subdir}/{animal}/. "
            f"Verify the per-half WS subdir exists and the wavesurfer_raw mount "
            f"is reachable."
        )

    from stroke_orofacial.spout_behavior.wavesurfer_io import (
        load_wavesurfer_signals,
    )
    ws_signals = load_wavesurfer_signals(half_spec.wavesurfer_file)

    # Camera CSV discovery — prefer half_spec's discovered timestamp_csv_files
    # (already filtered by HH_MM-prefix glob in build_manifest), fall back
    # to a fresh pick_camera_csv inside the per-half cam dir for robustness.
    if half_spec.timestamp_csv_files:
        cam_dir = half_spec.timestamp_csv_files[0].parent
    else:
        cam_dir = resolver.camera_dir(date, animal, half_subdir=half_spec.cam_subdir)
    csv_path = pick_camera_csv(cam_dir, cam_idx=cam_idx)
    cam_csv = load_camera_csv(csv_path)

    return make_alignment_template(ws_signals, cam_csv, params)


def compute_and_merge_alignment_multi_half(
    manifest: SessionManifest,
    resolver: PathResolver,
    params: dict[str, Any],
    *,
    force_recompute: bool = False,
) -> Any:
    """Compute per-half alignment templates (or load if present), merge,
    and return the merged template path.

    Layout (Decision 3 of the Phase 7-pre-multi-half Task 1 verdict):
      - Per-half NPZs land at
        ``{alignment_templates}/cam2/{ANIMAL}/{date_str}{halves_concat_label}/{date_str}{half_id}.npz``
        — exposed by :meth:`PathResolver.alignment_template_per_half`.
      - Merged NPZ lands at the parent
        ``{alignment_templates}/cam2/{ANIMAL}/{date_str}.npz`` — same path
        as for single-half sessions, so any downstream consumer reads
        the merged template via the existing :meth:`PathResolver.alignment_template`
        regardless of multi-half status.

    Behavior:
      - Each per-half NPZ is loaded if present and ``not force_recompute``,
        else computed fresh via :func:`_compute_per_half_alignment_template`
        + ``np.savez_compressed``.
      - The merged NPZ is written via :func:`merge_alignment_templates`
        (a faithful port of legacy cell 16) — overwriting if it exists
        (the merge function is the canonical writer for this path; if
        the caller wants to skip recomputation when the merged file is
        already present, they should branch before calling this
        function).

    Parameters
    ----------
    manifest : SessionManifest
        Multi-half manifest (``manifest.halves`` must be non-None).
    resolver : PathResolver
        Configured path resolver.
    params : dict
        ``alignment`` section from defaults.yaml. Required keys: same as
        :func:`make_alignment_template`'s contract — ``cam_idx``,
        ``key_sync``, ``csv_idx_sync``, ``csv_idx_time``, ``window``,
        ``p``, ``min_matched_edges``.
    force_recompute : bool
        When True, always recompute every per-half template even if the
        per-half NPZs exist. Useful for parity-gate runs that compare
        new outputs to legacy artefacts.

    Returns
    -------
    Path
        The merged template path (parent-level).

    Raises
    ------
    ValueError
        If ``manifest.halves`` is None — caller wired this function on a
        single-half manifest (use :func:`load_or_compute_alignment`).
    FileNotFoundError
        If a half's wavesurfer file or camera CSV is missing during
        recompute.
    """
    if manifest.halves is None:
        raise ValueError(
            f"compute_and_merge_alignment_multi_half: manifest.halves is None for "
            f"{manifest.session_id}. Use load_or_compute_alignment() for "
            f"single-half sessions."
        )
    cam_idx = int(params.get("cam_idx", 2))
    cam_name = f"cam{cam_idx}"
    halves = manifest.halves
    halves_concat_label = "".join(h.id for h in halves)

    # Per-half NPZ paths (Decision 3 layout)
    per_half_paths = [
        resolver.alignment_template_per_half(
            manifest.animal, manifest.date,
            halves_concat_label=halves_concat_label,
            half_id=h.id,
            cam=cam_name,
        )
        for h in halves
    ]

    # Compute or skip per-half templates
    for h, out_path in zip(halves, per_half_paths, strict=True):
        if out_path.exists() and not force_recompute:
            continue
        template_dict = _compute_per_half_alignment_template(
            h, manifest.animal, manifest.date, resolver, params, cam_idx=cam_idx,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(str(out_path), **template_dict)

    # Merge (always re-merges; deterministic from per-half NPZs)
    from stroke_orofacial.spout_behavior.multi_half_merge import (
        merge_alignment_templates,
    )
    merged_path = resolver.alignment_template(
        manifest.animal, manifest.date, cam=cam_name,
    )
    merge_alignment_templates(per_half_paths, merged_path)
    return merged_path
