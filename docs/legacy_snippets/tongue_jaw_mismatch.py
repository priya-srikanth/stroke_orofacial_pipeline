r"""Vendored from
//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Cells 51, 52, 53, 54, 55.

Captured for Phase 7a.5 — 2026-04-30 from the MICROSCOPE share at
\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\.

3-tier-rule disambiguation: same canonical notebook 7a.2 vendored Cell 23
and 7a.3 V3 vendored Cells 33/36/39/42/50 from. The mismatch section
(cells 51-55) is OUTSIDE the 7a.3 V3 vendor scope; this file fills that
gap. No sibling notebooks contain alternative implementations of the
tongue-jaw mismatch classifier or its plot families.

Source SHA256: ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643
Source size: 403,798,697 B
Cells included:
  - Cell 51 (1 lines, markdown, sha256 d2d006083e1cd8f2...): ## Tongue-jaw mismatch trials
  - Cell 52 (1 lines, markdown, sha256 48a5cc3f8f58a4e1...): ### Classify trials with few/no tongue licks but with jaw Y movement
  - Cell 53 (605 lines, code    , sha256 5ed7b814cf2b5a53...): # ===== Candidate trial classifier: few/no tongue licks + jaw movement =====
  - Cell 54 (1 lines, markdown, sha256 336bf22841d8f5ec...): ### Plot candidate trials
  - Cell 55 (1295 lines, code    , sha256 98c8cb1b0e46cc24...): # ===== Multi-mouse trial viewer + within-session grids + cross-session overlays =====

Cells excluded (and why):
  - The `_sessionBaseline_` predecessor variant of Cell 53 (visible only
    via the older `PS46_*_sessionBaseline_v5p3.csv` saved output, mtime
    2026-04-16, 32-col schema): Deprecated. Used per-session baselines;
    superseded by the per-trial baseline cell that emits the canonical
    37-col `_v5p3.csv` (mtime 2026-04-17). The `_sessionBaseline_` cell
    is no longer present in the canonical notebook.
  - Plot-only sanity / scratch cells outside the `## Tongue-jaw mismatch
    trials` section (cells <51 or >55): Out of scope; covered by 7a.2 /
    7a.3 V3 / 7a.4 vendor scopes or by `# Statistics` (cell 56+, future
    phase).

DO NOT edit, reformat, or lint this file. # ruff: noqa, # fmt: off
preserve byte-identity with capture time.
"""
# ruff: noqa
# fmt: off

# %% Cell 51 (type=markdown, lines=1, sha256=d2d006083e1cd8f2ab3b322f49c7bc2df80ff9c423414ba756a1344750f4ada4)
## Tongue-jaw mismatch trials

# %% Cell 52 (type=markdown, lines=1, sha256=48a5cc3f8f58a4e11ef9cbcd717b4b50fb539a1f0d8e0f309c043361654f1162)
### Classify trials with few/no tongue licks but with jaw Y movement

# %% Cell 53 (type=code, lines=605, sha256=5ed7b814cf2b5a53a5f7127a0e0818410b7be352a301edbf649f5999770a6010)
# ===== Candidate trial classifier: few/no tongue licks + jaw movement =====
# Uses:
#   - tongue final interpolated data for lick detection
#   - jaw final interpolated data for jaw-movement quantification
# Output:
#   - df_trials_candidates: one row per reward trial with classification metrics
#
# Candidate rule:
#   (A) n tongue licks in lick_count_win_ms <= max_licks_for_quiet
#   (B) jaw deflection relative to baseline exceeds threshold according to jaw_direction_mode:
#         - "above"          : jaw_defl > + jaw_thresh_sd * baseline_sd AND jaw_defl >= jaw_min_abs_px
#         - "above_or_below" : abs(jaw_defl) > jaw_thresh_sd * baseline_sd AND abs(jaw_defl) >= jaw_min_abs_px
#   (C) QC: at least jaw_min_frames_over suprathreshold frames in any jaw_frame_window
#
# NEW:
#   - universal editable defaults for lick/jaw criteria
#   - each mouse inherits defaults unless explicitly overridden in MOUSE_SPECS
#   - jaw_direction_mode toggle
#   - minimum absolute jaw deflection threshold (jaw_min_abs_px)

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== USER KNOBS =====================
CAM = "cam2"
INTERP_VERSION = "v5p3"

TONGUE_CENTER_MODE = "centered_spout_midpoint"
JAW_CENTER_MODE    = "centered_eye_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- UNIVERSAL DEFAULT CLASSIFIER PARAMETERS ----
DEFAULT_LICK_COUNT_WIN_MS   = (70, 5000)
DEFAULT_MAX_LICKS_FOR_QUIET = 0

DEFAULT_JAW_BASELINE_WIN_MS = (-500, 0)
DEFAULT_JAW_TEST_WIN_MS     = (0, 5000)
DEFAULT_JAW_THRESH_SD       = 4.0
DEFAULT_JAW_MIN_ABS_PX      = 4.0   # NEW
DEFAULT_JAW_MIN_FRAMES_OVER = 5
DEFAULT_JAW_FRAME_WINDOW    = 8

#   "above"          -> only positive jaw deflections count
#   "above_or_below" -> positive or negative jaw deflections count
DEFAULT_JAW_DIRECTION_MODE  = "above_or_below"

# ---- per-animal config ----
# Dates/d0 live here.
# Any mouse can optionally override one or more of the universal defaults above by adding keys like:
#   lick_count_win_ms=...
#   max_licks_for_quiet=...
#   jaw_baseline_win_ms=...
#   jaw_test_win_ms=...
#   jaw_thresh_sd=...
#   jaw_min_abs_px=...
#   jaw_min_frames_over=...
#   jaw_frame_window=...
#   jaw_direction_mode=...
MOUSE_SPECS = {
    "PS46": dict(
        date_start="20250307", date_end="20250406", d0="20250313",
        include_dates=None, exclude_dates=None,
    ),
    "PS47": dict(
        date_start="20250307", date_end="20250406", d0="20250313",
        include_dates=None, exclude_dates=None,
    ),
    "PS48": dict(
        date_start="20250307", date_end="20250406", d0="20250313",
        include_dates=None, exclude_dates=None,
    ),
    "PS49": dict(
        date_start="20250310", date_end="20250406", d0="20250317",
        include_dates=None, exclude_dates=None,
    ),
    "PS50": dict(
        date_start="20250319", date_end="20250406", d0="20250323",
        include_dates=None, exclude_dates=None,
    ),
    "PS51": dict(
        date_start="20250416", date_end="20250709", d0="20250429",
        include_dates=None, exclude_dates=None,
    ),
    "PS54": dict(
        date_start="20250416", date_end="20250709", d0="20250430",
        include_dates=None, exclude_dates=None,
    ),
    "PS55": dict(
        date_start="20250416", date_end="20250709", d0="20250430",
        include_dates=None, exclude_dates=None,
    ),
}

MICE_TO_RUN = None   # e.g. ["PS51"] ; None => all

USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"    # "pre", "post", "both", "all"
REL_DAY_RANGE = None

PLOT_SIDES = ("L", "R")

# ---- shared snippet window pulled around reward ----
# Keep this wide enough to contain baseline/test/count windows.
SNIPPET_WIN_MS = (-1500.0, 5500.0)

# ---- tongue lick detector settings (match your other cells) ----
DO_SMOOTH_Y = False
SMOOTH_MS = 12.0
RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0
MIN_PEAK_Y_ABS = 20.0
PEAK_PAD_MS = 52.0
STRICT_NO_FALLBACK = True
FAIL_FALLBACK = "max_abs"

SAVE_TABLES = True
TABLE_DIRNAME = "jaw_tongue_candidate_trials"
# ======================================================


# ---------- helpers ----------
def yyyymmdd_to_date(s):
    return datetime.strptime(s, "%Y%m%d").date()

def daterange_yyyymmdd(start_s, end_s):
    d0 = yyyymmdd_to_date(start_s)
    d1 = yyyymmdd_to_date(end_s)
    if d1 < d0:
        raise ValueError("date_end must be >= date_start")
    out = []
    d = d0
    while d <= d1:
        out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out

def keep_by_prepost(date_str, stroke_dt):
    if (PREPOST_MODE == "all") or (stroke_dt is None):
        return True
    d = yyyymmdd_to_date(date_str)
    rel = (d - stroke_dt).days
    if PREPOST_MODE == "pre":
        return rel <= 0
    if PREPOST_MODE == "post":
        return rel >= 1
    if PREPOST_MODE == "both":
        return True
    raise ValueError("PREPOST_MODE must be one of: 'pre','post','both','all'")

def _ms_to_frames(ms, fps):
    return int(np.round((ms / 1000.0) * fps))

def _moving_average_nan(y, w):
    y = np.asarray(y, float)
    n = len(y)
    if w <= 1:
        return y.copy()
    finite = np.isfinite(y)
    y0 = np.where(finite, y, 0.0)
    kernel = np.ones(int(w), dtype=float)
    num = np.convolve(y0, kernel, mode="same")
    den = np.convolve(finite.astype(float), kernel, mode="same")
    out = np.full(n, np.nan, float)
    good = den > 0
    out[good] = num[good] / den[good]
    return out

def _first_run_from(mask, min_len, start=0):
    mask = np.asarray(mask, bool)
    n = len(mask)
    i = int(max(0, start))
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        if (j - i) >= int(min_len):
            return i, j
        i = j
    return None, None

def _snippet(arr, center_fr, pre_f, post_f):
    T = pre_f + post_f + 1
    lo = center_fr - pre_f
    hi = center_fr + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, len(arr) - 1)
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo:dst_hi+1] = arr[src_lo:src_hi+1]
    return out

def _window_mask(t_ms, win_ms):
    lo, hi = map(float, win_ms)
    t = np.asarray(t_ms, float)
    return np.isfinite(t) & (t >= lo) & (t <= hi)

def _count_true_runs_in_window(mask_bool, min_true=3, run_window=6):
    """Return True if any length-run_window segment contains >= min_true True values."""
    x = np.asarray(mask_bool, bool).astype(int)
    if x.size == 0:
        return False
    W = int(max(1, run_window))
    K = int(max(1, min_true))
    if x.size < W:
        return int(np.sum(x)) >= K
    kernel = np.ones(W, dtype=int)
    counts = np.convolve(x, kernel, mode="valid")
    return bool(np.any(counts >= K))

