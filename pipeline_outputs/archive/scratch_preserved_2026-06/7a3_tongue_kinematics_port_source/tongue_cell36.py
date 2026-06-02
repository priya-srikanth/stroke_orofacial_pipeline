=== cell 36 (code, 1020 lines) ===
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

