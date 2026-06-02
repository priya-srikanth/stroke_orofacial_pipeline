=== cell 50 (code, 1592 lines) ===
# ===== Exploratory tongue angle / lick-phase analysis (single-session + cross-session overlays) =====

import re
import hashlib
import warnings
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from scipy.ndimage import gaussian_filter1d

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ===================== USER KNOBS =====================

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

CENTER_MODE = "centered_spout_midpoint"
INTERP_VERSION = "v5p3"

# centered parquet cache used to estimate session-fixed eye midpoint
CACHE_CENTER_MODE = "spout_midpoint"
CACHE_CENTER_LIK_THR = 0.70
SIGNATURE_OVERRIDE = None
REQUIRE_EXPECTED_SIG = False

# run mode
RUN_MODE = "batch"   # "single" or "batch"
MICE_TO_RUN = None   # eg ["PS46"]; None => all mice in MOUSE_SPECS when RUN_MODE="batch"

# single-session test
TEST_MOUSE = "PS46"
TEST_DATE  = "20250315"
CAM = "cam2"

# optional single-session overrides (set to None to use MOUSE_SPECS defaults)
TEST_PLOT_WIN_MS = None
TEST_DETECT_WIN_MS = None

# multi-animal structure
MOUSE_SPECS = {
    "PS46": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS47": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS48": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS49": dict(date_start="20250310", date_end="20250406", d0="20250317", bin_days=2, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS50": dict(date_start="20250319", date_end="20250406", d0="20250323", bin_days=2, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS51": dict(date_start="20250416", date_end="20250709", d0="20250429", bin_days=7, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS54": dict(date_start="20250416", date_end="20250709", d0="20250430", bin_days=7, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
    "PS55": dict(date_start="20250416", date_end="20250709", d0="20250430", bin_days=7, include_dates=None, exclude_dates=None,
                 plot_win_ms=(0.0, 8000.0), detect_win_ms=(70.0, 3000.0)),
}

# source arrays inside tongue interpolation NPZ
PHASE_Y_KEY = "y_final"
ANGLE_XY_KEYS_PREFERRED = [
    ("x_interp_filled", "y_interp_filled"),
    ("x_interp", "y_interp"),
    ("x_final", "y_final"),
]

# eye midpoint estimation from centered parquet cache
EYE_LIK_THR = 0.70
MIN_VALID_EYE_FRAMES = 100
ALLOW_ONE_EYE_FALLBACK = True

# angle sign convention
ANGLE_SIGN_FLIP = -1.0   # left negative, right positive

# ---------- smoothing ----------
# lick detection smoothing on Y (used only for dy/dt lick detection)
DO_SMOOTH_Y_FOR_DETECTION = True
GAUSS_SIGMA_MS_DETECT_Y = 12.0

# angle smoothing for analysis / display (independent of lick detection)
DO_SMOOTH_ANGLE = True
GAUSS_SIGMA_MS_ANGLE = 8.0

# optional light circular smoothing of the phase summary curve across bins
DO_SMOOTH_PHASE_CURVE = True
PHASE_CURVE_SIGMA_BINS = 1.0

# phase-bin support thresholds
MIN_PHASE_POINTS_PER_BIN_SINGLE = 5   # single-session phase plot
MIN_PHASE_POINTS_PER_BIN_OVERLAY = 5   # pooled cross-session overlays; lower to reduce broken segments

# cross-session overlay y-axis limits (shared across all 6 panels within animal)
# examples: (1.0, 99.0) or (0.1, 99.9); set to None to disable percentile clipping
OVERLAY_Y_PCT = (0.10, 99.9)
OVERLAY_Y_PAD_FRAC = 0.15  # vertical padding as fraction of data range after percentile clipping

# ---------- pooled-analysis inclusion thresholds (session-level; overlays only) ----------
# Set optional thresholds to 0 to disable.
MIN_TIME_TRIALS_PER_SESSION      = 0   # reward-aligned pooled rows
MIN_FIRSTPEAK_TRIALS_PER_SESSION = 5   # first-peak aligned pooled rows
MIN_PHASE_LICKS_PER_SESSION      = 15  # detected lick peaks contributing to selected phase summary
MIN_PHASE_TRIALS_PER_SESSION     = 5   # unique trials contributing to selected phase summary

# ---------- lick detection semantics ----------
RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0
MIN_PEAK_Y_ABS = 20.0
PEAK_PAD_MS = 52.0
MAX_LICKS_PER_TRIAL = 40

# ---------- bout logic ----------
ALLOW_SINGLE_LICK_BOUTS = True
BOUT_MAX_IPI_MS = 300.0
SINGLE_BOUT_WIN_MS = (-120.0, 200.0)

# ---------- which bouts contribute to each summary ----------
# reward-aligned time plot: "all_bouts", "first_bout", "first_multi"
TIME_SUMMARY_MODE = "first_multi"

# phase-aligned and XY phase plots: "all_multi" or "first_multi"
PHASE_SUMMARY_MODE = "first_multi"
XY_SUMMARY_MODE = "first_multi"

# ---------- first detected lick peak–aligned panel ----------
FIRST_PEAK_ALIGN_WIN_MS = (-180.0, 1000.0)

# ---------- phase binning ----------
N_PHASE_BINS = 72

# ---------- figure toggles ----------
SHOW_SINGLE_SESSION_FIGS = False
SAVE_SINGLE_SESSION_FIGS = True

SHOW_OVERLAY_ALLSESS_FIGS = True
SAVE_OVERLAY_ALLSESS_FIGS = True

SHOW_OVERLAY_BINNED_FIGS = True
SAVE_OVERLAY_BINNED_FIGS = True

SAVE_TABLES = True
FIG_DPI = 200

VIEW_N_TRIALS_PER_SIDE = 10
VIEW_SIDES = ("L", "R")
SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}

# QC plot display
QC_DETECT_ALPHA = 0.035
QC_BOUT_ALPHA = 0.012
QC_PEAK_SIZE = 18

# overlay appearance
OVERLAY_LINE_LW = 1.2
OVERLAY_LINE_ALPHA = 0.7
BIN_FILL_ALPHA = 0.15
PRE_COLOR = "0.55"
POST_CMAP = plt.get_cmap("plasma")

# save dir
SAVE_SUBDIR = "angle_phase_exploratory"

# ======================================================


# ===================== HELPERS =====================

def yyyymmdd_to_date(s):
    return datetime.strptime(str(s), "%Y%m%d").date()

def daterange_yyyymmdd(start_s, end_s):
    d0 = yyyymmdd_to_date(start_s)
    d1 = yyyymmdd_to_date(end_s)
    if d1 < d0:
        raise ValueError("DATE_END must be >= DATE_START")
    out = []
    d = d0
    while d <= d1:
        out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out

def _rel_day_from_d0(date_str, d0_str):
    return (yyyymmdd_to_date(date_str) - yyyymmdd_to_date(d0_str)).days

def _bin_rel_day(rel_day, bin_days):
    rel_day = int(rel_day)
    b = int(bin_days)
    if rel_day >= 1:
        start = ((rel_day - 1) // b) * b + 1
        end = start + b - 1
    else:
        end = -((abs(rel_day)) // b) * b
        start = end - (b - 1)
    center = 0.5 * (start + end)
    label = f"{start}..{end}"
    return start, end, center, label

def _post_color(rel_day, max_post_day):
    if (rel_day is None) or (pd.isna(rel_day)) or (rel_day <= 0):
        return PRE_COLOR
    if max_post_day is None or max_post_day <= 1:
        return POST_CMAP(0.8)
    v = (float(rel_day) - 1.0) / max(1e-9, float(max_post_day) - 1.0)
    v = np.clip(v, 0.0, 1.0)
    return POST_CMAP(v)

def _post_color_from_center(center, max_post_center):
    if (center is None) or (pd.isna(center)) or (center <= 0):
        return PRE_COLOR
    if max_post_center is None or max_post_center <= 1:
        return POST_CMAP(0.8)
    v = (float(center) - 1.0) / max(1e-9, float(max_post_center) - 1.0)
    v = np.clip(v, 0.0, 1.0)
    return POST_CMAP(v)

def _ms_to_frames(ms, fps):
    return int(np.round((ms / 1000.0) * fps))

def _snippet(arr, center_fr, pre_f, post_f):
    T = pre_f + post_f + 1
    lo = center_fr - pre_f
    hi = center_fr + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, len(arr) - 1)
    if src_hi < src_lo:
        return out
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo:dst_hi+1] = arr[src_lo:src_hi+1]
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

def _gaussian_smooth_nan(y, sigma_f, mode="nearest"):
    y = np.asarray(y, float)
    if (sigma_f is None) or (sigma_f <= 0):
        return y.copy()
    finite = np.isfinite(y)
    if not np.any(finite):
        return np.full_like(y, np.nan, dtype=float)
    y0 = np.where(finite, y, 0.0)
    num = gaussian_filter1d(y0, sigma=sigma_f, mode=mode)
    den = gaussian_filter1d(finite.astype(float), sigma=sigma_f, mode=mode)
    out = np.full_like(y, np.nan, dtype=float)
    good = den > 1e-8
    out[good] = num[good] / den[good]
    return out

def _expected_sig(center_mode, center_lik_thr):
    s = f"CENTER={center_mode}|CLIK={center_lik_thr}"
    return hashlib.md5(s.encode()).hexdigest()[:8]

def _list_session_npzs(mouse, cam):
    sess_dir = OUT_ROOT / mouse / f"{mouse}_tongue_kinematics" / "processed_interpolated_data" / f"{CENTER_MODE}"
    if not sess_dir.exists():
        raise FileNotFoundError(f"Missing processed_interpolated_data folder:\n  {sess_dir}")
    pat = re.compile(rf"^{re.escape(mouse)}_(?P<date>\d{{8}})_{re.escape(cam)}_tongue_interp_{INTERP_VERSION}\.npz$")
    available = {}
    for p in sorted(sess_dir.glob(f"{mouse}_*_{cam}_tongue_interp_{INTERP_VERSION}.npz")):
        m = pat.match(p.name)
        if m:
            available[m.group("date")] = p
    return available, sess_dir

def _pick_session_dates(mouse, spec):
    inc = spec.get("include_dates", None)
    exc = set(spec.get("exclude_dates", None) or [])
    if inc:
        dates = [d for d in inc]
    else:
        dates = daterange_yyyymmdd(spec["date_start"], spec["date_end"])
    return [d for d in dates if d not in exc]

def _load_eye_cache_df(mouse, date_yyyymmdd, cam):
    cache_dir = OUT_ROOT / mouse / f"_dlc_cache_centered_{CACHE_CENTER_MODE}"
    if not cache_dir.exists():
        raise FileNotFoundError(f"Missing cache dir:\n  {cache_dir}")

    date_iso = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    cam_num = cam.replace("cam", "")
    token = f"video{cam_num}_{date_iso}"

    expected_sig = _expected_sig(CACHE_CENTER_MODE, CACHE_CENTER_LIK_THR)
    pat = re.compile(r"^(?P<base>.+)\.intermediate\.(?P<sig>[0-9a-f]{8})\.parquet$")

    matches = []
    for f in cache_dir.glob("*.parquet"):
        m = pat.match(f.name)
        if not m:
            continue
        base = m.group("base")
        sig = m.group("sig")
        if token in base:
            matches.append((base, sig, f))

    if not matches:
        raise FileNotFoundError(f"No cache parquet found for {mouse} {cam} {date_yyyymmdd} in\n  {cache_dir}")

    if SIGNATURE_OVERRIDE is not None:
        matches2 = [x for x in matches if x[1] == SIGNATURE_OVERRIDE]
        if matches2:
            matches = matches2
    elif any(sig == expected_sig for _, sig, _ in matches):
        matches = [x for x in matches if x[1] == expected_sig]
    elif REQUIRE_EXPECTED_SIG:
        raise FileNotFoundError(
            f"Found cache parquet(s) for {mouse} {cam} {date_yyyymmdd}, but none matched expected sig={expected_sig}"
        )

    matches = sorted(matches, key=lambda x: x[0])
    dfs = [pd.read_parquet(f) for _, _, f in matches]
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    return df, [str(x[2]) for x in matches]

def _estimate_session_eye_midpoint(df_eye):
    req = ["L_eye_x", "L_eye_y", "L_eye_likelihood", "R_eye_x", "R_eye_y", "R_eye_likelihood"]
    missing = [c for c in req if c not in df_eye.columns]
    if missing:
        raise KeyError(f"Eye columns missing from centered cache DF: {missing}")

    lx = pd.to_numeric(df_eye["L_eye_x"], errors="coerce").to_numpy(float)
    ly = pd.to_numeric(df_eye["L_eye_y"], errors="coerce").to_numpy(float)
    ll = pd.to_numeric(df_eye["L_eye_likelihood"], errors="coerce").to_numpy(float)

    rx = pd.to_numeric(df_eye["R_eye_x"], errors="coerce").to_numpy(float)
    ry = pd.to_numeric(df_eye["R_eye_y"], errors="coerce").to_numpy(float)
    rl = pd.to_numeric(df_eye["R_eye_likelihood"], errors="coerce").to_numpy(float)

    both = (
        np.isfinite(lx) & np.isfinite(ly) & np.isfinite(ll) & (ll >= EYE_LIK_THR) &
        np.isfinite(rx) & np.isfinite(ry) & np.isfinite(rl) & (rl >= EYE_LIK_THR)
    )

    if np.sum(both) >= MIN_VALID_EYE_FRAMES:
        midx = 0.5 * (lx[both] + rx[both])
        midy = 0.5 * (ly[both] + ry[both])
        return float(np.nanmedian(midx)), float(np.nanmedian(midy)), int(np.sum(both)), "both_eyes"

    if not ALLOW_ONE_EYE_FALLBACK:
        raise RuntimeError(
            f"Only {np.sum(both)} valid both-eye frames; MIN_VALID_EYE_FRAMES={MIN_VALID_EYE_FRAMES}"
        )

    left_ok = np.isfinite(lx) & np.isfinite(ly) & np.isfinite(ll) & (ll >= EYE_LIK_THR)
    right_ok = np.isfinite(rx) & np.isfinite(ry) & np.isfinite(rl) & (rl >= EYE_LIK_THR)

    if np.sum(left_ok) < MIN_VALID_EYE_FRAMES or np.sum(right_ok) < MIN_VALID_EYE_FRAMES:
        raise RuntimeError(
            f"Insufficient eye frames: both={np.sum(both)}, left={np.sum(left_ok)}, right={np.sum(right_ok)}"
        )

    ex = 0.5 * (float(np.nanmedian(lx[left_ok])) + float(np.nanmedian(rx[right_ok])))
    ey = 0.5 * (float(np.nanmedian(ly[left_ok])) + float(np.nanmedian(ry[right_ok])))
    return ex, ey, int(min(np.sum(left_ok), np.sum(right_ok))), "one_eye_fallback"

def _choose_xy_keys(Z):
    for kx, ky in ANGLE_XY_KEYS_PREFERRED:
        if (kx in Z) and (ky in Z):
            return kx, ky
    raise KeyError(f"None of the preferred angle XY key pairs were found: {ANGLE_XY_KEYS_PREFERRED}")

def _compute_signed_tongue_angle_deg(x_geom, y_geom, eye_x, eye_y):
    x_geom = np.asarray(x_geom, float)
    y_geom = np.asarray(y_geom, float)

    ref_x = -float(eye_x)
    ref_y = -float(eye_y)
    ref_norm = np.hypot(ref_x, ref_y)
    if not np.isfinite(ref_norm) or ref_norm <= 0:
        raise RuntimeError("Reference vector eye->spout has invalid norm.")

    vx = x_geom - float(eye_x)
    vy = y_geom - float(eye_y)

    dot = ref_x * vx + ref_y * vy
    cross = ref_x * vy - ref_y * vx

    ang = ANGLE_SIGN_FLIP * np.degrees(np.arctan2(cross, dot))
    bad = (~np.isfinite(x_geom)) | (~np.isfinite(y_geom)) | (~np.isfinite(vx)) | (~np.isfinite(vy))
    ang[bad] = np.nan
    return ang

def _detect_up_to_n_tongue_licks_dydt(xw, yw, fps, detect_win_ms, t_ms, max_licks=20):
    lo_ms, hi_ms = map(float, detect_win_ms)
    i0 = int(np.searchsorted(t_ms, lo_ms, side="left"))
    i1 = int(np.searchsorted(t_ms, hi_ms, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms) - 1))
    i1 = max(0, min(i1, len(t_ms) - 1))
    if i1 < i0:
        i0, i1 = i1, i0

    xseg0 = np.asarray(xw[i0:i1+1], float)
    yseg0 = np.asarray(yw[i0:i1+1], float)
    if not np.any(np.isfinite(yseg0)):
        return []

    ys = yseg0.copy()
    if DO_SMOOTH_Y_FOR_DETECTION and (GAUSS_SIGMA_MS_DETECT_Y is not None) and (GAUSS_SIGMA_MS_DETECT_Y > 0):
        sigma_f = max(0.5, (GAUSS_SIGMA_MS_DETECT_Y / 1000.0) * float(fps))
        ys = _gaussian_smooth_nan(ys, sigma_f)

    dt_s = 1.0 / float(fps)
    dy = np.gradient(ys) / dt_s

    finite = np.isfinite(ys) & np.isfinite(dy) & np.isfinite(xseg0)
    rise_mask = finite & (dy > +float(SLOPE_THR_PX_PER_S))
    fall_mask = finite & (dy < -float(SLOPE_THR_PX_PER_S))

    rise_min_f = max(1, _ms_to_frames(RISE_MIN_MS, fps))
    fall_min_f = max(1, _ms_to_frames(FALL_MIN_MS, fps))
    pad_f = max(0, _ms_to_frames(PEAK_PAD_MS, fps))

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
        y_peak = float(yseg0[j_peak])

        end_idx = j_peak
        f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
        if f0 is not None:
            end_idx = max(end_idx, f1 - 1)

        if np.isfinite(y_peak) and (y_peak >= float(MIN_PEAK_Y_ABS)):
            i_peak_snip = i0 + j_peak
            peaks.append(dict(
                i_peak=int(i_peak_snip),
                t_ms=float(t_ms[i_peak_snip]),
                x_peak=float(xw[i_peak_snip]) if np.isfinite(xw[i_peak_snip]) else np.nan,
                y_peak=float(yw[i_peak_snip]) if np.isfinite(yw[i_peak_snip]) else np.nan,
                end_idx=int(i0 + end_idx),
            ))

        start = int(end_idx + 1)
        if start >= L:
            break

    return peaks

