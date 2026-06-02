=== cell 33 (code, 795 lines) ===
# ===== First+Second-lick per-trial FIRST-PEAK metrics (v5, dY/dt method)
# -> per-session mean ± SEM, L vs R separately
#
# MULTI-ANIMAL / MULTI-SESSION version (tongue)
# - Loops over MOUSE_SPECS (like your multi-animal tongue plots)
# - Keeps your lick1+lick2 detector + plotting style + save structure
# - Saves per-mouse into:
#     .../<MOUSE>_tongue_kinematics/kinematics_figures/<CENTER_MODE>/lick_metrics/{firstlick_metrics,secondlick_metrics}/
# - Saves CSVs into BOTH firstlick_metrics and secondlick_metrics folders (same as your original)
#
# UPDATED:
# - Plot-only filter: sessions must have >= MIN_DETECTED_TRIALS_TO_PLOT detected lick trials
#   for the relevant lick metric to be included in the plot
# - CSVs still include ALL sessions
# - Legend example dot sizes updated to [10, 25, 50]

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== USER KNOBS =====================
CAM   = "cam2"
CENTER_MODE = "centered_spout_midpoint"     # "nose", "spout_midpoint", "eye_midpoint", etc.

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# v5 only
INTERP_VERSION = "v5p3"

# ---- across-animal specification (lick timing; tongue NPZs) ----
MOUSE_SPECS = {
    "PS46": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None),
    "PS47": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None),
    "PS48": dict(date_start="20250307", date_end="20250406", d0="20250313", include_dates=None, exclude_dates=None),
    "PS49": dict(date_start="20250310", date_end="20250406", d0="20250317", include_dates=None, exclude_dates=None),
    "PS50": dict(date_start="20250319", date_end="20250406", d0="20250323", include_dates=None, exclude_dates=None),
    "PS51": dict(date_start="20250416", date_end="20250709", d0="20250429", include_dates=None, exclude_dates=None),
    "PS54": dict(date_start="20250416", date_end="20250709", d0="20250430", include_dates=None, exclude_dates=None),
    "PS55": dict(date_start="20250416", date_end="20250709", d0="20250430", include_dates=None, exclude_dates=None),
}

# Choose which mice to run (None => all keys in MOUSE_SPECS)
MICE_TO_RUN = None  # e.g. ["PS48"] or ["PS51","PS54","PS55"]

# ---- pre/post stroke labeling + filtering ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"           # "pre", "post", "both", or "all"
REL_DAY_RANGE = None            # None or (min_day, max_day) inclusive

# ---- which reward trials to include in plots ----
PLOT_SIDES = ("L", "R")         # any subset of ("L","R")

# ---- which arrays to use from the npz ----
USE_SRC = "final"               # "final" or "thr_interp"

# ---- windows, with negative meaning before reward ----
PLOT_WIN_MS   = (-200.0, 2500.0)  # snippet pulled per trial
DETECT_WIN_MS = (70, 2000)        # detection window inside snippet

# ---- peak detector settings ----
DO_SMOOTH_Y = False
SMOOTH_MS = 12.0

RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0

MIN_PEAK_Y_ABS = 20.0
PEAK_PAD_MS = 52.0

# if True: if any step fails (no rise/turnover/fall/amp), lick is NaN
STRICT_NO_FALLBACK = True
FAIL_FALLBACK = "max_abs"  # only used if STRICT_NO_FALLBACK=False

# ---- plots ----
DO_PLOT_TIME = True
DO_PLOT_Y    = True
DO_PLOT_X    = True

# ---- NEW: minimum number of detected lick trials required for plotting ----
# Sessions below this threshold remain in CSV outputs but are excluded from plots.
MIN_DETECTED_TRIALS_TO_PLOT = 10

# ---- dot size scaling by n_detected (ABSOLUTE) ----
DOT_SIZE_MIN  = 10
DOT_SIZE_MAX  = 50
DOT_SIZE_MODE = "linear"   # "linear" or "sqrt"
LEGEND_N_EXAMPLES = [10, 25, 50]  # updated legend examples
DOT_SIZE_N_MAX = 50               # absolute reference for dot sizes

