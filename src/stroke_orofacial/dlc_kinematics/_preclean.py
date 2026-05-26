"""Phase 7e — v7 pre-clean for DLC tongue interpolated traces.

Ports the v7 pre-clean algorithm from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 147-324)
plus the Addendum #1 x-side rules (see
``docs/prompts/phase-7e-addendum-1-task0-x-audit-verdict.md``).

This module is the canonical Stage 1 cleaner that runs BEFORE the v7
detector (:mod:`._detector_v2`). Consumes the Phase 7a.2 v5p3
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
from scipy.interpolate import PchipInterpolator


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


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


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
    pchip_extend = max(2, int(round(
        float(params["pchip_extend_ms"]) / 1000.0 * fps,
    )))

    # === Y-side ===
    # Step 1a: classify clusters
    clusters = _classify_raw_clusters(
        y, is_interp_fill, is_baseline_fill, n_frames, fps, params=params,
    )

    y_clean = y.copy()
    is_base_clean = is_baseline_fill.copy()
    n_pchip_extended = 0

    # Step 1c: wipe artifact clusters + Step 1d PCHIP-extend around each
    for c in clusters:
        if not c.label.startswith("artifact"):
            continue
        y_clean[c.lo:c.hi + 1] = 0.0
        is_base_clean[c.lo:c.hi + 1] = True
        # PCHIP-extend both ends
        n_pchip_extended += _extend_pchip_around_range(
            c.lo, c.hi, y_clean, is_base_clean, is_interp_fill,
            n_frames, pchip_extend,
        )

    # Step 1b: frame-level y outliers within kept clusters
    # (run AFTER Step 1c so we don't waste work on already-wiped clusters)
    n_frame_outliers = 0
    frame_outlier_seeds = _find_y_frame_outliers(
        y_clean, clusters, n_frames, fps, params=params,
    )
    for k in frame_outlier_seeds:
        if is_base_clean[k]:
            continue  # already wiped (shouldn't happen but guard anyway)
        y_clean[k] = 0.0
        is_base_clean[k] = True
        n_frame_outliers += 1
        # PCHIP-extend around the single-frame wipe
        n_pchip_extended += _extend_pchip_around_range(
            k, k, y_clean, is_base_clean, is_interp_fill,
            n_frames, pchip_extend,
        )

    # Step 1e: bracketed-interp wipe (any is_intp run bracketed on BOTH
    # sides by wiped/baseline-fill → wipe the run too)
    n_interp_wiped = _wipe_bracketed_interp(
        y_clean, is_interp_fill, is_base_clean, n_frames,
    )

    # === X-side (Addendum #1 Rules 1-4) ===
    (
        x_clean,
        x_hard_outlier_mask,
        x_joint_outlier_mask,
        x_extend_mask,
        is_base_clean_augmented,
        x0,
    ) = _clean_x_trace(
        x, is_interp_fill, is_base_clean, is_baseline_fill,
        n_frames, fps, params=params,
    )

    # Rule 4 production-port requirement: at joint x+y outlier frames,
    # ALSO wipe y (set y=0, is_base_clean=True) so the detector re-runs
    # on the joint-cleaned trace.
    if x_joint_outlier_mask.any():
        y_clean[x_joint_outlier_mask] = 0.0
        is_base_clean = is_base_clean_augmented

    # Bookkeeping
    n_artifact_clusters = sum(
        1 for c in clusters if c.label.startswith("artifact")
    )
    n_artifact_frames = sum(
        c.length for c in clusters if c.label.startswith("artifact")
    )
    diagnostics = _PrecleanDiagnostics(
        clusters=clusters,
        n_artifact_clusters=n_artifact_clusters,
        n_artifact_frames=n_artifact_frames,
        n_interp_wiped=n_interp_wiped,
        n_frame_outliers=n_frame_outliers,
        n_pchip_extended=n_pchip_extended,
        n_x_hard_outliers=int(x_hard_outlier_mask.sum()),
        n_x_joint_outliers=int(x_joint_outlier_mask.sum()),
        n_x_pchip_extended=int(x_extend_mask.sum()),
        x0_baseline_fill=x0,
    )
    return y_clean, x_clean, is_base_clean, diagnostics


# ---------------------------------------------------------------------------
# Y-side helpers
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
    high_thr = float(params["high_thr_px"])
    shape_low_thr = float(params["shape_low_thr_px"])
    shape_range_thr = float(params["shape_range_thr_px"])
    isolated_max_n = int(params["isolated_max_n"])
    flat_min_len = int(params["flat_min_len"])
    flat_max_range = float(params["flat_max_range_px"])
    flat_min_y = float(params["flat_min_y_px"])
    nbrhd_radius = max(1, int(round(
        float(params["nbrhd_radius_ms"]) / 1000.0 * fps,
    )))
    isolated_radius = max(1, int(round(
        float(params["isolated_radius_ms"]) / 1000.0 * fps,
    )))

    raw_mask = (~is_interp_fill) & (~is_baseline_fill) & np.isfinite(y)
    # Non-base = NOT baseline-fill (raw + PCHIP-interp count as non-base)
    non_base_mask = (~is_baseline_fill) & np.isfinite(y)

    clusters: list[_RawCluster] = []
    i = 0
    while i < n_frames:
        if not raw_mask[i]:
            i += 1
            continue
        j = i
        while j < n_frames and raw_mask[j]:
            j += 1
        # Cluster spans [i, j)
        cluster_y = y[i:j]
        n = j - i
        y_max = float(np.max(cluster_y))
        y_min = float(np.min(cluster_y))
        y_median = float(np.median(cluster_y))
        y_range = y_max - y_min

        label = "keep_low"
        if y_max >= high_thr:
            # Rule A: intra-cluster shape
            rule_A = (y_min < shape_low_thr) or (y_range > shape_range_thr)
            # Rule B1: immediate non-base neighbor
            left_connected = (i > 0) and bool(non_base_mask[i - 1])
            right_connected = (j < n_frames) and bool(non_base_mask[j])
            rule_B1 = left_connected or right_connected
            # Rule B2: any non-base frame in ±nbrhd with y < HIGH_THR (outside cluster)
            nlo = max(0, i - nbrhd_radius)
            nhi = min(n_frames, j + nbrhd_radius)
            nbrhd_nb = non_base_mask[nlo:nhi].copy()
            nbrhd_nb[(i - nlo):(j - nlo)] = False  # exclude self
            nbrhd_y = y[nlo:nhi]
            rule_B2 = bool((nbrhd_nb & (nbrhd_y < high_thr)).any())
            rule_B = rule_B1 and rule_B2

            if rule_A or rule_B:
                label = (
                    f"keep_real (A={int(rule_A)} "
                    f"B1={int(rule_B1)} B2={int(rule_B2)})"
                )
            else:
                label = (
                    f"artifact_narrow max={y_max:.0f} min={y_min:.0f} "
                    f"range={y_range:.0f} n={n} "
                    f"B1={int(rule_B1)} B2={int(rule_B2)}"
                )

            # Isolated-short override (Decision 11): short cluster with
            # no other raw cluster within ±isolated_radius
            if n <= isolated_max_n:
                iso_lo = max(0, i - isolated_radius)
                iso_hi = min(n_frames, j + isolated_radius)
                other_raw = raw_mask[iso_lo:iso_hi].copy()
                other_raw[(i - iso_lo):(j - iso_lo)] = False
                if not bool(other_raw.any()):
                    label = (
                        f"artifact_isolated_short max={y_max:.0f} n={n}"
                    )

        # Belt-and-suspenders long flat plateau
        if (n >= flat_min_len
            and y_range < flat_max_range
            and y_median > flat_min_y):
            label = f"artifact_flat n={n} range={y_range:.1f}"

        clusters.append(_RawCluster(
            lo=i, hi=j - 1, length=n,
            y_min=y_min, y_max=y_max, y_median=y_median, y_range=y_range,
            label=label,
        ))
        i = j

    return clusters


def _find_y_frame_outliers(
    y_clean: np.ndarray, clusters: list[_RawCluster], n_frames: int,
    fps: float, *, params: dict[str, Any],
) -> list[int]:
    """Step 1b — frame-level y outlier check (Decision 12).

    Within each NON-artifact cluster, finds frames where
    ``|y - local_median| > frame_jump_thr_px`` (local median computed
    over ±frame_radius_ms within the same cluster). Returns the list of
    seed frame indices to wipe. Direct port of scratch lines 267-303.
    """
    frame_jump_thr = float(params["frame_jump_thr_px"])
    frame_radius = max(2, int(round(
        float(params["frame_radius_ms"]) / 1000.0 * fps,
    )))

    seeds: list[int] = []
    for c in clusters:
        if c.label.startswith("artifact"):
            continue
        lo, hi = c.lo, c.hi
        for k in range(lo, hi + 1):
            klo = max(lo, k - frame_radius)
            khi = min(hi + 1, k + frame_radius + 1)
            others = [
                y_clean[kk] for kk in range(klo, khi)
                if kk != k and np.isfinite(y_clean[kk])
            ]
            if len(others) < 3:
                continue
            local_median = float(np.median(others))
            if abs(float(y_clean[k]) - local_median) > frame_jump_thr:
                seeds.append(k)
    return seeds


def _extend_pchip_around_range(
    lo: int, hi: int,
    y_clean: np.ndarray, is_base_clean: np.ndarray, is_interp_fill: np.ndarray,
    n_frames: int, pchip_extend: int,
) -> int:
    """Step 1d helper — walk left from ``lo - 1`` and right from
    ``hi + 1`` into is_intp frames, wiping each (y=0, is_base=True) up
    to ``pchip_extend`` frames per side or until a non-interp or
    already-wiped frame is hit. Mutates y_clean + is_base_clean in
    place. Returns the count of frames newly wiped.

    Used by both Step 1c (cluster wipe) and Step 1b (frame outlier
    wipe). For single-frame seed, call with lo == hi.
    """
    n_extended = 0
    # Walk left
    k = lo - 1
    cnt = 0
    while (k >= 0 and is_interp_fill[k] and not is_base_clean[k]
           and cnt < pchip_extend):
        y_clean[k] = 0.0
        is_base_clean[k] = True
        n_extended += 1
        k -= 1
        cnt += 1
    # Walk right
    k = hi + 1
    cnt = 0
    while (k < n_frames and is_interp_fill[k] and not is_base_clean[k]
           and cnt < pchip_extend):
        y_clean[k] = 0.0
        is_base_clean[k] = True
        n_extended += 1
        k += 1
        cnt += 1
    return n_extended


def _wipe_bracketed_interp(
    y_clean: np.ndarray, is_interp_fill: np.ndarray,
    is_base_clean: np.ndarray, n_frames: int,
) -> int:
    """Step 1e — wipe any is_intp run bracketed by wiped/baseline-fill
    on BOTH sides. Mutates y_clean + is_base_clean in place. Returns
    the count of frames newly wiped. Direct port of scratch lines
    305-321.
    """
    n_wiped = 0
    i = 0
    while i < n_frames:
        if is_interp_fill[i] and not is_base_clean[i]:
            j = i
            while j < n_frames and is_interp_fill[j] and not is_base_clean[j]:
                j += 1
            left_wiped = (i == 0) or bool(is_base_clean[i - 1])
            right_wiped = (j >= n_frames) or bool(is_base_clean[j])
            if left_wiped and right_wiped:
                y_clean[i:j] = 0.0
                is_base_clean[i:j] = True
                n_wiped += (j - i)
            i = j
        else:
            i += 1
    return n_wiped


# ---------------------------------------------------------------------------
# X-side helpers (Addendum #1 Rules 1-4)
# ---------------------------------------------------------------------------


def _derive_x0_baseline_fill(
    x: np.ndarray, is_baseline_fill_orig: np.ndarray,
) -> float:
    """Addendum #1 Rule 1 helper — derive x0 from Phase 7a.2's stage-5
    baseline-fill convention.

    ``x0 = median(x[is_baseline_fill_orig])`` if any baseline-fill frames
    exist with finite values, else ``0.0``.
    """
    if not is_baseline_fill_orig.any():
        return 0.0
    vals = x[is_baseline_fill_orig]
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return 0.0
    return float(np.median(vals))


def _find_x_isolated_jumps(
    x: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill_clean: np.ndarray,
    n_frames: int, x0: float, *, params: dict[str, Any],
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

    Ported from ``.scratch_phase_7e/visualize_x_imputation.py:find_x_isolated_jumps``.
    """
    jump_thr = float(params["x_jump_thr_px"])
    max_flank_distance = int(params["x_flank_max_distance"])

    raw_mask = (~is_interp_fill) & (~is_baseline_fill_clean) & np.isfinite(x)
    flag = np.zeros(n_frames, dtype=bool)
    for i in range(n_frames):
        if not raw_mask[i]:
            continue
        # Nearest RAW flank to the left
        left_idx = -1
        for d in range(1, max_flank_distance + 1):
            k = i - d
            if k < 0:
                break
            if raw_mask[k]:
                left_idx = k
                break
        if left_idx < 0:
            continue
        # Nearest RAW flank to the right
        right_idx = -1
        for d in range(1, max_flank_distance + 1):
            k = i + d
            if k >= n_frames:
                break
            if raw_mask[k]:
                right_idx = k
                break
        if right_idx < 0:
            continue
        x_left = float(x[left_idx])
        x_right = float(x[right_idx])
        x_curr = float(x[i])
        if abs(x_curr - x_left) <= jump_thr:
            continue
        if abs(x_curr - x_right) <= jump_thr:
            continue
        if abs(x_curr - x0) >= min(abs(x_left - x0), abs(x_right - x0)):
            continue
        flag[i] = True
    return flag