def list_session_npzs_v5_only(mouse, cam, modality, center_mode):
    # modality: "tongue" or "jaw"
    sess_dir = (
        OUT_ROOT
        / mouse
        / f"{mouse}_{modality}_kinematics"
        / "processed_interpolated_data"
        / f"{center_mode}"
    )
    if not sess_dir.exists():
        raise FileNotFoundError(f"Missing processed_interpolated_data folder:\n  {sess_dir}")

    pat = re.compile(
        rf"^{re.escape(mouse)}_(?P<date>\d{{8}})_{re.escape(cam)}_{re.escape(modality)}_interp_{INTERP_VERSION}\.npz$"
    )

    available = {}
    for p in sorted(sess_dir.glob(f"{mouse}_*_{cam}_{modality}_interp_{INTERP_VERSION}.npz")):
        m = pat.match(p.name)
        if m:
            available[m.group("date")] = p
    return available, sess_dir

# ---------- tongue lick detector ----------
def _detect_up_to_n_tongue_licks_dydt(xw, yw, fps, detect_win_ms, t_ms, max_licks=20):
    lo_ms, hi_ms = detect_win_ms
    i0 = int(np.searchsorted(t_ms, lo_ms, side="left"))
    i1 = int(np.searchsorted(t_ms, hi_ms, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms)-1))
    i1 = max(0, min(i1, len(t_ms)-1))
    if i1 < i0:
        i0, i1 = i1, i0

    xseg0 = np.asarray(xw[i0:i1+1], float)
    yseg0 = np.asarray(yw[i0:i1+1], float)
    if not np.any(np.isfinite(yseg0)):
        return []

    ys = yseg0.copy()
    if DO_SMOOTH_Y and (SMOOTH_MS is not None) and (SMOOTH_MS > 0):
        w = max(1, _ms_to_frames(SMOOTH_MS, fps))
        if w >= 3:
            ys = _moving_average_nan(ys, w)

    dt_s = 1.0 / fps
    dy = np.gradient(ys) / dt_s

    finite = np.isfinite(ys) & np.isfinite(dy) & np.isfinite(xseg0)
    rise_mask = finite & (dy > +SLOPE_THR_PX_PER_S)
    fall_mask = finite & (dy < -SLOPE_THR_PX_PER_S)

    rise_min_f = max(1, _ms_to_frames(RISE_MIN_MS, fps))
    fall_min_f = max(1, _ms_to_frames(FALL_MIN_MS, fps))
    pad_f      = max(0, _ms_to_frames(PEAK_PAD_MS, fps))

    L = len(yseg0)
    peaks = []
    start = 0

    for _ in range(int(max_licks)):
        r0, r1 = _first_run_from(rise_mask, rise_min_f, start=start)
        if r0 is None:
            break

        k = r1
        while k < L and (not np.isfinite(dy[k]) or dy[k] > 0):
            k += 1
        if k >= L:
            break

        seg_lo = r0
        seg_hi = min(L - 1, k + pad_f)
        seg = yseg0[seg_lo:seg_hi+1]
        if not np.any(np.isfinite(seg)):
            start = seg_hi + 1
            if start >= L:
                break
            continue

        j_local = int(np.nanargmax(seg))
        j_peak = seg_lo + j_local

        end_idx = j_peak
        if fall_min_f > 1:
            f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
            if f0 is not None:
                end_idx = max(end_idx, f1 - 1)

        ypk = float(yseg0[j_peak])
        if (MIN_PEAK_Y_ABS is not None) and (abs(ypk) >= MIN_PEAK_Y_ABS):
            i_peak = i0 + j_peak
            peaks.append(dict(
                i_peak=int(i_peak),
                t_peak_ms=float(t_ms[i_peak]),
                y_peak=float(yw[i_peak]),
                x_peak=float(xw[i_peak]),
            ))

        start = int(end_idx + 1)
        if start >= L:
            break

    return peaks


# ===================== RUN =====================
mice = list(MOUSE_SPECS.keys()) if (MICE_TO_RUN is None) else list(MICE_TO_RUN)

trial_rows = []

for mouse in mice:
    if mouse not in MOUSE_SPECS:
        print(f"[skip] {mouse} not in MOUSE_SPECS")
        continue

    spec = dict(MOUSE_SPECS[mouse])
    date_start = spec["date_start"]
    date_end   = spec["date_end"]
    include_dates = set(spec.get("include_dates") or [])
    exclude_dates = set(spec.get("exclude_dates") or [])
    d0 = spec.get("d0", None)

    # ---- resolve per-mouse parameters from universal defaults + optional overrides ----
    lick_count_win_ms   = tuple(spec.get("lick_count_win_ms", DEFAULT_LICK_COUNT_WIN_MS))
    max_licks_for_quiet = int(spec.get("max_licks_for_quiet", DEFAULT_MAX_LICKS_FOR_QUIET))

    jaw_baseline_win_ms = tuple(spec.get("jaw_baseline_win_ms", DEFAULT_JAW_BASELINE_WIN_MS))
    jaw_test_win_ms     = tuple(spec.get("jaw_test_win_ms", DEFAULT_JAW_TEST_WIN_MS))
    jaw_thresh_sd       = float(spec.get("jaw_thresh_sd", DEFAULT_JAW_THRESH_SD))
    jaw_min_abs_px      = float(spec.get("jaw_min_abs_px", DEFAULT_JAW_MIN_ABS_PX))   # NEW
    jaw_min_frames_over = int(spec.get("jaw_min_frames_over", DEFAULT_JAW_MIN_FRAMES_OVER))
    jaw_frame_window    = int(spec.get("jaw_frame_window", DEFAULT_JAW_FRAME_WINDOW))
    jaw_direction_mode  = str(spec.get("jaw_direction_mode", DEFAULT_JAW_DIRECTION_MODE))

    if jaw_direction_mode not in ("above", "above_or_below"):
        raise ValueError(f"{mouse}: jaw_direction_mode must be 'above' or 'above_or_below', got {jaw_direction_mode!r}")

    tong_avail, tong_dir = list_session_npzs_v5_only(mouse, CAM, "tongue", TONGUE_CENTER_MODE)
    jaw_avail, jaw_dir   = list_session_npzs_v5_only(mouse, CAM, "jaw",   JAW_CENTER_MODE)

    common_dates = sorted(set(tong_avail.keys()) & set(jaw_avail.keys()))

    if include_dates:
        dates = [d for d in common_dates if d in include_dates]
    else:
        dates = [d for d in common_dates if (date_start <= d <= date_end)]
    dates = [d for d in dates if d not in exclude_dates]

    if not dates:
        print(f"[warn] {mouse}: no common tongue+jaw sessions.")
        continue

    stroke_dt = yyyymmdd_to_date(d0) if (USE_STROKE_ALIGNMENT and d0) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        print(f"[warn] {mouse}: no sessions after filtering.")
        continue

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    print(f"\n[info] ===== {mouse} =====")
    print(f"[info] sessions: {dates}")
    print(f"[info] quiet tongue: <= {max_licks_for_quiet} licks in {lick_count_win_ms} ms")
    print(f"[info] jaw movement: baseline={jaw_baseline_win_ms} ms | test={jaw_test_win_ms} ms | thresh={jaw_thresh_sd} SD AND >= {jaw_min_abs_px} px | mode={jaw_direction_mode} | QC={jaw_min_frames_over} in {jaw_frame_window}")

    for d in dates:
        p_tong = tong_avail[d]
        p_jaw  = jaw_avail[d]

        Zt = np.load(p_tong, allow_pickle=True)
        Zj = np.load(p_jaw, allow_pickle=True)

        fps_t = float(Zt["fps"])
        fps_j = float(Zj["fps"])
        if abs(fps_t - fps_j) > 1e-6:
            raise ValueError(f"{mouse} {d}: tongue/jaw fps mismatch ({fps_t} vs {fps_j})")

        fps = fps_t
        n_frames_t = int(Zt["n_frames"])
        n_frames_j = int(Zj["n_frames"])

        # final interpolated traces
        tongue_x = Zt["x_final"].astype(float)
        tongue_y = Zt["y_final"].astype(float)
        jaw_y    = Zj["y_final"].astype(float)

        pre_f  = abs(_ms_to_frames(SNIPPET_WIN_MS[0], fps))
        post_f = abs(_ms_to_frames(SNIPPET_WIN_MS[1], fps))
        t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))

        rel_day = np.nan
        if stroke_dt is not None:
            rel_day = (yyyymmdd_to_date(d) - stroke_dt).days

        centers_by_side = {}
        if "L" in PLOT_SIDES:
            cL_t = Zt["fr_reward_mouseL"].astype(int)
            cL_j = Zj["fr_reward_mouseL"].astype(int)
            nL = min(len(cL_t), len(cL_j))
            centers_by_side["L"] = (cL_t[:nL], cL_j[:nL])
        if "R" in PLOT_SIDES:
            cR_t = Zt["fr_reward_mouseR"].astype(int)
            cR_j = Zj["fr_reward_mouseR"].astype(int)
            nR = min(len(cR_t), len(cR_j))
            centers_by_side["R"] = (cR_t[:nR], cR_j[:nR])

        for side, (centers_t, centers_j) in centers_by_side.items():
            for k, (ct, cj) in enumerate(zip(centers_t, centers_j)):
                ct = int(ct)
                cj = int(cj)

                if not (0 <= ct < n_frames_t and 0 <= cj < n_frames_j):
                    continue

                tongue_yw = _snippet(tongue_y, ct, pre_f, post_f)
                tongue_xw = _snippet(tongue_x, ct, pre_f, post_f)
                jaw_yw    = _snippet(jaw_y,    cj, pre_f, post_f)

                # tongue lick peaks
                peaks = _detect_up_to_n_tongue_licks_dydt(
                    tongue_xw, tongue_yw, fps, lick_count_win_ms, t_ms, max_licks=30
                )
                lick_peak_times_ms = [float(p["t_peak_ms"]) for p in peaks]
                n_licks_in_window = int(len(peaks))
                quiet_tongue_pass = bool(n_licks_in_window <= max_licks_for_quiet)

                # jaw baseline
                base_mask = _window_mask(t_ms, jaw_baseline_win_ms)
                jaw_base = np.asarray(jaw_yw, float)[base_mask]
                jaw_base = jaw_base[np.isfinite(jaw_base)]

                if jaw_base.size >= 2:
                    jaw_baseline_mean = float(np.nanmean(jaw_base))
                    jaw_baseline_sd   = float(np.nanstd(jaw_base))
                else:
                    jaw_baseline_mean = np.nan
                    jaw_baseline_sd   = np.nan

                # jaw test window
                test_mask = _window_mask(t_ms, jaw_test_win_ms)
                jaw_test = np.asarray(jaw_yw, float)
                jaw_defl = jaw_test - jaw_baseline_mean if np.isfinite(jaw_baseline_mean) else np.full_like(jaw_test, np.nan)

                jaw_peak_pos_deflection = np.nan
                jaw_peak_neg_deflection = np.nan
                jaw_peak_abs_deflection = np.nan
                jaw_peak_selected_deflection = np.nan

                if np.any(np.isfinite(jaw_defl[test_mask])):
                    jaw_test_vals = np.asarray(jaw_defl[test_mask], float)
                    jaw_test_vals = jaw_test_vals[np.isfinite(jaw_test_vals)]

                    if jaw_test_vals.size > 0:
                        jaw_peak_pos_deflection = float(np.nanmax(jaw_test_vals))
                        jaw_peak_neg_deflection = float(np.nanmin(jaw_test_vals))
                        jaw_peak_abs_deflection = float(np.nanmax(np.abs(jaw_test_vals)))

                        if jaw_direction_mode == "above":
                            jaw_peak_selected_deflection = float(jaw_peak_pos_deflection)
                        else:
                            idx_sel = int(np.nanargmax(np.abs(jaw_test_vals)))
                            jaw_peak_selected_deflection = float(jaw_test_vals[idx_sel])

                if np.isfinite(jaw_baseline_sd) and (jaw_baseline_sd > 0):
                    jaw_thresh_sd_abs = jaw_thresh_sd * jaw_baseline_sd

                    if jaw_direction_mode == "above":
                        supra = (
                            np.isfinite(jaw_defl) & test_mask &
                            (jaw_defl > jaw_thresh_sd_abs) &
                            (jaw_defl >= jaw_min_abs_px)
                        )
                    elif jaw_direction_mode == "above_or_below":
                        supra = (
                            np.isfinite(jaw_defl) & test_mask &
                            (np.abs(jaw_defl) > jaw_thresh_sd_abs) &
                            (np.abs(jaw_defl) >= jaw_min_abs_px)
                        )
                    else:
                        raise ValueError(f"Unexpected jaw_direction_mode: {jaw_direction_mode}")

                    jaw_thresh_px_used = float(max(jaw_thresh_sd_abs, jaw_min_abs_px))
                    jaw_n_frames_over_thresh = int(np.sum(supra))
                    jaw_pass_qc = _count_true_runs_in_window(
                        supra[test_mask],
                        min_true=jaw_min_frames_over,
                        run_window=jaw_frame_window
                    )
                else:
                    jaw_thresh_sd_abs = np.nan
                    jaw_thresh_px_used = np.nan
                    jaw_n_frames_over_thresh = 0
                    jaw_pass_qc = False

                candidate_no_lick_with_jaw_move = bool(quiet_tongue_pass and jaw_pass_qc)

                trial_rows.append(dict(
                    mouse=mouse,
                    date=d,
                    date_dt=yyyymmdd_to_date(d),
                    rel_day=rel_day,
                    side=side,
                    trial_index=int(k),
                    reward_center_fr_tongue=int(ct),
                    reward_center_fr_jaw=int(cj),
                    fps=float(fps),

                    lick_count_win_ms_lo=float(lick_count_win_ms[0]),
                    lick_count_win_ms_hi=float(lick_count_win_ms[1]),
                    max_licks_for_quiet=int(max_licks_for_quiet),
                    n_licks_in_window=int(n_licks_in_window),
                    tongue_peak_times_ms=";".join([f"{v:.3f}" for v in lick_peak_times_ms]),
                    quiet_tongue_pass=bool(quiet_tongue_pass),

                    jaw_baseline_win_ms_lo=float(jaw_baseline_win_ms[0]),
                    jaw_baseline_win_ms_hi=float(jaw_baseline_win_ms[1]),
                    jaw_test_win_ms_lo=float(jaw_test_win_ms[0]),
                    jaw_test_win_ms_hi=float(jaw_test_win_ms[1]),
                    jaw_baseline_mean=float(jaw_baseline_mean) if np.isfinite(jaw_baseline_mean) else np.nan,
                    jaw_baseline_sd=float(jaw_baseline_sd) if np.isfinite(jaw_baseline_sd) else np.nan,
                    jaw_thresh_sd=float(jaw_thresh_sd),
                    jaw_thresh_abs=float(jaw_thresh_sd_abs) if np.isfinite(jaw_thresh_sd_abs) else np.nan,
                    jaw_min_abs_px=float(jaw_min_abs_px),
                    jaw_thresh_px_used=float(jaw_thresh_px_used) if np.isfinite(jaw_thresh_px_used) else np.nan,
                    jaw_direction_mode=str(jaw_direction_mode),

                    jaw_peak_pos_deflection=float(jaw_peak_pos_deflection) if np.isfinite(jaw_peak_pos_deflection) else np.nan,
                    jaw_peak_neg_deflection=float(jaw_peak_neg_deflection) if np.isfinite(jaw_peak_neg_deflection) else np.nan,
                    jaw_peak_abs_deflection=float(jaw_peak_abs_deflection) if np.isfinite(jaw_peak_abs_deflection) else np.nan,
                    jaw_peak_selected_deflection=float(jaw_peak_selected_deflection) if np.isfinite(jaw_peak_selected_deflection) else np.nan,

                    jaw_n_frames_over_thresh=int(jaw_n_frames_over_thresh),
                    jaw_min_frames_over=int(jaw_min_frames_over),
                    jaw_frame_window=int(jaw_frame_window),
                    jaw_pass_qc=bool(jaw_pass_qc),

                    candidate_no_lick_with_jaw_move=bool(candidate_no_lick_with_jaw_move),

                    tongue_npz=str(p_tong),
                    jaw_npz=str(p_jaw),
                ))