def _build_bouts_from_peaks(peaks, bout_max_ipi_ms=300.0, allow_single=True):
    if len(peaks) == 0:
        return []

    bouts = []
    current = [peaks[0]]
    for p_prev, p_now in zip(peaks[:-1], peaks[1:]):
        ipi = float(p_now["t_ms"] - p_prev["t_ms"])
        if np.isfinite(ipi) and (ipi <= float(bout_max_ipi_ms)):
            current.append(p_now)
        else:
            bouts.append(current)
            current = [p_now]
    bouts.append(current)

    out = []
    multi_rank = 0
    for i, b in enumerate(bouts):
        if (len(b) >= 2) or (allow_single and len(b) == 1):
            item = dict(bout_idx=i, peaks=b, n_peaks=len(b), bout_rank=i)
            if len(b) >= 2:
                item["multi_bout_rank"] = multi_rank
                multi_rank += 1
            else:
                item["multi_bout_rank"] = np.nan
            out.append(item)
    return out

def _bout_time_bounds_ms(bout):
    peaks = bout["peaks"]
    if len(peaks) >= 2:
        lead = 0.5 * (peaks[1]["t_ms"] - peaks[0]["t_ms"])
        tail = 0.5 * (peaks[-1]["t_ms"] - peaks[-2]["t_ms"])
        t0 = peaks[0]["t_ms"] - lead
        t1 = peaks[-1]["t_ms"] + tail
    else:
        t0 = peaks[0]["t_ms"] + float(SINGLE_BOUT_WIN_MS[0])
        t1 = peaks[0]["t_ms"] + float(SINGLE_BOUT_WIN_MS[1])
    return float(t0), float(t1)