def _clean_x_trace(
    x: np.ndarray, is_interp_fill: np.ndarray,
    is_baseline_fill_clean: np.ndarray, is_baseline_fill_orig: np.ndarray,
    n_frames: int, fps: float, *, params: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Addendum #1 Rules 1-4 — full x-side pre-clean.

    Applies x0 baseline-fill (Rule 1), drops y-wiped frames from anchor
    set (Rule 2 — built into raw_mask via is_base_clean), wipes
    |x|>x_abs_max_px frames + PCHIP-extend (Rule 3), and runs the joint
    x+y short-burst detector (Rule 4). Returns:

      x_clean, x_hard_outlier_mask, x_joint_outlier_mask,
      x_extend_mask, is_baseline_fill_clean_augmented, x0

    The ``is_baseline_fill_clean_augmented`` mask includes the x_joint_-
    outlier frames so the caller (:func:`preclean_trace`) can also wipe
    y at those frames before the detector runs.

    Ported from ``.scratch_phase_7e/visualize_x_imputation.py:clean_x_trace``.
    """
    x_abs_max = float(params["x_abs_max_px"])
    pchip_extend = max(2, int(round(
        float(params["x_pchip_extend_ms"]) / 1000.0 * fps,
    )))

    # Rule 1 helper: derive x0 from ORIGINAL baseline-fill convention.
    x0 = _derive_x0_baseline_fill(x, is_baseline_fill_orig)

    # Raw-mask uses is_base_clean (post y pre-clean) → Rule 2 (y-wiped
    # frames excluded from x anchor set) is automatic.
    raw_mask = (~is_interp_fill) & (~is_baseline_fill_clean) & np.isfinite(x)

    # Rule 3: hard biological bound
    x_hard_outlier_mask = raw_mask & (np.abs(x) > x_abs_max)

    # Rule 4: direction-aware nearest-raw-flank check
    x_joint_outlier_mask = _find_x_isolated_jumps(
        x, is_interp_fill, is_baseline_fill_clean, n_frames, x0,
        params=params,
    )
    x_joint_outlier_mask &= ~x_hard_outlier_mask  # don't double-count

    # PCHIP-extend wipe — HARD outliers only (joint outliers are
    # localized; their immediate is_intp neighbors are not necessarily
    # tainted because the burst is brief).
    x_extend_mask = np.zeros(n_frames, dtype=bool)
    for i in np.where(x_hard_outlier_mask)[0]:
        # Walk left
        k = i - 1
        cnt = 0
        while (k >= 0 and is_interp_fill[k] and not is_baseline_fill_clean[k]
               and cnt < pchip_extend):
            x_extend_mask[k] = True
            k -= 1
            cnt += 1
        # Walk right
        k = i + 1
        cnt = 0
        while (k < n_frames and is_interp_fill[k]
               and not is_baseline_fill_clean[k]
               and cnt < pchip_extend):
            x_extend_mask[k] = True
            k += 1
            cnt += 1

    # Anchor set: raw frames not in any x outlier mask
    anchor_mask = raw_mask & (~x_hard_outlier_mask) & (~x_joint_outlier_mask)
    anchor_idx = np.where(anchor_mask)[0]

    x_clean = np.full(n_frames, np.nan, dtype=np.float64)
    x_clean[anchor_idx] = x[anchor_idx]

    # Augmented base_clean = original y-side base_clean + joint x+y
    # outliers. Caller uses this to wipe y at joint outlier frames too
    # (Rule 4 production-port requirement).
    is_base_clean_augmented = is_baseline_fill_clean | x_joint_outlier_mask

    # Rule 1: x = x0 ONLY at y-side base_clean frames (whole-cluster wipes
    # + Phase 7a.2 baseline-fill). NOT at joint outliers (those get
    # PCHIP-interp below — the burst sits inside an otherwise-real lick,
    # snapping to x0 would create a visible discontinuity).
    x_clean[is_baseline_fill_clean] = x0

    # Rule 4 re-interp + Rule 3 re-interp: at is_intp non-base frames,
    # hard outliers, and joint outliers (inside anchor range), evaluate
    # PCHIP through the outlier-excluded anchor set.
    if len(anchor_idx) >= 4:
        pchip = PchipInterpolator(
            anchor_idx.astype(float), x[anchor_idx],
            extrapolate=False,
        )
        interp_mask = (
            (is_interp_fill & (~is_baseline_fill_clean))
            | x_hard_outlier_mask
            | x_joint_outlier_mask
        )
        idx_to_eval = np.where(interp_mask)[0]
        if len(idx_to_eval):
            vals = pchip(idx_to_eval.astype(float))
            finite = np.isfinite(vals)
            x_clean[idx_to_eval[finite]] = vals[finite]

    return (
        x_clean, x_hard_outlier_mask, x_joint_outlier_mask,
        x_extend_mask, is_base_clean_augmented, x0,
    )
