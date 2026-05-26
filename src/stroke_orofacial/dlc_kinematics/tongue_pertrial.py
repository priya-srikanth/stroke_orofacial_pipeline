"""Phase 7a.3 V3 — tongue per-trial features (Cells 33/36/39/42/50).

Ported from canonical tongue notebook
(``20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb``,
SHA256 ``ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643``,
Cells 33/36/39/42/50 vendored at
``docs/legacy_snippets/tongue_pertrial_features.py``).

Module shape (4-file split per Q-Split sign-off 2026-04-28):

- ``tongue_pertrial.py`` (this file): public API, dataclasses, loaders,
  trial-slice helper, Cells 33/36/39 + Cell 42 reductions/traces,
  driver core.
- ``_detector.py``: unified slope detector + bout helpers + bout-mode filter.
- ``_angle.py``: Cell 50 angle math, NaN-aware smoothing, per-trial
  scalar sampling, own-bout scalars, session-inclusion evaluator.
- ``_writers.py``: three atomic writers (parquet × 2 + JSON).

Inputs
------
- 7a.2 tongue interpolated_traces parquet
  (``frame_idx``, ``x_final``, ``y_final``, ``likelihood_raw``,
  ``is_interp_fill``, ``is_baseline_fill``, ``fill_method``)
- Consolidated centered_spout_midpoint parquet
  (39 float32 cols: nose / jaw / tongue / {L,R}_whiskers_{1,2,3} /
  {L,R}_eye / {L,R}_spout × {x, y, likelihood})
- :class:`SessionManifest` (animal, date)
- ``trial_events`` (per-trial tone-onset frame + side; ``TrialEvent.tone_frame_idx``
  field name PRESERVED per Phase 7b-light Addendum #1 — DataFrame column /
  on-disk surface) — supplied by caller (Q7 lock 2026-04-28: keep as
  required arg; auto-derive deferred to Task 5 wrapper)

Outputs (atomic, three files per session)
-----------------------------------------
- ``<outputs>/dlc_kinematics/per_frame/tongue/<animal>/<YYYYMMDD>.parquet``
  (per-frame angle parquet, 2 cols + 10 file-level metadata keys)
- ``<outputs>/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet``
  (per-session × side traces parquet, 6 cols + 17 file-level metadata keys)
- ``<outputs>/dlc_kinematics/per_trial/tongue/<animal>/<YYYYMMDD>.json``
  (per-trial endpoints JSON, ``schema_version="v7a.3"``)
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics._angle import (
    _evaluate_session_inclusion,
    _extract_angle_at_lick_timestamps,
    _extract_angle_max_signed_per_lick,
    _extract_cell50_own_bout_scalars,
    _extract_per_frame_angle_smoothed,
)
from stroke_orofacial.dlc_kinematics._detector import (
    _build_bouts,
    _moving_avg_nan,
    _slope_detect_lick_peaks,
)
# Task 5c: alias the legacy slope detector for use as both the
# "bounded" and "legacy" source in the v7 orchestrator (called twice
# with different detector_params).
_slope_detect_lick_peaks_legacy = _slope_detect_lick_peaks
from stroke_orofacial.dlc_kinematics._detector_v2 import (
    _PeakList as _PeakList_v2,
    detect_local_maxima as _detect_local_maxima_v2,
    merge_detector_outputs as _merge_detector_outputs_v2,
)
from stroke_orofacial.dlc_kinematics._gates import (
    gate_D as _gate_D_v7,
    gate_E as _gate_E_v7,
    gate_F as _gate_F_v7,
    parabolic_excise as _parabolic_excise_v7,
    run_m_gate as _run_m_gate_v7,
    spline_excise as _spline_excise_v7,
)
from stroke_orofacial.dlc_kinematics._preclean import (
    _PrecleanDiagnostics,
    preclean_trace as _preclean_trace_v7,
)
from stroke_orofacial.dlc_kinematics._writers import (
    _write_angle_parquet_atomic,
    _write_endpoints_json_atomic,
    _write_traces_parquet_atomic,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

# Version tag stamped into every emitted parquet/JSON. Bumping requires a
# DECISIONS entry + 14-session legacy_approximate parity re-run.
FEATURE_EXTRACTION_VERSION: str = "v7a.3"
INTERPOLATION_VERSION: str = "v5p3"

# Legacy default; consolidated callers read fps from upstream parquet metadata.
_DEFAULT_FPS: float = 250.0


# ===========================================================================
# Public dataclasses
# ===========================================================================


@dataclass
class TrialEvent:
    """Per-trial alignment record passed in by the caller.

    The driver iterates over a :class:`Sequence` of these to extract per-trial
    snippets from the session-wide interpolated trace. ``tone_frame_idx``
    (field name PRESERVED per Addendum #1 — DataFrame column / on-disk
    surface; semantically the tone-onset frame index under Case-2 universal)
    pins t=0 for that trial; ``side`` keys the Cell 42 per-side aggregation.

    Why this is a caller-provided argument (Q7 lock 2026-04-28): trial-event
    resolution depends on upstream spout_behavior products (wavesurfer
    tone-onset times + alignment LUT → cam-frame indices) that are out of
    scope for 7a.3. The Phase 7a.3 V3 parity harness (Task 5) wires these
    in from existing spout_behavior outputs; production callers do the same.
    """

    trial_index: int
    tone_frame_idx: int
    side: Literal["L", "R"]


@dataclass
class TonguePertrialResult:
    """In-memory container for the three on-disk emit pieces (pre-write).

    Carried by :class:`_PertrialCoreResult` (alongside
    :class:`TongueVisualBundle`). The driver writes all three artifacts
    atomically; callers that want the pure computation without I/O can
    call :func:`_build_tongue_pertrial_core` directly and ignore the
    bundle field.
    """

    angle_per_frame: pd.DataFrame
    licking_dynamics_traces: pd.DataFrame
    endpoints: dict[str, Any]
    angle_metadata: dict[str, str]
    licking_dynamics_metadata: dict[str, str]


@dataclass(frozen=True)
class TongueVisualBundle:
    """Phase 7a.4 — in-memory per-trial array DataFrames for the visual gate.

    Returned by :func:`build_tongue_visual_bundle`. NOT emitted to disk —
    the 7a.3 V3 emit set (angle parquet + licking-dynamics traces parquet
    + endpoints JSON) is unchanged. The visual bundle exposes intermediate
    per-trial array snippets and per-frame phase rows that the Cell 50
    plot families consume but the on-disk emit set doesn't carry. See
    Phase 7a.4 Task 1.5b audit for the rationale.

    Attributes
    ----------
    df_trials : DataFrame
        One row per trial. Columns: identifier (``trial_index``, ``side``)
        + per-trial array snippets (``t_ms``, ``y_snip``, ``angle_snip``,
        ``angle_allbouts_snip``, ``angle_firstbout_snip``,
        ``angle_firstmulti_snip``, ``t_firstpeak_align_ms``,
        ``angle_firstpeak_snip``) + scalars (``n_peaks``, ``n_bouts``,
        ``n_multi_lick_bouts``, ``first_peak_t_ms``).
    df_bouts : DataFrame
        Mixed-row schema (legacy Cell 50 convention): one summary row per
        bout (carries bout-level fields, peak-level fields NaN) plus one
        row per peak in the bout (carries peak-level fields, bout-level
        fields NaN). Rendered by :func:`_plot_qc_trials` for bout-window
        shading + peak markers.
    df_phase : DataFrame
        One row per (trial, frame-in-multi-bout). Columns: ``side``,
        ``trial_index``, ``bout_idx``, ``bout_rank``, ``multi_bout_rank``,
        ``t_ms``, ``phase`` (0..1), ``phase_bin`` (int), ``phase_bin_center``
        (float), ``angle_deg``, ``x_geom``, ``y_geom``. Empty if the trial
        has no multi-lick bouts.
    angle_per_frame : DataFrame
        Session-length per-frame smoothed signed tongue angle. Same
        DataFrame as :attr:`TonguePertrialResult.angle_per_frame` (shared
        compute via :func:`_extract_per_frame_angle_smoothed`).
    metadata : dict
        Session-level scalars: ``animal``, ``date``, ``fps``,
        ``n_frames``, ``eye_in_spout_frame_x``, ``eye_in_spout_frame_y``,
        ``angle_sign_flip``, ``smoothing_gaussian_sigma_ms``, plus the
        bundle-window knobs (``plot_win_ms``, ``detect_win_ms``,
        ``first_peak_align_win_ms``, ``n_phase_bins``) that drove the
        per-trial compute.
    """

    df_trials: pd.DataFrame
    df_bouts: pd.DataFrame
    df_phase: pd.DataFrame
    angle_per_frame: pd.DataFrame
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _PertrialCoreResult:
    """Return shape of :func:`_build_tongue_pertrial_core`.

    PRIVATE — both public entry points (:func:`build_tongue_pertrial` and
    :func:`build_tongue_visual_bundle`) consume this same core return.
    Keeps the compute path single-sourced; the two public functions just
    project different views of the same intermediates.
    """

    tongue_pertrial: TonguePertrialResult
    visual_bundle: TongueVisualBundle
    v7_trial_results: list["_V7TrialResult"] | None = None
    # ^ NEW Phase 7e — populated ONLY when use_v7_pipeline=True. List of
    # per-trial v7 results in trial_events order. None when flag is False
    # (= legacy-only run). Consumed by Task 6 parquet writers + Task 7
    # downstream metric updates.


@dataclass(frozen=True)
class _V7TrialResult:
    """Per-trial output of the Phase 7e v7 pipeline (Task 5).

    Produced by :func:`_run_v7_pipeline_per_trial` when
    ``dlc_kinematics.tongue_pertrial.use_v7_pipeline`` is True. Carries:

    - ``y_clean, x_clean, is_baseline_fill_clean``: post-pre-clean trace
      (Addendum #1 Rules 1-4 applied). Same shape as the input trial
      slice; ready to feed the cleaned_traces parquet (Task 6).
    - ``kept_licks``: list of kept-lick records, one per kept peak after
      gates F/D/E/M run. Each record has the per-lick fields needed by
      the ``lick_events/`` parquet (Decision 4 schema minus the session-
      level fields animal/date/trial/side which the caller adds).
    - ``preclean_diag``: full :class:`_PrecleanDiagnostics` for
      bookkeeping + figure rendering.

    All frame indices are trial-slice-local (not session-local).
    """

    trial_index: int
    side: Literal["L", "R"]
    y_clean: np.ndarray
    x_clean: np.ndarray
    is_baseline_fill_clean: np.ndarray
    t_ms: np.ndarray         # per-frame trial-relative ms (post-tone)
    kept_licks: list[dict[str, Any]]
    preclean_diag: _PrecleanDiagnostics


# ===========================================================================
# Public selectors / builders over TongueVisualBundle (Addenda #9 + #10)
# ===========================================================================
#
# The phase-aligned-angle plot family (per-session ``_1st_lick`` /
# ``_all_licks`` PNGs and forthcoming cross-session variants) consumes
# CENTERED-ON-PEAK phase rows built from per-frame ``angle_snip`` +
# ``df_bouts`` peak times — NOT the bundle's existing ``df_phase``
# (which carries legacy peak-to-peak-shifted phase per
# :func:`_assign_phase_peak_to_peak_shifted`).
#
# Centered convention per peak ``p`` with forward inter-lick interval
# ``ILI = next_peak - p``:
#
#   window = (p - ILI / 2, p + ILI / 2)
#   phase  = (t - (p - ILI / 2)) / ILI ∈ [0, 1]
#
# ``p`` lands at ``phase == 0.5``; cycle is symmetric about the peak.
# The rendered curve reads naturally as "approach peak → at peak →
# leave peak" left-to-right. See Addenda #9 + #10 DECISIONS entry.
#
# LAST PEAK of each multi-bout (no forward ILI) is dropped — no
# synthetic-ILI fallback. Loses ~10-20% of peaks across the dataset;
# accepted as the cleanest-convention trade-off.
#
# Per Addendum #5 Option α: trials with NO multi-bouts contribute
# nothing — phase requires ≥2 peaks to define a cycle.


_CENTERED_PHASE_ROW_COLUMNS: tuple[str, ...] = (
    "side", "trial_index", "peak_t_ms", "t_ms", "phase",
    "phase_bin", "phase_bin_center", "angle_deg",
)


def _empty_centered_phase_rows_df() -> pd.DataFrame:
    """Empty centered-phase DataFrame with the expected columns."""
    cols = {
        "side": pd.Series(dtype=object),
        "trial_index": pd.Series(dtype=int),
        "peak_t_ms": pd.Series(dtype=float),
        "t_ms": pd.Series(dtype=float),
        "phase": pd.Series(dtype=float),
        "phase_bin": pd.Series(dtype=int),
        "phase_bin_center": pd.Series(dtype=float),
        "angle_deg": pd.Series(dtype=float),
    }
    return pd.DataFrame(cols)


def _centered_phase_rows_from_peaks(
    *,
    peak_times_ms: np.ndarray,
    ilis_ms: np.ndarray,
    t_arr: np.ndarray,
    angle_snip: np.ndarray,
    side: str,
    trial_index: int,
    phase_bin_edges: np.ndarray,
    phase_bin_centers: np.ndarray,
) -> list[dict[str, Any]]:
    """Shared building block for the centered-phase helpers
    (Addenda #9 + #10).

    For each ``(p, ili)`` pair in ``zip(peak_times_ms, ilis_ms)`` with
    finite ``ili > 0``, identifies frames in the trial slice whose
    ``t_arr`` falls in ``(p - ili / 2, p + ili / 2)`` and emits one
    row per qualifying frame with phase computed as
    ``(t - (p - ili / 2)) / ili`` (clamped to ``[0, 1]``).

    Returns an unwrapped list of dicts — callers concatenate across
    trials and sides into the final DataFrame.
    """
    out: list[dict[str, Any]] = []
    n_phase_bins = len(phase_bin_centers)
    for p, ili in zip(peak_times_ms, ilis_ms):
        p = float(p)
        ili = float(ili)
        if not (np.isfinite(p) and np.isfinite(ili) and ili > 0):
            continue
        win_lo = p - ili / 2.0
        win_hi = p + ili / 2.0
        mask = (
            (t_arr >= win_lo) & (t_arr <= win_hi)
            & np.isfinite(angle_snip)
        )
        for ii in np.where(mask)[0]:
            t = float(t_arr[ii])
            phase = (t - win_lo) / ili
            phase = float(np.clip(phase, 0.0, 1.0))
            bin_idx = int(np.clip(
                np.searchsorted(phase_bin_edges, phase, side="right") - 1,
                0, n_phase_bins - 1,
            ))
            out.append({
                "side": side,
                "trial_index": trial_index,
                "peak_t_ms": p,
                "t_ms": t,
                "phase": phase,
                "phase_bin": bin_idx,
                "phase_bin_center": float(phase_bin_centers[bin_idx]),
                "angle_deg": float(angle_snip[ii]),
            })
    return out


def _bundle_phase_bin_arrays(
    bundle: "TongueVisualBundle",
) -> tuple[np.ndarray, np.ndarray]:
    n_phase_bins = int(bundle.metadata.get("n_phase_bins", 72))
    phase_bin_edges = np.linspace(
        0.0, 1.0, n_phase_bins + 1, dtype=np.float64,
    )
    phase_bin_centers = 0.5 * (phase_bin_edges[:-1] + phase_bin_edges[1:])
    return phase_bin_edges, phase_bin_centers


def _trial_arrays(
    df_trials: pd.DataFrame, trial_index: int, side: str,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Pull ``(t_ms, angle_snip)`` for one trial; ``None`` if missing."""
    trial_row = df_trials[
        (df_trials["trial_index"] == trial_index)
        & (df_trials["side"] == side)
    ]
    if trial_row.empty:
        return None
    t_arr = np.asarray(trial_row.iloc[0]["t_ms"], dtype=np.float64)
    angle_arr = np.asarray(trial_row.iloc[0]["angle_snip"], dtype=np.float64)
    return t_arr, angle_arr


def build_first_lick_centered_phase_rows(
    bundle: "TongueVisualBundle",
    *,
    synthetic_ili_ms: float | None = None,
    ili_source: Literal["real_only", "hybrid", "synthetic_only"] = "synthetic_only",
) -> pd.DataFrame:
    """Build centered-on-first-peak phase rows per (trial, side).

    Phase 7a.4-cross-session-angle Addenda #9 / #12 / #14 / #15
    (2026-05-04).

    ``ili_source`` (Addendum #14; default flipped to
    ``"synthetic_only"`` per Addendum #15 — Mode 3 won the 3-way
    PS46/PS50/PS55 visual gate for both ``_1st_lick`` and
    ``first_2_licks`` plot families):

      - ``"synthetic_only"`` (default): cycle width =
        ``synthetic_ili_ms`` for EVERY peak regardless of forward-
        neighbour existence. "First lick" = chronologically-first
        detected peak. Real-ILI lookup bypassed entirely.
        ``synthetic_ili_ms`` REQUIRED (raises ValueError if not
        finite + positive). Eliminates per-cycle width variance
        from the per-bin aggregation; remaining variance is the
        natural angle-shape variation across trials (the science
        of interest).
      - ``"hybrid"``: "first lick" = chronologically-first detected
        peak per (trial, side); ILI = forward neighbour across ALL
        bouts if available, else ``synthetic_ili_ms``. Isolated-
        lick-only trials contribute via synthetic. Production
        default between Addendum #12 and Addendum #15.
      - ``"real_only"``: real forward ILI from same-bout adjacency
        only. "First lick" = peak[0] of the FIRST MULTI-BOUT per
        (trial, side); ILI = peak[1] - peak[0] in same bout.
        Isolated-lick-only trials drop. ``synthetic_ili_ms`` is
        IGNORED.

    Phase formula (all modes):

      window = (peak_t - ILI / 2, peak_t + ILI / 2)
      phase  = (t - (peak_t - ILI / 2)) / ILI ∈ [0, 1]

    Returns a DataFrame with columns ``side, trial_index, peak_t_ms,
    t_ms, phase, phase_bin, phase_bin_center, angle_deg``.
    """
    if ili_source not in ("real_only", "hybrid", "synthetic_only"):
        raise ValueError(
            f"ili_source must be 'real_only' / 'hybrid' / "
            f"'synthetic_only'; got {ili_source!r}"
        )
    synth = (
        float(synthetic_ili_ms)
        if synthetic_ili_ms is not None
        else float("nan")
    )
    synth_finite = np.isfinite(synth) and synth > 0
    if ili_source == "synthetic_only" and not synth_finite:
        raise ValueError(
            f"ili_source='synthetic_only' requires a finite positive "
            f"synthetic_ili_ms; got {synthetic_ili_ms!r}"
        )
    # Byte-for-byte Addendum #12 NaN-fallback semantic: hybrid mode
    # without a finite synthetic ILI degrades to real_only (multi-
    # bout-only). Production caller passes
    # bundle.metadata["pre_stroke_median_ili_ms"] which can be NaN
    # when the animal has no pre-stroke sessions on disk.
    if ili_source == "hybrid" and not synth_finite:
        ili_source = "real_only"

    df_trials = bundle.df_trials
    df_bouts = bundle.df_bouts
    if df_trials.empty or df_bouts.empty:
        return _empty_centered_phase_rows_df()

    phase_bin_edges, phase_bin_centers = _bundle_phase_bin_arrays(bundle)

    rows: list[dict[str, Any]] = []
    if ili_source == "real_only":
        # Multi-bout-only: peak[0] of first multi-bout per trial,
        # ILI from same-bout adjacency.
        summaries = df_bouts[
            df_bouts["peak_t_ms"].isna()
            & (df_bouts["multi_bout_rank"] == 0)
            & df_bouts["peak_t0_ms"].notna()
            & df_bouts["peak_t1_ms"].notna()
        ][["trial_index", "side", "peak_t0_ms", "peak_t1_ms"]].drop_duplicates()
        if summaries.empty:
            return _empty_centered_phase_rows_df()
        for _, summary in summaries.iterrows():
            trial_idx = int(summary["trial_index"])
            side = str(summary["side"])
            arrs = _trial_arrays(df_trials, trial_idx, side)
            if arrs is None:
                continue
            t_arr, angle_arr = arrs
            p0 = float(summary["peak_t0_ms"])
            p1 = float(summary["peak_t1_ms"])
            rows.extend(_centered_phase_rows_from_peaks(
                peak_times_ms=np.array([p0]),
                ilis_ms=np.array([p1 - p0]),
                t_arr=t_arr, angle_snip=angle_arr,
                side=side, trial_index=trial_idx,
                phase_bin_edges=phase_bin_edges,
                phase_bin_centers=phase_bin_centers,
            ))
    else:
        # "hybrid" or "synthetic_only" — both walk all chronologically-
        # ordered peaks per (trial, side). Hybrid uses real ILI when
        # available, synthetic as fallback. Synthetic_only forces
        # synthetic for every peak.
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
        ][["trial_index", "side", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "peak_t_ms"],
        )
        for (trial_idx, side), grp in per_peak.groupby(
            ["trial_index", "side"], sort=False,
        ):
            peak_times = np.asarray(
                grp["peak_t_ms"].to_numpy(), dtype=np.float64,
            )
            if peak_times.size == 0:
                continue
            trial_idx = int(trial_idx)
            side = str(side)
            arrs = _trial_arrays(df_trials, trial_idx, side)
            if arrs is None:
                continue
            t_arr, angle_arr = arrs
            p0 = float(peak_times[0])
            if ili_source == "synthetic_only":
                ili = synth
            else:  # hybrid
                ili = (
                    float(peak_times[1] - peak_times[0])
                    if peak_times.size >= 2 else synth
                )
                if not (np.isfinite(ili) and ili > 0):
                    ili = synth
            if not (np.isfinite(ili) and ili > 0):
                # Hybrid with no synthetic available → skip this trial.
                continue
            rows.extend(_centered_phase_rows_from_peaks(
                peak_times_ms=np.array([p0]),
                ilis_ms=np.array([ili]),
                t_arr=t_arr, angle_snip=angle_arr,
                side=side, trial_index=trial_idx,
                phase_bin_edges=phase_bin_edges,
                phase_bin_centers=phase_bin_centers,
            ))

    if not rows:
        return _empty_centered_phase_rows_df()
    return pd.DataFrame(rows)


def build_first_n_licks_centered_phase_rows(
    bundle: "TongueVisualBundle",
    *,
    n_peaks: int = 2,
    synthetic_ili_ms: float | None = None,
    ili_source: Literal["real_only", "hybrid", "synthetic_only"] = "synthetic_only",
) -> pd.DataFrame:
    """Build centered-phase rows for the FIRST ``n_peaks`` consecutive
    licks per (trial, side). Phase 7a.4-cross-session-angle Addenda
    #11 Part A / #12 / #14 / #15 (2026-05-04).

    ``ili_source`` (Addendum #14; default flipped to
    ``"synthetic_only"`` per Addendum #15 verdict):

      - ``"synthetic_only"`` (default): first ``n_peaks`` peaks
        chronologically across all bouts; cycle width =
        ``synthetic_ili_ms`` for ALL cycles regardless of forward-
        neighbour existence.
      - ``"hybrid"``: first ``n_peaks`` peaks chronologically across
        all bouts; ILI[i] = forward neighbour if available, else
        ``synthetic_ili_ms``. Requires ``n_peaks`` total peaks.
      - ``"real_only"``: first ``n_peaks`` peaks of the FIRST
        MULTI-BOUT; ILI[i] = same-bout forward neighbour. Requires
        ``n_peaks + 1`` peaks in the first multi-bout.

    Phase formula (peak[i] at x = i + 0.5):

      x_global = (i + 0.5) + (t - p[i]) / ILI[i]   # in [i, i + 1]

    Phase-bin edges/centers span ``[0, n_peaks]`` with
    ``n_phase_bins * n_peaks`` total bins. Returns a DataFrame with
    the same columns as the single-cycle builders; ``phase`` /
    ``phase_bin_center`` span ``[0, n_peaks]``.
    """
    if int(n_peaks) < 2:
        raise ValueError(f"n_peaks must be >= 2; got {n_peaks!r}")
    if ili_source not in ("real_only", "hybrid", "synthetic_only"):
        raise ValueError(
            f"ili_source must be 'real_only' / 'hybrid' / "
            f"'synthetic_only'; got {ili_source!r}"
        )
    synth = (
        float(synthetic_ili_ms)
        if synthetic_ili_ms is not None
        else float("nan")
    )
    synth_finite = np.isfinite(synth) and synth > 0
    if ili_source == "synthetic_only" and not synth_finite:
        raise ValueError(
            f"ili_source='synthetic_only' requires a finite positive "
            f"synthetic_ili_ms; got {synthetic_ili_ms!r}"
        )
    # Addendum #12 NaN-fallback: hybrid + missing synthetic → real_only.
    if ili_source == "hybrid" and not synth_finite:
        ili_source = "real_only"

    df_trials = bundle.df_trials
    df_bouts = bundle.df_bouts
    if df_trials.empty or df_bouts.empty:
        return _empty_centered_phase_rows_df()

    n_phase_bins = int(bundle.metadata.get("n_phase_bins", 72))
    total_bins = int(n_phase_bins) * int(n_peaks)
    phase_bin_edges = np.linspace(
        0.0, float(n_peaks), total_bins + 1, dtype=np.float64,
    )
    phase_bin_centers = 0.5 * (phase_bin_edges[:-1] + phase_bin_edges[1:])

    if ili_source == "real_only":
        # Multi-bout-only: first multi-bout per trial.
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
            & (df_bouts["multi_bout_rank"] == 0)
        ][["trial_index", "side", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "peak_t_ms"],
        )
    else:
        # hybrid + synthetic_only: chronologically-ordered peaks
        # across ALL bouts.
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
        ][["trial_index", "side", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "peak_t_ms"],
        )
    if per_peak.empty:
        return _empty_centered_phase_rows_df()

    rows: list[dict[str, Any]] = []
    for (trial_idx, side), grp in per_peak.groupby(
        ["trial_index", "side"], sort=False,
    ):
        peak_times = np.asarray(
            grp["peak_t_ms"].to_numpy(), dtype=np.float64,
        )
        if ili_source == "real_only":
            # Need n_peaks + 1 peaks in the first multi-bout.
            if peak_times.size < int(n_peaks) + 1:
                continue
        else:
            # hybrid + synthetic_only: need n_peaks total peaks.
            if peak_times.size < int(n_peaks):
                continue
        trial_idx = int(trial_idx)
        side = str(side)
        arrs = _trial_arrays(df_trials, trial_idx, side)
        if arrs is None:
            continue
        t_arr, angle_arr = arrs
        for i in range(int(n_peaks)):
            p_i = float(peak_times[i])
            if ili_source == "synthetic_only":
                ili = synth
            elif ili_source == "real_only":
                # Same-bout forward neighbour required.
                ili = float(peak_times[i + 1] - p_i)
                if not (np.isfinite(ili) and ili > 0):
                    continue
            else:  # hybrid
                if i + 1 < peak_times.size:
                    ili = float(peak_times[i + 1] - p_i)
                    if not (np.isfinite(ili) and ili > 0):
                        ili = synth
                else:
                    ili = synth
            if not (np.isfinite(ili) and ili > 0):
                continue
            win_lo = p_i - ili / 2.0
            win_hi = p_i + ili / 2.0
            mask = (
                (t_arr >= win_lo) & (t_arr <= win_hi)
                & np.isfinite(angle_arr)
            )
            for ii in np.where(mask)[0]:
                t = float(t_arr[ii])
                x_global = float(i) + 0.5 + (t - p_i) / ili
                x_global = float(np.clip(x_global, 0.0, float(n_peaks)))
                bin_idx = int(np.clip(
                    np.searchsorted(
                        phase_bin_edges, x_global, side="right",
                    ) - 1,
                    0, total_bins - 1,
                ))
                rows.append({
                    "side": side,
                    "trial_index": trial_idx,
                    "peak_t_ms": p_i,
                    "t_ms": t,
                    "phase": x_global,
                    "phase_bin": bin_idx,
                    "phase_bin_center": float(phase_bin_centers[bin_idx]),
                    "angle_deg": float(angle_arr[ii]),
                })

    if not rows:
        return _empty_centered_phase_rows_df()
    return pd.DataFrame(rows)


