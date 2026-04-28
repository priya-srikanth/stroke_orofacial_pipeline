"""Vendored from
//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Cells 33, 36, 39, 42, 50.

Captured for Phase 7a.3 — 2026-04-28 from the MICROSCOPE share at
\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\.
The Mac path /Users/Priya2/Github/facerhythm_stroke_biomarker_exp_Priya/
referenced in CLAUDE.md is the legacy-repo equivalent for Mac sessions;
both paths reference the same canonical notebook content.

3-tier-rule disambiguation: the parent notebook is the same canonical
20260203 tongue notebook 7a.2 vendored Cell 23 from. Cells 33/36/39/42/50
are downstream of Cell 23 in the same notebook. No sibling notebooks
contain alternative implementations of these per-trial features
(reward-aligned-parquet siblings exist for upstream parquet-build work
but do NOT contain per-trial scalar / angle cells).

Source SHA256: ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643
Source size: 403,798,697 B
Cells included:
  - Cell 33 (795 lines, SHA256 936245f159624fa4...): lick1/lick2 first-peak slope detector (CSV writer)
  - Cell 36 (1020 lines, SHA256 3359bf7104685cd4...): per-lick peak velocity, first 5 licks per trial (NPZ + CSV writer)
  - Cell 39 (1144 lines, SHA256 561f5ee9c3b729c6...): licks-per-trial counter (n_licks per trial, plus directional + binned variants)
  - Cell 42 (827 lines, SHA256 986d008ab6fd41c5...): within-bout ILI rate / lick rate / probability traces (per-session time-binned, CSV)
  - Cell 50 (1592 lines, SHA256 940f172a996002f4...): per-frame tongue angle in spout-centered frame; per-bout/per-peak angle rows (3 CSVs)

Cells excluded (and why):
  - All plot-velocity-traces / plot-amplitude-distribution / plot-
    angle-phase-exploratory cells: Exploratory, inspection-only.
    Saved figures from these cells live on MICROSCOPE; Cell 50
    visual parity is comparison against those saved figures.
  - Any cell containing _v0/_mod/_old-suffixed helpers: Deprecated.
  - Cell 41 (jaw notebook stats cell consuming files the jaw notebook
    never produces — confirmed by audit): N/A; this file is tongue-only.

DO NOT edit, reformat, or lint this file. # ruff: noqa, # fmt: off
preserve byte-identity with capture time.
"""
# ruff: noqa
# fmt: off

# %% Cell 33 (lines=795, sha256=936245f159624fa43dd2cfd4643a2db2cde719a7dd63763fee1bf9ae97889d5f)
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

# %% Cell 36 (lines=1020, sha256=3359bf7104685cd44ae7ed8cf74d9be07a7074ffe85efc03298014027dd8998d)
# ===== Multi-ANIMAL Multi-lick PEAK-VELOCITY metrics (v5, dY/dt method) =====
# - Per-animal date ranges + stroke dates
# - Same plotting rules: integer rel-day ticks, label every 7th + always 0; stroke divider at 0.5
# - Broken y-axis when exceeding thresholds; legend on LOWER axis
#
# UPDATED:
# - Plot-only filter: sessions must have >= MIN_DETECTED_TO_PLOT for the relevant metric
# - CSV/NPZ still save ALL sessions/trials
# - Legend dot-size examples updated to [10, 25, 50]

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== GLOBAL KNOBS =====================
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- which reward trials to include in plots ----
PLOT_SIDES = ("L", "R")

# ---- windows ----
PLOT_WIN_MS       = (-200.0, 4000.0)
VEL_DETECT_WIN_MS = (70.0, 3000.0)

# ---- lick detector settings ----
RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0
PEAK_PAD_MS = 52.0

# ---- how many licks ----
N_LICKS = 5

# ---- velocity validity requirement ----
MIN_FINITE_SAMPLES_PER_LICK = 5

# ---- smoothing ----
DO_SMOOTH_DETECT = False
SMOOTH_MS_DETECT = 12.0

DO_SMOOTH_VEL    = True
SMOOTH_MS_VEL    = 12.0

# ---- pre/post stroke labeling + filtering ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"      # "pre", "post", "both", or "all"
REL_DAY_RANGE = None       # None or (min_day, max_day) inclusive

# ---- plots ----
DO_PLOT_VY  = True
DO_PLOT_VXY = True

# ---- NEW: plot-only minimum detected count filter ----
# Applied to the relevant n_col for each figure:
#   trialmax plots use n_valid_trials_vy / n_valid_trials_vxy
#   all_licks plots use n_valid_licks_vy / n_valid_licks_vxy
# Sessions below threshold remain in saved CSV/NPZ tables.
MIN_DETECTED_TO_PLOT = 15

# ---- dot size scaling by n_detected (ABSOLUTE) ----
DOT_SIZE_MIN  = 10
DOT_SIZE_MAX  = 50
DOT_SIZE_MODE = "linear"   # "linear" or "sqrt"
LEGEND_N_EXAMPLES = [10, 25, 50]
DOT_SIZE_N_MAX = 50         # absolute ref for dot sizes (None -> per-animal max)

# ---- COLORS / ALPHAS ----
SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}
PRE_COLOR   = "0.6"
POST_CMAP   = "plasma"

LINE_ALPHA  = 0.45
DOT_ALPHA   = 0.95
SEM_ALPHA   = 0.12

# ---- DEFAULT broken-axis thresholds ----
BREAK_THR_TRIALMAX_DEFAULT = 12000.0   # trialmax
BREAK_THR_ALLLICKS_DEFAULT = 9000.0    # all_licks

# ---- saving ----
SAVE_FIGS = True
FIG_DPI = 200

SAVE_TABLES = True
SAVE_NPZ    = True

# ===================== PER-ANIMAL CONFIG =====================
# Each mouse can override: date_start/date_end/stroke_date/include_dates/exclude_dates/break thresholds
ANIMALS = {
    "PS46": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS47": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS48": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS49": dict(
        date_start="20250310",
        date_end="20250406",
        stroke_date="20250317",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS50": dict(
        date_start="20250319",
        date_end="20250406",
        stroke_date="20250323",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS51": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250429",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=9000.0,
        break_thr_alllicks=7000.0,
    ),
    "PS54": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
    "PS55": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        include_dates=set(),
        exclude_dates=set(),
        break_thr_trialmax=12000.0,
        break_thr_alllicks=9000.0,
    ),
}

# Optionally: where to put multi-animal outputs (inside each mouse folder, like your other pipelines)
OUT_SUBFOLDER = "velocity_metrics"  # under .../kinematics_figures/<CENTER_MODE>/
# ============================================================


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

def list_session_npzs_v5_only(mouse, cam, interp_version):
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
        rf"^{re.escape(mouse)}_(?P<date>\d{{8}})_{re.escape(cam)}_tongue_interp_{interp_version}\.npz$"
    )

    available = {}
    for p in sorted(sess_dir.glob(f"{mouse}_*_{cam}_tongue_interp_{interp_version}.npz")):
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

def _make_legend_block(ax, nmax_for_size, loc="upper right", bbox_to_anchor=None):
    """Single 2-column legend block, column-major ordering."""
    side_handles = []
    side_labels  = []
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
        loc=loc,
        bbox_to_anchor=bbox_to_anchor,
        frameon=False,
        handlelength=2.2,
        handletextpad=0.6,
        columnspacing=1.6,
        borderaxespad=0.4,
    )

def _apply_rel_day_ticks_mark_all_label_every_k(ax, x_all, step=7):
    x_all = np.asarray(x_all, float)
    x_all = x_all[np.isfinite(x_all)]
    if x_all.size == 0:
        return
    xmin = int(np.floor(np.min(x_all)))
    xmax = int(np.ceil(np.max(x_all)))
    ticks = np.arange(xmin, xmax + 1, 1)
    ax.set_xticks(ticks)
    labels = []
    for t in ticks:
        if (t == 0) or (t % int(step) == 0):
            labels.append(str(int(t)))
        else:
            labels.append("")
    ax.set_xticklabels(labels)

def _draw_break_marks(ax_top, ax_bot, size=0.008):
    kwargs = dict(transform=ax_top.transAxes, color="k", clip_on=False, lw=1.0)
    ax_top.plot((-size, +size), (-size, +size), **kwargs)
    ax_top.plot((1 - size, 1 + size), (-size, +size), **kwargs)
    kwargs = dict(transform=ax_bot.transAxes, color="k", clip_on=False, lw=1.0)
    ax_bot.plot((-size, +size), (1 - size, 1 + size), **kwargs)
    ax_bot.plot((1 - size, 1 + size), (1 - size, 1 + size), **kwargs)

def _style_broken_axis_blank_gap(ax_top, ax_bot, d=0.008):
    ax_top.spines["bottom"].set_visible(False)
    ax_bot.spines["top"].set_visible(False)
    ax_top.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    ax_bot.tick_params(axis="x", which="both", top=False, labeltop=False)
    ax_top.tick_params(axis="y", which="both", bottom=False)
    ax_bot.tick_params(axis="y", which="both", top=False)
    ax_top.minorticks_off()
    ax_bot.minorticks_off()
    ax_top.grid(False)
    kwargs = dict(transform=ax_top.transAxes, color="k", clip_on=False, lw=1.1)
    ax_top.plot((-d, +d), (-d, +d), **kwargs)
    ax_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)
    kwargs.update(transform=ax_bot.transAxes)
    ax_bot.plot((-d, +d), (1 - d, 1 + d), **kwargs)
    ax_bot.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