df_trials_candidates = pd.DataFrame(trial_rows).sort_values(
    ["mouse", "date_dt", "side", "trial_index"]
).reset_index(drop=True)

print("\n[candidate summary]")
if len(df_trials_candidates) == 0:
    print("No trials found.")
else:
    print(
        df_trials_candidates.groupby("mouse")["candidate_no_lick_with_jaw_move"]
        .sum()
        .rename("n_candidates")
        .to_string()
    )

    print("\n[first rows]")
    show_cols = [
        "mouse","date","rel_day","side","trial_index",
        "n_licks_in_window","quiet_tongue_pass",
        "jaw_direction_mode","jaw_peak_pos_deflection","jaw_peak_neg_deflection",
        "jaw_peak_abs_deflection","jaw_baseline_sd","jaw_thresh_abs","jaw_min_abs_px",
        "jaw_n_frames_over_thresh","jaw_pass_qc","candidate_no_lick_with_jaw_move"
    ]
    print(df_trials_candidates[show_cols].head(20).to_string(index=False))

# save
if SAVE_TABLES and len(df_trials_candidates) > 0:
    for mouse in sorted(df_trials_candidates["mouse"].unique()):
        pdir = (
            OUT_ROOT / mouse / f"{mouse}_jaw_kinematics" / "kinematics_figures" /
            JAW_CENTER_MODE / TABLE_DIRNAME
        )
        pdir.mkdir(parents=True, exist_ok=True)
        out_csv = pdir / f"{mouse}_{CAM}_jawMove_noTongueLick_candidates_{INTERP_VERSION}.csv"
        df_trials_candidates[df_trials_candidates["mouse"] == mouse].to_csv(out_csv, index=False)
        print(f"[save] {out_csv}")

print("[ok] classification done")

# %% Cell 54 (type=markdown, lines=1, sha256=336bf22841d8f5ec69a35bb0e26a67e0d89b90bce96546f241167d5fa3ba9dc2)
### Plot candidate trials

# %% Cell 55 (type=code, lines=1295, sha256=98c8cb1b0e46cc24377898de96c1145e911db28266eb729a9a1c84edd3321c49)
# ===== Multi-mouse trial viewer + within-session grids + cross-session overlays =====
# Per eligible session:
#   1) individual-trial figure
#      - col 1 = candidate trials
#      - col 2 = non-candidate trials
#
#   2) within-session 4x2 overlay grid
#      - col 1 = L trials
#      - col 2 = R trials
#      - row 1 = overlay candidate trials
#      - row 2 = overlay non-candidate trials
#      - row 3 = mean ± SEM candidate trials
#      - row 4 = mean ± SEM non-candidate trials
#
# Per mouse:
#   3) cross-session 2x2 session-overlay grid
#      - col 1 = L
#      - col 2 = R
#      - row 1 = candidate
#      - row 2 = non-candidate
#      - each session mean ± SEM overlaid
#
#   4) cross-session 2x2 binned grid
#      - col 1 = L
#      - col 2 = R
#      - row 1 = candidate
#      - row 2 = non-candidate
#      - binned across sessions by relative day using bin_size_days
#
# Notes:
#   - jaw = solid line
#   - tongue = dotted line
#   - within-session colors: L = dodgerblue, R = mediumvioletred
#   - cross-session colors: pre-stroke = grey, post-stroke = plasma colormap
#   - day 0 is treated as pre-stroke
#   - denominator in session subtitles = total trials in that session/side subset
#   - candidate status comes from df_trials_candidates
#   - scale bars: jaw solid grey, tongue dotted grey
#   - jaw can be raw or baseline-subtracted
#   - individual rows are sorted independently within candidate and non-candidate groups

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import cm, colors as mcolors
from pathlib import Path
from datetime import datetime

# ===================== USER KNOBS =====================

MOUSE_SPECS = {
    "PS46": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None, bin_size_days=2),
    "PS47": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None, bin_size_days=2),
    "PS48": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None, bin_size_days=2),
    "PS49": dict(date_start="20250310", date_end="20250406", d0="20250317", include_dates=None, exclude_dates=None, bin_size_days=2),
    "PS50": dict(date_start="20250319", date_end="20250406", d0="20250323", include_dates=None, exclude_dates=None, bin_size_days=2),
    "PS51": dict(date_start="20250416", date_end="20250709", d0="20250429", include_dates=None, exclude_dates=None, bin_size_days=7),
    "PS54": dict(date_start="20250416", date_end="20250709", d0="20250430", include_dates=None, exclude_dates=None, bin_size_days=7),
    "PS55": dict(date_start="20250416", date_end="20250709", d0="20250430", include_dates=None, exclude_dates=None, bin_size_days=7),
}

MICE_TO_RUN = None          # e.g. ["PS51", "PS55"] or None for all
SIDE_FILTER = None          # None, "L", or "R"

# ---- within-session display/save toggles ----
DISPLAY_SESSION_INDIVIDUAL = False
SAVE_SESSION_INDIVIDUAL = True

DISPLAY_SESSION_GRID = False
SAVE_SESSION_GRID = True

# ---- cross-session display/save toggles ----
DISPLAY_CROSS_SESSION_OVERLAY = True
SAVE_CROSS_SESSION_OVERLAY = True

DISPLAY_CROSS_SESSION_BINNED = True
SAVE_CROSS_SESSION_BINNED = True

# ---- individual trial viewer ----
TOP_N_BY_JAW_DEFLECTION = None     # applied separately to candidate and non-candidate individual rows; None = all
SORT_DESCENDING_BY_JAW = True
# "jaw_pos", "jaw_abs", "jaw_selected"
SORT_METRIC = "jaw_abs"

