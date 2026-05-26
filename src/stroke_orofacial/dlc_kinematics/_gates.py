"""Phase 7e — v7 post-detection gates F/D/E/M + imputation.

Ports the v7 gates from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 529-664
+ M-gate loop at 784-830). Plus Addendum #1 Rule 5 (early-window M-gate
relaxation, integrated INTO ``run_m_gate`` per the addendum spec —
scratch ref at
``.scratch_phase_7e/visualize_x_imputation.py:relax_m_gate_early_window``).

This module is the canonical Stage 3 gate runner that runs AFTER the
detector (:mod:`._detector_v2`) and emits the final keep/reject
decisions + optional per-peak imputation (E gate spline/parabolic).

Gates (per-peak, in order):

  F — within-peak raw std. Rejects plateau-shaped peaks where
    ``std(raw y in ±f_wp_win_ms) < f_wp_std_thr``.
  D — left/right low context. Rejects peaks lacking baseline-fill or
    raw low-y context within ±d_win_ms.
  E — outlier z-vs-peers + imputation. Runs ONLY for the first un-
    promoted peak (Decision 17). If ``z > e_z_thr`` AND ``lik <
    e_lik_override``, tries :func:`parabolic_excise` first (concave-
    down vertex; Decision 16), falls back to :func:`spline_excise`
    (PCHIP through ±spline_anchor_win_ms anchors with outlier window
    excluded). Imputed peak_y + new_peak_frame replace the original.

  M — confidence-based inter-lick interval (Decision 2 + Addendum #1
    Rule 5). For each pair of consecutive KEPT peaks within
    ``m_min_interval_ms`` (80 ms), drop the LOWER-CONFIDENCE peak
    (#raw_frames in ±m_conf_radius_ms × mean_likelihood). Higher-y
    tiebreaker. Iterate until no more close-pair conflicts.

    **Addendum #1 Rule 5:** inside the first ``m_early_win_ms`` (250 ms)
    post-tone, the interval threshold is relaxed to
    ``m_early_interval_ms`` (60 ms). Preserves close-paired first licks
    (PS54 76L rescue case) — first-lick coordinates are critical for
    downstream analyses.

All numeric constants from ``configs/defaults.yaml:
dlc_kinematics.tongue_pertrial.gates`` (no magic numbers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.interpolate import PchipInterpolator


@dataclass
class LickEventRecord:
    """One row of the per-trial-per-lick ``lick_events/`` parquet
    (Phase 7e Task 6 schema per Decision 4).

    Emitted ONCE per kept peak after all gates (F/D/E/M) run. Becomes the
    canonical source of "which licks count" for downstream consumers
    (lick_angle, tongue_velocity, etc.); the cleaned_traces parquet is
    the canonical TRACE source but does NOT encode rejection status
    (per Decision 3 amendment in Addendum #1).

    Schema:
      - ``animal, date, trial, side, lick_idx``: session + lick identity
      - ``t_ms``: peak time relative to tone (ms post-tone)
      - ``y, x``: peak coordinates (post pre-clean; imputed if E fired)
      - ``y_original``: pre-imputation y (NaN if not imputed) — preserved
        so downstream can detect imputation events
      - ``rise_start_ms, fall_end_ms``: lick rise/fall boundaries (ms
        post-tone) — feeds tongue_velocity per-kept-lick gating per
        Decision 5
      - ``imputed``: True if E gate fired and y was replaced via
        parabolic/spline excise
      - ``source``: which detector emitted the original peak —
        ``"lmax"``, ``"bounded"``, or ``"legacy"`` (Decision 14)
      - ``confidence``: M-gate confidence at this peak (Decision 2)
      - ``likelihood``: raw DLC likelihood at the peak frame
    """

    animal: str
    date: str               # ISO format YYYY-MM-DD
    trial: int
    side: str               # "L" | "R"
    lick_idx: int           # 0-based within trial
    t_ms: float
    y: float
    x: float
    y_original: float       # NaN if not imputed
    rise_start_ms: float
    fall_end_ms: float
    imputed: bool
    source: str             # "lmax" | "bounded" | "legacy"
    confidence: float
    likelihood: float
    # Phase 7e Task 7 additions per Decisions 5 + 6.
    # peak_angle_deg: signed lick angle at the (imputed) peak frame, computed
    #   from cleaned (x, y) relative to the session's eye-in-spout-frame
    #   origin. Consumes Task 5b's imputed x (LickEventRecord.x is already
    #   the post-Task-5b x_imputed for imputed licks).
    # max_velocity_y_px_per_s: max dy/dt inside the kept lick's
    #   [rise_start_frame, fall_end_frame] window, with is_baseline_fill=True
    #   frames masked. Computed from the cleaned y trace (per Decision 5).
    peak_angle_deg: float = float("nan")
    max_velocity_y_px_per_s: float = float("nan")


# ---------------------------------------------------------------------------
# F gate — within-peak raw std (Decision 1, Stage 3)
# ---------------------------------------------------------------------------


def gate_F(
    y: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> tuple[bool, str, float]:
    """Within-peak raw-y std check.

    Returns ``(reject, reason, std_raw)``. Rejects if
    ``std(raw y in ±f_wp_win_ms) < f_wp_std_thr`` (plateau-shaped
    peak). Direct port of scratch lines 529-540.

    Reject codes:
      - ``"F_too_few_raw n=<count>"`` — fewer than ``f_k_min_raw`` raw
        frames in the window (can't compute std reliably).
      - ``"F_raw_flat std=<value>"`` — std below threshold.
    """
    win_ms = float(params["f_wp_win_ms"])
    std_thr = float(params["f_wp_std_thr"])
    k_min_raw = int(params["f_k_min_raw"])

    win_frames = int(round(win_ms / 1000.0 * fps))
    lo = max(0, peak_frame - win_frames)
    hi = min(n_frames, peak_frame + win_frames + 1)
    y_w = y[lo:hi]
    raw_mask = (~is_interp_fill[lo:hi]) & (~is_baseline_fill[lo:hi]) & np.isfinite(y_w)
    raw_y = y_w[raw_mask]
    if len(raw_y) < k_min_raw:
        return True, f"F_too_few_raw n={len(raw_y)}", float("nan")
    std_raw = float(np.std(raw_y))
    if std_raw < std_thr:
        return True, f"F_raw_flat std={std_raw:.2f}", std_raw
    return False, "", std_raw


# ---------------------------------------------------------------------------
# D gate — left/right low context (Decision 1, Stage 3)
# ---------------------------------------------------------------------------


def gate_D(
    y: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> tuple[bool, str]:
    """Left/right low-context check.

    Returns ``(keep, reason)``. Note inverted convention vs gate_F: True
    here means KEEP. Direct port of scratch lines 543-555.

    Requires both ±d_win_ms windows around the peak to contain either:
      - a raw frame with ``y < d_y_thr_px`` (real baseline / rise context), OR
      - a baseline-fill frame

    Reject codes:
      - ``"D_left"`` — left context missing
      - ``"D_right"`` — right context missing

    ``d_y_thr_px`` matches ``preclean.high_thr_px`` by design
    (Decision 10).
    """
    win_ms = float(params["d_win_ms"])
    y_thr = float(params["d_y_thr_px"])

    win_frames = int(round(win_ms / 1000.0 * fps))
    lo = max(0, peak_frame - win_frames)
    hi = min(n_frames, peak_frame + win_frames + 1)
    y_w = y[lo:hi]
    is_intp_w = is_interp_fill[lo:hi]
    is_base_w = is_baseline_fill[lo:hi]
    raw_mask = (~is_intp_w) & (~is_base_w) & np.isfinite(y_w)
    pi = peak_frame - lo
    left_ok = (
        bool((raw_mask[:pi] & (y_w[:pi] < y_thr)).any())
        or bool(is_base_w[:pi].any())
    )
    right_ok = (
        bool((raw_mask[pi + 1:] & (y_w[pi + 1:] < y_thr)).any())
        or bool(is_base_w[pi + 1:].any())
    )
    if left_ok and right_ok:
        return True, ""
    if not left_ok:
        return False, "D_left"
    return False, "D_right"


# ---------------------------------------------------------------------------
# E gate — outlier z-vs-peers (Decision 1, Stage 3 + Decision 17)
# ---------------------------------------------------------------------------


def gate_E(
    candidate_y: float, candidate_lik: float, peer_ys: list[float],
    *, params: dict[str, Any],
) -> tuple[bool, str, float, float]:
    """Outlier z-vs-peers check.

    Returns ``(reject, reason, z, peer_median)``. Direct port of scratch
    lines 558-570.

    Rejects if ``z > e_z_thr`` AND ``candidate_lik < e_lik_override``.
    The likelihood escape hatch (`e_lik_override`) prevents flagging
    high-confidence outliers (real licks that happen to be tall).

    Abstain codes (returns (False, ...)):
      - ``"abstain_few_peers"`` — fewer than e_k_min_peers finite peer ys
      - ``"abstain_stationary"`` — peer MAD too small to estimate z

    Caller (per Decision 17) applies E only to the first un-promoted
    peak per trial.
    """
    z_thr = float(params["e_z_thr"])
    lik_override = float(params["e_lik_override"])
    k_min = int(params["e_k_min_peers"])

    peers = [yp for yp in peer_ys if np.isfinite(yp)]
    if len(peers) < k_min:
        return False, "abstain_few_peers", float("nan"), float("nan")
    median = float(np.median(peers))
    mad = float(np.median(np.abs(np.array(peers) - median)))
    robust_std = 1.4826 * mad
    if robust_std < 0.5:
        return False, "abstain_stationary", float("nan"), median
    z = (candidate_y - median) / robust_std
    if z > z_thr and candidate_lik < lik_override:
        return True, f"E_outlier z={z:.2f}", z, median
    return False, "", z, median


# ---------------------------------------------------------------------------
# Imputation — parabolic / spline excise (Decision 16)
# ---------------------------------------------------------------------------


def _compute_imputed_x(
    x: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    outlier_peak_frame: int, new_peak_frame: int,
    n_frames: int, fps: float, *, params: dict[str, Any],
) -> float:
    """Task 5b: compute x at the imputed peak frame via PCHIP through
    wide x anchors, with the ±x_outlier_excise_ms window around
    ``outlier_peak_frame`` excluded.

    Mirrors the audit's ``local_pchip_x(exclude_outlier_window=True)``
    used in the visualization audit
    (``.scratch_phase_7e/visualize_x_imputation.py``). Returns NaN if
    the anchor set is too sparse to fit a PCHIP, in which case the
    caller falls back to ``cleaned_x[new_peak_frame]``.

    Used by :func:`parabolic_excise` and :func:`spline_excise` to
    produce the ``new_peak_x`` return field. Catches the PS54 46L
    case where trace-level Rule 2/4 can't reach past the is_intp
    frames around the raw outlier — the imputation step excises the
    outlier window explicitly here, matching the audit-derived value.
    """
    excise_radius_ms = float(params["x_outlier_excise_ms"])
    anchor_win_ms = float(params["spline_anchor_win_ms"])
    min_anchors = int(params["spline_min_anchors"])

    excise_radius = max(1, int(round(excise_radius_ms / 1000.0 * fps)))
    anchor_radius = max(4, int(round(anchor_win_ms / 1000.0 * fps)))

    lo_out = max(0, outlier_peak_frame - excise_radius)
    hi_out = min(n_frames, outlier_peak_frame + excise_radius + 1)
    a_lo = max(0, outlier_peak_frame - anchor_radius)
    a_hi = min(n_frames, outlier_peak_frame + anchor_radius + 1)

    raw_mask = (~is_interp_fill) & (~is_baseline_fill) & np.isfinite(x)
    candidate_anchor = raw_mask.copy()
    candidate_anchor[lo_out:hi_out] = False  # excise outlier window
    window_mask = np.zeros(n_frames, dtype=bool)
    window_mask[a_lo:a_hi] = True
    anchor_mask = candidate_anchor & window_mask
    anchor_idx = np.where(anchor_mask)[0]

    if len(anchor_idx) < min_anchors:
        return float("nan")
    if not (
        (anchor_idx < outlier_peak_frame).any()
        and (anchor_idx > outlier_peak_frame).any()
    ):
        return float("nan")
    if new_peak_frame < anchor_idx.min() or new_peak_frame > anchor_idx.max():
        return float("nan")
    try:
        pchip = PchipInterpolator(
            anchor_idx.astype(float), x[anchor_idx], extrapolate=False,
        )
    except Exception:  # pragma: no cover  # noqa: BLE001
        return float("nan")
    val = float(pchip(float(new_peak_frame)))
    if not np.isfinite(val):
        return float("nan")
    return val


def parabolic_excise(
    y: np.ndarray, x: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    outlier_peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> dict[str, Any] | None:
    """Quadratic-fit imputation for E-rejected peaks (Decision 16).

    Fits a quadratic to ±parabolic_tight_radius_ms anchors around the
    outlier (excluding the outlier window). If concave-down with vertex
    in window, returns
    ``{new_peak_y, new_peak_x, new_peak_frame, interp_y, outlier_lo,
      outlier_hi, method="parabolic"}``. Else returns None (caller falls
    back to :func:`spline_excise`).

    **Task 5b correction of Decision 6** (see Addendum #1 footer): also
    computes ``new_peak_x`` via PCHIP through wide x anchors
    (±spline_anchor_win_ms, same as y-side fallback) with the outlier
    excise window (±x_outlier_excise_ms around ``outlier_peak_frame``)
    excluded. This catches the PS54 46L case where the raw outlier sits
    on a frame whose neighbors are ``is_intp=True`` (PCHIP-fill that the
    outlier itself anchored) — trace-level Rule 2/4 can't see past the
    is_intp frames to drop the raw outlier from x's anchor set, so the
    imputation step does it explicitly.

    Direct port of scratch lines 573-617 + Task 5b x extension.
    """
    tight_radius_ms = float(params["parabolic_tight_radius_ms"])
    min_anchors = int(params["parabolic_min_anchors"])
    excise_radius_ms = float(params["spline_excise_radius_ms"])

    tight_radius = max(2, int(round(tight_radius_ms / 1000.0 * fps)))
    excise_radius = max(1, int(round(excise_radius_ms / 1000.0 * fps)))
    lo_out = max(0, outlier_peak_frame - excise_radius)
    hi_out = min(n_frames, outlier_peak_frame + excise_radius + 1)
    a_lo = max(0, outlier_peak_frame - tight_radius)
    a_hi = min(n_frames, outlier_peak_frame + tight_radius + 1)

    raw_mask = (~is_interp_fill) & (~is_baseline_fill) & np.isfinite(y)
    candidate_anchor = raw_mask.copy()
    candidate_anchor[lo_out:hi_out] = False
    window_mask = np.zeros(n_frames, dtype=bool)
    window_mask[a_lo:a_hi] = True
    anchor_mask = candidate_anchor & window_mask
    anchor_idx = np.where(anchor_mask)[0]

    if len(anchor_idx) < min_anchors:
        return None
    if not (
        (anchor_idx < outlier_peak_frame).any()
        and (anchor_idx > outlier_peak_frame).any()
    ):
        return None

    x_a = anchor_idx.astype(float)
    y_a = y[anchor_idx]
    try:
        coef = np.polyfit(x_a, y_a, 2)
    except Exception:  # pragma: no cover  # noqa: BLE001
        return None

    a, b, c = float(coef[0]), float(coef[1]), float(coef[2])
    if a >= 0:  # not concave down → not a peak
        return None
    vx = -b / (2.0 * a)
    if not (a_lo <= vx <= a_hi - 1):
        return None

    vy = a * vx * vx + b * vx + c
    new_peak_frame = int(round(vx))
    new_peak_y = float(vy)
    eval_x = np.arange(lo_out, hi_out, dtype=float)
    interp_y = a * eval_x ** 2 + b * eval_x + c
    # Task 5b: x at new_peak_frame via wide-anchor PCHIP with the outlier
    # excise window excluded — matches the audit's local_pchip_x logic.
    new_peak_x = _compute_imputed_x(
        x, is_interp_fill, is_baseline_fill,
        outlier_peak_frame=outlier_peak_frame,
        new_peak_frame=new_peak_frame,
        n_frames=n_frames, fps=fps, params=params,
    )
    return dict(
        new_peak_y=new_peak_y, new_peak_x=new_peak_x,
        new_peak_frame=new_peak_frame,
        interp_y=interp_y, outlier_lo=lo_out, outlier_hi=hi_out,
        method="parabolic",
    )


def spline_excise(
    y: np.ndarray, x: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    outlier_peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> dict[str, Any] | None:
    """PCHIP-fit imputation for E-rejected peaks (Decision 16 fallback).

    Builds PCHIP through ±spline_anchor_win_ms raw anchors with the
    outlier excise window excluded; finds the max y in
    ±spline_local_max_win_ms window. Returns
    ``{new_peak_y, new_peak_x, new_peak_frame, interp_y, outlier_lo,
      outlier_hi}``. Returns None if too few anchors.

    **Task 5b correction:** also computes ``new_peak_x`` via wide-anchor
    PCHIP with ±x_outlier_excise_ms window excluded (see
    :func:`parabolic_excise` docstring for full rationale).

    Direct port of scratch lines 620-663 + Task 5b x extension.
    """
    excise_radius_ms = float(params["spline_excise_radius_ms"])
    anchor_win_ms = float(params["spline_anchor_win_ms"])
    local_max_win_ms = float(params["spline_local_max_win_ms"])
    min_anchors = int(params["spline_min_anchors"])

    excise_radius = max(1, int(round(excise_radius_ms / 1000.0 * fps)))
    anchor_radius = max(4, int(round(anchor_win_ms / 1000.0 * fps)))
    local_max_radius = max(2, int(round(local_max_win_ms / 1000.0 * fps)))

    lo_out = max(0, outlier_peak_frame - excise_radius)
    hi_out = min(n_frames, outlier_peak_frame + excise_radius + 1)
    a_lo = max(0, outlier_peak_frame - anchor_radius)
    a_hi = min(n_frames, outlier_peak_frame + anchor_radius + 1)

    raw_mask = (~is_interp_fill) & (~is_baseline_fill) & np.isfinite(y)
    candidate_anchor = raw_mask.copy()
    candidate_anchor[lo_out:hi_out] = False
    window_mask = np.zeros(n_frames, dtype=bool)
    window_mask[a_lo:a_hi] = True
    anchor_mask = candidate_anchor & window_mask
    anchor_idx = np.where(anchor_mask)[0]

    if len(anchor_idx) < min_anchors:
        return None
    if not (
        (anchor_idx < outlier_peak_frame).any()
        and (anchor_idx > outlier_peak_frame).any()
    ):
        return None

    anchor_x = anchor_idx.astype(float)
    anchor_y = y[anchor_idx]
    try:
        pchip = PchipInterpolator(anchor_x, anchor_y, extrapolate=False)
    except Exception:  # pragma: no cover  # noqa: BLE001
        return None

    eval_x = np.arange(lo_out, hi_out, dtype=float)
    interp_y = pchip(eval_x)

    lm_lo = max(0, outlier_peak_frame - local_max_radius)
    lm_hi = min(n_frames, outlier_peak_frame + local_max_radius + 1)
    eval_x_lm = np.arange(lm_lo, lm_hi, dtype=float)
    cleaned_lm = pchip(eval_x_lm)
    valid = np.isfinite(cleaned_lm)
    in_kept = np.array([
        raw_mask[idx] and not (lo_out <= idx < hi_out)
        for idx in range(lm_lo, lm_hi)
    ])
    all_vals = np.full(lm_hi - lm_lo, -np.inf)
    all_vals[valid] = cleaned_lm[valid]
    for j_local, idx in enumerate(range(lm_lo, lm_hi)):
        if in_kept[j_local]:
            all_vals[j_local] = max(all_vals[j_local], y[idx])
    if not np.any(np.isfinite(all_vals)):
        return None

    new_peak_y = float(np.max(all_vals))
    new_peak_local = int(np.argmax(all_vals))
    new_peak_frame = lm_lo + new_peak_local
    # Task 5b: x at new_peak_frame via wide-anchor PCHIP with the outlier
    # excise window excluded — matches the audit's local_pchip_x logic.
    new_peak_x = _compute_imputed_x(
        x, is_interp_fill, is_baseline_fill,
        outlier_peak_frame=outlier_peak_frame,
        new_peak_frame=new_peak_frame,
        n_frames=n_frames, fps=fps, params=params,
    )
    return dict(
        new_peak_y=new_peak_y, new_peak_x=new_peak_x,
        new_peak_frame=new_peak_frame,
        interp_y=interp_y, outlier_lo=lo_out, outlier_hi=hi_out,
    )


# ---------------------------------------------------------------------------
# M gate — confidence-based inter-lick interval + Addendum #1 Rule 5
# ---------------------------------------------------------------------------


def _peak_confidence(
    peak_frame: int, likelihood: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    n_frames: int, conf_radius: int,
) -> float:
    """Confidence = #raw_frames in ±conf_radius × mean_likelihood of those.

    Returns 0.0 if no raw frames in window. Direct port of the scratch's
    ``_peak_confidence`` closure inside ``evaluate_trial``.
    """
    lo = max(0, peak_frame - conf_radius)
    hi = min(n_frames, peak_frame + conf_radius + 1)
    raw_in_win = (~is_interp_fill[lo:hi]) & (~is_baseline_fill[lo:hi])
    n_raw = int(raw_in_win.sum())
    if n_raw == 0:
        return 0.0
    mean_lik = float(np.mean(likelihood[lo:hi][raw_in_win]))
    return n_raw * mean_lik


def run_m_gate(
    decisions: list[dict[str, Any]],
    y: np.ndarray, likelihood: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    n_frames: int, fps: float,
    promoted: dict[str, Any] | None,
    *, params: dict[str, Any],
) -> dict[str, Any] | None:
    """M-gate loop with Addendum #1 early-window relaxation (Rule 5).

    For each pair of consecutive KEPT peaks within the inter-lick
    interval threshold, drops the LOWER-CONFIDENCE peak (confidence =
    #raw_frames in ±m_conf_radius_ms × mean_likelihood; higher-y
    tiebreaker). Iterates until no more close-pair conflicts.

    **Rule 5 — early-window relaxation:** the interval threshold is

      - ``m_early_interval_ms`` (60 ms) if BOTH peaks have ``t_ms <
        m_early_win_ms`` (250 ms post-tone)
      - ``m_min_interval_ms`` (80 ms) otherwise (Decision 2 default)

    Mutates the ``decisions`` list in place; returns the (possibly
    updated) ``promoted`` peak.

    Direct port of scratch lines 784-830 + Addendum #1 early-window
    threshold inside the close-pair check.
    """
    m_min = float(params["m_min_interval_ms"])
    m_early_int = float(params["m_early_interval_ms"])
    m_early_win = float(params["m_early_win_ms"])
    conf_radius_ms = float(params["m_conf_radius_ms"])
    conf_radius = max(1, int(round(conf_radius_ms / 1000.0 * fps)))

    def _interval_threshold(t1_ms: float, t2_ms: float) -> float:
        """Rule 5: relaxed 60 ms if both peaks in early window, else 80 ms."""
        if t1_ms < m_early_win and t2_ms < m_early_win:
            return m_early_int
        return m_min

    while True:
        kept_decs = [d for d in decisions if d["keep"]]
        kept_decs.sort(key=lambda d: d["t_ms"])
        merged = False
        for i in range(len(kept_decs) - 1):
            d1, d2 = kept_decs[i], kept_decs[i + 1]
            threshold = _interval_threshold(d1["t_ms"], d2["t_ms"])
            if d2["t_ms"] - d1["t_ms"] < threshold:
                c1 = _peak_confidence(
                    d1["peak_frame_local"], likelihood,
                    is_interp_fill, is_baseline_fill,
                    n_frames, conf_radius,
                )
                c2 = _peak_confidence(
                    d2["peak_frame_local"], likelihood,
                    is_interp_fill, is_baseline_fill,
                    n_frames, conf_radius,
                )
                # Higher confidence wins; tiebreak by higher y
                if c1 < c2:
                    loser = d1
                elif c2 < c1:
                    loser = d2
                else:
                    loser = d1 if d1["y"] < d2["y"] else d2
                loser["keep"] = False
                loser["reason"] = (
                    f"M_close interval={d2['t_ms'] - d1['t_ms']:.0f}ms "
                    f"thr={threshold:.0f}ms c1={c1:.2f} c2={c2:.2f} "
                    f"drop_{'d1' if loser is d1 else 'd2'}"
                )
                loser["gate"] = "M"
                merged = True
                # If the loser was the promoted peak, re-promote the
                # highest-conf survivor
                if promoted is not None and loser["t_ms"] == promoted.get("t_ms"):
                    surviving = [d for d in decisions if d["keep"]]
                    surviving.sort(key=lambda d: d["t_ms"])
                    promoted = surviving[0] if surviving else None
                break
        if not merged:
            break
    return promoted
