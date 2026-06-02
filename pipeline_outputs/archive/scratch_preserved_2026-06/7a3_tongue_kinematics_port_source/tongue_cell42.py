=== cell 42 (code, 827 lines) ===
# ===== Reward-aligned licking summaries using within-bout ILI rate (v5) =====
# Adds BOTH:
#   (A) P(bout-state): "active_frac" = fraction of trials with >=1 *bout-ILI sample* in bin
#   (B) P(lick-peak):  "p_lick"      = fraction of trials with >=1 *lick peak* in bin
#
# Then: day-bin sessions by rel_day (toggle bin size in days), plot mean±SEM across sessions within each day-bin.
# Plotting: 4 rows (metrics) x 2 cols (L,R), share y within each row; legend on right (outside), no colorbar.
#
# NEW in this version:
#   - multi-animal configuration via MOUSE_SPECS
#   - per-animal day-bin size via bin_days
#   - explicit separate smoothing parameters for:
#       * overall lick rate
#       * within-bout ILI rate
#       * probability traces
#   - MIN_TRIALS_PER_BIN for within-bout ILI support
#   - unsupported bout-rate bins are set to NaN
#   - smoothing of bout-rate traces preserves unsupported bins as NaN
#
# Output per mouse:
#   - df_sess_traces: one row per session x side (stores full traces as lists)
#   - df_bin_traces:  one row per rel_day_bin x side x timebin (mean±SEM across sessions)
#   - PNG + CSVs saved under each mouse's lick_rate directory

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== SHARED USER KNOBS =====================
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ===================== PER-ANIMAL CONFIG =====================
MOUSE_SPECS = {
    "PS46": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None),
    "PS47": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None),
    "PS48": dict(date_start="20250307", date_end="20250406", d0="20250313", bin_days=2, include_dates=None, exclude_dates=None),
    "PS49": dict(date_start="20250310", date_end="20250406", d0="20250317", bin_days=2, include_dates=None, exclude_dates=None),
    "PS50": dict(date_start="20250319", date_end="20250406", d0="20250323", bin_days=2, include_dates=None, exclude_dates=None),
    "PS51": dict(date_start="20250416", date_end="20250709", d0="20250429", bin_days=7, include_dates=None, exclude_dates=None),
    "PS54": dict(date_start="20250416", date_end="20250709", d0="20250430", bin_days=7, include_dates=None, exclude_dates=None),
    "PS55": dict(date_start="20250416", date_end="20250709", d0="20250430", bin_days=7, include_dates=None, exclude_dates=None),
}

# ---- stroke alignment ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"        # "pre", "post", "both", "all"
REL_DAY_RANGE = None         # None or (min_day, max_day) inclusive

# ---- sides ----
PLOT_SIDES = ("L", "R")
USE_SRC = "final"            # "final" or "thr_interp"

# ---- snippet/detect windows (ms) ----
PLOT_WIN_MS   = (-200.0, 8000.0)
DETECT_WIN_MS = (70.0, 8000.0)

# ---- rate window + time binning ----
RATE_WIN_MS = (0.0, 2500.0)
BIN_MS = 20.0

# ---- smoothing (explicit, separate) ----
DO_SMOOTH_LICKRATE = True
LICKRATE_SMOOTH_SIGMA_MS = 50.0     # overall lick-rate Gaussian sigma

DO_SMOOTH_ILI = True
ILI_SMOOTH_SIGMA_MS = 50.0          # within-bout ILI-rate Gaussian sigma

DO_SMOOTH_PROB = True
PROB_SMOOTH_MOVAVG_MS = 200.0       # moving-average window for P(lick) and P(ILI present)

# ---- within-bout definition (ILI-based) ----
BOUT_MAX_ILI_MS = 400.0
BOUT_MIN_ILI_MS = 80.0
MIN_LICKS_IN_BOUT = 3

# ---- minimum contributing trials per ILI bin ----
MIN_TRIALS_PER_BIN = 3