# ---- within-session 4x2 grid toggles ----
SHOW_ROW_CANDIDATE_OVERLAY = True
SHOW_ROW_NONCANDIDATE_OVERLAY = True
SHOW_ROW_CANDIDATE_MEANSEM = True
SHOW_ROW_NONCANDIDATE_MEANSEM = True

# ---- plot window ----
VIEW_WIN_MS = (-500.0, 5000.0)

# ---- styling ----
FIG_DPI = 200
ROW_HEIGHT = 1.8
INDIVIDUAL_FIGSIZE = (18, 12)
SESSION_GRID_FIGSIZE = (14, 18)
CROSS_SESSION_GRID_FIGSIZE = (13, 8.5)

SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}

JAW_LW = 1.5
TONGUE_LW = 1.2
TONGUE_LS = ":"

REWARD_COLOR = "red"
PEAK_MARKER_SIZE = 4

# ---- jaw plotting mode ----
# "raw" or "baseline_subtracted"
JAW_ROWS_MODE = "baseline_subtracted"
JAW_OVERLAY_MODE = "baseline_subtracted"

SHOW_JAW_ZERO_LINE_WHEN_BASELINE_SUBTRACTED = True
JAW_ZERO_LINE_COLOR = "0.4"
JAW_ZERO_LINE_LS = "--"
JAW_ZERO_LINE_ALPHA = 0.7

# ---- axis-limit options ----
# "global" | "per_trial" | "percentile_cap"
JAW_YLIM_MODE = "percentile_cap"
TONGUE_YLIM_MODE = "percentile_cap"

JAW_YMAX_PERCENTILE = 99.9
TONGUE_YMAX_PERCENTILE = 99.9

JAW_YMIN_PERCENTILE = None
TONGUE_YMIN_PERCENTILE = None

YLIM_PAD_FRAC = 0.05

# ---- shared Y toggles for grids ----
SESSION_GRID_SHARED_Y = True
CROSS_SESSION_GRID_SHARED_Y = True

# ---- scale bars ----
SHOW_SCALE_BARS = True

AUTO_SCALEBARS = True
SCALEBAR_FRAC_OF_AXIS_HEIGHT = 0.25

JAW_SCALEBAR_PX = 20.0
TONGUE_SCALEBAR_PX = 20.0

SCALEBAR_COLOR = "0.5"
JAW_SCALEBAR_LS = "-"
TONGUE_SCALEBAR_LS = ":"
SCALEBAR_LW = 1.5

# ---- within-session overlay style ----
OVERLAY_JAW_ALPHA = 0.2
OVERLAY_TONGUE_ALPHA = 0.1
OVERLAY_SHOW_PEAKS = False

# ---- mean ± SEM settings ----
MEAN_JAW_LW = 2
MEAN_TONGUE_LW = 1.5
MEAN_JAW_ALPHA = 0.95
MEAN_TONGUE_ALPHA = 0.95
SEM_JAW_ALPHA = 0.10
SEM_TONGUE_ALPHA = 0.06

SHOW_FAINT_TRIALS_IN_MEAN_SEM_OVERLAY = True
FAINT_TRIAL_JAW_LW = 0.8
FAINT_TRIAL_TONGUE_LW = 0.7
FAINT_TRIAL_JAW_ALPHA = 0.08
FAINT_TRIAL_TONGUE_ALPHA = 0.04

# ---- cross-session style ----
CROSS_SESSION_LINE_LW = 0.8
CROSS_SESSION_LINE_ALPHA = 0.8          # NEW
CROSS_SESSION_FILL_ALPHA = 0.08

CROSS_SESSION_BIN_LINE_LW = 0.8
CROSS_SESSION_BIN_LINE_ALPHA = 0.8      # NEW
CROSS_SESSION_BIN_FILL_ALPHA = 0.08

POSTSTROKE_CMAP_NAME = "plasma"

# save root
OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")
JAW_CENTER_MODE = "centered_eye_midpoint"
SAVE_FOLDERNAME = "jaw_tongue_candidate_trials"

# ======================================================


# ---------- helpers ----------
def _yyyymmdd_to_date(s):
    return datetime.strptime(str(s), "%Y%m%d").date()

def _first_finite(*vals):
    for v in vals:
        try:
            fv = float(v)
            if np.isfinite(fv):
                return fv
        except Exception:
            pass
    return np.nan

def _jaw_title_metrics(meta):
    jaw_dir = str(meta.get("jaw_direction_mode", "NA"))

    jaw_pos = _first_finite(meta.get("jaw_peak_pos_deflection", np.nan))
    jaw_neg = _first_finite(meta.get("jaw_peak_neg_deflection", np.nan))
    jaw_abs = _first_finite(meta.get("jaw_peak_abs_deflection", np.nan))
    jaw_sel = _first_finite(meta.get("jaw_peak_selected_deflection", np.nan), jaw_pos)
    jaw_thr = _first_finite(meta.get("jaw_thresh_px_used", np.nan), meta.get("jaw_thresh_abs", np.nan))
    jaw_sd = _first_finite(meta.get("jaw_baseline_sd", np.nan))

    return dict(
        jaw_dir=jaw_dir,
        jaw_pos=jaw_pos,
        jaw_neg=jaw_neg,
        jaw_abs=jaw_abs,
        jaw_sel=jaw_sel,
        jaw_thr=jaw_thr,
        jaw_sd=jaw_sd,
    )

def _ms_to_frames(ms, fps):
    return int(np.round((ms / 1000.0) * fps))

def _snippet(arr, center_fr, pre_f, post_f):
    T = pre_f + post_f + 1
    lo = center_fr - pre_f
    hi = center_fr + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, len(arr) - 1)
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo:dst_hi+1] = arr[src_lo:src_hi+1]
    return out

def _parse_peak_times(s):
    if (s is None) or (not isinstance(s, str)) or (len(s.strip()) == 0):
        return np.array([], float)
    return np.array([float(x) for x in s.split(";") if len(x) > 0], float)

def _draw_capless_scalebar(ax, x, y0, dy, text, color="k", text_dx=0.0, linestyle="-", lw=1.5):
    ax.plot([x, x], [y0, y0 + dy], color=color, lw=lw, linestyle=linestyle, clip_on=False)
    ax.text(x + text_dx, y0 + 0.5 * dy, text, color=color, va="center", ha="left", fontsize=8)

def _safe_float(v, default=np.nan):
    try:
        return float(v)
    except Exception:
        return default

def _finite_vals(arr):
    x = np.asarray(arr, float)
    return x[np.isfinite(x)]

def _pad(lo, hi, frac=0.05):
    if (not np.isfinite(lo)) or (not np.isfinite(hi)):
        return lo, hi
    if hi == lo:
        return lo - 1.0, hi + 1.0
    d = (hi - lo) * frac
    return lo - d, hi + d

def _limits_from_values(vals, mode="global", ymax_percentile=99.0, ymin_percentile=None, pad_frac=0.05):
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return (np.nan, np.nan)

    if mode == "global":
        lo = float(np.nanmin(vals))
        hi = float(np.nanmax(vals))
    elif mode == "percentile_cap":
        if ymin_percentile is None:
            lo = float(np.nanmin(vals))
        else:
            lo = float(np.nanpercentile(vals, ymin_percentile))
        hi = float(np.nanpercentile(vals, ymax_percentile))
    elif mode == "per_trial":
        lo = float(np.nanmin(vals))
        hi = float(np.nanmax(vals))
    else:
        raise ValueError("mode must be 'global', 'per_trial', or 'percentile_cap'")

    return _pad(lo, hi, frac=pad_frac)

def _limits_from_rows(rows, key, mode="global", ymax_percentile=99.0, ymin_percentile=None, pad_frac=0.05):
    vals = []
    for row in rows:
        x = _finite_vals(row[key])
        if x.size:
            vals.append(x)
    if len(vals) == 0:
        return (np.nan, np.nan)
    allv = np.concatenate(vals)
    return _limits_from_values(
        allv,
        mode=mode,
        ymax_percentile=ymax_percentile,
        ymin_percentile=ymin_percentile,
        pad_frac=pad_frac
    )

def _limits_from_summary_items(items, mu_key, sem_key, mode="global", ymax_percentile=99.0, ymin_percentile=None, pad_frac=0.05):
    vals = []
    for it in items:
        mu = np.asarray(it[mu_key], float)
        sem = np.asarray(it[sem_key], float)
        if np.any(np.isfinite(mu)):
            vals.append(mu[np.isfinite(mu)])
        if np.any(np.isfinite(mu + sem)):
            vals.append((mu + sem)[np.isfinite(mu + sem)])
        if np.any(np.isfinite(mu - sem)):
            vals.append((mu - sem)[np.isfinite(mu - sem)])
    if len(vals) == 0:
        return (np.nan, np.nan)
    return _limits_from_values(
        np.concatenate(vals),
        mode=mode,
        ymax_percentile=ymax_percentile,
        ymin_percentile=ymin_percentile,
        pad_frac=pad_frac
    )

def _limits_for_single_trace(arr, pad_frac=0.05):
    vals = _finite_vals(arr)
    if vals.size == 0:
        return (np.nan, np.nan)
    return _limits_from_values(vals, mode="global", pad_frac=pad_frac)

def _get_baseline_mean(meta):
    if "jaw_baseline_mean" in meta.index:
        return _safe_float(meta["jaw_baseline_mean"])
    if "jaw_session_baseline_mean" in meta.index:
        return _safe_float(meta["jaw_session_baseline_mean"])
    return np.nan

def _jaw_trace_for_mode(jaw_y, meta, mode):
    jaw_y = np.asarray(jaw_y, float)
    if mode == "raw":
        return jaw_y
    elif mode == "baseline_subtracted":
        b = _get_baseline_mean(meta)
        if np.isfinite(b):
            return jaw_y - b
        return np.full_like(jaw_y, np.nan)
    else:
        raise ValueError("JAW mode must be 'raw' or 'baseline_subtracted'")

def _jaw_ylabel(mode):
    return "Jaw Y (px)" if mode == "raw" else "Jaw Y - baseline (px)"

def _jaw_mode_tag(mode):
    return "jawRaw" if mode == "raw" else "jawBaselineSub"

def _format_baseline_text(meta):
    if "jaw_baseline_mean" in meta.index:
        b = _safe_float(meta["jaw_baseline_mean"])
        return f"jaw_base={b:.2f}" if np.isfinite(b) else "jaw_base=nan"
    if "jaw_session_baseline_mean" in meta.index:
        b = _safe_float(meta["jaw_session_baseline_mean"])
        return f"jaw_session_base={b:.2f}" if np.isfinite(b) else "jaw_session_base=nan"
    return "jaw_base=NA"