def build_all_licks_centered_phase_rows(
    bundle: "TongueVisualBundle",
    *,
    synthetic_ili_ms: float | None = None,
    ili_source: Literal["real_only", "hybrid", "synthetic_only"] = "synthetic_only",
) -> pd.DataFrame:
    """Build centered-on-peak phase rows for ALL detected licks per
    (trial, side). Phase 7a.4-cross-session-angle Addenda #10 / #12
    / #14 / #15 (2026-05-04).

    ``ili_source`` (Addendum #14; default flipped to
    ``"synthetic_only"`` per Addendum #15 verdict):

      - ``"synthetic_only"`` (default): every peak across all bouts;
        cycle width = ``synthetic_ili_ms`` for ALL peaks regardless
        of forward-neighbour existence.
      - ``"hybrid"``: every peak across all bouts; forward-neighbour
        ILI if available (across bout boundaries), else
        ``synthetic_ili_ms``. Last-peak-of-trial + isolated-lick
        bouts contribute via synthetic. Production default between
        #12 and #15.
      - ``"real_only"``: every peak in every MULTI-bout; ILI =
        same-bout forward neighbour; LAST peak of each bout
        dropped. Isolated-lick bouts contribute nothing.

    Phase formula:

      window[i] = (p[i] - ILI[i] / 2, p[i] + ILI[i] / 2)
      phase     = (t - window_lo) / ILI[i] ∈ [0, 1]

    Returns a DataFrame with the same columns as
    :func:`build_first_lick_centered_phase_rows`.
    """
    if ili_source not in ("real_only", "hybrid", "synthetic_only"):
        raise ValueError(
            f"ili_source must be 'real_only' / 'hybrid' / "
            f"'synthetic_only'; got {ili_source!r}"
        )
    synth = (
        float(synthetic_ili_ms)
        if synthetic_ili_ms is not None
        else float("nan")
    )
    synth_finite = np.isfinite(synth) and synth > 0
    if ili_source == "synthetic_only" and not synth_finite:
        raise ValueError(
            f"ili_source='synthetic_only' requires a finite positive "
            f"synthetic_ili_ms; got {synthetic_ili_ms!r}"
        )
    # Addendum #12 NaN-fallback: hybrid + missing synthetic → real_only.
    if ili_source == "hybrid" and not synth_finite:
        ili_source = "real_only"

    df_trials = bundle.df_trials
    df_bouts = bundle.df_bouts
    if df_trials.empty or df_bouts.empty:
        return _empty_centered_phase_rows_df()

    phase_bin_edges, phase_bin_centers = _bundle_phase_bin_arrays(bundle)
    use_synthetic = (
        ili_source in ("hybrid", "synthetic_only")
        and synth_finite
    )

    if use_synthetic:
        # All detected peaks per (trial, side), regardless of bout
        # structure. Forward ILI = chronologically-next peak's
        # difference; synthetic for the trial's last peak.
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
        ][["trial_index", "side", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "peak_t_ms"],
        )
    else:
        # Multi-bout-only: per-peak rows in multi-bouts.
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
            & df_bouts["multi_bout_rank"].notna()
        ][["trial_index", "side", "bout_idx", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "bout_idx", "peak_t_ms"],
        )
    if per_peak.empty:
        return _empty_centered_phase_rows_df()

    rows: list[dict[str, Any]] = []
    if use_synthetic:
        for (trial_idx, side), trial_side_rows in per_peak.groupby(
            ["trial_index", "side"], sort=False,
        ):
            trial_idx = int(trial_idx)
            side = str(side)
            arrs = _trial_arrays(df_trials, trial_idx, side)
            if arrs is None:
                continue
            t_arr, angle_arr = arrs
            peak_times = np.asarray(
                trial_side_rows["peak_t_ms"].to_numpy(), dtype=np.float64,
            )
            if peak_times.size == 0:
                continue
            peaks_to_render: list[float] = []
            ilis_to_render: list[float] = []
            for i in range(peak_times.size):
                p = float(peak_times[i])
                if ili_source == "synthetic_only":
                    ili = synth
                else:  # hybrid
                    if i + 1 < peak_times.size:
                        ili = float(peak_times[i + 1] - peak_times[i])
                        if not (np.isfinite(ili) and ili > 0):
                            ili = synth
                    else:
                        ili = synth
                peaks_to_render.append(p)
                ilis_to_render.append(ili)
            rows.extend(_centered_phase_rows_from_peaks(
                peak_times_ms=np.asarray(peaks_to_render),
                ilis_ms=np.asarray(ilis_to_render),
                t_arr=t_arr, angle_snip=angle_arr,
                side=side, trial_index=trial_idx,
                phase_bin_edges=phase_bin_edges,
                phase_bin_centers=phase_bin_centers,
            ))
    else:
        for (trial_idx, side), trial_side_rows in per_peak.groupby(
            ["trial_index", "side"], sort=False,
        ):
            trial_idx = int(trial_idx)
            side = str(side)
            arrs = _trial_arrays(df_trials, trial_idx, side)
            if arrs is None:
                continue
            t_arr, angle_arr = arrs
            peaks_to_render = []
            ilis_to_render = []
            for _bout_idx, bout_rows in trial_side_rows.groupby(
                "bout_idx", sort=False,
            ):
                peak_times = np.asarray(
                    bout_rows["peak_t_ms"].to_numpy(),
                    dtype=np.float64,
                )
                if peak_times.size < 2:
                    continue
                for i in range(peak_times.size - 1):
                    p = float(peak_times[i])
                    ili = float(peak_times[i + 1] - peak_times[i])
                    peaks_to_render.append(p)
                    ilis_to_render.append(ili)
            if not peaks_to_render:
                continue
            rows.extend(_centered_phase_rows_from_peaks(
                peak_times_ms=np.asarray(peaks_to_render),
                ilis_ms=np.asarray(ilis_to_render),
                t_arr=t_arr, angle_snip=angle_arr,
                side=side, trial_index=trial_idx,
                phase_bin_edges=phase_bin_edges,
                phase_bin_centers=phase_bin_centers,
            ))

    if not rows:
        return _empty_centered_phase_rows_df()
    return pd.DataFrame(rows)