def _detect_first_n_licks_and_vel(xw, yw, fps, t_ms, win_ms,
                                 n_licks=5,
                                 slope_thr=SLOPE_THR_PX_PER_S,
                                 rise_min_ms=RISE_MIN_MS,
                                 fall_min_ms=FALL_MIN_MS,
                                 peak_pad_ms=PEAK_PAD_MS,
                                 do_smooth_detect=False, smooth_ms_detect=12.0,
                                 do_smooth_vel=False, smooth_ms_vel=12.0,
                                 min_finite_samples=5):
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
        return [], np.full(n_licks, np.nan), np.full(n_licks, np.nan)

    # detection dy/dt
    y_det = yseg0.copy()
    if do_smooth_detect and (smooth_ms_detect is not None) and (smooth_ms_detect > 0):
        w = max(1, _ms_to_frames(smooth_ms_detect, fps))
        if w >= 3:
            y_det = _moving_average_nan(y_det, w)

    dt_s = 1.0 / fps
    dy_det = np.gradient(y_det) / dt_s

    finite_det = np.isfinite(y_det) & np.isfinite(dy_det) & np.isfinite(xseg0)
    rise_mask = finite_det & (dy_det > +slope_thr)
    fall_mask = finite_det & (dy_det < -slope_thr)

    rise_min_f = max(1, _ms_to_frames(rise_min_ms, fps))
    fall_min_f = max(1, _ms_to_frames(fall_min_ms, fps))
    pad_f      = max(0, _ms_to_frames(peak_pad_ms, fps))

    # velocity derivatives (optional smoothing)
    x_vel = xseg0.copy()
    y_vel = yseg0.copy()
    if do_smooth_vel and (smooth_ms_vel is not None) and (smooth_ms_vel > 0):
        wv = max(1, _ms_to_frames(smooth_ms_vel, fps))
        if wv >= 3:
            x_vel = _moving_average_nan(x_vel, wv)
            y_vel = _moving_average_nan(y_vel, wv)

    dx_vel = np.gradient(x_vel) / dt_s
    dy_vel = np.gradient(y_vel) / dt_s
    vxy_vel = np.sqrt(dx_vel**2 + dy_vel**2)

    lick_info = []
    vy_peaks  = np.full(n_licks, np.nan, float)
    vxy_peaks = np.full(n_licks, np.nan, float)

    start = 0
    L = len(yseg0)

    for ell in range(n_licks):
        r0, r1 = _first_run_from(rise_mask, rise_min_f, start=start)
        if r0 is None:
            break

        k = r1
        while k < L and (not np.isfinite(dy_det[k]) or dy_det[k] > 0):
            k += 1
        if k >= L:
            break

        seg_lo = r0
        seg_hi = min(L - 1, k + pad_f)
        seg = yseg0[seg_lo:seg_hi+1]
        if not np.any(np.isfinite(seg)):
            start = seg_hi + 1
            continue

        j_local = int(np.nanargmax(seg))
        j_peak = seg_lo + j_local

        end_idx = j_peak
        f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
        if f0 is not None:
            end_idx = max(end_idx, f1 - 1)

        vel_lo = r0
        vel_hi = min(L - 1, k)
        vel_ok = np.isfinite(dx_vel[vel_lo:vel_hi+1]) & np.isfinite(dy_vel[vel_lo:vel_hi+1])
        if int(np.sum(vel_ok)) >= int(min_finite_samples):
            vy_peaks[ell]  = float(np.nanmax(dy_vel[vel_lo:vel_hi+1]))
            vxy_peaks[ell] = float(np.nanmax(vxy_vel[vel_lo:vel_hi+1]))
        else:
            vy_peaks[ell]  = np.nan
            vxy_peaks[ell] = np.nan

        lick_info.append(dict(
            seg_i0=int(i0), seg_i1=int(i1),
            i_rise0=int(i0 + r0),
            i_turn=int(i0 + k),
            i_ypeak=int(i0 + j_peak),
            i_end=int(i0 + end_idx),
        ))

        start = int(end_idx + 1)
        if start >= L:
            break

    return lick_info, vy_peaks, vxy_peaks


# ---------- plotting helpers ----------
def _collect_y_range_for_metric(df_sess_in, mean_col, sem_col):
    v = []
    for side in PLOT_SIDES:
        dd = df_sess_in[df_sess_in["side"] == side]
        if dd.empty:
            continue
        m = dd[mean_col].to_numpy(float)
        s = dd[sem_col].to_numpy(float)
        ok = np.isfinite(m)
        if np.any(ok):
            if np.any(np.isfinite(s)):
                v.append(m[ok] + np.nan_to_num(s[ok], nan=0.0))
                v.append(m[ok] - np.nan_to_num(s[ok], nan=0.0))
            else:
                v.append(m[ok])
    if not v:
        return np.nan, np.nan
    vv = np.concatenate([np.ravel(x) for x in v])
    vv = vv[np.isfinite(vv)]
    if vv.size == 0:
        return np.nan, np.nan
    return float(np.min(vv)), float(np.max(vv))

def _plot_session_series(df_sess_in, stroke_dt, mean_col, sem_col, n_col,
                         ylabel, title, out_png,
                         break_threshold=None,
                         min_detected_to_plot=0):

    # plot-only filter
    df_plot = df_sess_in.copy()
    if min_detected_to_plot is not None and min_detected_to_plot > 0:
        df_plot = df_plot[df_plot[n_col].fillna(0) >= int(min_detected_to_plot)].copy()

    if df_plot.empty:
        print(f"[skip] No sessions met plotting threshold for {mean_col} ({n_col} >= {min_detected_to_plot}).")
        return

    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT

    # dot-size absolute reference
    if DOT_SIZE_N_MAX is None:
        nmax_for_size = float(np.nanmax(df_plot[n_col].to_numpy(float))) if n_col in df_plot.columns else 1.0
        nmax_for_size = max(1.0, nmax_for_size)
    else:
        nmax_for_size = float(DOT_SIZE_N_MAX)

    y_min, y_max = _collect_y_range_for_metric(df_plot, mean_col, sem_col)
    need_break = (
        (break_threshold is not None)
        and np.isfinite(y_max)
        and (y_max > float(break_threshold))
    )

    if need_break:
        fig = plt.figure(figsize=(11, 4))
        gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[0.2, 0.8], hspace=0.05)
        ax_top = fig.add_subplot(gs[0, 0])
        ax_bot = fig.add_subplot(gs[1, 0], sharex=ax_top)
        _style_broken_axis_blank_gap(ax_top, ax_bot, d=0.008)
        axes_to_plot = (ax_top, ax_bot)
    else:
        fig, ax_bot = plt.subplots(figsize=(11, 4))
        ax_top = None
        axes_to_plot = (ax_bot,)

    for ax in axes_to_plot:
        for side in PLOT_SIDES:
            dd = df_plot[df_plot["side"] == side].copy()
            if dd.empty:
                continue

            if use_rel_day_axis:
                dd = dd.sort_values("rel_day").reset_index(drop=True)
                x_axis = dd["rel_day"].to_numpy(float)
            else:
                dd = dd.sort_values("date_dt").reset_index(drop=True)
                x_axis = dd["date_dt"].to_list()

            m   = dd[mean_col].to_numpy(float)
            s   = dd[sem_col].to_numpy(float)
            rel = dd["rel_day"].to_numpy(float)

            dot_colors = _session_dot_colors_from_rel_days(rel, cmap_name=POST_CMAP, pre_color=PRE_COLOR)
            sizes = _dot_sizes_from_n_absolute(
                dd[n_col].to_numpy(float),
                n_max=nmax_for_size,
                smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX, mode=DOT_SIZE_MODE
            )

            side_c = SIDE_COLORS.get(side, "k")
            ax.plot(x_axis, m, color=side_c, alpha=LINE_ALPHA, zorder=2)
            ax.scatter(x_axis, m, c=dot_colors, s=sizes, alpha=DOT_ALPHA, zorder=3, edgecolors="none")

            ok = np.isfinite(m) & np.isfinite(s)
            if np.any(ok):
                x_ok = np.array(x_axis)[ok]
                m_ok = m[ok]
                s_ok = s[ok]
                ax.fill_between(x_ok, m_ok - s_ok, m_ok + s_ok, color=side_c, alpha=SEM_ALPHA, lw=0, zorder=1)

        if use_rel_day_axis:
            ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9, zorder=0)
            _apply_rel_day_ticks_mark_all_label_every_k(ax, df_plot["rel_day"].to_numpy(float), step=7)
        ax.grid(True, alpha=0.2)

    # labels
    if use_rel_day_axis:
        ax_bot.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    else:
        ax_bot.set_xlabel("Session date")
    ax_bot.set_ylabel(ylabel)

    title_full = title + f" | plotted sessions require ≥{min_detected_to_plot}"
    if ax_top is None:
        ax_bot.set_title(title_full)
    else:
        ax_top.set_title(title_full)
        plt.setp(ax_top.get_xticklabels(), visible=False)

    # broken-axis y-lims + legend placement
    if need_break:
        thr = float(break_threshold)
        ylo = y_min if np.isfinite(y_min) else 0.0
        pad = 0.04 * (thr - ylo) if thr > ylo else 1.0
        ax_bot.set_ylim(ylo - pad, thr)

        yhi = y_max
        pad2 = 0.06 * (yhi - thr) if yhi > thr else 1.0
        ax_top.set_ylim(thr, yhi + pad2)

        _draw_break_marks(ax_top, ax_bot, size=0.010)
        _make_legend_block(ax_bot, nmax_for_size, loc="upper right", bbox_to_anchor=(1.0, 0.98))
    else:
        _make_legend_block(ax_bot, nmax_for_size, loc="best")

    plt.tight_layout()

    if SAVE_FIGS:
        fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_png}")

    plt.show()
    plt.close(fig)