def _auto_scalebar_px_from_ylim(ylim, frac=0.5, min_px=1):
    lo, hi = ylim
    if (not np.isfinite(lo)) or (not np.isfinite(hi)):
        return np.nan
    span = abs(float(hi) - float(lo))
    if span <= 0:
        return np.nan
    return max(int(min_px), int(np.round(float(frac) * span)))

def _choose_scalebar_px(ylim, auto=True, frac=0.5, fallback_px=20.0):
    if auto:
        v = _auto_scalebar_px_from_ylim(ylim, frac=frac, min_px=1)
        return float(v) if np.isfinite(v) else float(fallback_px)
    return float(fallback_px)

def _resolve_sort_series(df, sort_metric):
    if sort_metric == "jaw_pos":
        if "jaw_peak_pos_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_pos_deflection"], errors="coerce")
        raise KeyError("jaw_peak_pos_deflection not found")

    if sort_metric == "jaw_abs":
        if "jaw_peak_abs_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_abs_deflection"], errors="coerce")
        if "jaw_peak_selected_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_selected_deflection"], errors="coerce").abs()
        if "jaw_peak_pos_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_pos_deflection"], errors="coerce").abs()
        raise KeyError("No absolute-compatible jaw deflection column found")

    if sort_metric == "jaw_selected":
        if "jaw_peak_selected_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_selected_deflection"], errors="coerce")
        if "jaw_peak_pos_deflection" in df.columns:
            return pd.to_numeric(df["jaw_peak_pos_deflection"], errors="coerce")
        raise KeyError("No selected-compatible jaw deflection column found")

    raise ValueError("SORT_METRIC must be 'jaw_pos', 'jaw_abs', or 'jaw_selected'")

def _mean_sem_matrix(M):
    M = np.asarray(M, float)
    mu = np.nanmean(M, axis=0)
    n_eff = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0)
    sem = np.full(mu.shape, np.nan, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sem = sd / np.sqrt(np.maximum(1, n_eff))
    sem[n_eff < 2] = np.nan
    return mu, sem, n_eff

def _format_candidate_count_text(side, df_total, df_candidates):
    n_total = int(np.sum(df_total["side"].astype(str) == side))
    n_cand  = int(np.sum(df_candidates["side"].astype(str) == side))
    if n_total == 0:
        return ""
    return f"{side} candidate trials: {n_cand}/{n_total}"

def _format_noncandidate_count_text(side, df_total, df_candidates):
    n_total = int(np.sum(df_total["side"].astype(str) == side))
    n_cand  = int(np.sum(df_candidates["side"].astype(str) == side))
    n_non   = n_total - n_cand
    if n_total == 0:
        return ""
    return f"{side} non-candidate trials: {n_non}/{n_total} (candidates: {n_cand}/{n_total})"

def _select_dates_from_specs(df_mouse, spec):
    avail = sorted(df_mouse["date"].astype(str).unique())
    include_dates = set(spec.get("include_dates") or [])
    exclude_dates = set(spec.get("exclude_dates") or [])
    date_start = str(spec["date_start"])
    date_end = str(spec["date_end"])

    if include_dates:
        dates = [d for d in avail if d in include_dates]
    else:
        dates = [d for d in avail if date_start <= d <= date_end]

    dates = [d for d in dates if d not in exclude_dates]
    return sorted(dates)

def _rel_day_from_d0(date_str, d0_str):
    if d0_str is None:
        return np.nan
    return (_yyyymmdd_to_date(date_str) - _yyyymmdd_to_date(d0_str)).days

def _build_rows_from_df(df_in):
    rows_local = []
    for _, r in df_in.iterrows():
        Zt = np.load(r["tongue_npz"], allow_pickle=True)
        Zj = np.load(r["jaw_npz"], allow_pickle=True)

        fps_t = float(Zt["fps"])
        fps_j = float(Zj["fps"])
        if abs(fps_t - fps_j) > 1e-6:
            raise ValueError(f"fps mismatch for {r['mouse']} {r['date']} trial {r['trial_index']}")

        fps = fps_t
        pre_f  = abs(_ms_to_frames(VIEW_WIN_MS[0], fps))
        post_f = abs(_ms_to_frames(VIEW_WIN_MS[1], fps))
        t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))

        tongue_y = Zt["y_final"].astype(float)
        jaw_y    = Zj["y_final"].astype(float)

        tongue_yw = _snippet(tongue_y, int(r["reward_center_fr_tongue"]), pre_f, post_f)
        jaw_yw    = _snippet(jaw_y,    int(r["reward_center_fr_jaw"]),    pre_f, post_f)

        rows_local.append(dict(
            meta=r,
            fps=fps,
            t_ms=t_ms,
            tongue_y=tongue_yw,
            jaw_y_rows=_jaw_trace_for_mode(jaw_yw, r, JAW_ROWS_MODE),
            jaw_y_overlay=_jaw_trace_for_mode(jaw_yw, r, JAW_OVERLAY_MODE),
            peak_times_ms=_parse_peak_times(r["tongue_peak_times_ms"]),
        ))
    return rows_local

def _rows_subset(rows_all, date=None, side=None, candidate=None):
    out = rows_all
    if date is not None:
        out = [r for r in out if str(r["meta"]["date"]) == str(date)]
    if side is not None:
        out = [r for r in out if str(r["meta"]["side"]) == side]
    if candidate is not None:
        out = [r for r in out if bool(r["meta"]["candidate_no_lick_with_jaw_move"]) == bool(candidate)]
    return out

def _compute_overlay_limits(rows_subset):
    overlay_jaw_mode_limits = "global" if JAW_YLIM_MODE == "per_trial" else JAW_YLIM_MODE
    overlay_tong_mode_limits = "global" if TONGUE_YLIM_MODE == "per_trial" else TONGUE_YLIM_MODE

    jaw_lim = _limits_from_rows(
        rows_subset, "jaw_y_overlay",
        mode=overlay_jaw_mode_limits,
        ymax_percentile=JAW_YMAX_PERCENTILE,
        ymin_percentile=JAW_YMIN_PERCENTILE,
        pad_frac=YLIM_PAD_FRAC,
    )
    tong_lim = _limits_from_rows(
        rows_subset, "tongue_y",
        mode=overlay_tong_mode_limits,
        ymax_percentile=TONGUE_YMAX_PERCENTILE,
        ymin_percentile=TONGUE_YMIN_PERCENTILE,
        pad_frac=YLIM_PAD_FRAC,
    )
    return jaw_lim, tong_lim

def _add_overlay_scalebars(ax, ax2, rows_subset, jaw_lim, tong_lim):
    if not SHOW_SCALE_BARS:
        return

    jaw_bar_px = _choose_scalebar_px(
        jaw_lim, auto=AUTO_SCALEBARS,
        frac=SCALEBAR_FRAC_OF_AXIS_HEIGHT,
        fallback_px=JAW_SCALEBAR_PX
    )
    tong_bar_px = _choose_scalebar_px(
        tong_lim, auto=AUTO_SCALEBARS,
        frac=SCALEBAR_FRAC_OF_AXIS_HEIGHT,
        fallback_px=TONGUE_SCALEBAR_PX
    )

    jaw_vals = np.concatenate(
        [r["jaw_y_overlay"][np.isfinite(r["jaw_y_overlay"])] for r in rows_subset if np.any(np.isfinite(r["jaw_y_overlay"]))]
    ) if len(rows_subset) else np.array([])

    tong_vals = np.concatenate(
        [r["tongue_y"][np.isfinite(r["tongue_y"])] for r in rows_subset if np.any(np.isfinite(r["tongue_y"]))]
    ) if len(rows_subset) else np.array([])

    if jaw_vals.size > 0 and np.isfinite(jaw_bar_px):
        y0 = np.nanmin(jaw_vals)
        xbar = VIEW_WIN_MS[1] * 1.03
        _draw_capless_scalebar(
            ax, xbar, y0, jaw_bar_px, f"{int(round(jaw_bar_px))} px",
            color=SCALEBAR_COLOR, text_dx=20,
            linestyle=JAW_SCALEBAR_LS, lw=SCALEBAR_LW
        )

    if tong_vals.size > 0 and np.isfinite(tong_bar_px):
        y0t = np.nanmin(tong_vals)
        xbar2 = VIEW_WIN_MS[1] * 1.12
        _draw_capless_scalebar(
            ax2, xbar2, y0t, tong_bar_px, f"{int(round(tong_bar_px))} px",
            color=SCALEBAR_COLOR, text_dx=20,
            linestyle=TONGUE_SCALEBAR_LS, lw=SCALEBAR_LW
        )

def _make_poststroke_color_tools(rel_days_post):
    cmap = cm.get_cmap(POSTSTROKE_CMAP_NAME)
    vmax = max(rel_days_post) if len(rel_days_post) else 1
    norm = mcolors.Normalize(vmin=1, vmax=vmax)
    return cmap, norm

def _session_color(rel_day, cmap, norm):
    if not np.isfinite(rel_day) or rel_day <= 0:
        return "0.65"
    return cmap(norm(rel_day))

def _rel_day_bin_info(rel_day, bin_size_days):
    b = int(max(1, bin_size_days))
    rd = int(rel_day)

    if rd <= 0:
        idx = (-rd) // b
        bin_end = -(idx * b)
        bin_start = bin_end - (b - 1)
        rep_day = 0.0
        sort_key = bin_end
    else:
        idx = (rd - 1) // b
        bin_start = 1 + idx * b
        bin_end = bin_start + (b - 1)
        rep_day = 0.5 * (bin_start + bin_end)
        sort_key = bin_start

    label = f"d{bin_start:+d}" if bin_start == bin_end else f"d{bin_start:+d} to d{bin_end:+d}"
    return dict(sort_key=sort_key, bin_start=bin_start, bin_end=bin_end, rep_day=rep_day, label=label)

def _compute_session_summary_items(rows_mouse_total, eligible_dates, d0_str):
    items = []
    for d in eligible_dates:
        rel_day = _rel_day_from_d0(d, d0_str)
        for side in ("L", "R"):
            for candidate_flag in (True, False):
                rows_side = _rows_subset(rows_mouse_total, date=d, side=side, candidate=candidate_flag)
                if len(rows_side) == 0:
                    continue

                t_ms = np.asarray(rows_side[0]["t_ms"], float)
                jawM = np.vstack([np.asarray(r["jaw_y_overlay"], float) for r in rows_side])
                tongueM = np.vstack([np.asarray(r["tongue_y"], float) for r in rows_side])

                jaw_mu, jaw_sem, _ = _mean_sem_matrix(jawM)
                tongue_mu, tongue_sem, _ = _mean_sem_matrix(tongueM)

                items.append(dict(
                    date=str(d),
                    rel_day=float(rel_day),
                    side=side,
                    candidate=bool(candidate_flag),
                    t_ms=t_ms,
                    jaw_mu=jaw_mu,
                    jaw_sem=jaw_sem,
                    tongue_mu=tongue_mu,
                    tongue_sem=tongue_sem,
                    n_trials=len(rows_side),
                ))
    return items

