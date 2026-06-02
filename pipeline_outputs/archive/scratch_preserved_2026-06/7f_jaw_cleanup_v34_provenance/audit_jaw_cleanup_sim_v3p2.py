"""Phase 7f scoping audit #5 — pre-Stage-4 cleanup simulation v3.

Addendum #6 pivot (Priya 2026-05-26): exclusion rules must operate at
the RAW DLC level, BETWEEN Stage 3 (drop low-lk + isolated-hi-lk) and
Stage 4 (PCHIP gap-fill). v2's post-v5p3 cleanup framework was wrong —
it could pick PCHIP-bridged values as "peaks" (e.g., PS54 / 5-05 /
t010 L where clean_peak landed at lk=0.05, a frame that was dropped at
Stage 2 and PCHIP-interpolated). Pre-Stage-4 cleanup means
interpolation never sees the artifact frames as anchors, so the
resulting trace doesn't bridge through them.

Simulation strategy (no production code touched):
  1. Load v5p3 parquet (y_final, likelihood_raw, fill_method).
  2. Identify the v5p3-kept RAW set: frames with `fill_method == 0`.
     These are the frames that survived Stages 1-3 (X-range filter,
     lk_thr=0.5, isolated-hi-lk drop).
  3. Apply pre-clean to the RAW set:
     R1 Y-ceiling   — drop raw frames with `(y_final - baseline_mean) > 80`.
     R3 Frame outlier — drop raw frames with
         `|y - rolling_median(±20ms within cluster)| > 80`.
     R2 Isolated-short — drop raw clusters of length ≤ 5 frames
         surrounded by long gaps (no other raw cluster within ±30ms).
  4. Re-interpolate: PCHIP-bridge surviving anchors over gaps ≤ 120 ms
     (jaw v5p3 max_gap_ms cap), leave longer gaps at baseline (y=0 in
     y_final coordinates by Stage 5 baseline-fill convention).
  5. Recompute jaw_pertrial peak + pass_qc on the cleaned y_final.

Outputs at `.scratch_phase_7f_scoping/audit_results/cleanup_sim_v3/`:
  - per_trial_cleanup_v3p2.parquet
  - by_phenotype_epoch_cleanup_v3p2.csv
  - jaw_pass_qc_flip_table_v3p2.csv
  - sign_flip_prod_vs_cleanup_v3p2.csv
  - wipe_prevalence_v3p2.csv
  - cohort_mean_delta_bar_v3p2.png + pass_qc_rate plot

Visual renders at `.scratch_phase_7f_scoping/visual_renders_cleanup_v3/`:
  - 8 severe-acute trials with v3 cleanup overlay.
"""
from __future__ import annotations

import logging
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import median_filter

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from stroke_orofacial.animals import get_animal  # noqa: E402
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates  # noqa: E402
from stroke_orofacial.config_loader import load_session_overrides  # noqa: E402
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (  # noqa: E402
    _derive_trial_events_from_spout_behavior,
)
from stroke_orofacial.manifest import (  # noqa: E402
    build_manifest,
    load_secondary_spout_sessions,
)
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402

ANIMALS = ["PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55"]
BASELINE_WIN_MS = (-500.0, 0.0)
DETECT_WIN_MS = (0.0, 5000.0)

# v3.1 cleanup constants. Frame-outlier threshold tightened from
# v3's 80 → 70 px per Priya 2026-05-26 visual review (PS54 / 5-01 /
# t013 R has a low-outlier at ~150ms with ~75 px deviation from local
# median, just under v3's 80 px threshold).
Y_CEILING_PX = 80.0
ISOLATED_MAX_N = 5
ISOLATED_RADIUS_MS = 30.0
FRAME_JUMP_THR_PX = 70.0                       # v3 was 80
FRAME_OUTLIER_LOCAL_MEDIAN_MS = 20.0
MAX_GAP_MS_PCHIP = 120.0     # jaw v5p3 default; gaps > this fall to baseline

# jaw_pertrial constants (matches `configs/defaults.yaml`).
JAW_THRESH_SD_MULT = 4.0
JAW_THRESH_MIN_PX = 4.0
JAW_SUSTAINED_DENSITY = 0.625
JAW_SUSTAINED_WINDOW_N = 8

OUT_DIR = Path(__file__).parent / "audit_results" / "cleanup_sim_v3p2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RENDER_DIR = Path(__file__).parent / "visual_renders_cleanup_v3p2"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

LOG = logging.getLogger("audit_cleanup_v3p2")


# ===========================================================================
# Numeric helpers
# ===========================================================================


def _ms_to_frames(ms: float, fps: float) -> int:
    return int(np.round((ms / 1000.0) * fps))


# ===========================================================================
# v3 cleanup — applied at RAW level (fill_method == 0 frames)
# ===========================================================================


