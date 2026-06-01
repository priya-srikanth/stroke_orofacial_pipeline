"""Phase 9.1 Q-lock 13b + 13c — phase-aligned tongue endpoints per (trial, side).

Phase 9.1 Q-lock 13b (Addenda #1 + #2 locks, 2026-05-27) defined three
scalar endpoints derived from the first-lick-centered phase trajectory.
Q-lock 13c Stage 1 (2026-05-29) adds two y-signal analogs (D + E):

- A ``peak_angle_deg`` — tongue angle at ``phase = 0.5`` (lick-1 peak time).
- B ``signed_angle_at_max_abs_phase_0_075_deg`` — signed ``angle_deg``
  at ``argmax(|angle_deg|)`` over ``phase in [0, 0.75]`` (selection by
  magnitude; reported value signed — positive vs negative is meaningful).
- C ``signed_x_at_max_abs_phase_0_075_px`` — ``x_centered`` at the time-point
  of largest ``|x_centered|`` over ``phase in [0, 0.75]`` (selection by
  magnitude; reported value signed). Q-lock 13b Addendum #2 Q6 refinement.
- D ``peak_y_px`` — tongue y at ``phase = 0.5`` (lick-1 peak time). Q-lock
  13c Stage 1 y-analog of A.
- E ``signed_y_at_max_abs_phase_0_075_px`` — ``y_centered`` at
  ``argmax(|y_centered|)`` over ``phase in [0, 0.75]`` (selection by
  magnitude; reported value signed). Q-lock 13c Stage 1 y-analog of C.

All five endpoints share the same first-lick-centered phase substrate
(``build_first_lick_centered_phase_rows`` with ``ili_source="synthetic_only"``
per Addendum #1 Q1 lock; cycle width = the animal's pre-stroke median ILI
on ``bundle.metadata["pre_stroke_median_ili_ms"]``).

``x_centered`` and ``y_centered`` are consumed in the spout-midpoint
reference frame (Addendum #2 D2 lock + Q-lock 13c Stage 1: x = 0 =
tongue aligned with spout midline; y = 0 = tongue tip vertically aligned
with spout midpoint, positive y = protrusion; no eye-relative
re-centering applied here).

Per-trial NaN policy
--------------------
- Endpoint A: NaN if no phase row falls within ``|phase - 0.5| <= 0.05``
  (typical synthetic_only frame spacing per trial is 1/72 ≈ 0.014; 0.05
  is a generous tolerance that still rejects trials where the peak frame
  wasn't included in the centered window).
- Endpoint B: NaN if the phase ``[0, 0.75]`` window has no finite
  ``angle_deg`` rows.
- Endpoint C: NaN if the phase ``[0, 0.75]`` window has no finite
  ``x_centered`` rows.
- Endpoint D: NaN policy identical to A but on ``y_centered``.
- Endpoint E: NaN policy identical to C but on ``y_centered``.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .tongue_pertrial import (
    TongueVisualBundle,
    build_all_licks_centered_phase_rows,
    build_first_lick_centered_phase_rows,
)


# Endpoint-window constants pinned in the kickoff body + Addendum #2.
PHASE_PEAK: float = 0.5
PHASE_WINDOW_LO: float = 0.0
PHASE_WINDOW_HI: float = 0.75

# Tolerance for "frame at phase = 0.5". The synthetic_only first-lick
# window is exactly 0.5 wide on each side; a finite ``fps`` divides into
# ``n_phase_bins`` (= 72 default) so the closest frame is within
# 1/(2 * 72) ≈ 0.007 of phase = 0.5. 0.05 leaves headroom for low-fps
# or short-cycle edge cases while still rejecting "no peak frame
# present" trials.
PHASE_PEAK_TOLERANCE: float = 0.05

PHASE_ALIGNED_ENDPOINT_COLUMNS: tuple[str, ...] = (
    "trial_index",
    "side",
    "peak_angle_deg",
    "signed_angle_at_max_abs_phase_0_075_deg",
    "signed_x_at_max_abs_phase_0_075_px",
    "peak_y_px",
    "signed_y_at_max_abs_phase_0_075_px",
)


def _empty_phase_aligned_endpoints_df() -> pd.DataFrame:
    """Empty DataFrame with the expected column dtypes."""
    return pd.DataFrame({
        "trial_index": pd.Series(dtype=int),
        "side": pd.Series(dtype=object),
        "peak_angle_deg": pd.Series(dtype=float),
        "signed_angle_at_max_abs_phase_0_075_deg": pd.Series(dtype=float),
        "signed_x_at_max_abs_phase_0_075_px": pd.Series(dtype=float),
        "peak_y_px": pd.Series(dtype=float),
        "signed_y_at_max_abs_phase_0_075_px": pd.Series(dtype=float),
    })


def compute_phase_aligned_endpoints_per_trial(
    bundle: TongueVisualBundle,
    *,
    lick_set: str = "first_lick",
) -> pd.DataFrame:
    """Compute Phase 9.1 Q-lock 13b endpoints A + B + C per (trial, side).

    Parameters
    ----------
    bundle : TongueVisualBundle
        Must carry a finite ``metadata["pre_stroke_median_ili_ms"]`` for
        the ``synthetic_only`` phase-row builder to consume. Production
        bundles built by ``build_tongue_visual_bundle_by_animal_date``
        always populate this when the animal has any pre-stroke session
        on disk. Bundles without it (e.g. brand-new animals) return an
        empty result.

    Returns
    -------
    pd.DataFrame
        One row per (``trial_index``, ``side``) pair that had at least one
        emitted phase row. Columns per
        :data:`PHASE_ALIGNED_ENDPOINT_COLUMNS`. Empty DataFrame (with the
        expected columns) when no phase rows were produced.
    """
    synth = float(bundle.metadata.get("pre_stroke_median_ili_ms", float("nan")))
    if not (np.isfinite(synth) and synth > 0):
        return _empty_phase_aligned_endpoints_df()

    # ``all_multi`` (I, 2026-06-01) computes the SAME endpoints per individual
    # lick (group also by ``peak_t_ms``), pooled downstream as n=licks; the
    # default ``first_lick`` keeps the shipped per-trial first-lick grain.
    if lick_set == "all_multi":
        phase_rows = build_all_licks_centered_phase_rows(
            bundle, synthetic_ili_ms=synth, ili_source="synthetic_only",
        )
        group_keys = ["trial_index", "side", "peak_t_ms"]
    else:
        phase_rows = build_first_lick_centered_phase_rows(
            bundle, synthetic_ili_ms=synth, ili_source="synthetic_only",
        )
        group_keys = ["trial_index", "side"]
    if phase_rows.empty:
        return _empty_phase_aligned_endpoints_df()

    out_rows: list[dict[str, Any]] = []
    for key, grp in phase_rows.groupby(group_keys, sort=True):
        trial_idx, side = key[0], key[1]
        row = {
            "trial_index": int(trial_idx),
            "side": str(side),
            "peak_angle_deg": _endpoint_a_peak_angle(grp),
            "signed_angle_at_max_abs_phase_0_075_deg": _endpoint_b_max_abs_angle(grp),
            "signed_x_at_max_abs_phase_0_075_px": _endpoint_c_signed_x_at_max_abs(grp),
            "peak_y_px": _endpoint_d_peak_y(grp),
            "signed_y_at_max_abs_phase_0_075_px": _endpoint_e_signed_y_at_max_abs(grp),
        }
        if lick_set == "all_multi":
            row["peak_t_ms"] = float(key[2])
        out_rows.append(row)

    if not out_rows:
        return _empty_phase_aligned_endpoints_df()
    cols = list(PHASE_ALIGNED_ENDPOINT_COLUMNS)
    if lick_set == "all_multi":
        cols = cols + ["peak_t_ms"]
    return pd.DataFrame(out_rows, columns=cols)


def _endpoint_a_peak_angle(grp: pd.DataFrame) -> float:
    """Endpoint A: angle_deg at phase ≈ 0.5 (lick-1 peak time)."""
    if grp.empty:
        return float("nan")
    phase_arr = grp["phase"].to_numpy(dtype=np.float64)
    angle_arr = grp["angle_deg"].to_numpy(dtype=np.float64)
    deltas = np.abs(phase_arr - PHASE_PEAK)
    finite_angle = np.isfinite(angle_arr)
    deltas = np.where(finite_angle, deltas, np.inf)
    if not np.isfinite(deltas).any():
        return float("nan")
    j = int(np.argmin(deltas))
    if deltas[j] > PHASE_PEAK_TOLERANCE:
        return float("nan")
    return float(angle_arr[j])


def _endpoint_b_max_abs_angle(grp: pd.DataFrame) -> float:
    """Endpoint B: signed angle_deg at argmax(|angle_deg|) over phase in
    [0, 0.75]. Selection criterion uses magnitude; reported value is
    signed (preserves laterality direction — per Priya 2026-05-27:
    positive vs negative tongue angle is meaningful)."""
    window = _phase_window(grp)
    if window.empty:
        return float("nan")
    angle_arr = window["angle_deg"].to_numpy(dtype=np.float64)
    finite = np.isfinite(angle_arr)
    if not finite.any():
        return float("nan")
    abs_angle = np.where(finite, np.abs(angle_arr), -np.inf)
    j = int(np.argmax(abs_angle))
    return float(angle_arr[j])


def _endpoint_c_signed_x_at_max_abs(grp: pd.DataFrame) -> float:
    """Endpoint C: signed x_centered at argmax(|x_centered|) over phase
    in [0, 0.75]. Selection criterion uses magnitude; reported value is
    signed (preserves laterality direction)."""
    window = _phase_window(grp)
    if window.empty or "x_centered" not in window.columns:
        return float("nan")
    x_arr = window["x_centered"].to_numpy(dtype=np.float64)
    finite = np.isfinite(x_arr)
    if not finite.any():
        return float("nan")
    abs_x = np.where(finite, np.abs(x_arr), -np.inf)
    j = int(np.argmax(abs_x))
    return float(x_arr[j])


def _endpoint_d_peak_y(grp: pd.DataFrame) -> float:
    """Endpoint D: y_centered at phase ≈ 0.5 (lick-1 peak time).

    Q-lock 13c Stage 1 y-analog of endpoint A. ``y_centered`` is in the
    spout-midpoint frame (y = 0 = tongue tip aligned with spout midpoint;
    positive y = protrusion). Tolerance + NaN policy match A."""
    if grp.empty or "y_centered" not in grp.columns:
        return float("nan")
    phase_arr = grp["phase"].to_numpy(dtype=np.float64)
    y_arr = grp["y_centered"].to_numpy(dtype=np.float64)
    deltas = np.abs(phase_arr - PHASE_PEAK)
    finite_y = np.isfinite(y_arr)
    deltas = np.where(finite_y, deltas, np.inf)
    if not np.isfinite(deltas).any():
        return float("nan")
    j = int(np.argmin(deltas))
    if deltas[j] > PHASE_PEAK_TOLERANCE:
        return float("nan")
    return float(y_arr[j])


def _endpoint_e_signed_y_at_max_abs(grp: pd.DataFrame) -> float:
    """Endpoint E: signed y_centered at argmax(|y_centered|) over phase
    in [0, 0.75]. Selection criterion uses magnitude; reported value is
    signed (preserves protrusion-vs-retraction direction).

    Q-lock 13c Stage 1 y-analog of endpoint C."""
    window = _phase_window(grp)
    if window.empty or "y_centered" not in window.columns:
        return float("nan")
    y_arr = window["y_centered"].to_numpy(dtype=np.float64)
    finite = np.isfinite(y_arr)
    if not finite.any():
        return float("nan")
    abs_y = np.where(finite, np.abs(y_arr), -np.inf)
    j = int(np.argmax(abs_y))
    return float(y_arr[j])


def _phase_window(grp: pd.DataFrame) -> pd.DataFrame:
    """Filter to rows with phase in [PHASE_WINDOW_LO, PHASE_WINDOW_HI]."""
    if grp.empty:
        return grp
    phase_arr = grp["phase"].to_numpy(dtype=np.float64)
    mask = (phase_arr >= PHASE_WINDOW_LO) & (phase_arr <= PHASE_WINDOW_HI)
    return grp.loc[mask]


def align_endpoints_to_trial_order(
    endpoints_df: pd.DataFrame,
    trial_indices: list[int],
    sides: list[str],
) -> dict[str, list[float]]:
    """Align per-(trial, side) endpoint rows to the canonical trial_events order.

    Phase 9.1 Q-lock 13b Addendum #2 D1: the per-trial tongue endpoints
    JSON stores parallel lists indexed by the session's trial_events
    ordering (``trial_indices`` + ``sides`` at the JSON top level). This
    helper builds three NaN-aware parallel lists matching that ordering.

    Parameters
    ----------
    endpoints_df : pd.DataFrame
        Output of :func:`compute_phase_aligned_endpoints_per_trial`. One
        row per (trial_index, side) that produced phase rows.
    trial_indices : list[int]
        Canonical trial-events ordering (one entry per trial_event).
    sides : list[str]
        Side per trial-event (parallel to ``trial_indices``).

    Returns
    -------
    dict[str, list[float]]
        Keys: ``peak_angle_deg``, ``signed_angle_at_max_abs_phase_0_075_deg``,
        ``signed_x_at_max_abs_phase_0_075_px``, ``peak_y_px``,
        ``signed_y_at_max_abs_phase_0_075_px`` (last two added in Q-lock
        13c Stage 1; 2026-05-29). Each value is a
        ``len(trial_indices)``-long list of floats; trial_events with
        no matching endpoints row (no detected first lick on that side
        of that trial) get NaN at their position.
    """
    if len(trial_indices) != len(sides):
        raise ValueError(
            f"trial_indices and sides must be the same length; got "
            f"{len(trial_indices)} vs {len(sides)}.",
        )
    n = len(trial_indices)
    out: dict[str, list[float]] = {
        "peak_angle_deg": [float("nan")] * n,
        "signed_angle_at_max_abs_phase_0_075_deg": [float("nan")] * n,
        "signed_x_at_max_abs_phase_0_075_px": [float("nan")] * n,
        "peak_y_px": [float("nan")] * n,
        "signed_y_at_max_abs_phase_0_075_px": [float("nan")] * n,
    }
    if endpoints_df.empty:
        return out

    # Q-lock 13c Stage 1: y endpoint columns may be absent on
    # endpoints DataFrames produced by pre-13c callers (e.g. test
    # fixtures that build DataFrames by hand). NaN-fill the y keys
    # in that case so the function degrades gracefully.
    has_y_peak = "peak_y_px" in endpoints_df.columns
    has_y_signed = (
        "signed_y_at_max_abs_phase_0_075_px" in endpoints_df.columns
    )

    by_key: dict[tuple[int, str], dict[str, float]] = {}
    for _, row in endpoints_df.iterrows():
        key = (int(row["trial_index"]), str(row["side"]))
        by_key[key] = {
            "peak_angle_deg": float(row["peak_angle_deg"]),
            "signed_angle_at_max_abs_phase_0_075_deg":
                float(row["signed_angle_at_max_abs_phase_0_075_deg"]),
            "signed_x_at_max_abs_phase_0_075_px":
                float(row["signed_x_at_max_abs_phase_0_075_px"]),
            "peak_y_px":
                float(row["peak_y_px"]) if has_y_peak else float("nan"),
            "signed_y_at_max_abs_phase_0_075_px":
                float(row["signed_y_at_max_abs_phase_0_075_px"])
                if has_y_signed else float("nan"),
        }

    for i, (ti, side) in enumerate(zip(trial_indices, sides)):
        rec = by_key.get((int(ti), str(side)))
        if rec is None:
            continue
        for key in out:
            out[key][i] = rec[key]
    return out