# ---- COLORS / ALPHAS ----
SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}  # line + SEM color per side
PRE_COLOR   = "0.6"   # grey for pre-stroke dots
POST_CMAP   = "plasma"

LINE_ALPHA  = 0.45
DOT_ALPHA   = 0.95
SEM_ALPHA   = 0.12

# ---- saving figures + tables ----
SAVE_FIGS = True
FIG_DPI = 200
SAVE_TABLES = True
# ======================================================

# ---------- helpers ----------
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
        OUT_ROOT
        / mouse
        / f"{mouse}_tongue_kinematics"
        / "processed_interpolated_data"
        / f"{CENTER_MODE}"
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
    rel = (d - stroke_dt).days  # stroke date is last pre => d0
    if PREPOST_MODE == "pre":
        return rel <= 0
    if PREPOST_MODE == "post":
        return rel >= 1
    if PREPOST_MODE == "both":
        return True
    raise ValueError("PREPOST_MODE must be one of: 'pre','post','both','all'")

def _ms_to_frames(ms, fps):
    return int(np.round((ms / 1000.0) * fps))

def _mean_sem_1d(v):
    v = np.asarray(v, dtype=float)
    m = np.isfinite(v)
    n = int(np.sum(m))
    if n == 0:
        return np.nan, np.nan, 0
    mu = float(np.nanmean(v))
    sd = float(np.nanstd(v))
    sem = sd / np.sqrt(n) if n > 0 else np.nan
    return mu, sem, n

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
    """Return first run [i,j) of True of length >=min_len beginning at/after start."""
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

def _session_dot_colors_from_rel_days(rel_days, cmap_name="plasma", pre_color="0.6"):
    rel = np.asarray(rel_days, float)
    cmap = plt.get_cmap(cmap_name)

    if np.all(~np.isfinite(rel)):
        return [cmap(i / max(1, len(rel) - 1)) for i in range(len(rel))]

    post_idx = np.flatnonzero(np.isfinite(rel) & (rel >= 1))
    n_post = len(post_idx)

    colors = [pre_color] * len(rel)
    for j, i in enumerate(post_idx):
        colors[i] = cmap(j / max(1, n_post - 1))
    return colors

# ---- ABSOLUTE dot size mapping (FIX) ----
def _dot_sizes_from_n_absolute(n_detected, n_max, smin=18, smax=110, mode="sqrt"):
    n = np.asarray(n_detected, float)
    if n.size == 0:
        return np.array([], float)

    n_f = np.where(np.isfinite(n), n, 0.0)
    n_max = float(max(1.0, n_max))
    n_f = np.clip(n_f, 0.0, n_max)

    if mode == "sqrt":
        u = np.sqrt(n_f) / np.sqrt(n_max)
    else:
        u = n_f / n_max

    return smin + u * (smax - smin)

def _dot_size_legend_handles_absolute(n_examples, n_max,
                                      smin=18, smax=110, mode="sqrt",
                                      color="0.4"):
    sizes = _dot_sizes_from_n_absolute(
        np.array(n_examples, float),
        n_max=n_max,
        smin=smin, smax=smax, mode=mode
    )
    handles = []
    for n, s in zip(n_examples, sizes):
        handles.append(Line2D(
            [0], [0],
            marker="o", linestyle="None",
            markersize=np.sqrt(s),
            markerfacecolor=color, markeredgecolor="none",
            alpha=0.85,
            label=f"n={int(n)}"
        ))
    return handles

