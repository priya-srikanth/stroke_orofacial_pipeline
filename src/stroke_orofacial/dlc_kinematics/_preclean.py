"""Phase 7e — v7 pre-clean for DLC tongue interpolated traces (SKELETON).

Ports the v7 pre-clean algorithm from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 147-324)
plus the Addendum #1 x-side rules (see
``docs/prompts/phase-7e-addendum-1-task0-x-audit-verdict.md``).

This module is the canonical Stage 1 cleaner that runs BEFORE the v7
detector (:mod:`.detector_v2`). Consumes the Phase 7a.2 v5p3
``interpolated_traces/`` parquet and emits a cleaned trace + per-cluster
diagnostics.

Algorithm overview (per Decision 1 + Addendum #1):

**Y-side (Decisions 9-13 — direct port from scratch):**

  Step 1a — cluster classifier. Each contiguous raw cluster
    (``~is_intp & ~is_base``) is labeled as ``keep_low`` / ``keep_real`` /
    ``artifact_narrow`` / ``artifact_flat`` / ``artifact_isolated_short``
    via the combined Rule A (intra-cluster shape) + Rule B (non-base low
    neighbor) + isolated-short override. See Decisions 9-11.
  Step 1b — frame-level y outlier. Within each kept cluster, frames where
    ``|y - local_median| > frame_jump_thr_px`` are single-frame wiped.
    See Decision 12.
  Step 1c — wipe artifact clusters + frame outliers (set y=0,
    is_baseline_fill=True).
  Step 1d — PCHIP-extend wipe. ±pchip_extend_ms into adjacent is_intp
    frames around each wipe. See Decision 13.
  Step 1e — bracketed-interp wipe. Wipe any is_intp run bracketed on both
    sides by wiped/baseline-fill.

**X-side (Addendum #1 Rules 1-4):**

  Rule 1 — at all is_baseline_fill_clean frames (Phase 7a.2 stage-5 fill
    OR y-side pre-clean wipes), set ``x = x0`` where ``x0 = median(
    x_final[is_baseline_fill_orig])`` (per-session). Symmetric with y=0
    convention.
  Rule 2 — drop y-wiped frames from x's PCHIP anchor set when re-
    interpolating x at PCHIP-fill frames.
  Rule 3 — frames with ``|x| > x_abs_max_px`` are wiped as biological
    outliers; ±x_pchip_extend_ms into adjacent is_intp frames are also
    wiped; all wiped frames re-PCHIP'd through the outlier-excluded
    anchor set.
  Rule 4 — joint x+y short-burst wipe via direction-aware nearest-raw-
    flank rule. For each raw frame ``i``, find nearest raw flanks within
    ±x_flank_max_distance frames (skipping is_intp/is_base). Flag if
    burst deviates from BOTH flanks by > x_jump_thr_px AND burst is
    CLOSER to x0 than both flanks. At flagged frames, x is re-PCHIP-
    interpolated (NOT snapped to x0 — burst sits inside an otherwise-
    real lick) AND y is also wiped (set y=0, is_baseline_fill=True) so
    the detector re-runs on the joint-cleaned trace.

All numeric constants are sourced from
``configs/defaults.yaml: dlc_kinematics.tongue_pertrial.preclean`` — no
magic numbers in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class _RawCluster:
    """One contiguous run of raw DLC frames.

    Used internally by :func:`preclean_trace` Step 1a. Each cluster gets
    classified as keep_low / keep_real / artifact_* and the artifacts
    are wiped to baseline-fill.
    """

    lo: int                 # first frame index (inclusive)
    hi: int                 # last frame index (inclusive)
    length: int             # hi - lo + 1
    y_min: float
    y_max: float
    y_median: float
    y_range: float
    label: str              # "keep_low" / "keep_real" / "artifact_*"


@dataclass
class _PrecleanDiagnostics:
    """Per-trace cleaning diagnostics returned by :func:`preclean_trace`.

    Useful for downstream visualization (mirrors scratch impl's
    ``render_trial`` consumption) and for parquet metadata.
    """

    clusters: list[_RawCluster] = field(default_factory=list)
    n_artifact_clusters: int = 0
    n_artifact_frames: int = 0
    n_interp_wiped: int = 0          # bracketed-interp wipes (Step 1e)
    n_frame_outliers: int = 0        # Step 1b single-frame y outliers
    n_pchip_extended: int = 0        # Step 1d PCHIP-extend frames
    # Addendum #1 x-side counters
    n_x_hard_outliers: int = 0       # Rule 3 hits
    n_x_joint_outliers: int = 0      # Rule 4 hits
    n_x_pchip_extended: int = 0      # Rule 3 PCHIP-extend
    x0_baseline_fill: float = 0.0    # Rule 1 — session-derived baseline-fill x


def preclean_trace(
    y: np.ndarray,
    x: np.ndarray,
    is_interp_fill: np.ndarray,
    is_baseline_fill: np.ndarray,
    n_frames: int,
    fps: float,
    *,
    params: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, _PrecleanDiagnostics]:
    """V7 pre-clean — y-side cluster + frame rules + x-side Addendum #1 rules.

    See module docstring for algorithm overview. Direct port of
    ``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.preclean_trace``
    (lines 147-324) + Addendum #1 x-side rules.

    Parameters
    ----------
    y : np.ndarray, shape (n_frames,)
        Phase 7a.2 v5p3 interpolated y values.
    x : np.ndarray, shape (n_frames,)
        Phase 7a.2 v5p3 interpolated x values.
    is_interp_fill : np.ndarray, shape (n_frames,) dtype bool
        From Phase 7a.2 parquet — True at PCHIP-interpolated frames.
    is_baseline_fill : np.ndarray, shape (n_frames,) dtype bool
        From Phase 7a.2 parquet — True at stage-5 baseline-fill frames.
    n_frames : int
    fps : float
    params : dict
        Loaded from ``configs/defaults.yaml`` —
        ``dlc_kinematics.tongue_pertrial.preclean``.

    Returns
    -------
    y_clean, x_clean : np.ndarray, shape (n_frames,)
        Cleaned y/x with artifact wipes + PCHIP re-interpolation applied.
    is_baseline_fill_clean : np.ndarray, shape (n_frames,) dtype bool
        Updated baseline-fill mask (original ∪ y-side wipes ∪ joint x+y
        Rule 4 wipes).
    diagnostics : _PrecleanDiagnostics
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


