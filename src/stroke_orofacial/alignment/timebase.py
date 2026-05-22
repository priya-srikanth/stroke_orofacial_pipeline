"""Time-base converters and AlignmentResult dataclass.

Implements the §4.4 time-base contract from DESIGN.md:
  - session_time (seconds, float, starts at 0 = wavesurfer session start)
  - ws_samples -> session_time: divide by Fs (1000 Hz)
  - video_frame_index -> session_time: via alignment template interpolation
  - dlc_frame_index -> session_time: equals video_frame_index by construction
"""

from __future__ import annotations

import datetime
import logging
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
from stroke_orofacial.manifest import (
    SessionManifest,
    build_manifest,
    iter_session_suffixes,
)
from stroke_orofacial.paths import PathResolver

logger = logging.getLogger(__name__)


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

    Single-entry-point dispatch (Phase 7-pre-multi-half):

      - **Single-half manifest** (``manifest.halves is None``): default
        behavior — load from ``manifest.alignment_template`` (cam2 only)
        or via :meth:`PathResolver.alignment_template_legacy_read` for
        other cams. If the template doesn't exist (or
        ``force_recompute=True``), compute fresh from
        ``manifest.wavesurfer_file`` + camera CSV.
      - **Multi-half manifest** (``manifest.halves is not None``):
        dispatches into :func:`compute_and_merge_alignment_multi_half`
        which computes/caches per-half templates (under the ``_new``
        resolvers, ``pipeline_outputs/``) and merges them. The merged
        NPZ is then loaded back into an :class:`AlignmentResult`.
        ``slope_ws_per_camFrame`` and ``intercept_ws_samples`` are NaN
        for multi-half (each half has its own affine fit; no single
        diagnostic value applies to a stitched time axis). ``source``
        on the returned AlignmentResult is ``"merged_multi_half"``.

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

    # Phase 7-pre-multi-half: multi-half manifests dispatch into the
    # per-half orchestrator. Single-entry-point flow — downstream callers
    # of load_or_compute_alignment don't need to know whether the session
    # is single-half or multi-half; they just get an AlignmentResult.
    #
    # The orchestrator computes/caches per-half templates under _new
    # resolvers (pipeline_outputs/) and merges them into a parent-level
    # merged NPZ. We then load that merged NPZ and return an
    # AlignmentResult.
    #
    # slope_ws_per_camFrame and intercept_ws_samples are diagnostic-only
    # in single-half (no downstream consumers; verified 2026-05-09 grep).
    # For multi-half they are conceptually undefined — each half has its
    # own affine fit, and a single slope/intercept doesn't apply to a
    # stitched time axis. Set them to NaN so the AlignmentResult shape
    # is preserved without inventing a meaningless number.
    if manifest.halves is not None:
        merged_path = compute_and_merge_alignment_multi_half(
            manifest, resolver, params, force_recompute=force_recompute,
        )
        tmpl = load_alignment_template(merged_path)
        return AlignmentResult(
            sig_camIdx__idx_ws=tmpl["sig_camIdx__idx_ws"],
            sig_wsIdx__idx_cam=tmpl["sig_wsIdx__idx_cam"],
            slope_ws_per_camFrame=float("nan"),
            intercept_ws_samples=float("nan"),
            Fs_ws=float(tmpl["Fs_ws_input"]),
            source="merged_multi_half",
        )

    # Existing-template path: prefer the manifest's cam2 entry; fall back
    # to the resolver for other cams (manifest only tracks cam2) or when
    # the manifest didn't see the template at build time but it now exists.
    #
    # Phase 7-pre-secondary-spout: thread manifest.session_suffix into
    # the cache-discovery resolver so Pattern B b-half manifests look at
    # {date_str}b.npz (not {date_str}.npz). Without this thread, the
    # b-half load would spuriously miss the cache + overwrite the bare-
    # half template on recompute (since neither b nor bare write to disk
    # in the single-half branch, but the cache-hit logic short-circuits
    # the recompute incorrectly).
    if cam_idx == 2 and manifest.alignment_template is not None:
        existing_path = manifest.alignment_template
    else:
        # Phase 7-pre-alignment-templates Task 4 cutover: read via the
        # unified prefer-new-then-legacy resolver. Reaches here when
        # cam_idx != 2 (manifest only tracks cam2's template) OR when
        # manifest didn't see the template at build time. Returns the
        # new-tree path post-F-P-7 cohort emit; legacy fallback per
        # Addendum #1 L3 for sessions the new pipeline can't emit.
        try:
            existing_path = resolver.alignment_template_for_reading(
                animal, date, cam=cam_name,
                session_suffix=manifest.session_suffix,
            )
        except FileNotFoundError:
            # Sentinel: neither tree has the file — leave existing_path
            # pointing at the new-tree-shaped path so the
            # ``existing_path.exists()`` check below short-circuits the
            # cache hit and we fall into the recompute branch (same
            # outcome as pre-cutover when alignment_template_legacy_read
            # returned a non-existent path).
            existing_path = resolver.alignment_template_new(
                animal, date, cam=cam_name,
                session_suffix=manifest.session_suffix,
            )

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
    #
    # Phase 7-pre-secondary-spout: derive a subdir_override for the
    # fallback path so Pattern B b-half manifests resolve to the b-half
    # cam dir ``{date_str}b/`` by convention. The if-branch (line above)
    # already resolves correctly because build_manifest populates
    # manifest.video_files using the suffix-aware cam_dir at manifest-
    # build time. This else-branch fallback only fires when video
    # discovery yielded no AVIs (degraded case); without the override
    # it would silently resolve to the bare-half cam dir. The
    # Pattern B bare-half + bare_cam_subdir_override case is unsupported
    # here (no current cohort session has that asymmetry; Task 1 audit
    # confirms PS55/2025-04-24 has WS asymmetry only).
    if cam_idx == 2 and manifest.video_files:
        cam_dir = manifest.video_files[0].parent
    else:
        date_str = date.strftime("%Y%m%d")
        cam_subdir_override = (
            f"{date_str}b" if manifest.session_suffix == "b" else None
        )
        cam_dir = resolver.camera_dir(
            date, animal, subdir_override=cam_subdir_override,
        )
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
    overrides_config: dict[str, Any] | None = None,
) -> dict[str | None, AlignmentResult]:
    """Convenience wrapper: builds one or more ``SessionManifest`` instances
    then calls :func:`load_or_compute_alignment` for each.

    Phase 7-pre-secondary-spout: the wrapper iterates
    :func:`stroke_orofacial.manifest.iter_session_suffixes` so Pattern B
    (closer-spout 2nd-acquisition) sessions compute BOTH halves'
    alignment templates as independent single-half templates — one
    bare half (``session_suffix=None``) and one b half
    (``session_suffix="b"``). Vanilla single-half + Pattern A
    multi-half-merged sessions iterate once with
    ``session_suffix=None``; Pattern A's merged result still comes
    back through :func:`load_or_compute_alignment` →
    :func:`compute_and_merge_alignment_multi_half` (unchanged), wrapped
    in a single-entry ``{None: AlignmentResult(source="merged_multi_half")}``
    dict.

    There is NO Phase 3 merge for Pattern B sessions — each half emits
    its own alignment template at its own suffix-aware path (the
    ``{date_str}.npz`` / ``{date_str}b.npz`` write convention is owned
    by :meth:`PathResolver.alignment_template_legacy_read` /
    :meth:`PathResolver.alignment_template_new`, both already
    suffix-aware per Phase 7-pre-secondary-spout Task 3c).

    Phase 3 alignment is DLC-agnostic; ``build_manifest()`` treats DLC
    files as optional, so this wrapper works for sessions where DLC
    inference hasn't run yet. The ``analysis_context="alignment"``
    argument scopes exclusion checks: sessions with
    ``applies_to: [dlc]`` exclusions (e.g., "missing camera data") also
    block alignment since the wavesurfer↔camera mapping needs the camera
    timestamp CSVs — mark those sessions with ``applies_to: [dlc,
    alignment]`` or ``applies_to: [alignment]`` as appropriate.

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
        Pre-loaded wavesurfer signals. Threaded through to every
        per-suffix :func:`load_or_compute_alignment` call. Typically
        only meaningful for non-Pattern-B sessions (one suffix); for
        Pattern B, each half loads its own WS signals from its own
        per-half WS file.
    force_recompute : bool
        If True, always recompute even if existing templates exist.
        Applied to every suffix in the iteration.
    overrides_config : dict, optional
        Pre-loaded ``configs/session_overrides.yaml`` dict. When None,
        lazily loaded here (once per call) and threaded through to
        :func:`build_manifest`. Tests may pass an in-memory dict to
        avoid touching the on-disk YAML.

    Returns
    -------
    dict[str | None, AlignmentResult]
        Mapping ``session_suffix -> AlignmentResult``. Keys:

        - ``None`` (always present for non-Pattern-B and Pattern A
          sessions; present for Pattern B if the bare half succeeded).
        - ``"b"`` (present for Pattern B sessions if the b half
          succeeded).

        Partial-failure tolerance: if one half raises
        :class:`FileNotFoundError` or :class:`RuntimeError` (missing
        WS/cam inputs OR alignment-compute boundary error) but the
        other half succeeds, the returned dict includes only the
        successful half's entry; the failure is logged as a WARNING.
        If BOTH halves fail, the FIRST encountered exception is
        re-raised so single-half callers' existing semantics are
        preserved.

    Raises
    ------
    FileNotFoundError, RuntimeError
        When EVERY suffix raises. Single-half non-Pattern-B sessions
        surface this as before — there's only one suffix in the
        iteration, so a single raise becomes the re-raise.
    """
    animal_info = get_animal(animal)

    # Lazy-load overrides_config once (mirrors build_manifest's pattern
    # and process_session_by_animal_date's Task-4 lazy-load).
    if overrides_config is None:
        from stroke_orofacial.config_loader import load_session_overrides
        overrides_config = load_session_overrides()

    suffixes = iter_session_suffixes(animal, date, overrides_config)
    result_per_suffix: dict[str | None, AlignmentResult] = {}
    per_suffix_errors: dict[str | None, Exception] = {}

    for suffix in suffixes:
        try:
            manifest = build_manifest(
                animal, date, resolver, animal_info,
                analysis_context="alignment",
                overrides_config=overrides_config,
                session_suffix=suffix,
            )
            result_per_suffix[suffix] = load_or_compute_alignment(
                manifest, resolver, params,
                ws_signals=ws_signals,
                force_recompute=force_recompute,
            )
        except (FileNotFoundError, RuntimeError) as e:
            # FileNotFoundError: missing on-disk inputs (WS file, cam
            # CSV) for this half.
            # RuntimeError: alignment-compute boundary errors
            # (e.g. monotonicity / shape failures from
            # make_alignment_template) — partial-failure tolerance
            # lets the other half still produce a result.
            per_suffix_errors[suffix] = e
            logger.warning(
                "Phase 7-pre-secondary-spout: skipping alignment for "
                "%s/%s suffix=%r due to %s: %s",
                animal, date.isoformat(), suffix, type(e).__name__, e,
            )
            # Continue to the next suffix.

    # Partial-failure policy: if at least one suffix succeeded, return
    # the partial result. If all suffixes failed, re-raise the first
    # exception so single-half callers' existing raise semantics are
    # preserved unchanged.
    if not result_per_suffix:
        if per_suffix_errors:
            first_suffix = next(iter(per_suffix_errors))
            raise per_suffix_errors[first_suffix]
        # No suffixes iterated at all — impossible because
        # iter_session_suffixes always returns at least [None]. Defensive
        # case: return empty mapping.
        return {}

    return result_per_suffix


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

    Layout (Decision 3 of the Phase 7-pre-multi-half Task 1 verdict;
    revised 2026-05-05 incident response — paths route through
    pipeline_outputs/, not the live MICROSCOPE legacy tree):
      - Per-half NPZs land at
        ``<pipeline_outputs>/dlc_analysis/alignment_templates/cam2/{ANIMAL}/{date_str}{halves_concat_label}/{date_str}{half_id}.npz``
        — exposed by :meth:`PathResolver.alignment_template_per_half_new`.
      - Merged NPZ lands at
        ``<pipeline_outputs>/dlc_analysis/alignment_templates/cam2/{ANIMAL}/{date_str}.npz``
        — exposed by :meth:`PathResolver.alignment_template_new`.
      Single-half code paths still read legacy templates via
      :meth:`PathResolver.alignment_template_legacy_read` (which routes
      through ``microscope_server`` and is read-only).

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

    # Per-half NPZ paths (Decision 3 layout). Routed through
    # alignment_template_per_half_new (under pipeline_outputs/) so the
    # 2026-05-05 incident class — writes to the live MICROSCOPE legacy
    # tree — is structurally impossible. Defense-in-depth via
    # assert_safe_write_path before each np.savez_compressed below.
    from stroke_orofacial._writeguard import assert_safe_write_path
    per_half_paths = [
        resolver.alignment_template_per_half_new(
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
        # Defense-in-depth: writeguard fires before the actual write.
        # The resolver SHOULD already give us a safe path, but a
        # belt-and-suspenders check here makes any future regression
        # in alignment_template_per_half_new fail loud at the call
        # site instead of silently corrupting legacy data.
        assert_safe_write_path(out_path)
        np.savez_compressed(str(out_path), **template_dict)

    # Merge — writes to alignment_template_new (parent-level under
    # pipeline_outputs/). Deterministic from per-half NPZs; merge
    # function does its own writeguard via the conftest fixture in
    # tests, and assert_safe_write_path is a redundant check for
    # the production path here.
    from stroke_orofacial.spout_behavior.multi_half_merge import (
        merge_alignment_templates,
    )
    merged_path = resolver.alignment_template_new(
        manifest.animal, manifest.date, cam=cam_name,
    )
    assert_safe_write_path(merged_path)
    merge_alignment_templates(per_half_paths, merged_path)
    return merged_path