# ---------- lick detector: detect up to 2 licks (1st + 2nd) ----------
def _detect_first_two_lick_peaks_dydt(xw, yw, fps, win_ms, t_ms):
    """
    Detect lick1 then lick2 (sequentially) within win_ms.
    Returns per-lick:
      i_peak (index into snippet), t_peak_ms, y_peak, x_at_peak, end_index_for_skip
    If lick missing -> (None, nan, nan, nan, None)
    """
    lo_ms, hi_ms = win_ms
    i0 = int(np.searchsorted(t_ms, lo_ms, side="left"))
    i1 = int(np.searchsorted(t_ms, hi_ms, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms)-1))
    i1 = max(0, min(i1, len(t_ms)-1))
    if i1 < i0:
        i0, i1 = i1, i0

    xseg0 = np.asarray(xw[i0:i1+1], float)
    yseg0 = np.asarray(yw[i0:i1+1], float)
    if not np.any(np.isfinite(yseg0)):
        return [(None, np.nan, np.nan, np.nan, None),
                (None, np.nan, np.nan, np.nan, None)]

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

    def detect_one(start_idx):
        r0, r1 = _first_run_from(rise_mask, rise_min_f, start=start_idx)
        if r0 is None:
            if STRICT_NO_FALLBACK:
                return (None, np.nan, np.nan, np.nan, None)

        if r0 is None and not STRICT_NO_FALLBACK:
            j = int(np.nanargmax(np.abs(yseg0))) if FAIL_FALLBACK == "max_abs" else int(np.nanargmax(yseg0))
            i_peak = i0 + j
            return (i_peak, float(t_ms[i_peak]), float(yw[i_peak]), float(xw[i_peak]), j)

        k = r1
        while k < L and (not np.isfinite(dy[k]) or dy[k] > 0):
            k += 1
        if k >= L:
            if STRICT_NO_FALLBACK:
                return (None, np.nan, np.nan, np.nan, None)
            j = int(np.nanargmax(np.abs(yseg0))) if FAIL_FALLBACK == "max_abs" else int(np.nanargmax(yseg0))
            i_peak = i0 + j
            return (i_peak, float(t_ms[i_peak]), float(yw[i_peak]), float(xw[i_peak]), j)

        seg_lo = r0
        seg_hi = min(L - 1, k + pad_f)
        seg = yseg0[seg_lo:seg_hi+1]
        if not np.any(np.isfinite(seg)):
            if STRICT_NO_FALLBACK:
                return (None, np.nan, np.nan, np.nan, None)
            j = int(np.nanargmax(np.abs(yseg0))) if FAIL_FALLBACK == "max_abs" else int(np.nanargmax(yseg0))
            i_peak = i0 + j
            return (i_peak, float(t_ms[i_peak]), float(yw[i_peak]), float(xw[i_peak]), j)

        j_local = int(np.nanargmax(seg))
        j_peak = seg_lo + j_local

        end_idx = j_peak
        if fall_min_f > 1:
            f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
            if f0 is None:
                if STRICT_NO_FALLBACK:
                    return (None, np.nan, np.nan, np.nan, None)
            else:
                end_idx = max(end_idx, f1 - 1)

        ypk = float(yseg0[j_peak])
        if (MIN_PEAK_Y_ABS is not None) and (abs(ypk) < MIN_PEAK_Y_ABS):
            if STRICT_NO_FALLBACK:
                return (None, np.nan, np.nan, np.nan, None)
            j = int(np.nanargmax(np.abs(yseg0))) if FAIL_FALLBACK == "max_abs" else int(np.nanargmax(yseg0))
            i_peak = i0 + j
            return (i_peak, float(t_ms[i_peak]), float(yw[i_peak]), float(xw[i_peak]), j)

        i_peak = i0 + j_peak
        return (i_peak, float(t_ms[i_peak]), float(yw[i_peak]), float(xw[i_peak]), end_idx)

    l1 = detect_one(start_idx=0)
    start2 = (l1[4] + 1) if (l1[4] is not None) else L
    l2 = detect_one(start_idx=int(start2))
    return [l1, l2]