# ---------------------------------------------------------------------------
# Y-side helpers (Phase 7e Task 2 port targets)
# ---------------------------------------------------------------------------


def _classify_raw_clusters(
    y: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    n_frames: int, fps: float, *, params: dict[str, Any],
) -> list[_RawCluster]:
    """Step 1a — cluster classifier (Decisions 9-11).

    Iterates contiguous raw clusters; labels each as keep_low / keep_real /
    artifact_narrow / artifact_flat / artifact_isolated_short via the
    combined Rule A + Rule B + isolated-short override. Direct port of
    scratch lines 165-240.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


def _find_y_frame_outliers(
    y: np.ndarray, clusters: list[_RawCluster], n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> np.ndarray:
    """Step 1b — frame-level y outlier check (Decision 12).

    Within each KEPT cluster, flags frames where ``|y - local_median|
    > frame_jump_thr_px`` for single-frame wipe. Direct port of scratch
    lines 267-303.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


def _pchip_extend_wipes(
    wiped_mask: np.ndarray, is_interp_fill: np.ndarray,
    is_baseline_fill_clean: np.ndarray, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> tuple[np.ndarray, int]:
    """Step 1d — extend wipe into adjacent is_intp frames (Decision 13).

    For each frame in ``wiped_mask``, walk left and right into is_intp
    frames up to ±pchip_extend_ms; add those frames to the wipe mask.
    Returns the updated baseline-fill-clean mask + count of new frames.
    Direct port of scratch lines 252-265 + 290-303.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


def _wipe_bracketed_interp(
    y_clean: np.ndarray, is_interp_fill: np.ndarray,
    is_baseline_fill_clean: np.ndarray, n_frames: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Step 1e — wipe any is_intp run bracketed by wiped/baseline-fill
    on BOTH sides. Direct port of scratch lines 305-321.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


# ---------------------------------------------------------------------------
# X-side helpers (Phase 7e Task 2 — Addendum #1 Rules 1-4)
# ---------------------------------------------------------------------------


def _derive_x0_baseline_fill(
    x: np.ndarray, is_baseline_fill_orig: np.ndarray,
) -> float:
    """Addendum #1 Rule 1 helper — derive x0 from Phase 7a.2's stage-5
    baseline-fill convention.

    ``x0 = median(x[is_baseline_fill_orig])`` if any baseline-fill frames
    exist, else ``0.0``. Typically near 0 in spout-centered frame but
    session-specific.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


def _find_x_isolated_jumps(
    x: np.ndarray, is_interp_fill: np.ndarray,
    is_baseline_fill_clean: np.ndarray, n_frames: int, fps: float,
    x0: float, *, params: dict[str, Any],
) -> np.ndarray:
    """Addendum #1 Rule 4 — direction-aware nearest-raw-flank check.

    For each raw frame ``i``, find the nearest RAW flank (skipping
    is_intp/is_base frames) within ±x_flank_max_distance each direction.
    Flag the frame if:

      (a) ``|x[i] - x_left| > x_jump_thr_px``
      (b) ``|x[i] - x_right| > x_jump_thr_px``
      (c) ``|x[i] - x0| < min(|x_left - x0|, |x_right - x0|)``
          (direction TOWARD x0 — DLC default-back-to-zero pattern;
          distinguishes from real lick protrusions which deviate AWAY
          from x0)

    Validated on canonical-9: catches PS54 51L first peak (x=−2, flanks
    +48/+30) ✓; preserves PS54 76L first lick (x=+90, flanks +50/+50)
    ✓; preserves PS54 24L 1700ms peak (x=+95, flanks +90/+90) ✓; no
    false positives on PS47 33L active-licking troughs ✓.

    Ported from ``.scratch_phase_7e/visualize_x_imputation.py:find_x_isolated_jumps``.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")


def _clean_x_trace(
    x: np.ndarray, y_clean: np.ndarray, is_interp_fill: np.ndarray,
    is_baseline_fill_clean: np.ndarray, is_baseline_fill_orig: np.ndarray,
    n_frames: int, fps: float, *, params: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Addendum #1 Rules 1-4 — full x-side pre-clean.

    Applies x0 baseline-fill (Rule 1), drops y-wiped frames from anchor
    set (Rule 2), wipes |x|>x_abs_max_px frames + PCHIP-extend (Rule 3),
    and runs the joint x+y short-burst detector (Rule 4). Returns:

      x_clean, x_hard_outlier_mask, x_joint_outlier_mask,
      x_extend_mask, is_baseline_fill_clean_augmented, x0

    The ``is_baseline_fill_clean_augmented`` mask includes the x_joint_-
    outlier frames so the caller (:func:`preclean_trace`) can also wipe
    y at those frames before the detector runs (Rule 4 production-port
    requirement — propagate the flag to y-side state).

    Ported from ``.scratch_phase_7e/visualize_x_imputation.py:clean_x_trace``.
    """
    raise NotImplementedError("Port body in Phase 7e Task 2")