# ---- dy/dt lick peak detector settings ----
DO_SMOOTH_Y = False
SMOOTH_Y_MS = 12.0

RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0
PEAK_PAD_MS = 52.0
MAX_LICKS_PER_TRIAL = 80

# ---- plotting style ----
PRE_COLOR = "0.3"
POST_CMAP = "plasma"

# ---- saving ----
SAVE_FIGS   = True
FIG_DPI     = 200
SAVE_TABLES = True
# ======================================================


# ---------------- helpers ----------------
def yyyymmdd_to_date(s):
    return datetime.strptime(s, "%Y%m%d").date()

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

def list_session_npzs_v5_only(mouse, cam):
    sess_dir = (
        OUT_ROOT / mouse / f"{mouse}_tongue_kinematics" /
        "processed_interpolated_data" / f"{CENTER_MODE}"
    )
    if not sess_dir.exists():
        raise FileNotFoundError(f"Missing processed_interpolated_data folder:\n  {sess_dir}")

    pat = re.compile(
        rf"^{re.escape(mouse)}_(?P<date>\d{{8}})_{re.escape(cam)}_tongue_interp_{INTERP_VERSION}\.npz$"
    )
    available = {}
    for p in sorted(sess_dir.glob(f"{mouse}_*_{cam}_tongue_interp_{INTERP_VERSION}.npz")):
        m = pat.match(p.name)
        if m:
            available[m.group("date")] = p
    return available, sess_dir

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
    if w <= 1:
        return y.copy()
    finite = np.isfinite(y)
    y0 = np.where(finite, y, 0.0)
    kernel = np.ones(int(w), dtype=float)
    num = np.convolve(y0, kernel, mode="same")
    den = np.convolve(finite.astype(float), kernel, mode="same")
    out = np.full_like(y, np.nan, dtype=float)
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

def _gaussian_kernel_1d(sigma_bins, radius_bins=None):
    sigma_bins = float(sigma_bins)
    if sigma_bins <= 0:
        return np.array([1.0], float)
    if radius_bins is None:
        radius_bins = int(np.ceil(4 * sigma_bins))
    r = int(max(1, radius_bins))
    x = np.arange(-r, r + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma_bins) ** 2)
    k /= np.sum(k)
    return k

def _smooth_rate_gauss(rate, sigma_ms, bin_ms):
    if (sigma_ms is None) or (sigma_ms <= 0):
        return rate
    sigma_bins = float(sigma_ms) / float(bin_ms)
    k = _gaussian_kernel_1d(sigma_bins)
    return np.convolve(rate, k, mode="same")

def _smooth_movavg(y, win_ms, bin_ms):
    if (win_ms is None) or (win_ms <= 0):
        return y
    w = int(np.round(float(win_ms) / float(bin_ms)))
    w = max(1, w)
    return _moving_average_nan(y, w)

def _smooth_preserve_nan_mask_gauss(y, sigma_ms, bin_ms):
    y = np.asarray(y, float)
    mask = np.isfinite(y)
    if (sigma_ms is None) or (sigma_ms <= 0):
        return y.copy()
    y0 = np.where(mask, y, 0.0)
    sigma_bins = float(sigma_ms) / float(bin_ms)
    k = _gaussian_kernel_1d(sigma_bins)
    num = np.convolve(y0, k, mode="same")
    den = np.convolve(mask.astype(float), k, mode="same")
    out = np.full_like(y, np.nan, dtype=float)
    good = den > 0
    out[good] = num[good] / den[good]
    out[~mask] = np.nan
    return out

def _rel_day_bin_edges(rel_days, bin_size):
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return np.array([0, 1], int)

    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))
    B = int(max(1, bin_size))

    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

    bins = []
    lo = pre_start
    hi = lo + (B - 1)
    while hi <= 0:
        bins.append((lo, hi))
        lo += B
        hi += B

    lo = 1
    hi = lo + (B - 1)
    while lo <= mx:
        bins.append((lo, hi))
        lo += B
        hi += B

    return bins