# ---------- plotting ----------
def _plot_session_series(df_sess_in, metric_mean_col, metric_sem_col, n_col,
                         ylabel, title, out_path_png,
                         stroke_dt, min_detected_trials_to_plot=0,
                         show_stroke_divider=True):
    # plotting filter only; CSVs remain unchanged
    df_plot = df_sess_in.copy()
    if min_detected_trials_to_plot is not None and min_detected_trials_to_plot > 0:
        df_plot = df_plot[df_plot[n_col].fillna(0) >= int(min_detected_trials_to_plot)].copy()

    if df_plot.empty:
        print(f"[skip] No sessions met plotting threshold for {metric_mean_col} ({n_col} >= {min_detected_trials_to_plot}).")
        return

    fig, ax = plt.subplots(figsize=(11, 4))
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT

    # dot size absolute reference
    nmax_for_size = float(DOT_SIZE_N_MAX) if (DOT_SIZE_N_MAX is not None) else float(np.nanmax(df_plot[n_col].to_numpy(float)))

    for side in PLOT_SIDES:
        dd = df_plot[df_plot["side"] == side].copy()
        if dd.empty:
            continue

        if use_rel_day_axis:
            dd = dd.sort_values("rel_day").reset_index(drop=True)
            x = dd["rel_day"].to_numpy(float)
        else:
            dd = dd.sort_values("date_dt").reset_index(drop=True)
            x = dd["date_dt"].to_list()

        m   = dd[metric_mean_col].to_numpy(float)
        s   = dd[metric_sem_col].to_numpy(float)
        rel = dd["rel_day"].to_numpy(float)

        dot_colors = _session_dot_colors_from_rel_days(rel, cmap_name=POST_CMAP, pre_color=PRE_COLOR)
        sizes = _dot_sizes_from_n_absolute(dd[n_col].to_numpy(float),
                                           n_max=nmax_for_size,
                                           smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX,
                                           mode=DOT_SIZE_MODE)

        side_c = SIDE_COLORS.get(side, "k")
        ax.plot(x, m, color=side_c, alpha=LINE_ALPHA, label=f"{side} trials", zorder=2)
        ax.scatter(x, m, c=dot_colors, s=sizes, alpha=DOT_ALPHA, zorder=3, edgecolors="none")

        ok = np.isfinite(m) & np.isfinite(s)
        if np.any(ok):
            x_ok = np.array(x)[ok]
            ax.fill_between(x_ok, m[ok] - s[ok], m[ok] + s[ok], color=side_c, alpha=SEM_ALPHA, lw=0, zorder=1)

    if use_rel_day_axis and show_stroke_divider:
        ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9, zorder=0)

        x_all = df_plot["rel_day"].to_numpy(float)
        x_all = x_all[np.isfinite(x_all)]
        if x_all.size > 0:
            xmin = int(np.floor(np.min(x_all)))
            xmax = int(np.ceil(np.max(x_all)))
            all_days = np.arange(xmin, xmax + 1, 1)
            ax.set_xticks(all_days)

            label_set = set(int(v) for v in all_days if (int(v) % 7 == 0))
            label_set.add(0)

            def _fmt_day(v, pos):
                iv = int(np.round(v))
                if abs(v - iv) > 1e-6:
                    return ""
                return f"{iv}" if iv in label_set else ""

            ax.xaxis.set_major_formatter(FuncFormatter(_fmt_day))
        ax.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    else:
        ax.set_xlabel("Session date")

    ax.set_title(title + f" | plotted sessions require ≥{min_detected_trials_to_plot} detected trials")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.2)

    # ----- SINGLE 2-column legend block in loc="best" -----
    side_handles, side_labels = [], []
    for side in PLOT_SIDES:
        c = SIDE_COLORS.get(side, "k")
        side_handles.append(Line2D([0], [0], color=c, lw=2.2, alpha=0.9))
        side_labels.append(f"{side} trials")

    size_handles = _dot_size_legend_handles_absolute(
        LEGEND_N_EXAMPLES, n_max=nmax_for_size,
        smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX, mode=DOT_SIZE_MODE,
        color="0.4"
    )
    size_labels = [h.get_label() for h in size_handles]

    n_rows = max(len(side_handles), len(size_handles))
    blank = Line2D([0], [0], linestyle="None", marker=None, alpha=0.0)

    side_handles_pad = side_handles + [blank] * (n_rows - len(side_handles))
    side_labels_pad  = side_labels  + [""]    * (n_rows - len(side_labels))

    size_handles_pad = size_handles + [blank] * (n_rows - len(size_handles))
    size_labels_pad  = size_labels  + [""]    * (n_rows - len(size_labels))

    legend_handles = side_handles_pad + size_handles_pad
    legend_labels  = side_labels_pad  + size_labels_pad

    ax.legend(
        legend_handles,
        legend_labels,
        ncol=2,
        loc="best",
        frameon=False,
        handlelength=2.2,
        handletextpad=0.6,
        columnspacing=1.6,
        borderaxespad=0.4,
    )

    plt.tight_layout()

    if SAVE_FIGS:
        fig.savefig(out_path_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_path_png}")

    plt.show()
    plt.close(fig)