# ===================== MAIN LOOP: animals =====================
all_trials = []
all_sess   = []
all_npz_paths = []

for mouse, cfg in ANIMALS.items():
    print("\n" + "="*80)
    print(f"[animal] {mouse}  CAM={CAM}  INTERP={INTERP_VERSION}")

    DATE_START = cfg["date_start"]
    DATE_END   = cfg["date_end"]
    INCLUDE_DATES = set(cfg.get("include_dates", set()) or set())
    EXCLUDE_DATES = set(cfg.get("exclude_dates", set()) or set())
    STROKE_DATE   = cfg.get("stroke_date", None)

    break_thr_trialmax = float(cfg.get("break_thr_trialmax", BREAK_THR_TRIALMAX_DEFAULT))
    break_thr_alllicks = float(cfg.get("break_thr_alllicks", BREAK_THR_ALLLICKS_DEFAULT))

    # ---- locate files (per-animal) ----
    available, sess_dir = list_session_npzs_v5_only(mouse, CAM, INTERP_VERSION)

    if INCLUDE_DATES:
        dates = sorted([d for d in INCLUDE_DATES if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
    dates = [d for d in dates if d not in EXCLUDE_DATES]

    if not dates:
        some = sorted(available.keys())
        raise RuntimeError(
            f"No sessions matched for {mouse}.\n"
            f"Folder: {sess_dir}\n"
            f"Available {INTERP_VERSION} dates (first 60): {some[:60]}\n"
            f"Your selection: start={DATE_START}, end={DATE_END}, include={sorted(INCLUDE_DATES)}, exclude={sorted(EXCLUDE_DATES)}"
        )

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        raise RuntimeError(f"After pre/post stroke filtering, no sessions remain for {mouse}.")

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    print(f"[info] sessions to analyze ({len(dates)}): {dates}")
    print(f"[info] N_LICKS={N_LICKS}  VEL_DETECT_WIN_MS={VEL_DETECT_WIN_MS}  stroke_align={USE_STROKE_ALIGNMENT}")

    # ---- output dirs (per-animal) ----
    BASE_DIR = (
        OUT_ROOT
        / mouse
        / f"{mouse}_tongue_kinematics"
        / "kinematics_figures"
        / f"{CENTER_MODE}"
        / OUT_SUBFOLDER
    )
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_OUT_DIR = BASE_DIR
    TABLE_DIR   = BASE_DIR
    NPZ_DIR     = BASE_DIR

    # ---- compute per-trial + per-session summaries (per-animal) ----
    trial_rows = []
    sess_rows  = []

    trial_index_global = 0
    npz_trial_meta = []
    npz_vy_licks  = []
    npz_vxy_licks = []

    for d in dates:
        p_npz = available[d]
        Z = np.load(p_npz, allow_pickle=True)

        fps = float(Z["fps"])
        n_frames = int(Z["n_frames"])

        x = Z["x_final"].astype(float)
        y = Z["y_final"].astype(float)

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
                    mouse=mouse, cam=CAM,
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side,
                    n_trials=0,

                    n_valid_trials_vy=0, n_valid_trials_vxy=0,
                    vy_trialmax_mean=np.nan, vy_trialmax_sem=np.nan,
                    vxy_trialmax_mean=np.nan, vxy_trialmax_sem=np.nan,

                    n_valid_licks_vy=0, n_valid_licks_vxy=0,
                    vy_alllicks_mean=np.nan, vy_alllicks_sem=np.nan,
                    vxy_alllicks_mean=np.nan, vxy_alllicks_sem=np.nan,

                    npz=str(p_npz),
                ))
                continue

            vy_trialmax  = []
            vxy_trialmax = []

            vy_all_licks  = []
            vxy_all_licks = []

            for k, c in enumerate(centers):
                c = int(c)
                yw = _snippet(y, c, pre_f, post_f)
                xw = _snippet(x, c, pre_f, post_f)

                lick_info, vy_peaks, vxy_peaks = _detect_first_n_licks_and_vel(
                    xw, yw, fps, t_ms, VEL_DETECT_WIN_MS,
                    n_licks=N_LICKS,
                    slope_thr=SLOPE_THR_PX_PER_S,
                    rise_min_ms=RISE_MIN_MS,
                    fall_min_ms=FALL_MIN_MS,
                    peak_pad_ms=PEAK_PAD_MS,
                    do_smooth_detect=DO_SMOOTH_DETECT,
                    smooth_ms_detect=SMOOTH_MS_DETECT,
                    do_smooth_vel=DO_SMOOTH_VEL,
                    smooth_ms_vel=SMOOTH_MS_VEL,
                    min_finite_samples=MIN_FINITE_SAMPLES_PER_LICK,
                )

                vy_max  = float(np.nanmax(vy_peaks))  if np.any(np.isfinite(vy_peaks))  else np.nan
                vxy_max = float(np.nanmax(vxy_peaks)) if np.any(np.isfinite(vxy_peaks)) else np.nan

                vy_trialmax.append(vy_max)
                vxy_trialmax.append(vxy_max)

                vy_all_licks.extend(list(np.asarray(vy_peaks, float)))
                vxy_all_licks.extend(list(np.asarray(vxy_peaks, float)))

                row = dict(
                    mouse=mouse, cam=CAM,
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side, trial_index=int(k), reward_center_fr=int(c),
                    fps=float(fps), npz=str(p_npz),
                    vy_trialmax=float(vy_max),
                    vxy_trialmax=float(vxy_max),
                )
                for j in range(N_LICKS):
                    row[f"vy_peak_lick{j+1}"]  = float(vy_peaks[j])  if j < len(vy_peaks)  else np.nan
                    row[f"vxy_peak_lick{j+1}"] = float(vxy_peaks[j]) if j < len(vxy_peaks) else np.nan

                row["vy_lickmean"]  = float(np.nanmean(vy_peaks))  if np.any(np.isfinite(vy_peaks))  else np.nan
                row["vxy_lickmean"] = float(np.nanmean(vxy_peaks)) if np.any(np.isfinite(vxy_peaks)) else np.nan

                trial_rows.append(row)

                # NPZ packing (per-animal file)
                npz_trial_meta.append(dict(
                    global_trial_index=int(trial_index_global),
                    mouse=str(mouse),
                    date=str(d),
                    rel_day=float(rel_day) if np.isfinite(rel_day) else np.nan,
                    side=str(side),
                    trial_index=int(k),
                    reward_center_fr=int(c),
                    fps=float(fps),
                    npz=str(p_npz),
                ))
                npz_vy_licks.append(np.asarray(vy_peaks, float))
                npz_vxy_licks.append(np.asarray(vxy_peaks, float))
                trial_index_global += 1

            n_trials = int(len(centers))

            # trialmax summary
            vy_tm_mean,  vy_tm_sem,  _ = _mean_sem_1d(vy_trialmax)
            vxy_tm_mean, vxy_tm_sem, _ = _mean_sem_1d(vxy_trialmax)
            n_valid_trials_vy  = int(np.sum(np.isfinite(vy_trialmax)))
            n_valid_trials_vxy = int(np.sum(np.isfinite(vxy_trialmax)))

            # all-licks summary
            vy_all  = np.asarray(vy_all_licks, float)
            vxy_all = np.asarray(vxy_all_licks, float)
            vy_al_mean,  vy_al_sem,  _ = _mean_sem_1d(vy_all)
            vxy_al_mean, vxy_al_sem, _ = _mean_sem_1d(vxy_all)
            n_valid_licks_vy  = int(np.sum(np.isfinite(vy_all)))
            n_valid_licks_vxy = int(np.sum(np.isfinite(vxy_all)))

            sess_rows.append(dict(
                mouse=mouse, cam=CAM,
                date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                side=side,
                n_trials=n_trials,

                # trialmax
                n_valid_trials_vy=n_valid_trials_vy,
                n_valid_trials_vxy=n_valid_trials_vxy,
                vy_trialmax_mean=float(vy_tm_mean),   vy_trialmax_sem=float(vy_tm_sem),
                vxy_trialmax_mean=float(vxy_tm_mean), vxy_trialmax_sem=float(vxy_tm_sem),

                # all-licks
                n_valid_licks_vy=n_valid_licks_vy,
                n_valid_licks_vxy=n_valid_licks_vxy,
                vy_alllicks_mean=float(vy_al_mean),   vy_alllicks_sem=float(vy_al_sem),
                vxy_alllicks_mean=float(vxy_al_mean), vxy_alllicks_sem=float(vxy_al_sem),

                npz=str(p_npz),
            ))

    df_trials = pd.DataFrame(trial_rows)
    df_sess   = pd.DataFrame(sess_rows).sort_values(["date_dt","side"]).reset_index(drop=True)

    print("\n[session summaries]")
    cols_show = [
        "mouse","date","rel_day","side","n_trials",
        "n_valid_trials_vy","vy_trialmax_mean","n_valid_licks_vy","vy_alllicks_mean",
        "n_valid_trials_vxy","vxy_trialmax_mean","n_valid_licks_vxy","vxy_alllicks_mean",
    ]
    print(df_sess[cols_show].to_string(index=False))

    # ---------- plots (per-animal) ----------
    side_str = ",".join(PLOT_SIDES)
    detect_str = f"licks={N_LICKS} | detect={VEL_DETECT_WIN_MS[0]}–{VEL_DETECT_WIN_MS[1]}ms | plot={PLOT_WIN_MS[0]}–{PLOT_WIN_MS[1]}ms"
    smooth_str = f"sd={int(DO_SMOOTH_DETECT)}({SMOOTH_MS_DETECT}ms)_sv={int(DO_SMOOTH_VEL)}({SMOOTH_MS_VEL}ms)"

    if DO_PLOT_VY:
        # trialmax
        _plot_session_series(
            df_sess_in=df_sess, stroke_dt=stroke_dt,
            mean_col="vy_trialmax_mean", sem_col="vy_trialmax_sem", n_col="n_valid_trials_vy",
            ylabel="Peak rise velocity dy/dt (px/s)",
            title=f"{mouse} {CAM} | y_final/x_final | {side_str} | {detect_str} | {smooth_str} | agg=trialmax | mean±SEM",
            out_png=FIG_OUT_DIR / f"{mouse}_{CAM}_peakVY_meanSEM_agg=trialmax_{DATE_START}-{DATE_END}.png",
            break_threshold=break_thr_trialmax,
            min_detected_to_plot=MIN_DETECTED_TO_PLOT,
        )
        # all_licks
        _plot_session_series(
            df_sess_in=df_sess, stroke_dt=stroke_dt,
            mean_col="vy_alllicks_mean", sem_col="vy_alllicks_sem", n_col="n_valid_licks_vy",
            ylabel="Peak rise velocity dy/dt (px/s)",
            title=f"{mouse} {CAM} | y_final/x_final | {side_str} | {detect_str} | {smooth_str} | agg=all_licks | mean±SEM",
            out_png=FIG_OUT_DIR / f"{mouse}_{CAM}_peakVY_meanSEM_agg=all_licks_{DATE_START}-{DATE_END}.png",
            break_threshold=break_thr_alllicks,
            min_detected_to_plot=MIN_DETECTED_TO_PLOT,
        )

    if DO_PLOT_VXY:
        # trialmax
        _plot_session_series(
            df_sess_in=df_sess, stroke_dt=stroke_dt,
            mean_col="vxy_trialmax_mean", sem_col="vxy_trialmax_sem", n_col="n_valid_trials_vxy",
            ylabel="Peak rise speed √(dx²+dy²)/dt (px/s)",
            title=f"{mouse} {CAM} | y_final/x_final | {side_str} | {detect_str} | {smooth_str} | agg=trialmax | mean±SEM",
            out_png=FIG_OUT_DIR / f"{mouse}_{CAM}_peakVXY_meanSEM_agg=trialmax_{DATE_START}-{DATE_END}.png",
            break_threshold=break_thr_trialmax,
            min_detected_to_plot=MIN_DETECTED_TO_PLOT,
        )
        # all_licks
        _plot_session_series(
            df_sess_in=df_sess, stroke_dt=stroke_dt,
            mean_col="vxy_alllicks_mean", sem_col="vxy_alllicks_sem", n_col="n_valid_licks_vxy",
            ylabel="Peak rise speed √(dx²+dy²)/dt (px/s)",
            title=f"{mouse} {CAM} | y_final/x_final | {side_str} | {detect_str} | {smooth_str} | agg=all_licks | mean±SEM",
            out_png=FIG_OUT_DIR / f"{mouse}_{CAM}_peakVXY_meanSEM_agg=all_licks_{DATE_START}-{DATE_END}.png",
            break_threshold=break_thr_alllicks,
            min_detected_to_plot=MIN_DETECTED_TO_PLOT,
        )

    # ---------- saves (per-animal) ----------
    if SAVE_TABLES:
        p_trials = TABLE_DIR / f"{mouse}_{CAM}_peakvel_pertrial_first{N_LICKS}_dydt_{INTERP_VERSION}.csv"
        p_sess   = TABLE_DIR / f"{mouse}_{CAM}_peakvel_persession_meanSEM_first{N_LICKS}_BOTHAGG_dydt_{INTERP_VERSION}.csv"
        df_trials.to_csv(p_trials, index=False)
        df_sess.to_csv(p_sess, index=False)
        print(f"[save] {p_trials}")
        print(f"[save] {p_sess}")

    if SAVE_NPZ:
        vy_licks  = np.vstack(npz_vy_licks)  if len(npz_vy_licks)  else np.zeros((0, N_LICKS), float)
        vxy_licks = np.vstack(npz_vxy_licks) if len(npz_vxy_licks) else np.zeros((0, N_LICKS), float)

        params = dict(
            mouse=mouse, cam=CAM,
            center_mode=CENTER_MODE,
            interp_version=INTERP_VERSION,
            date_start=DATE_START, date_end=DATE_END,
            include_dates=sorted(list(INCLUDE_DATES)),
            exclude_dates=sorted(list(EXCLUDE_DATES)),
            stroke_date=STROKE_DATE,
            plot_win_ms=PLOT_WIN_MS,
            vel_detect_win_ms=VEL_DETECT_WIN_MS,
            n_licks=N_LICKS,
            slope_thr_px_per_s=SLOPE_THR_PX_PER_S,
            rise_min_ms=RISE_MIN_MS,
            fall_min_ms=FALL_MIN_MS,
            peak_pad_ms=PEAK_PAD_MS,
            min_finite_samples_per_lick=MIN_FINITE_SAMPLES_PER_LICK,
            do_smooth_detect=DO_SMOOTH_DETECT,
            smooth_ms_detect=SMOOTH_MS_DETECT,
            do_smooth_vel=DO_SMOOTH_VEL,
            smooth_ms_vel=SMOOTH_MS_VEL,
            dot_size_n_max=DOT_SIZE_N_MAX,
            legend_n_examples=LEGEND_N_EXAMPLES,
            min_detected_to_plot=MIN_DETECTED_TO_PLOT,
            break_thr_trialmax=break_thr_trialmax,
            break_thr_alllicks=break_thr_alllicks,
            prepost_mode=PREPOST_MODE,
            rel_day_range=REL_DAY_RANGE,
        )

        p_npz_out = NPZ_DIR / f"{mouse}_{CAM}_peakvel_first{N_LICKS}_pertrial_lickresolved_BOTHAGG_{INTERP_VERSION}.npz"
        np.savez_compressed(
            p_npz_out,
            params=np.array([params], dtype=object),
            trial_meta=np.array(npz_trial_meta, dtype=object),
            vy_peaks_bylick=vy_licks,
            vxy_peaks_bylick=vxy_licks,
        )
        print(f"[save] {p_npz_out}")

    # accumulate across animals (optional convenience)
    all_trials.append(df_trials)
    all_sess.append(df_sess)
    all_npz_paths.append(str(BASE_DIR))