def _assign_rel_day_to_bin(rel_day, bins):
    rd = int(rel_day)
    for (lo, hi) in bins:
        if lo <= rd <= hi:
            return f"{lo}..{hi}", 0.5 * (lo + hi)
    return None, np.nan

def _lick_peaks_from_y_dydt_times(yw, xw, fps, t_ms, detect_win_ms,
                                 slope_thr=SLOPE_THR_PX_PER_S,
                                 rise_min_ms=RISE_MIN_MS,
                                 fall_min_ms=FALL_MIN_MS,
                                 peak_pad_ms=PEAK_PAD_MS,
                                 do_smooth_y=DO_SMOOTH_Y,
                                 smooth_ms=SMOOTH_Y_MS,
                                 max_licks=80):
    lo_ms, hi_ms = map(float, detect_win_ms)
    i0 = int(np.searchsorted(t_ms, lo_ms, side="left"))
    i1 = int(np.searchsorted(t_ms, hi_ms, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms) - 1))
    i1 = max(0, min(i1, len(t_ms) - 1))
    if i1 < i0:
        i0, i1 = i1, i0

    yseg0 = np.asarray(yw[i0:i1+1], float)
    xseg0 = np.asarray(xw[i0:i1+1], float)
    if not np.any(np.isfinite(yseg0)):
        return np.array([], float)

    ys = yseg0.copy()
    if do_smooth_y and (smooth_ms is not None) and (smooth_ms > 0):
        w = max(1, _ms_to_frames(smooth_ms, fps))
        if w >= 3:
            ys = _moving_average_nan(ys, w)

    dt_s = 1.0 / float(fps)
    dy = np.gradient(ys) / dt_s

    finite = np.isfinite(ys) & np.isfinite(dy) & np.isfinite(xseg0)
    rise_mask = finite & (dy > +float(slope_thr))
    fall_mask = finite & (dy < -float(slope_thr))

    rise_min_f = max(1, _ms_to_frames(rise_min_ms, fps))
    fall_min_f = max(1, _ms_to_frames(fall_min_ms, fps))
    pad_f      = max(0, _ms_to_frames(peak_pad_ms, fps))

    L = len(yseg0)
    peaks_ms = []
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

        j_peak = seg_lo + int(np.nanargmax(seg))

        end_idx = j_peak
        f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
        if f0 is not None:
            end_idx = max(end_idx, f1 - 1)

        i_peak_global = i0 + j_peak
        peaks_ms.append(float(t_ms[i_peak_global]))

        start = int(end_idx + 1)
        if start >= L:
            break

    return np.asarray(peaks_ms, float)

def _bout_ili_rate_samples(peaks_ms,
                           win_ms,
                           ili_min_ms=50.0,
                           ili_max_ms=250.0,
                           min_licks_in_bout=0):
    t0, t1 = map(float, win_ms)
    p = np.asarray(peaks_ms, float)
    p = p[np.isfinite(p)]
    p = p[(p >= t0) & (p <= t1)]
    if p.size < 2:
        return np.array([], float), np.array([], float)

    p = np.sort(p)
    ili = np.diff(p)
    good = (ili >= float(ili_min_ms)) & (ili <= float(ili_max_ms))
    if not np.any(good):
        return np.array([], float), np.array([], float)

    if (min_licks_in_bout is not None) and (min_licks_in_bout >= 2):
        min_edges = int(min_licks_in_bout) - 1
        keep_edge = np.zeros_like(good, dtype=bool)
        i = 0
        while i < good.size:
            if not good[i]:
                i += 1
                continue
            j = i
            while j < good.size and good[j]:
                j += 1
            if (j - i) >= min_edges:
                keep_edge[i:j] = True
            i = j
        good = keep_edge
        if not np.any(good):
            return np.array([], float), np.array([], float)

    ili_good = ili[good]
    t_mid = 0.5 * (p[:-1][good] + p[1:][good])
    rate = 1000.0 / ili_good
    return t_mid.astype(float), rate.astype(float)