def _compute_binned_summary_items(session_items, bin_size_days):
    grouped = {}
    for it in session_items:
        info = _rel_day_bin_info(int(it["rel_day"]), bin_size_days)
        key = (it["side"], it["candidate"], info["bin_start"], info["bin_end"])
        grouped.setdefault(key, []).append((it, info))

    out = []
    for key, vals in grouped.items():
        side, candidate, bin_start, bin_end = key
        t_ms = vals[0][0]["t_ms"]

        jaw_stack = np.vstack([v[0]["jaw_mu"] for v in vals])
        tongue_stack = np.vstack([v[0]["tongue_mu"] for v in vals])

        jaw_mu, jaw_sem, _ = _mean_sem_matrix(jaw_stack)
        tongue_mu, tongue_sem, _ = _mean_sem_matrix(tongue_stack)

        rep_day = np.median([v[1]["rep_day"] for v in vals])
        label = vals[0][1]["label"]
        sort_key = vals[0][1]["sort_key"]

        out.append(dict(
            side=side,
            candidate=bool(candidate),
            bin_start=int(bin_start),
            bin_end=int(bin_end),
            rep_day=float(rep_day),
            sort_key=float(sort_key),
            label=label,
            t_ms=t_ms,
            jaw_mu=jaw_mu,
            jaw_sem=jaw_sem,
            tongue_mu=tongue_mu,
            tongue_sem=tongue_sem,
            n_sessions=len(vals),
            n_trials_total=int(sum(v[0]["n_trials"] for v in vals)),   # NEW
        ))

    out = sorted(out, key=lambda x: (x["sort_key"], x["side"], x["candidate"]))
    return out

def _add_cross_session_colorbar(fig, cmap, norm):
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.90, 0.22, 0.015, 0.56])
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label("Post-stroke day")
    return cb

def _plot_individual_two_col(rows_cand, rows_non, title_prefix, save_path=None, display=True, save=False):
    if (len(rows_cand) == 0) and (len(rows_non) == 0):
        print("[info] no rows for individual 2-column viewer")
        return

    rows_all = rows_cand + rows_non
    jaw_global_lim_rows = _limits_from_rows(
        rows_all, "jaw_y_rows",
        mode=JAW_YLIM_MODE if JAW_YLIM_MODE != "per_trial" else "global",
        ymax_percentile=JAW_YMAX_PERCENTILE,
        ymin_percentile=JAW_YMIN_PERCENTILE,
        pad_frac=YLIM_PAD_FRAC,
    )
    tong_global_lim = _limits_from_rows(
        rows_all, "tongue_y",
        mode=TONGUE_YLIM_MODE if TONGUE_YLIM_MODE != "per_trial" else "global",
        ymax_percentile=TONGUE_YMAX_PERCENTILE,
        ymin_percentile=TONGUE_YMIN_PERCENTILE,
        pad_frac=YLIM_PAD_FRAC,
    )

    n_rows = max(len(rows_cand), len(rows_non))
    fig_height = max(INDIVIDUAL_FIGSIZE[1], ROW_HEIGHT * n_rows)
    fig, axs = plt.subplots(
        nrows=n_rows, ncols=2,
        figsize=(INDIVIDUAL_FIGSIZE[0], fig_height),
        sharex=True
    )
    axs = np.atleast_2d(axs)

    col_names = ["Candidate trials", "Non-candidate trials"]
    for cix in range(2):
        axs[0, cix].text(
            0.5, 1.18, col_names[cix],
            transform=axs[0, cix].transAxes,
            ha="center", va="bottom", fontsize=12, fontweight="bold"
        )

    for rix in range(n_rows):
        for cix, group_rows in enumerate([rows_cand, rows_non]):
            ax = axs[rix, cix]

            if rix >= len(group_rows):
                ax.axis("off")
                continue

            row = group_rows[rix]
            meta = row["meta"]
            t_ms = row["t_ms"]
            jaw_y_plot = np.asarray(row["jaw_y_rows"], float)
            tongue_y = np.asarray(row["tongue_y"], float)
            peak_times_ms = np.asarray(row["peak_times_ms"], float)

            side = str(meta["side"])
            c = SIDE_COLORS.get(side, "k")

            jm = _jaw_title_metrics(meta)

            if JAW_YLIM_MODE == "per_trial":
                jaw_lim_row = _limits_for_single_trace(jaw_y_plot, pad_frac=YLIM_PAD_FRAC)
            else:
                jaw_lim_row = jaw_global_lim_rows

            if TONGUE_YLIM_MODE == "per_trial":
                tong_lim_row = _limits_for_single_trace(tongue_y, pad_frac=YLIM_PAD_FRAC)
            else:
                tong_lim_row = tong_global_lim

            ax.plot(t_ms, jaw_y_plot, color=c, lw=JAW_LW, linestyle="-")
            ax.axvline(0, color=REWARD_COLOR, linestyle=":", lw=1.4, alpha=0.9)
            if JAW_ROWS_MODE == "baseline_subtracted" and SHOW_JAW_ZERO_LINE_WHEN_BASELINE_SUBTRACTED:
                ax.axhline(0, color=JAW_ZERO_LINE_COLOR, linestyle=JAW_ZERO_LINE_LS, lw=1.0, alpha=JAW_ZERO_LINE_ALPHA)
            ax.set_ylabel(_jaw_ylabel(JAW_ROWS_MODE), color=c)
            ax.tick_params(axis="y", labelcolor=c)
            ax.grid(True, alpha=0.2)
            if np.isfinite(jaw_lim_row[0]) and np.isfinite(jaw_lim_row[1]):
                ax.set_ylim(*jaw_lim_row)

            ax2 = ax.twinx()
            ax2.plot(t_ms, tongue_y, color=c, lw=TONGUE_LW, alpha=0.95, linestyle=TONGUE_LS)
            ax2.set_ylabel("Tongue Y (px)", color=c)
            ax2.tick_params(axis="y", labelcolor=c)
            if np.isfinite(tong_lim_row[0]) and np.isfinite(tong_lim_row[1]):
                ax2.set_ylim(*tong_lim_row)

            if peak_times_ms.size > 0:
                for tp in peak_times_ms:
                    idx = np.argmin(np.abs(t_ms - tp))
                    if 0 <= idx < len(tongue_y) and np.isfinite(tongue_y[idx]):
                        ax2.plot([t_ms[idx]], [tongue_y[idx]], marker="o", color=c, markersize=PEAK_MARKER_SIZE, linestyle="None")

            grp = "candidate" if bool(meta["candidate_no_lick_with_jaw_move"]) else "non-candidate"
            ttl = (
                f"{grp} | {meta['date']} | {side} trial {int(meta['trial_index'])} | "
                f"n_licks={int(meta['n_licks_in_window'])} | "
                f"jaw_sel={jm['jaw_sel']:.2f}px | "
                f"abs={jm['jaw_abs']:.2f}px | "
                f"pos={jm['jaw_pos']:.2f}px | "
                f"neg={jm['jaw_neg']:.2f}px | "
                f"thr={jm['jaw_thr']:.2f}px | "
                f"dir={jm['jaw_dir']} | "
                f"jaw_sd={jm['jaw_sd']:.2f} | "
                f"frames_over={int(meta['jaw_n_frames_over_thresh'])} | "
                f"{_format_baseline_text(meta)}"
            )
            ax.set_title(ttl, fontsize=9, loc="left")

            if SHOW_SCALE_BARS:
                jaw_finite = jaw_y_plot[np.isfinite(jaw_y_plot)]
                tongue_finite = tongue_y[np.isfinite(tongue_y)]

                jaw_bar_px = _choose_scalebar_px(
                    jaw_lim_row,
                    auto=AUTO_SCALEBARS,
                    frac=SCALEBAR_FRAC_OF_AXIS_HEIGHT,
                    fallback_px=JAW_SCALEBAR_PX
                )
                tong_bar_px = _choose_scalebar_px(
                    tong_lim_row,
                    auto=AUTO_SCALEBARS,
                    frac=SCALEBAR_FRAC_OF_AXIS_HEIGHT,
                    fallback_px=TONGUE_SCALEBAR_PX
                )

                if jaw_finite.size > 0 and np.isfinite(jaw_bar_px):
                    y0 = np.nanmin(jaw_finite)
                    xbar = VIEW_WIN_MS[1] * 1.03
                    _draw_capless_scalebar(
                        ax, xbar, y0, jaw_bar_px, f"{int(round(jaw_bar_px))} px",
                        color=SCALEBAR_COLOR, text_dx=20,
                        linestyle=JAW_SCALEBAR_LS, lw=SCALEBAR_LW
                    )

                if tongue_finite.size > 0 and np.isfinite(tong_bar_px):
                    y0t = np.nanmin(tongue_finite)
                    xbar2 = VIEW_WIN_MS[1] * 1.12
                    _draw_capless_scalebar(
                        ax2, xbar2, y0t, tong_bar_px, f"{int(round(tong_bar_px))} px",
                        color=SCALEBAR_COLOR, text_dx=20,
                        linestyle=TONGUE_SCALEBAR_LS, lw=SCALEBAR_LW
                    )

    for cix in range(2):
        axs[-1, cix].set_xlabel("Time relative to reward (ms)")

    fig.suptitle(title_prefix, y=0.995)
    plt.tight_layout()

    if save and (save_path is not None):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {save_path}")
    if display:
        plt.show()
    else:
        plt.close(fig)