# Optional: concatenated tables across animals (not plotted)
if len(all_trials) and len(all_sess):
    df_trials_all = pd.concat(all_trials, ignore_index=True)
    df_sess_all   = pd.concat(all_sess,   ignore_index=True)
    print("\n[ok] multi-animal done")
    print(f"[info] total trials rows: {len(df_trials_all)}")
    print(f"[info] total sess   rows: {len(df_sess_all)}")

# %% Cell 39 (lines=1144, sha256=561f5ee9c3b729c69cb55869b5051c9ccd373a4d94b0323e7da16a248187cc56)
# ===== Multi-ANIMAL Licks-per-trial metrics from interpolated tongue data (v5) =====
# Per-animal start/end/include/exclude + stroke dates, same plots/outputs as single-animal version.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== GLOBAL KNOBS =====================
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- stroke filtering (global; applied per animal if stroke_date present) ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"        # "pre", "post", "both", "all"
REL_DAY_RANGE = None         # None or (min_day, max_day) inclusive

# ---- trials / sides ----
PLOT_SIDES = ("L", "R")      # subset of ("L","R")
USE_SRC = "final"            # "final" or "thr_interp"

# ---- lick detection windows ----
PLOT_WIN_MS   = (-200.0, 8000.0)   # snippet pulled per trial around reward
DETECT_WIN_MS = (0.0, 8000.0)      # lick detection restricted to this inside snippet

# Count window for summary metrics (relative to reward)
LICK_COUNT_WIN_MS = (0.0, 5000.0)

# Direction counts computed within this window (None -> DETECT_WIN_MS)
DIR_COUNT_WIN_MS = (0.0, 5000.0)

# Direction thresholds
X_LEFT_THR_PX  = +5.0   # leftward lick if x_at_peak > +5 px
X_RIGHT_THR_PX = -5.0   # rightward lick if x_at_peak < -5 px

# Threshold for "ge10" metric (set to 10 to match your description; change to 5 if desired)
LICK_GE10_THR = 10

# Binning
DO_BINNED = True
BIN_WIN_MS = (0.0, 5000.0)
BIN_MS = 1000.0
BIN_PLOT_MODE = "overlay"   # "separate" | "overlay" | "heatmap"

# ---- lick detector settings (dy/dt based) ----
DO_SMOOTH_Y = False
SMOOTH_MS = 12.0