# ===================== MAIN LOOP OVER ANIMALS =====================
for MOUSE, cfg in MOUSE_SPECS.items():
    print("\n" + "="*90)
    print(f"[mouse] {MOUSE}")

    DATE_START = cfg["date_start"]
    DATE_END = cfg["date_end"]
    STROKE_DATE = cfg.get("d0", None)
    REL_DAY_BIN_SIZE_D = int(cfg.get("bin_days", 2))
    INCLUDE_DATES = set(cfg.get("include_dates") or [])
    EXCLUDE_DATES = set(cfg.get("exclude_dates") or [])

    FIG_DIR = (
        OUT_ROOT / MOUSE / f"{MOUSE}_tongue_kinematics" / "kinematics_figures" /
        f"{CENTER_MODE}" / "lick_metrics" / "lick_rate"
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        available, sess_dir = list_session_npzs_v5_only(MOUSE, CAM)
    except Exception as e:
        print(f"[warn] {MOUSE}: could not locate session npzs\n{e}")
        continue

    if INCLUDE_DATES:
        dates = sorted([d for d in INCLUDE_DATES if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
    dates = [d for d in dates if d not in EXCLUDE_DATES]

    if not dates:
        some = sorted(available.keys())
        print(
            "[warn] No sessions matched.\n"
            f"Folder: {sess_dir}\n"
            f"Available {INTERP_VERSION} dates (first 60): {some[:60]}\n"
            f"Your selection: start={DATE_START}, end={DATE_END}"
        )
        continue

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        print("[warn] After pre/post filtering, no sessions remain.")
        continue

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    print(f"[info] analyzing {len(dates)} sessions: {dates}")
    print(f"[info] time window={RATE_WIN_MS} ms, timebin={BIN_MS} ms")
    print(f"[info] bout ILI in [{BOUT_MIN_ILI_MS}, {BOUT_MAX_ILI_MS}] ms; MIN_LICKS_IN_BOUT={MIN_LICKS_IN_BOUT}")
    print(f"[info] MIN_TRIALS_PER_BIN for ILI rate = {MIN_TRIALS_PER_BIN}")
    print(f"[info] rel_day bin size={REL_DAY_BIN_SIZE_D} d")

    t0, t1 = map(float, RATE_WIN_MS)
    bin_ms = float(BIN_MS)
    edges_ms = np.arange(t0, t1 + bin_ms, bin_ms, dtype=float)
    centers_ms = 0.5 * (edges_ms[:-1] + edges_ms[1:])
    n_timebins = len(centers_ms)

    sess_rows = []

    for d in dates:
        p_npz = available[d]
        Z = np.load(p_npz, allow_pickle=True)

        fps = float(Z["fps"])
        n_frames = int(Z["n_frames"])

        if USE_SRC == "final":
            x = Z["x_final"].astype(float)
            y = Z["y_final"].astype(float)
            src_label = "final"
        elif USE_SRC == "thr_interp":
            x = Z["x_thr_interp"].astype(float)
            y = Z["y_thr_interp"].astype(float)
            src_label = "thr_interp"
        else:
            raise ValueError("USE_SRC must be 'final' or 'thr_interp'")

        pre_f  = abs(_ms_to_frames(PLOT_WIN_MS[0], fps))
        post_f = abs(_ms_to_frames(PLOT_WIN_MS[1], fps))
        t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))

        rel_day = np.nan
        if stroke_dt is not None:
            rel_day = (yyyymmdd_to_date(d) - stroke_dt).days

        centers_by_side = {}
        if "L" in PLOT_SIDES:
            centers_by_side["L"] = Z["fr_reward_mouseL"].astype(int)
        if "R" in PLOT_SIDES:
            centers_by_side["R"] = Z["fr_reward_mouseR"].astype(int)

        for side, centers in centers_by_side.items():
            centers = centers[(centers >= 0) & (centers < n_frames)]
            n_trials = int(len(centers))

            lickrate_trials = np.full((n_trials, n_timebins), np.nan, float)
            boutrate_trials = np.full((n_trials, n_timebins), np.nan, float)
            boutactive_trials = np.zeros((n_trials, n_timebins), float)
            lickpresent_trials = np.zeros((n_trials, n_timebins), float)

            for k, c in enumerate(centers):
                c = int(c)
                yw = _snippet(y, c, pre_f, post_f)
                xw = _snippet(x, c, pre_f, post_f)

                peaks_ms = _lick_peaks_from_y_dydt_times(
                    yw, xw, fps, t_ms, DETECT_WIN_MS,
                    slope_thr=SLOPE_THR_PX_PER_S,
                    rise_min_ms=RISE_MIN_MS,
                    fall_min_ms=FALL_MIN_MS,
                    peak_pad_ms=PEAK_PAD_MS,
                    do_smooth_y=DO_SMOOTH_Y,
                    smooth_ms=SMOOTH_Y_MS,
                    max_licks=MAX_LICKS_PER_TRIAL,
                )

                p = peaks_ms[np.isfinite(peaks_ms)]
                p = p[(p >= t0) & (p <= t1)]

                h, _ = np.histogram(p, bins=edges_ms)
                rate = h.astype(float) / (bin_ms / 1000.0)
                if DO_SMOOTH_LICKRATE:
                    rate = _smooth_rate_gauss(rate, sigma_ms=LICKRATE_SMOOTH_SIGMA_MS, bin_ms=bin_ms)
                lickrate_trials[k, :] = rate

                lickpresent_trials[k, :] = (h > 0).astype(float)

                t_mid, r_hz = _bout_ili_rate_samples(
                    peaks_ms,
                    win_ms=RATE_WIN_MS,
                    ili_min_ms=BOUT_MIN_ILI_MS,
                    ili_max_ms=BOUT_MAX_ILI_MS,
                    min_licks_in_bout=MIN_LICKS_IN_BOUT,
                )

                if t_mid.size > 0:
                    bin_idx = np.searchsorted(edges_ms, t_mid, side="right") - 1
                    ok = (bin_idx >= 0) & (bin_idx < n_timebins) & np.isfinite(r_hz)
                    bin_idx = bin_idx[ok]
                    r_hz_ok = r_hz[ok]

                    if bin_idx.size > 0:
                        tmp_sum = np.zeros(n_timebins, float)
                        tmp_n   = np.zeros(n_timebins, float)
                        for bi, rv in zip(bin_idx, r_hz_ok):
                            tmp_sum[int(bi)] += float(rv)
                            tmp_n[int(bi)]   += 1.0

                        with np.errstate(invalid="ignore", divide="ignore"):
                            br = tmp_sum / tmp_n
                        br[tmp_n == 0] = np.nan
                        boutrate_trials[k, :] = br
                        boutactive_trials[k, :] = (tmp_n > 0).astype(float)

            lick_mean = np.nanmean(lickrate_trials, axis=0) if n_trials > 0 else np.full(n_timebins, np.nan)
            lick_sem  = (np.nanstd(lickrate_trials, axis=0) / np.sqrt(max(1, n_trials))) if n_trials > 0 else np.full(n_timebins, np.nan)

            act_frac = (np.nanmean(boutactive_trials, axis=0) if n_trials > 0 else np.full(n_timebins, np.nan))
            act_sem  = (np.sqrt(act_frac * (1.0 - act_frac) / n_trials) if n_trials > 1 else np.full(n_timebins, np.nan))

            p_lick = (np.nanmean(lickpresent_trials, axis=0) if n_trials > 0 else np.full(n_timebins, np.nan))
            p_lick_sem = (np.sqrt(p_lick * (1.0 - p_lick) / n_trials) if n_trials > 1 else np.full(n_timebins, np.nan))

            bout_mean = np.nanmean(boutrate_trials, axis=0) if n_trials > 0 else np.full(n_timebins, np.nan)
            nn = np.sum(np.isfinite(boutrate_trials), axis=0) if n_trials > 0 else np.zeros(n_timebins, int)
            bout_sem = np.full(n_timebins, np.nan, float)

            if n_trials > 0:
                sd = np.nanstd(boutrate_trials, axis=0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    bout_sem = sd / np.sqrt(np.maximum(1, nn))
                bout_sem[nn < 2] = np.nan

            support_mask = (nn >= int(MIN_TRIALS_PER_BIN))
            bout_mean[~support_mask] = np.nan
            bout_sem[~support_mask] = np.nan

            sess_rows.append(dict(
                date=d,
                date_dt=yyyymmdd_to_date(d),
                rel_day=float(rel_day) if np.isfinite(rel_day) else np.nan,
                side=side,
                n_trials=int(n_trials),
                src=src_label,
                npz=str(p_npz),

                t_ms=centers_ms.tolist(),

                lick_rate_mean_hz=lick_mean.tolist(),
                lick_rate_sem_hz=lick_sem.tolist(),

                bout_state_frac=act_frac.tolist(),
                bout_state_frac_sem=act_sem.tolist(),

                p_lick=p_lick.tolist(),
                p_lick_sem=p_lick_sem.tolist(),

                bout_rate_mean_hz=bout_mean.tolist(),
                bout_rate_sem_hz=bout_sem.tolist(),

                bout_active_n_trials=nn.astype(int).tolist(),
                bout_rate_supported_mask=support_mask.astype(int).tolist(),
            ))

    df_sess_traces = pd.DataFrame(sess_rows).sort_values(["date_dt", "side"]).reset_index(drop=True)
    if df_sess_traces.empty:
        print(f"[warn] {MOUSE}: no session traces generated.")
        continue

    print("\n[info] df_sess_traces head:")
    print(df_sess_traces[["date","rel_day","side","n_trials","src"]].head(10).to_string(index=False))

    if not (USE_STROKE_ALIGNMENT and stroke_dt is not None):
        print(f"[warn] {MOUSE}: this plotting cell expects stroke alignment.")
        continue

    rel_days_all = df_sess_traces["rel_day"].to_numpy(float)
    bins = _rel_day_bin_edges(rel_days_all, bin_size=REL_DAY_BIN_SIZE_D)

    bin_labels = []
    bin_centers = []
    for rd in df_sess_traces["rel_day"].to_numpy(float):
        if not np.isfinite(rd):
            bin_labels.append(None)
            bin_centers.append(np.nan)
        else:
            lab, cen = _assign_rel_day_to_bin(int(rd), bins)
            bin_labels.append(lab)
            bin_centers.append(float(cen))
    df_sess_traces["rel_day_bin"] = bin_labels
    df_sess_traces["rel_day_bin_center"] = bin_centers

    df_sess_traces = df_sess_traces[df_sess_traces["rel_day_bin"].notna()].copy()
    if df_sess_traces.empty:
        print(f"[warn] {MOUSE}: no sessions had finite rel_day_bin assignments.")
        continue

    def _stack_listcol_to_matrix(dd, colname):
        return np.vstack([np.asarray(v, float) for v in dd[colname].to_list()])

    bin_rows = []
    for (side, b_lab, b_cen), dd in df_sess_traces.groupby(["side", "rel_day_bin", "rel_day_bin_center"], sort=True):
        dd = dd.sort_values("rel_day")
        n_sess = int(dd.shape[0])
        tvec = np.asarray(dd["t_ms"].iloc[0], float)

        for metric in ["lick_rate_mean_hz", "bout_rate_mean_hz", "p_lick", "bout_state_frac"]:
            M = _stack_listcol_to_matrix(dd, metric)
            m = np.nanmean(M, axis=0)
            s = np.nanstd(M, axis=0) / np.sqrt(max(1, n_sess))

            if metric == "bout_rate_mean_hz":
                support_sessions = np.sum(np.isfinite(M), axis=0)
                m[support_sessions == 0] = np.nan
                s[support_sessions == 0] = np.nan
            else:
                support_sessions = np.sum(np.isfinite(M), axis=0)

            bin_rows.append(dict(
                side=side,
                rel_day_bin=b_lab,
                rel_day_bin_center=float(b_cen),
                n_sessions=n_sess,
                t_ms=tvec.tolist(),
                metric=metric,
                mean=m.tolist(),
                sem=s.tolist(),
                n_support_sessions=support_sessions.astype(int).tolist(),
            ))

    df_bin_traces = pd.DataFrame(bin_rows)
    print("\n[info] df_bin_traces head:")
    print(df_bin_traces[["side","rel_day_bin","rel_day_bin_center","n_sessions","metric"]].head(12).to_string(index=False))

    def _color_for_bin(center):
        if not np.isfinite(center):
            return PRE_COLOR
        if center <= 0:
            return PRE_COLOR
        post_max = float(np.nanmax(df_sess_traces["rel_day"].to_numpy(float)))
        denom = max(1.0, (post_max - 1.0))
        return plt.get_cmap(POST_CMAP)((center - 1.0) / denom)

    bin_order = (
        df_sess_traces[["rel_day_bin","rel_day_bin_center"]]
        .drop_duplicates()
        .sort_values("rel_day_bin_center")
    )
    bins_in_plot = [(r.rel_day_bin, float(r.rel_day_bin_center)) for r in bin_order.itertuples(index=False)]

    legend_items = []
    for lab, cen in bins_in_plot:
        n = int(df_sess_traces[df_sess_traces["rel_day_bin"] == lab]["date"].nunique())
        legend_items.append((lab, cen, n))

    metric_info = [
        ("lick_rate_mean_hz", "Overall lick rate (Hz)"),
        ("bout_rate_mean_hz", "Inter-lick interval rate (Hz)"),
        ("p_lick",            "P(lick)"),
        ("bout_state_frac",   "P(ILI present)"),
    ]

    fig, axes = plt.subplots(
        nrows=len(metric_info), ncols=2, figsize=(15.2, 11.2),
        sharex=True, sharey="row",
        gridspec_kw=dict(hspace=0.14, wspace=0.08)
    )
    fig.subplots_adjust(right=0.80)

    side_to_col = {"L": 0, "R": 1}

    for r, (metric, ylabel) in enumerate(metric_info):
        for side in PLOT_SIDES:
            c = side_to_col[side]
            ax = axes[r, c]

            for (lab, cen, n_sess) in legend_items:
                dd = df_bin_traces[
                    (df_bin_traces["side"] == side) &
                    (df_bin_traces["rel_day_bin"] == lab) &
                    (df_bin_traces["metric"] == metric)
                ]
                if dd.empty:
                    continue

                tvec = np.asarray(dd["t_ms"].iloc[0], float)
                m = np.asarray(dd["mean"].iloc[0], float)
                s = np.asarray(dd["sem"].iloc[0], float)

                col = _color_for_bin(cen)

                if metric == "lick_rate_mean_hz" and DO_SMOOTH_LICKRATE:
                    m = _smooth_rate_gauss(m, sigma_ms=LICKRATE_SMOOTH_SIGMA_MS, bin_ms=BIN_MS)
                    s = _smooth_rate_gauss(s, sigma_ms=LICKRATE_SMOOTH_SIGMA_MS, bin_ms=BIN_MS)

                elif metric == "bout_rate_mean_hz" and DO_SMOOTH_ILI:
                    m = _smooth_preserve_nan_mask_gauss(m, sigma_ms=ILI_SMOOTH_SIGMA_MS, bin_ms=BIN_MS)
                    s = _smooth_preserve_nan_mask_gauss(s, sigma_ms=ILI_SMOOTH_SIGMA_MS, bin_ms=BIN_MS)

                elif metric in ("p_lick", "bout_state_frac") and DO_SMOOTH_PROB:
                    m = _smooth_movavg(m, win_ms=PROB_SMOOTH_MOVAVG_MS, bin_ms=BIN_MS)
                    s = _smooth_movavg(s, win_ms=PROB_SMOOTH_MOVAVG_MS, bin_ms=BIN_MS)

                ax.plot(tvec, m, color=col, lw=1.6, alpha=0.75)
                ok = np.isfinite(m) & np.isfinite(s)
                if np.any(ok):
                    ax.fill_between(tvec[ok], (m - s)[ok], (m + s)[ok], color=col, alpha=0.12, lw=0)

            ax.axvline(0, color="k", lw=1.0, alpha=0.6)
            ax.grid(True, alpha=0.2)

            if c == 0:
                ax.set_ylabel(ylabel)
            if r == 0:
                ax.set_title(f"{side} trials")

    axes[-1, 0].set_xlabel("Time relative to reward (ms)")
    axes[-1, 1].set_xlabel("Time relative to reward (ms)")

    title = (
        f"{MOUSE} {CAM} | reward-aligned licking; day-binned (bin={REL_DAY_BIN_SIZE_D}d) | "
        f"timebin={BIN_MS:.0f}ms | bout ILI∈[{BOUT_MIN_ILI_MS:.0f},{BOUT_MAX_ILI_MS:.0f}]ms | "
        f"MIN_TRIALS_PER_BIN={MIN_TRIALS_PER_BIN}"
    )
    if DO_SMOOTH_LICKRATE:
        title += f" | lickrate σ={LICKRATE_SMOOTH_SIGMA_MS:.0f}ms"
    if DO_SMOOTH_ILI:
        title += f" | ILI σ={ILI_SMOOTH_SIGMA_MS:.0f}ms"
    if DO_SMOOTH_PROB:
        title += f" | prob movavg={PROB_SMOOTH_MOVAVG_MS:.0f}ms"
    fig.suptitle(title, y=0.995)

    handles, labels = [], []
    for lab, cen, n_sess in legend_items:
        col = _color_for_bin(cen)
        handles.append(Line2D([0],[0], color=col, lw=2.8))
        labels.append(f"{lab} (n={n_sess})")
    fig.legend(
        handles, labels,
        title="rel_day bins",
        loc="center left",
        bbox_to_anchor=(0.82, 0.5),
        frameon=False,
        ncol=1,
    )

    plt.tight_layout()

    if SAVE_FIGS:
        out_tag = (
            f"{MOUSE}_{CAM}_ILIwithinBout_daybin{REL_DAY_BIN_SIZE_D}d_"
            f"timebin{int(BIN_MS)}ms_ili{int(BOUT_MIN_ILI_MS)}-{int(BOUT_MAX_ILI_MS)}ms_"
            f"minTrialsPerBin{int(MIN_TRIALS_PER_BIN)}_{DATE_START}-{DATE_END}_{INTERP_VERSION}"
        )
        p = FIG_DIR / f"{out_tag}.png"
        fig.savefig(p, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {p}")

    plt.show()
    plt.close(fig)

    if SAVE_TABLES:
        p_sess = FIG_DIR / (
            f"{MOUSE}_{CAM}_ILIwithinBout_perSessionTraces_"
            f"minTrialsPerBin{int(MIN_TRIALS_PER_BIN)}_{DATE_START}-{DATE_END}_{INTERP_VERSION}.csv"
        )
        p_bin  = FIG_DIR / (
            f"{MOUSE}_{CAM}_ILIwithinBout_dayBinnedTraces_bin{REL_DAY_BIN_SIZE_D}d_"
            f"minTrialsPerBin{int(MIN_TRIALS_PER_BIN)}_{DATE_START}-{DATE_END}_{INTERP_VERSION}.csv"
        )
        df_sess_traces.to_csv(p_sess, index=False)
        df_bin_traces.to_csv(p_bin, index=False)
        print(f"[save] {p_sess}")
        print(f"[save] {p_bin}")

print("\n[ok] done")