def _plot_session_grid(rows_session_total, dd_session_total, dd_session_candidates, mouse, date_str, save_path=None, display=True, save=False):
    if len(rows_session_total) == 0:
        print(f"[info] no rows for session grid {mouse} {date_str}")
        return

    if SESSION_GRID_SHARED_Y:
        session_shared_jaw_lim = _limits_from_rows(
            rows_session_total, "jaw_y_overlay",
            mode="global" if JAW_YLIM_MODE == "per_trial" else JAW_YLIM_MODE,
            ymax_percentile=JAW_YMAX_PERCENTILE,
            ymin_percentile=JAW_YMIN_PERCENTILE,
            pad_frac=YLIM_PAD_FRAC,
        )
        session_shared_tong_lim = _limits_from_rows(
            rows_session_total, "tongue_y",
            mode="global" if TONGUE_YLIM_MODE == "per_trial" else TONGUE_YLIM_MODE,
            ymax_percentile=TONGUE_YMAX_PERCENTILE,
            ymin_percentile=TONGUE_YMIN_PERCENTILE,
            pad_frac=YLIM_PAD_FRAC,
        )
    else:
        session_shared_jaw_lim = (np.nan, np.nan)
        session_shared_tong_lim = (np.nan, np.nan)

    fig, axes = plt.subplots(4, 2, figsize=SESSION_GRID_FIGSIZE, sharex=True)
    fig.subplots_adjust(hspace=0.38, wspace=0.22)

    row_specs = [
        dict(enabled=SHOW_ROW_CANDIDATE_OVERLAY, candidate=True,  meansem=False, row_label="overlay candidate"),
        dict(enabled=SHOW_ROW_NONCANDIDATE_OVERLAY, candidate=False, meansem=False, row_label="overlay non-candidate"),
        dict(enabled=SHOW_ROW_CANDIDATE_MEANSEM, candidate=True,  meansem=True,  row_label="mean±SEM candidate"),
        dict(enabled=SHOW_ROW_NONCANDIDATE_MEANSEM, candidate=False, meansem=True,  row_label="mean±SEM non-candidate"),
    ]

    for rix, spec in enumerate(row_specs):
        for cix, side in enumerate(["L", "R"]):
            ax = axes[rix, cix]
            ax2 = ax.twinx()

            rows_side = _rows_subset(rows_session_total, side=side, candidate=spec["candidate"])
            subtitle = (
                _format_candidate_count_text(side, dd_session_total, dd_session_candidates)
                if spec["candidate"]
                else _format_noncandidate_count_text(side, dd_session_total, dd_session_candidates)
            )

            panel_title = f"{spec['row_label']} | side={side}"
            if len(subtitle) > 0:
                panel_title += f"\n{subtitle}"
            ax.set_title(panel_title, fontsize=10)

            if not spec["enabled"]:
                ax.text(0.5, 0.5, "disabled", ha="center", va="center", transform=ax.transAxes, fontsize=11, color="0.5")
                ax.set_xticks([])
                ax.set_yticks([])
                ax2.set_yticks([])
                continue

            if len(rows_side) == 0:
                ax.text(0.5, 0.5, "no trials", ha="center", va="center", transform=ax.transAxes, fontsize=11, color="0.5")
                ax.set_xticks([])
                ax.set_yticks([])
                ax2.set_yticks([])
                continue

            c = SIDE_COLORS[side]

            if SESSION_GRID_SHARED_Y:
                jaw_lim, tong_lim = session_shared_jaw_lim, session_shared_tong_lim
            else:
                jaw_lim, tong_lim = _compute_overlay_limits(rows_side)

            if spec["meansem"]:
                if SHOW_FAINT_TRIALS_IN_MEAN_SEM_OVERLAY:
                    for row in rows_side:
                        ax.plot(
                            np.asarray(row["t_ms"], float),
                            np.asarray(row["jaw_y_overlay"], float),
                            color=c, lw=FAINT_TRIAL_JAW_LW, alpha=FAINT_TRIAL_JAW_ALPHA, linestyle="-"
                        )
                        ax2.plot(
                            np.asarray(row["t_ms"], float),
                            np.asarray(row["tongue_y"], float),
                            color=c, lw=FAINT_TRIAL_TONGUE_LW, alpha=FAINT_TRIAL_TONGUE_ALPHA, linestyle=TONGUE_LS
                        )

                t_side = np.asarray(rows_side[0]["t_ms"], float)
                jawM = np.vstack([np.asarray(r["jaw_y_overlay"], float) for r in rows_side])
                tongM = np.vstack([np.asarray(r["tongue_y"], float) for r in rows_side])

                jaw_mu, jaw_sem, _ = _mean_sem_matrix(jawM)
                tong_mu, tong_sem, _ = _mean_sem_matrix(tongM)

                ax.plot(t_side, jaw_mu, color=c, lw=MEAN_JAW_LW, alpha=MEAN_JAW_ALPHA, linestyle="-")
                okj = np.isfinite(jaw_mu) & np.isfinite(jaw_sem)
                if np.any(okj):
                    ax.fill_between(t_side[okj], (jaw_mu - jaw_sem)[okj], (jaw_mu + jaw_sem)[okj],
                                    color=c, alpha=SEM_JAW_ALPHA, lw=0)

                ax2.plot(t_side, tong_mu, color=c, lw=MEAN_TONGUE_LW, alpha=MEAN_TONGUE_ALPHA, linestyle=TONGUE_LS)
                okt = np.isfinite(tong_mu) & np.isfinite(tong_sem)
                if np.any(okt):
                    ax2.fill_between(t_side[okt], (tong_mu - tong_sem)[okt], (tong_mu + tong_sem)[okt],
                                     color=c, alpha=SEM_TONGUE_ALPHA, lw=0)
            else:
                for row in rows_side:
                    t_ms = np.asarray(row["t_ms"], float)
                    jaw_y_plot = np.asarray(row["jaw_y_overlay"], float)
                    tongue_y = np.asarray(row["tongue_y"], float)
                    peak_times_ms = np.asarray(row["peak_times_ms"], float)

                    ax.plot(t_ms, jaw_y_plot, color=c, lw=JAW_LW, alpha=OVERLAY_JAW_ALPHA, linestyle="-")
                    ax2.plot(t_ms, tongue_y, color=c, lw=TONGUE_LW, alpha=OVERLAY_TONGUE_ALPHA, linestyle=TONGUE_LS)

                    if OVERLAY_SHOW_PEAKS and peak_times_ms.size > 0:
                        for tp in peak_times_ms:
                            idx = np.argmin(np.abs(t_ms - tp))
                            if 0 <= idx < len(tongue_y) and np.isfinite(tongue_y[idx]):
                                ax2.plot([t_ms[idx]], [tongue_y[idx]], marker="o", color=c, markersize=3, linestyle="None", alpha=0.8)

            ax.axvline(0, color=REWARD_COLOR, linestyle=":", lw=1.4, alpha=0.9)
            if JAW_OVERLAY_MODE == "baseline_subtracted" and SHOW_JAW_ZERO_LINE_WHEN_BASELINE_SUBTRACTED:
                ax.axhline(0, color=JAW_ZERO_LINE_COLOR, linestyle=JAW_ZERO_LINE_LS, lw=1.0, alpha=JAW_ZERO_LINE_ALPHA)

            ax.set_ylabel(_jaw_ylabel(JAW_OVERLAY_MODE), color="k")
            ax2.set_ylabel("Tongue Y (px)", color="k")
            ax.grid(True, alpha=0.2)

            if np.isfinite(jaw_lim[0]) and np.isfinite(jaw_lim[1]):
                ax.set_ylim(*jaw_lim)
            if np.isfinite(tong_lim[0]) and np.isfinite(tong_lim[1]):
                ax2.set_ylim(*tong_lim)

            _add_overlay_scalebars(ax, ax2, rows_side, jaw_lim, tong_lim)

            if rix == 3:
                ax.set_xlabel("Time relative to reward (ms)")

    fig.suptitle(
        f"{mouse} {date_str} | within-session overlay grid | overlay={_jaw_mode_tag(JAW_OVERLAY_MODE)}",
        y=0.995
    )
    plt.tight_layout()

    if save and (save_path is not None):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {save_path}")
    if display:
        plt.show()
    else:
        plt.close(fig)

def _plot_cross_session_grid(items, mouse, title_label, save_path=None, display=True, save=False, binned=False):
    if len(items) == 0:
        print(f"[info] no items for cross-session figure: {mouse} {title_label}")
        return

    fig, axes = plt.subplots(2, 2, figsize=CROSS_SESSION_GRID_FIGSIZE, sharex=True)
    fig.subplots_adjust(hspace=0.34, wspace=0.24)

    if CROSS_SESSION_GRID_SHARED_Y:
        jaw_lim = _limits_from_summary_items(
            items, "jaw_mu", "jaw_sem",
            mode="global" if JAW_YLIM_MODE == "per_trial" else JAW_YLIM_MODE,
            ymax_percentile=JAW_YMAX_PERCENTILE,
            ymin_percentile=JAW_YMIN_PERCENTILE,
            pad_frac=YLIM_PAD_FRAC
        )
        tong_lim = _limits_from_summary_items(
            items, "tongue_mu", "tongue_sem",
            mode="global" if TONGUE_YLIM_MODE == "per_trial" else TONGUE_YLIM_MODE,
            ymax_percentile=TONGUE_YMAX_PERCENTILE,
            ymin_percentile=TONGUE_YMIN_PERCENTILE,
            pad_frac=YLIM_PAD_FRAC
        )
    else:
        jaw_lim = (np.nan, np.nan)
        tong_lim = (np.nan, np.nan)

    post_vals = sorted({
        int(it["rel_day"] if not binned else it["rep_day"])
        for it in items
        if (it["rel_day"] if not binned else it["rep_day"]) > 0
    })
    cmap, norm = _make_poststroke_color_tools(post_vals)

    for rix, candidate_flag in enumerate([True, False]):
        for cix, side in enumerate(["L", "R"]):
            ax = axes[rix, cix]
            ax2 = ax.twinx()

            panel_items = [it for it in items if (it["side"] == side and bool(it["candidate"]) == candidate_flag)]

            row_label = "candidate" if candidate_flag else "non-candidate"

            if len(panel_items) == 0:
                ax.set_title(f"{row_label} | side={side}", fontsize=10)
                ax.text(0.5, 0.5, "no sessions", ha="center", va="center", transform=ax.transAxes, fontsize=11, color="0.5")
                ax.set_xticks([])
                ax.set_yticks([])
                ax2.set_yticks([])
                continue

            n_trials_total = int(sum(it.get("n_trials_total", it.get("n_trials", 0)) for it in panel_items))
            if binned:
                n_groups = int(sum(it.get("n_sessions", 1) for it in panel_items))
                subtitle = f"n_trials={n_trials_total} | n_sessions={n_groups} | n_bins={len(panel_items)}"
            else:
                subtitle = f"n_trials={n_trials_total} | n_sessions={len(panel_items)}"

            ax.set_title(f"{row_label} | side={side}\n{subtitle}", fontsize=10)

            if not CROSS_SESSION_GRID_SHARED_Y:
                jaw_lim_panel = _limits_from_summary_items(
                    panel_items, "jaw_mu", "jaw_sem",
                    mode="global" if JAW_YLIM_MODE == "per_trial" else JAW_YLIM_MODE,
                    ymax_percentile=JAW_YMAX_PERCENTILE,
                    ymin_percentile=JAW_YMIN_PERCENTILE,
                    pad_frac=YLIM_PAD_FRAC
                )
                tong_lim_panel = _limits_from_summary_items(
                    panel_items, "tongue_mu", "tongue_sem",
                    mode="global" if TONGUE_YLIM_MODE == "per_trial" else TONGUE_YLIM_MODE,
                    ymax_percentile=TONGUE_YMAX_PERCENTILE,
                    ymin_percentile=TONGUE_YMIN_PERCENTILE,
                    pad_frac=YLIM_PAD_FRAC
                )
            else:
                jaw_lim_panel = jaw_lim
                tong_lim_panel = tong_lim

            for it in panel_items:
                color_val = _session_color(it["rep_day"] if binned else it["rel_day"], cmap, norm)
                lw = CROSS_SESSION_BIN_LINE_LW if binned else CROSS_SESSION_LINE_LW
                line_alpha = CROSS_SESSION_BIN_LINE_ALPHA if binned else CROSS_SESSION_LINE_ALPHA
                fill_alpha_j = CROSS_SESSION_BIN_FILL_ALPHA if binned else CROSS_SESSION_FILL_ALPHA
                fill_alpha_t = 0.8 * fill_alpha_j

                t_ms = np.asarray(it["t_ms"], float)

                ax.plot(
                    t_ms, it["jaw_mu"],
                    color=color_val, lw=lw, alpha=line_alpha, linestyle="-"
                )
                okj = np.isfinite(it["jaw_mu"]) & np.isfinite(it["jaw_sem"])
                if np.any(okj):
                    ax.fill_between(
                        t_ms[okj],
                        (it["jaw_mu"] - it["jaw_sem"])[okj],
                        (it["jaw_mu"] + it["jaw_sem"])[okj],
                        color=color_val, alpha=fill_alpha_j, lw=0
                    )

                ax2.plot(
                    t_ms, it["tongue_mu"],
                    color=color_val, lw=lw, alpha=line_alpha, linestyle=TONGUE_LS
                )
                okt = np.isfinite(it["tongue_mu"]) & np.isfinite(it["tongue_sem"])
                if np.any(okt):
                    ax2.fill_between(
                        t_ms[okt],
                        (it["tongue_mu"] - it["tongue_sem"])[okt],
                        (it["tongue_mu"] + it["tongue_sem"])[okt],
                        color=color_val, alpha=fill_alpha_t, lw=0
                    )

            ax.axvline(0, color=REWARD_COLOR, linestyle=":", lw=1.2, alpha=0.9)
            if JAW_OVERLAY_MODE == "baseline_subtracted" and SHOW_JAW_ZERO_LINE_WHEN_BASELINE_SUBTRACTED:
                ax.axhline(0, color=JAW_ZERO_LINE_COLOR, linestyle=JAW_ZERO_LINE_LS, lw=1.0, alpha=JAW_ZERO_LINE_ALPHA)

            ax.set_ylabel(_jaw_ylabel(JAW_OVERLAY_MODE), color="k")
            ax2.set_ylabel("Tongue Y (px)", color="k")
            ax.grid(True, alpha=0.2)

            if np.isfinite(jaw_lim_panel[0]) and np.isfinite(jaw_lim_panel[1]):
                ax.set_ylim(*jaw_lim_panel)
            if np.isfinite(tong_lim_panel[0]) and np.isfinite(tong_lim_panel[1]):
                ax2.set_ylim(*tong_lim_panel)

            if rix == 1:
                ax.set_xlabel("Time relative to reward (ms)")

    legend_handles = [
        Line2D([0], [0], color="k", lw=2.0, linestyle="-", label="Jaw"),
        Line2D([0], [0], color="k", lw=2.0, linestyle=TONGUE_LS, label="Tongue"),
        Line2D([0], [0], color="0.65", lw=2.0, linestyle="-", label="Pre-stroke"),
    ]
    fig.legend(handles=legend_handles, frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.995))

    fig.suptitle(
        f"{mouse} | {title_label} | pre-stroke=grey, post-stroke={POSTSTROKE_CMAP_NAME} | day 0 treated as pre-stroke",
        y=1.03
    )

    plt.tight_layout(rect=[0.0, 0.0, 0.88, 0.98])

    if len(post_vals) > 0:
        _add_cross_session_colorbar(fig, cmap, norm)

    if save and (save_path is not None):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {save_path}")
    if display:
        plt.show()
    else:
        plt.close(fig)


