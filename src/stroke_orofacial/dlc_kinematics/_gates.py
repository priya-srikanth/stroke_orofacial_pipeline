"""Phase 7e — v7 post-detection gates F/D/E/M + imputation (SKELETON).

Ports the v7 gates from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 529-664
+ M-gate loop at 784-830). Plus Addendum #1 Rule 5 (early-window M-gate
relaxation, scratch ref:
``.scratch_phase_7e/visualize_x_imputation.py:relax_m_gate_early_window``).

This module is the canonical Stage 3 gate runner that runs AFTER the
detector (:mod:`.detector_v2`) and emits the final keep/reject decisions
+ optional per-peak imputation (E gate spline/parabolic).

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


def gate_F(
    y: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> tuple[bool, str, float]:
    """Within-peak raw-y std check (Decision 1, Stage 3).

    Returns ``(reject, reason, std_raw)``. Direct port of scratch lines
    529-540. Rejects if ``std(raw y in ±f_wp_win_ms) < f_wp_std_thr``
    (plateau-shaped peak).
    """
    raise NotImplementedError("Port body in Phase 7e Task 4")


def gate_D(
    y: np.ndarray, is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> tuple[bool, str]:
    """Left/right low-context check (Decision 1, Stage 3).

    Returns ``(keep, reason)``. Direct port of scratch lines 543-555.
    Requires both ±d_win_ms windows to contain either a raw frame with
    ``y < d_y_thr_px`` OR a baseline-fill frame. ``d_y_thr_px`` matches
    ``preclean.high_thr_px`` by design (Decision 10).
    """
    raise NotImplementedError("Port body in Phase 7e Task 4")


def gate_E(
    candidate_y: float, candidate_lik: float, peer_ys: list[float],
    *, params: dict[str, Any],
) -> tuple[bool, str, float, float]:
    """Outlier z-vs-peers check (Decision 1, Stage 3 + Decision 17).

    Returns ``(reject, reason, z, peer_median)``. Direct port of scratch
    lines 558-570. Rejects if ``z > e_z_thr`` AND ``candidate_lik <
    e_lik_override``. Caller (per Decision 17) applies E only to the
    first un-promoted peak per trial.
    """
    raise NotImplementedError("Port body in Phase 7e Task 4")


def parabolic_excise(
    y: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    outlier_peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> dict[str, Any] | None:
    """Quadratic-fit imputation for E-rejected peaks (Decision 16).

    Fits a quadratic to ±parabolic_tight_radius_ms anchors around the
    outlier (excluding the outlier window). If concave-down with vertex
    in window, returns
    ``{new_peak_y, new_peak_frame, interp_y, outlier_lo, outlier_hi,
      method="parabolic"}``. Else returns None (caller falls back to
    :func:`spline_excise`).

    Y-only imputation; the imputed ``x`` at ``new_peak_frame`` is read
    from the post-pre-clean ``cleaned_x`` (trace-level fix per Addendum
    #1 Rules 1-4 is canonical for x — Decision 6 RESOLVED). The
    ``LickEventRecord`` builder reads ``x = cleaned_x[new_peak_frame]``
    directly; no per-peak ``new_peak_x`` field is carried.

    Direct port of scratch lines 573-617.
    """
    raise NotImplementedError("Port body in Phase 7e Task 4")


def spline_excise(
    y: np.ndarray,
    is_interp_fill: np.ndarray, is_baseline_fill: np.ndarray,
    outlier_peak_frame: int, n_frames: int, fps: float,
    *, params: dict[str, Any],
) -> dict[str, Any] | None:
    """PCHIP-fit imputation for E-rejected peaks (Decision 16 fallback).

    Builds PCHIP through ±spline_anchor_win_ms raw anchors with the
    outlier excise window excluded; finds the max y in
    ±spline_local_max_win_ms window. Returns
    ``{new_peak_y, new_peak_frame, interp_y, outlier_lo, outlier_hi}``.
    Returns None if too few anchors.

    Y-only imputation; ``x`` at ``new_peak_frame`` is read from
    ``cleaned_x`` (see :func:`parabolic_excise` docstring for the
    Addendum #1 Decision 6 RESOLVED rationale).

    Direct port of scratch lines 620-663.
    """
    raise NotImplementedError("Port body in Phase 7e Task 4")


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
    raise NotImplementedError("Port body in Phase 7e Task 4")