# ===========================================================================
# First-vs-second peak angle pairs (Phase 7a.4-cross-session-angle
# Addendum #11 Part B)
# ===========================================================================


def extract_first_vs_second_peak_pairs(
    df_bouts: pd.DataFrame,
) -> pd.DataFrame:
    """Per (trial, side), extract the angle of the first two
    chronologically-detected lick peaks.

    Phase 7a.4-cross-session-angle Addendum #11 Part B (2026-05-04).

    Used by the per-session ``first_vs_second_peak_scatter`` plot
    family (and the forthcoming cross-session aggregator) to
    visualize the per-trial pairing of peak[0] and peak[1] angles
    — direct view of the warming-up first-lick vs settled second-
    lick angle phenotype.

    "First two peaks" semantic:
      Per (trial_index, side), take the two chronologically-
      earliest per-peak rows in ``df_bouts`` (``peak_t_ms.notna()``)
      regardless of bout structure (multi-bout vs isolated). This
      matches the post-#15 centered-phase plot convention where
      "first lick" means the chronologically-first detected peak.
      Trials with fewer than 2 detected peaks total contribute
      nothing.

    Parameters
    ----------
    df_bouts : DataFrame
        Mixed bout-summary + per-peak rows from
        :class:`TongueVisualBundle.df_bouts`. Per-peak rows have
        ``peak_t_ms.notna()``; this helper consumes only those.

    Returns
    -------
    DataFrame
        One row per (trial_index, side) with columns:
          - ``side``
          - ``trial_index``
          - ``peak0_t_ms``      first peak time
          - ``peak0_angle_deg`` first peak angle (degrees)
          - ``peak1_t_ms``      second peak time
          - ``peak1_angle_deg`` second peak angle (degrees)
        Empty DataFrame (with these columns) if ``df_bouts`` is
        empty or has no eligible (≥2-peak) trials.
    """
    cols = (
        "side", "trial_index",
        "peak0_t_ms", "peak0_angle_deg",
        "peak1_t_ms", "peak1_angle_deg",
    )
    if df_bouts.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype=(int if c == "trial_index" else (
                object if c == "side" else float)
            )) for c in cols}
        )
    per_peak = df_bouts[
        df_bouts["peak_t_ms"].notna()
    ][["trial_index", "side", "peak_t_ms", "peak_angle_deg"]].sort_values(
        ["trial_index", "side", "peak_t_ms"],
    )
    if per_peak.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype=(int if c == "trial_index" else (
                object if c == "side" else float)
            )) for c in cols}
        )

    rows: list[dict[str, Any]] = []
    for (trial_idx, side), grp in per_peak.groupby(
        ["trial_index", "side"], sort=False,
    ):
        if len(grp) < 2:
            continue
        first_two = grp.iloc[:2]
        rows.append({
            "side": str(side),
            "trial_index": int(trial_idx),
            "peak0_t_ms": float(first_two.iloc[0]["peak_t_ms"]),
            "peak0_angle_deg": float(first_two.iloc[0]["peak_angle_deg"]),
            "peak1_t_ms": float(first_two.iloc[1]["peak_t_ms"]),
            "peak1_angle_deg": float(first_two.iloc[1]["peak_angle_deg"]),
        })

    if not rows:
        return pd.DataFrame(
            {c: pd.Series(dtype=(int if c == "trial_index" else (
                object if c == "side" else float)
            )) for c in cols}
        )
    return pd.DataFrame(rows, columns=list(cols))


# ===========================================================================
# Per-animal pre-stroke median ILI (Phase 7a.4-cross-session-angle Addendum #12)
# ===========================================================================
#
# The synthetic cycle width for isolated licks (and last-peak-of-bout
# in centered-phase plots under Addendum #12) is the per-animal
# pre-stroke median ILI in ms. Walking pre-stroke sessions to compute
# this median is expensive; the cache below makes repeated lookups for
# the same animal O(1).


_PRE_STROKE_MEDIAN_ILI_CACHE: dict[str, float] = {}


def compute_pre_stroke_median_ili_ms(
    animal: str,
    *,
    resolver: PathResolver,
    animal_info: AnimalInfo | None = None,
    params: dict[str, Any] | None = None,
) -> float:
    """Per-animal pre-stroke median multi-bout ILI in milliseconds.

    Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04) — supplies
    the synthetic cycle width for isolated-lick (and last-peak-of-
    multi-bout) cycles in the centered-phase plots, so isolated licks
    plot at the animal's natural pre-stroke lick rate even when no
    forward-neighboring peak exists.

    Algorithm:
      1. Enumerate session dates from on-disk
         ``tongue_pertrial_endpoints_json`` paths (= 7a.3 V3 emit set
         dates).
      2. Filter to ``rel_day <= 0`` (pre-stroke; Addendum #17:
         ``rel_day == 0`` = day of stroke induction, recording done
         BEFORE stroke earlier that day, so d0 is pre-stroke per
         project-wide convention) via
         :meth:`AnimalInfo.day_relative_to_stroke`.
      3. For each pre-stroke session, build a
         :class:`TongueVisualBundle` (without recursive median ILI
         computation — pass ``pre_stroke_median_ili_ms=float("nan")``)
         and extract per-multi-bout inter-peak intervals
         (``peak[i + 1] - peak[i]`` for adjacent peaks in the same
         multi-bout).
      4. Return the median across all collected ILIs.

    Returns ``float("nan")`` if the animal has no pre-stroke sessions
    on disk OR no multi-bouts contributed any ILI. Callers (renderers
    + dispatcher) interpret NaN as "fall back to multi-bout-only
    behaviour" (i.e., no isolated-lick contribution).

    Note: this function builds bundles for every pre-stroke session
    sequentially. Cost is roughly N_sessions × bundle_build_time
    (~5 s each). For repeated lookups, prefer
    :func:`get_pre_stroke_median_ili_ms` which caches per animal.
    """
    if params is None:
        params = load_defaults()
    if animal_info is None:
        animal_info = get_animal(animal)

    endpoints_dir = resolver.tongue_pertrial_endpoints_dir(animal)
    if not endpoints_dir.exists():
        return float("nan")

    pre_dates: list[datetime.date] = []
    for p in sorted(endpoints_dir.glob("*.json")):
        m = re.match(r"(\d{8})\.json$", p.name)
        if m is None:
            continue
        d = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        try:
            rel_day = int(animal_info.day_relative_to_stroke(d))
        except Exception:
            continue
        # Addendum #17 (2026-05-04): d0 is pre-stroke (recording done
        # before stroke induction earlier that day). Pre-stroke =
        # rel_day <= 0 (was rel_day < 0 pre-#17).
        if rel_day <= 0:
            pre_dates.append(d)

    if not pre_dates:
        return float("nan")

    all_ilis_ms: list[float] = []
    for d in pre_dates:
        try:
            manifest = build_manifest(
                animal, d, resolver, animal_info,
                analysis_context="dlc.kinematics.tongue_pertrial",
            )
        except Exception:
            continue
        try:
            trial_events = _derive_trial_events_from_spout_behavior(
                animal=animal, date=d, resolver=resolver, manifest=manifest,
            )
        except Exception:
            continue
        try:
            bundle = build_tongue_visual_bundle(
                manifest=manifest, resolver=resolver,
                trial_events=trial_events, params=params,
                animal_info=animal_info,
                # Explicit NaN to short-circuit recursive computation
                # — this is the lower-level builder; the by-animal-date
                # wrapper is what populates the cohort scalar.
                pre_stroke_median_ili_ms=float("nan"),
            )
        except Exception:
            continue
        df_bouts = bundle.df_bouts
        if df_bouts.empty:
            continue
        per_peak = df_bouts[
            df_bouts["peak_t_ms"].notna()
            & df_bouts["multi_bout_rank"].notna()
        ][["trial_index", "side", "bout_idx", "peak_t_ms"]].sort_values(
            ["trial_index", "side", "bout_idx", "peak_t_ms"],
        )
        if per_peak.empty:
            continue
        for _key, grp in per_peak.groupby(
            ["trial_index", "side", "bout_idx"], sort=False,
        ):
            peak_times = np.asarray(
                grp["peak_t_ms"].to_numpy(), dtype=np.float64,
            )
            if peak_times.size < 2:
                continue
            for j in range(peak_times.size - 1):
                ili = float(peak_times[j + 1] - peak_times[j])
                if np.isfinite(ili) and ili > 0:
                    all_ilis_ms.append(ili)

    if not all_ilis_ms:
        return float("nan")
    return float(np.median(all_ilis_ms))


def get_pre_stroke_median_ili_ms(
    animal: str,
    *,
    resolver: PathResolver,
    animal_info: AnimalInfo | None = None,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> float:
    """Cached wrapper around :func:`compute_pre_stroke_median_ili_ms`.

    Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04). Caches
    per-animal results in a module-level dict to avoid repeated
    cross-session walks across multiple bundle builds for the same
    animal in a single process. Pass ``use_cache=False`` to force
    recomputation (e.g., in tests).
    """
    if use_cache and animal in _PRE_STROKE_MEDIAN_ILI_CACHE:
        return _PRE_STROKE_MEDIAN_ILI_CACHE[animal]
    value = compute_pre_stroke_median_ili_ms(
        animal, resolver=resolver,
        animal_info=animal_info, params=params,
    )
    if use_cache:
        _PRE_STROKE_MEDIAN_ILI_CACHE[animal] = value
    return value


# ===========================================================================
# Public API
# ===========================================================================


def build_tongue_pertrial(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    params: dict[str, Any] | None = None,
    *,
    overwrite: Literal["skip", "force"] = "skip",
    animal_info: AnimalInfo | None = None,
) -> dict[str, Path] | None:
    """Build tongue per-trial features for one session.

    Writes three files atomically (per-frame angle parquet, per-session × side
    licking-dynamics traces parquet, per-trial endpoints JSON). Returns a dict
    of paths or ``None`` if ``overwrite="skip"`` AND all three already exist.

    ``trial_events`` is REQUIRED. It is not resolvable from a
    :class:`SessionManifest` alone (manifest carries DLC files + alignment
    template, not tone-onset times). Callers must derive it from upstream
    spout_behavior products (Q7 lock 2026-04-28; Task 5 parity-harness
    wrapper does this for cohort runs).

    Parameters
    ----------
    manifest
        Session manifest (provides ``animal``, ``date``).
    resolver
        Configured PathResolver. Output paths via
        :meth:`PathResolver.tongue_pertrial_*`; input parquets via
        :meth:`PathResolver.dlc_centered_spout_midpoint_parquet` and
        :meth:`PathResolver.interpolated_trace`.
    trial_events
        Sequence of :class:`TrialEvent` (one per trial) — required.
    params
        Loaded :func:`load_defaults` block. If ``None``, loads the repo
        default.
    overwrite
        ``"skip"`` returns existing paths if all three exist. ``"force"``
        always rewrites.
    animal_info
        Optional :class:`AnimalInfo`. If ``None``, loaded via
        :func:`get_animal`.

    Returns
    -------
    dict[str, Path] | None
        Keys: ``"angle_parquet"``, ``"licking_dynamics_traces_parquet"``,
        ``"endpoints_json"``. ``None`` only when ``overwrite="skip"`` and
        all three target files already exist.

    Raises
    ------
    KeyError
        If ``params`` is missing the ``dlc_kinematics.tongue_pertrial:`` block.
    FileNotFoundError
        If the upstream tongue interpolated_traces or centered_spout_midpoint
        parquet is missing for ``(animal, date)``.
    RuntimeError
        From :func:`_resolve_eye_midpoint_session_median` if the spout-frame
        sanity check fails (input parquet not in spout-centered frame, V3
        Task 1.5 finding).
    """
    if overwrite not in ("skip", "force"):
        raise ValueError(f"overwrite must be 'skip' or 'force'; got {overwrite!r}.")

    if animal_info is None:
        animal_info = get_animal(manifest.animal)
    if manifest.excluded:
        return None

    if params is None:
        params = load_defaults()

    out_paths = {
        "angle_parquet": resolver.tongue_pertrial_angle_parquet(
            manifest.animal, manifest.date,
        ),
        "licking_dynamics_traces_parquet":
            resolver.tongue_pertrial_licking_dynamics_traces_parquet(
                manifest.animal, manifest.date,
            ),
        "endpoints_json": resolver.tongue_pertrial_endpoints_json(
            manifest.animal, manifest.date,
        ),
    }

    if overwrite == "skip" and all(p.exists() for p in out_paths.values()):
        return out_paths

    core = _build_tongue_pertrial_core(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        params=params,
        animal_info=animal_info,
    )
    tp_result = core.tongue_pertrial

    _write_angle_parquet_atomic(
        out_paths["angle_parquet"],
        tp_result.angle_per_frame,
        tp_result.angle_metadata,
    )
    _write_traces_parquet_atomic(
        out_paths["licking_dynamics_traces_parquet"],
        tp_result.licking_dynamics_traces,
        tp_result.licking_dynamics_metadata,
    )
    _write_endpoints_json_atomic(out_paths["endpoints_json"], tp_result.endpoints)

    return out_paths


def build_tongue_visual_bundle(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    params: dict[str, Any] | None = None,
    *,
    animal_info: AnimalInfo | None = None,
    pre_stroke_median_ili_ms: float | None = None,
) -> TongueVisualBundle:
    """Phase 7a.4 — return the in-memory per-trial array DataFrames for the
    Cell 50 visual gate.

    Same compute path as :func:`build_tongue_pertrial` — calls the same
    :func:`_build_tongue_pertrial_core`, then projects the
    :attr:`_PertrialCoreResult.visual_bundle` field. No on-disk artifacts
    are written; the 7a.3 V3 emit set is unaffected.

    Parameters mirror :func:`build_tongue_pertrial` (manifest, resolver,
    trial_events, params, animal_info), minus ``overwrite`` (no I/O to
    skip), plus ``pre_stroke_median_ili_ms`` (Phase
    7a.4-cross-session-angle Addendum #12) — explicit per-animal
    synthetic ILI scalar. Stored at
    ``bundle.metadata["pre_stroke_median_ili_ms"]`` for downstream
    centered-phase helpers; defaults to ``NaN`` (= "fall back to
    multi-bout-only behaviour"). The by-animal-date wrapper
    :func:`build_tongue_visual_bundle_by_animal_date` populates this
    value via :func:`get_pre_stroke_median_ili_ms` (cached) when not
    supplied.

    Returns
    -------
    TongueVisualBundle
        See :class:`TongueVisualBundle` for field documentation.
    """
    if animal_info is None:
        animal_info = get_animal(manifest.animal)
    if params is None:
        params = load_defaults()
    core = _build_tongue_pertrial_core(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        params=params,
        animal_info=animal_info,
        pre_stroke_median_ili_ms=pre_stroke_median_ili_ms,
    )
    return core.visual_bundle


def build_tongue_visual_bundle_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    trial_events: Sequence[TrialEvent] | None = None,
    **kwargs: Any,
) -> TongueVisualBundle:
    """Convenience wrapper analogous to
    :func:`build_tongue_pertrial_by_animal_date`. Auto-derives
    ``trial_events`` from upstream spout_behavior products if not passed.

    Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04): if
    ``pre_stroke_median_ili_ms`` is not supplied via ``kwargs``, the
    per-animal cohort scalar is computed (or read from cache) via
    :func:`get_pre_stroke_median_ili_ms` and injected into the bundle
    metadata. Cohort-mode callers can pass the precomputed value
    explicitly to skip the per-call cache lookup.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.tongue_pertrial",
    )
    if trial_events is None:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
    kwargs.setdefault("animal_info", animal_info)
    if "pre_stroke_median_ili_ms" not in kwargs:
        kwargs["pre_stroke_median_ili_ms"] = get_pre_stroke_median_ili_ms(
            animal, resolver=resolver, animal_info=animal_info,
            params=kwargs.get("params"),
        )
    return build_tongue_visual_bundle(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        **kwargs,
    )


def build_tongue_pertrial_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    trial_events: Sequence[TrialEvent] | None = None,
    **kwargs: Any,
) -> dict[str, Path] | None:
    """Build tongue per-trial features from ``(animal, date)`` — manifests internally.

    Convenience wrapper analogous to
    :func:`build_interpolated_trace_by_animal_date`. If ``trial_events``
    is ``None`` (default), they are auto-derived via
    :func:`_derive_trial_events_from_spout_behavior` from the consolidated
    ``licks_and_rewards`` NPZ + cam2 alignment template (see Task 5.0,
    2026-04-28). Callers that want explicit control may still pass an
    explicit list.
    """
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.tongue_pertrial",
    )
    if trial_events is None:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
    kwargs.setdefault("animal_info", animal_info)
    return build_tongue_pertrial(
        manifest=manifest,
        resolver=resolver,
        trial_events=trial_events,
        **kwargs,
    )


# ===========================================================================
# Trial-events auto-derive (Task 5.0, 2026-04-28)
# ===========================================================================


def _derive_trial_events_from_spout_behavior(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    manifest: SessionManifest,
) -> list[TrialEvent]:
    """Auto-derive per-trial tone-onset frame + side from upstream pipeline products.

    Mirrors legacy's ``Z["fr_reward_mouseL"]`` / ``Z["fr_reward_mouseR"]``
    semantics by re-deriving at consume time (legacy NPZ-key citations
    preserved). The 7a.2 consolidated parquet deliberately drops the
    legacy tone-onset arrays per §5 Option A pure-bodypart schema, so
    7a.3 reads the consolidated ``licks_and_rewards`` NPZ + cam2
    alignment template and reapplies the WS→cam translation. No new
    alignment code: this is a thin orchestration of public helpers
    already battle-tested by Phase 6 + 7a.2's
    :func:`_load_tone_centers_cam`.

    ``trial_index`` is **chronological-across-sides** (Option α lock 2026-04-28):
    tone events are sorted by ``tone_frame_idx`` (field name preserved;
    semantically tone-onset under Case-2 universal) and assigned globally
    unique ``trial_index = 0..N-1``. Per-side enumeration (legacy parity)
    is the parity harness's responsibility (sort-by-(side, tone_frame_idx)
    → re-key).

    Side translation: NOT applied here. The licks NPZ keys ``Tone_L`` /
    ``Tone_R`` are already in mouse-frame coords post task #17 re-emit
    + Phase 8a.10.1 swap-fix (Phase 6.8 boundary at Phase 2 emit).
    :func:`load_tone_events` validates the ``side_convention_version=1``
    + ``wavesurfer_sides_match_mouse_sides`` stamps and raises on
    pre-task-#17 NPZs — let it raise its own error (don't wrap or
    pre-validate).

    Parameters
    ----------
    animal, date
        Session identifiers.
    resolver
        Configured PathResolver.
    manifest
        Session manifest. Used for ``manifest.wavesurfer_sides_match_mouse_sides``
        (cross-checked against the licks NPZ stamp inside ``load_tone_events``).

    Returns
    -------
    list[TrialEvent]
        Sorted by ``tone_frame_idx`` (field name preserved),
        ``trial_index`` 0-indexed contiguous.

    Raises
    ------
    FileNotFoundError
        If the licks NPZ, the alignment template, or the upstream tongue
        parquet is missing.
    ValueError
        If any ``tone_frame_idx`` value falls outside ``[0, n_frames)``
        after the WS→cam translation. (``load_tone_events`` raises
        ValueError on its own for pre-task-#17 / mismatched-stamp NPZs
        — propagated.)
    """
    # 1. n_frames from the upstream tongue parquet metadata (must match the
    #    cam-frame count the alignment LUT was built for).
    tongue_path = resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    if not tongue_path.exists():
        raise FileNotFoundError(
            f"7a.2 tongue interpolated_traces parquet missing for "
            f"{animal}/{date.isoformat()}: expected at {tongue_path}. "
            f"Run build_interpolated_trace first.",
        )
    schema = pq.read_schema(tongue_path)
    raw_meta = schema.metadata or {}
    n_frames_meta = raw_meta.get(b"n_frames")
    if n_frames_meta is None:
        raise ValueError(
            f"7a.2 tongue parquet at {tongue_path} missing 'n_frames' "
            f"metadata key (expected per the 7a.2 schema lock).",
        )
    n_frames = int(n_frames_meta)

    # 2. Phase 2 licks_and_rewards NPZ path via the Phase 7d (Addendum #4)
    #    spout_licks_and_rewards_npz resolver method.
    date_str = date.strftime("%Y%m%d")
    licks_path = resolver.spout_licks_and_rewards_npz(animal, date)

    # 3. Alignment template (cam2 — same fallback chain as 7a.2's
    #    _load_tone_centers_cam: prefer manifest if set, else resolver).
    align_path = manifest.alignment_template
    if align_path is None or not align_path.exists():
        align_path = resolver.alignment_template_for_reading(animal, date, cam="cam2")
    if not align_path.exists():
        raise FileNotFoundError(
            f"{animal}/{date_str}: cam2 alignment template missing at "
            f"{align_path}. Run scripts/make_alignment_templates.py.",
        )

    from stroke_orofacial.alignment.templates import load_alignment_template
    from stroke_orofacial.dlc_spatial.tone_aligned import (
        load_tone_events,
        ws_samples_to_frame_indices,
    )

    aln = load_alignment_template(align_path)
    sig_camIdx__idx_ws = aln["sig_camIdx__idx_ws"]

    # 4-5. Per-side: load WS tone-onset indices (X1-β rename
    # 2026-05-14; semantically tone-anchored under Case-2 universal,
    # with side-stamp validation), translate to cam frames, drop
    # invalid (-1). Local variable `ws_idx` carries tone-onset
    # samples; legacy name kept under Phase 7b deferral.
    events: list[tuple[int, str]] = []  # (tone_frame_idx, side)
    for side in ("L", "R"):
        ws_idx = load_tone_events(
            licks_path, trial_group=side,
            wavesurfer_sides_match_mouse_sides=(
                manifest.wavesurfer_sides_match_mouse_sides
            ),
        )
        if len(ws_idx) == 0:
            continue
        cam_frames = ws_samples_to_frame_indices(
            ws_idx, sig_camIdx__idx_ws, n_cam_frames=n_frames,
        )
        for f in cam_frames:
            if f < 0:
                continue  # invalid translation; legacy `centers >= 0` filter
            if f >= n_frames:
                raise ValueError(
                    f"{animal}/{date_str}: tone_frame_idx={f} >= n_frames"
                    f"={n_frames} after WS→cam translation. The alignment "
                    f"LUT may be out of sync with the tongue parquet's "
                    f"n_frames metadata.",
                )
            events.append((int(f), side))

    # 6-7. Sort chronologically across sides; assign globally unique trial_index.
    events.sort(key=lambda ev: ev[0])
    return [
        TrialEvent(trial_index=k, tone_frame_idx=fr, side=sd)
        for k, (fr, sd) in enumerate(events)
    ]


# ===========================================================================
# Loaders
# ===========================================================================


def _load_tongue_centered_trace(
    manifest: SessionManifest, resolver: PathResolver,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Read the 7a.2 tongue interpolated_traces parquet for this session.

    Returns the dataframe (``frame_idx``, ``x_final``, ``y_final``,
    ``likelihood_raw``, ...) and the file-level metadata as a dict.
    """
    path = resolver.interpolated_trace(
        bodypart="tongue", animal=manifest.animal, date=manifest.date,
    )
    if not path.exists():
        raise FileNotFoundError(
            f"7a.2 tongue interpolated_traces parquet missing for "
            f"{manifest.animal}/{manifest.date.isoformat()}: expected at {path}. "
            f"Run build_interpolated_trace first.",
        )
    df = pd.read_parquet(path)
    schema = pq.read_schema(path)
    raw_meta = schema.metadata or {}
    meta: dict[str, str] = {}
    for k, v in raw_meta.items():
        try:
            meta[k.decode("utf-8")] = v.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            meta[k.decode("utf-8")] = repr(v)
    return df, meta