# ===================== RUN (MULTI-MOUSE) =====================
mice = list(MOUSE_SPECS.keys()) if (MICE_TO_RUN is None) else list(MICE_TO_RUN)

for MOUSE in mice:
    if MOUSE not in MOUSE_SPECS:
        print(f"[skip] {MOUSE} not in MOUSE_SPECS")
        continue

    spec = dict(MOUSE_SPECS[MOUSE])
    DATE_START = spec["date_start"]
    DATE_END   = spec["date_end"]
    STROKE_DATE = spec.get("d0", None)
    INCLUDE_DATES = set(spec.get("include_dates") or [])
    EXCLUDE_DATES = set(spec.get("exclude_dates") or [])

    print("\n" + "="*90)
    print(f"[mouse] {MOUSE} | dates {DATE_START}..{DATE_END} | d0={STROKE_DATE}")

    # output folders (per mouse)
    BASE_FIG_DIR = OUT_ROOT / MOUSE / f"{MOUSE}_tongue_kinematics" / "kinematics_figures" / f"{CENTER_MODE}" / "lick_metrics"
    FIG_DIR_FIRST  = BASE_FIG_DIR / "firstlick_metrics"
    FIG_DIR_SECOND = BASE_FIG_DIR / "secondlick_metrics"
    FIG_DIR_FIRST.mkdir(parents=True, exist_ok=True)
    FIG_DIR_SECOND.mkdir(parents=True, exist_ok=True)

    # locate files
    available, sess_dir = list_session_npzs_v5_only(MOUSE, CAM)

    # choose dates
    if INCLUDE_DATES:
        dates = sorted([d for d in INCLUDE_DATES if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
    dates = [d for d in dates if d not in EXCLUDE_DATES]

    if not dates:
        some = sorted(available.keys())
        print(
            "[warn] No sessions matched.\n"
            f"  Folder: {sess_dir}\n"
            f"  Available {INTERP_VERSION} dates (first 60): {some[:60]}\n"
            f"  Selection: start={DATE_START}, end={DATE_END}, include={sorted(INCLUDE_DATES)}, exclude={sorted(EXCLUDE_DATES)}"
        )
        continue

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        print("[warn] After pre/post stroke filtering, no sessions remain.")
        continue

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    print(f"[info] sessions to analyze ({len(dates)}): {dates}")
    print(f"[info] PLOT_SIDES={PLOT_SIDES}  PLOT_WIN_MS={PLOT_WIN_MS}  DETECT_WIN_MS={DETECT_WIN_MS}  USE_SRC={USE_SRC}")

    # ---------- compute per-trial + per-session summaries ----------
    trial_rows = []
    sess_rows  = []

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

            if centers.size == 0:
                sess_rows.append(dict(
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side, n_trials=0,
                    n_detected_lick1=0, frac_detected_lick1=0.0,
                    n_detected_lick2=0, frac_detected_lick2=0.0,
                    src=src_label, npz=str(p_npz),

                    lick1_t_peak_ms_mean=np.nan, lick1_t_peak_ms_sem=np.nan,
                    lick1_y_peak_mean=np.nan,    lick1_y_peak_sem=np.nan,
                    lick1_x_at_ypeak_mean=np.nan, lick1_x_at_ypeak_sem=np.nan,

                    lick2_t_peak_ms_mean=np.nan, lick2_t_peak_ms_sem=np.nan,
                    lick2_y_peak_mean=np.nan,    lick2_y_peak_sem=np.nan,
                    lick2_x_at_ypeak_mean=np.nan, lick2_x_at_ypeak_sem=np.nan,
                ))
                continue

            l1_t, l1_y, l1_x = [], [], []
            l2_t, l2_y, l2_x = [], [], []

            for k, c in enumerate(centers):
                c = int(c)
                yw = _snippet(y, c, pre_f, post_f)
                xw = _snippet(x, c, pre_f, post_f)

                (i1, t1, y1, x1, end1), (i2, t2, y2, x2, end2) = _detect_first_two_lick_peaks_dydt(
                    xw, yw, fps, DETECT_WIN_MS, t_ms
                )

                if i1 is None or (not np.isfinite(t1)) or (not np.isfinite(y1)) or (not np.isfinite(x1)):
                    t1 = np.nan; y1 = np.nan; x1 = np.nan
                if i2 is None or (not np.isfinite(t2)) or (not np.isfinite(y2)) or (not np.isfinite(x2)):
                    t2 = np.nan; y2 = np.nan; x2 = np.nan

                trial_rows.append(dict(
                    mouse=MOUSE,
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side, trial_index=int(k), reward_center_fr=int(c),
                    fps=float(fps), src=src_label, npz=str(p_npz),

                    lick1_t_peak_ms=float(t1),
                    lick1_y_peak=float(y1),
                    lick1_x_at_ypeak=float(x1),

                    lick2_t_peak_ms=float(t2),
                    lick2_y_peak=float(y2),
                    lick2_x_at_ypeak=float(x2),
                ))

                l1_t.append(t1); l1_y.append(y1); l1_x.append(x1)
                l2_t.append(t2); l2_y.append(y2); l2_x.append(x2)

            l1_t_mean, l1_t_sem, _ = _mean_sem_1d(l1_t)
            l1_y_mean, l1_y_sem, _ = _mean_sem_1d(l1_y)
            l1_x_mean, l1_x_sem, _ = _mean_sem_1d(l1_x)

            l2_t_mean, l2_t_sem, _ = _mean_sem_1d(l2_t)
            l2_y_mean, l2_y_sem, _ = _mean_sem_1d(l2_y)
            l2_x_mean, l2_x_sem, _ = _mean_sem_1d(l2_x)

            n_trials = int(len(centers))
            n_detected_lick1 = int(np.sum(np.isfinite(l1_t)))
            n_detected_lick2 = int(np.sum(np.isfinite(l2_t)))

            sess_rows.append(dict(
                mouse=MOUSE,
                date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                side=side, n_trials=n_trials,
                n_detected_lick1=n_detected_lick1, frac_detected_lick1=(n_detected_lick1 / max(1, n_trials)),
                n_detected_lick2=n_detected_lick2, frac_detected_lick2=(n_detected_lick2 / max(1, n_trials)),
                src=src_label, npz=str(p_npz),

                lick1_t_peak_ms_mean=l1_t_mean, lick1_t_peak_ms_sem=l1_t_sem,
                lick1_y_peak_mean=l1_y_mean,    lick1_y_peak_sem=l1_y_sem,
                lick1_x_at_ypeak_mean=l1_x_mean, lick1_x_at_ypeak_sem=l1_x_sem,

                lick2_t_peak_ms_mean=l2_t_mean, lick2_t_peak_ms_sem=l2_t_sem,
                lick2_y_peak_mean=l2_y_mean,    lick2_y_peak_sem=l2_y_sem,
                lick2_x_at_ypeak_mean=l2_x_mean, lick2_x_at_ypeak_sem=l2_x_sem,
            ))

    df_trials = pd.DataFrame(trial_rows)
    df_sess   = pd.DataFrame(sess_rows).sort_values(["date_dt","side"]).reset_index(drop=True)

    print("\n[session summaries]")
    cols_show = [
        "date","rel_day","side","n_trials",
        "n_detected_lick1","lick1_t_peak_ms_mean",
        "n_detected_lick2","lick2_t_peak_ms_mean",
    ]
    if not df_sess.empty:
        print(df_sess[cols_show].to_string(index=False))
    else:
        print("[warn] empty df_sess")

    side_str = ",".join(PLOT_SIDES)
    detect_str = f"detect={DETECT_WIN_MS[0]}–{DETECT_WIN_MS[1]}ms | plot={PLOT_WIN_MS[0]}–{PLOT_WIN_MS[1]}ms"
    src_str = f"v5 {USE_SRC}"

    # ---------- FIRST LICK plots ----------
    if DO_PLOT_TIME:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick1_t_peak_ms_mean",
            metric_sem_col="lick1_t_peak_ms_sem",
            n_col="n_detected_lick1",
            ylabel="Time of detected 1st Y peak (ms)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 1 | mean±SEM",
            out_path_png=FIG_DIR_FIRST / f"{MOUSE}_{CAM}_firstlick_tpeak_time_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    if DO_PLOT_Y:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick1_y_peak_mean",
            metric_sem_col="lick1_y_peak_sem",
            n_col="n_detected_lick1",
            ylabel="Y at detected peak (px)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 1 | mean±SEM",
            out_path_png=FIG_DIR_FIRST / f"{MOUSE}_{CAM}_firstlick_ypeak_y_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    if DO_PLOT_X:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick1_x_at_ypeak_mean",
            metric_sem_col="lick1_x_at_ypeak_sem",
            n_col="n_detected_lick1",
            ylabel="X at detected Y-peak time (px)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 1 | mean±SEM",
            out_path_png=FIG_DIR_FIRST / f"{MOUSE}_{CAM}_firstlick_ypeak_x_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    # ---------- SECOND LICK plots ----------
    if DO_PLOT_TIME:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick2_t_peak_ms_mean",
            metric_sem_col="lick2_t_peak_ms_sem",
            n_col="n_detected_lick2",
            ylabel="Time of detected 2nd Y peak (ms)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 2 | mean±SEM",
            out_path_png=FIG_DIR_SECOND / f"{MOUSE}_{CAM}_secondlick_tpeak_time_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    if DO_PLOT_Y:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick2_y_peak_mean",
            metric_sem_col="lick2_y_peak_sem",
            n_col="n_detected_lick2",
            ylabel="Y at detected peak (px)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 2 | mean±SEM",
            out_path_png=FIG_DIR_SECOND / f"{MOUSE}_{CAM}_secondlick_ypeak_y_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    if DO_PLOT_X:
        _plot_session_series(
            df_sess,
            metric_mean_col="lick2_x_at_ypeak_mean",
            metric_sem_col="lick2_x_at_ypeak_sem",
            n_col="n_detected_lick2",
            ylabel="X at detected Y-peak time (px)",
            title=f"{MOUSE} {CAM} | {src_str} | {side_str} | {detect_str} | LICK 2 | mean±SEM",
            out_path_png=FIG_DIR_SECOND / f"{MOUSE}_{CAM}_secondlick_ypeak_x_{DATE_START}-{DATE_END}_meanSEM_{INTERP_VERSION}.png",
            stroke_dt=stroke_dt,
            min_detected_trials_to_plot=MIN_DETECTED_TRIALS_TO_PLOT,
        )

    print("[ok] plotting done for", MOUSE)

    # ---------- saves ----------
    if SAVE_TABLES:
        # per-mouse CSVs into BOTH folders (same as your single-mouse version)
        df_trials.to_csv(FIG_DIR_FIRST / f"{MOUSE}_{CAM}_lick1lick2_pertrial_{INTERP_VERSION}.csv", index=False)
        df_sess.to_csv(FIG_DIR_FIRST / f"{MOUSE}_{CAM}_lick1lick2_persession_meanSEM_{INTERP_VERSION}.csv", index=False)

        df_trials.to_csv(FIG_DIR_SECOND / f"{MOUSE}_{CAM}_lick1lick2_pertrial_{INTERP_VERSION}.csv", index=False)
        df_sess.to_csv(FIG_DIR_SECOND / f"{MOUSE}_{CAM}_lick1lick2_persession_meanSEM_{INTERP_VERSION}.csv", index=False)

        print(f"[save] {FIG_DIR_FIRST / f'{MOUSE}_{CAM}_lick1lick2_pertrial_{INTERP_VERSION}.csv'}")
        print(f"[save] {FIG_DIR_FIRST / f'{MOUSE}_{CAM}_lick1lick2_persession_meanSEM_{INTERP_VERSION}.csv'}")

print("\n[ok] all mice done")

