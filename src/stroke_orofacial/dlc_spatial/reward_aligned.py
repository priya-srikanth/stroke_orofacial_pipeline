"""Reward-aligned spatial analysis functions.

Ported from cell 16 (and cells 18, 20) of canonical notebook
``20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb``.

Loads reward events from Phase 2's ``licks_and_rewards`` NPZ, converts
WS sample indices → camera frame indices via Phase 3's alignment template,
builds peri-reward frame windows, and produces reward-aligned heatmaps.

This is the first phase without array-level parity reference — the legacy
cell 16 was coded but never run to produce saved outputs on MICROSCOPE.
Tongue config is legacy-ported; jaw, nose, and whisker configs are
sanity-check-only defaults.

**Phase 6.8a (mouse-frame trial_group):** Phase 2 NPZs carry mouse-frame
``Reward_L`` / ``Reward_R`` keys post-task-#17 re-emit, stamped with
``wavesurfer_sides_match_mouse_sides`` + ``side_convention_version``
scalars. :func:`load_reward_events` now verifies that stamp is present
and, if the caller supplies ``wavesurfer_sides_match_mouse_sides``, that
it agrees with what Phase 2 wrote — guarding against silently reading a
pre-re-emit NPZ as if it were mouse-frame. Callers pass
``trial_group="L"`` / ``"R"`` meaning *mouse*-L / *mouse*-R and the
orchestrator forwards that meaning through the return dict so downstream
writers (notebook 12 → :func:`save_heatmap_npz`) can stamp the Phase 6
output with the same convention.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import numpy as np

from stroke_orofacial.animals import get_animal
from stroke_orofacial.dlc_spatial.window_selector import (
    RewardAlignedWindow,
    _ws_to_cam_frames,
)
from stroke_orofacial.lr_convention import (
    SIDE_CONVENTION_MATCH_KEY,
    SIDE_CONVENTION_VERSION,
    SIDE_CONVENTION_VERSION_KEY,
    stamp_side_convention,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver


def load_reward_events(
    licks_npz_path: Path | str,
    trial_group: str = "all",
    *,
    wavesurfer_sides_match_mouse_sides: bool | None = None,
) -> np.ndarray:
    """Load reward onset indices from a licks_and_rewards NPZ.

    Per Phase 6.8a, ``trial_group`` is interpreted in the **mouse frame**:
    ``"L"`` means mouse-left reward trials, ``"R"`` means mouse-right.
    Phase 2's licks NPZ must carry the :mod:`stroke_orofacial.lr_convention`
    stamp so this function can verify it was emitted in the mouse frame
    (via task #17's re-emit). A pre-re-emit NPZ without the stamp would
    still have ``Reward_L`` / ``Reward_R`` keys — but interpreted as
    experimenter-frame — and reading it as mouse-frame would silently
    swap L and R on the mirrored rig. We raise instead.

    Parameters
    ----------
    licks_npz_path : Path or str
        Path to the ``licks_and_rewards/{animal}/{YYYYMMDD}.npz`` file
        from Phase 2 (mouse-frame post task #17).
    trial_group : str
        ``"all"`` (both sides), ``"L"`` (mouse-left rewards only), or
        ``"R"`` (mouse-right rewards only).
    wavesurfer_sides_match_mouse_sides : bool, optional
        When provided, verifies the Phase 2 NPZ's stamped value equals
        this boolean. Mismatch → :class:`ValueError` (typically means
        the caller's ``AnimalInfo`` is out of sync with the NPZ on disk
        — e.g. the yaml flag was edited after the NPZ was emitted).
        When ``None``, the stamp is still required to exist but its
        value is not cross-checked.

    Returns
    -------
    np.ndarray
        Sorted array of reward onset indices in wavesurfer sample space.
        (L/R is mouse-frame; the *array values* are WS sample indices
        — those are frame-neutral, since the alignment LUT is
        per-session and cares only about WS↔camera, not L↔R.)

    Raises
    ------
    ValueError
        If the Phase 2 NPZ is missing the side-convention stamp
        (pre-re-emit file), if the stamped version doesn't match
        :data:`SIDE_CONVENTION_VERSION`, or if
        ``wavesurfer_sides_match_mouse_sides`` was provided and
        disagrees with the stamped value.
    """
    data = np.load(str(licks_npz_path), allow_pickle=True)

    # Phase 6.8a: require the Phase 2 side-convention stamp (task #17
    # re-emit). Without it we can't tell whether Reward_L in this file
    # is experimenter-L (pre-re-emit) or mouse-L (post-re-emit), and
    # silently picking the wrong interpretation on the mirrored rig
    # swaps the stratification.
    if SIDE_CONVENTION_VERSION_KEY not in data.files:
        raise ValueError(
            f"{licks_npz_path}: Phase 2 NPZ is missing "
            f"{SIDE_CONVENTION_VERSION_KEY!r} — this is a pre-task-#17 "
            f"emission and its Reward_L/Reward_R keys are in the "
            f"wavesurfer frame, not the mouse frame. Re-emit Phase 2 "
            f"(see docs/runbooks/reemit-phase-5-6-after-lr-fix.md §4) "
            f"before running reward-aligned Phase 6 analyses."
        )
    if SIDE_CONVENTION_MATCH_KEY not in data.files:
        raise ValueError(
            f"{licks_npz_path}: Phase 2 NPZ has "
            f"{SIDE_CONVENTION_VERSION_KEY!r} but is missing "
            f"{SIDE_CONVENTION_MATCH_KEY!r} — malformed stamp. Re-emit "
            f"Phase 2."
        )
    stamped_version = int(data[SIDE_CONVENTION_VERSION_KEY])
    if stamped_version != SIDE_CONVENTION_VERSION:
        raise ValueError(
            f"{licks_npz_path}: stamped side_convention_version="
            f"{stamped_version} but this code expects "
            f"{SIDE_CONVENTION_VERSION}. The convention scheme changed; "
            f"re-emit Phase 2 under the new scheme before running "
            f"Phase 6 analyses."
        )
    stamped_match = bool(data[SIDE_CONVENTION_MATCH_KEY])
    if (
        wavesurfer_sides_match_mouse_sides is not None
        and stamped_match != wavesurfer_sides_match_mouse_sides
    ):
        raise ValueError(
            f"{licks_npz_path}: caller passed "
            f"wavesurfer_sides_match_mouse_sides="
            f"{wavesurfer_sides_match_mouse_sides} but the Phase 2 NPZ "
            f"was emitted with {stamped_match}. This typically means "
            f"configs/animals.yaml was edited after the NPZ was "
            f"written — re-emit Phase 2 to pick up the new flag."
        )

    if trial_group == "L":
        return np.sort(data["Reward_L"].astype(int))
    elif trial_group == "R":
        return np.sort(data["Reward_R"].astype(int))
    else:
        return np.sort(np.concatenate([
            data.get("Reward_L", np.array([], dtype=int)).astype(int),
            data.get("Reward_R", np.array([], dtype=int)).astype(int),
        ]))


def ws_samples_to_frame_indices(
    ws_samples: np.ndarray,
    sig_camIdx__idx_ws: np.ndarray,
    n_cam_frames: int,
) -> np.ndarray:
    """Convert wavesurfer sample indices to camera frame indices.

    Thin wrapper around ``_ws_to_cam_frames`` for public use.

    Parameters
    ----------
    ws_samples : np.ndarray
        Reward onset indices in WS sample space.
    sig_camIdx__idx_ws : np.ndarray
        Alignment lookup table from ``AlignmentResult``.
    n_cam_frames : int
        Total number of camera/DLC frames.

    Returns
    -------
    np.ndarray
        Frame indices (int). Invalid entries are -1.
    """
    return _ws_to_cam_frames(ws_samples, sig_camIdx__idx_ws, n_cam_frames)


def build_reward_aligned_window(
    reward_ws_samples: np.ndarray,
    sig_camIdx__idx_ws: np.ndarray,
    window_ms: tuple[float, float],
    fps: float,
    n_frames: int,
) -> RewardAlignedWindow:
    """Construct a RewardAlignedWindow from reward events + alignment data.

    Parameters
    ----------
    reward_ws_samples : np.ndarray
        Reward onset indices in WS sample space.
    sig_camIdx__idx_ws : np.ndarray
        Alignment lookup from Phase 3.
    window_ms : tuple[float, float]
        (pre_ms, post_ms) — e.g. ``(-500, 5000)`` for 500ms before to
        5000ms after each reward.
    fps : float
        Camera frame rate (250 Hz).
    n_frames : int
        Total DLC/camera frames in the session.

    Returns
    -------
    RewardAlignedWindow
    """
    return RewardAlignedWindow(
        reward_ws_samples=reward_ws_samples,
        sig_camIdx__idx_ws=sig_camIdx__idx_ws,
        window_ms=window_ms,
        fps=fps,
        n_frames=n_frames,
    )


def build_reward_aligned_analysis(
    manifest: SessionManifest,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    window_ms: tuple[float, float],
    resolver: PathResolver,
    spatial_config: dict[str, Any],
    reward_config: dict[str, Any],
    *,
    wavesurfer_sides_match_mouse_sides: bool | None = None,
) -> dict[str, Any] | None:
    """Run a complete reward-aligned spatial analysis for one session.

    Primary entry point — consumes a ``SessionManifest`` produced by
    ``build_manifest()``. Reads DLC h5 files from ``manifest.dlc_h5_files``
    and the cam2 alignment template from ``manifest.alignment_template``
    instead of re-discovering. Phase 6 is DLC-required (it reads the
    centered parquet derived from DLC h5).

    Pure function — no module-level state. Loads all inputs from disk,
    builds the reward-aligned window, computes the histogram, and returns
    the results.

    For callers that prefer the legacy (animal, date_str) entry point,
    see ``build_reward_aligned_analysis_by_animal_date()`` below.

    Parameters
    ----------
    manifest : SessionManifest
        Per-session manifest. ``dlc_h5_files`` must be populated.
        ``alignment_template`` (cam2) and the Phase 2 licks NPZ must
        exist on disk for the analysis to proceed.
    bodypart : str
        Bodypart name.
    center_mode : str
        Centering mode (nose, spout_midpoint, eye_midpoint).
    trial_group : str
        ``"all"``, ``"L"``, or ``"R"`` — mouse-frame per Phase 6.8a
        (post task #17 re-emit of Phase 2). ``"L"`` means mouse-left
        reward trials regardless of rig orientation.
    window_ms : tuple[float, float]
        Reward window in ms.
    resolver : PathResolver
        Configured path resolver (used for output-tree placement and as
        a cam2 alignment-template fallback when the manifest didn't see it).
    spatial_config : dict
        The ``dlc_spatial`` section from defaults.yaml.
    reward_config : dict
        The ``dlc_spatial_reward_aligned`` section from defaults.yaml.
    wavesurfer_sides_match_mouse_sides : bool, optional
        Per-animal rig-orientation flag from
        :attr:`stroke_orofacial.animals.AnimalInfo.wavesurfer_sides_match_mouse_sides`.
        When provided, the loader verifies the Phase 2 NPZ's stamp
        agrees with this value (catches stale NPZs after yaml edits)
        and the value is forwarded into the returned dict so the
        downstream writer (notebook 12 → :func:`save_heatmap_npz`)
        can stamp the Phase 6 NPZ with the same convention. When
        ``None``, the Phase 2 stamp is still required to exist (else
        we can't tell mouse-frame from wavesurfer-frame) but its value
        is not cross-checked.

    Returns
    -------
    dict or None
        ``{"histogram": ..., "window": ..., "n_rewards": ..., "n_selected_frames": ..., "trial_group": ..., "window_ms": ..., "bodypart": ..., "center_mode": ..., "wavesurfer_sides_match_mouse_sides": ...}``
        — or None if the manifest has zero rewards for the requested
        ``trial_group`` (a valid-but-empty data condition; e.g. a
        post-stroke session with no L-only trials). The
        ``wavesurfer_sides_match_mouse_sides`` field echoes the kwarg
        when provided, else the value stamped into the Phase 2 NPZ
        (read back from disk), so notebook 12 can stamp the Phase 6
        output without having to re-lookup ``AnimalInfo``.

    Raises
    ------
    FileNotFoundError
        If any Phase-6 prerequisite is missing: empty
        ``manifest.dlc_h5_files`` (need DLC inference), missing Phase 4
        centered parquet (need ``scripts/run_notebook_10_phase_4_centering.py``),
        missing Phase 2 licks NPZ (need Phase 2 re-emit), or missing
        cam2 alignment template (need
        ``scripts/make_alignment_templates.py``). Each variant names
        the exact missing artefact so log triage points at the right
        upstream stage.
    ValueError
        Propagated from :func:`load_reward_events` if the Phase 2 NPZ
        is un-stamped (pre-task-#17) or its stamp disagrees with
        ``wavesurfer_sides_match_mouse_sides``.
    """
    if not manifest.dlc_h5_files:
        raise FileNotFoundError(
            f"{manifest.session_id}: manifest.dlc_h5_files is empty. "
            f"Phase 6 reward-aligned spatial analysis requires DLC. "
            f"Either provide a manifest with DLC files, or run DLC "
            f"inference first."
        )

    from stroke_orofacial.dlc_io.parquet import _param_sig, read_centered_parquet
    from stroke_orofacial.dlc_spatial.pixel_bins import build_histogram

    animal = manifest.animal
    date = manifest.date
    date_str = date.strftime("%Y%m%d")

    # Locate the centered parquet derived from this manifest's first DLC h5.
    lik_thr_centering = 0.7  # Phase 4 centering threshold
    sig = _param_sig(center_mode, lik_thr_centering)
    parquet_dir = resolver.pipeline_outputs("dlc_analysis") / f"centered_{center_mode}" / animal
    parquet_name = f"{manifest.dlc_h5_files[0].name}.intermediate.{sig}.parquet"
    parquet_path = parquet_dir / parquet_name
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}/{center_mode}: Phase 4 centered parquet "
            f"missing at {parquet_path}. Run "
            f"`python scripts/run_notebook_10_phase_4_centering.py "
            f"--animals {animal} --dates {date_str} --center-modes {center_mode}` "
            f"(or notebook 10) to emit it."
        )

    df = read_centered_parquet(parquet_path)
    n_frames = len(df)

    # Load reward events from Phase 2 licks NPZ (manifest gives animal+date).
    spout_root = resolver.pipeline_outputs("spout_behavior")
    licks_path = spout_root / "licks_and_rewards" / animal / f"{date_str}.npz"
    if not licks_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: Phase 2 licks NPZ missing at "
            f"{licks_path}. Run notebook 06 (lick/reward extraction) "
            f"for this session before Phase 6.8a."
        )

    reward_ws = load_reward_events(
        licks_path, trial_group,
        wavesurfer_sides_match_mouse_sides=wavesurfer_sides_match_mouse_sides,
    )
    if len(reward_ws) == 0:
        return None

    # Phase 6.8a: surface the effective L/R convention on the return dict
    # so the caller (notebook 12) can stamp the Phase 6 NPZ without a
    # second AnimalInfo lookup. If the caller supplied the flag we echo
    # it; otherwise read back what Phase 2 stamped (authoritative).
    if wavesurfer_sides_match_mouse_sides is not None:
        effective_flag = wavesurfer_sides_match_mouse_sides
    else:
        licks_data = np.load(str(licks_path), allow_pickle=True)
        effective_flag = bool(licks_data[SIDE_CONVENTION_MATCH_KEY])

    # Alignment template: prefer the manifest's cam2 entry; fall back to
    # the resolver if the manifest didn't see it at build time.
    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_legacy_read(animal, date, cam="cam2")
    if not align_path.exists():
        raise FileNotFoundError(
            f"{manifest.session_id}: cam2 alignment template missing at "
            f"{align_path} (and not on manifest). Run "
            f"`python scripts/make_alignment_templates.py` for this "
            f"session before Phase 6.8a."
        )

    align_data = np.load(str(align_path), allow_pickle=True)
    sig_camIdx = align_data["sig_camIdx__idx_ws"]

    # Build reward-aligned window
    fps = float(reward_config.get("fps", 250.0))
    window = build_reward_aligned_window(reward_ws, sig_camIdx, window_ms, fps, n_frames)

    # Build histogram with window.
    # Reward-aligned analyses use the Phase 6 `dlc_spatial_reward_aligned`
    # config for likelihood thresholds and (per-bodypart, non-center-mode-aware)
    # x_range filters; axis limits come from the Phase 5 `dlc_spatial` config
    # which IS per-(bodypart, center_mode).
    bp_config = reward_config.get("bodyparts", {}).get(bodypart, {})
    bp_x_range_reward = bp_config.get("x_range")
    lik_thresholds = bp_config.get("likelihood_thresholds", [0.8])
    lik_thr = lik_thresholds[0] if lik_thresholds else 0.8

    nbins_list = reward_config.get("default_nbins", [80, 80])
    nbins = nbins_list[0] if isinstance(nbins_list[0], int) else int(nbins_list[0])

    # Override only the likelihood threshold (reward-aligned thresholds differ
    # from whole-session thresholds). All other per-(bodypart, center_mode)
    # values (xlim, ylim, x_range) come from the Phase 5 spatial_config via
    # the build_histogram center_mode kwarg.
    config_for_hist = dict(spatial_config)
    config_for_hist["bodyparts"] = dict(config_for_hist.get("bodyparts", {}))
    existing_bp = dict(config_for_hist["bodyparts"].get(bodypart, {}))
    existing_bp["likelihood_threshold"] = lik_thr
    config_for_hist["bodyparts"][bodypart] = existing_bp

    # Reward-aligned per-bodypart x_range (Phase 6 config) takes precedence
    # over the Phase 5 per_center_mode.x_range when provided; fall back to
    # Phase 5's value otherwise by passing x_range=None to build_histogram.
    x_range_override = tuple(bp_x_range_reward) if bp_x_range_reward is not None else None

    histogram = build_histogram(
        df, bodypart, config_for_hist,
        center_mode=center_mode,
        x_range=x_range_override,
        nbins=nbins,
        window=window,
    )

    return {
        "histogram": histogram,
        "window": window,
        "n_rewards": window.n_events,
        "n_selected_frames": window.n_selected,
        "trial_group": trial_group,
        "window_ms": window_ms,
        "bodypart": bodypart,
        "center_mode": center_mode,
        "wavesurfer_sides_match_mouse_sides": effective_flag,
    }


def build_reward_aligned_analysis_by_animal_date(
    animal: str,
    date_str: str,
    bodypart: str,
    center_mode: str,
    trial_group: str,
    window_ms: tuple[float, float],
    resolver: PathResolver,
    spatial_config: dict[str, Any],
    reward_config: dict[str, Any],
    *,
    wavesurfer_sides_match_mouse_sides: bool | None = None,
) -> dict[str, Any] | None:
    """Convenience wrapper: builds a SessionManifest then calls build_reward_aligned_analysis().

    Equivalent to::

        animal_info = get_animal(animal)
        date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
        manifest = build_manifest(
            animal, date, resolver, animal_info,
            analysis_context="dlc.spatial",
        )
        return build_reward_aligned_analysis(
            manifest, bodypart, center_mode, trial_group, window_ms,
            resolver, spatial_config, reward_config,
            wavesurfer_sides_match_mouse_sides=(
                animal_info.wavesurfer_sides_match_mouse_sides
                if wavesurfer_sides_match_mouse_sides is None
                else wavesurfer_sides_match_mouse_sides
            ),
        )

    Per Phase 6.8a, if the caller doesn't pass
    ``wavesurfer_sides_match_mouse_sides`` explicitly, the wrapper
    auto-populates it from the animal's yaml config. This is the
    common path for scripts/tests that identify a session by
    (animal, date) — callers who are already holding an
    ``AnimalInfo`` or ``SessionManifest`` should use the primary
    ``build_reward_aligned_analysis()`` signature directly and pass
    the flag from there.

    The ``analysis_context="dlc.spatial"`` argument scopes exclusion
    checks to DLC-spatial-relevant entries per the Phase 7-pre
    prefix-match schema.

    Phase 6 is DLC-required; if DLC inference hasn't run for this session,
    the underlying ``build_reward_aligned_analysis`` raises FileNotFoundError.
    """
    animal_info = get_animal(animal)
    date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.spatial",
    )
    # Auto-populate the L/R flag from AnimalInfo when the caller didn't
    # pass it explicitly. Explicit kwarg wins — used by tests that need
    # to exercise the flag-mismatch rejection path.
    effective_flag = (
        animal_info.wavesurfer_sides_match_mouse_sides
        if wavesurfer_sides_match_mouse_sides is None
        else wavesurfer_sides_match_mouse_sides
    )
    return build_reward_aligned_analysis(
        manifest, bodypart, center_mode, trial_group, window_ms,
        resolver, spatial_config, reward_config,
        wavesurfer_sides_match_mouse_sides=effective_flag,
    )


def save_reward_aligned_npz(
    result: dict[str, Any],
    path: Path | str,
) -> None:
    """Serialize a reward-aligned analysis result dict to NPZ.

    Phase 6.8a addition — complements the PNG that notebook 12 already
    writes. The NPZ captures the fine-grid histogram arrays (previously
    discarded after PNG render) so Phase 9 stats and post-merge drift
    diagnostics can read ``H_counts`` programmatically without
    re-rendering from parquet.

    NPZ schema:

      - ``H_counts`` — raw 2D histogram counts (nbins × nbins).
      - ``H_proportion`` — normalized so total = 1.
      - ``xedges``, ``yedges`` — bin edges.
      - ``x_limits``, ``y_limits`` — 2-element float arrays giving the
        axis range used for binning (extracted from ``hist["extent"]``).
      - ``nbins`` — histogram resolution per axis.
      - ``trial_group`` — string scalar (``"all"`` / ``"L"`` / ``"R"``,
        mouse-frame per Phase 6.8a).
      - ``window_ms`` — 2-element float array ``[pre_ms, post_ms]``.
      - ``n_rewards`` — int, number of reward events contributing.
      - ``n_selected_frames`` — int, number of DLC frames in the window.
      - ``bodypart`` — string scalar.
      - ``center_mode`` — string scalar.
      - ``wavesurfer_sides_match_mouse_sides`` + ``side_convention_version``
        — stamped via :func:`stamp_side_convention`.

    Parameters
    ----------
    result : dict
        The dict returned by :func:`build_reward_aligned_analysis`.
        Must contain a non-None ``histogram`` entry (callers that
        receive ``None`` from the analysis should skip NPZ saving).
    path : Path or str
        Destination NPZ path. Parent directories are created.

    Raises
    ------
    ValueError
        If ``result["histogram"]`` is ``None``.
    """
    hist = result["histogram"]
    if hist is None:
        raise ValueError(
            "save_reward_aligned_npz: result['histogram'] is None; "
            "caller should skip saving for sessions with no valid "
            "histogram rather than calling this function."
        )

    extent = hist["extent"]
    payload: dict[str, Any] = {
        "H_counts": hist["H_counts"],
        "H_proportion": hist["H_proportion"],
        "xedges": hist["xedges"],
        "yedges": hist["yedges"],
        "x_limits": np.asarray([extent[0], extent[1]], dtype=np.float64),
        "y_limits": np.asarray([extent[2], extent[3]], dtype=np.float64),
        "nbins": int(hist["H_counts"].shape[0]),
        "trial_group": np.asarray(result["trial_group"]),
        "window_ms": np.asarray(
            [float(result["window_ms"][0]), float(result["window_ms"][1])],
            dtype=np.float64,
        ),
        "n_rewards": int(result["n_rewards"]),
        "n_selected_frames": int(result["n_selected_frames"]),
        "bodypart": np.asarray(result["bodypart"]),
        "center_mode": np.asarray(result["center_mode"]),
    }
    stamp_side_convention(
        payload, result["wavesurfer_sides_match_mouse_sides"],
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **payload)