RISE_MIN_MS = 16.0
FALL_MIN_MS = 16.0
SLOPE_THR_PX_PER_S = 250.0
PEAK_PAD_MS = 52.0

MAX_LICKS_PER_TRIAL = 40

# ---- dot size scaling by ABSOLUTE n ----
DOT_SIZE_MIN  = 5
DOT_SIZE_MAX  = 50
DOT_SIZE_MODE = "linear"         # "linear" or "sqrt"
LEGEND_N_EXAMPLES = [5, 25, 50]
DOT_SIZE_N_MAX = 50              # absolute reference for dot sizes (None -> per-mouse max)

# ---- COLORS / ALPHAS ----
SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}
PRE_COLOR   = "0.6"
POST_CMAP   = "plasma"

LINE_ALPHA  = 0.45
DOT_ALPHA   = 0.95
SEM_ALPHA   = 0.12

# ---- saving ----
SAVE_FIGS = True
FIG_DPI = 200
SAVE_TABLES = True
SAVE_NPZ    = True

# ===================== PER-ANIMAL CONFIG =====================
ANIMALS = {
    "PS46": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS47": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS48": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS49": dict(
        date_start="20250310",
        date_end="20250406",
        stroke_date="20250317",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS50": dict(
        date_start="20250319",
        date_end="20250406",
        stroke_date="20250323",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS51": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250429",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS54": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        include_dates=set(),
        exclude_dates=set(),
    ),
    "PS55": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        include_dates=set(),
        exclude_dates=set(),
    ),
}
# =============================================================


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
    if w <= 1:
        return y.copy()
    finite = np.isfinite(y)
    y0 = np.where(finite, y, 0.0)
    kernel = np.ones(int(w), dtype=float)
    num = np.convolve(y0, kernel, mode="same")
    den = np.convolve(finite.astype(float), kernel, mode="same")
    out = np.full(len(y), np.nan, float)
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

def _set_rel_day_ticks_keep_all_marks_label_every_7(ax, xmin, xmax):
    ticks_all = np.arange(int(xmin), int(xmax) + 1, 1)
    ax.set_xticks(ticks_all)
    span = int(xmax) - int(xmin)
    label_step = 1 if span <= 21 else 7
    labels = []
    for t in ticks_all:
        t_int = int(t)
        show = (t_int == 0) or ((t_int % label_step) == 0)
        labels.append(f"{t_int}" if show else "")
    ax.set_xticklabels(labels)

def _lick_peaks_from_y_dydt(yw, xw, fps, t_ms, detect_win_ms,
                           slope_thr=SLOPE_THR_PX_PER_S,
                           rise_min_ms=RISE_MIN_MS,
                           fall_min_ms=FALL_MIN_MS,
                           peak_pad_ms=PEAK_PAD_MS,
                           do_smooth_y=DO_SMOOTH_Y,
                           smooth_ms=SMOOTH_MS,
                           max_licks=40):
    lo_ms, hi_ms = detect_win_ms
    i0 = int(np.searchsorted(t_ms, lo_ms, side="left"))
    i1 = int(np.searchsorted(t_ms, hi_ms, side="right")) - 1
    i0 = max(0, min(i0, len(t_ms) - 1))
    i1 = max(0, min(i1, len(t_ms) - 1))
    if i1 < i0:
        i0, i1 = i1, i0

    yseg0 = np.asarray(yw[i0:i1+1], float)
    xseg0 = np.asarray(xw[i0:i1+1], float)
    if not np.any(np.isfinite(yseg0)):
        return []

    ys = yseg0.copy()
    if do_smooth_y and (smooth_ms is not None) and (smooth_ms > 0):
        w = max(1, _ms_to_frames(smooth_ms, fps))
        if w >= 3:
            ys = _moving_average_nan(ys, w)

    dt_s = 1.0 / fps
    dy = np.gradient(ys) / dt_s

    finite = np.isfinite(ys) & np.isfinite(dy) & np.isfinite(xseg0)
    rise_mask = finite & (dy > +slope_thr)
    fall_mask = finite & (dy < -slope_thr)

    rise_min_f = max(1, _ms_to_frames(rise_min_ms, fps))
    fall_min_f = max(1, _ms_to_frames(fall_min_ms, fps))
    pad_f      = max(0, _ms_to_frames(peak_pad_ms, fps))

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
        f0, f1 = _first_run_from(fall_mask, fall_min_f, start=j_peak)
        if f0 is not None:
            end_idx = max(end_idx, f1 - 1)

        i_peak_snip = i0 + j_peak
        peaks.append(dict(
            i_peak=int(i_peak_snip),
            t_ms=float(t_ms[i_peak_snip]),
            x_peak=float(xw[i_peak_snip]),
            y_peak=float(yw[i_peak_snip]),
        ))

        start = int(end_idx + 1)
        if start >= L:
            break

    return peaks


# ---------- plotting helpers ----------
def _legend_2col_side_plus_sizes(ax, sides, nmax_for_size):
    side_handles, side_labels = [], []
    for side in sides:
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

    ax.legend(
        side_handles_pad + size_handles_pad,
        side_labels_pad  + size_labels_pad,
        ncol=2, loc="best",
        frameon=False,
        handlelength=2.2,
        handletextpad=0.6,
        columnspacing=1.6,
        borderaxespad=0.4,
    )

def _plot_mean_sem_series(df_sess_in, stroke_dt, mean_col, sem_col, n_for_dot_size_col,
                          ylabel, title, out_png, ylims=None, show_stroke_divider=True):
    fig, ax = plt.subplots(figsize=(11, 4))
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT

    if DOT_SIZE_N_MAX is None:
        nmax_for_size = float(max(1.0, np.nanmax(df_sess_in[n_for_dot_size_col].to_numpy(float))))
    else:
        nmax_for_size = float(DOT_SIZE_N_MAX)

    for side in PLOT_SIDES:
        dd = df_sess_in[df_sess_in["side"] == side].copy()
        if dd.empty:
            continue

        if use_rel_day_axis:
            dd = dd.sort_values("rel_day").reset_index(drop=True)
            x = dd["rel_day"].to_numpy(float)
        else:
            dd = dd.sort_values("date_dt").reset_index(drop=True)
            x = dd["date_dt"].to_list()

        m = dd[mean_col].to_numpy(float)
        s = dd[sem_col].to_numpy(float)
        rel = dd["rel_day"].to_numpy(float)

        dot_colors = _session_dot_colors_from_rel_days(rel, cmap_name=POST_CMAP, pre_color=PRE_COLOR)
        sizes = _dot_sizes_from_n_absolute(
            dd[n_for_dot_size_col].to_numpy(float),
            n_max=nmax_for_size,
            smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX, mode=DOT_SIZE_MODE
        )

        side_c = SIDE_COLORS.get(side, "k")
        ax.plot(x, m, color=side_c, alpha=LINE_ALPHA, zorder=2)
        ax.scatter(x, m, c=dot_colors, s=sizes, alpha=DOT_ALPHA, zorder=3, edgecolors="none")

        ok = np.isfinite(m) & np.isfinite(s)
        if np.any(ok):
            x_ok = np.array(x)[ok]
            ax.fill_between(x_ok, m[ok] - s[ok], m[ok] + s[ok], color=side_c, alpha=SEM_ALPHA, lw=0, zorder=1)

    if use_rel_day_axis:
        if show_stroke_divider:
            ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9, zorder=0)
        x_all = df_sess_in["rel_day"].to_numpy(float)
        x_all = x_all[np.isfinite(x_all)]
        if x_all.size > 0:
            xmin = int(np.floor(np.min(x_all)))
            xmax = int(np.ceil(np.max(x_all)))
            _set_rel_day_ticks_keep_all_marks_label_every_7(ax, xmin, xmax)
        ax.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    else:
        ax.set_xlabel("Session date")

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if ylims is not None:
        ax.set_ylim(*ylims)
    ax.grid(True, alpha=0.2)

    _legend_2col_side_plus_sizes(ax, PLOT_SIDES, nmax_for_size)

    plt.tight_layout()
    if SAVE_FIGS:
        fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_png}")
    plt.show()
    plt.close(fig)