def _time_bounds_to_indices(t_ms, t0, t1):
    i0 = int(np.searchsorted(t_ms, t0, side="left"))
    i1 = int(np.searchsorted(t_ms, t1, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms) - 1))
    i1 = max(0, min(i1, len(t_ms) - 1))
    if i1 < i0:
        i0, i1 = i1, i0
    return i0, i1

def _assign_phase_peak_to_peak_shifted(t_ms, bout):
    phase = np.full(len(t_ms), np.nan, dtype=float)
    peaks = bout["peaks"]
    if len(peaks) < 2:
        return phase

    for p0, p1 in zip(peaks[:-1], peaks[1:]):
        i0 = int(p0["i_peak"])
        i1 = int(p1["i_peak"])
        if i1 <= i0:
            continue
        u = (np.arange(i0, i1 + 1) - i0) / float(i1 - i0)
        phase_shift = np.mod(u - 0.5, 1.0)
        phase[i0:i1+1] = phase_shift
    return phase

def _session_save_dir(mouse):
    d = OUT_ROOT / mouse / f"{mouse}_tongue_kinematics" / "kinematics_figures" / f"{CENTER_MODE}" / SAVE_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d

def _robust_mean_sem(M):
    M = np.asarray(M, float)
    if M.ndim == 1:
        M = M[None, :]
    mu = np.nanmean(M, axis=0)
    n = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0, ddof=0)
    sem = np.full_like(mu, np.nan)
    good = n > 0
    sem[good] = sd[good] / np.sqrt(np.maximum(1, n[good]))
    return mu, sem, n

def _compute_percentile_ylim(arrays, pct=(1.0, 99.0), pad_frac=0.05, min_span=1.0):
    vals = []
    for a in arrays:
        if a is None:
            continue
        a = np.asarray(a, float).ravel()
        a = a[np.isfinite(a)]
        if a.size:
            vals.append(a)

    if len(vals) == 0:
        return None

    vals = np.concatenate(vals)
    lo, hi = np.nanpercentile(vals, pct)

    if not np.isfinite(lo) or not np.isfinite(hi):
        return None

    if hi <= lo:
        mid = 0.5 * (lo + hi)
        half = max(min_span / 2.0, abs(mid) * 0.05, 0.5)
        return (mid - half, mid + half)

    pad = max((hi - lo) * pad_frac, min_span * 0.02)
    return (lo - pad, hi + pad)

def _apply_shared_ylim_from_percentiles(axes, arrays, pct=(1.0, 99.0), pad_frac=0.05):
    if pct is None:
        return
    ylim = _compute_percentile_ylim(arrays, pct=pct, pad_frac=pad_frac)
    if ylim is None:
        return
    for ax in np.ravel(axes):
        ax.set_ylim(*ylim)

def _select_phase_rows(df_phase, mode):
    if df_phase.empty:
        return df_phase.copy()
    if mode == "all_multi":
        return df_phase.copy()
    if mode == "first_multi":
        return df_phase[df_phase["multi_bout_rank"] == 0].copy()
    raise ValueError("mode must be 'all_multi' or 'first_multi'")

def _pick_time_array_column(mode):
    if mode == "all_bouts":
        return "angle_allbouts_snip"
    if mode == "first_bout":
        return "angle_firstbout_snip"
    if mode == "first_multi":
        return "angle_firstmulti_snip"
    raise ValueError("TIME_SUMMARY_MODE must be 'all_bouts', 'first_bout', or 'first_multi'")

def _selected_phase_peak_count(df_bouts, mode, side=None, date=None):
    d = df_bouts.copy()
    d = d[pd.notna(d["peak_t_ms"])].copy()
    if side is not None:
        d = d[d["side"] == side].copy()
    if date is not None:
        d = d[d["date"] == date].copy()

    if mode == "first_multi":
        d = d[d["multi_bout_rank"] == 0].copy()
    elif mode == "all_multi":
        d = d[pd.notna(d["multi_bout_rank"])].copy()
    else:
        raise ValueError("mode must be 'all_multi' or 'first_multi'")

    if d.empty:
        return 0

    return int(len(d[["trial_index", "bout_idx", "peak_t_ms"]].drop_duplicates()))