def _load_consolidated_eye_landmarks(
    manifest: SessionManifest, resolver: PathResolver,
) -> pd.DataFrame:
    """Read the consolidated centered_spout_midpoint parquet (Task 1.5 verified).

    Returns the full 39-col float32 DataFrame; the eye-midpoint resolver
    casts only the columns it consumes to float64. Reuses
    :func:`stroke_orofacial.dlc_io.parquet.read_centered_parquet` (a clean
    path-based reader) rather than 7a.2's ``_load_centered_df`` (manifest-
    coupled, asserts a single bodypart's 3 columns) — per V3 Q2 sign-off.
    """
    from stroke_orofacial.dlc_io.parquet import read_centered_parquet

    path = resolver.dlc_centered_spout_midpoint_parquet(
        animal=manifest.animal, date=manifest.date,
    )
    return read_centered_parquet(path)


def _resolve_eye_midpoint_session_median(
    eye_df: pd.DataFrame, *, params: dict[str, Any],
) -> tuple[float, float]:
    """Cell 50 eye-resolution: 7-step algorithm per V3 kickoff §1.5c Branch A.

    Steps (Task 1.5 lock 2026-04-28):

    1. Cast eye + spout columns float32 → float64 (numerical stability).
    2. **Spout-frame sanity check:** assert
       ``|0.5 * (median(L_spout) + median(R_spout))| <= spout_frame_origin_tol_px``
       on both x and y. The input parquet has no ``center_mode`` metadata,
       so verify empirically; raise on failure (fail loud rather than emit
       angles in the wrong frame).
    3. Filter to frames where both eyes have ``likelihood >= eye_lik_thr``
       AND all four x/y values are finite.
    4. Require ``>= min_valid_eye_frames`` valid frames. If fewer AND
       ``allow_one_eye_fallback``, fall back to per-eye-only median (each
       eye uses its own valid-frame mask independently).
    5. Compute per-eye medians.
    6. ``eye_in_spout_frame = 0.5 * (median_L + median_R)``.
    7. **Return directly.** No translation step (data is already in
       spout-centered frame, verified upstream).
    """
    angle_params = params["dlc_kinematics"]["tongue_pertrial"]["angle"]
    eye_lik_thr = float(angle_params["eye_likelihood_threshold"])
    min_valid = int(angle_params["min_valid_eye_frames"])
    allow_fallback = bool(angle_params["allow_one_eye_fallback"])
    spout_tol = float(angle_params["spout_frame_origin_tol_px"])

    # Step 1: cast float32 → float64.
    needed_cols = (
        "L_eye_x", "L_eye_y", "L_eye_likelihood",
        "R_eye_x", "R_eye_y", "R_eye_likelihood",
        "L_spout_x", "L_spout_y", "L_spout_likelihood",
        "R_spout_x", "R_spout_y", "R_spout_likelihood",
    )
    for col in needed_cols:
        if col not in eye_df.columns:
            raise KeyError(
                f"Eye-landmark parquet missing required column {col!r}. "
                f"Task 1.5 verified the schema includes these; an upstream "
                f"re-emit may have changed it.",
            )
    arrs: dict[str, np.ndarray] = {
        col: eye_df[col].to_numpy(dtype=np.float64, copy=True)
        for col in needed_cols
    }

    # Step 2: spout-frame sanity check (C5.6, 2026-04-29). Filter L_spout
    # / R_spout medians by likelihood >= eye_lik_thr to match the upstream
    # centering algorithm's quality bar (see
    # ``src/stroke_orofacial/dlc_io/centering.py:_median_from_lik``, which
    # uses the same default threshold of 0.7). Without this filter, sessions
    # where one spout has low-likelihood DLC drift to the OTHER spout's
    # location (e.g. PS55/2025-05-02 R_spout: 92% of frames are low-lik
    # and drifted to L_spout's image x ≈ 472, pulling the median off-center
    # to +67 px) would erroneously fail this check even though the upstream
    # centering correctly used only high-lik frames.
    L_spout_mask = (
        (arrs["L_spout_likelihood"] >= eye_lik_thr)
        & np.isfinite(arrs["L_spout_x"])
        & np.isfinite(arrs["L_spout_y"])
    )
    R_spout_mask = (
        (arrs["R_spout_likelihood"] >= eye_lik_thr)
        & np.isfinite(arrs["R_spout_x"])
        & np.isfinite(arrs["R_spout_y"])
    )
    n_L_spout = int(np.count_nonzero(L_spout_mask))
    n_R_spout = int(np.count_nonzero(R_spout_mask))
    if n_L_spout < min_valid or n_R_spout < min_valid:
        raise RuntimeError(
            f"Spout-frame sanity check: insufficient high-likelihood spout "
            f"frames (n_L={n_L_spout}, n_R={n_R_spout}, "
            f"min={min_valid}); cannot verify centering."
        )
    spout_mid_x = 0.5 * (
        float(np.nanmedian(arrs["L_spout_x"][L_spout_mask]))
        + float(np.nanmedian(arrs["R_spout_x"][R_spout_mask]))
    )
    spout_mid_y = 0.5 * (
        float(np.nanmedian(arrs["L_spout_y"][L_spout_mask]))
        + float(np.nanmedian(arrs["R_spout_y"][R_spout_mask]))
    )
    if abs(spout_mid_x) > spout_tol or abs(spout_mid_y) > spout_tol:
        raise RuntimeError(
            f"Spout-frame sanity check failed: high-likelihood spout "
            f"midpoint at ({spout_mid_x:.3f}, {spout_mid_y:.3f}) is "
            f"outside ±{spout_tol} px of origin. The input parquet does "
            f"not appear to be in the spout-centered frame V3 design "
            f"assumes (Task 1.5 lock).",
        )

    # Step 3: per-eye finite/likelihood masks.
    mask_L = (
        (arrs["L_eye_likelihood"] >= eye_lik_thr)
        & np.isfinite(arrs["L_eye_x"])
        & np.isfinite(arrs["L_eye_y"])
    )
    mask_R = (
        (arrs["R_eye_likelihood"] >= eye_lik_thr)
        & np.isfinite(arrs["R_eye_x"])
        & np.isfinite(arrs["R_eye_y"])
    )

    # Step 4: enforce min_valid; fall back to per-eye-only median if needed.
    n_both = int(np.count_nonzero(mask_L & mask_R))
    n_L = int(np.count_nonzero(mask_L))
    n_R = int(np.count_nonzero(mask_R))
    if n_both >= min_valid:
        valid_mask_L = valid_mask_R = mask_L & mask_R
    elif allow_fallback and n_L >= min_valid and n_R >= min_valid:
        valid_mask_L = mask_L
        valid_mask_R = mask_R
    else:
        raise RuntimeError(
            f"Cell 50 eye_midpoint resolution failed: "
            f"n_both={n_both}, n_L={n_L}, n_R={n_R}, min_valid={min_valid}, "
            f"allow_one_eye_fallback={allow_fallback}.",
        )

    # Steps 5-6: per-eye medians, then 0.5 * (L + R).
    median_L_x = float(np.median(arrs["L_eye_x"][valid_mask_L]))
    median_L_y = float(np.median(arrs["L_eye_y"][valid_mask_L]))
    median_R_x = float(np.median(arrs["R_eye_x"][valid_mask_R]))
    median_R_y = float(np.median(arrs["R_eye_y"][valid_mask_R]))
    eye_x = 0.5 * (median_L_x + median_R_x)
    eye_y = 0.5 * (median_L_y + median_R_y)

    # Step 7: return directly. No translation (data is already spout-centered).
    return eye_x, eye_y


# ===========================================================================
# Phase 7e v7 pipeline orchestrator (Task 5)
# ===========================================================================


def _legacy_peaks_to_peak_list(
    legacy: Any, detector_params: dict[str, Any], fps: float,
) -> Any:
    """Task 5c adapter: convert :class:`._detector._LickPeaks` (legacy
    detector output) → :class:`._detector_v2._PeakList` (v7 dedupe
    input shape).

    The legacy ``_LickPeaks`` has ``rise_starts`` + ``turnover`` +
    ``peak_indices`` (post-Task-5c also ``fall_ends``); the v7
    ``_PeakList`` needs ``peak_indices`` + ``rise_starts`` +
    ``fall_ends``. We copy the fields directly; ``turnover`` (= dy-
    crosses-zero frame ≈ peak frame) isn't carried into the v7 shape.

    If the legacy output's ``fall_ends`` is empty (backwards-compat
    edge case for callers that don't populate it), falls back to a
    ``i_peak + peak_pad_n`` approximation so dedupe still gets a
    sensible value.
    """
    if len(legacy) == 0:
        return _PeakList_v2.empty()
    fall_ends_legacy = legacy.fall_ends
    if len(fall_ends_legacy) == len(legacy.peak_indices):
        fall_ends_out = fall_ends_legacy
    else:
        # Backwards-compat fallback — approximate via peak_pad_n
        peak_pad_n = max(1, int(round(
            float(detector_params["peak_pad_ms"]) / 1000.0 * fps,
        )))
        fall_ends_out = legacy.peak_indices + peak_pad_n
    return _PeakList_v2(
        peak_times_ms=legacy.peak_times_ms,
        peak_y=legacy.peak_y,
        peak_x=legacy.peak_x,
        peak_indices=legacy.peak_indices,
        rise_starts=legacy.rise_starts,
        fall_ends=fall_ends_out,
    )


