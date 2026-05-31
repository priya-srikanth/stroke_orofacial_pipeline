"""Jaw v3.4 cleanup — produce ``cleaned_traces/jaw/<animal>/<date>.parquet``.

Phase 7f "Step 1" producer, reconstructed in-repo (chore
``substrate-routing-and-secondary-spout-per-half-fix`` Stage 0b, 2026-05-31).

The original Step-1 producer (`reemit_jaw_clean_traces.py`, commit aa5a524 on
``investigation/jaw-quality-audit``) was a gitignored scratch script never
committed. The cleanup ALGORITHM survives in
``.scratch_phase_7f_scoping/audit_jaw_cleanup_sim_v3p4.py`` (``compute_v3_clean_trace``);
this module lifts it into the package and adds the production producer (loop +
write parquet) that the scratch script provided. A byte-content parity test
(``tests/test_jaw_cleanup_v34.py``) re-derives an existing on-disk cleaned
parquet and asserts equality — the critical gate that surfaces any
translation error.

Algorithm (operates on the Phase 7a.2 v5p3 ``interpolated_traces/jaw`` parquet,
at the RAW level — frames with ``fill_method == 0``):

  - **R1-y** Y-ceiling: wipe RAW frames with ``y - bmean_y > Y_CEILING_PX``
    (positive side only).
  - **R1-x** X-ceiling: wipe RAW frames with ``|x - bmean_x| > X_CEILING_PX``
    (bidirectional).
  - **R3** frame-outlier on Y: cross-cluster ``median_filter`` on the raw-frame
    array; wipe deviations ``> FRAME_JUMP_THR_PX``.
  - **R2** isolated-short: wipe raw clusters ``<= ISOLATED_MAX_N`` frames with
    no other raw cluster within ``+- ISOLATED_RADIUS_MS``.
  - **R4** re-PCHIP both x AND y from the surviving anchor set over gaps
    ``<= MAX_GAP_MS_PCHIP``; gaps beyond that fall to baseline (x=0, y=0 in
    centered coords).

Baselines (``bmean_y``, ``bmean_x``) are session-level: the median over the
per-trial baseline-window means, matching the scratch sim's ~100x-faster
session-level hoist.
"""
from __future__ import annotations

import datetime
import json
from typing import Any, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import median_filter

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    _derive_trial_events_from_spout_behavior,
)
from stroke_orofacial.manifest import SessionManifest, build_manifest
from stroke_orofacial.paths import PathResolver

# v3.4 cleanup constants (locked across the Phase 7f scoping addenda; values
# stamped into every cleaned parquet's cleanup_constants_json metadata).
CLEANUP_VERSION = "v3.4"
Y_CEILING_PX = 125.0
X_CEILING_PX = 40.0  # v3.4: bidirectional |x - bmean_x| > 40 (Priya 2026-05-26)
ISOLATED_MAX_N = 5
ISOLATED_RADIUS_MS = 30.0
FRAME_JUMP_THR_PX = 70.0
FRAME_OUTLIER_LOCAL_MEDIAN_MS = 20.0
MAX_GAP_MS_PCHIP = 120.0  # jaw v5p3 default; gaps > this fall to baseline
BASELINE_WIN_MS = (-500.0, 0.0)

# fill_method encoding (matches the v5p3 interpolated_traces schema):
#   0 = raw (kept anchor), 1 = interp/PCHIP, 3 = baseline-fill (x=0, y=0).
_FM_RAW, _FM_INTERP, _FM_BASELINE = 0, 1, 3

# Exact cleanup_constants_json content (key order + text matched to the
# on-disk parquets so the metadata is byte-identical under json.dumps).
_CLEANUP_CONSTANTS: dict[str, Any] = {
    "cleanup_version": CLEANUP_VERSION,
    "Y_CEILING_PX": Y_CEILING_PX,
    "X_CEILING_PX": X_CEILING_PX,
    "ISOLATED_MAX_N": ISOLATED_MAX_N,
    "ISOLATED_RADIUS_MS": ISOLATED_RADIUS_MS,
    "FRAME_JUMP_THR_PX": FRAME_JUMP_THR_PX,
    "FRAME_OUTLIER_LOCAL_MEDIAN_MS": FRAME_OUTLIER_LOCAL_MEDIAN_MS,
    "MAX_GAP_MS_PCHIP": MAX_GAP_MS_PCHIP,
    "rules_applied": [
        "R1-y Y-ceiling on RAW frames (y - bmean_y > Y_CEILING_PX, "
        "positive-side only)",
        "R1-x X-ceiling on RAW frames (|x - bmean_x| > X_CEILING_PX, "
        "bidirectional)",
        "R3 frame-outlier on Y (cross-cluster median_filter on raw-frame "
        "array)",
        "R2 isolated-short (raw clusters <=5 frames with no other raw within "
        "+-30ms)",
        "R4 re-PCHIP from surviving anchors over gaps <= MAX_GAP_MS_PCHIP "
        "— BOTH x and y",
        "gaps > MAX_GAP_MS_PCHIP fall to baseline (y=0, x=0 in centered "
        "coords)",
    ],
    "note": (
        "Wipe masks applied to BOTH x and y consistently (R1-y, R1-x, R2, R3 "
        "union). Re-PCHIP both x and y from the same surviving anchor index "
        "set so (x_final, y_final) pairs are co-temporally consistent. "
        "Baselines (bmean_y, bmean_x) computed as median over per-trial "
        "baseline window."
    ),
}