def _plot_qc_trials(df_qc, mouse, date, side, detect_win_ms, outdir=None):
    dd = df_qc[df_qc["side"] == side].copy()
    if dd.empty:
        return

    trial_ids = sorted(dd["trial_index"].unique().tolist())[:int(VIEW_N_TRIALS_PER_SIDE)]
    if len(trial_ids) == 0:
        return

    fig, (ax_y, ax_a) = plt.subplots(2, 1, figsize=(12, max(4.5, 0.8 * len(trial_ids) + 2)), sharex=True)
    color = SIDE_COLORS.get(side, "k")

    det_lo, det_hi = map(float, detect_win_ms)
    ax_y.axvspan(det_lo, det_hi, color="0.25", alpha=QC_DETECT_ALPHA, zorder=0)
    ax_a.axvspan(det_lo, det_hi, color="0.25", alpha=QC_DETECT_ALPHA, zorder=0)
    ax_y.axvline(det_lo, color="0.4", ls="--", lw=1.0, alpha=0.8)
    ax_y.axvline(det_hi, color="0.4", ls="--", lw=1.0, alpha=0.8)
    ax_a.axvline(det_lo, color="0.4", ls="--", lw=1.0, alpha=0.8)
    ax_a.axvline(det_hi, color="0.4", ls="--", lw=1.0, alpha=0.8)

    ranges_y = []
    ranges_a = []
    for tid in trial_ids:
        rr = dd[dd["trial_index"] == tid].iloc[0]
        yw = np.asarray(rr["y_snip"], float)
        aw = np.asarray(rr["angle_snip"], float)
        if np.any(np.isfinite(yw)):
            ranges_y.append(np.nanpercentile(yw, 95) - np.nanpercentile(yw, 5))
        if np.any(np.isfinite(aw)):
            ranges_a.append(np.nanpercentile(aw, 95) - np.nanpercentile(aw, 5))
    dy_off = 1.2 * np.nanmedian(ranges_y) if len(ranges_y) else 50.0
    da_off = 1.2 * np.nanmedian(ranges_a) if len(ranges_a) else 30.0

    for j, tid in enumerate(trial_ids):
        sub = dd[dd["trial_index"] == tid].copy()
        rr = sub.iloc[0]
        t = np.asarray(rr["t_ms"], float)
        yw = np.asarray(rr["y_snip"], float)
        aw = np.asarray(rr["angle_snip"], float)
        yoff = j * dy_off
        aoff = j * da_off

        ax_y.plot(t, yw + yoff, color=color, lw=1.2, alpha=0.9, zorder=2)
        ax_a.plot(t, aw + aoff, color=color, lw=1.2, alpha=0.9, zorder=2)

        sub_bouts = (
            sub[pd.notna(sub["bout_t0_ms"]) & pd.notna(sub["bout_t1_ms"])]
            [["bout_idx", "bout_t0_ms", "bout_t1_ms"]]
            .drop_duplicates()
            .sort_values(["bout_t0_ms", "bout_t1_ms"])
        )
        for _, brow in sub_bouts.iterrows():
            ax_y.axvspan(float(brow["bout_t0_ms"]), float(brow["bout_t1_ms"]), color=color, alpha=QC_BOUT_ALPHA, zorder=1)
            ax_a.axvspan(float(brow["bout_t0_ms"]), float(brow["bout_t1_ms"]), color=color, alpha=QC_BOUT_ALPHA, zorder=1)

        sub_peaks = (
            sub[pd.notna(sub["peak_t_ms"])]
            [["peak_t_ms", "peak_y", "peak_angle_deg"]]
            .drop_duplicates()
            .sort_values("peak_t_ms")
        )
        if not sub_peaks.empty:
            ax_y.scatter(sub_peaks["peak_t_ms"], sub_peaks["peak_y"] + yoff, s=QC_PEAK_SIZE, color="k", zorder=5)
            ax_a.scatter(sub_peaks["peak_t_ms"], sub_peaks["peak_angle_deg"] + aoff, s=QC_PEAK_SIZE, color="k", zorder=5)

        ax_y.text(t[0], yoff, f"trial {tid}", fontsize=8, va="bottom", ha="left")
        ax_a.text(t[0], aoff, f"trial {tid}", fontsize=8, va="bottom", ha="left")

    ax_y.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax_a.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax_y.set_title(f"{mouse} {date} | {side} trials | QC: Y + detected bouts/peaks")
    ax_a.set_title(f"{mouse} {date} | {side} trials | QC: angle + detected bouts/peaks")
    ax_a.set_xlabel("Time from reward (ms)")
    ax_y.set_ylabel("Tongue Y (offset)")
    ax_a.set_ylabel("Angle (deg, offset)")
    ax_y.set_yticks([])
    ax_a.set_yticks([])
    ax_y.grid(True, alpha=0.15)
    ax_a.grid(True, alpha=0.15)
    plt.tight_layout()

    if SAVE_SINGLE_SESSION_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_{date}_{side}_anglePhase_QCtrials.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_SINGLE_SESSION_FIGS:
        plt.show()
    plt.close(fig)

def _plot_reward_aligned_angle(df_trials, mouse, date, outdir=None):
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    arr_col = _pick_time_array_column(TIME_SUMMARY_MODE)

    for side in VIEW_SIDES:
        dd = df_trials[df_trials["side"] == side].copy()
        if dd.empty:
            continue

        T = np.vstack(dd[arr_col].to_list())
        t = np.asarray(dd.iloc[0]["t_ms"], float)

        mu, sem, _ = _robust_mean_sem(T)
        n_trials_contrib = int(np.sum(np.any(np.isfinite(T), axis=1)))

        c = SIDE_COLORS.get(side, "k")
        ax.plot(t, mu, color=c, lw=2.0, label=f"{side} (trials: {n_trials_contrib})")
        ax.fill_between(t, mu - sem, mu + sem, color=c, alpha=0.18, lw=0)

    ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    ax.set_title(f"{mouse} {date} | reward-aligned tongue angle | mode={TIME_SUMMARY_MODE}")
    ax.set_xlabel("Time from reward (ms)")
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()

    if SAVE_SINGLE_SESSION_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_{date}_anglePhase_rewardAlignedAngle_{TIME_SUMMARY_MODE}.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_SINGLE_SESSION_FIGS:
        plt.show()
    plt.close(fig)

def _plot_first_peak_aligned_angle(df_trials, mouse, date, outdir=None):
    fig, ax = plt.subplots(figsize=(8.2, 4.2))

    for side in VIEW_SIDES:
        dd = df_trials[df_trials["side"] == side].copy()
        dd = dd[pd.notna(dd["first_peak_t_ms"])].copy()
        if dd.empty:
            continue

        T = np.vstack(dd["angle_firstpeak_snip"].to_list())
        t = np.asarray(dd.iloc[0]["t_firstpeak_align_ms"], float)

        mu, sem, _ = _robust_mean_sem(T)
        n_trials_contrib = int(np.sum(np.any(np.isfinite(T), axis=1)))

        c = SIDE_COLORS.get(side, "k")
        ax.plot(t, mu, color=c, lw=2.0, label=f"{side} (trials: {n_trials_contrib})")
        ax.fill_between(t, mu - sem, mu + sem, color=c, alpha=0.18, lw=0)

    ax.axvline(0, color="red", ls=":", lw=1.4, alpha=0.9)
    ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
    ax.set_title(f"{mouse} {date} | angle aligned to first detected lick peak")
    ax.set_xlabel("Time from first detected lick peak (ms)")
    ax.set_ylabel("Tongue angle (deg)")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()

    if SAVE_SINGLE_SESSION_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_{date}_anglePhase_firstPeakAlignedAngle.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_SINGLE_SESSION_FIGS:
        plt.show()
    plt.close(fig)