def _run_v7_pipeline_per_trial(
    y_slice: np.ndarray,
    x_slice: np.ndarray,
    is_interp_fill_slice: np.ndarray,
    is_baseline_fill_slice: np.ndarray,
    likelihood_slice: np.ndarray,
    t_ms: np.ndarray,
    fps: float,
    *,
    trial_index: int,
    side: Literal["L", "R"],
    params: dict[str, Any],
) -> _V7TrialResult:
    """Run the full Phase 7e v7 pipeline on one trial slice.

    Composes ``_preclean.preclean_trace`` → ``_detector_v2.detect_local_maxima``
    → ``_detector_v2.merge_detector_outputs`` → ``_gates.gate_F`` /
    ``gate_D`` / ``gate_E`` (with parabolic/spline imputation per Decisions
    16-17) → ``_gates.run_m_gate`` (with Addendum #1 Rule 5 early-window
    relaxation).

    **Scope (Task 5 minimum):** uses ``detect_local_maxima`` alone. The
    scratch v7 ran three detectors (lmax + bounded + legacy) deduped via
    ``merge_detector_outputs``; bounded-fall + legacy are deferred to a
    follow-up (the lmax detector is the most accurate per Decision 14, so
    lmax-only is the safest minimum). When bounded-fall lands, add it to
    the ``peak_lists`` argument to ``merge_detector_outputs``.

    Returns a :class:`_V7TrialResult` carrying the cleaned trace +
    per-trial kept-lick records (the latter become rows in the
    ``lick_events/`` parquet per Decision 4, written by Task 6).
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    preclean_params = tp["preclean"]
    detector_params = tp["detector"]
    detector_v2_params = tp["detector_v2"]
    gates_params = tp["gates"]
    # Match scratch DETECT_WIN_MS (70-3000 ms); v7 metrics use the
    # same narrow window as the legacy lick1/lick2 extractor (Cell 33).
    detect_win_ms = tuple(tp["lick12_detect_win_ms"])

    n_frames = len(y_slice)

    # Stage 1: pre-clean (y-side + Addendum Rules 1-4 for x)
    y_clean, x_clean, is_base_clean, diag = _preclean_trace_v7(
        y_slice, x_slice, is_interp_fill_slice, is_baseline_fill_slice,
        n_frames, fps, params=preclean_params,
    )

    # Stage 2: run all three detectors per Decision 14 (Task 5c —
    # restored from Task 5's lmax-only deferral).
    # 1) detect_local_maxima (lmax) — find_peaks based, NEW for v7
    lmax_pl = _detect_local_maxima_v2(
        y=y_clean, x=x_clean, t_ms=t_ms, fps=fps,
        is_baseline_fill=is_base_clean,
        detect_win_ms=detect_win_ms,
        detector_params=detector_params,
        params=detector_v2_params,
    )
    # 2) bounded-fall — reuses _slope_detect_lick_peaks with the
    #    max_fall_search_ms + accept_implicit_baseline_fall knobs
    #    (Task 5c parameterization). max_fall_search_ms read from
    #    detector_v2 config block; the implicit-baseline-fall acceptance
    #    requires the cleaned baseline-fill mask. See scratch lines
    #    332-423 for the original detect_bounded_fall implementation
    #    that this configuration reproduces.
    bounded_detector_params = dict(detector_params)
    bounded_detector_params["max_fall_search_ms"] = float(
        detector_v2_params["max_fall_search_ms"]
    )
    bounded_detector_params["accept_implicit_baseline_fall"] = True
    # Bounded-fall doesn't use strict_no_fallback rejection — it has its
    # own conditional acceptance path via implicit baseline fall. Keep
    # strict_no_fallback aligned with scratch's behavior (True; the
    # implicit_baseline_fall path overrides it when applicable).
    bounded_legacy = _slope_detect_lick_peaks_legacy(
        y_t=y_clean, x_t=x_clean, t_ms=t_ms, fps=fps,
        detect_win_ms=detect_win_ms,
        detector_params=bounded_detector_params,
        n_max=None,
        is_baseline_fill=is_base_clean,
    )
    bounded_pl = _legacy_peaks_to_peak_list(bounded_legacy, detector_params, fps)
    # 3) legacy slope detector — unchanged behavior (no bounded-fall knobs)
    legacy_legacy = _slope_detect_lick_peaks_legacy(
        y_t=y_clean, x_t=x_clean, t_ms=t_ms, fps=fps,
        detect_win_ms=detect_win_ms,
        detector_params=detector_params,
        n_max=None,
    )
    legacy_pl = _legacy_peaks_to_peak_list(legacy_legacy, detector_params, fps)

    # Stage 2.5: cross-detector dedupe per Decision 14. Processing
    # order lmax → bounded → legacy; lmax wins on overlap (most
    # accurate peak location).
    merged_peaks = _merge_detector_outputs_v2(
        [
            ("lmax", lmax_pl),
            ("bounded", bounded_pl),
            ("legacy", legacy_pl),
        ],
        likelihood=likelihood_slice,
        fps=fps,
        params=detector_v2_params,
    )

    # Convert _DetectedPeak list to scratch-shaped decision dicts so
    # gate_E + run_m_gate (which expect dict access) can iterate.
    # The decision dict's "peak_frame_local" is trial-slice-local.
    decisions: list[dict[str, Any]] = []
    for rank, p in enumerate(merged_peaks):
        decisions.append({
            "rank": rank,
            "src": p.source,
            "peak_frame_local": p.frame,
            "t_ms": p.t_ms,
            "y": p.y,
            "lik": p.likelihood,
            "rise_start_frame": p.rise_start_frame,
            "fall_end_frame": p.fall_end_frame,
            "keep": True,
            "imputed": False,
            "gate": "",
            "reason": "",
        })

    # Stage 3: per-peak F → D → E with parabolic/spline imputation.
    # E runs ONLY for the first un-promoted peak (Decision 17).
    promoted: dict[str, Any] | None = None
    min_peak_y_abs = float(detector_params["min_peak_y_abs"])
    for r in decisions:
        pf = r["peak_frame_local"]
        F_rej, F_reason, F_std = _gate_F_v7(
            y_clean, is_interp_fill_slice, is_base_clean, pf, n_frames, fps,
            params=gates_params,
        )
        if F_rej:
            r["keep"] = False
            r["reason"] = F_reason
            r["gate"] = "F"
            r["wp_raw_std"] = F_std
            continue
        keep_D, reason_D = _gate_D_v7(
            y_clean, is_interp_fill_slice, is_base_clean, pf, n_frames, fps,
            params=gates_params,
        )
        if not keep_D:
            r["keep"] = False
            r["reason"] = reason_D
            r["gate"] = "D"
            r["wp_raw_std"] = F_std
            continue
        if promoted is None:
            peer_ys = [pr["y"] for pr in decisions if pr["rank"] != r["rank"]]
            E_rej, E_reason, z, peer_med = _gate_E_v7(
                r["y"], r["lik"], peer_ys, params=gates_params,
            )
            if E_rej:
                # Parabolic first (Decision 16), spline fallback. Both
                # take x_slice and return new_peak_x via wide-anchor
                # PCHIP with the outlier excise window excluded (Task
                # 5b correction of Decision 6 — see Addendum #1 footer).
                # NOTE: x is passed as x_slice (the raw Phase 7a.2 PCHIP
                # x_final at the trial slice), NOT x_clean. The excise
                # mechanism needs the original PCHIP values so it can
                # rebuild a corrected x at new_peak_frame from anchors
                # that exclude the outlier window.
                spline = _parabolic_excise_v7(
                    y_clean, x_slice, is_interp_fill_slice, is_base_clean, pf,
                    n_frames, fps, params=gates_params,
                )
                if spline is None:
                    spline = _spline_excise_v7(
                        y_clean, x_slice, is_interp_fill_slice, is_base_clean, pf,
                        n_frames, fps, params=gates_params,
                    )
                if spline is None:
                    r["keep"] = False
                    r["reason"] = "E_spline_no_anchors"
                    r["gate"] = "E_spline_drop"
                    r["z"] = z
                    continue
                if spline["new_peak_y"] < min_peak_y_abs:
                    r["keep"] = False
                    r["reason"] = f"E_spline_low_y new={spline['new_peak_y']:.1f}"
                    r["gate"] = "E_spline_drop"
                    r["z"] = z
                    continue
                # Impute: replace y + peak_frame; track original;
                # carry new_peak_x for the kept-lick builder below
                r["y_original"] = r["y"]
                r["y"] = float(spline["new_peak_y"])
                r["peak_frame_local"] = int(spline["new_peak_frame"])
                r["new_peak_x"] = float(spline.get("new_peak_x", float("nan")))
                r["imputed"] = True
                r["gate"] = "E_spline_impute"
                r["reason"] = (
                    f"E_spline_imputed (orig y={r['y_original']:.0f} "
                    f"-> {r['y']:.0f})"
                )
                r["z"] = z
                promoted = r
                continue
        # Keep with no imputation
        r["wp_raw_std"] = F_std if "wp_raw_std" not in r else r["wp_raw_std"]
        if promoted is None:
            promoted = r

    # Stage 4: M-gate (with Addendum #1 Rule 5 early-window relaxation).
    promoted = _run_m_gate_v7(
        decisions, y_clean, likelihood_slice,
        is_interp_fill_slice, is_base_clean,
        n_frames, fps, promoted, params=gates_params,
    )

    # Stage 5: build per-trial kept-lick records (Decision 4 schema minus
    # session-level fields). x at the (possibly imputed) peak_frame_local
    # comes from x_clean (trace-level x pre-clean per Addendum Rules 1-4
    # is canonical — Decision 6 RESOLVED).
    conf_radius_ms = float(gates_params["m_conf_radius_ms"])
    conf_radius = max(1, int(round(conf_radius_ms / 1000.0 * fps)))
    kept_licks: list[dict[str, Any]] = []
    lick_idx = 0
    for r in decisions:
        if not r["keep"]:
            continue
        pf = int(r["peak_frame_local"])
        # Peak confidence per Decision 2 (same formula as M-gate)
        lo = max(0, pf - conf_radius)
        hi = min(n_frames, pf + conf_radius + 1)
        raw_in_win = (~is_interp_fill_slice[lo:hi]) & (~is_base_clean[lo:hi])
        n_raw_in_win = int(raw_in_win.sum())
        if n_raw_in_win == 0:
            confidence = 0.0
        else:
            mean_lik = float(np.mean(likelihood_slice[lo:hi][raw_in_win]))
            confidence = n_raw_in_win * mean_lik
        rise_start_frame = r.get("rise_start_frame", -1)
        fall_end_frame = r.get("fall_end_frame", -1)
        rise_start_ms = (
            float(t_ms[rise_start_frame])
            if 0 <= rise_start_frame < n_frames else float("nan")
        )
        fall_end_ms = (
            float(t_ms[fall_end_frame])
            if 0 <= fall_end_frame < n_frames else float("nan")
        )
        # Task 5b: for imputed licks, prefer the excise-derived
        # new_peak_x (mirrors audit's local_pchip_x at the new peak
        # frame, with the outlier window excluded). Falls back to
        # cleaned_x[new_peak_frame] if the excise computation returned
        # NaN (too-few-anchors edge case). For non-imputed licks,
        # always use cleaned_x[new_peak_frame] (= the canonical
        # trace-level x per Addendum #1 Rules 1-4).
        is_imputed = bool(r.get("imputed", False))
        if is_imputed:
            new_peak_x = float(r.get("new_peak_x", float("nan")))
            if np.isfinite(new_peak_x):
                x_at_peak = new_peak_x
            elif 0 <= pf < n_frames:
                x_at_peak = float(x_clean[pf])
            else:
                x_at_peak = float("nan")
        else:
            x_at_peak = (
                float(x_clean[pf]) if 0 <= pf < n_frames else float("nan")
            )
        kept_licks.append({
            "lick_idx": lick_idx,
            "t_ms": float(r["t_ms"]),
            "y": float(r["y"]),
            "x": x_at_peak,
            "y_original": float(r.get("y_original", float("nan"))),
            "rise_start_ms": rise_start_ms,
            "fall_end_ms": fall_end_ms,
            "imputed": is_imputed,
            "source": str(r["src"]),
            "confidence": confidence,
            "likelihood": float(r["lik"]),
        })
        lick_idx += 1

    return _V7TrialResult(
        trial_index=trial_index,
        side=side,
        y_clean=y_clean,
        x_clean=x_clean,
        is_baseline_fill_clean=is_base_clean,
        t_ms=t_ms,
        kept_licks=kept_licks,
        preclean_diag=diag,
    )


def _extract_trial_slice(
    arr: np.ndarray, tone_frame_idx: int, win_ms: tuple[float, float], fps: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Slice ``arr`` to a per-trial window and build the relative time axis.

    ``win_ms = (lo_ms, hi_ms)`` is the post-tone window in ms (positive =
    after tone onset). ``t_ms = (frame_idx - tone_frame_idx) / fps *
    1000`` (field name preserved), relative to the tone onset.

    Returns ``(arr_slice, t_ms_slice)``. Both arrays have the same length.
    Slice is empty if the window falls entirely outside the session.
    """
    n_frames = len(arr)
    lo_frame = int(tone_frame_idx + np.floor(win_ms[0] / 1000.0 * fps))
    hi_frame = int(tone_frame_idx + np.ceil(win_ms[1] / 1000.0 * fps))
    lo = max(0, lo_frame)
    hi = min(n_frames, hi_frame + 1)
    if lo >= hi:
        return arr[lo:lo], np.zeros(0, dtype=np.float64)
    sliced = arr[lo:hi]
    t_ms = (np.arange(lo, hi, dtype=np.float64) - tone_frame_idx) / fps * 1000.0
    return sliced, t_ms


# ===========================================================================
# Per-cell knob override helpers (C5.2 2026-04-28)
# ===========================================================================
# Legacy had per-cell-different detector + bout knob values (e.g. Cell 33's
# MIN_PEAK_Y_ABS=20 pre-existing while Cells 36/39/42 lacked it; Cell 36's
# MIN_FINITE_SAMPLES_PER_LICK=5 pre-existing while Cells 33/39/42 lacked
# it; Cell 42's bout_max_ili=400 pre-existing while V3 unified to 300).
# The shared-detector-with-shared-knobs design above can't apply per-cell-
# different values via a single knob set. The parity harness uses these
# helpers in `legacy_approximate` mode to recover bit-identical legacy
# semantics by setting per-cell overrides in the YAML. Default mode has
# empty per-cell dicts → behavior unchanged.


def _per_cell_detector(params: dict[str, Any], cell_key: str) -> dict[str, Any]:
    """Return the per-cell detector knob dict (shallow merge over base)."""
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    base = tp["detector"]
    override = (tp.get("detector_per_cell") or {}).get(cell_key, {}) or {}
    return {**base, **override}


def _per_cell_bout(params: dict[str, Any], cell_key: str) -> dict[str, Any]:
    """Return the per-cell bout knob dict (shallow merge over base)."""
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    base = tp["bout"]
    override = (tp.get("bout_per_cell") or {}).get(cell_key, {}) or {}
    return {**base, **override}


# ===========================================================================
# Cell 33 — lick1 / lick2 first-peak scalars
# ===========================================================================