def _plot_direction_counts_two_panels(df_sess_in, stroke_dt, out_png, mouse):
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT
    if not use_rel_day_axis:
        print("[warn] direction plots expect stroke-aligned rel_day; skipping.")
        return

    fig, (axL, axR) = plt.subplots(nrows=2, ncols=1, figsize=(11, 6), sharex=True, gridspec_kw=dict(hspace=0.08))
    fig.subplots_adjust(right=0.82)

    legend_handles = [
        Line2D([0], [0], color="k", lw=2.0, linestyle="-",  label="leftward (x>thr)"),
        Line2D([0], [0], color="k", lw=2.0, linestyle="--", label="rightward (x<thr)"),
    ]

    for ax, side in [(axL, "L"), (axR, "R")]:
        dd = df_sess_in[df_sess_in["side"] == side].copy()
        if dd.empty:
            ax.set_axis_off()
            continue

        dd = dd.sort_values("rel_day").reset_index(drop=True)
        x = dd["rel_day"].to_numpy(float)

        rel = dd["rel_day"].to_numpy(float)
        dot_colors = _session_dot_colors_from_rel_days(rel, cmap_name=POST_CMAP, pre_color=PRE_COLOR)

        if DOT_SIZE_N_MAX is None:
            nmax_for_size = float(max(1.0, np.nanmax(dd["n_trials"].to_numpy(float))))
        else:
            nmax_for_size = float(DOT_SIZE_N_MAX)

        sizes = _dot_sizes_from_n_absolute(
            dd["n_trials"].to_numpy(float),
            n_max=nmax_for_size,
            smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX, mode=DOT_SIZE_MODE
        )

        side_c = SIDE_COLORS.get(side, "k")

        mL = dd["n_leftward_dirwin_mean"].to_numpy(float)
        sL = dd["n_leftward_dirwin_sem"].to_numpy(float)
        ax.plot(x, mL, color=side_c, alpha=LINE_ALPHA, lw=2.0, zorder=2)
        ax.scatter(x, mL, c=dot_colors, s=sizes, alpha=DOT_ALPHA, zorder=3, edgecolors="none")
        ok = np.isfinite(mL) & np.isfinite(sL)
        if np.any(ok):
            ax.fill_between(x[ok], mL[ok] - sL[ok], mL[ok] + sL[ok], color=side_c, alpha=SEM_ALPHA, lw=0, zorder=1)

        mR = dd["n_rightward_dirwin_mean"].to_numpy(float)
        sR = dd["n_rightward_dirwin_sem"].to_numpy(float)
        ax.plot(x, mR, color=side_c, alpha=LINE_ALPHA, lw=2.0, linestyle="--", zorder=2)
        ax.scatter(x, mR, c=dot_colors, s=sizes, alpha=0.55, zorder=3, edgecolors="none")
        ok = np.isfinite(mR) & np.isfinite(sR)
        if np.any(ok):
            ax.fill_between(x[ok], mR[ok] - sR[ok], mR[ok] + sR[ok], color=side_c, alpha=0.06, lw=0, zorder=1)

        ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9, zorder=0)
        ax.grid(True, alpha=0.2)
        ax.set_ylabel(f"{side} trials\nMean # licks/trial")

    x_all = df_sess_in["rel_day"].to_numpy(float)
    x_all = x_all[np.isfinite(x_all)]
    if x_all.size > 0:
        xmin = int(np.floor(np.min(x_all)))
        xmax = int(np.ceil(np.max(x_all)))
        _set_rel_day_ticks_keep_all_marks_label_every_7(axR, xmin, xmax)

    axR.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    fig.suptitle(
        f"{mouse} {CAM} | direction counts within {DIR_COUNT_WIN_MS[0]}–{DIR_COUNT_WIN_MS[1]} ms "
        f"(left: x>{X_LEFT_THR_PX}px, right: x<{X_RIGHT_THR_PX}px) | mean±SEM",
        y=0.995
    )

    fig.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.83, 0.85),
        frameon=False,
        borderaxespad=0.0,
    )

    plt.tight_layout()
    if SAVE_FIGS:
        fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_png}")
    plt.show()
    plt.close(fig)


# ---------- binned plots (reuse your exact plot logic, but per-animal) ----------
def _plot_binned_separate(df_sess_in, stroke_dt, fig_dir, mouse):
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT
    for bi in range(n_bins):
        mean_col = f"bin{bi}_mean"
        sem_col  = f"bin{bi}_sem"
        title = f"{mouse} {CAM} | licks/bin per trial | bin={bin_edges[bi]:.0f}–{bin_edges[bi+1]:.0f} ms | mean±SEM"
        out_png = fig_dir / f"{mouse}_{CAM}_binned_bin{bi}_{int(bin_edges[bi])}-{int(bin_edges[bi+1])}ms.png"

        fig, ax = plt.subplots(figsize=(11, 4))

        if DOT_SIZE_N_MAX is None:
            nmax_for_size = float(max(1.0, np.nanmax(df_sess_in["n_trials"].to_numpy(float))))
        else:
            nmax_for_size = float(DOT_SIZE_N_MAX)

        for side in PLOT_SIDES:
            dd = df_sess_in[df_sess_in["side"] == side].copy()
            if dd.empty:
                continue

            if use_rel_day_axis:
                dd = dd.sort_values("rel_day").reset_index(drop=True)
                x = dd["rel_day"].to_numpy(float)
            else:
                dd = dd.sort_values("date_dt").reset_index(drop=True)
                x = dd["date_dt"].to_list()

            m = dd[mean_col].to_numpy(float)
            s = dd[sem_col].to_numpy(float)
            rel = dd["rel_day"].to_numpy(float)

            dot_colors = _session_dot_colors_from_rel_days(rel, cmap_name=POST_CMAP, pre_color=PRE_COLOR)
            sizes = _dot_sizes_from_n_absolute(
                dd["n_trials"].to_numpy(float),
                n_max=nmax_for_size,
                smin=DOT_SIZE_MIN, smax=DOT_SIZE_MAX, mode=DOT_SIZE_MODE
            )

            side_c = SIDE_COLORS.get(side, "k")
            ax.plot(x, m, color=side_c, alpha=LINE_ALPHA, zorder=2)
            ax.scatter(x, m, c=dot_colors, s=sizes, alpha=DOT_ALPHA, zorder=3, edgecolors="none")

            ok = np.isfinite(m) & np.isfinite(s)
            if np.any(ok):
                x_ok = np.array(x)[ok]
                ax.fill_between(x_ok, m[ok] - s[ok], m[ok] + s[ok], color=side_c, alpha=SEM_ALPHA, lw=0, zorder=1)

        if use_rel_day_axis:
            ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9, zorder=0)
            x_all = df_sess_in["rel_day"].to_numpy(float)
            x_all = x_all[np.isfinite(x_all)]
            if x_all.size > 0:
                xmin = int(np.floor(np.min(x_all)))
                xmax = int(np.ceil(np.max(x_all)))
                _set_rel_day_ticks_keep_all_marks_label_every_7(ax, xmin, xmax)
            ax.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
        else:
            ax.set_xlabel("Session date")

        ax.set_title(title)
        ax.set_ylabel("Licks / trial in bin (mean±SEM)")
        ax.grid(True, alpha=0.2)
        _legend_2col_side_plus_sizes(ax, PLOT_SIDES, nmax_for_size)

        plt.tight_layout()
        if SAVE_FIGS:
            fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
            print(f"[save] {out_png}")
        plt.show()
        plt.close(fig)

def _plot_binned_overlay_stacked_bars(df_sess_in, stroke_dt, fig_dir, mouse):
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT
    if not use_rel_day_axis:
        print("[warn] overlay stacked bars expects stroke-aligned rel_day; skipping.")
        return

    x_all = df_sess_in["rel_day"].to_numpy(float)
    x_all = x_all[np.isfinite(x_all)]
    if x_all.size == 0:
        print("[warn] no rel_day; skipping.")
        return

    xmin = int(np.floor(np.min(x_all)))
    xmax = int(np.ceil(np.max(x_all)))
    days = np.arange(xmin, xmax + 1, 1, dtype=int)

    cmap = plt.get_cmap("viridis")
    bin_colors = [cmap(i / max(1, n_bins - 1)) for i in range(n_bins)]

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(11, 6), sharex=True, gridspec_kw=dict(hspace=0.08))
    fig.subplots_adjust(right=0.78)

    for ax, side in [(ax1, "L"), (ax2, "R")]:
        M = np.zeros((n_bins, len(days)), dtype=float)
        dd = df_sess_in[df_sess_in["side"] == side].copy()
        dd = dd[np.isfinite(dd["rel_day"].to_numpy(float))].copy()
        for _, r in dd.iterrows():
            rd = int(r["rel_day"])
            j = rd - xmin
            if 0 <= j < len(days):
                for bi in range(n_bins):
                    M[bi, j] = float(r.get(f"bin{bi}_mean", 0.0))

        bottoms = np.zeros(len(days), float)
        for bi in range(n_bins):
            ax.bar(days, M[bi, :], bottom=bottoms, width=0.9, align="center",
                   color=bin_colors[bi], edgecolor="none")
            bottoms += M[bi, :]

        ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9)
        ax.set_ylabel(f"{side} trials\nMean licks/trial")
        ax.grid(True, axis="y", alpha=0.2)

    _set_rel_day_ticks_keep_all_marks_label_every_7(ax2, xmin, xmax)
    ax2.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    ax1.set_title(f"{mouse} {CAM} | stacked binned licks/trial ({BIN_MS:.0f}ms bins) | mean")

    handles = [Line2D([0], [0], color=bin_colors[bi], lw=6) for bi in range(n_bins)]
    labels  = [f"{int(bin_edges[bi])}-{int(bin_edges[bi+1])}ms" for bi in range(n_bins)]
    fig.legend(
        handles, labels,
        loc="upper left",
        bbox_to_anchor=(0.80, 0.85),
        frameon=False,
        ncol=1,
        fontsize=9,
        borderaxespad=0.0,
        handlelength=1.6,
        handletextpad=0.6,
        labelspacing=0.4,
    )

    plt.tight_layout()
    out_png = fig_dir / f"{mouse}_{CAM}_binned_STACKEDBARS_LR_{int(BIN_MS)}msbins.png"
    if SAVE_FIGS:
        fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_png}")
    plt.show()
    plt.close(fig)