def _plot_phase_aligned_angle(df_phase, df_bouts, mouse, date, outdir=None):
    dfp = _select_phase_rows(df_phase, PHASE_SUMMARY_MODE)

    fig, ax = plt.subplots(figsize=(8.0, 4.2))

    if dfp.empty:
        ax.text(0.5, 0.5, f"No phase rows for mode={PHASE_SUMMARY_MODE}", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    else:
        for side in VIEW_SIDES:
            dd = dfp[dfp["side"] == side].copy()
            if dd.empty:
                continue

            grouped = dd.groupby("phase_bin_center", as_index=False).agg(
                angle_mean=("angle_deg", "mean"),
                angle_sem=("angle_deg", lambda x: np.nanstd(np.asarray(x, float), ddof=0) / np.sqrt(max(1, np.sum(np.isfinite(np.asarray(x, float)))))),
                n=("angle_deg", lambda x: np.sum(np.isfinite(np.asarray(x, float))))
            )

            x = grouped["phase_bin_center"].to_numpy(float)
            m = grouped["angle_mean"].to_numpy(float)
            s = grouped["angle_sem"].to_numpy(float)
            n = grouped["n"].to_numpy(float)

            m[n < MIN_PHASE_POINTS_PER_BIN_SINGLE] = np.nan
            s[n < MIN_PHASE_POINTS_PER_BIN_SINGLE] = np.nan

            if DO_SMOOTH_PHASE_CURVE and (PHASE_CURVE_SIGMA_BINS is not None) and (PHASE_CURVE_SIGMA_BINS > 0):
                m = _gaussian_smooth_nan(m, PHASE_CURVE_SIGMA_BINS, mode="wrap")
                s = _gaussian_smooth_nan(s, PHASE_CURVE_SIGMA_BINS, mode="wrap")

            lick_count = _selected_phase_peak_count(df_bouts, PHASE_SUMMARY_MODE, side=side, date=date)

            c = SIDE_COLORS.get(side, "k")
            ax.plot(x, m, color=c, lw=2.0, label=f"{side} (licks: {lick_count})")
            ax.fill_between(x, m - s, m + s, color=c, alpha=0.18, lw=0)

        ax.axhline(0, color="0.6", lw=1.0, alpha=0.8)
        ax.axvline(0.0, color="0.7", lw=1.0, ls="--")
        ax.axvline(0.5, color="0.7", lw=1.0, ls="--")
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_title(f"{mouse} {date} | phase-aligned tongue angle | mode={PHASE_SUMMARY_MODE}")
        ax.set_xlabel("Normalized lick phase (0 = between peaks, 0.5 = peak protrusion)")
        ax.set_ylabel("Tongue angle (deg)")
        ax.grid(True, alpha=0.2)
        ax.legend(frameon=False)

    plt.tight_layout()

    if SAVE_SINGLE_SESSION_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_{date}_anglePhase_phaseAlignedAngle_{PHASE_SUMMARY_MODE}.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_SINGLE_SESSION_FIGS:
        plt.show()
    plt.close(fig)

def _plot_xy_colored_by_phase(df_phase, mouse, date, outdir=None):
    dfp = _select_phase_rows(df_phase, XY_SUMMARY_MODE)

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), sharex=True, sharey=True)
    norm = Normalize(vmin=0.0, vmax=1.0)
    fig.subplots_adjust(right=0.86, wspace=0.08)

    any_points = False
    sc = None

    x_all = pd.to_numeric(dfp["x_geom"], errors="coerce").to_numpy(float) if not dfp.empty else np.array([])
    if x_all.size and np.any(np.isfinite(x_all)):
        xmax = float(np.nanmax(np.abs(x_all))) * 1.05
        xmax = max(1.0, xmax)
    else:
        xmax = 50.0

    for ax, side in zip(axes, VIEW_SIDES):
        dd = dfp[dfp["side"] == side].copy()
        if dd.empty:
            ax.text(0.5, 0.5, "No multi-lick bouts", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(f"{side} trials")
            ax.grid(True, alpha=0.15)
            ax.set_xlim(-xmax, xmax)
            continue

        any_points = True
        sc = ax.scatter(
            dd["x_geom"], dd["y_geom"],
            c=dd["phase"], cmap="twilight", norm=norm,
            s=8, alpha=0.65, edgecolors="none"
        )

        ax.set_title(f"{side} trials")
        ax.set_xlabel("Tongue X (spout-centered px)")
        ax.grid(True, alpha=0.15)
        ax.set_xlim(-xmax, xmax)

    axes[0].set_ylabel("Tongue Y (geom source)")
    fig.suptitle(f"{mouse} {date} | XY trajectory colored by phase | mode={XY_SUMMARY_MODE}", y=0.98)

    for ax in axes:
        if not ax.yaxis_inverted():
            ax.invert_yaxis()

    if any_points and sc is not None:
        cax = fig.add_axes([0.875, 0.16, 0.015, 0.68])
        cbar = fig.colorbar(sc, cax=cax)
        cbar.set_label("Normalized phase")

    print("Y inverted:", axes[0].yaxis_inverted(), axes[1].yaxis_inverted())

    if SAVE_SINGLE_SESSION_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_{date}_anglePhase_XYphase_{XY_SUMMARY_MODE}.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")

    if SHOW_SINGLE_SESSION_FIGS:
        plt.show()
    plt.close(fig)

# ---------- overlay summary helpers ----------

def _session_time_summary(df_trials_s, arr_col):
    if df_trials_s.empty:
        return None, None, 0

    T = np.vstack(df_trials_s[arr_col].to_list())
    t = np.asarray(df_trials_s.iloc[0]["t_ms"], float)
    mu, _, _ = _robust_mean_sem(T)
    n_trials_contrib = int(np.sum(np.any(np.isfinite(T), axis=1)))

    if n_trials_contrib < int(MIN_TIME_TRIALS_PER_SESSION):
        return None, None, n_trials_contrib

    return t, mu, n_trials_contrib

def _session_firstpeak_summary(df_trials_s):
    if df_trials_s.empty:
        return None, None, 0

    d = df_trials_s[pd.notna(df_trials_s["first_peak_t_ms"])].copy()
    if d.empty:
        return None, None, 0

    T = np.vstack(d["angle_firstpeak_snip"].to_list())
    t = np.asarray(d.iloc[0]["t_firstpeak_align_ms"], float)
    mu, _, _ = _robust_mean_sem(T)
    n_trials_contrib = int(np.sum(np.any(np.isfinite(T), axis=1)))

    if n_trials_contrib < int(MIN_FIRSTPEAK_TRIALS_PER_SESSION):
        return None, None, n_trials_contrib

    return t, mu, n_trials_contrib

def _session_phase_summary(df_phase_s, df_bouts_s, mode):
    dfp = _select_phase_rows(df_phase_s, mode)
    if dfp.empty:
        return None, None, 0

    lick_count = _selected_phase_peak_count(df_bouts_s, mode)
    n_phase_trials = int(dfp["trial_index"].nunique())

    if (lick_count < int(MIN_PHASE_LICKS_PER_SESSION)) or (n_phase_trials < int(MIN_PHASE_TRIALS_PER_SESSION)):
        return None, None, lick_count

    full_bins = np.arange(N_PHASE_BINS, dtype=int)
    phase_edges = np.linspace(0, 1, int(N_PHASE_BINS) + 1)
    full_x = 0.5 * (phase_edges[:-1] + phase_edges[1:])

    grouped = dfp.groupby("phase_bin", as_index=False).agg(
        angle_mean=("angle_deg", "mean"),
        n=("angle_deg", lambda x: np.sum(np.isfinite(np.asarray(x, float))))
    )

    grouped = (
        pd.DataFrame({"phase_bin": full_bins})
        .merge(grouped, on="phase_bin", how="left")
        .sort_values("phase_bin")
    )

    x = full_x
    m = grouped["angle_mean"].to_numpy(float)
    n = grouped["n"].fillna(0).to_numpy(float)

    m[n < MIN_PHASE_POINTS_PER_BIN_OVERLAY] = np.nan

    if DO_SMOOTH_PHASE_CURVE and (PHASE_CURVE_SIGMA_BINS is not None) and (PHASE_CURVE_SIGMA_BINS > 0):
        m = _gaussian_smooth_nan(m, PHASE_CURVE_SIGMA_BINS, mode="wrap")

    return x, m, lick_count

def _plot_overlay_grid_all_sessions(mouse, df_trials_m, df_phase_m, df_bouts_m, mouse_meta, outdir=None):
    rel_days = sorted(mouse_meta["rel_day"].dropna().unique().tolist())
    pos_days = [d for d in rel_days if d > 0]
    max_post_day = max(pos_days) if len(pos_days) else None

    fig, axes = plt.subplots(3, 2, figsize=(12.5, 10.6), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.88, top=0.90, bottom=0.08, hspace=0.50, wspace=0.10)

    row_titles = [
        f"Reward-aligned angle | mode={TIME_SUMMARY_MODE}",
        "Angle aligned to first detected lick peak",
        f"Phase-aligned angle | mode={PHASE_SUMMARY_MODE}",
    ]

    arr_col = _pick_time_array_column(TIME_SUMMARY_MODE)
    all_y_for_limits = []

    for col, side in enumerate(VIEW_SIDES):
        df_trials_side = df_trials_m[df_trials_m["side"] == side].copy()
        df_phase_side = df_phase_m[df_phase_m["side"] == side].copy()
        df_bouts_side = df_bouts_m[df_bouts_m["side"] == side].copy()

        dates_side = sorted(df_trials_side["date"].dropna().astype(str).unique().tolist())

        ax = axes[0, col]
        for date in dates_side:
            dd = df_trials_side[df_trials_side["date"] == date].copy()
            meta_row = mouse_meta[mouse_meta["date"] == date].iloc[0]
            rel_day = int(meta_row["rel_day"])
            c = _post_color(rel_day, max_post_day)
            t, mu, _ = _session_time_summary(dd, arr_col)
            if t is None:
                continue
            ax.plot(t, mu, color=c, lw=OVERLAY_LINE_LW, alpha=OVERLAY_LINE_ALPHA)
            all_y_for_limits.append(mu)

        ax1 = axes[1, col]
        for date in dates_side:
            dd = df_trials_side[df_trials_side["date"] == date].copy()
            meta_row = mouse_meta[mouse_meta["date"] == date].iloc[0]
            rel_day = int(meta_row["rel_day"])
            c = _post_color(rel_day, max_post_day)
            t, mu, _ = _session_firstpeak_summary(dd)
            if t is None:
                continue
            ax1.plot(t, mu, color=c, lw=OVERLAY_LINE_LW, alpha=OVERLAY_LINE_ALPHA)
            all_y_for_limits.append(mu)

        ax2 = axes[2, col]
        dates_phase = sorted(df_phase_side["date"].dropna().astype(str).unique().tolist())
        for date in dates_phase:
            ddp = df_phase_side[df_phase_side["date"] == date].copy()
            ddb = df_bouts_side[df_bouts_side["date"] == date].copy()
            if ddp.empty:
                continue
            meta_row = mouse_meta[mouse_meta["date"] == date].iloc[0]
            rel_day = int(meta_row["rel_day"])
            c = _post_color(rel_day, max_post_day)
            x, m, _ = _session_phase_summary(ddp, ddb, PHASE_SUMMARY_MODE)
            if x is None:
                continue
            ax2.plot(x, m, color=c, lw=OVERLAY_LINE_LW, alpha=OVERLAY_LINE_ALPHA)
            all_y_for_limits.append(m)

        axes[0, col].set_title(f"{side} trials")

    for r in range(3):
        axes[r, 0].set_ylabel("Tongue angle (deg)")
        for c in range(2):
            axes[r, c].grid(True, alpha=0.20)
            axes[r, c].axhline(0, color="0.6", lw=1.0, alpha=0.8)

    axes[0, 0].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[0, 1].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[1, 0].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[1, 1].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[2, 0].axvline(0.0, color="0.7", lw=1.0, ls="--")
    axes[2, 0].axvline(0.5, color="0.7", lw=1.0, ls="--")
    axes[2, 1].axvline(0.0, color="0.7", lw=1.0, ls="--")
    axes[2, 1].axvline(0.5, color="0.7", lw=1.0, ls="--")
    axes[2, 0].set_xlim(0, 1)
    axes[2, 1].set_xlim(0, 1)

    axes[0, 0].set_xlabel("Time from reward (ms)")
    axes[0, 1].set_xlabel("Time from reward (ms)")
    axes[1, 0].set_xlabel("Time from first detected lick peak (ms)")
    axes[1, 1].set_xlabel("Time from first detected lick peak (ms)")
    axes[2, 0].set_xlabel("Normalized lick phase")
    axes[2, 1].set_xlabel("Normalized lick phase")

    for r in range(3):
        pos = axes[r, 0].get_position()
        y = pos.y1 + 0.015
        fig.text(0.07, y, row_titles[r], ha="left", va="bottom", fontsize=12)

    _apply_shared_ylim_from_percentiles(
        axes,
        all_y_for_limits,
        pct=OVERLAY_Y_PCT,
        pad_frac=OVERLAY_Y_PAD_FRAC,
    )

    fig.suptitle(f"{mouse} | all-session overlays | pre-stroke=grey, post-stroke=plasma", y=0.99)

    if max_post_day is not None:
        cax = fig.add_axes([0.90, 0.17, 0.015, 0.68])
        sm = plt.cm.ScalarMappable(cmap=POST_CMAP, norm=Normalize(vmin=1, vmax=max_post_day))
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label("Post-stroke day")

    if SAVE_OVERLAY_ALLSESS_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_anglePhase_overlay_allSessions.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_OVERLAY_ALLSESS_FIGS:
        plt.show()
    plt.close(fig)

def _plot_overlay_grid_binned(mouse, df_trials_m, df_phase_m, df_bouts_m, mouse_meta, bin_days, outdir=None):
    meta = mouse_meta.copy()
    meta["bin_start"] = np.nan
    meta["bin_end"] = np.nan
    meta["bin_center"] = np.nan
    meta["bin_label"] = None

    for i, row in meta.iterrows():
        bs, be, bc, bl = _bin_rel_day(int(row["rel_day"]), int(bin_days))
        meta.loc[i, "bin_start"] = bs
        meta.loc[i, "bin_end"] = be
        meta.loc[i, "bin_center"] = bc
        meta.loc[i, "bin_label"] = bl

    centers = sorted(meta["bin_center"].dropna().unique().tolist())
    pos_centers = [c for c in centers if c > 0]
    max_post_center = max(pos_centers) if len(pos_centers) else None

    fig, axes = plt.subplots(3, 2, figsize=(12.5, 10.6), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.88, top=0.90, bottom=0.08, hspace=0.50, wspace=0.10)

    row_titles = [
        f"Binned reward-aligned angle | mode={TIME_SUMMARY_MODE}",
        "Binned angle aligned to first detected lick peak",
        f"Binned phase-aligned angle | mode={PHASE_SUMMARY_MODE}",
    ]
    arr_col = _pick_time_array_column(TIME_SUMMARY_MODE)
    all_y_for_limits = []

    for col, side in enumerate(VIEW_SIDES):
        df_trials_side = df_trials_m[df_trials_m["side"] == side].copy()
        df_phase_side = df_phase_m[df_phase_m["side"] == side].copy()
        df_bouts_side = df_bouts_m[df_bouts_m["side"] == side].copy()

        ax = axes[0, col]
        for bc in centers:
            dates_bin = meta.loc[meta["bin_center"] == bc, "date"].astype(str).tolist()
            session_curves = []
            t_ref = None
            for date in dates_bin:
                dd = df_trials_side[df_trials_side["date"] == date].copy()
                t, mu, _ = _session_time_summary(dd, arr_col)
                if t is None:
                    continue
                t_ref = t
                session_curves.append(mu)
            if len(session_curves) == 0:
                continue
            M = np.vstack(session_curves)
            mu, sem, _ = _robust_mean_sem(M)
            c = _post_color_from_center(bc, max_post_center)
            ax.plot(t_ref, mu, color=c, lw=2.0)
            ax.fill_between(t_ref, mu - sem, mu + sem, color=c, alpha=BIN_FILL_ALPHA, lw=0)
            all_y_for_limits.append(mu)

        ax1 = axes[1, col]
        for bc in centers:
            dates_bin = meta.loc[meta["bin_center"] == bc, "date"].astype(str).tolist()
            session_curves = []
            t_ref = None
            for date in dates_bin:
                dd = df_trials_side[df_trials_side["date"] == date].copy()
                t, mu, _ = _session_firstpeak_summary(dd)
                if t is None:
                    continue
                t_ref = t
                session_curves.append(mu)
            if len(session_curves) == 0:
                continue
            M = np.vstack(session_curves)
            mu, sem, _ = _robust_mean_sem(M)
            c = _post_color_from_center(bc, max_post_center)
            ax1.plot(t_ref, mu, color=c, lw=2.0)
            ax1.fill_between(t_ref, mu - sem, mu + sem, color=c, alpha=BIN_FILL_ALPHA, lw=0)
            all_y_for_limits.append(mu)

        ax2 = axes[2, col]
        for bc in centers:
            dates_bin = meta.loc[meta["bin_center"] == bc, "date"].astype(str).tolist()
            session_curves = []
            x_ref = None
            for date in dates_bin:
                ddp = df_phase_side[df_phase_side["date"] == date].copy()
                ddb = df_bouts_side[df_bouts_side["date"] == date].copy()
                x, m, _ = _session_phase_summary(ddp, ddb, PHASE_SUMMARY_MODE)
                if x is None:
                    continue
                x_ref = x
                session_curves.append(m)
            if len(session_curves) == 0:
                continue
            M = np.vstack(session_curves)
            mu, sem, _ = _robust_mean_sem(M)
            c = _post_color_from_center(bc, max_post_center)
            ax2.plot(x_ref, mu, color=c, lw=2.0)
            ax2.fill_between(x_ref, mu - sem, mu + sem, color=c, alpha=BIN_FILL_ALPHA, lw=0)
            all_y_for_limits.append(mu)

        axes[0, col].set_title(f"{side} trials")

    for r in range(3):
        axes[r, 0].set_ylabel("Tongue angle (deg)")
        for c in range(2):
            axes[r, c].grid(True, alpha=0.20)
            axes[r, c].axhline(0, color="0.6", lw=1.0, alpha=0.8)

    axes[0, 0].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[0, 1].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[1, 0].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[1, 1].axvline(0, color="red", ls=":", lw=1.2, alpha=0.9)
    axes[2, 0].axvline(0.0, color="0.7", lw=1.0, ls="--")
    axes[2, 0].axvline(0.5, color="0.7", lw=1.0, ls="--")
    axes[2, 1].axvline(0.0, color="0.7", lw=1.0, ls="--")
    axes[2, 1].axvline(0.5, color="0.7", lw=1.0, ls="--")
    axes[2, 0].set_xlim(0, 1)
    axes[2, 1].set_xlim(0, 1)

    axes[0, 0].set_xlabel("Time from reward (ms)")
    axes[0, 1].set_xlabel("Time from reward (ms)")
    axes[1, 0].set_xlabel("Time from first detected lick peak (ms)")
    axes[1, 1].set_xlabel("Time from first detected lick peak (ms)")
    axes[2, 0].set_xlabel("Normalized lick phase")
    axes[2, 1].set_xlabel("Normalized lick phase")

    for r in range(3):
        pos = axes[r, 0].get_position()
        y = pos.y1 + 0.02
        fig.text(0.07, y, row_titles[r], ha="left", va="bottom", fontsize=12)

    _apply_shared_ylim_from_percentiles(
        axes,
        all_y_for_limits,
        pct=OVERLAY_Y_PCT,
        pad_frac=OVERLAY_Y_PAD_FRAC,
    )

    fig.suptitle(f"{mouse} | binned overlays (bin_days={bin_days}) | pre-stroke=grey, post-stroke=plasma", y=0.99)

    if max_post_center is not None:
        cax = fig.add_axes([0.90, 0.17, 0.015, 0.68])
        sm = plt.cm.ScalarMappable(cmap=POST_CMAP, norm=Normalize(vmin=1, vmax=max_post_center))
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label("Post-stroke bin center day")

    if SAVE_OVERLAY_BINNED_FIGS and (outdir is not None):
        p = outdir / f"{mouse}_anglePhase_overlay_binned_bin{bin_days}d.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")
    if SHOW_OVERLAY_BINNED_FIGS:
        plt.show()
    plt.close(fig)