def _extract_lick1_lick2(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, params: dict[str, Any],
) -> dict[str, float]:
    """Per-trial 6 scalars for lick1 / lick2 (NaN where lick missing).

    Window: ``lick12_detect_win_ms`` (V3: ``[70, 3000]``; legacy was
    ``[70, 2000]``).
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detect_win = tuple(tp["lick12_detect_win_ms"])
    detector = _per_cell_detector(params, "cell33")
    peaks = _slope_detect_lick_peaks(
        y_t, x_t, t_ms, fps,
        detect_win_ms=detect_win, detector_params=detector, n_max=2,
    )
    out = {
        "lick1_y_peak": np.nan,
        "lick1_t_peak_ms": np.nan,
        "lick1_x_at_ypeak": np.nan,
        "lick2_y_peak": np.nan,
        "lick2_t_peak_ms": np.nan,
        "lick2_x_at_ypeak": np.nan,
    }
    if len(peaks) >= 1:
        out["lick1_y_peak"] = float(peaks.peak_y[0])
        out["lick1_t_peak_ms"] = float(peaks.peak_times_ms[0])
        out["lick1_x_at_ypeak"] = float(peaks.peak_x[0])
    if len(peaks) >= 2:
        out["lick2_y_peak"] = float(peaks.peak_y[1])
        out["lick2_t_peak_ms"] = float(peaks.peak_times_ms[1])
        out["lick2_x_at_ypeak"] = float(peaks.peak_x[1])
    return out


# ===========================================================================
# Cell 36 — peak velocity, first 5 licks per trial
# ===========================================================================


def _extract_peak_velocity_first5(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, params: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Per-trial first-5 lick velocity peaks + peak times.

    Smoothing happens AT VELOCITY STAGE (post-differentiation), not on the
    detection y. Output shape ``(5,)`` NaN-padded.
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detect_win = tuple(tp["peak_velocity_detect_win_ms"])
    detector = _per_cell_detector(params, "cell36")
    smooth_vel = bool(detector["do_smooth_vel"])
    smooth_ms_vel = float(detector["smooth_ms_vel"])
    min_finite = int(detector["min_finite_samples_per_lick"])

    peaks = _slope_detect_lick_peaks(
        y_t, x_t, t_ms, fps,
        detect_win_ms=detect_win, detector_params=detector, n_max=5,
    )
    n_lick = 5
    vy_out = np.full(n_lick, np.nan, dtype=np.float64)
    vxy_out = np.full(n_lick, np.nan, dtype=np.float64)
    t_out = np.full(n_lick, np.nan, dtype=np.float64)
    if len(peaks) == 0:
        return {
            "vy_peaks_bylick": vy_out,
            "vxy_peaks_bylick": vxy_out,
            "lick_t_peaks_bylick": t_out,
        }

    # Re-slice the trial to the same detect window so peaks.* indices align
    # with x_seg/y_seg below. (The detector does its own clipping, but we
    # need the same slice here for velocity computation.)
    in_win = (t_ms >= detect_win[0]) & (t_ms <= detect_win[1])
    if not np.any(in_win):
        return {
            "vy_peaks_bylick": vy_out,
            "vxy_peaks_bylick": vxy_out,
            "lick_t_peaks_bylick": t_out,
        }
    i_lo = int(np.argmax(in_win))
    i_hi = int(len(in_win) - 1 - np.argmax(in_win[::-1]))
    xseg = x_t[i_lo:i_hi + 1].astype(np.float64, copy=True)
    yseg = y_t[i_lo:i_hi + 1].astype(np.float64, copy=True)

    # Smooth position before differentiating (legacy SMOOTH_VEL pattern).
    if smooth_vel:
        x_vel = _moving_avg_nan(xseg, smooth_ms_vel, fps)
        y_vel = _moving_avg_nan(yseg, smooth_ms_vel, fps)
    else:
        x_vel = xseg.copy()
        y_vel = yseg.copy()
    finite_pos = np.isfinite(x_vel) & np.isfinite(y_vel)
    if np.count_nonzero(finite_pos) < 2:
        return {
            "vy_peaks_bylick": vy_out,
            "vxy_peaks_bylick": vxy_out,
            "lick_t_peaks_bylick": t_out,
        }
    dx_vel = np.gradient(x_vel) * fps
    dy_vel = np.gradient(y_vel) * fps
    vxy_vel = np.sqrt(dx_vel**2 + dy_vel**2)

    n_actual = min(n_lick, len(peaks))
    for j in range(n_actual):
        r0 = int(peaks.rise_starts[j])
        k = int(peaks.turnover[j])
        win_lo = max(0, r0)
        win_hi = min(len(yseg) - 1, k)
        if win_hi < win_lo:
            continue
        vy_win = dy_vel[win_lo:win_hi + 1]
        vxy_win = vxy_vel[win_lo:win_hi + 1]
        if int(np.count_nonzero(np.isfinite(vy_win))) < min_finite:
            continue
        vy_out[j] = float(np.nanmax(vy_win))
        vxy_out[j] = float(np.nanmax(vxy_win))
        t_out[j] = float(peaks.peak_times_ms[j])
    return {
        "vy_peaks_bylick": vy_out,
        "vxy_peaks_bylick": vxy_out,
        "lick_t_peaks_bylick": t_out,
    }


# ===========================================================================
# Cell 39 — n_licks family (count + direction tally + categorical + binning)
# ===========================================================================


def _extract_n_licks_family(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, params: dict[str, Any],
) -> dict[str, Any]:
    """Per-trial: ``n_licks``, ``n_left``, ``n_right``, ``n_other``,
    ``lick_ge10`` (bool), ``n_licks_per_bin`` (int[5]).

    Detect window ``[70, 8000]`` ms; apply window ``[70, 5000]`` ms; binning
    window ``[70, 5070]`` for clean 1-s bins (V3).
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detect_win = tuple(tp["lick_count_detect_win_ms"])
    apply_win = tuple(tp["lick_count_apply_win_ms"])
    bin_win = tuple(tp["lick_count_bin_win_ms"])
    detector = _per_cell_detector(params, "cell39")
    dir_thr = tp["direction_thresholds"]
    x_left_thr = float(dir_thr["x_left_thr_px"])
    x_right_thr = float(dir_thr["x_right_thr_px"])
    ge10_thr = int(tp["n_licks_categorical"]["lick_ge10_thr"])
    n_bins = int(tp["n_licks_binning"]["bin_count"])
    bin_ms = float(tp["n_licks_binning"]["bin_ms"])
    cap = int(tp["max_licks_per_trial"])

    peaks = _slope_detect_lick_peaks(
        y_t, x_t, t_ms, fps,
        detect_win_ms=detect_win, detector_params=detector, n_max=cap,
    )
    if len(peaks) == 0:
        return {
            "n_licks": 0, "n_left": 0, "n_right": 0, "n_other": 0,
            "lick_ge10": False,
            "n_licks_per_bin": np.zeros(n_bins, dtype=np.int64),
        }

    in_apply = (
        (peaks.peak_times_ms >= apply_win[0])
        & (peaks.peak_times_ms <= apply_win[1])
    )
    n_licks = int(np.count_nonzero(in_apply))

    # Direction tally (within apply window).
    x_apply = peaks.peak_x[in_apply]
    n_left = int(np.count_nonzero(x_apply > x_left_thr))
    n_right = int(np.count_nonzero(x_apply < x_right_thr))
    n_other = int(n_licks - n_left - n_right)

    lick_ge10 = bool(n_licks >= ge10_thr)

    # Per-bin counts: 5 × bin_ms-wide bins over [bin_win[0], bin_win[0]+5*bin_ms].
    # Kickoff config bin_count=5, bin_ms=1000, bin_win=[70, 5070] →
    # edges = [70, 1070, 2070, 3070, 4070, 5070].
    edges = np.array(
        [bin_win[0] + i * bin_ms for i in range(n_bins + 1)],
        dtype=np.float64,
    )
    in_bin = (
        (peaks.peak_times_ms >= edges[0])
        & (peaks.peak_times_ms < edges[-1])
    )
    if np.any(in_bin):
        counts, _ = np.histogram(peaks.peak_times_ms[in_bin], bins=edges)
    else:
        counts = np.zeros(n_bins, dtype=np.int64)

    return {
        "n_licks": n_licks,
        "n_left": n_left,
        "n_right": n_right,
        "n_other": n_other,
        "lick_ge10": lick_ge10,
        "n_licks_per_bin": counts.astype(np.int64),
    }


# ===========================================================================
# Cell 42 — within-bout licking dynamics (per-session × side traces +
# per-trial reductions)
# ===========================================================================