def cleanup_constants_json() -> str:
    """Return the exact ``cleanup_constants_json`` metadata string."""
    return json.dumps(_CLEANUP_CONSTANTS)


def _ms_to_frames(ms: float, fps: float) -> int:
    return int(np.round((ms / 1000.0) * fps))


def _raw_clusters(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return ``[start, end)`` index runs where ``mask`` is True."""
    n = len(mask)
    clusters: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i + 1
        while j < n and mask[j]:
            j += 1
        clusters.append((i, j))
        i = j
    return clusters


def compute_v3_clean_trace(
    y_final: np.ndarray,
    fill_method: np.ndarray,
    baseline_mean: float,
    fps: float,
    *,
    x_final: np.ndarray | None = None,
    baseline_mean_x: float = float("nan"),
    y_ceiling_px: float = Y_CEILING_PX,
    x_ceiling_px: float = X_CEILING_PX,
    isolated_max_n: int = ISOLATED_MAX_N,
    isolated_radius_ms: float = ISOLATED_RADIUS_MS,
    frame_jump_thr_px: float = FRAME_JUMP_THR_PX,
    frame_outlier_radius_ms: float = FRAME_OUTLIER_LOCAL_MEDIAN_MS,
    max_gap_ms_pchip: float = MAX_GAP_MS_PCHIP,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return v3.4-cleaned ``y`` + the four wipe masks per rule.

    Faithful port of ``audit_jaw_cleanup_sim_v3p4.compute_v3_clean_trace``.

    Returns
    -------
    y_clean : (n,) float64
    wiped_y : (n,) bool  — R1-y Y-ceiling wipes (positive side only)
    wiped_x : (n,) bool  — R1-x X-ceiling wipes (bidirectional)
    wiped_iso : (n,) bool  — R2 isolated-short wipes
    wiped_fo : (n,) bool  — R3 frame-outlier (y) wipes
    """
    n = len(y_final)
    is_raw = (fill_method == _FM_RAW)

    # R1-y: hard Y-ceiling on raw frames (positive side only).
    if np.isfinite(baseline_mean):
        wiped_y = (
            is_raw & np.isfinite(y_final)
            & ((y_final - baseline_mean) > y_ceiling_px)
        )
    else:
        wiped_y = np.zeros(n, dtype=bool)

    # R1-x: bidirectional X-ceiling on raw frames.
    wiped_x = np.zeros(n, dtype=bool)
    if x_final is not None and np.isfinite(baseline_mean_x):
        wiped_x = (
            is_raw & np.isfinite(x_final)
            & (np.abs(x_final - baseline_mean_x) > x_ceiling_px)
        )

    # R3: frame-level outlier using neighbor raw frames across cluster
    # boundaries — local median over the K nearest raw frames.
    is_raw_after_r1 = is_raw & ~wiped_y & ~wiped_x
    wiped_fo = np.zeros(n, dtype=bool)
    frame_outlier_radius_f = max(
        _ms_to_frames(frame_outlier_radius_ms, fps), 1,
    )
    raw_after_r1_idx = np.where(is_raw_after_r1)[0]
    if raw_after_r1_idx.size >= 3:
        raw_y_arr = y_final[raw_after_r1_idx]
        window = 2 * frame_outlier_radius_f + 1
        local_med = median_filter(raw_y_arr, size=window, mode="nearest")
        deviation = np.abs(raw_y_arr - local_med)
        is_outlier = deviation > frame_jump_thr_px
        wiped_fo[raw_after_r1_idx[is_outlier]] = True

    # R2: isolated-short cluster wipe (clusters after R1 + R3).
    is_raw_after_r1_r3 = is_raw & ~wiped_y & ~wiped_fo
    clusters = _raw_clusters(is_raw_after_r1_r3)
    wiped_iso = np.zeros(n, dtype=bool)
    isolated_radius_f = max(_ms_to_frames(isolated_radius_ms, fps), 1)
    for k, (s, e) in enumerate(clusters):
        if (e - s) > isolated_max_n:
            continue
        win_lo = s - isolated_radius_f
        win_hi = e + isolated_radius_f
        has_nearby = False
        for k2, (s2, e2) in enumerate(clusters):
            if k2 == k:
                continue
            if e2 <= win_lo:
                continue
            if s2 >= win_hi:
                break
            has_nearby = True
            break
        if not has_nearby:
            wiped_iso[s:e] = True

    # Final surviving-anchor mask + re-PCHIP y over gaps <= cap.
    is_raw_final = is_raw & ~wiped_y & ~wiped_x & ~wiped_fo & ~wiped_iso
    anchor_idx = np.where(is_raw_final & np.isfinite(y_final))[0]
    y_clean, _ = _repchip_over_anchors(
        y_final, anchor_idx, n, max(_ms_to_frames(max_gap_ms_pchip, fps), 1),
    )
    return y_clean, wiped_y, wiped_x, wiped_iso, wiped_fo


def _repchip_over_anchors(
    values: np.ndarray,
    anchor_idx: np.ndarray,
    n: int,
    max_gap_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    """PCHIP-fill ``values`` over ``anchor_idx`` for gaps <= ``max_gap_frames``.

    Returns ``(clean, fillable)`` where ``clean`` is ``0`` outside fillable
    gaps (baseline), the raw value at anchors, and the PCHIP value in fillable
    gaps; ``fillable`` is the boolean mask of non-anchor frames that received a
    PCHIP value.
    """
    clean = np.zeros(n, dtype=np.float64)
    fillable = np.zeros(n, dtype=bool)
    if anchor_idx.size >= 2:
        anchor_v = values[anchor_idx]
        pchip = PchipInterpolator(anchor_idx, anchor_v, extrapolate=False)
        all_idx = np.arange(n)
        v_pchip_all = pchip(all_idx)
        prev_loc = np.searchsorted(anchor_idx, all_idx, side="right") - 1
        next_loc = prev_loc + 1
        valid_pair = (prev_loc >= 0) & (next_loc < len(anchor_idx))
        gap_len = np.where(
            valid_pair,
            anchor_idx[np.clip(next_loc, 0, len(anchor_idx) - 1)]
            - anchor_idx[np.clip(prev_loc, 0, len(anchor_idx) - 1)] - 1,
            np.iinfo(np.int64).max,
        )
        fillable = (
            valid_pair
            & (gap_len <= max_gap_frames)
            & np.isfinite(v_pchip_all)
        )
        clean[fillable] = v_pchip_all[fillable]
        clean[anchor_idx] = anchor_v
    elif anchor_idx.size == 1:
        clean[anchor_idx] = values[anchor_idx]
    return clean, fillable


def compute_session_baselines(
    x_final: np.ndarray,
    y_final: np.ndarray,
    trial_events: Sequence[Any],
    fps: float,
    n_frames: int,
) -> tuple[float, float] | None:
    """Session-level baselines: median of per-trial baseline-window means.

    Returns ``(bmean_y, bmean_x)`` or ``None`` if no trial yields a finite
    y baseline (session is unusable for cleanup).
    """
    base_lo = _ms_to_frames(BASELINE_WIN_MS[0], fps)
    base_hi = _ms_to_frames(BASELINE_WIN_MS[1], fps)
    bmeans_y: list[float] = []
    bmeans_x: list[float] = []
    for ev in trial_events:
        tone_fi = int(ev.tone_frame_idx)
        if tone_fi < 0 or tone_fi >= n_frames:
            continue
        lo = max(tone_fi + base_lo, 0)
        hi = min(tone_fi + base_hi + 1, n_frames)
        yb = y_final[lo:hi]
        yb = yb[np.isfinite(yb)]
        if yb.size >= 2:
            bmeans_y.append(float(np.mean(yb)))
        xb = x_final[lo:hi]
        xb = xb[np.isfinite(xb)]
        if xb.size >= 2:
            bmeans_x.append(float(np.mean(xb)))
    if not bmeans_y:
        return None
    bmean_y = float(np.median(bmeans_y))
    bmean_x = float(np.median(bmeans_x)) if bmeans_x else 0.0
    return bmean_y, bmean_x


def clean_jaw_session_arrays(
    x_final: np.ndarray,
    y_final: np.ndarray,
    fill_method: np.ndarray,
    baseline_mean: float,
    baseline_mean_x: float,
    fps: float,
) -> dict[str, np.ndarray]:
    """Apply the full v3.4 cleanup to a session's jaw arrays.

    Re-PCHIPs BOTH x and y from the same surviving anchor set. Returns a dict
    with ``x_final``, ``y_final`` (float64), ``fill_method`` (int8),
    ``is_interp_fill`` (bool), ``is_baseline_fill`` (bool).
    """
    n = len(y_final)
    _, wiped_y, wiped_x, wiped_iso, wiped_fo = compute_v3_clean_trace(
        y_final, fill_method, baseline_mean, fps,
        x_final=x_final, baseline_mean_x=baseline_mean_x,
    )
    is_raw = (fill_method == _FM_RAW)
    is_raw_final = is_raw & ~wiped_y & ~wiped_x & ~wiped_fo & ~wiped_iso
    anchor_idx = np.where(is_raw_final & np.isfinite(y_final))[0]
    max_gap_frames = max(_ms_to_frames(MAX_GAP_MS_PCHIP, fps), 1)

    y_clean, fillable = _repchip_over_anchors(
        y_final, anchor_idx, n, max_gap_frames,
    )
    x_clean, _ = _repchip_over_anchors(
        x_final, anchor_idx, n, max_gap_frames,
    )

    is_anchor = np.zeros(n, dtype=bool)
    is_anchor[anchor_idx] = True
    fm = np.full(n, _FM_BASELINE, dtype=np.int8)
    fm[fillable] = _FM_INTERP
    fm[is_anchor] = _FM_RAW
    return {
        "x_final": x_clean,
        "y_final": y_clean,
        "fill_method": fm,
        "is_interp_fill": fm == _FM_INTERP,
        "is_baseline_fill": fm == _FM_BASELINE,
    }


def _write_cleaned_jaw_parquet(
    in_path,
    out_path,
    cleaned: dict[str, np.ndarray],
) -> None:
    """Write the cleaned jaw parquet, preserving the v5p3 input schema +
    metadata and adding ``cleanup_version`` + ``cleanup_constants_json``.

    Atomic via a ``.tmp`` sibling. The output is a v5p3-compatible drop-in:
    same columns, dtypes, and metadata as the interpolated_traces parquet,
    with cleaned ``x_final``/``y_final``/flag columns substituted.
    """
    in_table = pq.read_table(str(in_path))
    cols = {name: in_table.column(name) for name in in_table.column_names}
    # Substitute the cleaned columns, preserving each column's arrow type.
    for name in (
        "x_final", "y_final", "fill_method", "is_interp_fill",
        "is_baseline_fill",
    ):
        cols[name] = pa.array(
            cleaned[name], type=in_table.schema.field(name).type,
        )
    md = dict(in_table.schema.metadata or {})
    md[b"cleanup_version"] = CLEANUP_VERSION.encode()
    md[b"cleanup_constants_json"] = cleanup_constants_json().encode()
    out_table = pa.table(
        [cols[name] for name in in_table.column_names],
        names=in_table.column_names,
    ).replace_schema_metadata(md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    pq.write_table(out_table, str(tmp))
    tmp.replace(out_path)


def build_jaw_cleaned_trace(
    manifest: SessionManifest,
    resolver: PathResolver,
    trial_events: Sequence[Any],
    *,
    overwrite: str = "force",
):
    """Produce the v3.4 ``cleaned_traces/jaw`` parquet for one session.

    Reads the Phase 7a.2 v5p3 ``interpolated_traces/jaw`` parquet, computes
    session baselines from ``trial_events``, applies the v3.4 cleanup, and
    writes the cleaned parquet. Returns the output ``Path``, or ``None`` if the
    input is missing or the session has no usable baseline.
    """
    animal, date = manifest.animal, manifest.date
    in_path = resolver.interpolated_trace("jaw", animal, date)
    if not in_path.exists():
        return None
    out_path = resolver.cleaned_trace(bodypart="jaw", animal=animal, date=date)
    if out_path.exists() and overwrite == "skip":
        return out_path

    df = pd.read_parquet(
        in_path,
        columns=["x_final", "y_final", "fill_method"],
    )
    meta = pq.read_schema(str(in_path)).metadata or {}
    fps = float(meta[b"fps"].decode())
    n_frames = int(meta[b"n_frames"].decode())
    x = df["x_final"].to_numpy(dtype=np.float64)
    y = df["y_final"].to_numpy(dtype=np.float64)
    fm = df["fill_method"].to_numpy()

    baselines = compute_session_baselines(x, y, trial_events, fps, n_frames)
    if baselines is None:
        return None
    bmean_y, bmean_x = baselines

    cleaned = clean_jaw_session_arrays(x, y, fm, bmean_y, bmean_x, fps)
    _write_cleaned_jaw_parquet(in_path, out_path, cleaned)
    return out_path


def build_jaw_cleaned_trace_by_animal_date(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    overwrite: str = "force",
    animal_info: AnimalInfo | None = None,
):
    """Convenience wrapper: build the manifest + trial events, then clean.

    Returns the output ``Path`` or ``None`` (missing input, no trial events,
    or no usable baseline).
    """
    if animal_info is None:
        animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.jaw_pertrial",
    )
    if manifest.excluded:
        return None
    try:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
    except Exception:
        return None
    if not trial_events:
        return None
    return build_jaw_cleaned_trace(
        manifest, resolver, trial_events, overwrite=overwrite,
    )
