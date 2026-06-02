=== cell 39 (code, 1145 lines) ===
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