def _extract_licking_dynamics_reductions(
    y_t: np.ndarray, x_t: np.ndarray, t_ms: np.ndarray, fps: float,
    *, params: dict[str, Any],
) -> dict[str, float | int]:
    """Per-trial Cell 42 reductions: ``bout_count``,
    ``mean_within_bout_ili_ms``, ``lick_rate_hz``.

    Bout-modes per V3 §2a (Q8 corrected 2026-04-28):
      * ``bout_count``: ``"all"`` (counts multi-lick bouts among all
        apply-window peaks; the metric is a tally over the whole bout
        list, not a peak-set filter).
      * ``mean_within_bout_ili_ms``: ``"first_multi_bout"`` (mean ILI inside
        the first multi-lick bout, valid ILIs only).
      * ``lick_rate_hz``: ``"all"`` (apply-window licks / window duration).

    Note: ``n_licks_in_first_multi_bout`` is emitted by
    :func:`_extract_cell50_own_bout_scalars` (Cell 50 own-bout, Q9 placement
    lock per kickoff §3a 2026-04-28) — same value either side, since both
    cells share the detector + ``bout.max_ili_ms`` config and use identical
    detect/apply windows.
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detect_win = tuple(tp["licking_dyn_detect_win_ms"])
    apply_win = tuple(tp["licking_dyn_apply_win_ms"])
    detector = _per_cell_detector(params, "cell42")
    bout = _per_cell_bout(params, "cell42")
    max_ili = float(bout["max_ili_ms"])
    min_ili = float(bout["min_ili_ms"])
    min_in_bout = int(bout["min_licks_in_bout_for_ili"])

    peaks = _slope_detect_lick_peaks(
        y_t, x_t, t_ms, fps,
        detect_win_ms=detect_win, detector_params=detector,
    )
    in_apply = (
        (peaks.peak_times_ms >= apply_win[0])
        & (peaks.peak_times_ms <= apply_win[1])
    )
    apply_peaks_t = peaks.peak_times_ms[in_apply]

    win_duration_s = (apply_win[1] - apply_win[0]) / 1000.0
    lick_rate_hz = (
        float(len(apply_peaks_t) / win_duration_s) if win_duration_s > 0 else float("nan")
    )

    bouts = _build_bouts(apply_peaks_t, max_ili)
    multi_bouts = [b for b in bouts if len(b) >= 2]
    bout_count = len(multi_bouts)

    if not multi_bouts:
        return {
            "bout_count": int(bout_count),
            "mean_within_bout_ili_ms": float("nan"),
            "lick_rate_hz": lick_rate_hz,
        }
    first = multi_bouts[0]
    if len(first) < min_in_bout:
        return {
            "bout_count": int(bout_count),
            "mean_within_bout_ili_ms": float("nan"),
            "lick_rate_hz": lick_rate_hz,
        }
    sorted_t = np.sort(apply_peaks_t[first])
    ilis = np.diff(sorted_t)
    valid = (ilis >= min_ili) & (ilis <= max_ili)
    if not np.any(valid):
        return {
            "bout_count": int(bout_count),
            "mean_within_bout_ili_ms": float("nan"),
            "lick_rate_hz": lick_rate_hz,
        }
    mean_ili = float(np.mean(ilis[valid]))
    return {
        "bout_count": int(bout_count),
        "mean_within_bout_ili_ms": mean_ili,
        "lick_rate_hz": lick_rate_hz,
    }


def _extract_licking_dynamics_traces(
    per_trial_peaks_by_side: dict[str, list[np.ndarray]],
    *, params: dict[str, Any],
) -> pd.DataFrame:
    """Per-session × side time-binned traces over the apply window.

    Each entry of ``per_trial_peaks_by_side[side]`` is the array of
    apply-window peak times for one trial of that side. Aggregates across
    all trials of each side. Emits 4 trace columns at ``bin_ms`` resolution:

    - ``lick_rate_per_t``: gaussian-smoothed lick density (Hz)
    - ``ili_within_bout_rate_per_t``: gaussian-smoothed within-bout ILI rate
    - ``p_lick_per_t``: moving-avg P(any lick in bin)
    - ``p_within_bout_per_t``: moving-avg P(within-bout lick in bin)
    """
    from stroke_orofacial.dlc_kinematics._angle import _gaussian_smooth_nan

    tp = params["dlc_kinematics"]["tongue_pertrial"]
    apply_win = tuple(tp["licking_dyn_apply_win_ms"])
    ld = tp["licking_dynamics"]
    bin_ms = float(ld["bin_ms"])
    sigma_lick_ms = float(ld["lickrate_smooth_sigma_ms"])
    sigma_ili_ms = float(ld["ili_smooth_sigma_ms"])
    movavg_prob_ms = float(ld["prob_smooth_movavg_ms"])
    min_trials_per_bin = int(ld["min_trials_per_bin"])
    bout = _per_cell_bout(params, "cell42")
    max_ili_ms = float(bout["max_ili_ms"])
    min_in_bout = int(bout["min_licks_in_bout_for_ili"])

    edges = np.arange(apply_win[0], apply_win[1] + bin_ms, bin_ms)
    centers = 0.5 * (edges[:-1] + edges[1:])
    n_bins = len(centers)

    sigma_lick_bins = sigma_lick_ms / bin_ms
    sigma_ili_bins = sigma_ili_ms / bin_ms
    movavg_prob_n = max(1, int(round(movavg_prob_ms / bin_ms)))

    rows: list[dict[str, Any]] = []
    for side, trial_peak_lists in per_trial_peaks_by_side.items():
        n_trials = len(trial_peak_lists)
        if n_trials == 0:
            for c in centers:
                rows.append({
                    "timebin_ms": float(c), "side": side,
                    "lick_rate_per_t": np.nan,
                    "ili_within_bout_rate_per_t": np.nan,
                    "p_lick_per_t": np.nan,
                    "p_within_bout_per_t": np.nan,
                })
            continue

        lick_count = np.zeros(n_bins, dtype=np.float64)
        ili_rate_sum = np.zeros(n_bins, dtype=np.float64)
        ili_rate_n = np.zeros(n_bins, dtype=np.int64)
        n_trials_with_lick = np.zeros(n_bins, dtype=np.int64)
        n_trials_with_within_bout = np.zeros(n_bins, dtype=np.int64)

        for trial_peaks in trial_peak_lists:
            if len(trial_peaks) == 0:
                continue
            counts, _ = np.histogram(trial_peaks, bins=edges)
            lick_count += counts
            n_trials_with_lick += (counts > 0).astype(np.int64)

            sorted_t = np.sort(trial_peaks)
            bouts = _build_bouts(sorted_t, max_ili_ms)
            within_bout_t: list[float] = []
            for b in bouts:
                if len(b) < min_in_bout:
                    continue
                bt = sorted_t[b]
                ilis = np.diff(bt)
                bin_idx = np.digitize(bt[1:], edges) - 1
                for bi, dt_ms in zip(bin_idx, ilis):
                    if 0 <= bi < n_bins and dt_ms > 0:
                        ili_rate_sum[bi] += 1000.0 / float(dt_ms)
                        ili_rate_n[bi] += 1
                within_bout_t.extend(bt.tolist())
            if within_bout_t:
                wb_counts, _ = np.histogram(np.asarray(within_bout_t), bins=edges)
                n_trials_with_within_bout += (wb_counts > 0).astype(np.int64)

        lick_rate_hz = lick_count / n_trials / (bin_ms / 1000.0)
        ili_rate_mean = np.where(
            ili_rate_n >= min_trials_per_bin,
            ili_rate_sum / np.maximum(ili_rate_n, 1),
            np.nan,
        )
        p_lick = n_trials_with_lick / n_trials
        p_within_bout = n_trials_with_within_bout / n_trials

        lick_rate_smoothed = _gaussian_smooth_nan(lick_rate_hz, sigma_lick_bins)
        ili_rate_smoothed = _gaussian_smooth_nan(ili_rate_mean, sigma_ili_bins)
        p_lick_smoothed = _moving_avg_window(p_lick, movavg_prob_n)
        p_within_smoothed = _moving_avg_window(p_within_bout, movavg_prob_n)

        for i, c in enumerate(centers):
            rows.append({
                "timebin_ms": float(c),
                "side": side,
                "lick_rate_per_t": float(lick_rate_smoothed[i]),
                "ili_within_bout_rate_per_t": float(ili_rate_smoothed[i]),
                "p_lick_per_t": float(p_lick_smoothed[i]),
                "p_within_bout_per_t": float(p_within_smoothed[i]),
            })

    return pd.DataFrame(rows)


def _moving_avg_window(arr: np.ndarray, win_n: int) -> np.ndarray:
    """Centered moving average over ``win_n`` bins (float)."""
    win_n = max(1, int(win_n))
    if win_n <= 1:
        return arr.astype(np.float64, copy=True)
    finite = np.isfinite(arr).astype(np.float64)
    safe = np.where(np.isfinite(arr), arr, 0.0)
    kernel = np.ones(win_n, dtype=np.float64)
    num = np.convolve(safe, kernel, mode="same")
    den = np.convolve(finite, kernel, mode="same")
    out = np.full_like(arr, np.nan, dtype=np.float64)
    nz = den > 0
    out[nz] = num[nz] / den[nz]
    return out


# ===========================================================================
# Phase 7a.4 visual-bundle helpers (Task 3.5)
# ===========================================================================
# These helpers materialise the per-trial array snippets + per-bout/per-peak
# rows + per-frame phase rows that the Cell 50 plot families (Phase 7a.4)
# consume. They run inside the same trial loop as the emit-set scalar
# extractors but produce intermediate in-memory DataFrames that the on-disk
# emit set deliberately does not carry. See Phase 7a.4 Task 1.5b audit
# (.scratch_7a4/cell50_plot_families_audit.md) for the rationale.


def _bout_time_bounds_ms(
    peak_times_ms: np.ndarray, single_bout_win_ms: tuple[float, float],
) -> tuple[float, float]:
    """Time bounds for a bout (legacy Cell 50 ``_bout_time_bounds_ms``).

    For multi-lick bouts, extends pre/post by half the first/last ILI.
    For single-lick bouts, applies a fixed ``single_bout_win_ms`` window
    (defaults to ``[-120, 200]`` ms — see ``defaults.yaml`` block
    ``dlc_kinematics.tongue_pertrial.bout.single_bout_win_ms``).
    """
    n = len(peak_times_ms)
    if n >= 2:
        lead = 0.5 * (peak_times_ms[1] - peak_times_ms[0])
        tail = 0.5 * (peak_times_ms[-1] - peak_times_ms[-2])
        t0 = float(peak_times_ms[0] - lead)
        t1 = float(peak_times_ms[-1] + tail)
    else:
        t0 = float(peak_times_ms[0]) + float(single_bout_win_ms[0])
        t1 = float(peak_times_ms[0]) + float(single_bout_win_ms[1])
    return t0, t1


def _assign_phase_peak_to_peak_shifted(
    n_samples: int, peak_indices: np.ndarray,
) -> np.ndarray:
    """Per-frame phase ∈ [0, 1) for a multi-lick bout (legacy Cell 50).

    For each adjacent pair ``(peak_i, peak_{i+1})`` in ``peak_indices``,
    assigns ``u = (frame - peak_i) / (peak_{i+1} - peak_i)``, then
    ``phase = (u - 0.5) mod 1.0``. Phase 0 = midpoint between peaks;
    phase 0.5 = peak protrusion. NaN outside multi-bout intervals.

    ``peak_indices`` are integer indices into the trial slice
    (length ``n_samples``).
    """
    phase = np.full(n_samples, np.nan, dtype=np.float64)
    if len(peak_indices) < 2:
        return phase
    for i0, i1 in zip(peak_indices[:-1], peak_indices[1:]):
        i0 = int(i0)
        i1 = int(i1)
        if i1 <= i0:
            continue
        u = (np.arange(i0, i1 + 1) - i0) / float(i1 - i0)
        phase[i0:i1 + 1] = np.mod(u - 0.5, 1.0)
    return phase


def _build_visual_bundle_per_trial(
    trial_index: int,
    side: str,
    *,
    x_final: np.ndarray,
    y_final: np.ndarray,
    angle_per_frame: np.ndarray,
    tone_frame_idx: int,
    fps: float,
    plot_win_ms: tuple[float, float],
    detect_win_ms: tuple[float, float],
    first_peak_align_win_ms: tuple[float, float],
    detector_params: dict[str, Any],
    max_ili_ms: float,
    single_bout_win_ms: tuple[float, float],
    max_licks_per_trial: int,
    phase_bin_edges: np.ndarray,
    phase_bin_centers: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compute one trial's contribution to df_trials, df_bouts, df_phase.

    Returns
    -------
    trial_row : dict
        Single row for ``df_trials`` with the array snippets + scalars.
    bout_rows : list[dict]
        Mixed bout-summary + per-peak rows for ``df_bouts`` (legacy
        Cell 50 schema). Empty if the trial has zero detected peaks.
    phase_rows : list[dict]
        One row per frame in any multi-lick bout for ``df_phase``. Empty
        if the trial has no multi-lick bouts.
    """
    # Slice all three session-length arrays at the bundle's plot window.
    y_snip, t_ms = _extract_trial_slice(
        y_final, tone_frame_idx, plot_win_ms, fps,
    )
    x_snip, _ = _extract_trial_slice(
        x_final, tone_frame_idx, plot_win_ms, fps,
    )
    angle_snip, _ = _extract_trial_slice(
        angle_per_frame, tone_frame_idx, plot_win_ms, fps,
    )

    # Per-trial peak detection within detect_win_ms (Cell 50 = [70, 3000]).
    peaks = _slope_detect_lick_peaks(
        y_snip, x_snip, t_ms, fps,
        detect_win_ms=detect_win_ms,
        detector_params=detector_params,
        n_max=int(max_licks_per_trial),
    )
    n_peaks = len(peaks)

    # C5.5 (2026-04-30) — peak_indices coordinate fix. The 7a.3 V3
    # ``_slope_detect_lick_peaks`` returns ``peak_indices`` that are LOCAL
    # to its internal ``yseg = y_snip[i_lo:i_hi+1]`` (the detect-window
    # subset of the trial slice). Translating to trial-slice frame
    # indices requires adding the i_lo offset (= the frame in t_ms where
    # detect_win_ms[0] starts). 7a.3 V3 emit-set consumers don't trip
    # this because they use peak_times_ms / peak_y (which the detector
    # already pre-offset via ``tseg`` / ``yseg`` indexing). The bundle
    # consumer DOES use peak_indices directly to:
    #   (a) lookup angle_snip at the peak (peak_angle_deg field of
    #       df_bouts), and
    #   (b) seed the phase-assignment frame range
    #       (`_assign_phase_peak_to_peak_shifted`).
    # Without this offset, peak markers in the QC plot offset off the
    # angle line, AND multi-bout phase assignment shifts (peaks no
    # longer land at phase=0.5).
    if t_ms.size > 0:
        in_win = (t_ms >= detect_win_ms[0]) & (t_ms <= detect_win_ms[1])
        detect_lo_offset = (
            int(np.argmax(in_win)) if np.any(in_win) else 0
        )
    else:
        detect_lo_offset = 0
    # Trial-slice-local peak frame indices (consumed below by phase
    # assignment + per-peak angle lookups). Original peaks.peak_indices
    # remains unchanged so 7a.3 V3 consumers see no behavior change.
    peaks_in_snip = peaks.peak_indices + detect_lo_offset

    # Build bouts.
    bouts_idx_lists = _build_bouts(peaks.peak_times_ms, float(max_ili_ms))
    n_bouts = len(bouts_idx_lists)
    n_multi = sum(1 for b in bouts_idx_lists if len(b) >= 2)

    # Per-bout angle masks (shape = trial-slice length).
    angle_allbouts_snip = np.full_like(angle_snip, np.nan, dtype=np.float64)
    angle_firstbout_snip = np.full_like(angle_snip, np.nan, dtype=np.float64)
    angle_firstmulti_snip = np.full_like(angle_snip, np.nan, dtype=np.float64)

    bout_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    first_bout_done = False
    first_multi_done = False
    multi_seen = 0

    for bout_rank, idxs in enumerate(bouts_idx_lists):
        is_multi = len(idxs) >= 2
        multi_rank = float(multi_seen) if is_multi else float("nan")
        if is_multi:
            multi_seen += 1

        peak_times = peaks.peak_times_ms[idxs]
        peak_xs = peaks.peak_x[idxs]
        peak_ys = peaks.peak_y[idxs]
        # peak_local_idxs are in TRIAL-SLICE coordinates (post-C5.5 fix
        # 2026-04-30). They index into angle_snip / phase array directly.
        peak_local_idxs = peaks_in_snip[idxs]

        t0_ms, t1_ms = _bout_time_bounds_ms(peak_times, single_bout_win_ms)
        # Convert (t0_ms, t1_ms) → indices into the trial slice.
        i_lo = int(max(0, np.searchsorted(t_ms, t0_ms, side="left")))
        i_hi_excl = int(min(len(t_ms), np.searchsorted(t_ms, t1_ms, side="right")))

        angle_allbouts_snip[i_lo:i_hi_excl] = angle_snip[i_lo:i_hi_excl]
        if not first_bout_done:
            angle_firstbout_snip[i_lo:i_hi_excl] = angle_snip[i_lo:i_hi_excl]
            first_bout_done = True
        if is_multi and not first_multi_done:
            angle_firstmulti_snip[i_lo:i_hi_excl] = angle_snip[i_lo:i_hi_excl]
            first_multi_done = True

        # Bout-summary row (peak0/peak1 fields populated, peak fields NaN).
        def _peak_angle_at(j: int) -> float:
            if j >= len(peak_local_idxs):
                return float("nan")
            li = int(peak_local_idxs[j])
            if li < 0 or li >= len(angle_snip):
                return float("nan")
            v = angle_snip[li]
            return float(v) if np.isfinite(v) else float("nan")

        bout_rows.append({
            "side": side,
            "trial_index": int(trial_index),
            "bout_idx": int(bout_rank),
            "bout_rank": int(bout_rank),
            "multi_bout_rank": multi_rank,
            "n_peaks": int(len(idxs)),
            "bout_t0_ms": float(t0_ms),
            "bout_t1_ms": float(t1_ms),
            "peak_t0_ms": float(peak_times[0]) if len(peak_times) >= 1 else float("nan"),
            "peak_t1_ms": float(peak_times[1]) if len(peak_times) >= 2 else float("nan"),
            "peak_y0": float(peak_ys[0]) if len(peak_times) >= 1 else float("nan"),
            "peak_angle0": _peak_angle_at(0),
            "peak_y1": float(peak_ys[1]) if len(peak_times) >= 2 else float("nan"),
            "peak_angle1": _peak_angle_at(1),
            "peak_t_ms": float("nan"),
            "peak_y": float("nan"),
            "peak_x": float("nan"),
            "peak_angle_deg": float("nan"),
        })
        # Per-peak rows (one per peak; bout-summary fields NaN).
        for j in range(len(peak_times)):
            li = int(peak_local_idxs[j])
            peak_angle = float("nan")
            if 0 <= li < len(angle_snip) and np.isfinite(angle_snip[li]):
                peak_angle = float(angle_snip[li])
            bout_rows.append({
                "side": side,
                "trial_index": int(trial_index),
                "bout_idx": int(bout_rank),
                "bout_rank": int(bout_rank),
                "multi_bout_rank": multi_rank,
                "n_peaks": int(len(idxs)),
                "bout_t0_ms": float(t0_ms),
                "bout_t1_ms": float(t1_ms),
                "peak_t0_ms": float("nan"),
                "peak_t1_ms": float("nan"),
                "peak_y0": float("nan"),
                "peak_angle0": float("nan"),
                "peak_y1": float("nan"),
                "peak_angle1": float("nan"),
                "peak_t_ms": float(peak_times[j]),
                "peak_y": float(peak_ys[j]),
                "peak_x": float(peak_xs[j]),
                "peak_angle_deg": peak_angle,
            })

        # Phase rows for multi-lick bouts only.
        if is_multi:
            phase = _assign_phase_peak_to_peak_shifted(
                len(t_ms), peak_local_idxs,
            )
            mask = (
                np.isfinite(phase)
                & np.isfinite(angle_snip)
                & np.isfinite(x_snip)
                & np.isfinite(y_snip)
            )
            for ii in np.where(mask)[0]:
                ph = float(phase[ii])
                bin_idx = int(np.clip(
                    np.searchsorted(phase_bin_edges, ph, side="right") - 1,
                    0, len(phase_bin_centers) - 1,
                ))
                phase_rows.append({
                    "side": side,
                    "trial_index": int(trial_index),
                    "bout_idx": int(bout_rank),
                    "bout_rank": int(bout_rank),
                    "multi_bout_rank": int(multi_rank) if is_multi else -1,
                    "t_ms": float(t_ms[ii]),
                    "phase": ph,
                    "phase_bin": bin_idx,
                    "phase_bin_center": float(phase_bin_centers[bin_idx]),
                    "angle_deg": float(angle_snip[ii]),
                    "x_geom": float(x_snip[ii]),
                    "y_geom": float(y_snip[ii]),
                })

    # First-peak-aligned snippet (centered on the first detected peak's
    # session-frame index, span = first_peak_align_win_ms). NaN-filled if
    # no peak was detected in this trial.
    pre_f = max(0, int(np.floor(-first_peak_align_win_ms[0] / 1000.0 * fps)))
    post_f = max(0, int(np.ceil(first_peak_align_win_ms[1] / 1000.0 * fps)))
    expected_len = pre_f + post_f + 1
    if n_peaks > 0:
        # C5.5 (2026-04-30): convert via peak_times_ms (which the
        # detector already pre-offsets via tseg = t_ms[i_lo:i_hi+1])
        # rather than via peak_indices (yseg-local; would miss the
        # detect_lo_offset and produce a snippet centered on the wrong
        # frame).
        first_peak_t_ms_val = float(peaks.peak_times_ms[0])
        first_peak_session_frame = int(round(
            tone_frame_idx + first_peak_t_ms_val / 1000.0 * fps
        ))
        angle_firstpeak_snip, t_firstpeak_align_ms = _extract_trial_slice(
            angle_per_frame, first_peak_session_frame,
            (-float(pre_f) / fps * 1000.0, float(post_f) / fps * 1000.0), fps,
        )
        # Pad to expected length if the slice clipped at session edges.
        if len(angle_firstpeak_snip) != expected_len:
            padded = np.full(expected_len, np.nan, dtype=np.float64)
            t_padded = (
                np.arange(-pre_f, post_f + 1, dtype=np.float64) / fps * 1000.0
            )
            # Best-effort centering; if the slice landed near a session edge
            # we just keep what we got + NaN-pad. The bundle is for visual
            # use, not a parity comparator.
            n_have = len(angle_firstpeak_snip)
            padded[:n_have] = angle_firstpeak_snip
            angle_firstpeak_snip = padded
            t_firstpeak_align_ms = t_padded
    else:
        t_firstpeak_align_ms = (
            np.arange(-pre_f, post_f + 1, dtype=np.float64) / fps * 1000.0
        )
        angle_firstpeak_snip = np.full(expected_len, np.nan, dtype=np.float64)

    first_peak_t_ms = (
        float(peaks.peak_times_ms[0]) if n_peaks > 0 else float("nan")
    )

    trial_row = {
        "side": side,
        "trial_index": int(trial_index),
        "n_peaks": int(n_peaks),
        "n_bouts": int(n_bouts),
        "n_multi_lick_bouts": int(n_multi),
        "first_peak_t_ms": first_peak_t_ms,
        "t_ms": t_ms.copy(),
        "y_snip": y_snip.copy(),
        "angle_snip": angle_snip.copy(),
        "angle_allbouts_snip": angle_allbouts_snip,
        "angle_firstbout_snip": angle_firstbout_snip,
        "angle_firstmulti_snip": angle_firstmulti_snip,
        "t_firstpeak_align_ms": t_firstpeak_align_ms,
        "angle_firstpeak_snip": angle_firstpeak_snip,
    }
    return trial_row, bout_rows, phase_rows


# ===========================================================================
# Driver core
# ===========================================================================