# ===================== MAIN PROCESSOR =====================

def process_one_session(mouse, date, cam, plot_win_ms, detect_win_ms):
    avail, _ = _list_session_npzs(mouse, cam)
    if date not in avail:
        raise FileNotFoundError(f"No processed tongue interp NPZ found for {mouse} {date} {cam}")
    p_npz = avail[date]
    Z = np.load(p_npz, allow_pickle=True)

    fps = float(Z["fps"]) if "fps" in Z else 250.0
    n_frames = int(Z["n_frames"]) if "n_frames" in Z else len(Z[PHASE_Y_KEY])

    if PHASE_Y_KEY not in Z:
        raise KeyError(f"{PHASE_Y_KEY} not found in {p_npz}")
    y_phase_full = np.asarray(Z[PHASE_Y_KEY], float)

    kx, ky = _choose_xy_keys(Z)
    x_geom_full = np.asarray(Z[kx], float)
    y_geom_full = np.asarray(Z[ky], float)

    n_frames = min(n_frames, len(y_phase_full), len(x_geom_full), len(y_geom_full))
    y_phase_full = y_phase_full[:n_frames]
    x_geom_full = x_geom_full[:n_frames]
    y_geom_full = y_geom_full[:n_frames]

    df_eye, eye_cache_files = _load_eye_cache_df(mouse, date, cam)
    eye_x, eye_y, n_eye_used, eye_mode = _estimate_session_eye_midpoint(df_eye)
    angle_raw_full = _compute_signed_tongue_angle_deg(x_geom_full, y_geom_full, eye_x, eye_y)

    if DO_SMOOTH_ANGLE and (GAUSS_SIGMA_MS_ANGLE is not None) and (GAUSS_SIGMA_MS_ANGLE > 0):
        sigma_f_ang = max(0.5, (GAUSS_SIGMA_MS_ANGLE / 1000.0) * float(fps))
        angle_full = _gaussian_smooth_nan(angle_raw_full, sigma_f_ang, mode="nearest")
    else:
        angle_full = angle_raw_full.copy()

    centers_by_side = {}
    if "fr_reward_mouseL" in Z:
        c = np.asarray(Z["fr_reward_mouseL"]).astype(int)
        c = c[(c >= 0) & (c < n_frames)]
        centers_by_side["L"] = c
    if "fr_reward_mouseR" in Z:
        c = np.asarray(Z["fr_reward_mouseR"]).astype(int)
        c = c[(c >= 0) & (c < n_frames)]
        centers_by_side["R"] = c
    if not centers_by_side:
        raise KeyError(f"No fr_reward_mouseL / fr_reward_mouseR found in {p_npz}")

    pre_f = max(0, _ms_to_frames(-float(plot_win_ms[0]), fps)) if float(plot_win_ms[0]) < 0 else 0
    post_f = max(0, _ms_to_frames(float(plot_win_ms[1]), fps))
    t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps)).astype(float)

    peak_pre_f = max(0, _ms_to_frames(-float(FIRST_PEAK_ALIGN_WIN_MS[0]), fps)) if float(FIRST_PEAK_ALIGN_WIN_MS[0]) < 0 else 0
    peak_post_f = max(0, _ms_to_frames(float(FIRST_PEAK_ALIGN_WIN_MS[1]), fps))
    t_firstpeak_align_ms = (np.arange(-peak_pre_f, peak_post_f + 1) * (1000.0 / fps)).astype(float)

    phase_bin_edges = np.linspace(0, 1, int(N_PHASE_BINS) + 1)
    phase_bin_centers = 0.5 * (phase_bin_edges[:-1] + phase_bin_edges[1:])

    rows_trial = []
    rows_bout = []
    rows_phase = []

    for side, centers in centers_by_side.items():
        for trial_index, cfr in enumerate(centers):
            y_snip = _snippet(y_phase_full, int(cfr), pre_f, post_f)
            xgeom_snip = _snippet(x_geom_full, int(cfr), pre_f, post_f)
            ygeom_snip = _snippet(y_geom_full, int(cfr), pre_f, post_f)
            angle_snip = _snippet(angle_full, int(cfr), pre_f, post_f)

            peaks = _detect_up_to_n_tongue_licks_dydt(
                xgeom_snip, y_snip, fps, detect_win_ms, t_ms, max_licks=MAX_LICKS_PER_TRIAL
            )
            bouts = _build_bouts_from_peaks(peaks, bout_max_ipi_ms=BOUT_MAX_IPI_MS, allow_single=ALLOW_SINGLE_LICK_BOUTS)

            angle_allbouts = np.full_like(angle_snip, np.nan, dtype=float)
            angle_firstbout = np.full_like(angle_snip, np.nan, dtype=float)
            angle_firstmulti = np.full_like(angle_snip, np.nan, dtype=float)

            if len(peaks) >= 1:
                first_peak_local_idx = int(peaks[0]["i_peak"])
                first_peak_t_ms = float(peaks[0]["t_ms"])
                angle_firstpeak = _snippet(angle_snip, first_peak_local_idx, peak_pre_f, peak_post_f)
            else:
                first_peak_t_ms = np.nan
                angle_firstpeak = np.full_like(t_firstpeak_align_ms, np.nan, dtype=float)

            if len(bouts) == 0:
                rows_trial.append(dict(
                    mouse=mouse, date=date, side=side, trial_index=int(trial_index),
                    n_peaks=0, n_bouts=0, n_multi_lick_bouts=0,
                    first_peak_t_ms=np.nan,
                    t_firstpeak_align_ms=t_firstpeak_align_ms.copy(),
                    angle_firstpeak_snip=angle_firstpeak.copy(),
                    t_ms=t_ms.copy(), y_snip=y_snip.copy(), angle_snip=angle_snip.copy(),
                    angle_allbouts_snip=angle_allbouts.copy(),
                    angle_firstbout_snip=angle_firstbout.copy(),
                    angle_firstmulti_snip=angle_firstmulti.copy(),
                ))
                continue

            first_bout_done = False
            first_multi_done = False
            multi_bout_count = 0

            for bout in bouts:
                peaks_b = bout["peaks"]

                if bout["n_peaks"] >= 2:
                    multi_bout_count += 1

                bout_t0_ms, bout_t1_ms = _bout_time_bounds_ms(bout)
                ib0, ib1 = _time_bounds_to_indices(t_ms, bout_t0_ms, bout_t1_ms)

                angle_allbouts[ib0:ib1+1] = angle_snip[ib0:ib1+1]

                if not first_bout_done:
                    angle_firstbout[ib0:ib1+1] = angle_snip[ib0:ib1+1]
                    first_bout_done = True

                if (bout["n_peaks"] >= 2) and (not first_multi_done):
                    angle_firstmulti[ib0:ib1+1] = angle_snip[ib0:ib1+1]
                    first_multi_done = True

                phase = _assign_phase_peak_to_peak_shifted(t_ms, bout)

                rows_bout.append(dict(
                    mouse=mouse, date=date, side=side, trial_index=int(trial_index),
                    bout_idx=int(bout["bout_idx"]),
                    bout_rank=int(bout["bout_rank"]),
                    multi_bout_rank=float(bout["multi_bout_rank"]) if pd.notna(bout["multi_bout_rank"]) else np.nan,
                    n_peaks=int(bout["n_peaks"]),
                    bout_t0_ms=float(bout_t0_ms), bout_t1_ms=float(bout_t1_ms),
                    peak_t0_ms=float(peaks_b[0]["t_ms"]) if len(peaks_b) >= 1 else np.nan,
                    peak_t1_ms=float(peaks_b[1]["t_ms"]) if len(peaks_b) >= 2 else np.nan,
                    peak_y0=float(peaks_b[0]["y_peak"]) if len(peaks_b) >= 1 else np.nan,
                    peak_angle0=float(angle_snip[int(peaks_b[0]["i_peak"])]) if len(peaks_b) >= 1 and np.isfinite(angle_snip[int(peaks_b[0]["i_peak"])]) else np.nan,
                    peak_y1=float(peaks_b[1]["y_peak"]) if len(peaks_b) >= 2 else np.nan,
                    peak_angle1=float(angle_snip[int(peaks_b[1]["i_peak"])]) if len(peaks_b) >= 2 and np.isfinite(angle_snip[int(peaks_b[1]["i_peak"])]) else np.nan,
                    peak_t_ms=np.nan, peak_y=np.nan, peak_x=np.nan, peak_angle_deg=np.nan,
                ))

                for pk in peaks_b:
                    rows_bout.append(dict(
                        mouse=mouse, date=date, side=side, trial_index=int(trial_index),
                        bout_idx=int(bout["bout_idx"]),
                        bout_rank=int(bout["bout_rank"]),
                        multi_bout_rank=float(bout["multi_bout_rank"]) if pd.notna(bout["multi_bout_rank"]) else np.nan,
                        n_peaks=int(bout["n_peaks"]),
                        bout_t0_ms=float(bout_t0_ms), bout_t1_ms=float(bout_t1_ms),
                        peak_t0_ms=np.nan, peak_t1_ms=np.nan,
                        peak_y0=np.nan, peak_angle0=np.nan, peak_y1=np.nan, peak_angle1=np.nan,
                        peak_t_ms=float(pk["t_ms"]),
                        peak_y=float(pk["y_peak"]),
                        peak_x=float(pk["x_peak"]),
                        peak_angle_deg=float(angle_snip[int(pk["i_peak"])]) if np.isfinite(angle_snip[int(pk["i_peak"])]) else np.nan,
                    ))

                if bout["n_peaks"] >= 2:
                    mask = np.isfinite(phase) & np.isfinite(angle_snip) & np.isfinite(xgeom_snip) & np.isfinite(ygeom_snip)
                    idxs = np.where(mask)[0]
                    for ii in idxs:
                        ph = float(phase[ii])
                        bin_idx = int(np.clip(np.searchsorted(phase_bin_edges, ph, side="right") - 1, 0, len(phase_bin_centers) - 1))
                        rows_phase.append(dict(
                            mouse=mouse, date=date, side=side, trial_index=int(trial_index),
                            bout_idx=int(bout["bout_idx"]),
                            bout_rank=int(bout["bout_rank"]),
                            multi_bout_rank=int(bout["multi_bout_rank"]) if pd.notna(bout["multi_bout_rank"]) else np.nan,
                            t_ms=float(t_ms[ii]),
                            phase=ph,
                            phase_bin=int(bin_idx),
                            phase_bin_center=float(phase_bin_centers[bin_idx]),
                            angle_deg=float(angle_snip[ii]),
                            x_geom=float(xgeom_snip[ii]),
                            y_geom=float(ygeom_snip[ii]),
                        ))

            rows_trial.append(dict(
                mouse=mouse, date=date, side=side, trial_index=int(trial_index),
                n_peaks=int(len(peaks)), n_bouts=int(len(bouts)), n_multi_lick_bouts=int(multi_bout_count),
                first_peak_t_ms=first_peak_t_ms,
                t_firstpeak_align_ms=t_firstpeak_align_ms.copy(),
                angle_firstpeak_snip=angle_firstpeak.copy(),
                t_ms=t_ms.copy(), y_snip=y_snip.copy(), angle_snip=angle_snip.copy(),
                angle_allbouts_snip=angle_allbouts.copy(),
                angle_firstbout_snip=angle_firstbout.copy(),
                angle_firstmulti_snip=angle_firstmulti.copy(),
            ))

    df_trials = pd.DataFrame(rows_trial)
    df_bouts = pd.DataFrame(rows_bout)
    df_phase = pd.DataFrame(rows_phase)

    meta = dict(
        mouse=mouse, date=date, cam=cam, npz_path=str(p_npz),
        angle_xy_keys=(kx, ky),
        eye_x=float(eye_x), eye_y=float(eye_y),
        n_eye_used=int(n_eye_used), eye_mode=str(eye_mode),
        eye_cache_files=eye_cache_files,
        fps=float(fps),
        plot_win_ms=tuple(plot_win_ms),
        detect_win_ms=tuple(detect_win_ms),
        angle_smoothing_sigma_ms=float(GAUSS_SIGMA_MS_ANGLE) if DO_SMOOTH_ANGLE else np.nan,
        phase_summary_mode=str(PHASE_SUMMARY_MODE),
        time_summary_mode=str(TIME_SUMMARY_MODE),
        xy_summary_mode=str(XY_SUMMARY_MODE),
    )
    return df_trials, df_bouts, df_phase, meta