def _plot_binned_heatmap_two_panels(df_sess_in, stroke_dt, fig_dir, mouse):
    use_rel_day_axis = (stroke_dt is not None) and USE_STROKE_ALIGNMENT
    if not use_rel_day_axis:
        print("[warn] heatmap expects stroke-aligned rel_day; falling back to 'separate'.")
        _plot_binned_separate(df_sess_in, stroke_dt, fig_dir, mouse)
        return

    x_all = df_sess_in["rel_day"].to_numpy(float)
    x_all = x_all[np.isfinite(x_all)]
    if x_all.size == 0:
        print("[warn] no finite rel_day; skipping heatmap.")
        return

    xmin = int(np.floor(np.min(x_all)))
    xmax = int(np.ceil(np.max(x_all)))
    days = np.arange(xmin, xmax + 1, 1, dtype=int)

    mats = {}
    for side in ("L", "R"):
        M = np.full((n_bins, len(days)), np.nan, float)
        dd = df_sess_in[df_sess_in["side"] == side].copy()
        if not dd.empty:
            dd = dd[np.isfinite(dd["rel_day"].to_numpy(float))].copy()
            for _, r in dd.iterrows():
                rd = int(r["rel_day"])
                j = rd - xmin
                if 0 <= j < len(days):
                    for bi in range(n_bins):
                        M[bi, j] = float(r.get(f"bin{bi}_mean", np.nan))
        mats[side] = M

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(11, 6), sharex=True)
    fig.subplots_adjust(right=0.86, hspace=0.08)

    extent = [xmin - 0.5, xmax + 0.5, bin_edges[0], bin_edges[-1]]
    im1 = ax1.imshow(mats.get("L"), aspect="auto", origin="lower", extent=extent)
    im2 = ax2.imshow(mats.get("R"), aspect="auto", origin="lower", extent=extent)

    for ax, side in [(ax1, "L"), (ax2, "R")]:
        ax.axvline(0.5, color="red", linestyle=":", lw=1.6, alpha=0.9)
        ax.set_ylabel(f"{side} trials\nBin start (ms)")
        step = 1 if n_bins <= 10 else 2
        yt = bin_edges[:-1:step]
        ax.set_yticks(yt)
        ax.set_yticklabels([f"{int(v)}" for v in yt])

    ax2.set_xlabel("Relative day to stroke (d0 = last pre; d1 = first post)")
    _set_rel_day_ticks_keep_all_marks_label_every_7(ax2, xmin, xmax)
    ax1.set_title(f"{mouse} {CAM} | binned licks/trial HEATMAP ({BIN_MS:.0f}ms bins) | mean")

    cax = fig.add_axes([0.88, 0.17, 0.02, 0.66])
    cbar = fig.colorbar(im2, cax=cax)
    cbar.set_label("Mean licks / trial in bin")

    out_png = fig_dir / f"{mouse}_{CAM}_binned_HEATMAP_LR_{int(BIN_MS)}msbins.png"
    if SAVE_FIGS:
        fig.savefig(out_png, dpi=FIG_DPI, bbox_inches="tight")
        print(f"[save] {out_png}")
    plt.show()
    plt.close(fig)


# ===================== MAIN LOOP: animals =====================
all_trials = []
all_sess   = []