# ===================== MAIN =====================
if "df_trials_candidates" not in globals():
    raise RuntimeError("df_trials_candidates not found. Run the classifier cell first.")

mice = list(MOUSE_SPECS.keys()) if (MICE_TO_RUN is None) else list(MICE_TO_RUN)

for mouse in mice:
    if mouse not in MOUSE_SPECS:
        print(f"[skip] {mouse}: not in MOUSE_SPECS")
        continue

    spec = MOUSE_SPECS[mouse]
    d0_str = spec.get("d0", None)
    bin_size_days = int(spec.get("bin_size_days", 1))

    dd_mouse_all = df_trials_candidates.copy()
    dd_mouse_all = dd_mouse_all[dd_mouse_all["mouse"] == mouse].copy()

    if SIDE_FILTER is not None:
        dd_mouse_all = dd_mouse_all[dd_mouse_all["side"] == SIDE_FILTER].copy()

    if dd_mouse_all.empty:
        print(f"[warn] {mouse}: no trials found")
        continue

    eligible_dates = _select_dates_from_specs(dd_mouse_all, spec)
    if len(eligible_dates) == 0:
        print(f"[warn] {mouse}: no eligible dates after filtering")
        continue

    dd_mouse_total = dd_mouse_all[dd_mouse_all["date"].astype(str).isin(eligible_dates)].copy()
    dd_mouse_total = dd_mouse_total.sort_values(["date_dt", "side", "trial_index"]).reset_index(drop=True)

    if dd_mouse_total.empty:
        print(f"[warn] {mouse}: eligible date set is empty in df_trials_candidates")
        continue

    save_dir = (
        OUT_ROOT / mouse / f"{mouse}_jaw_kinematics" / "kinematics_figures" /
        JAW_CENTER_MODE / SAVE_FOLDERNAME
    )
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[info] ===== {mouse} =====")
    print(f"[info] eligible dates: {eligible_dates}")
    print(f"[info] n trials total: {len(dd_mouse_total)}")

    # build rows once per mouse
    rows_mouse_total = _build_rows_from_df(dd_mouse_total)

    rowmap = {
        (str(r["meta"]["date"]), str(r["meta"]["side"]), int(r["meta"]["trial_index"])): r
        for r in rows_mouse_total
    }

    def _lookup_rows(df_in):
        out = []
        for _, r in df_in.iterrows():
            key = (str(r["date"]), str(r["side"]), int(r["trial_index"]))
            if key in rowmap:
                out.append(rowmap[key])
        return out

    # ---------- within-session figures ----------
    for date_str in eligible_dates:
        dd_session_total = dd_mouse_total[dd_mouse_total["date"].astype(str) == str(date_str)].copy().reset_index(drop=True)
        if dd_session_total.empty:
            continue

        dd_session_candidates = dd_session_total[dd_session_total["candidate_no_lick_with_jaw_move"]].copy().reset_index(drop=True)
        dd_session_noncandidates = dd_session_total[~dd_session_total["candidate_no_lick_with_jaw_move"]].copy().reset_index(drop=True)

        def _sort_and_limit(df_in):
            if len(df_in) == 0:
                return df_in.copy()
            out = df_in.copy()
            if TOP_N_BY_JAW_DEFLECTION is not None:
                out["_sort_metric_"] = _resolve_sort_series(out, SORT_METRIC)
                out = (
                    out.sort_values("_sort_metric_", ascending=(not SORT_DESCENDING_BY_JAW))
                       .head(int(TOP_N_BY_JAW_DEFLECTION))
                       .drop(columns=["_sort_metric_"])
                       .reset_index(drop=True)
                )
            return out

        dd_individual_candidates = _sort_and_limit(dd_session_candidates)
        dd_individual_noncandidates = _sort_and_limit(dd_session_noncandidates)

        rows_individual_candidates = _lookup_rows(dd_individual_candidates)
        rows_individual_noncandidates = _lookup_rows(dd_individual_noncandidates)

        rows_session_total = _rows_subset(rows_mouse_total, date=date_str)

        date_tag = f"_{date_str}"
        side_tag = f"_side-{SIDE_FILTER}" if SIDE_FILTER is not None else ""
        jaw_rows_tag = _jaw_mode_tag(JAW_ROWS_MODE)
        jaw_overlay_tag = _jaw_mode_tag(JAW_OVERLAY_MODE)

        if DISPLAY_SESSION_INDIVIDUAL or SAVE_SESSION_INDIVIDUAL:
            rows_title = (
                f"{mouse}{date_tag} | individual trials | "
                f"col1=candidate, col2=non-candidate | rows={jaw_rows_tag}"
            )
            rows_save = save_dir / (
                f"{mouse}{date_tag}{side_tag}_individualTrials2col_candidateVsNoncandidate_{jaw_rows_tag}.png"
            )
            _plot_individual_two_col(
                rows_individual_candidates,
                rows_individual_noncandidates,
                title_prefix=rows_title,
                save_path=rows_save,
                display=DISPLAY_SESSION_INDIVIDUAL,
                save=SAVE_SESSION_INDIVIDUAL
            )

        if DISPLAY_SESSION_GRID or SAVE_SESSION_GRID:
            grid_save = save_dir / (
                f"{mouse}{date_tag}{side_tag}_sessionOverlayGrid4x2_{jaw_overlay_tag}.png"
            )
            _plot_session_grid(
                rows_session_total,
                dd_session_total,
                dd_session_candidates,
                mouse=mouse,
                date_str=date_str,
                save_path=grid_save,
                display=DISPLAY_SESSION_GRID,
                save=SAVE_SESSION_GRID
            )

    # ---------- cross-session figures ----------
    session_items = _compute_session_summary_items(rows_mouse_total, eligible_dates, d0_str)

    if DISPLAY_CROSS_SESSION_OVERLAY or SAVE_CROSS_SESSION_OVERLAY:
        out_path = save_dir / f"{mouse}_crossSessionOverlay2x2_{_jaw_mode_tag(JAW_OVERLAY_MODE)}.png"
        _plot_cross_session_grid(
            session_items,
            mouse=mouse,
            title_label="cross-session session overlays (mean ± SEM per session)",
            save_path=out_path,
            display=DISPLAY_CROSS_SESSION_OVERLAY,
            save=SAVE_CROSS_SESSION_OVERLAY,
            binned=False
        )

    binned_items = _compute_binned_summary_items(session_items, bin_size_days=bin_size_days)

    if DISPLAY_CROSS_SESSION_BINNED or SAVE_CROSS_SESSION_BINNED:
        out_path = save_dir / f"{mouse}_crossSessionBinned2x2_bins{bin_size_days}_{_jaw_mode_tag(JAW_OVERLAY_MODE)}.png"
        _plot_cross_session_grid(
            binned_items,
            mouse=mouse,
            title_label=f"cross-session binned overlays (bin size = {bin_size_days} days)",
            save_path=out_path,
            display=DISPLAY_CROSS_SESSION_BINNED,
            save=SAVE_CROSS_SESSION_BINNED,
            binned=True
        )

print("[ok] plotting done")