# ===================== RUN =====================

session_jobs = []

if RUN_MODE == "single":
    if TEST_MOUSE not in MOUSE_SPECS:
        raise KeyError(f"{TEST_MOUSE} not found in MOUSE_SPECS")
    spec = MOUSE_SPECS[TEST_MOUSE]
    plot_win_ms = TEST_PLOT_WIN_MS if TEST_PLOT_WIN_MS is not None else spec["plot_win_ms"]
    detect_win_ms = TEST_DETECT_WIN_MS if TEST_DETECT_WIN_MS is not None else spec["detect_win_ms"]
    session_jobs = [(TEST_MOUSE, TEST_DATE, CAM, plot_win_ms, detect_win_ms, spec["d0"], spec["bin_days"])]

elif RUN_MODE == "batch":
    mice_run = list(MOUSE_SPECS.keys()) if MICE_TO_RUN is None else list(MICE_TO_RUN)
    for mouse in mice_run:
        spec = MOUSE_SPECS[mouse]
        dates = _pick_session_dates(mouse, spec)
        avail, _ = _list_session_npzs(mouse, CAM)
        for d in dates:
            if d in avail:
                session_jobs.append((mouse, d, CAM, spec["plot_win_ms"], spec["detect_win_ms"], spec["d0"], spec["bin_days"]))
