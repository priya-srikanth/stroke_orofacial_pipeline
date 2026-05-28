"""Phase 9.1 Q-lock 13b — phase-aligned tongue endpoints per (trial, side).

Phase 9.1 Q-lock 13b (Addenda #1 + #2 locks, 2026-05-27). Three scalar
endpoints derived from the first-lick-centered phase trajectory:

- A ``peak_angle_deg`` — tongue angle at ``phase = 0.5`` (lick-1 peak time).
- B ``signed_angle_at_max_abs_phase_0_075_deg`` — signed ``angle_deg``
  at ``argmax(|angle_deg|)`` over ``phase in [0, 0.75]`` (selection by
  magnitude; reported value signed — positive vs negative is meaningful).
- C ``signed_x_at_max_abs_phase_0_075_px`` — ``x_centered`` at the time-point
  of largest ``|x_centered|`` over ``phase in [0, 0.75]`` (selection by
  magnitude; reported value signed). Q-lock 13b Addendum #2 Q6 refinement.

All three endpoints share the same first-lick-centered phase substrate
(``build_first_lick_centered_phase_rows`` with ``ili_source="synthetic_only"``
per Addendum #1 Q1 lock; cycle width = the animal's pre-stroke median ILI
on ``bundle.metadata["pre_stroke_median_ili_ms"]``).

``x_centered`` is consumed in the spout-midpoint reference frame (Addendum
#2 D2 lock: x = 0 = tongue aligned with spout midline; no eye-relative
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
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .tongue_pertrial import (
    TongueVisualBundle,
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
)


def _empty_phase_aligned_endpoints_df() -> pd.DataFrame:
    """Empty DataFrame with the expected column dtypes."""
    return pd.DataFrame({
        "trial_index": pd.Series(dtype=int),
        "side": pd.Series(dtype=object),
        "peak_angle_deg": pd.Series(dtype=float),
        "signed_angle_at_max_abs_phase_0_075_deg": pd.Series(dtype=float),
        "signed_x_at_max_abs_phase_0_075_px": pd.Series(dtype=float),
    })


def compute_phase_aligned_endpoints_per_trial(
    bundle: TongueVisualBundle,
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

    phase_rows = build_first_lick_centered_phase_rows(
        bundle, synthetic_ili_ms=synth, ili_source="synthetic_only",
    )
    if phase_rows.empty:
        return _empty_phase_aligned_endpoints_df()

    out_rows: list[dict[str, Any]] = []
    for (trial_idx, side), grp in phase_rows.groupby(
        ["trial_index", "side"], sort=True,
    ):
        peak_angle = _endpoint_a_peak_angle(grp)
        max_abs_angle = _endpoint_b_max_abs_angle(grp)
        signed_x = _endpoint_c_signed_x_at_max_abs(grp)
        out_rows.append({
            "trial_index": int(trial_idx),
            "side": str(side),
            "peak_angle_deg": peak_angle,
            "signed_angle_at_max_abs_phase_0_075_deg": max_abs_angle,
            "signed_x_at_max_abs_phase_0_075_px": signed_x,
        })

    if not out_rows:
        return _empty_phase_aligned_endpoints_df()
    return pd.DataFrame(out_rows, columns=list(PHASE_ALIGNED_ENDPOINT_COLUMNS))


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
        ``signed_x_at_max_abs_phase_0_075_px``. Each value is a
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
    }
    if endpoints_df.empty:
        return out

    by_key: dict[tuple[int, str], dict[str, float]] = {}
    for _, row in endpoints_df.iterrows():
        key = (int(row["trial_index"]), str(row["side"]))
        by_key[key] = {
            "peak_angle_deg": float(row["peak_angle_deg"]),
            "signed_angle_at_max_abs_phase_0_075_deg":
                float(row["signed_angle_at_max_abs_phase_0_075_deg"]),
            "signed_x_at_max_abs_phase_0_075_px":
                float(row["signed_x_at_max_abs_phase_0_075_px"]),
        }

    for i, (ti, side) in enumerate(zip(trial_indices, sides)):
        rec = by_key.get((int(ti), str(side)))
        if rec is None:
            continue
        for key in out:
            out[key][i] = rec[key]
    return out