def compute_v3_clean_trace(
    y_final: np.ndarray,
    fill_method: np.ndarray,
    baseline_mean: float,
    fps: float,
    *,
    y_ceiling_px: float = Y_CEILING_PX,
    isolated_max_n: int = ISOLATED_MAX_N,
    isolated_radius_ms: float = ISOLATED_RADIUS_MS,
    frame_jump_thr_px: float = FRAME_JUMP_THR_PX,
    frame_outlier_radius_ms: float = FRAME_OUTLIER_LOCAL_MEDIAN_MS,
    max_gap_ms_pchip: float = MAX_GAP_MS_PCHIP,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return v3-cleaned y_final + wipe masks per rule.

    Strategy:
      1. raw_kept = frames where fill_method == 0 AND survived all
         three pre-clean rules.
      2. Re-PCHIP raw_kept anchors over gaps ≤ max_gap_ms_pchip.
      3. Longer gaps → y = 0 (baseline-fill convention).
      4. Frames not in any gap (i.e., already baseline-fill OR
         re-baseline-filled) keep y = 0.

    Returns
    -------
    y_clean : (n,) float64
        New y_final after v3 cleanup + re-interpolation.
    wiped_y : (n,) bool  — frames wiped by Rule 1.
    wiped_iso : (n,) bool  — frames wiped by Rule 2.
    wiped_fo : (n,) bool  — frames wiped by Rule 3.
    """
    n = len(y_final)
    is_raw = (fill_method == 0)

    # ---- Rule 1: hard Y-ceiling on raw frames ----
    if np.isfinite(baseline_mean):
        wiped_y = is_raw & np.isfinite(y_final) & ((y_final - baseline_mean) > y_ceiling_px)
    else:
        wiped_y = np.zeros(n, dtype=bool)

    # ---- Identify raw clusters AFTER R1 ----
    is_raw_after_r1 = is_raw & ~wiped_y
    raw_clusters_after_r1: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not is_raw_after_r1[i]:
            i += 1
            continue
        j = i + 1
        while j < n and is_raw_after_r1[j]:
            j += 1
        raw_clusters_after_r1.append((i, j))
        i = j

    # ---- Rule 3 (v3.2): frame-level outlier using NEIGHBOR RAW FRAMES
    # across cluster boundaries. v3.1's within-cluster rule missed
    # single-frame raw clusters (e.g., PS54 / 5-01 / t013 R, frame 213464
    # at t=184ms, y=-36 — a 1-frame raw cluster surrounded by baseline-fill
    # bands with the nearest other raw cluster 8ms away). v3.2 computes
    # the local median over the K nearest raw frames (K = 2*W+1 with W =
    # frame_outlier_radius_f, default 11 frames at 250 fps × ±20ms). In
    # densely-tracked regions this is equivalent to ±20ms time window; in
    # sparse regions it bridges cluster boundaries to capture single-
    # frame outliers between baseline-fill bands.
    # Vectorized via scipy.ndimage.median_filter on the raw-frame array.
    wiped_fo = np.zeros(n, dtype=bool)
    frame_outlier_radius_f = max(_ms_to_frames(frame_outlier_radius_ms, fps), 1)
    raw_after_r1_idx = np.where(is_raw_after_r1)[0]
    if raw_after_r1_idx.size >= 3:
        raw_y_arr = y_final[raw_after_r1_idx]
        window = 2 * frame_outlier_radius_f + 1
        local_med = median_filter(raw_y_arr, size=window, mode="nearest")
        deviation = np.abs(raw_y_arr - local_med)
        is_outlier = deviation > frame_jump_thr_px
        wiped_fo[raw_after_r1_idx[is_outlier]] = True

    # ---- Re-identify raw clusters AFTER R1 + R3 ----
    is_raw_after_r1_r3 = is_raw & ~wiped_y & ~wiped_fo
    raw_clusters_after_r1_r3: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if not is_raw_after_r1_r3[i]:
            i += 1
            continue
        j = i + 1
        while j < n and is_raw_after_r1_r3[j]:
            j += 1
        raw_clusters_after_r1_r3.append((i, j))
        i = j

    # ---- Rule 2: isolated-short cluster wipe ----
    wiped_iso = np.zeros(n, dtype=bool)
    isolated_radius_f = max(_ms_to_frames(isolated_radius_ms, fps), 1)
    for k, (s, e) in enumerate(raw_clusters_after_r1_r3):
        length = e - s
        if length > isolated_max_n:
            continue
        win_lo = s - isolated_radius_f
        win_hi = e + isolated_radius_f
        has_nearby = False
        for k2, (s2, e2) in enumerate(raw_clusters_after_r1_r3):
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

    # ---- Compute final kept-raw mask ----
    is_raw_final = is_raw & ~wiped_y & ~wiped_fo & ~wiped_iso

    # ---- Re-interpolate: PCHIP over gaps ≤ max_gap_ms_pchip ----
    # Vectorized: build one PCHIP interpolator over surviving anchors,
    # evaluate at all frames at once, then zero out frames that fall
    # inside gaps longer than the cap.
    y_clean = np.zeros(n, dtype=np.float64)
    anchor_idx = np.where(is_raw_final & np.isfinite(y_final))[0]
    if anchor_idx.size >= 2:
        max_gap_frames = max(_ms_to_frames(max_gap_ms_pchip, fps), 1)
        anchor_y = y_final[anchor_idx]
        pchip = PchipInterpolator(anchor_idx, anchor_y, extrapolate=False)
        all_idx = np.arange(n)
        y_pchip_all = pchip(all_idx)  # NaN outside [anchor_idx[0], anchor_idx[-1]]

        # For each non-anchor frame: determine the gap length of the
        # interval [prev_anchor, next_anchor] containing it. Fillable
        # iff gap_len_frames ≤ max_gap_frames AND we're between two
        # anchors (not at session edges).
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
            & np.isfinite(y_pchip_all)
        )
        y_clean[fillable] = y_pchip_all[fillable]
        # Anchor frames themselves take their raw y values.
        y_clean[anchor_idx] = anchor_y
    elif anchor_idx.size == 1:
        y_clean[anchor_idx] = y_final[anchor_idx]
    # else: no anchors → entire trace is baseline-fill (already y=0).

    return y_clean, wiped_y, wiped_iso, wiped_fo


# ===========================================================================
# jaw_pertrial scalar recompute (matches jaw_pertrial.py logic)
# ===========================================================================


def _check_sustained_density(
    defl_test_window: np.ndarray, threshold: float,
    window_n: int = JAW_SUSTAINED_WINDOW_N,
    density_thr: float = JAW_SUSTAINED_DENSITY,
) -> tuple[bool, int]:
    supra = np.isfinite(defl_test_window) & (np.abs(defl_test_window) > threshold)
    n_over = int(np.sum(supra))
    W = max(1, int(window_n))
    K = max(1, int(np.ceil(density_thr * W)))
    if supra.size == 0:
        return False, n_over
    if supra.size < W:
        return bool(supra.sum() >= K), n_over
    counts = np.convolve(supra.astype(int), np.ones(W, dtype=int), mode="valid")
    return bool(np.any(counts >= K)), n_over


# ===========================================================================
# Per-trial result
# ===========================================================================


@dataclass
class TrialResultV3:
    animal: str
    date: str
    rel_day: int
    epoch_label: str
    phenotype: str
    trial_index: int
    side: str
    tone_frame_idx: int

    baseline_mean: float
    baseline_sd: float

    peak_abs_prod: float
    peak_y_prod: float
    peak_t_ms_prod: float
    peak_lk_prod: float
    n_over_prod: int
    pass_qc_prod: bool

    peak_abs_clean: float
    peak_y_clean: float
    peak_t_ms_clean: float
    peak_lk_clean: float
    n_over_clean: int
    pass_qc_clean: bool

    frac_wiped_y: float
    frac_wiped_iso: float
    frac_wiped_fo: float
    frac_any_wiped: float


def _compute_pair_v3(
    *,
    animal: str,
    date_str: str,
    rel_day: int,
    epoch_label: str,
    phenotype: str,
    trial_index: int,
    side: str,
    tone_frame_idx: int,
    y_final: np.ndarray,
    y_clean_full: np.ndarray,
    lk_raw: np.ndarray,
    wiped_y_full: np.ndarray,
    wiped_iso_full: np.ndarray,
    wiped_fo_full: np.ndarray,
    fps: float,
) -> TrialResultV3:
    base_lo_f = tone_frame_idx + _ms_to_frames(BASELINE_WIN_MS[0], fps)
    base_hi_f = tone_frame_idx + _ms_to_frames(BASELINE_WIN_MS[1], fps)
    det_lo_f = tone_frame_idx + _ms_to_frames(DETECT_WIN_MS[0], fps)
    det_hi_f = tone_frame_idx + _ms_to_frames(DETECT_WIN_MS[1], fps) + 1

    y_base = y_final[max(base_lo_f, 0):min(base_hi_f + 1, len(y_final))]
    y_base_finite = y_base[np.isfinite(y_base)]
    if y_base_finite.size < 2:
        baseline_mean = float("nan")
        baseline_sd = float("nan")
    else:
        baseline_mean = float(np.nanmean(y_base_finite))
        baseline_sd = float(np.nanstd(y_base_finite))

    lo = max(det_lo_f, 0)
    hi = min(det_hi_f, len(y_final))

    y_det_prod = y_final[lo:hi]
    y_det_clean = y_clean_full[lo:hi]
    lk_det = lk_raw[lo:hi]
    wy_d = wiped_y_full[lo:hi]
    wi_d = wiped_iso_full[lo:hi]
    wf_d = wiped_fo_full[lo:hi]

    dt_idx_ms = (np.arange(lo, hi) - tone_frame_idx) * (1000.0 / fps)
    in_win = (dt_idx_ms >= DETECT_WIN_MS[0]) & (dt_idx_ms <= DETECT_WIN_MS[1])

    if not np.isfinite(baseline_mean) or baseline_sd <= 0:
        thresh_abs = float("nan")
    else:
        thresh_abs = float(max(JAW_THRESH_SD_MULT * baseline_sd, JAW_THRESH_MIN_PX))

    # Production peak.
    if not np.isfinite(baseline_mean):
        peak_abs_prod = peak_y_prod = peak_t_prod = peak_lk_prod = float("nan")
        n_over_prod = 0
        pass_qc_prod = False
    else:
        defl_prod = y_det_prod - baseline_mean
        mask_prod = in_win & np.isfinite(defl_prod)
        if not mask_prod.any():
            peak_abs_prod = peak_y_prod = peak_t_prod = peak_lk_prod = float("nan")
        else:
            abs_d = np.where(mask_prod, np.abs(defl_prod), -np.inf)
            k = int(np.argmax(abs_d))
            peak_y_prod = float(defl_prod[k])
            peak_abs_prod = float(abs(peak_y_prod))
            peak_t_prod = float(dt_idx_ms[k])
            peak_lk_prod = float(lk_det[k])
        if np.isfinite(thresh_abs):
            defl_in_win = defl_prod[in_win]
            pass_qc_prod, n_over_prod = _check_sustained_density(
                defl_in_win, thresh_abs,
            )
        else:
            n_over_prod = 0
            pass_qc_prod = False

    # v3-cleaned peak.
    if not np.isfinite(baseline_mean):
        peak_abs_clean = peak_y_clean = peak_t_clean = peak_lk_clean = float("nan")
        n_over_clean = 0
        pass_qc_clean = False
    else:
        defl_clean = y_det_clean - baseline_mean
        mask_clean = in_win & np.isfinite(defl_clean)
        if not mask_clean.any():
            peak_abs_clean = peak_y_clean = peak_t_clean = peak_lk_clean = float("nan")
        else:
            abs_d = np.where(mask_clean, np.abs(defl_clean), -np.inf)
            k = int(np.argmax(abs_d))
            peak_y_clean = float(defl_clean[k])
            peak_abs_clean = float(abs(peak_y_clean))
            peak_t_clean = float(dt_idx_ms[k])
            peak_lk_clean = float(lk_det[k])
        if np.isfinite(thresh_abs):
            defl_in_win = defl_clean[in_win]
            pass_qc_clean, n_over_clean = _check_sustained_density(
                defl_in_win, thresh_abs,
            )
        else:
            n_over_clean = 0
            pass_qc_clean = False

    return TrialResultV3(
        animal=animal, date=date_str, rel_day=rel_day,
        epoch_label=epoch_label, phenotype=phenotype,
        trial_index=trial_index, side=side, tone_frame_idx=tone_frame_idx,
        baseline_mean=baseline_mean, baseline_sd=baseline_sd,
        peak_abs_prod=peak_abs_prod, peak_y_prod=peak_y_prod,
        peak_t_ms_prod=peak_t_prod, peak_lk_prod=peak_lk_prod,
        n_over_prod=int(n_over_prod), pass_qc_prod=bool(pass_qc_prod),
        peak_abs_clean=peak_abs_clean, peak_y_clean=peak_y_clean,
        peak_t_ms_clean=peak_t_clean, peak_lk_clean=peak_lk_clean,
        n_over_clean=int(n_over_clean), pass_qc_clean=bool(pass_qc_clean),
        frac_wiped_y=float(np.mean(wy_d)),
        frac_wiped_iso=float(np.mean(wi_d)),
        frac_wiped_fo=float(np.mean(wf_d)),
        frac_any_wiped=float(np.mean(wy_d | wi_d | wf_d)),
    )


# ===========================================================================
# Driver
# ===========================================================================


def _read_jaw_parquet(path: Path) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, float, int,
]:
    df = pd.read_parquet(path, columns=[
        "y_final", "likelihood_raw", "fill_method",
    ])
    meta = pq.read_schema(path).metadata or {}
    fps = float(meta[b"fps"].decode())
    n_frames = int(meta[b"n_frames"].decode())
    return (
        df["y_final"].to_numpy(dtype=np.float64),
        df["likelihood_raw"].to_numpy(dtype=np.float64),
        df["fill_method"].to_numpy(dtype=np.int64),
        fps,
        n_frames,
    )


def _process_session(
    animal: str,
    date: Any,
    resolver: PathResolver,
    secondary_registry: dict[str, dict[str, dict[str, Any]]],
) -> list[TrialResultV3]:
    animal_info = get_animal(animal)
    iso = date.isoformat()
    if animal in secondary_registry and iso in secondary_registry[animal]:
        return []

    rel_day = (date - animal_info.stroke_date).days
    epoch_label = assign_epoch_label(rel_day, animal_info) or "transitional"
    phenotype = animal_info.recovery_phenotype or "unknown"

    jaw_path = resolver.interpolated_trace("jaw", animal, date)
    if not jaw_path.exists():
        return []

    try:
        y, lk, fm, fps, n_frames = _read_jaw_parquet(jaw_path)
    except Exception as e:
        LOG.warning("  FAIL %s/%s parquet read: %s", animal, iso, e)
        return []

    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.jaw_pertrial",
    )
    if manifest.excluded:
        return []
    try:
        trial_events = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=manifest,
        )
    except Exception as e:
        LOG.warning("  FAIL %s/%s trial-event derivation: %s", animal, iso, e)
        return []

    # Compute SESSION-MEAN baseline_mean once (median of per-trial
    # baseline_means). The per-trial variation is typically < 5 px so
    # using a session-level approximation is fine for R1 (Y-ceiling),
    # and it lets us hoist the entire cleanup (cluster walk + median
    # filter + isolated-short + PCHIP) to session level — ~100x faster
    # than per-trial. Per-trial baseline_mean still computed for the
    # threshold-test pass_qc / scalar reporting.
    trial_bmeans = []
    for ev in trial_events:
        if ev.tone_frame_idx < 0 or ev.tone_frame_idx >= n_frames:
            continue
        tone_fi = int(ev.tone_frame_idx)
        base_lo_f = tone_fi + _ms_to_frames(BASELINE_WIN_MS[0], fps)
        base_hi_f = tone_fi + _ms_to_frames(BASELINE_WIN_MS[1], fps)
        y_base = y[max(base_lo_f, 0):min(base_hi_f + 1, n_frames)]
        y_base_finite = y_base[np.isfinite(y_base)]
        if y_base_finite.size >= 2:
            trial_bmeans.append(float(np.nanmean(y_base_finite)))
    if not trial_bmeans:
        return []
    session_bmean = float(np.median(trial_bmeans))

    # Run v3 cleanup ONCE per session.
    y_clean_session, w_y_session, w_iso_session, w_fo_session = (
        compute_v3_clean_trace(y, fm, session_bmean, fps)
    )

    results: list[TrialResultV3] = []
    for ev in trial_events:
        if ev.tone_frame_idx < 0 or ev.tone_frame_idx >= n_frames:
            continue
        results.append(_compute_pair_v3(
            animal=animal, date_str=iso, rel_day=rel_day,
            epoch_label=epoch_label, phenotype=phenotype,
            trial_index=int(ev.trial_index), side=str(ev.side),
            tone_frame_idx=int(ev.tone_frame_idx),
            y_final=y, y_clean_full=y_clean_session, lk_raw=lk,
            wiped_y_full=w_y_session,
            wiped_iso_full=w_iso_session,
            wiped_fo_full=w_fo_session,
            fps=fps,
        ))
    LOG.info(
        "  OK   %s/%s (rel_day=%+d, epoch=%s) — %d trials",
        animal, iso, rel_day, epoch_label, len(results),
    )
    return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
    )
    LOG.info("Phase 7f scoping audit #5 — pre-Stage-4 cleanup sim v3")
    LOG.info(
        "Constants: Y_CEIL=%.0fpx, ISOLATED_MAX_N=%d, ISOLATED_RAD=%.0fms, "
        "FRAME_JUMP=%.0fpx, MAX_GAP_MS_PCHIP=%.0fms",
        Y_CEILING_PX, ISOLATED_MAX_N, ISOLATED_RADIUS_MS,
        FRAME_JUMP_THR_PX, MAX_GAP_MS_PCHIP,
    )
    LOG.info("Output dir: %s", OUT_DIR)

    resolver = PathResolver()
    overrides = load_session_overrides()
    secondary_registry = load_secondary_spout_sessions(overrides)

    t0 = time.time()
    all_rows: list[TrialResultV3] = []
    for animal in ANIMALS:
        LOG.info("== Animal %s ==", animal)
        dates = yaml_driven_session_dates(animal, analysis_context="dlc")
        for date in dates:
            try:
                rows = _process_session(animal, date, resolver, secondary_registry)
                all_rows.extend(rows)
            except Exception as e:
                LOG.error(
                    "  FAIL %s/%s — %s\n%s",
                    animal, date.isoformat(), e, traceback.format_exc(),
                )

    LOG.info("Total trial pairs: %d", len(all_rows))
    LOG.info("Elapsed: %.1f s", time.time() - t0)
    if not all_rows:
        LOG.error("No trials processed; aborting.")
        return

    df = pd.DataFrame([row.__dict__ for row in all_rows])
    df.to_parquet(OUT_DIR / "per_trial_cleanup_v3p2.parquet", index=False)
    LOG.info("Wrote per_trial_cleanup_v3p2.parquet (%d rows)", len(df))

    _emit_aggregates(df)
    _emit_histograms(df)
    _emit_visual_renders(df, resolver)


def _emit_aggregates(df: pd.DataFrame) -> None:
    grp = df.groupby(["phenotype", "epoch_label"])
    summary = grp.agg(
        n_animals=("animal", "nunique"),
        n_sessions=("date", "nunique"),
        n_trials=("trial_index", "count"),
        prod_mean_peak_abs=("peak_abs_prod", "mean"),
        prod_median_peak_abs=("peak_abs_prod", "median"),
        prod_mean_peak_lk=("peak_lk_prod", "mean"),
        prod_pass_qc_rate=("pass_qc_prod", "mean"),
        prod_mean_n_over=("n_over_prod", "mean"),
        clean_mean_peak_abs=("peak_abs_clean", lambda s: float(np.nanmean(s))),
        clean_median_peak_abs=("peak_abs_clean", lambda s: float(np.nanmedian(s))),
        clean_mean_peak_lk=("peak_lk_clean", lambda s: float(np.nanmean(s))),
        clean_pass_qc_rate=("pass_qc_clean", "mean"),
        clean_mean_n_over=("n_over_clean", "mean"),
        mean_frac_wiped_y=("frac_wiped_y", "mean"),
        mean_frac_wiped_iso=("frac_wiped_iso", "mean"),
        mean_frac_wiped_fo=("frac_wiped_fo", "mean"),
        mean_frac_any_wiped=("frac_any_wiped", "mean"),
    ).reset_index()
    summary["delta_mean_peak_abs"] = (
        summary["clean_mean_peak_abs"] - summary["prod_mean_peak_abs"]
    )
    summary["pct_delta_mean_peak_abs"] = (
        100.0 * summary["delta_mean_peak_abs"] / summary["prod_mean_peak_abs"]
    )
    summary["delta_pass_qc_rate"] = (
        summary["clean_pass_qc_rate"] - summary["prod_pass_qc_rate"]
    )
    summary.to_csv(OUT_DIR / "by_phenotype_epoch_cleanup_v3p2.csv", index=False)
    LOG.info("Wrote by_phenotype_epoch_cleanup_v3p2.csv (%d rows)", len(summary))

    # pass_qc flip table.
    flip_rows = []
    for (ph, ep), sub in grp:
        n = len(sub)
        prod_true = sub["pass_qc_prod"].sum()
        clean_true = sub["pass_qc_clean"].sum()
        true_to_false = ((sub["pass_qc_prod"]) & (~sub["pass_qc_clean"])).sum()
        false_to_true = ((~sub["pass_qc_prod"]) & (sub["pass_qc_clean"])).sum()
        flip_rows.append({
            "phenotype": ph, "epoch_label": ep,
            "n_trials": int(n),
            "prod_pass_qc_count": int(prod_true),
            "clean_pass_qc_count": int(clean_true),
            "prod_pass_qc_rate": float(prod_true / max(n, 1)),
            "clean_pass_qc_rate": float(clean_true / max(n, 1)),
            "n_true_to_false": int(true_to_false),
            "n_false_to_true": int(false_to_true),
            "net_change": int(clean_true - prod_true),
            "frac_flipped_any_direction": float(
                (true_to_false + false_to_true) / max(n, 1),
            ),
        })
    pd.DataFrame(flip_rows).to_csv(
        OUT_DIR / "jaw_pass_qc_flip_table_v3p2.csv", index=False,
    )
    LOG.info("Wrote jaw_pass_qc_flip_table_v3p2.csv (%d rows)", len(flip_rows))

    # Sign flips.
    flip2_rows = []
    for (ph, ep), sub in grp:
        sub_p = sub.dropna(subset=["peak_y_prod", "peak_y_clean"])
        sub_p = sub_p[(sub_p["peak_y_prod"] != 0) & (sub_p["peak_y_clean"] != 0)]
        if sub_p.empty:
            continue
        flips = np.sign(sub_p["peak_y_prod"]) != np.sign(sub_p["peak_y_clean"])
        flip2_rows.append({
            "phenotype": ph, "epoch_label": ep,
            "n_trials_compared": int(len(sub_p)),
            "n_sign_flips": int(flips.sum()),
            "frac_sign_flips": float(flips.mean()),
        })
    pd.DataFrame(flip2_rows).to_csv(
        OUT_DIR / "sign_flip_prod_vs_cleanup_v3p2.csv", index=False,
    )
    LOG.info("Wrote sign_flip_prod_vs_cleanup_v3p2.csv (%d rows)", len(flip2_rows))

    wipe = grp.agg(
        mean_frac_wiped_y=("frac_wiped_y", "mean"),
        mean_frac_wiped_iso=("frac_wiped_iso", "mean"),
        mean_frac_wiped_fo=("frac_wiped_fo", "mean"),
        mean_frac_any_wiped=("frac_any_wiped", "mean"),
    ).reset_index()
    wipe.to_csv(OUT_DIR / "wipe_prevalence_v3p2.csv", index=False)
    LOG.info("Wrote wipe_prevalence_v3p2.csv (%d rows)", len(wipe))


def _emit_histograms(df: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    phenotypes = ["mild", "moderate", "moderate-severe", "severe"]
    epochs = ["pre", "acute", "sub_acute", "chronic"]
    cells = [(p, e) for p in phenotypes for e in epochs]

    # Cohort mean peak_abs prod vs clean.
    prods, cleans, labels = [], [], []
    for p, e in cells:
        sub = df[(df["phenotype"] == p) & (df["epoch_label"] == e)]
        if sub.empty:
            continue
        labels.append(f"{p[:6]}/{e[:5]}")
        prods.append(float(sub["peak_abs_prod"].mean()))
        cleans.append(float(np.nanmean(sub["peak_abs_clean"].values)))
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(14, 5))
    w = 0.4
    ax.bar(x - w/2, prods, w, color="C0", label="prod (v5p3)")
    ax.bar(x + w/2, cleans, w, color="C4",
           label=f"clean v3 (pre-Stage-4: Ycap={Y_CEILING_PX:.0f}, iso<={ISOLATED_MAX_N}+r={ISOLATED_RADIUS_MS:.0f}ms, frame_jump={FRAME_JUMP_THR_PX:.0f})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("cohort mean |peak deflection| (px)")
    ax.set_title(
        "Cohort mean |jaw peak deflection| — production vs cleanup v3p2 (pre-Stage-4)"
    )
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cohort_mean_delta_bar_v3p2.png", dpi=110)
    plt.close(fig)
    LOG.info("Wrote cohort_mean_delta_bar_v3p2.png")

    # pass_qc rate.
    prods_q, cleans_q, labels_q = [], [], []
    for p, e in cells:
        sub = df[(df["phenotype"] == p) & (df["epoch_label"] == e)]
        if sub.empty:
            continue
        labels_q.append(f"{p[:6]}/{e[:5]}")
        prods_q.append(float(sub["pass_qc_prod"].mean()))
        cleans_q.append(float(sub["pass_qc_clean"].mean()))
    x = np.arange(len(labels_q))
    fig, ax = plt.subplots(figsize=(14, 5))
    w = 0.4
    ax.bar(x - w/2, prods_q, w, color="C0", label="prod jaw_pass_qc rate")
    ax.bar(x + w/2, cleans_q, w, color="C2", label="clean v3 jaw_pass_qc rate")
    ax.set_xticks(x)
    ax.set_xticklabels(labels_q, rotation=45, ha="right")
    ax.set_ylabel("jaw_pass_qc rate (frac of trials)")
    ax.set_title(
        "jaw_pass_qc cohort rate — prod vs cleanup v3p2 (pre-Stage-4)"
    )
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "pass_qc_rate_prod_vs_clean_v3p2.png", dpi=110)
    plt.close(fig)
    LOG.info("Wrote pass_qc_rate_prod_vs_clean_v3p2.png")

    # lk_at_peak under cleanup.
    fig, axes = plt.subplots(
        len(phenotypes), len(epochs),
        figsize=(4 * len(epochs), 3 * len(phenotypes)),
        sharex=True, sharey=False,
    )
    for i, ph in enumerate(phenotypes):
        for j, ep in enumerate(epochs):
            ax = axes[i, j]
            sub = df[(df["phenotype"] == ph) & (df["epoch_label"] == ep)]
            sub = sub[np.isfinite(sub["peak_lk_clean"])]
            if sub.empty:
                ax.set_title(f"{ph} / {ep}\n(no data)", fontsize=9)
                ax.axis("off")
                continue
            ax.hist(
                sub["peak_lk_clean"].values,
                bins=np.linspace(0, 1, 41), color="C4", edgecolor="none",
            )
            ax.axvline(0.5, color="grey", linestyle="--", linewidth=0.6)
            ax.axvline(0.85, color="red", linestyle="--", linewidth=0.6)
            med = float(np.nanmedian(sub["peak_lk_clean"]))
            ax.set_title(
                f"{ph} / {ep}\nN={len(sub)} trials, median={med:.2f}",
                fontsize=9,
            )
            ax.set_xlim(0, 1)
    for ax in axes[-1, :]:
        ax.set_xlabel("likelihood at v3-CLEANED jaw peak frame")
    for ax in axes[:, 0]:
        ax.set_ylabel("count")
    fig.suptitle(
        f"Jaw lk@peak under cleanup v3p2 (pre-Stage-4; Y_ceil={Y_CEILING_PX:.0f}px)",
        fontsize=11,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_DIR / "lk_at_peak_hist_cleanup_v3p2.png", dpi=110)
    plt.close(fig)
    LOG.info("Wrote lk_at_peak_hist_cleanup_v3p2.png")


def _emit_visual_renders(df: pd.DataFrame, resolver: PathResolver) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chosen_path = (
        Path(__file__).parent / "visual_renders" / "chosen_trials.csv"
    )
    if not chosen_path.exists():
        LOG.warning("chosen_trials.csv missing; skipping v3 renders")
        return
    chosen = pd.read_csv(chosen_path)
    RENDER_LO_MS, RENDER_HI_MS = -500.0, 5500.0

    for _, row in chosen.iterrows():
        animal = str(row["animal"])
        date_iso = str(row["date"])
        from datetime import date as Date
        date = Date.fromisoformat(date_iso)
        trial_index = int(row["trial_index"])
        side = str(row["side"])

        match = df[
            (df["animal"] == animal)
            & (df["date"] == date_iso)
            & (df["trial_index"] == trial_index)
            & (df["side"] == side)
        ]
        if match.empty:
            continue
        r = match.iloc[0]

        jaw_path = resolver.interpolated_trace("jaw", animal, date)
        df_full = pd.read_parquet(
            jaw_path,
            columns=[
                "y_final", "likelihood_raw", "is_interp_fill",
                "is_baseline_fill", "fill_method",
            ],
        )
        meta = pq.read_schema(jaw_path).metadata or {}
        fps = float(meta[b"fps"].decode())
        n_frames = int(meta[b"n_frames"].decode())

        y = df_full["y_final"].to_numpy()
        lk = df_full["likelihood_raw"].to_numpy()
        fm = df_full["fill_method"].to_numpy()

        baseline_mean = float(r["baseline_mean"])
        y_clean_full, w_y, w_iso, w_fo = compute_v3_clean_trace(
            y, fm, baseline_mean, fps,
        )

        tone_fi = int(r["tone_frame_idx"])
        lo = max(tone_fi + _ms_to_frames(RENDER_LO_MS, fps), 0)
        hi = min(tone_fi + _ms_to_frames(RENDER_HI_MS, fps) + 1, n_frames)
        t_ms = (np.arange(lo, hi) - tone_fi) * (1000.0 / fps)
        y_w = y[lo:hi]
        y_c = y_clean_full[lo:hi]
        lk_w = lk[lo:hi]
        fm_w = fm[lo:hi]
        wy_w = w_y[lo:hi]
        wi_w = w_iso[lo:hi]
        wf_w = w_fo[lo:hi]
        is_raw = (fm_w == 0)
        is_intp_prod = (fm_w == 1) | (fm_w == 2)
        is_base_prod = (fm_w == 3)

        fig, (ax, ax_lk) = plt.subplots(
            2, 1, figsize=(13, 6.5), sharex=True,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
        )

        if np.isfinite(baseline_mean):
            ax.axhline(baseline_mean, color="black", linestyle=":",
                       linewidth=0.5,
                       label=f"baseline_mean={baseline_mean:.2f}")
            ax.axhline(baseline_mean + Y_CEILING_PX, color="purple",
                       linestyle="--", linewidth=0.7,
                       label=f"Y_ceiling = baseline + {Y_CEILING_PX:.0f}px")

        ax.plot(t_ms, y_w, color="C0", linewidth=0.6, alpha=0.4,
                label="v5p3 y_final (prod)", zorder=1)
        ax.plot(t_ms, y_c, color="purple", linewidth=1.0,
                label="y_final after cleanup v3p2 (re-interpolated)", zorder=2)

        if is_intp_prod.any():
            ax.scatter(t_ms[is_intp_prod], y_w[is_intp_prod],
                       s=4, color="grey", alpha=0.5,
                       label=f"v5p3 PCHIP/linear (n={int(is_intp_prod.sum())})",
                       zorder=2)
        if is_base_prod.any():
            ax.scatter(t_ms[is_base_prod], y_w[is_base_prod],
                       s=6, color="red", marker="x", alpha=0.5,
                       label=f"v5p3 baseline-fill (n={int(is_base_prod.sum())})",
                       zorder=3)
        if is_raw.any():
            kept_raw = is_raw & ~wy_w & ~wi_w & ~wf_w
            wiped_y_only = is_raw & wy_w & ~wi_w & ~wf_w
            wiped_iso_only = is_raw & wi_w
            wiped_fo_only = is_raw & wf_w & ~wi_w
            if kept_raw.any():
                ax.scatter(t_ms[kept_raw], y_w[kept_raw],
                           s=8, color="black", alpha=0.7,
                           label=f"raw DLC kept (n={int(kept_raw.sum())})", zorder=4)
            if wiped_y_only.any():
                ax.scatter(t_ms[wiped_y_only], y_w[wiped_y_only],
                           s=14, facecolors="none", edgecolors="purple",
                           linewidth=1.0,
                           label=f"R1 Y-ceiling wipe (n={int(wiped_y_only.sum())})",
                           zorder=5)
            if wiped_iso_only.any():
                ax.scatter(t_ms[wiped_iso_only], y_w[wiped_iso_only],
                           s=14, facecolors="none", edgecolors="orange",
                           linewidth=1.0,
                           label=f"R2 isolated-short (n={int(wiped_iso_only.sum())})",
                           zorder=5)
            if wiped_fo_only.any():
                ax.scatter(t_ms[wiped_fo_only], y_w[wiped_fo_only],
                           s=18, facecolors="none", edgecolors="red",
                           linewidth=1.2,
                           label=f"R3 frame-outlier (n={int(wiped_fo_only.sum())})",
                           zorder=6)

        peak_t_prod = float(r["peak_t_ms_prod"])
        peak_y_prod_disp = float(r["peak_y_prod"]) + baseline_mean
        peak_t_clean = float(r["peak_t_ms_clean"])
        peak_y_clean_disp = float(r["peak_y_clean"]) + baseline_mean
        peak_abs_prod = float(r["peak_abs_prod"])
        peak_abs_clean = float(r["peak_abs_clean"])
        peak_lk_prod = float(r["peak_lk_prod"])
        peak_lk_clean = float(r["peak_lk_clean"])
        pass_qc_prod = bool(r["pass_qc_prod"])
        pass_qc_clean = bool(r["pass_qc_clean"])

        if np.isfinite(peak_t_prod):
            ax.plot([peak_t_prod], [peak_y_prod_disp], marker="*",
                    color="darkorange", markersize=14, markeredgecolor="black",
                    label=(
                        f"prod peak: t={peak_t_prod:.0f}ms |defl|={peak_abs_prod:.1f}px "
                        f"lk={peak_lk_prod:.2f} qc={pass_qc_prod}"
                    ))
        if np.isfinite(peak_t_clean):
            ax.plot([peak_t_clean], [peak_y_clean_disp], marker="P",
                    color="purple", markersize=14, markeredgecolor="black",
                    label=(
                        f"clean v3 peak: t={peak_t_clean:.0f}ms |defl|={peak_abs_clean:.1f}px "
                        f"lk={peak_lk_clean:.2f} qc={pass_qc_clean}"
                    ))

        ax.axvline(0, color="green", linestyle="-", linewidth=0.6, alpha=0.5)
        ax.set_ylabel("jaw y_final (centered, px)")
        ax.set_title(
            f"{animal} / {date_iso} / trial {trial_index} / side {side} | "
            f"prod |defl|={peak_abs_prod:.1f} (qc={pass_qc_prod}) → "
            f"clean v3 |defl|={peak_abs_clean:.1f} (qc={pass_qc_clean}) "
            f"Δ={peak_abs_clean - peak_abs_prod:+.1f}px",
            fontsize=10,
        )
        ax.legend(fontsize=7, loc="upper right", framealpha=0.85)
        ax.grid(alpha=0.2)

        ax_lk.plot(t_ms, lk_w, color="purple", linewidth=0.7)
        ax_lk.axhline(0.5, color="grey", linestyle="--", linewidth=0.5)
        ax_lk.axhline(0.85, color="red", linestyle="--", linewidth=0.5)
        ax_lk.axvline(0, color="green", linestyle="-", linewidth=0.6, alpha=0.5)
        ax_lk.set_ylim(-0.05, 1.05)
        ax_lk.set_ylabel("lk_raw")
        ax_lk.set_xlabel("t (ms) relative to tone onset")
        ax_lk.grid(alpha=0.2)
        ax_lk.set_xlim(RENDER_LO_MS, RENDER_HI_MS)

        out = RENDER_DIR / (
            f"jaw_{animal}_{date_iso.replace('-', '')}_t{trial_index:03d}_{side}_cleanup_v3p2.png"
        )
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        LOG.info("  wrote %s", out.name)


if __name__ == "__main__":
    main()