for mouse, cfg in ANIMALS.items():
    print("\n" + "="*80)
    print(f"[animal] {mouse}  CAM={CAM}  INTERP={INTERP_VERSION}")

    DATE_START = cfg["date_start"]
    DATE_END   = cfg["date_end"]
    INCLUDE_DATES = set(cfg.get("include_dates", set()) or set())
    EXCLUDE_DATES = set(cfg.get("exclude_dates", set()) or set())
    STROKE_DATE   = cfg.get("stroke_date", None)

    available, sess_dir = list_session_npzs_v5_only(mouse, CAM)

    if INCLUDE_DATES:
        dates = sorted([d for d in INCLUDE_DATES if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
    dates = [d for d in dates if d not in EXCLUDE_DATES]

    if not dates:
        some = sorted(available.keys())
        raise RuntimeError(
            f"No sessions matched for {mouse}.\n"
            f"Folder: {sess_dir}\n"
            f"Available {INTERP_VERSION} dates (first 60): {some[:60]}\n"
            f"Your selection: start={DATE_START}, end={DATE_END}, include={sorted(INCLUDE_DATES)}, exclude={sorted(EXCLUDE_DATES)}"
        )

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        raise RuntimeError(f"After pre/post stroke filtering, no sessions remain for {mouse}.")

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    # DIR window default
    dir_win = DIR_COUNT_WIN_MS if (DIR_COUNT_WIN_MS is not None) else DETECT_WIN_MS

    print(f"[info] sessions to analyze ({len(dates)}): {dates}")
    print(f"[info] LICK_COUNT_WIN_MS={LICK_COUNT_WIN_MS}  DIR_COUNT_WIN_MS={dir_win}")
    print(f"[info] BIN_WIN_MS={BIN_WIN_MS}  BIN_MS={BIN_MS}  BIN_PLOT_MODE={BIN_PLOT_MODE}")
    print(f"[info] direction thresholds: left if x>{X_LEFT_THR_PX}, right if x<{X_RIGHT_THR_PX}")
    print(f"[info] ge10 threshold: >= {LICK_GE10_THR} licks in count window")

    # output folder (per mouse; same structure as your single-animal version)
    FIG_DIR = (
        OUT_ROOT / mouse / f"{mouse}_tongue_kinematics" / "kinematics_figures" /
        f"{CENTER_MODE}" / "lick_metrics" / "licks_per_trial"
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # bins
    bin_edges = np.arange(BIN_WIN_MS[0], BIN_WIN_MS[1] + BIN_MS, BIN_MS, dtype=float) if DO_BINNED else None
    n_bins = (len(bin_edges) - 1) if (bin_edges is not None and len(bin_edges) >= 2) else 0

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
            n_trials = int(len(centers))

            if n_trials == 0:
                sess_rows.append(dict(
                    mouse=mouse, cam=CAM,
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side, n_trials=0,
                    n_licks_countwin_mean=np.nan, n_licks_countwin_sem=np.nan,
                    frac_ge1_mean=np.nan, frac_ge1_sem=np.nan, n_trials_ge1=0,
                    frac_ge10_mean=np.nan, frac_ge10_sem=np.nan, n_trials_ge10=0,
                    n_leftward_dirwin_mean=np.nan, n_leftward_dirwin_sem=np.nan,
                    n_rightward_dirwin_mean=np.nan, n_rightward_dirwin_sem=np.nan,
                    **({f"bin{bi}_mean": np.nan for bi in range(n_bins)} if (DO_BINNED and n_bins > 0) else {}),
                    **({f"bin{bi}_sem":  np.nan for bi in range(n_bins)} if (DO_BINNED and n_bins > 0) else {}),
                    src=src_label, npz=str(p_npz),
                ))
                continue

            n_licks_countwin = np.zeros(n_trials, dtype=float)
            ge1  = np.zeros(n_trials, dtype=float)
            ge10 = np.zeros(n_trials, dtype=float)

            n_left_dirwin  = np.zeros(n_trials, dtype=float)
            n_right_dirwin = np.zeros(n_trials, dtype=float)

            bin_counts = np.full((n_trials, n_bins), np.nan, dtype=float) if (DO_BINNED and n_bins > 0) else None

            for k, c in enumerate(centers):
                c = int(c)
                yw = _snippet(y, c, pre_f, post_f)
                xw = _snippet(x, c, pre_f, post_f)

                peaks = _lick_peaks_from_y_dydt(
                    yw, xw, fps, t_ms, DETECT_WIN_MS,
                    slope_thr=SLOPE_THR_PX_PER_S,
                    rise_min_ms=RISE_MIN_MS,
                    fall_min_ms=FALL_MIN_MS,
                    peak_pad_ms=PEAK_PAD_MS,
                    do_smooth_y=DO_SMOOTH_Y,
                    smooth_ms=SMOOTH_MS,
                    max_licks=MAX_LICKS_PER_TRIAL,
                )

                # --- count-window metrics ---
                w0, w1 = map(float, LICK_COUNT_WIN_MS)
                t_peaks = np.array([p["t_ms"] for p in peaks], float)
                in_count = (t_peaks >= w0) & (t_peaks <= w1)
                n_in_count = int(np.sum(in_count))

                n_licks_countwin[k] = float(n_in_count)
                ge1[k]  = 1.0 if (n_in_count >= 1) else 0.0
                ge10[k] = 1.0 if (n_in_count >= int(LICK_GE10_THR)) else 0.0

                # --- direction window ---
                dw0, dw1 = map(float, dir_win)
                nL = 0
                nR = 0
                for p in peaks:
                    t = float(p["t_ms"])
                    if not (dw0 <= t <= dw1):
                        continue
                    xp = float(p["x_peak"])
                    if np.isfinite(xp) and (xp > float(X_LEFT_THR_PX)):
                        nL += 1
                    elif np.isfinite(xp) and (xp < float(X_RIGHT_THR_PX)):
                        nR += 1
                n_left_dirwin[k]  = float(nL)
                n_right_dirwin[k] = float(nR)

                # --- binned counts ---
                if (DO_BINNED and bin_counts is not None):
                    bw0, bw1 = map(float, BIN_WIN_MS)
                    in_binwin = (t_peaks >= bw0) & (t_peaks <= bw1)
                    vals = t_peaks[in_binwin]
                    if vals.size == 0:
                        bin_counts[k, :] = 0.0
                    else:
                        h, _ = np.histogram(vals, bins=bin_edges)
                        bin_counts[k, :] = h.astype(float)

                trial_row = dict(
                    mouse=mouse, cam=CAM,
                    date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                    side=side, trial_index=int(k), reward_center_fr=int(c),
                    fps=float(fps), src=src_label, npz=str(p_npz),

                    n_licks_in_countwin=int(n_in_count),
                    has_lick_in_countwin=int(n_in_count >= 1),
                    has_ge10_in_countwin=int(n_in_count >= int(LICK_GE10_THR)),

                    n_leftward_dirwin=int(nL),
                    n_rightward_dirwin=int(nR),
                )
                if (DO_BINNED and bin_counts is not None):
                    for bi in range(n_bins):
                        trial_row[f"licks_bin{bi}_count"] = float(bin_counts[k, bi])

                trial_rows.append(trial_row)

            # session summaries
            mu_n, se_n, _ = _mean_sem_1d(n_licks_countwin)
            mu_ge1, se_ge1, _ = _mean_sem_1d(ge1)
            mu_ge10, se_ge10, _ = _mean_sem_1d(ge10)
            mu_l, se_l, _ = _mean_sem_1d(n_left_dirwin)
            mu_r, se_r, _ = _mean_sem_1d(n_right_dirwin)

            sess_row = dict(
                mouse=mouse, cam=CAM,
                date=d, date_dt=yyyymmdd_to_date(d), rel_day=rel_day,
                side=side, n_trials=n_trials,

                n_licks_countwin_mean=float(mu_n),
                n_licks_countwin_sem=float(se_n),

                frac_ge1_mean=float(mu_ge1),
                frac_ge1_sem=float(se_ge1),
                n_trials_ge1=int(np.sum(ge1 >= 0.5)),

                frac_ge10_mean=float(mu_ge10),
                frac_ge10_sem=float(se_ge10),
                n_trials_ge10=int(np.sum(ge10 >= 0.5)),

                n_leftward_dirwin_mean=float(mu_l),
                n_leftward_dirwin_sem=float(se_l),
                n_rightward_dirwin_mean=float(mu_r),
                n_rightward_dirwin_sem=float(se_r),

                src=src_label, npz=str(p_npz),
            )

            if (DO_BINNED and bin_counts is not None):
                for bi in range(n_bins):
                    mu, se, _ = _mean_sem_1d(bin_counts[:, bi])
                    sess_row[f"bin{bi}_mean"] = float(mu)
                    sess_row[f"bin{bi}_sem"]  = float(se)

            sess_rows.append(sess_row)

    df_trials = pd.DataFrame(trial_rows)
    df_sess   = pd.DataFrame(sess_rows).sort_values(["date_dt","side"]).reset_index(drop=True)

    print("\n[session summaries head]")
    print(df_sess.head(10).to_string(index=False))

    # ---------- plots ----------
    side_str = ",".join(PLOT_SIDES)
    src_str = f"v5 {USE_SRC}"
    detect_str = f"detect={DETECT_WIN_MS[0]}–{DETECT_WIN_MS[1]}ms | plot={PLOT_WIN_MS[0]}–{PLOT_WIN_MS[1]}ms"
    countwin_str = f"countwin={LICK_COUNT_WIN_MS[0]}–{LICK_COUNT_WIN_MS[1]}ms"

    _plot_mean_sem_series(
        df_sess_in=df_sess, stroke_dt=stroke_dt,
        mean_col="n_licks_countwin_mean", sem_col="n_licks_countwin_sem",
        n_for_dot_size_col="n_trials",
        ylabel="Mean # licks per trial (count window)",
        title=f"{mouse} {CAM} | {src_str} | {side_str} | {detect_str} | {countwin_str} | mean # licks/trial | mean±SEM",
        out_png=FIG_DIR / f"{mouse}_{CAM}_meanNlicks_countwin_{DATE_START}-{DATE_END}_{INTERP_VERSION}.png",
    )

    _plot_mean_sem_series(
        df_sess_in=df_sess, stroke_dt=stroke_dt,
        mean_col="frac_ge1_mean", sem_col="frac_ge1_sem",
        n_for_dot_size_col="n_trials_ge1",
        ylabel="Frac trials with ≥1 lick (mean±SEM)",
        title=f"{mouse} {CAM} | {src_str} | {side_str} | {detect_str} | {countwin_str} | trials with ≥1 lick | mean±SEM",
        out_png=FIG_DIR / f"{mouse}_{CAM}_fracTrials_ge1lick_{DATE_START}-{DATE_END}_{INTERP_VERSION}.png",
        ylims=(-0.02, 1.02),
    )

    _plot_mean_sem_series(
        df_sess_in=df_sess, stroke_dt=stroke_dt,
        mean_col="frac_ge10_mean", sem_col="frac_ge10_sem",
        n_for_dot_size_col="n_trials_ge10",
        ylabel=f"Frac trials with ≥{LICK_GE10_THR} licks (mean±SEM)",
        title=f"{mouse} {CAM} | {src_str} | {side_str} | {detect_str} | {countwin_str} | trials with ≥{LICK_GE10_THR} licks | mean±SEM",
        out_png=FIG_DIR / f"{mouse}_{CAM}_fracTrials_ge{LICK_GE10_THR}lick_{DATE_START}-{DATE_END}_{INTERP_VERSION}.png",
        ylims=(-0.02, 1.02),
    )

    _plot_direction_counts_two_panels(
        df_sess_in=df_sess, stroke_dt=stroke_dt, mouse=mouse,
        out_png=FIG_DIR / f"{mouse}_{CAM}_dirCounts_LRpanels_{int(dir_win[0])}-{int(dir_win[1])}ms_{DATE_START}-{DATE_END}_{INTERP_VERSION}.png"
    )

    if DO_BINNED and (n_bins > 0):
        if BIN_PLOT_MODE == "separate":
            _plot_binned_separate(df_sess, stroke_dt, FIG_DIR, mouse)
        elif BIN_PLOT_MODE == "overlay":
            _plot_binned_overlay_stacked_bars(df_sess, stroke_dt, FIG_DIR, mouse)
        elif BIN_PLOT_MODE == "heatmap":
            _plot_binned_heatmap_two_panels(df_sess, stroke_dt, FIG_DIR, mouse)
        else:
            raise ValueError("BIN_PLOT_MODE must be one of: 'separate','overlay','heatmap'")

    print("[ok] plotting done")

    # ---------- saves ----------
    if SAVE_TABLES:
        p_trials = FIG_DIR / f"{mouse}_{CAM}_licksPerTrial_pertrial_{DATE_START}-{DATE_END}_{INTERP_VERSION}.csv"
        p_sess   = FIG_DIR / f"{mouse}_{CAM}_licksPerTrial_persession_{DATE_START}-{DATE_END}_{INTERP_VERSION}.csv"
        df_trials.to_csv(p_trials, index=False)
        df_sess.to_csv(p_sess, index=False)
        print(f"[save] {p_trials}")
        print(f"[save] {p_sess}")F

    if SAVE_NPZ:
        params = dict(
            mouse=mouse, cam=CAM,
            center_mode=CENTER_MODE,
            interp_version=INTERP_VERSION,
            date_start=DATE_START, date_end=DATE_END,
            include_dates=sorted(list(INCLUDE_DATES)),
            exclude_dates=sorted(list(EXCLUDE_DATES)),
            stroke_date=cfg.get("stroke_date", None),
            use_src=USE_SRC,
            plot_win_ms=PLOT_WIN_MS,
            detect_win_ms=DETECT_WIN_MS,
            lick_count_win_ms=LICK_COUNT_WIN_MS,
            dir_count_win_ms=dir_win,
            lick_ge10_threshold=int(LICK_GE10_THR),
            dir_thresholds_px=dict(x_left_gt=X_LEFT_THR_PX, x_right_lt=X_RIGHT_THR_PX),
            do_binned=DO_BINNED,
            bin_win_ms=BIN_WIN_MS,
            bin_ms=BIN_MS,
            bin_edges_ms=bin_edges.tolist() if bin_edges is not None else None,
            detector=dict(
                do_smooth_y=DO_SMOOTH_Y,
                smooth_ms=SMOOTH_MS,
                rise_min_ms=RISE_MIN_MS,
                fall_min_ms=FALL_MIN_MS,
                slope_thr_px_per_s=SLOPE_THR_PX_PER_S,
                peak_pad_ms=PEAK_PAD_MS,
                max_licks_per_trial=MAX_LICKS_PER_TRIAL,
            ),
            prepost_mode=PREPOST_MODE,
            rel_day_range=REL_DAY_RANGE,
        )
        p_npz = FIG_DIR / f"{mouse}_{CAM}_licksPerTrial_trials+session_{DATE_START}-{DATE_END}_{INTERP_VERSION}.npz"
        np.savez_compressed(
            str(p_npz),
            params=np.array([params], dtype=object),
            df_trials=df_trials.to_dict("list"),
            df_sess=df_sess.to_dict("list"),
        )
        print(f"[save] {p_npz}")

    all_trials.append(df_trials)
    all_sess.append(df_sess)

print("\n[ok] done (multi-animal)")

# %% Cell 42 (lines=827, sha256=986d008ab6fd41c5abf99e3d6f47ed88e7558969ea2bb9bbd02817540e5cc455)
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

# %% Cell 50 (lines=1592, sha256=940f172a996002f49ddae2b3fa4695bbb74b4369005426bf01160bd64c91bf2e)
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