def _build_tongue_pertrial_core(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[TrialEvent],
    params: dict[str, Any],
    animal_info: AnimalInfo | None = None,
    pre_stroke_median_ili_ms: float | None = None,
) -> _PertrialCoreResult:
    """Pure-function driver: reads inputs, computes everything, returns result.

    Sequence (kickoff §3a):

    1. Load tongue parquet (``frame_idx``, ``x_final``, ``y_final``, fps).
    2. Load eye-landmark parquet.
    3. Resolve ``eye_in_spout_frame`` (median + spout-frame sanity check).
    4. Compute per-frame smoothed signed angle for the whole session.
    5. For each trial: extract Cells 33/36/39/42 reductions + Cell 50
       per-trial scalars + Cell 50 own-bout scalars + (Phase 7a.4) the
       per-trial array snippets / per-bout rows / per-frame phase rows
       that the visual-bundle consumer needs.
    6. Cell 42 traces: aggregate per-trial peak lists per side.
    7. Cell 50 session-inclusion: 4 booleans (Q9 binding 2026-04-28:
       ``n_phase_licks = sum(n_licks_in_first_multi_bout)`` across trials).
    8. Pack endpoints JSON, angle parquet, traces parquet, visual bundle.

    Returns
    -------
    _PertrialCoreResult
        Wraps both the legacy :class:`TonguePertrialResult` (emit-set
        artifacts) and the Phase 7a.4 :class:`TongueVisualBundle`
        (in-memory per-trial DataFrames). Both public entry points
        consume this single core return and project the field they need.
    """
    tp = params["dlc_kinematics"]["tongue_pertrial"]
    detector = tp["detector"]
    # Phase 7a.4 visual-bundle knobs (see configs/defaults.yaml
    # dlc_kinematics.tongue_visual.bundle and .render). Read once outside
    # the trial loop so the per-trial helper sees a stable view.
    visual_block = params["dlc_kinematics"].get("tongue_visual", {})
    bundle_cfg = visual_block.get("bundle", {})
    bundle_plot_win = tuple(bundle_cfg.get("plot_win_ms", [0.0, 8000.0]))
    bundle_detect_win = tuple(
        bundle_cfg.get("detect_win_ms", [70.0, 3000.0])
    )
    bundle_first_peak_win = tuple(
        bundle_cfg.get("first_peak_align_win_ms", [-180.0, 1000.0])
    )
    n_phase_bins = int(tp["phase"]["n_phase_bins"])
    phase_bin_edges = np.linspace(0.0, 1.0, n_phase_bins + 1, dtype=np.float64)
    phase_bin_centers = 0.5 * (phase_bin_edges[:-1] + phase_bin_edges[1:])
    bundle_detector = _per_cell_detector(params, "cell50")
    bundle_bout = _per_cell_bout(params, "cell50")
    bundle_max_ili = float(bundle_bout["max_ili_ms"])
    bundle_single_bout_win = tuple(bundle_bout["single_bout_win_ms"])
    bundle_max_licks = int(tp["max_licks_per_trial"])

    # Step 1: tongue parquet.
    tongue_df, tongue_meta = _load_tongue_centered_trace(manifest, resolver)
    fps = float(tongue_meta.get("fps", _DEFAULT_FPS))
    x_final = tongue_df["x_final"].to_numpy(dtype=np.float64, copy=True)
    y_final = tongue_df["y_final"].to_numpy(dtype=np.float64, copy=True)
    n_frames_session = int(len(tongue_df))

    # Phase 7e v7-pipeline flag (Task 5). When True, run the new
    # preclean → detect_v2 → gates pipeline PARALLEL to the legacy
    # per-cell extractions and collect per-trial v7 results into
    # ``v7_trial_results``. Task 5 leaves legacy outputs unchanged;
    # Tasks 6 + 7 wire the v7 results into parquet writers + downstream
    # metric consumers.
    use_v7_pipeline = bool(tp.get("use_v7_pipeline", False))
    if use_v7_pipeline:
        # Phase 7a.2 parquet carries is_interp_fill + is_baseline_fill +
        # likelihood_raw — all required by the v7 pipeline.
        is_interp_fill_session = tongue_df["is_interp_fill"].to_numpy(
            dtype=bool, copy=True,
        )
        is_baseline_fill_session = tongue_df["is_baseline_fill"].to_numpy(
            dtype=bool, copy=True,
        )
        likelihood_raw_session = tongue_df["likelihood_raw"].to_numpy(
            dtype=np.float64, copy=True,
        )
        v7_trial_results: list[_V7TrialResult] = []
    else:
        v7_trial_results = None  # type: ignore[assignment]

    # Step 2 + 3: eye landmarks + eye_midpoint resolution.
    eye_df = _load_consolidated_eye_landmarks(manifest, resolver)
    eye_x, eye_y = _resolve_eye_midpoint_session_median(eye_df, params=params)

    # Step 4: per-frame smoothed signed angle for the whole session.
    angle_per_frame = _extract_per_frame_angle_smoothed(
        x_final=x_final, y_final=y_final,
        eye_x_in_spout_frame=eye_x, eye_y_in_spout_frame=eye_y,
        fps=fps, params=params,
    )

    # Step 5: per-trial extraction. Use widest detect window for the slice
    # (Cells 39/42/50 = [70, 8000]); each cell enforces its own narrower
    # window inside its detector call.
    widest_detect = (70.0, 8000.0)
    peak_pad_ms = float(detector["peak_pad_ms"])

    n_trials = len(trial_events)
    trial_indices: list[int] = []
    sides: list[str] = []
    lick12_records: list[dict[str, float]] = []
    velocity_records: list[dict[str, np.ndarray]] = []
    n_licks_records: list[dict[str, Any]] = []
    licking_dyn_records: list[dict[str, float | int]] = []
    cell50_own: list[dict[str, float | int]] = []
    angle_at_lick1: list[float] = []
    angle_at_lick2: list[float] = []
    angle_at_vpeak: list[np.ndarray] = []
    angle_max_signed: list[np.ndarray] = []
    apply_peaks_per_side: dict[str, list[np.ndarray]] = {"L": [], "R": []}
    # Phase 7a.4 visual-bundle accumulators.
    visual_trial_rows: list[dict[str, Any]] = []
    visual_bout_rows: list[dict[str, Any]] = []
    visual_phase_rows: list[dict[str, Any]] = []

    for ev in trial_events:
        x_slice, t_ms = _extract_trial_slice(
            x_final, ev.tone_frame_idx, widest_detect, fps,
        )
        y_slice, _ = _extract_trial_slice(
            y_final, ev.tone_frame_idx, widest_detect, fps,
        )

        trial_indices.append(int(ev.trial_index))
        sides.append(ev.side)

        # Phase 7e v7 pipeline (Task 5) — run in parallel with the
        # legacy per-cell extractions when the feature flag is on. The
        # v7 result is collected for Task 6 (parquet writers) + Task 7
        # (downstream metric consumers); legacy outputs below are NOT
        # affected by this branch.
        if use_v7_pipeline:
            is_intp_slice, _ = _extract_trial_slice(
                is_interp_fill_session, ev.tone_frame_idx, widest_detect, fps,
            )
            is_base_slice, _ = _extract_trial_slice(
                is_baseline_fill_session, ev.tone_frame_idx, widest_detect, fps,
            )
            lik_slice, _ = _extract_trial_slice(
                likelihood_raw_session, ev.tone_frame_idx, widest_detect, fps,
            )
            v7_trial_results.append(_run_v7_pipeline_per_trial(
                y_slice=y_slice, x_slice=x_slice,
                is_interp_fill_slice=is_intp_slice,
                is_baseline_fill_slice=is_base_slice,
                likelihood_slice=lik_slice,
                t_ms=t_ms, fps=fps,
                trial_index=int(ev.trial_index), side=ev.side,
                params=params,
            ))

        lick12 = _extract_lick1_lick2(y_slice, x_slice, t_ms, fps, params=params)
        lick12_records.append(lick12)

        vel = _extract_peak_velocity_first5(
            y_slice, x_slice, t_ms, fps, params=params,
        )
        velocity_records.append(vel)

        n_licks = _extract_n_licks_family(
            y_slice, x_slice, t_ms, fps, params=params,
        )
        n_licks_records.append(n_licks)

        ld_red = _extract_licking_dynamics_reductions(
            y_slice, x_slice, t_ms, fps, params=params,
        )
        licking_dyn_records.append(ld_red)

        cell50 = _extract_cell50_own_bout_scalars(
            y_slice, x_slice, t_ms, fps, params=params,
        )
        cell50_own.append(cell50)

        # Cell 50 per-trial angle scalars: sample the session-wide angle at
        # per-trial lick timestamps.
        angle_at_lick1.append(_extract_angle_at_lick_timestamps(
            angle_per_frame, fps, ev.tone_frame_idx,
            lick12["lick1_t_peak_ms"],
        ))
        angle_at_lick2.append(_extract_angle_at_lick_timestamps(
            angle_per_frame, fps, ev.tone_frame_idx,
            lick12["lick2_t_peak_ms"],
        ))
        per_lick_v = vel["lick_t_peaks_bylick"]
        per_lick_angle_at_v = np.full(5, np.nan, dtype=np.float64)
        for j in range(5):
            per_lick_angle_at_v[j] = _extract_angle_at_lick_timestamps(
                angle_per_frame, fps, ev.tone_frame_idx, per_lick_v[j],
            )
        angle_at_vpeak.append(per_lick_angle_at_v)
        angle_max_signed.append(_extract_angle_max_signed_per_lick(
            angle_per_frame, fps, ev.tone_frame_idx,
            per_lick_v, peak_pad_ms,
        ))

        # Cell 42 traces per-side aggregation: gather apply-window peaks.
        # Use per-cell-overridden detector (matches the per-trial reductions
        # path) so legacy_approximate parity stays consistent.
        peaks_for_traces = _slope_detect_lick_peaks(
            y_slice, x_slice, t_ms, fps,
            detect_win_ms=tuple(tp["licking_dyn_detect_win_ms"]),
            detector_params=_per_cell_detector(params, "cell42"),
        )
        apply_lo, apply_hi = tuple(tp["licking_dyn_apply_win_ms"])
        in_apply = (
            (peaks_for_traces.peak_times_ms >= apply_lo)
            & (peaks_for_traces.peak_times_ms <= apply_hi)
        )
        apply_peaks = peaks_for_traces.peak_times_ms[in_apply]
        if ev.side in apply_peaks_per_side:
            apply_peaks_per_side[ev.side].append(apply_peaks)

        # Phase 7a.4 visual-bundle compute (additive; emit-set untouched).
        # Uses Cell 50's own windows from the tongue_visual.bundle block.
        v_trial, v_bouts, v_phase = _build_visual_bundle_per_trial(
            trial_index=int(ev.trial_index),
            side=ev.side,
            x_final=x_final,
            y_final=y_final,
            angle_per_frame=angle_per_frame,
            tone_frame_idx=int(ev.tone_frame_idx),
            fps=fps,
            plot_win_ms=bundle_plot_win,
            detect_win_ms=bundle_detect_win,
            first_peak_align_win_ms=bundle_first_peak_win,
            detector_params=bundle_detector,
            max_ili_ms=bundle_max_ili,
            single_bout_win_ms=bundle_single_bout_win,
            max_licks_per_trial=bundle_max_licks,
            phase_bin_edges=phase_bin_edges,
            phase_bin_centers=phase_bin_centers,
        )
        visual_trial_rows.append(v_trial)
        visual_bout_rows.extend(v_bouts)
        visual_phase_rows.extend(v_phase)

    # Step 6: traces.
    traces_df = _extract_licking_dynamics_traces(
        apply_peaks_per_side, params=params,
    )

    # Step 7: session inclusion (Q9 lock 2026-04-28; placement realigned to
    # Cell 50 own-bout per kickoff §3a).
    #   n_time_trials       = trials with finite cell50.first_peak_t_ms
    #   n_first_peak_trials = trials with finite lick1_t_peak_ms (Cell 33)
    #   n_phase_licks       = sum(cell50.n_licks_in_first_multi_bout) across trials
    #   n_phase_trials      = trials with cell50.n_multi_lick_bouts >= 1
    n_time_trials = sum(
        1 for r in cell50_own if np.isfinite(r["first_peak_t_ms"])
    )
    n_first_peak_trials = sum(
        1 for r in lick12_records if np.isfinite(r["lick1_t_peak_ms"])
    )
    n_phase_licks = int(sum(
        int(r["n_licks_in_first_multi_bout"]) for r in cell50_own
    ))
    n_phase_trials = sum(
        1 for r in cell50_own if int(r["n_multi_lick_bouts"]) >= 1
    )
    inclusion = _evaluate_session_inclusion(
        n_time_trials=n_time_trials,
        n_first_peak_trials=n_first_peak_trials,
        n_phase_licks=n_phase_licks,
        n_phase_trials=n_phase_trials,
        params=params,
    )

    # Step 8: pack outputs.
    angle_df = pd.DataFrame({
        "frame_idx": np.arange(n_frames_session, dtype=np.int64),
        "angle_deg_smoothed": angle_per_frame.astype(np.float64),
    })

    angle_meta = {
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "fps": repr(fps),
        "n_frames": str(n_frames_session),
        "center_mode": "centered_spout_midpoint",
        "eye_in_spout_frame_x": repr(float(eye_x)),
        "eye_in_spout_frame_y": repr(float(eye_y)),
        "smoothing_gaussian_sigma_ms": repr(
            float(tp["angle"]["smoothing_gaussian_sigma_ms"]),
        ),
        "angle_sign_flip": repr(float(tp["angle"]["sign_flip"])),
        "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
        "interpolation_version": INTERPOLATION_VERSION,
    }

    ld = tp["licking_dynamics"]
    bout = tp["bout"]
    apply_win_dyn = tuple(tp["licking_dyn_apply_win_ms"])
    traces_meta = {
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "fps": repr(fps),
        "n_trials": str(int(n_trials)),
        "bin_ms": repr(float(ld["bin_ms"])),
        "lickrate_smooth_sigma_ms": repr(float(ld["lickrate_smooth_sigma_ms"])),
        "ili_smooth_sigma_ms": repr(float(ld["ili_smooth_sigma_ms"])),
        "prob_smooth_movavg_ms": repr(float(ld["prob_smooth_movavg_ms"])),
        "bout_max_ili_ms": repr(float(bout["max_ili_ms"])),
        "bout_min_ili_ms": repr(float(bout["min_ili_ms"])),
        "min_licks_in_bout_for_ili": str(int(bout["min_licks_in_bout_for_ili"])),
        "min_trials_per_bin": str(int(ld["min_trials_per_bin"])),
        "max_licks_per_trial": str(int(ld["max_licks_per_trial"])),
        "apply_win_start_ms": repr(float(apply_win_dyn[0])),
        "apply_win_end_ms": repr(float(apply_win_dyn[1])),
        "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
        "interpolation_version": INTERPOLATION_VERSION,
    }

    endpoints_payload = {
        "schema_version": FEATURE_EXTRACTION_VERSION,
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "n_trials": int(n_trials),
        "trial_indices": trial_indices,
        "sides": sides,
        "tongue": {
            "lick1_lick2_metrics": {
                "lick1_y_peak": [r["lick1_y_peak"] for r in lick12_records],
                "lick1_t_peak_ms": [r["lick1_t_peak_ms"] for r in lick12_records],
                "lick1_x_at_ypeak":
                    [r["lick1_x_at_ypeak"] for r in lick12_records],
                "lick2_y_peak": [r["lick2_y_peak"] for r in lick12_records],
                "lick2_t_peak_ms": [r["lick2_t_peak_ms"] for r in lick12_records],
                "lick2_x_at_ypeak":
                    [r["lick2_x_at_ypeak"] for r in lick12_records],
            },
            "peak_velocity_per_lick": {
                "vy_peaks_bylick": [r["vy_peaks_bylick"] for r in velocity_records],
                "vxy_peaks_bylick":
                    [r["vxy_peaks_bylick"] for r in velocity_records],
                "lick_t_peaks_bylick":
                    [r["lick_t_peaks_bylick"] for r in velocity_records],
            },
            "n_licks_family": {
                "n_licks": [int(r["n_licks"]) for r in n_licks_records],
                "n_left": [int(r["n_left"]) for r in n_licks_records],
                "n_right": [int(r["n_right"]) for r in n_licks_records],
                "n_other": [int(r["n_other"]) for r in n_licks_records],
                "lick_ge10": [bool(r["lick_ge10"]) for r in n_licks_records],
                "n_licks_per_bin":
                    [r["n_licks_per_bin"] for r in n_licks_records],
            },
            "licking_dynamics_reductions": {
                "bout_count": [int(r["bout_count"]) for r in licking_dyn_records],
                "mean_within_bout_ili_ms":
                    [r["mean_within_bout_ili_ms"] for r in licking_dyn_records],
                "lick_rate_hz":
                    [r["lick_rate_hz"] for r in licking_dyn_records],
            },
            "tongue_angle": {
                "lick1_angle_at_ypeak": angle_at_lick1,
                "lick2_angle_at_ypeak": angle_at_lick2,
                "angle_at_peak_velocity_bylick": angle_at_vpeak,
                "angle_max_signed_per_lick": angle_max_signed,
            },
            "cell50_own_bout_scalars": {
                "n_peaks": [int(r["n_peaks"]) for r in cell50_own],
                "n_bouts": [int(r["n_bouts"]) for r in cell50_own],
                "n_multi_lick_bouts":
                    [int(r["n_multi_lick_bouts"]) for r in cell50_own],
                "first_peak_t_ms":
                    [r["first_peak_t_ms"] for r in cell50_own],
                "n_licks_in_first_multi_bout": [
                    int(r["n_licks_in_first_multi_bout"]) for r in cell50_own
                ],
            },
        },
        "session_inclusion": inclusion,
        "metadata": {
            "fps": float(fps),
            "n_frames": int(n_frames_session),
            "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
            "interpolation_version": INTERPOLATION_VERSION,
            "eye_in_spout_frame_x": float(eye_x),
            "eye_in_spout_frame_y": float(eye_y),
            "angle_sign_flip": float(tp["angle"]["sign_flip"]),
            "smoothing_gaussian_sigma_ms":
                float(tp["angle"]["smoothing_gaussian_sigma_ms"]),
        },
    }

    tp_result = TonguePertrialResult(
        angle_per_frame=angle_df,
        licking_dynamics_traces=traces_df,
        endpoints=endpoints_payload,
        angle_metadata=angle_meta,
        licking_dynamics_metadata=traces_meta,
    )

    # Phase 7a.4 visual bundle. df_trials carries per-trial array columns
    # (object-typed in pandas because each cell holds a numpy array of
    # n_timebins floats). df_bouts uses the legacy mixed-rows schema; an
    # empty bout list yields an empty DataFrame with all expected columns.
    _BOUT_COLUMNS = [
        "side", "trial_index", "bout_idx", "bout_rank", "multi_bout_rank",
        "n_peaks", "bout_t0_ms", "bout_t1_ms",
        "peak_t0_ms", "peak_t1_ms", "peak_y0", "peak_angle0",
        "peak_y1", "peak_angle1",
        "peak_t_ms", "peak_y", "peak_x", "peak_angle_deg",
    ]
    _PHASE_COLUMNS = [
        "side", "trial_index", "bout_idx", "bout_rank", "multi_bout_rank",
        "t_ms", "phase", "phase_bin", "phase_bin_center",
        "angle_deg", "x_geom", "y_geom",
    ]
    df_trials = pd.DataFrame(visual_trial_rows)
    df_bouts = (
        pd.DataFrame(visual_bout_rows)
        if visual_bout_rows
        else pd.DataFrame(columns=_BOUT_COLUMNS)
    )
    df_phase = (
        pd.DataFrame(visual_phase_rows)
        if visual_phase_rows
        else pd.DataFrame(columns=_PHASE_COLUMNS)
    )
    bundle_metadata = {
        "animal": manifest.animal,
        "date": manifest.date.isoformat(),
        "fps": float(fps),
        "n_frames": int(n_frames_session),
        "eye_in_spout_frame_x": float(eye_x),
        "eye_in_spout_frame_y": float(eye_y),
        "angle_sign_flip": float(tp["angle"]["sign_flip"]),
        "smoothing_gaussian_sigma_ms":
            float(tp["angle"]["smoothing_gaussian_sigma_ms"]),
        "feature_extraction_version": FEATURE_EXTRACTION_VERSION,
        "interpolation_version": INTERPOLATION_VERSION,
        "plot_win_ms": list(bundle_plot_win),
        "detect_win_ms": list(bundle_detect_win),
        "first_peak_align_win_ms": list(bundle_first_peak_win),
        "n_phase_bins": int(n_phase_bins),
        "max_licks_per_trial": int(bundle_max_licks),
        # Phase 7a.4-cross-session-angle Addendum #12 (2026-05-04):
        # per-animal pre-stroke median ILI (ms). Synthetic cycle width
        # for isolated-lick (and last-peak-of-multi-bout) cycles in
        # the centered-phase plots. ``NaN`` = "not available" — the
        # renderer interprets that as "fall back to multi-bout-only
        # behaviour" (no isolated-lick contribution). Populated by the
        # by-animal-date wrapper
        # :func:`build_tongue_visual_bundle_by_animal_date` which
        # calls :func:`get_pre_stroke_median_ili_ms` (cached). The
        # lower-level builder :func:`build_tongue_visual_bundle`
        # accepts an explicit value so the cohort driver / median ILI
        # walker can short-circuit recursive computation.
        "pre_stroke_median_ili_ms": (
            float(pre_stroke_median_ili_ms)
            if pre_stroke_median_ili_ms is not None
            else float("nan")
        ),
    }
    visual_bundle = TongueVisualBundle(
        df_trials=df_trials,
        df_bouts=df_bouts,
        df_phase=df_phase,
        angle_per_frame=angle_df,
        metadata=bundle_metadata,
    )

    return _PertrialCoreResult(
        tongue_pertrial=tp_result,
        visual_bundle=visual_bundle,
        v7_trial_results=v7_trial_results,
    )