else:
    raise ValueError("RUN_MODE must be 'single' or 'batch'")

all_trials = []
all_bouts = []
all_phase = []
all_meta = []

for mouse, date, cam, plot_win_ms, detect_win_ms, d0, bin_days in session_jobs:
    print(f"\n=== Processing {mouse} {date} {cam} ===")
    try:
        df_trials, df_bouts, df_phase, meta = process_one_session(mouse, date, cam, plot_win_ms, detect_win_ms)
        meta["rel_day"] = _rel_day_from_d0(date, d0)
        meta["d0"] = d0
        meta["bin_days"] = int(bin_days)

        all_trials.append(df_trials)
        all_bouts.append(df_bouts)
        all_phase.append(df_phase)
        all_meta.append(meta)

        print(f"[info] eye midpoint mode={meta['eye_mode']} | n_eye_used={meta['n_eye_used']} | eye=({meta['eye_x']:.2f}, {meta['eye_y']:.2f}) | rel_day={meta['rel_day']}")
        print(f"[info] trials={len(df_trials)} | bouts rows={len(df_bouts)} | phase rows={len(df_phase)}")

        outdir = _session_save_dir(mouse)

        if SHOW_SINGLE_SESSION_FIGS or SAVE_SINGLE_SESSION_FIGS:
            df_qc = df_bouts.merge(
                df_trials[["mouse", "date", "side", "trial_index", "t_ms", "y_snip", "angle_snip",
                           "angle_allbouts_snip", "angle_firstbout_snip", "angle_firstmulti_snip",
                           "first_peak_t_ms", "t_firstpeak_align_ms", "angle_firstpeak_snip"]],
                on=["mouse", "date", "side", "trial_index"], how="left"
            )

            for side in VIEW_SIDES:
                _plot_qc_trials(df_qc, mouse, date, side, detect_win_ms=detect_win_ms, outdir=outdir)

            _plot_reward_aligned_angle(df_trials, mouse, date, outdir=outdir)
            _plot_first_peak_aligned_angle(df_trials, mouse, date, outdir=outdir)
            _plot_phase_aligned_angle(df_phase, df_bouts, mouse, date, outdir=outdir)
            _plot_xy_colored_by_phase(df_phase, mouse, date, outdir=outdir)

        if SAVE_TABLES:
            pd.DataFrame([meta]).to_csv(outdir / f"{mouse}_{date}_{cam}_anglePhase_meta.csv", index=False)
            df_trials.drop(columns=["t_ms", "y_snip", "angle_snip",
                                    "angle_allbouts_snip", "angle_firstbout_snip", "angle_firstmulti_snip",
                                    "t_firstpeak_align_ms", "angle_firstpeak_snip"],
                           errors="ignore").to_csv(
                outdir / f"{mouse}_{date}_{cam}_anglePhase_trials.csv", index=False
            )
            df_bouts.to_csv(outdir / f"{mouse}_{date}_{cam}_anglePhase_bouts.csv", index=False)
            df_phase.to_csv(outdir / f"{mouse}_{date}_{cam}_anglePhase_phaseRows.csv", index=False)
            print(f"[save] tables -> {outdir}")

    except Exception as e:
        print(f"[FAIL] {mouse} {date} {cam}: {repr(e)}")

if len(all_trials):
    df_trials_all = pd.concat(all_trials, ignore_index=True)
    print(f"\n[ok] total trial rows: {len(df_trials_all)}")
else:
    df_trials_all = pd.DataFrame()

if len(all_bouts):
    df_bouts_all = pd.concat(all_bouts, ignore_index=True)
    print(f"[ok] total bout rows: {len(df_bouts_all)}")
else:
    df_bouts_all = pd.DataFrame()

if len(all_phase):
    df_phase_all = pd.concat(all_phase, ignore_index=True)
    print(f"[ok] total phase rows: {len(df_phase_all)}")
else:
    df_phase_all = pd.DataFrame()

if len(all_meta):
    df_meta_all = pd.DataFrame(all_meta)
else:
    df_meta_all = pd.DataFrame()

# ---------- animal-level overlays ----------
if (SHOW_OVERLAY_ALLSESS_FIGS or SAVE_OVERLAY_ALLSESS_FIGS or SHOW_OVERLAY_BINNED_FIGS or SAVE_OVERLAY_BINNED_FIGS) and (not df_meta_all.empty):
    for mouse in sorted(df_meta_all["mouse"].unique().tolist()):
        df_trials_m = df_trials_all[df_trials_all["mouse"] == mouse].copy()
        df_bouts_m = df_bouts_all[df_bouts_all["mouse"] == mouse].copy()
        df_phase_m = df_phase_all[df_phase_all["mouse"] == mouse].copy()
        meta_m = df_meta_all[df_meta_all["mouse"] == mouse].copy().sort_values("date")

        if meta_m.empty:
            continue

        outdir = _session_save_dir(mouse)
        bin_days = int(meta_m["bin_days"].iloc[0])

        if SHOW_OVERLAY_ALLSESS_FIGS or SAVE_OVERLAY_ALLSESS_FIGS:
            _plot_overlay_grid_all_sessions(mouse, df_trials_m, df_phase_m, df_bouts_m, meta_m, outdir=outdir)

        if SHOW_OVERLAY_BINNED_FIGS or SAVE_OVERLAY_BINNED_FIGS:
            _plot_overlay_grid_binned(mouse, df_trials_m, df_phase_m, df_bouts_m, meta_m, bin_days=bin_days, outdir=outdir)

