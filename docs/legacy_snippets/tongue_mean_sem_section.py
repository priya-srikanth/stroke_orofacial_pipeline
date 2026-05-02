r"""Vendored from
//research.files.med.harvard.edu/Neurobio/MICROSCOPE/Priya/DeepLabCut/code/20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Cells 31, 45, 47, 48.

Captured for Phase 7a.6 — 2026-05-01 from the MICROSCOPE share at
\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\.

3-tier-rule disambiguation: same canonical tongue notebook prior 7a.x
phases vendored from.

Cells 31, 45, 47, 48 are the production-viz cells of the `# Per session
and combined mean/SEM plots` section (cells 30-50, header to angle-
section boundary). The per-trial scalar cells (33/36/39/42) and angle
cell (50) inside the same range were already vendored by Phase 7a.3 V3
+ 7a.4. The trial viewer cells (34/37/40/43) are exploratory
plt.show()-only and excluded per Q4 of Phase 7a.6 Task 1 decisions. No
sibling notebooks contain alternative implementations of these per-
session mean/SEM plot families.

Source SHA256: ED12C54CD4CF348470CBD0FC05EE2FE20548195A52BE9832C1164737DABDB643
Source size: 403,798,697 B
Cells included:
  - Cell 31 (722 lines, type=code, sha256 dbdb19599bd7f219...): master per-session + cohort mean/SEM (4 plot families: individual_sessions, trial_overlays, session_overlays, binned_overlays)
  - Cell 45 (672 lines, type=code, sha256 399a861a6e140500...): across-session per-session mean XY lick trajectory overlays (L vs R)
  - Cell 47 (762 lines, type=code, sha256 01ba77895bd2762c...): across-session VIDEO of binned-mean per-session mean XY trajectory
  - Cell 48 (805 lines, type=code, sha256 fd50e94b02c3ea8d...): across-session VIDEO of binned-mean per-session mean XY trajectory, WITH FRAME TIMESTAMPS

Cells excluded (and why):
  - Cells 33/36/39/42 (per-trial scalar metrics): Already vendored in
    docs/legacy_snippets/tongue_pertrial_features.py (Phase 7a.3 V3,
    commit 0b78128). Re-vendoring would duplicate.
  - Cell 50 (per-frame tongue angle / 5-plot-family angle visual): Already
    vendored in docs/legacy_snippets/tongue_pertrial_features.py (Phase
    7a.3 V3) and shipped consolidated in tongue_visual.py (Phase 7a.4).
  - Cells 34, 37, 40, 43 (trial viewer cells): Exploratory display-only;
    end with `plt.show()` and emit no saved outputs (no `savefig()` calls).
    Per Phase 7a.6 Task 1 audit (2026-05-01), classified as exploratory
    and excluded by Q4 of the locked decisions.
  - Markdown headers between code cells (cells 30, 32, 35, 38, 41, 44, 46,
    49): Section-organizational only; not source code. Section context is
    documented in this file's preamble and in `.scratch_7a6/AUDIT_REPORT.md`.
  - Cells 51-55 (tongue-jaw mismatch): Already vendored in
    docs/legacy_snippets/tongue_jaw_mismatch.py (Phase 7a.5,
    commit 4d34a8f).
  - Cells 56+ (statistics + PSD section): Out of Phase 7a.6 scope. Cell 43
    PSD jaw-side is deferred to a future strategy §7 PSD phase per Q3 of
    the locked decisions; tongue cells 60-86 PSD are part of the same
    deferral.

DO NOT edit, reformat, or lint this file. # ruff: noqa, # fmt: off
preserve byte-identity with capture time.
"""
# ruff: noqa
# fmt: off

# %% Cell 31 (type=code, lines=722, sha256=dbdb19599bd7f2194c20d5ddc507e561de6e0799c6ee19e7b7dd1d38b785aab0)
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import re

# ===================== USER KNOBS =====================

# --- Multi-mouse specs (d0 = last pre-stroke day) ---
# Add bin_size_days per mouse (optional). If omitted, DEFAULT_BIN_SIZE_DAYS is used.
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

DEFAULT_BIN_SIZE_DAYS = 2  # used only if a mouse doesn't specify bin_size_days

CAM   = "cam2"
CENTER_MODE = "centered_spout_midpoint"
INTERP_VERSION = "v5p3"  # force v5

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# --- Run multiple reward-aligned windows ---
# Each tuple is (pre_ms, post_ms), meaning window is -pre_ms .. +post_ms
TIME_WINDOWS_MS = [
    (100, 1000),
    (500, 5000),
]

# ---- stroke alignment / filtering ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"      # "pre", "post", "both", or "all"
REL_DAY_RANGE = None       # None or (min_day, max_day), e.g. (-14, 28)

# ---- plotting style ----
PLOT_SEM = True
LINEWIDTH = 1
SEM_ALPHA = 0.18
CMAP_NAME = "plasma"
LINE_ALPHA = 0.5
PRE_COLOR = "0.3"

# ---- side colors for individual-session style plots ----
SIDE_COLORS = {"L": "dodgerblue", "R": "mediumvioletred"}

# ---- trial overlay style ----
TRIAL_ALPHA = 0.08
TRIAL_LINEWIDTH = 0.6

# ---- NEW: separate global limits for trial overlay plots ----
USE_SEPARATE_TRIAL_OVERLAY_LIMITS = True
TRIAL_OVERLAY_PERCENTILES = (1.0, 99.0)
TRIAL_OVERLAY_PAD_FRAC = 0.05

# ---- what to plot/save ----
PLOT_INDIVIDUAL_SESSIONS = True
PLOT_TRIAL_OVERLAYS      = True
PLOT_SESSION_OVERLAYS    = True
PLOT_BINNED_OVERLAYS     = True

SAVE_PNGS = True
SAVE_INDIVIDUAL_PNGS    = True
SAVE_TRIAL_OVERLAY_PNGS = True
SAVE_OVERLAY_PNGS       = True
SAVE_BINNED_PNGS        = True

DPI = 200

# ---- binned overlay controls ----
INCLUDE_PRE_BINS  = True
INCLUDE_POST_BINS = True

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

def mean_sem(A):
    A = np.asarray(A, float)
    if A.size == 0:
        T = A.shape[1] if A.ndim == 2 else 0
        return np.full((T,), np.nan), np.full((T,), np.nan)
    m = np.nanmean(A, axis=0)
    denom = np.sqrt(np.sum(np.isfinite(A), axis=0))
    s = np.nanstd(A, axis=0) / np.where(denom == 0, np.nan, denom)
    return m, s

def snippet(arr, c, pre_f, post_f):
    T = pre_f + post_f + 1
    lo = c - pre_f
    hi = c + post_f
    out = np.full(T, np.nan, dtype=float)
    src_lo = max(lo, 0)
    src_hi = min(hi, len(arr) - 1)
    if src_hi < src_lo:
        return out
    dst_lo = src_lo - lo
    dst_hi = dst_lo + (src_hi - src_lo)
    out[dst_lo:dst_hi+1] = arr[src_lo:src_hi+1]
    return out

def stack(arr, centers, pre_f, post_f):
    if len(centers) == 0:
        return np.zeros((0, pre_f + post_f + 1), dtype=float)
    return np.stack([snippet(arr, int(c), pre_f, post_f) for c in centers], axis=0)

def dlabel(rel_day: int):
    if rel_day == 0:
        return "d0"
    return f"d{rel_day:+d}"

def list_session_npzs_v5_only(mouse, cam, center_mode, interp_version):
    sess_dir = (
        OUT_ROOT
        / mouse
        / f"{mouse}_tongue_kinematics"
        / "processed_interpolated_data"
        / f"{center_mode}"
    )
    if not sess_dir.exists():
        raise FileNotFoundError(f"Missing processed_interpolated_data folder:\n  {sess_dir}")

    pat = re.compile(
        rf"^{re.escape(mouse)}_(?P<date>\d{{8}})_{re.escape(cam)}_tongue_interp_{re.escape(interp_version)}\.npz$"
    )

    available = {}
    for p in sorted(sess_dir.glob(f"{mouse}_*_{cam}_tongue_interp_{interp_version}.npz")):
        m = pat.match(p.name)
        if not m:
            continue
        available[m.group("date")] = p

    return available, sess_dir

def _finite_minmax(arrs):
    vals = []
    for a in arrs:
        if a is None:
            continue
        v = np.asarray(a).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            vals.append(v)
    if not vals:
        return np.nan, np.nan
    v = np.concatenate(vals)
    return float(np.min(v)), float(np.max(v))

def _pad(lo, hi, frac=0.05):
    if (not np.isfinite(lo)) or (not np.isfinite(hi)):
        return lo, hi
    if hi == lo:
        return lo - 1.0, hi + 1.0
    d = (hi - lo) * frac
    return lo - d, hi + d

def _finite_percentile_range(arrs, pct_lo=1.0, pct_hi=99.0):
    vals = []
    for a in arrs:
        if a is None:
            continue
        v = np.asarray(a).ravel()
        v = v[np.isfinite(v)]
        if v.size:
            vals.append(v)
    if not vals:
        return np.nan, np.nan
    v = np.concatenate(vals)
    return float(np.nanpercentile(v, pct_lo)), float(np.nanpercentile(v, pct_hi))

def _pad_from_percentiles(lo, hi, frac=0.05):
    if (not np.isfinite(lo)) or (not np.isfinite(hi)):
        return lo, hi
    if hi == lo:
        return lo - 1.0, hi + 1.0
    d = (hi - lo) * frac
    return lo - d, hi + d

def _overlay_colors_pre_grey_post_cmap(per_sess, cmap_name="plasma", pre_color="0.3"):
    cmap = plt.get_cmap(cmap_name)

    if any(s["rel_day"] is None for s in per_sess):
        return [cmap(i / max(1, len(per_sess) - 1)) for i in range(len(per_sess))]

    post_idx = [i for i, s in enumerate(per_sess) if s["rel_day"] is not None and s["rel_day"] >= 1]
    n_post = len(post_idx)

    colors = [None] * len(per_sess)
    for i, s in enumerate(per_sess):
        if s["rel_day"] is not None and s["rel_day"] <= 0:
            colors[i] = pre_color
    for j, i in enumerate(post_idx):
        colors[i] = cmap(j / max(1, n_post - 1))
    return colors

# --- binning helpers ---
def _make_rel_day_bins(rel_days, bin_size):
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return []

    B = int(max(1, bin_size))
    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))

    bins = []

    # pre bins (<=0)
    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

    lo = pre_start
    hi = lo + (B - 1)
    while hi <= 0:
        bins.append((lo, hi))
        lo += B
        hi += B

    # post bins (>=1)
    lo = 1
    hi = lo + (B - 1)
    while lo <= mx:
        bins.append((lo, hi))
        lo += B
        hi += B

    return bins

def _bin_label(lo, hi):
    return f"{lo}..{hi}"

def _bin_center(lo, hi):
    return 0.5 * (lo + hi)

def _assign_to_bin(rel_day, bins):
    rd = int(rel_day)
    for (lo, hi) in bins:
        if lo <= rd <= hi:
            return (lo, hi)
    return None

def _color_for_bin(lo, hi, post_max, cmap_name="plasma", pre_color="0.3"):
    cen = _bin_center(lo, hi)
    if cen <= 0:
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if (post_max is None) or (not np.isfinite(post_max)) or (post_max <= 1):
        return cmap(0.85)
    u = (float(cen) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)

def compute_binned(per_sess, bins):
    groups = {}
    for s in per_sess:
        if s["rel_day"] is None or (not np.isfinite(s["rel_day"])):
            continue
        b = _assign_to_bin(int(s["rel_day"]), bins)
        if b is None:
            continue
        groups.setdefault(b, []).append(s)

    out = []
    for (lo, hi), grp in sorted(groups.items(), key=lambda kv: _bin_center(kv[0][0], kv[0][1])):
        def _stack_means(key):
            return np.vstack([np.asarray(g[key], float) for g in grp])

        for_key = {}
        for key_m, key_s in [("myl","syl"),("myr","syr"),("mxl","sxl"),("mxr","sxr")]:
            M = _stack_means(key_m)
            mu = np.nanmean(M, axis=0)
            sem = np.nanstd(M, axis=0) / np.sqrt(max(1, M.shape[0]))
            for_key[key_m] = mu
            for_key[key_s] = sem

        out.append(dict(
            bin_lo=int(lo),
            bin_hi=int(hi),
            bin_label=_bin_label(int(lo), int(hi)),
            bin_center=float(_bin_center(int(lo), int(hi))),
            n_sessions=len(grp),
            sessions=[g["date"] for g in grp],
            **for_key
        ))
    return out

# ---------- plotting ----------
def plot_session_2x2(mouse, cam, sess, t_ms, y_lim, x_lim, fig_ind, win_tag):
    fig, axs = plt.subplots(2, 2, figsize=(12, 7), sharex=True)

    def one(ax, m, s, side, title, ylabel, ylim=None):
        c = SIDE_COLORS[side]
        ax.plot(t_ms, m, lw=LINEWIDTH, label="mean", color=c)
        if PLOT_SEM:
            ax.fill_between(t_ms, m - s, m + s, alpha=SEM_ALPHA, lw=0, color=c)
        ax.axvline(0, color="k", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel)
        if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
            ax.set_ylim(*ylim)

    one(axs[0,0], sess["myl"], sess["syl"], "L", f"Mouse LEFT rewards | Y | n={sess['nL']} ({sess['interp_version']})", "Tongue Y (px)", ylim=y_lim)
    one(axs[0,1], sess["myr"], sess["syr"], "R", f"Mouse RIGHT rewards | Y | n={sess['nR']} ({sess['interp_version']})", "Tongue Y (px)", ylim=y_lim)
    one(axs[1,0], sess["mxl"], sess["sxl"], "L", f"Mouse LEFT rewards | X | n={sess['nL']} ({sess['interp_version']})", "Tongue X (px)", ylim=x_lim)
    one(axs[1,1], sess["mxr"], sess["sxr"], "R", f"Mouse RIGHT rewards | X | n={sess['nR']} ({sess['interp_version']})", "Tongue X (px)", ylim=x_lim)

    for ax in axs[1,:]:
        ax.set_xlabel("Time relative to reward (ms)")

    title = f"{mouse} {cam} | {sess['date']}"
    if sess["rel_day"] is not None:
        title += f" ({sess['legend']})"
    title += f" | src={Path(sess['npz_path']).name}"
    fig.suptitle(title, y=1.02, fontsize=12)
    fig.tight_layout()

    if SAVE_PNGS and SAVE_INDIVIDUAL_PNGS:
        fn = f"{mouse}_{sess['date']}_{win_tag}_{cam}_{sess['interp_version']}_meanSEM_2x2"
        if sess["rel_day"] is not None:
            fn += f"_{sess['legend']}"
        out = fig_ind / f"{fn}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        print(f"[save] {out}")

    plt.show()
    plt.close(fig)

def plot_trial_overlays_2x2(mouse, cam, sess, t_ms, y_lim, x_lim, fig_trial, win_tag):
    fig, axs = plt.subplots(2, 2, figsize=(12, 7), sharex=True)

    def one(ax, A, m, s, side, title, ylabel, ylim=None):
        c = SIDE_COLORS[side]
        if A is not None and A.size > 0:
            for row in A:
                ax.plot(t_ms, row, lw=TRIAL_LINEWIDTH, alpha=TRIAL_ALPHA, color=c)
        ax.plot(t_ms, m, lw=LINEWIDTH, label="mean", color=c)
        if PLOT_SEM:
            ax.fill_between(t_ms, m - s, m + s, alpha=SEM_ALPHA, lw=0, color=c)
        ax.axvline(0, color="k", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel)
        if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
            ax.set_ylim(*ylim)

    one(axs[0,0], sess["Ayl"], sess["myl"], sess["syl"], "L", f"Mouse LEFT rewards | Y | n={sess['nL']} ({sess['interp_version']})", "Tongue Y (px)", ylim=y_lim)
    one(axs[0,1], sess["Ayr"], sess["myr"], sess["syr"], "R", f"Mouse RIGHT rewards | Y | n={sess['nR']} ({sess['interp_version']})", "Tongue Y (px)", ylim=y_lim)
    one(axs[1,0], sess["Axl"], sess["mxl"], sess["sxl"], "L", f"Mouse LEFT rewards | X | n={sess['nL']} ({sess['interp_version']})", "Tongue X (px)", ylim=x_lim)
    one(axs[1,1], sess["Axr"], sess["mxr"], sess["sxr"], "R", f"Mouse RIGHT rewards | X | n={sess['nR']} ({sess['interp_version']})", "Tongue X (px)", ylim=x_lim)

    for ax in axs[1,:]:
        ax.set_xlabel("Time relative to reward (ms)")

    title = f"{mouse} {cam} | {sess['date']} | all trials + mean±SEM"
    if sess["rel_day"] is not None:
        title += f" ({sess['legend']})"
    title += f" | src={Path(sess['npz_path']).name}"
    fig.suptitle(title, y=1.02, fontsize=12)
    fig.tight_layout()

    if SAVE_PNGS and SAVE_TRIAL_OVERLAY_PNGS:
        fn = f"{mouse}_{sess['date']}_{win_tag}_{cam}_{sess['interp_version']}_meanSEM_2x2_trials"
        if sess["rel_day"] is not None:
            fn += f"_{sess['legend']}"
        out = fig_trial / f"{fn}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        print(f"[save] {out}")

    plt.show()
    plt.close(fig)

def plot_overlay(mouse, cam, per_sess, t_ms, key_m, key_s, side_label, ylabel, outname, ylim, fig_ovr, suffix):
    colors = _overlay_colors_pre_grey_post_cmap(per_sess, cmap_name=CMAP_NAME, pre_color=PRE_COLOR)
    fig, ax = plt.subplots(figsize=(12, 4))

    for i, sess in enumerate(per_sess):
        m = sess[key_m]
        s = sess[key_s]
        c = colors[i]
        ax.plot(t_ms, m, lw=LINEWIDTH, color=c, alpha=LINE_ALPHA, label=sess["legend"])
        if PLOT_SEM:
            ax.fill_between(t_ms, m - s, m + s, color=c, alpha=SEM_ALPHA, lw=0)

    ax.axvline(0, color="k", lw=1)
    ax.set_title(f"{mouse} {cam} | {side_label} | mean±SEM | sessions={len(per_sess)} | src={per_sess[0]['interp_version']}")
    ax.set_xlabel("Time relative to reward (ms)")
    ax.set_ylabel(ylabel)
    if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
        ax.set_ylim(*ylim)

    n = len(per_sess)
    if n <= 16:
        ncol = 2; fsize = 9
    elif n <= 36:
        ncol = 3; fsize = 8
    else:
        ncol = 4; fsize = 7.5

    fig.subplots_adjust(right=0.78)
    ax.legend(
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        borderaxespad=0.0,
        ncol=ncol,
        fontsize=fsize,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=1.0,
        labelspacing=0.35,
    )

    if SAVE_PNGS and SAVE_OVERLAY_PNGS:
        out = fig_ovr / f"{mouse}_{suffix}_{cam}_{outname}_{per_sess[0]['interp_version']}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        print(f"[save] {out}")

    plt.show()
    plt.close(fig)

def plot_binned_overlay(mouse, cam, binned, t_ms, key_m, key_s, side_label, ylabel, outname, ylim, fig_bin, suffix, bin_size_days):
    if len(binned) == 0:
        print(f"[warn] {mouse}: no binned data to plot.")
        return

    post_centers = np.array([b["bin_center"] for b in binned if b["bin_center"] >= 1], float)
    post_max = float(np.nanmax(post_centers)) if post_centers.size else 1.0

    fig, ax = plt.subplots(figsize=(12, 4))

    for b in binned:
        lo, hi = b["bin_lo"], b["bin_hi"]
        cen = b["bin_center"]

        if cen <= 0 and not INCLUDE_PRE_BINS:
            continue
        if cen >= 1 and not INCLUDE_POST_BINS:
            continue

        c = _color_for_bin(lo, hi, post_max, cmap_name=CMAP_NAME, pre_color=PRE_COLOR)
        m = b[key_m]
        s = b[key_s]

        lab = f"{b['bin_label']} (n={b['n_sessions']})"
        ax.plot(t_ms, m, lw=1.5, color=c, alpha=0.5, label=lab)
        if PLOT_SEM:
            ax.fill_between(t_ms, m - s, m + s, color=c, alpha=SEM_ALPHA, lw=0)

    ax.axvline(0, color="k", lw=1)
    ax.set_title(f"{mouse} {cam} | BINNED overlays | bin={bin_size_days}d | {side_label} | src={INTERP_VERSION}")
    ax.set_xlabel("Time relative to reward (ms)")
    ax.set_ylabel(ylabel)
    if ylim is not None and np.isfinite(ylim[0]) and np.isfinite(ylim[1]):
        ax.set_ylim(*ylim)

    n = len(binned)
    if n <= 16:
        ncol = 1; fsize = 9
    elif n <= 28:
        ncol = 1; fsize = 8
    else:
        ncol = 2; fsize = 7.5

    fig.subplots_adjust(right=0.78)
    ax.legend(
        frameon=False,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        borderaxespad=0.0,
        ncol=ncol,
        fontsize=fsize,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=1.0,
        labelspacing=0.35,
    )

    if SAVE_PNGS and SAVE_BINNED_PNGS:
        out = fig_bin / f"{mouse}_{suffix}_{cam}_{outname}_BIN{bin_size_days}d_{INTERP_VERSION}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        print(f"[save] {out}")

    plt.show()
    plt.close(fig)

# ===================== MAIN LOOPS =====================

for mouse, spec in MOUSE_SPECS.items():
    BIN_SIZE_DAYS = int(spec.get("bin_size_days", DEFAULT_BIN_SIZE_DAYS))

    available, sess_dir = list_session_npzs_v5_only(mouse, CAM, CENTER_MODE, INTERP_VERSION)

    include_dates = spec.get("include_dates", None)
    exclude_dates = set(spec.get("exclude_dates", []) or [])
    date_start = spec["date_start"]
    date_end   = spec["date_end"]

    if include_dates:
        include_set = set(include_dates)
        dates = sorted([d for d in include_set if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(date_start, date_end) if d in available]
    dates = [d for d in dates if d not in exclude_dates]

    if not dates:
        some = sorted(available.keys())
        print(f"[warn] {mouse}: no sessions matched. Folder={sess_dir}")
        print(f"       Available dates (first 60): {some[:60]}")
        continue

    stroke_dt = yyyymmdd_to_date(spec["d0"]) if (USE_STROKE_ALIGNMENT and spec.get("d0", None)) else None

    def keep_by_prepost(date_str):
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

    dates = [d for d in dates if keep_by_prepost(d)]

    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        print(f"[warn] {mouse}: no sessions remain after stroke filtering.")
        continue

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)

    print(f"\n[info] ===== {mouse} =====")
    print(f"[info] sessions to process ({len(dates)}): {dates[:8]}{' ...' if len(dates) > 8 else ''}")
    print(f"[info] BIN_SIZE_DAYS={BIN_SIZE_DAYS}")

    for pre_ms, post_ms in TIME_WINDOWS_MS:
        win_tag = f"{int(pre_ms)}pre-{int(post_ms)}post"

        fig_root  = OUT_ROOT / mouse / f"{mouse}_Tongue_kinematics" / "kinematics_figures" / f"{CENTER_MODE}"
        fig_ind   = fig_root / "individual_sessions"
        fig_trial = fig_root / "trial_overlays"
        fig_ovr   = fig_root / "overlays"
        fig_bin   = fig_root / "binned_overlays"

        if SAVE_PNGS:
            if SAVE_INDIVIDUAL_PNGS:    fig_ind.mkdir(parents=True, exist_ok=True)
            if SAVE_TRIAL_OVERLAY_PNGS: fig_trial.mkdir(parents=True, exist_ok=True)
            if SAVE_OVERLAY_PNGS:       fig_ovr.mkdir(parents=True, exist_ok=True)
            if SAVE_BINNED_PNGS:        fig_bin.mkdir(parents=True, exist_ok=True)

        first = np.load(available[dates[0]], allow_pickle=True)
        fps0 = float(first["fps"])
        pre_f  = int(round((pre_ms/1000.0) * fps0))
        post_f = int(round((post_ms/1000.0) * fps0))
        t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps0))

        per_sess = []
        for d in dates:
            p_npz = available[d]
            Z = np.load(p_npz, allow_pickle=True)

            fps = float(Z["fps"])
            if abs(fps - fps0) > 1e-6:
                raise ValueError(f"{mouse}: fps mismatch across sessions: {d} has {fps}, expected {fps0}")

            x_fin = Z["x_final"]
            y_fin = Z["y_final"]

            cent_L = Z["fr_reward_mouseL"].astype(int)
            cent_R = Z["fr_reward_mouseR"].astype(int)

            Ayl = stack(y_fin, cent_L, pre_f, post_f)
            Ayr = stack(y_fin, cent_R, pre_f, post_f)
            Axl = stack(x_fin, cent_L, pre_f, post_f)
            Axr = stack(x_fin, cent_R, pre_f, post_f)

            myl, syl = mean_sem(Ayl)
            myr, syr = mean_sem(Ayr)
            mxl, sxl = mean_sem(Axl)
            mxr, sxr = mean_sem(Axr)

            rel_day = None
            leg = d
            if stroke_dt is not None:
                rel_day = (yyyymmdd_to_date(d) - stroke_dt).days
                leg = dlabel(int(rel_day))

            per_sess.append(dict(
                date=d,
                rel_day=rel_day,
                legend=leg,
                fps=fps,
                nL=len(cent_L),
                nR=len(cent_R),
                myl=myl, syl=syl,
                myr=myr, syr=syr,
                mxl=mxl, sxl=sxl,
                mxr=mxr, sxr=sxr,
                Ayl=Ayl, Ayr=Ayr,
                Axl=Axl, Axr=Axr,
                npz_path=str(p_npz),
                interp_version=INTERP_VERSION,
            ))

        if PLOT_SEM:
            y_lo, y_hi = _finite_minmax([
                *(s["myl"] - s["syl"] for s in per_sess),
                *(s["myl"] + s["syl"] for s in per_sess),
                *(s["myr"] - s["syr"] for s in per_sess),
                *(s["myr"] + s["syr"] for s in per_sess),
            ])
            x_lo, x_hi = _finite_minmax([
                *(s["mxl"] - s["sxl"] for s in per_sess),
                *(s["mxl"] + s["sxl"] for s in per_sess),
                *(s["mxr"] - s["sxr"] for s in per_sess),
                *(s["mxr"] + s["sxr"] for s in per_sess),
            ])
        else:
            y_lo, y_hi = _finite_minmax([*(s["myl"] for s in per_sess), *(s["myr"] for s in per_sess)])
            x_lo, x_hi = _finite_minmax([*(s["mxl"] for s in per_sess), *(s["mxr"] for s in per_sess)])

        y_lo, y_hi = _pad(y_lo, y_hi, frac=0.05)
        x_lo, x_hi = _pad(x_lo, x_hi, frac=0.05)
        y_lim = (y_lo, y_hi)
        x_lim = (x_lo, x_hi)

        # ---- NEW: separate global limits for trial overlay plots ----
        if USE_SEPARATE_TRIAL_OVERLAY_LIMITS:
            ty_lo, ty_hi = _finite_percentile_range(
                [*(s["Ayl"] for s in per_sess), *(s["Ayr"] for s in per_sess)],
                pct_lo=TRIAL_OVERLAY_PERCENTILES[0],
                pct_hi=TRIAL_OVERLAY_PERCENTILES[1],
            )
            tx_lo, tx_hi = _finite_percentile_range(
                [*(s["Axl"] for s in per_sess), *(s["Axr"] for s in per_sess)],
                pct_lo=TRIAL_OVERLAY_PERCENTILES[0],
                pct_hi=TRIAL_OVERLAY_PERCENTILES[1],
            )

            ty_lo, ty_hi = _pad_from_percentiles(ty_lo, ty_hi, frac=TRIAL_OVERLAY_PAD_FRAC)
            tx_lo, tx_hi = _pad_from_percentiles(tx_lo, tx_hi, frac=TRIAL_OVERLAY_PAD_FRAC)
        else:
            ty_lo, ty_hi = y_lo, y_hi
            tx_lo, tx_hi = x_lo, x_hi

        print(f"[info] mean-plot Y ylim: [{y_lo:.2f}, {y_hi:.2f}]")
        print(f"[info] mean-plot X ylim: [{x_lo:.2f}, {x_hi:.2f}]")
        print(f"[info] trial-overlay Y ylim: [{ty_lo:.2f}, {ty_hi:.2f}]")
        print(f"[info] trial-overlay X ylim: [{tx_lo:.2f}, {tx_hi:.2f}]")

        suffix = f"{spec['date_start']}-{spec['date_end']}_{win_tag}"
        if stroke_dt is not None:
            suffix += f"_strokeD0_{spec['d0']}_{PREPOST_MODE}"
            if REL_DAY_RANGE is not None:
                suffix += f"_relDay[{REL_DAY_RANGE[0]},{REL_DAY_RANGE[1]}]"

        print(f"[info] {mouse} | win={win_tag} | sessions={len(per_sess)} | save={fig_root}")

        if PLOT_INDIVIDUAL_SESSIONS:
            for sess in per_sess:
                plot_session_2x2(mouse, CAM, sess, t_ms, y_lim, x_lim, fig_ind, win_tag)

        if PLOT_TRIAL_OVERLAYS:
            for sess in per_sess:
                plot_trial_overlays_2x2(mouse, CAM, sess, t_ms, (ty_lo, ty_hi), (tx_lo, tx_hi), fig_trial, win_tag)

        if PLOT_SESSION_OVERLAYS:
            plot_overlay(mouse, CAM, per_sess, t_ms, "myl", "syl", "Mouse LEFT rewards",  "Tongue Y (px)", "overlay_Y_mouseLrewards", ylim=y_lim, fig_ovr=fig_ovr, suffix=suffix)
            plot_overlay(mouse, CAM, per_sess, t_ms, "myr", "syr", "Mouse RIGHT rewards", "Tongue Y (px)", "overlay_Y_mouseRrewards", ylim=y_lim, fig_ovr=fig_ovr, suffix=suffix)
            plot_overlay(mouse, CAM, per_sess, t_ms, "mxl", "sxl", "Mouse LEFT rewards",  "Tongue X (px)", "overlay_X_mouseLrewards", ylim=x_lim, fig_ovr=fig_ovr, suffix=suffix)
            plot_overlay(mouse, CAM, per_sess, t_ms, "mxr", "sxr", "Mouse RIGHT rewards", "Tongue X (px)", "overlay_X_mouseRrewards", ylim=x_lim, fig_ovr=fig_ovr, suffix=suffix)

        if PLOT_BINNED_OVERLAYS:
            if stroke_dt is None:
                print(f"[warn] {mouse}: skipping binned overlays (no d0 / stroke alignment).")
            else:
                rel_days = np.array([s["rel_day"] for s in per_sess], float)
                bins = _make_rel_day_bins(rel_days, bin_size=BIN_SIZE_DAYS)
                if len(bins) == 0:
                    print(f"[warn] {mouse}: no rel_day bins could be constructed.")
                else:
                    binned = compute_binned(per_sess, bins)
                    print(f"[info] {mouse} | win={win_tag} | binned overlays: bin={BIN_SIZE_DAYS}d | bins={len(binned)}")

                    plot_binned_overlay(mouse, CAM, binned, t_ms, "myl", "syl", "Mouse LEFT rewards",  "Tongue Y (px)", "binnedOverlay_Y_mouseLrewards", ylim=y_lim, fig_bin=fig_bin, suffix=suffix, bin_size_days=BIN_SIZE_DAYS)
                    plot_binned_overlay(mouse, CAM, binned, t_ms, "myr", "syr", "Mouse RIGHT rewards", "Tongue Y (px)", "binnedOverlay_Y_mouseRrewards", ylim=y_lim, fig_bin=fig_bin, suffix=suffix, bin_size_days=BIN_SIZE_DAYS)
                    plot_binned_overlay(mouse, CAM, binned, t_ms, "mxl", "sxl", "Mouse LEFT rewards",  "Tongue X (px)", "binnedOverlay_X_mouseLrewards", ylim=x_lim, fig_bin=fig_bin, suffix=suffix, bin_size_days=BIN_SIZE_DAYS)
                    plot_binned_overlay(mouse, CAM, binned, t_ms, "mxr", "sxr", "Mouse RIGHT rewards", "Tongue X (px)", "binnedOverlay_X_mouseRrewards", ylim=x_lim, fig_bin=fig_bin, suffix=suffix, bin_size_days=BIN_SIZE_DAYS)

print("\n[ok] done for all mice × all windows")

# %% Cell 45 (type=code, lines=672, sha256=399a861a6e1405006522f8bd7d6788fb7f9daa82891ca0ecbe36474edb5d9142)
# ===== Multi-ANIMAL Across-session overlays: per-session mean XY lick trajectory (L vs R) =====
# Adds per-animal MULTIPLE peri-reward windows: windows=[(PRE_MS, POST_MS), ...]
# Keeps: inverted Y (0 at top), no colorbar, shared bin legend between plots.

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import re
from matplotlib.lines import Line2D

# ===================== GLOBAL KNOBS =====================
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- stroke alignment (global behavior; stroke_date is per-animal) ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"      # "pre","post","both","all"
REL_DAY_RANGE = None       # None or (min_day, max_day) inclusive

# ---- which reward trial groups to compute ----
PLOT_SIDES = ("L", "R")    # subset of ("L","R")

# ---- trial selection within each session’s reward list ----
TRIAL_IDXS  = None         # e.g., [0,1,2]
TRIAL_RANGE = None         # e.g., (0, 49) inclusive, or None
FIRST_N     = None         # e.g., 50, or None (default all)

# ---- optional X-range filter applied to baseline-subtracted x/y ----
DO_X_RANGE_FILTER = True
X_RANGE = (-150.0, 150.0)

# ---- optional time smoothing on mean trajectory (within each session; along time) ----
DO_TIME_SMOOTH = True
TIME_SMOOTH_MOVAVG_MS = 40.0

# ---- downsample within the snippet to lighten plotting ----
STRIDE = 1  # 1 = no downsample, 2 = every other point, etc.

# ---- rel_day binning across sessions -----------------
DO_REL_DAY_BIN = True
REL_DAY_BIN_SIZE_D = 7
PLOT_INDIVIDUAL_SESSIONS_WHEN_BINNED = True

# ---------------- saving ----------------
SAVE_FIG = True
FIG_DPI = 200

# ---- plotting style ----
PRE_COLOR = "0.6"
POST_CMAP = "plasma"

LINE_ALPHA = 0.2
LINE_LW    = 0.8

SHOW_SEM_TUBE = True
TUBE_ALPHA = 0.15

FIGSIZE = (13.0, 6.2)

# ===================== PER-ANIMAL CONFIG =====================
# windows is a list of (PRE_MS, POST_MS) tuples in ms
ANIMALS = {
    "PS46": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS47": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS48": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS49": dict(
        date_start="20250310",
        date_end="20250406",
        stroke_date="20250317",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS50": dict(
        date_start="20250319",
        date_end="20250406",
        stroke_date="20250323",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS51": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250429",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
    "PS54": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
    "PS55": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
}
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

def _select_trial_indices(n_trials, trial_idxs, trial_range, first_n):
    if trial_idxs is not None:
        idxs = [int(i) for i in trial_idxs if 0 <= int(i) < n_trials]
        return idxs
    if trial_range is not None:
        a, b = int(trial_range[0]), int(trial_range[1])
        if b < a:
            a, b = b, a
        a = max(0, a)
        b = min(n_trials - 1, b)
        return list(range(a, b + 1)) if b >= a else []
    if first_n is not None:
        return list(range(min(int(first_n), n_trials)))
    return list(range(n_trials))

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

def _smooth_movavg_ms(arr, win_ms, fps, stride=1):
    if (win_ms is None) or (win_ms <= 0):
        return np.asarray(arr, float)
    dt_ms = (1000.0 / float(fps)) * float(stride)
    w = int(np.round(float(win_ms) / dt_ms))
    w = max(1, w)
    return _moving_average_nan(np.asarray(arr, float), w)

def _mean_sem_trials(M):
    M = np.asarray(M, float)
    if M.size == 0:
        return np.full((M.shape[1],), np.nan), np.full((M.shape[1],), np.nan), 0
    mu = np.nanmean(M, axis=0)
    n_eff = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0)
    sem = np.full_like(mu, np.nan, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sem = sd / np.sqrt(np.maximum(1, n_eff))
    return mu, sem, int(M.shape[0])

def _rel_day_bin_edges(rel_days, bin_size):
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return []

    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))
    B = int(max(1, bin_size))

    bins = []
    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

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

def _color_for_rel_day(rel_day, post_max, cmap_name=POST_CMAP, pre_color=PRE_COLOR):
    if (rel_day is None) or (not np.isfinite(rel_day)) or rel_day <= 0:
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if post_max is None or (not np.isfinite(post_max)) or post_max <= 1:
        return cmap(0.85)
    u = (float(rel_day) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)

def _plot_xy_mean(ax, mx, my, sx, sy, color, label=None, lw=1.0, alpha=0.4,
                  show_tube=False, tube_alpha=0.16):
    ax.plot(mx, my, color=color, lw=lw, alpha=alpha, label=label)
    if show_tube:
        ok = np.isfinite(mx) & np.isfinite(my)
        if np.any(ok) and (sx is not None) and np.any(np.isfinite(sx)):
            ax.plot(mx + sx, my, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx - sx, my, color=color, lw=1.0, alpha=tube_alpha)
        if np.any(ok) and (sy is not None) and np.any(np.isfinite(sy)):
            ax.plot(mx, my + sy, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx, my - sy, color=color, lw=1.0, alpha=tube_alpha)


# ===================== MAIN LOOP: animals × windows =====================
for mouse, cfg in ANIMALS.items():
    DATE_START = cfg["date_start"]
    DATE_END   = cfg["date_end"]
    INCLUDE_DATES = set(cfg.get("include_dates", set()) or set())
    EXCLUDE_DATES = set(cfg.get("exclude_dates", set()) or set())
    STROKE_DATE   = cfg.get("stroke_date", None)
    WINDOWS       = list(cfg.get("windows", [(0.0, 400.0)]))
    BIN_SIZE_D    = int(cfg.get("rel_day_bin_size_d", REL_DAY_BIN_SIZE_D))

    FIG_DIR = (
        OUT_ROOT
        / mouse
        / f"{mouse}_tongue_kinematics"
        / "kinematics_figures"
        / f"{CENTER_MODE}"
        / "mean_xy_overlays"
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*90)
    print(f"[animal] {mouse} | dates {DATE_START}..{DATE_END} | stroke={STROKE_DATE} | windows={WINDOWS} | bin={BIN_SIZE_D}d")

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
            f"Your selection: start={DATE_START}, end={DATE_END}"
        )

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        raise RuntimeError(f"After pre/post filtering, no sessions remain for {mouse}.")

    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    # ---- run each window separately ----
    for (PRE_MS, POST_MS) in WINDOWS:
        PRE_MS = float(PRE_MS)
        POST_MS = float(POST_MS)

        print(f"[window] {mouse} PRE={PRE_MS}ms POST={POST_MS}ms | analyzing {len(dates)} sessions")

        # ---------------- compute per-session mean trajectories ----------------
        rows = []

        for d in dates:
            p_npz = available[d]
            Z = np.load(p_npz, allow_pickle=True)

            fps = float(Z["fps"]) if "fps" in Z else 250.0
            n_frames = int(Z["n_frames"]) if "n_frames" in Z else len(Z["x_final"])

            x = Z["x_final"].astype(float, copy=False)
            y = Z["y_final"].astype(float, copy=False)
            n_frames = min(n_frames, len(x), len(y))

            if DO_X_RANGE_FILTER:
                x_lo, x_hi = map(float, X_RANGE)
                bad = (~np.isfinite(x)) | (x < x_lo) | (x > x_hi)
                if np.any(bad):
                    x = x.copy()
                    y = y.copy()
                    x[bad] = np.nan
                    y[bad] = np.nan

            rel_day = np.nan
            if stroke_dt is not None:
                rel_day = (yyyymmdd_to_date(d) - stroke_dt).days

            pre_f  = max(0, _ms_to_frames(PRE_MS, fps))
            post_f = max(0, _ms_to_frames(POST_MS, fps))
            t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))
            if STRIDE > 1:
                t_ms = t_ms[::STRIDE]

            centers_by_side = {}
            if "L" in PLOT_SIDES and ("fr_reward_mouseL" in Z):
                c = Z["fr_reward_mouseL"].astype(int)
                c = c[(c >= 0) & (c < n_frames)]
                centers_by_side["L"] = c
            if "R" in PLOT_SIDES and ("fr_reward_mouseR" in Z):
                c = Z["fr_reward_mouseR"].astype(int)
                c = c[(c >= 0) & (c < n_frames)]
                centers_by_side["R"] = c

            for side, centers in centers_by_side.items():
                idxs = _select_trial_indices(len(centers), TRIAL_IDXS, TRIAL_RANGE, FIRST_N)
                if len(idxs) == 0:
                    continue

                xs_trials = []
                ys_trials = []
                for i in idxs:
                    c_fr = int(centers[i])
                    xs = _snippet(x, c_fr, pre_f, post_f)
                    ys = _snippet(y, c_fr, pre_f, post_f)
                    if STRIDE > 1:
                        xs = xs[::STRIDE]
                        ys = ys[::STRIDE]
                    xs_trials.append(xs)
                    ys_trials.append(ys)

                xs_trials = np.vstack(xs_trials) if len(xs_trials) else np.empty((0, len(t_ms)))
                ys_trials = np.vstack(ys_trials) if len(ys_trials) else np.empty((0, len(t_ms)))

                mx, sx, ntr = _mean_sem_trials(xs_trials)
                my, sy, _   = _mean_sem_trials(ys_trials)

                if DO_TIME_SMOOTH:
                    mx = _smooth_movavg_ms(mx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    my = _smooth_movavg_ms(my, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    sx = _smooth_movavg_ms(sx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    sy = _smooth_movavg_ms(sy, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)

                rows.append(dict(
                    mouse=mouse,
                    date=d,
                    date_dt=yyyymmdd_to_date(d),
                    rel_day=float(rel_day) if np.isfinite(rel_day) else np.nan,
                    side=side,
                    n_trials=int(ntr),
                    fps=float(fps),
                    pre_ms=float(PRE_MS),
                    post_ms=float(POST_MS),
                    t_ms=t_ms.tolist(),
                    mx=mx.tolist(),
                    my=my.tolist(),
                    sx=sx.tolist(),
                    sy=sy.tolist(),
                    npz=str(p_npz),
                ))

        if len(rows) == 0:
            print(f"[warn] No trajectories computed for {mouse} window {PRE_MS}..{POST_MS}ms (check PLOT_SIDES / rewards / trial selection).")
            continue

        # post max for colormap scaling
        rel_days = np.array([r["rel_day"] for r in rows], float)
        post_days = rel_days[np.isfinite(rel_days) & (rel_days >= 1)]
        post_max = float(np.max(post_days)) if post_days.size else 1.0

        # ---------------- optional rel_day binning across sessions ----------------
        binned = None
        legend_handles = None
        legend_labels = None

        if DO_REL_DAY_BIN:
            if not (USE_STROKE_ALIGNMENT and stroke_dt is not None):
                raise RuntimeError(f"DO_REL_DAY_BIN=True requires stroke alignment for {mouse}.")

            bins = _rel_day_bin_edges(rel_days, bin_size=BIN_SIZE_D)

            # assign bins
            for r in rows:
                rd = r["rel_day"]
                if np.isfinite(rd):
                    lab, cen = _assign_rel_day_to_bin(int(rd), bins)
                else:
                    lab, cen = None, np.nan
                r["rel_day_bin"] = lab
                r["rel_day_bin_center"] = float(cen)

            rows_binnable = [r for r in rows if r.get("rel_day_bin") is not None]
            if len(rows_binnable) == 0:
                raise RuntimeError(f"No sessions assigned to rel_day bins for {mouse} (unexpected).")

            # binned means (per side)
            binned = []
            keys = sorted({(r["side"], r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable},
                          key=lambda k: (k[2], k[0]))

            for side, lab, cen in keys:
                grp = [r for r in rows_binnable if (r["side"] == side and r["rel_day_bin"] == lab and r["rel_day_bin_center"] == cen)]
                if len(grp) == 0:
                    continue

                mxM = np.vstack([np.asarray(r["mx"], float) for r in grp])
                myM = np.vstack([np.asarray(r["my"], float) for r in grp])

                mx = np.nanmean(mxM, axis=0)
                my = np.nanmean(myM, axis=0)

                sx = np.nanstd(mxM, axis=0) / np.sqrt(max(1, mxM.shape[0]))
                sy = np.nanstd(myM, axis=0) / np.sqrt(max(1, myM.shape[0]))

                binned.append(dict(
                    side=side,
                    rel_day_bin=lab,
                    rel_day_bin_center=float(cen),
                    n_sessions=len(grp),
                    t_ms=grp[0]["t_ms"],
                    mx=mx,
                    my=my,
                    sx=sx,
                    sy=sy,
                ))

            # ONE shared legend for bins between plots
            legend_items = []
            uniq_bins = sorted({(r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable},
                              key=lambda x: x[1])

            for lab, cen in uniq_bins:
                n_unique_sessions = len({r["date"] for r in rows_binnable if r["rel_day_bin"] == lab})
                legend_items.append((lab, float(cen), int(n_unique_sessions)))

            legend_handles, legend_labels = [], []
            for lab, cen, n in legend_items:
                col = _color_for_rel_day(cen, post_max)
                legend_handles.append(Line2D([0], [0], color=col, lw=3.0))
                legend_labels.append(f"{lab} (n={n})")

        # ---------------- plot overlays ----------------
        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE, sharex=False, sharey=True)
        fig.subplots_adjust(right=0.98, wspace=0.04)

        # SWAP ORDER: left=R, right=L
        ax_left, ax_right = axes[0], axes[1]
        side_to_ax = {"R": ax_left, "L": ax_right}

        # global y-limits with 0 at TOP
        all_y = []
        if DO_REL_DAY_BIN and (binned is not None):
            for b in binned:
                all_y.append(np.asarray(b["my"], float))
        else:
            for r in rows:
                all_y.append(np.asarray(r["my"], float))

        all_y = np.concatenate([v[np.isfinite(v)] for v in all_y if v is not None and np.any(np.isfinite(v))])
        if all_y.size == 0:
            raise RuntimeError(f"All y values are non-finite for {mouse} window {PRE_MS}..{POST_MS}ms.")
        y_max = float(np.nanmax(all_y))
        y_max = max(1e-6, y_max)
        y_pad = 0.05 * y_max
        y_top = 0.0
        y_bottom = y_max + y_pad

        for side in ("R", "L"):
            ax = side_to_ax[side]
            ax.set_title(f"{side} trials | session mean XY overlays")
            ax.set_xlabel("x (px, baseline-subtracted)")
            ax.set_ylabel("y (px, baseline-subtracted)")

            ax.set_ylim(y_bottom, y_top)  # 0 at top
            ax.set_aspect("equal", adjustable="box")
            ax.grid(True, alpha=0.2)

            if DO_REL_DAY_BIN:
                if PLOT_INDIVIDUAL_SESSIONS_WHEN_BINNED:
                    for r in rows:
                        if r["side"] != side:
                            continue
                        col = _color_for_rel_day(r["rel_day"], post_max)
                        mx = np.asarray(r["mx"], float)
                        my = np.asarray(r["my"], float)
                        _plot_xy_mean(ax, mx, my, None, None, color=col, lw=1, alpha=0.1, show_tube=False)

                for b in [bb for bb in (binned or []) if bb["side"] == side]:
                    cen = b["rel_day_bin_center"]
                    col = _color_for_rel_day(cen, post_max)
                    _plot_xy_mean(
                        ax, b["mx"], b["my"], b["sx"], b["sy"],
                        color=col, label=None, lw=2.5, alpha=0.6,
                        show_tube=SHOW_SEM_TUBE, tube_alpha=TUBE_ALPHA
                    )
            else:
                for r in rows:
                    if r["side"] != side:
                        continue
                    col = _color_for_rel_day(r["rel_day"], post_max)
                    mx = np.asarray(r["mx"], float)
                    my = np.asarray(r["my"], float)
                    sx = np.asarray(r["sx"], float)
                    sy = np.asarray(r["sy"], float)
                    _plot_xy_mean(
                        ax, mx, my, sx, sy,
                        color=col, label=None, lw=LINE_LW, alpha=LINE_ALPHA,
                        show_tube=SHOW_SEM_TUBE, tube_alpha=TUBE_ALPHA
                    )

        if DO_REL_DAY_BIN and (legend_handles is not None) and (legend_labels is not None):
            fig.legend(
                legend_handles,
                legend_labels,
                title="rel_day bins",
                loc="center",
                bbox_to_anchor=(0.51, 0.52),
                frameon=False,
                ncol=1,
                handlelength=2.2,
                handletextpad=0.6,
                labelspacing=0.4,
            )

        title = (
            f"{mouse} {CAM} | mean XY lick trajectory overlays | interp={INTERP_VERSION} | "
            f"window={-PRE_MS:.0f}..{POST_MS:.0f} ms"
        )
        if DO_REL_DAY_BIN:
            title += f" | rel_day bin={BIN_SIZE_D}d"
        if DO_TIME_SMOOTH:
            title += f" | time-smooth movavg {TIME_SMOOTH_MOVAVG_MS:.0f}ms"
        if DO_X_RANGE_FILTER:
            title += f" | x∈[{X_RANGE[0]},{X_RANGE[1]}]"
        fig.suptitle(title, y=0.995)

        plt.tight_layout()
        plt.show()

        # ---------------- save figure ----------------
        parts = [
            f"{mouse}",
            f"{CAM}",
            "sessionMeanXY",
            f"interp-{INTERP_VERSION}",
            f"win{-int(PRE_MS)}to{int(POST_MS)}ms",
        ]
        if DO_REL_DAY_BIN:
            parts.append(f"relDayBin{BIN_SIZE_D}d")
        if DO_TIME_SMOOTH:
            parts.append(f"timeSmooth{int(TIME_SMOOTH_MOVAVG_MS)}ms")
        if DO_X_RANGE_FILTER:
            parts.append(f"xlim{int(X_RANGE[0])}to{int(X_RANGE[1])}")

        fname = "_".join(parts) + ".png"
        out_path = FIG_DIR / fname

        if SAVE_FIG:
            fig.savefig(out_path, dpi=FIG_DPI, bbox_inches="tight")
            print(f"[save] {out_path}")

        plt.close(fig)

print("[ok] done (multi-animal × windows)")

# %% Cell 47 (type=code, lines=762, sha256=01ba77895bd2762c2044774e975a09f2bc1ea64a28d8ce79df97491a5a33b82f)
# ===== Multi-ANIMAL Across-session overlays (VIDEO): BINNED-MEAN session mean XY lick trajectory =====
# Per-animal MULTIPLE peri-reward windows: windows=[(PRE_MS, POST_MS), ...]
# Binned means ONLY.
# Keeps: y=0 at TOP, no colorbar, one shared bin legend on right, pre=grey post=plasma, R-left L-right.

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import re
from matplotlib.lines import Line2D
import matplotlib.animation as animation

# ===================== GLOBAL KNOBS =====================
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"
OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- stroke alignment (behavior global; stroke_date per-animal) ----
USE_STROKE_ALIGNMENT = True
PREPOST_MODE = "both"      # "pre","post","both","all"
REL_DAY_RANGE = None       # None or (min_day, max_day) inclusive

# ---- which reward trial groups to compute ----
PLOT_SIDES = ("L", "R")    # subset of ("L","R")

# ---- trial selection within each session’s reward list ----
TRIAL_IDXS  = None         # e.g., [0,1,2]
TRIAL_RANGE = None         # e.g., (0, 49) inclusive, or None
FIRST_N     = None         # e.g., 50, or None (default all)

# ---- optional X-range filter applied to baseline-subtracted x/y ----
DO_X_RANGE_FILTER = True
X_RANGE = (-150.0, 150.0)

# ---- optional time smoothing on mean trajectory (within each session; along time) ----
DO_TIME_SMOOTH = True
TIME_SMOOTH_MOVAVG_MS = 40.0

# ---- downsample within the snippet to lighten plotting ----
STRIDE = 1

# ---- rel_day binning across sessions (default; can override per animal) ----
DO_REL_DAY_BIN = True
REL_DAY_BIN_SIZE_D_DEFAULT = 7

# ---- plotting style ----
PRE_COLOR = "0.6"
POST_CMAP = "plasma"

BIN_LW    = 2.8
BIN_ALPHA = 0.60

SHOW_SEM_TUBE = False
TUBE_ALPHA = 0.14

FIGSIZE = (14.0, 6.2)

# ---------------- saving (static fig) ----------------
SAVE_FIG = False
FIG_DPI = 200

# ---------------- video knobs ----------------
MAKE_VIDEO = True
VIDEO_FORMAT = "mp4"       # "mp4" or "gif" (mp4 needs ffmpeg)

ANIM_MODE = "dot"          # "cumulative" or "dot"
TAIL_MS   = 100.0          # only used for "dot"

ANIM_FPS   = 60
ANIM_SPEED = 0.125
VIDEO_DPI  = 200

SAVE_BOTH_MODES = True     # if True, saves both cumulative + dot
# ======================================================

# ===================== PER-ANIMAL CONFIG =====================
# windows: list of (PRE_MS, POST_MS) in ms
ANIMALS = {
    "PS46": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS47": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS48": dict(
        date_start="20250307",
        date_end="20250406",
        stroke_date="20250313",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS49": dict(
        date_start="20250310",
        date_end="20250406",
        stroke_date="20250317",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS50": dict(
        date_start="20250319",
        date_end="20250406",
        stroke_date="20250323",
        windows=[(0.0, 500.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=2,  # optional override; if absent uses REL_DAY_BIN_SIZE_D
    ),
    "PS51": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250429",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
    "PS54": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
    "PS55": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        windows=[(0.0, 500.0), (0, 1000.0)],
        include_dates=set(),
        exclude_dates=set(),
        rel_day_bin_size_d=7,
    ),
}
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

def _select_trial_indices(n_trials, trial_idxs, trial_range, first_n):
    if trial_idxs is not None:
        idxs = [int(i) for i in trial_idxs if 0 <= int(i) < n_trials]
        return idxs
    if trial_range is not None:
        a, b = int(trial_range[0]), int(trial_range[1])
        if b < a:
            a, b = b, a
        a = max(0, a)
        b = min(n_trials - 1, b)
        return list(range(a, b + 1)) if b >= a else []
    if first_n is not None:
        return list(range(min(int(first_n), n_trials)))
    return list(range(n_trials))

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

def _smooth_movavg_ms(arr, win_ms, fps, stride=1):
    if (win_ms is None) or (win_ms <= 0):
        return np.asarray(arr, float)
    dt_ms = (1000.0 / float(fps)) * float(stride)
    w = int(np.round(float(win_ms) / dt_ms))
    w = max(1, w)
    return _moving_average_nan(np.asarray(arr, float), w)

def _mean_sem_trials(M):
    M = np.asarray(M, float)
    if M.size == 0:
        return np.full((M.shape[1],), np.nan), np.full((M.shape[1],), np.nan), 0
    mu = np.nanmean(M, axis=0)
    n_eff = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0)
    sem = np.full_like(mu, np.nan, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sem = sd / np.sqrt(np.maximum(1, n_eff))
    return mu, sem, int(M.shape[0])

def _rel_day_bin_edges(rel_days, bin_size):
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return []

    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))
    B = int(max(1, bin_size))

    bins = []
    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

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

def _color_for_rel_day(rel_day, post_max, cmap_name=POST_CMAP, pre_color=PRE_COLOR):
    if (rel_day is None) or (not np.isfinite(rel_day)) or rel_day <= 0:
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if post_max is None or (not np.isfinite(post_max)) or post_max <= 1:
        return cmap(0.85)
    u = (float(rel_day) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)

def _plot_xy_mean(ax, mx, my, sx, sy, color, label=None, lw=1.0, alpha=0.4,
                  show_tube=False, tube_alpha=0.16):
    ax.plot(mx, my, color=color, lw=lw, alpha=alpha, label=label)
    if show_tube:
        ok = np.isfinite(mx) & np.isfinite(my)
        if np.any(ok) and (sx is not None) and np.any(np.isfinite(sx)):
            ax.plot(mx + sx, my, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx - sx, my, color=color, lw=1.0, alpha=tube_alpha)
        if np.any(ok) and (sy is not None) and np.any(np.isfinite(sy)):
            ax.plot(mx, my + sy, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx, my - sy, color=color, lw=1.0, alpha=tube_alpha)

def _build_outname(mouse, pre_ms, post_ms, bin_size_d, kind, anim_mode=None, ext="png"):
    parts = [
        f"{mouse}",
        f"{CAM}",
        kind,
        f"interp-{INTERP_VERSION}",
        f"win{-int(pre_ms)}to{int(post_ms)}ms",
        f"relDayBin{int(bin_size_d)}d",
    ]
    if DO_TIME_SMOOTH:
        parts.append(f"timeSmooth{int(TIME_SMOOTH_MOVAVG_MS)}ms")
    if DO_X_RANGE_FILTER:
        parts.append(f"xlim{int(X_RANGE[0])}to{int(X_RANGE[1])}")
    if anim_mode is not None:
        parts.append(f"mode-{anim_mode}")
        parts.append(f"fps{int(ANIM_FPS)}")
        parts.append(f"speed{ANIM_SPEED:g}")
        if anim_mode == "dot":
            parts.append(f"tail{int(TAIL_MS)}ms")
    return "_".join(parts) + f".{ext}"


# ===================== MAIN LOOP: animals × windows =====================
for mouse, cfg in ANIMALS.items():
    DATE_START = cfg["date_start"]
    DATE_END   = cfg["date_end"]
    INCLUDE_DATES = set(cfg.get("include_dates", set()) or set())
    EXCLUDE_DATES = set(cfg.get("exclude_dates", set()) or set())
    STROKE_DATE   = cfg.get("stroke_date", None)
    WINDOWS       = list(cfg.get("windows", [(0.0, 2000.0)]))
    BIN_SIZE_D    = int(cfg.get("rel_day_bin_size_d", REL_DAY_BIN_SIZE_D_DEFAULT))

    # output directory per mouse (matches your conventions)
    FIG_DIR = (
        OUT_ROOT
        / mouse
        / f"{mouse}_tongue_kinematics"
        / "kinematics_figures"
        / f"{CENTER_MODE}"
        / "mean_xy_overlays"
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*100)
    print(f"[animal] {mouse} | dates {DATE_START}..{DATE_END} | stroke={STROKE_DATE} | windows={WINDOWS} | bin={BIN_SIZE_D}d")

    # collect sessions
    available, sess_dir = list_session_npzs_v5_only(mouse, CAM)

    if INCLUDE_DATES:
        dates = sorted([d for d in INCLUDE_DATES if d in available])
    else:
        dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
    dates = [d for d in dates if d not in EXCLUDE_DATES]

    if not dates:
        some = sorted(available.keys())
        print(f"[warn] No sessions matched for {mouse}. Folder={sess_dir}. First 40 available: {some[:40]}")
        continue

    stroke_dt = yyyymmdd_to_date(STROKE_DATE) if (USE_STROKE_ALIGNMENT and STROKE_DATE) else None
    dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
    if REL_DAY_RANGE is not None and stroke_dt is not None:
        lo, hi = REL_DAY_RANGE
        dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

    if not dates:
        print(f"[warn] After pre/post filtering, no sessions remain for {mouse}.")
        continue

    # sort by rel_day if available else by date
    if stroke_dt is not None:
        dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
    else:
        dates = sorted(dates)

    if not DO_REL_DAY_BIN:
        raise RuntimeError("This script is for BINNED means only: set DO_REL_DAY_BIN=True.")
    if not (USE_STROKE_ALIGNMENT and stroke_dt is not None):
        raise RuntimeError(f"{mouse}: binning requires stroke alignment (set stroke_date).")

    # ---- run each peri-reward window separately ----
    for (PRE_MS, POST_MS) in WINDOWS:
        PRE_MS = float(PRE_MS)
        POST_MS = float(POST_MS)

        print(f"[window] {mouse} PRE={PRE_MS}ms POST={POST_MS}ms | sessions={len(dates)}")

        # ---------------- compute per-session mean trajectories ----------------
        rows = []

        for d in dates:
            p_npz = available[d]
            Z = np.load(p_npz, allow_pickle=True)

            fps = float(Z["fps"]) if "fps" in Z else 250.0
            n_frames = int(Z["n_frames"]) if "n_frames" in Z else len(Z["x_final"])

            x = Z["x_final"].astype(float, copy=False)
            y = Z["y_final"].astype(float, copy=False)
            n_frames = min(n_frames, len(x), len(y))

            if DO_X_RANGE_FILTER:
                x_lo, x_hi = map(float, X_RANGE)
                bad = (~np.isfinite(x)) | (x < x_lo) | (x > x_hi)
                if np.any(bad):
                    x = x.copy()
                    y = y.copy()
                    x[bad] = np.nan
                    y[bad] = np.nan

            rel_day = (yyyymmdd_to_date(d) - stroke_dt).days if stroke_dt is not None else np.nan

            pre_f  = max(0, _ms_to_frames(PRE_MS, fps))
            post_f = max(0, _ms_to_frames(POST_MS, fps))
            t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))
            if STRIDE > 1:
                t_ms = t_ms[::STRIDE]

            centers_by_side = {}
            if "L" in PLOT_SIDES and ("fr_reward_mouseL" in Z):
                c = Z["fr_reward_mouseL"].astype(int)
                c = c[(c >= 0) & (c < n_frames)]
                centers_by_side["L"] = c
            if "R" in PLOT_SIDES and ("fr_reward_mouseR" in Z):
                c = Z["fr_reward_mouseR"].astype(int)
                c = c[(c >= 0) & (c < n_frames)]
                centers_by_side["R"] = c

            for side, centers in centers_by_side.items():
                idxs = _select_trial_indices(len(centers), TRIAL_IDXS, TRIAL_RANGE, FIRST_N)
                if len(idxs) == 0:
                    continue

                xs_trials = []
                ys_trials = []
                for i in idxs:
                    c_fr = int(centers[i])
                    xs = _snippet(x, c_fr, pre_f, post_f)
                    ys = _snippet(y, c_fr, pre_f, post_f)
                    if STRIDE > 1:
                        xs = xs[::STRIDE]
                        ys = ys[::STRIDE]
                    xs_trials.append(xs)
                    ys_trials.append(ys)

                xs_trials = np.vstack(xs_trials) if len(xs_trials) else np.empty((0, len(t_ms)))
                ys_trials = np.vstack(ys_trials) if len(ys_trials) else np.empty((0, len(t_ms)))

                mx, sx, ntr = _mean_sem_trials(xs_trials)
                my, sy, _   = _mean_sem_trials(ys_trials)

                if DO_TIME_SMOOTH:
                    mx = _smooth_movavg_ms(mx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    my = _smooth_movavg_ms(my, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    sx = _smooth_movavg_ms(sx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                    sy = _smooth_movavg_ms(sy, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)

                rows.append(dict(
                    date=d,
                    rel_day=float(rel_day),
                    side=side,
                    fps=float(fps),
                    t_ms=t_ms.tolist(),
                    mx=mx.tolist(),
                    my=my.tolist(),
                    sx=sx.tolist(),
                    sy=sy.tolist(),
                    n_trials=int(ntr),
                ))

        if len(rows) == 0:
            print(f"[warn] {mouse} window {PRE_MS}..{POST_MS}ms: no trajectories computed. Skipping.")
            continue

        # colormap scaling
        rel_days = np.array([r["rel_day"] for r in rows], float)
        post_days = rel_days[np.isfinite(rel_days) & (rel_days >= 1)]
        post_max = float(np.max(post_days)) if post_days.size else 1.0

        # ---------------- rel_day binning across sessions (required) ----------------
        bins = _rel_day_bin_edges(rel_days, bin_size=BIN_SIZE_D)

        for r in rows:
            rd = r["rel_day"]
            lab, cen = _assign_rel_day_to_bin(int(rd), bins) if np.isfinite(rd) else (None, np.nan)
            r["rel_day_bin"] = lab
            r["rel_day_bin_center"] = float(cen)

        rows_binnable = [r for r in rows if r.get("rel_day_bin") is not None]
        if len(rows_binnable) == 0:
            print(f"[warn] {mouse} window {PRE_MS}..{POST_MS}ms: no sessions assigned to bins. Skipping.")
            continue

        # binned means (per side)
        binned = []
        keys = sorted({(r["side"], r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable},
                      key=lambda k: (k[2], k[0]))

        for side, lab, cen in keys:
            grp = [r for r in rows_binnable if (r["side"] == side and r["rel_day_bin"] == lab and r["rel_day_bin_center"] == cen)]
            if len(grp) == 0:
                continue

            mxM = np.vstack([np.asarray(r["mx"], float) for r in grp])
            myM = np.vstack([np.asarray(r["my"], float) for r in grp])

            mx = np.nanmean(mxM, axis=0)
            my = np.nanmean(myM, axis=0)

            sx = np.nanstd(mxM, axis=0) / np.sqrt(max(1, mxM.shape[0]))
            sy = np.nanstd(myM, axis=0) / np.sqrt(max(1, myM.shape[0]))

            binned.append(dict(
                side=side,
                rel_day_bin=lab,
                rel_day_bin_center=float(cen),
                n_sessions=len(grp),
                t_ms=grp[0]["t_ms"],
                mx=mx,
                my=my,
                sx=sx,
                sy=sy,
            ))

        if len(binned) == 0:
            print(f"[warn] {mouse} window {PRE_MS}..{POST_MS}ms: no binned trajectories. Skipping.")
            continue

        # shared legend (right side)
        uniq_bins = sorted({(r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable}, key=lambda x: x[1])
        legend_items = []
        for lab, cen in uniq_bins:
            n_unique_sessions = len({r["date"] for r in rows_binnable if r["rel_day_bin"] == lab})
            legend_items.append((lab, float(cen), int(n_unique_sessions)))

        legend_handles, legend_labels = [], []
        for lab, cen, n in legend_items:
            col = _color_for_rel_day(cen, post_max)
            legend_handles.append(Line2D([0], [0], color=col, lw=3.0))
            legend_labels.append(f"{lab} (n={n})")

        # traces to animate (binned means only)
        traces = []
        for bb in binned:
            cen = bb["rel_day_bin_center"]
            col = _color_for_rel_day(cen, post_max)
            traces.append(dict(
                side=bb["side"],
                x=np.asarray(bb["mx"], float),
                y=np.asarray(bb["my"], float),
                sx=np.asarray(bb["sx"], float),
                sy=np.asarray(bb["sy"], float),
                color=col,
                lw=BIN_LW,
                alpha=BIN_ALPHA,
                label=bb["rel_day_bin"],
            ))

        # common length
        T = int(np.min([len(t["x"]) for t in traces]))
        if T < 2:
            print(f"[warn] {mouse} window {PRE_MS}..{POST_MS}ms: not enough points to animate. Skipping.")
            continue
        for t in traces:
            t["x"] = t["x"][:T]
            t["y"] = t["y"][:T]
            t["sx"] = t["sx"][:T]
            t["sy"] = t["sy"][:T]

        tms0 = np.asarray(binned[0]["t_ms"], float)
        dt_ms = float(np.nanmedian(np.diff(tms0))) if len(tms0) >= 2 else (1000.0 / 250.0)
        tail_frames = max(1, int(np.round(float(TAIL_MS) / max(1e-6, dt_ms))))

        # ---------------- animation factory ----------------
        def make_animation(anim_mode="cumulative"):
            fig, axes = plt.subplots(1, 2, figsize=FIGSIZE, sharex=False, sharey=True)
            fig.subplots_adjust(right=0.78, wspace=0.06)

            ax_left, ax_right = axes[0], axes[1]
            side_to_ax = {"R": ax_left, "L": ax_right}

            # global limits
            all_y = np.concatenate([t["y"][np.isfinite(t["y"])] for t in traces if np.any(np.isfinite(t["y"]))])
            all_x = np.concatenate([t["x"][np.isfinite(t["x"])] for t in traces if np.any(np.isfinite(t["x"]))])
            if all_y.size == 0 or all_x.size == 0:
                raise RuntimeError("No finite x/y values for axis limits.")

            y_max = float(np.nanmax(all_y))
            y_pad = 0.05 * y_max
            y_top = 0.0
            y_bottom = y_max + y_pad

            x_min = float(np.nanmin(all_x))
            x_max = float(np.nanmax(all_x))
            x_pad = 0.05 * (x_max - x_min + 1e-6)
            x_lims = (x_min - x_pad, x_max + x_pad)

            for side in ("R", "L"):
                ax = side_to_ax[side]
                ax.set_title(f"Tongue XY location, {side} trials")
                ax.set_xlabel("x (px)")
                ax.set_ylabel("y (px)")
                ax.set_aspect("equal", adjustable="box")
                ax.grid(True, alpha=0.2)

                # y=0 at TOP
                ax.set_ylim(y_bottom, y_top)
                ax.set_xlim(*x_lims)

            # shared legend on right
            fig.legend(
                legend_handles, legend_labels,
                title="rel_day bins",
                loc="center left",
                bbox_to_anchor=(0.80, 0.52),
                frameon=False,
                ncol=1,
                handlelength=2.2,
                handletextpad=0.6,
                labelspacing=0.4,
            )

            title = (
                f"{mouse} {CAM} | interp={INTERP_VERSION} | "
                f"window={-PRE_MS:.0f}..{POST_MS:.0f} ms | rel_day bin={BIN_SIZE_D}d"
            )
            if DO_TIME_SMOOTH:
                title += f" | time-smooth movavg {TIME_SMOOTH_MOVAVG_MS:.0f}ms"
            if DO_X_RANGE_FILTER:
                title += f" | x∈[{X_RANGE[0]},{X_RANGE[1]}]"
            fig.suptitle(title, y=0.995)

            # artists
            artists = []
            for tr in traces:
                ax = side_to_ax.get(tr["side"], None)
                if ax is None:
                    continue

                if anim_mode == "cumulative":
                    (ln,) = ax.plot([], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"])
                    artists.append(("line", ln, tr))

                elif anim_mode == "dot":
                    (tail_ln,) = ax.plot([], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"])
                    (dot,) = ax.plot([], [], marker="o", markersize=4.0, linestyle="None",
                                     color=tr["color"], alpha=min(1.0, tr["alpha"] + 0.25))
                    artists.append(("tail", tail_ln, tr))
                    artists.append(("dot", dot, tr))
                else:
                    raise ValueError("anim_mode must be 'cumulative' or 'dot'.")

            # optional SEM tubes (static)
            if SHOW_SEM_TUBE:
                for tr in traces:
                    ax = side_to_ax.get(tr["side"], None)
                    if ax is None:
                        continue
                    _plot_xy_mean(ax, tr["x"], tr["y"], tr["sx"], tr["sy"],
                                  color=tr["color"], lw=0.8, alpha=0.0,
                                  show_tube=True, tube_alpha=TUBE_ALPHA)

            def _init():
                for kind, artist, tr in artists:
                    artist.set_data([], [])
                return [a[1] for a in artists]

            def _update(frame_idx):
                k = int(np.clip(np.round(frame_idx * float(ANIM_SPEED)), 0, T - 1))
                for kind, artist, tr in artists:
                    x = tr["x"]
                    y = tr["y"]
                    if anim_mode == "cumulative":
                        if kind == "line":
                            artist.set_data(x[:k+1], y[:k+1])
                    else:
                        if kind == "tail":
                            lo = max(0, k - tail_frames)
                            artist.set_data(x[lo:k+1], y[lo:k+1])
                        elif kind == "dot":
                            artist.set_data([x[k]], [y[k]])
                return [a[1] for a in artists]

            n_frames = int(np.ceil((T - 1) / max(1e-6, float(ANIM_SPEED)))) + 1
            ani = animation.FuncAnimation(
                fig, _update, frames=n_frames,
                init_func=_init, blit=False,
                interval=1000.0 / float(ANIM_FPS),
            )
            return fig, ani

        # ---------------- make & save ----------------
        modes_to_make = [ANIM_MODE]
        if SAVE_BOTH_MODES:
            modes_to_make = ["cumulative", "dot"]

        for mode in modes_to_make:
            fig, ani = make_animation(anim_mode=mode)
            plt.show()

            if SAVE_FIG:
                png_name = _build_outname(mouse, PRE_MS, POST_MS, BIN_SIZE_D, "sessionMeanXY_BINNED_STATIC", ext="png")
                png_path = FIG_DIR / png_name
                fig.savefig(png_path, dpi=FIG_DPI, bbox_inches="tight")
                print(f"[save] {png_path}")

            if MAKE_VIDEO:
                if VIDEO_FORMAT.lower() == "mp4":
                    out_path = FIG_DIR / _build_outname(mouse, PRE_MS, POST_MS, BIN_SIZE_D,
                                                        "sessionMeanXY_BINNED_VIDEO", anim_mode=mode, ext="mp4")
                    try:
                        writer = animation.FFMpegWriter(fps=ANIM_FPS, bitrate=12000)
                        ani.save(out_path, writer=writer, dpi=VIDEO_DPI)
                        print(f"[save] {out_path}")
                    except Exception as e:
                        print("[warn] MP4 save failed (ffmpeg likely missing). Error:\n", e)
                        print("       Try: conda install -c conda-forge ffmpeg")
                        print("       Or set VIDEO_FORMAT='gif'.")
                elif VIDEO_FORMAT.lower() == "gif":
                    out_path = FIG_DIR / _build_outname(mouse, PRE_MS, POST_MS, BIN_SIZE_D,
                                                        "sessionMeanXY_BINNED_VIDEO", anim_mode=mode, ext="gif")
                    writer = animation.PillowWriter(fps=ANIM_FPS)
                    ani.save(out_path, writer=writer, dpi=VIDEO_DPI)
                    print(f"[save] {out_path}")
                else:
                    raise ValueError("VIDEO_FORMAT must be 'mp4' or 'gif'.")

            plt.close(fig)

print("[ok] done (multi-animal × windows; binned means video)")

# %% Cell 48 (type=code, lines=805, sha256=fd50e94b02c3ea8d6b9cab4ddd9540e1e979556bbfd0f5ba1789b5191e81b0af)
# ================== WITH FRAME TIMESTAMPS =====================

# ===== Across-session overlays (VIDEO): binned-mean session mean XY lick trajectory (R-left, L-right) =====
# MODS INCLUDED:
#   1) Per-animal configuration (date start/end, stroke date, rel-day bin size, etc.)
#   2) Per-animal peri-reward window(s): you can specify multiple (PRE_MS, POST_MS) windows per mouse
#      -> the script loops over windows and saves one video per window
#   3) Frame time label on each subplot: "t = ____ ms" updates every frame
#
# Keeps:
#   - y=0 at TOP (flipped y-axis)
#   - NO colorbar
#   - ONE shared rel_day-bin legend (right side)
#   - pre-stroke grey, post-stroke plasma
#   - R subplot on LEFT, L subplot on RIGHT
#
# Saves:
#   - static PNG (optional)
#   - video MP4 or GIF (optional; MP4 needs ffmpeg)

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import re
from matplotlib.lines import Line2D
import matplotlib.animation as animation

# ===================== USER KNOBS =====================
MOUSE = "PS55"
CAM   = "cam2"
INTERP_VERSION = "v5p3"
CENTER_MODE = "centered_spout_midpoint"

OUT_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

# ---- per-animal config ----
# You can override any defaults by adding keys per mouse.
# - peri_windows_ms: list of (PRE_MS, POST_MS) in ms; script will run each window
# - date_start/date_end: inclusive YYYYMMDD
# - stroke_date: last pre-stroke session (d0)
# - rel_day_bin_size_d: for binning across sessions

DEFAULTS = dict(
    date_start="20250416",
    date_end="20250709",
    stroke_date=None,                 # if None, stroke alignment off unless you set it below
    use_stroke_alignment=True,
    prepost_mode="both",              # "pre","post","both","all"
    rel_day_range=None,               # None or (min_day, max_day)
    rel_day_bin_size_d=7,
    peri_windows_ms=[(0.0, 2000.0)],  # default single window
)

MOUSE_CFG = {
    # Examples (edit as you want)
    "PS47": dict(
        date_start="20250307",
        date_end="20250401",
        stroke_date="20250313",
        peri_windows_ms=[(0.0, 400.0)],
        rel_day_bin_size_d=7,
    ),
    "PS51": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250429",
        peri_windows_ms=[(0.0, 400.0), (100.0, 1000.0)],
        rel_day_bin_size_d=7,
    ),
    "PS55": dict(
        date_start="20250416",
        date_end="20250709",
        stroke_date="20250430",
        peri_windows_ms=[(0.0, 2000.0)],
        rel_day_bin_size_d=7,
    ),
}

cfg = DEFAULTS.copy()
cfg.update(MOUSE_CFG.get(MOUSE, {}))

DATE_START = cfg["date_start"]
DATE_END   = cfg["date_end"]

USE_STROKE_ALIGNMENT = bool(cfg.get("use_stroke_alignment", True))
STROKE_DATE = cfg.get("stroke_date", None)   # "YYYYMMDD" or None
PREPOST_MODE = cfg.get("prepost_mode", "both")
REL_DAY_RANGE = cfg.get("rel_day_range", None)
REL_DAY_BIN_SIZE_D = int(cfg.get("rel_day_bin_size_d", 7))

PERI_WINDOWS_MS = list(cfg.get("peri_windows_ms", [(0.0, 2000.0)]))

# ---- date selection overrides ----
INCLUDE_DATES = set()     # overrides start/end if non-empty
EXCLUDE_DATES = set()

# ---- which reward trial groups to compute ----
PLOT_SIDES = ("L", "R")    # subset of ("L","R")

# ---- trial selection within each session’s reward list ----
TRIAL_IDXS  = None         # e.g., [0,1,2]
TRIAL_RANGE = None         # e.g., (0, 49) inclusive, or None
FIRST_N     = None         # e.g., 50, or None (default all)

# ---- optional X-range filter applied to baseline-subtracted x/y ----
DO_X_RANGE_FILTER = True
X_RANGE = (-150.0, 150.0)

# ---- optional time smoothing on mean trajectory (within each session; along time) ----
DO_TIME_SMOOTH = True
TIME_SMOOTH_MOVAVG_MS = 50.0   # moving-average window in ms for mx,my,sx,sy (if enabled)

# ---- downsample within the snippet to lighten plotting ----
STRIDE = 1  # 1 = no downsample, 2 = every other point, etc.

# ---- rel_day binning across sessions -----------------
DO_REL_DAY_BIN = True

# ---- plotting style (match your conventions) ----
PRE_COLOR = "0.6"
POST_CMAP = "plasma"

# binned mean styling
BIN_LW    = 2.8
BIN_ALPHA = 0.60

SHOW_SEM_TUBE = False     # tubes are static (not animated)
TUBE_ALPHA = 0.14

FIGSIZE = (14.0, 6.2)

# ---------------- saving (static fig) ----------------
SAVE_FIG = False
FIG_DPI = 200

FIG_DIR = (
    OUT_ROOT
    / MOUSE
    / f"{MOUSE}_tongue_kinematics"
    / "kinematics_figures"
    / f"{CENTER_MODE}"
    / "mean_xy_overlays"
)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- video knobs ----------------
MAKE_VIDEO = True
VIDEO_FORMAT = "mp4"       # "mp4" or "gif" (mp4 needs ffmpeg)

ANIM_MODE = "dot"          # "cumulative" or "dot"
TAIL_MS   = 100.0          # only used for "dot" mode (tail length in ms)

ANIM_FPS   = 60            # saved video fps
ANIM_SPEED = 0.125         # points advanced per video frame; >1 faster, <1 slower
VIDEO_DPI  = 200

# If you want to also save a second video in the other mode automatically:
SAVE_BOTH_MODES = True    # if True, saves both cumulative + dot (two files)
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

def _select_trial_indices(n_trials, trial_idxs, trial_range, first_n):
    if trial_idxs is not None:
        idxs = [int(i) for i in trial_idxs if 0 <= int(i) < n_trials]
        return idxs
    if trial_range is not None:
        a, b = int(trial_range[0]), int(trial_range[1])
        if b < a:
            a, b = b, a
        a = max(0, a)
        b = min(n_trials - 1, b)
        return list(range(a, b + 1)) if b >= a else []
    if first_n is not None:
        return list(range(min(int(first_n), n_trials)))
    return list(range(n_trials))

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

def _smooth_movavg_ms(arr, win_ms, fps, stride=1):
    if (win_ms is None) or (win_ms <= 0):
        return np.asarray(arr, float)
    dt_ms = (1000.0 / float(fps)) * float(stride)
    w = int(np.round(float(win_ms) / dt_ms))
    w = max(1, w)
    return _moving_average_nan(np.asarray(arr, float), w)

def _mean_sem_trials(M):
    M = np.asarray(M, float)
    if M.size == 0:
        return np.full((M.shape[1],), np.nan), np.full((M.shape[1],), np.nan), 0
    mu = np.nanmean(M, axis=0)
    n_eff = np.sum(np.isfinite(M), axis=0)
    sd = np.nanstd(M, axis=0)
    sem = np.full_like(mu, np.nan, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        sem = sd / np.sqrt(np.maximum(1, n_eff))
    return mu, sem, int(M.shape[0])

def _rel_day_bin_edges(rel_days, bin_size):
    rel_days = np.asarray(rel_days, float)
    rel_days = rel_days[np.isfinite(rel_days)]
    if rel_days.size == 0:
        return []

    mn = int(np.floor(rel_days.min()))
    mx = int(np.ceil(rel_days.max()))
    B = int(max(1, bin_size))

    bins = []

    # cover ...<=0
    pre_end = 0
    pre_start = pre_end - (B - 1)
    while pre_start > mn:
        pre_end -= B
        pre_start = pre_end - (B - 1)

    lo = pre_start
    hi = lo + (B - 1)
    while hi <= 0:
        bins.append((lo, hi))
        lo += B
        hi += B

    # cover 1.. upward
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

def _color_for_rel_day(rel_day, post_max, cmap_name=POST_CMAP, pre_color=PRE_COLOR):
    if (rel_day is None) or (not np.isfinite(rel_day)):
        return pre_color
    if rel_day <= 0:
        return pre_color
    cmap = plt.get_cmap(cmap_name)
    if post_max is None or (not np.isfinite(post_max)) or post_max <= 1:
        return cmap(0.85)
    u = (float(rel_day) - 1.0) / max(1.0, float(post_max) - 1.0)
    u = float(np.clip(u, 0.0, 1.0))
    return cmap(u)

def _plot_xy_mean(ax, mx, my, sx, sy, color, label=None, lw=1.0, alpha=0.4,
                  show_tube=False, tube_alpha=0.16):
    ax.plot(mx, my, color=color, lw=lw, alpha=alpha, label=label)
    if show_tube:
        ok = np.isfinite(mx) & np.isfinite(my)
        if np.any(ok) and (sx is not None) and np.any(np.isfinite(sx)):
            ax.plot(mx + sx, my, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx - sx, my, color=color, lw=1.0, alpha=tube_alpha)
        if np.any(ok) and (sy is not None) and np.any(np.isfinite(sy)):
            ax.plot(mx, my + sy, color=color, lw=1.0, alpha=tube_alpha)
            ax.plot(mx, my - sy, color=color, lw=1.0, alpha=tube_alpha)

def _build_outname(kind, pre_ms, post_ms, anim_mode=None, ext="png"):
    parts = [
        f"{MOUSE}",
        f"{CAM}",
        kind,
        f"interp-{INTERP_VERSION}",
        f"win{-int(pre_ms)}to{int(post_ms)}ms",
    ]
    if DO_REL_DAY_BIN:
        parts.append(f"relDayBin{REL_DAY_BIN_SIZE_D}d")
    if DO_TIME_SMOOTH:
        parts.append(f"timeSmooth{int(TIME_SMOOTH_MOVAVG_MS)}ms")
    if DO_X_RANGE_FILTER:
        parts.append(f"xlim{int(X_RANGE[0])}to{int(X_RANGE[1])}")
    if anim_mode is not None:
        parts.append(f"mode-{anim_mode}")
        parts.append(f"fps{int(ANIM_FPS)}")
        parts.append(f"speed{ANIM_SPEED:g}")
        if anim_mode == "dot":
            parts.append(f"tail{int(TAIL_MS)}ms")
    return "_".join(parts) + f".{ext}"

# ---------------- collect sessions ----------------
available, sess_dir = list_session_npzs_v5_only(MOUSE, CAM)

if INCLUDE_DATES:
    dates = sorted([d for d in INCLUDE_DATES if d in available])
else:
    dates = [d for d in daterange_yyyymmdd(DATE_START, DATE_END) if d in available]
dates = [d for d in dates if d not in EXCLUDE_DATES]

if not dates:
    some = sorted(available.keys())
    raise RuntimeError(
        "No sessions matched.\n"
        f"Folder: {sess_dir}\n"
        f"Available {INTERP_VERSION} dates (first 60): {some[:60]}\n"
        f"Your selection: start={DATE_START}, end={DATE_END}"
    )

stroke_dt = None
if USE_STROKE_ALIGNMENT and STROKE_DATE:
    stroke_dt = yyyymmdd_to_date(STROKE_DATE)

dates = [d for d in dates if keep_by_prepost(d, stroke_dt)]
if REL_DAY_RANGE is not None and stroke_dt is not None:
    lo, hi = REL_DAY_RANGE
    dates = [d for d in dates if (lo <= (yyyymmdd_to_date(d) - stroke_dt).days <= hi)]

if not dates:
    raise RuntimeError("After pre/post filtering, no sessions remain.")

# sort by rel_day if available else by date
if stroke_dt is not None:
    dates = sorted(dates, key=lambda s: (yyyymmdd_to_date(s) - stroke_dt).days)
else:
    dates = sorted(dates)

print(f"[info] analyzing {len(dates)} sessions: {dates}")
print(f"[info] peri-reward windows to run: {PERI_WINDOWS_MS}")
print(f"[info] rel_day bin size={REL_DAY_BIN_SIZE_D} d")

# ---------------- MAIN LOOP OVER PERI-REWARD WINDOWS ----------------
for (PRE_MS, POST_MS) in PERI_WINDOWS_MS:
    PRE_MS  = float(PRE_MS)
    POST_MS = float(POST_MS)

    print("\n" + "="*80)
    print(f"[run] window PRE={PRE_MS} ms, POST={POST_MS} ms")

    # ---------------- compute per-session mean trajectories ----------------
    rows = []

    for d in dates:
        p_npz = available[d]
        Z = np.load(p_npz, allow_pickle=True)

        fps = float(Z["fps"]) if "fps" in Z else 250.0
        n_frames = int(Z["n_frames"]) if "n_frames" in Z else len(Z["x_final"])

        x = Z["x_final"].astype(float, copy=False)
        y = Z["y_final"].astype(float, copy=False)
        n_frames = min(n_frames, len(x), len(y))

        if DO_X_RANGE_FILTER:
            x_lo, x_hi = map(float, X_RANGE)
            bad = (~np.isfinite(x)) | (x < x_lo) | (x > x_hi)
            if np.any(bad):
                x = x.copy()
                y = y.copy()
                x[bad] = np.nan
                y[bad] = np.nan

        rel_day = np.nan
        if stroke_dt is not None:
            rel_day = (yyyymmdd_to_date(d) - stroke_dt).days

        pre_f  = max(0, _ms_to_frames(PRE_MS, fps))
        post_f = max(0, _ms_to_frames(POST_MS, fps))
        t_ms = (np.arange(-pre_f, post_f + 1) * (1000.0 / fps))
        if STRIDE > 1:
            t_ms = t_ms[::STRIDE]

        centers_by_side = {}
        if "L" in PLOT_SIDES and ("fr_reward_mouseL" in Z):
            c = Z["fr_reward_mouseL"].astype(int)
            c = c[(c >= 0) & (c < n_frames)]
            centers_by_side["L"] = c
        if "R" in PLOT_SIDES and ("fr_reward_mouseR" in Z):
            c = Z["fr_reward_mouseR"].astype(int)
            c = c[(c >= 0) & (c < n_frames)]
            centers_by_side["R"] = c

        for side, centers in centers_by_side.items():
            idxs = _select_trial_indices(len(centers), TRIAL_IDXS, TRIAL_RANGE, FIRST_N)
            if len(idxs) == 0:
                continue

            xs_trials = []
            ys_trials = []
            for i in idxs:
                c_fr = int(centers[i])
                xs = _snippet(x, c_fr, pre_f, post_f)
                ys = _snippet(y, c_fr, pre_f, post_f)
                if STRIDE > 1:
                    xs = xs[::STRIDE]
                    ys = ys[::STRIDE]
                xs_trials.append(xs)
                ys_trials.append(ys)

            xs_trials = np.vstack(xs_trials) if len(xs_trials) else np.empty((0, len(t_ms)))
            ys_trials = np.vstack(ys_trials) if len(ys_trials) else np.empty((0, len(t_ms)))

            mx, sx, ntr = _mean_sem_trials(xs_trials)
            my, sy, _   = _mean_sem_trials(ys_trials)

            if DO_TIME_SMOOTH:
                mx = _smooth_movavg_ms(mx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                my = _smooth_movavg_ms(my, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                sx = _smooth_movavg_ms(sx, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)
                sy = _smooth_movavg_ms(sy, TIME_SMOOTH_MOVAVG_MS, fps=fps, stride=STRIDE)

            rows.append(dict(
                date=d,
                date_dt=yyyymmdd_to_date(d),
                rel_day=float(rel_day) if np.isfinite(rel_day) else np.nan,
                side=side,
                n_trials=int(ntr),
                fps=float(fps),
                t_ms=t_ms.tolist(),
                mx=mx.tolist(),
                my=my.tolist(),
                sx=sx.tolist(),
                sy=sy.tolist(),
                npz=str(p_npz),
            ))

    if len(rows) == 0:
        raise RuntimeError("No per-session trajectories computed (check PLOT_SIDES and trial selection).")

    # post max for colormap scaling
    rel_days = np.array([r["rel_day"] for r in rows], float)
    post_days = rel_days[np.isfinite(rel_days) & (rel_days >= 1)]
    post_max = float(np.max(post_days)) if post_days.size else 1.0

    # ---------------- rel_day binning across sessions (required for this cell) ----------------
    if not DO_REL_DAY_BIN:
        raise RuntimeError("This FULL CELL is configured for binned means only. Set DO_REL_DAY_BIN=True.")
    if not (USE_STROKE_ALIGNMENT and stroke_dt is not None):
        raise RuntimeError("DO_REL_DAY_BIN=True requires stroke alignment (USE_STROKE_ALIGNMENT and STROKE_DATE).")

    bins = _rel_day_bin_edges(rel_days, bin_size=REL_DAY_BIN_SIZE_D)

    # assign bins to per-session rows
    for r in rows:
        rd = r["rel_day"]
        if np.isfinite(rd):
            lab, cen = _assign_rel_day_to_bin(int(rd), bins)
        else:
            lab, cen = None, np.nan
        r["rel_day_bin"] = lab
        r["rel_day_bin_center"] = float(cen)

    rows_binnable = [r for r in rows if r.get("rel_day_bin") is not None]
    if len(rows_binnable) == 0:
        raise RuntimeError("No sessions assigned to rel_day bins (unexpected).")

    # binned means (per side)
    binned = []
    keys = sorted({(r["side"], r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable},
                  key=lambda k: (k[2], k[0]))  # sort by bin center, then side

    for side, lab, cen in keys:
        grp = [r for r in rows_binnable if (r["side"] == side and r["rel_day_bin"] == lab and r["rel_day_bin_center"] == cen)]
        if len(grp) == 0:
            continue

        mxM = np.vstack([np.asarray(r["mx"], float) for r in grp])
        myM = np.vstack([np.asarray(r["my"], float) for r in grp])

        mx = np.nanmean(mxM, axis=0)
        my = np.nanmean(myM, axis=0)

        # between-session SEM within bin
        sx = np.nanstd(mxM, axis=0) / np.sqrt(max(1, mxM.shape[0]))
        sy = np.nanstd(myM, axis=0) / np.sqrt(max(1, myM.shape[0]))

        binned.append(dict(
            side=side,
            rel_day_bin=lab,
            rel_day_bin_center=float(cen),
            n_sessions=len(grp),
            t_ms=grp[0]["t_ms"],
            mx=mx,
            my=my,
            sx=sx,
            sy=sy,
        ))

    if len(binned) == 0:
        raise RuntimeError("No binned trajectories produced.")

    # Build ONE shared legend for bins (independent of side)
    legend_items = []
    uniq_bins = sorted({(r["rel_day_bin"], r["rel_day_bin_center"]) for r in rows_binnable},
                       key=lambda x: x[1])

    for lab, cen in uniq_bins:
        n_unique_sessions = len({r["date"] for r in rows_binnable if r["rel_day_bin"] == lab})
        legend_items.append((lab, float(cen), int(n_unique_sessions)))

    legend_handles, legend_labels = [], []
    for lab, cen, n in legend_items:
        col = _color_for_rel_day(cen, post_max)
        legend_handles.append(Line2D([0], [0], color=col, lw=3.0))
        legend_labels.append(f"{lab} (n={n})")

    # ---------------- build traces to ANIMATE (BINNED MEANS ONLY) ----------------
    traces = []
    for bb in binned:
        cen = bb["rel_day_bin_center"]
        col = _color_for_rel_day(cen, post_max)
        traces.append(dict(
            side=bb["side"],
            x=np.asarray(bb["mx"], float),
            y=np.asarray(bb["my"], float),
            sx=np.asarray(bb["sx"], float),
            sy=np.asarray(bb["sy"], float),
            color=col,
            lw=BIN_LW,
            alpha=BIN_ALPHA,
            label=bb["rel_day_bin"],
        ))

    # determine common length across traces
    T = int(np.min([len(t["x"]) for t in traces]))
    if T < 2:
        raise RuntimeError("Not enough points in binned trajectories to animate.")
    for t in traces:
        t["x"] = t["x"][:T]
        t["y"] = t["y"][:T]
        t["sx"] = t["sx"][:T]
        t["sy"] = t["sy"][:T]

    # time vector for the animation label (ms)
    tms0 = np.asarray(binned[0]["t_ms"], float)[:T]
    if len(tms0) >= 2:
        dt_ms = float(np.nanmedian(np.diff(tms0)))
    else:
        dt_ms = 1000.0 / 250.0

    tail_frames = max(1, int(np.round(float(TAIL_MS) / max(1e-6, dt_ms))))

    # ---------------- plotting + animation builder ----------------
    def make_animation(anim_mode="cumulative"):
        # Figure / axes: R left, L right
        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE, sharex=False, sharey=True)

        # leave room on right for legend
        fig.subplots_adjust(right=0.78, wspace=0.06)

        ax_left, ax_right = axes[0], axes[1]
        side_to_ax = {"R": ax_left, "L": ax_right}

        # global limits
        all_y = np.concatenate([t["y"][np.isfinite(t["y"])] for t in traces if np.any(np.isfinite(t["y"]))])
        all_x = np.concatenate([t["x"][np.isfinite(t["x"])] for t in traces if np.any(np.isfinite(t["x"]))])
        if all_y.size == 0 or all_x.size == 0:
            raise RuntimeError("No finite x/y values for axis limits.")

        y_max = float(np.nanmax(all_y))
        y_pad = 0.05 * y_max
        y_top = 0.0
        y_bottom = y_max + y_pad

        x_min = float(np.nanmin(all_x))
        x_max = float(np.nanmax(all_x))
        x_pad = 0.05 * (x_max - x_min + 1e-6)
        x_lims = (x_min - x_pad, x_max + x_pad)

        # axes formatting
        for side in ("R", "L"):
            ax = side_to_ax[side]
            ax.set_title(f"Tongue XY location, {side} trials")
            ax.set_xlabel("x (px)")
            ax.set_ylabel("y (px)")
            ax.set_aspect("equal", adjustable="box")
            ax.grid(True, alpha=0.2)

            # y=0 at top
            ax.set_ylim(y_bottom, y_top)
            ax.set_xlim(*x_lims)

        # ---- frame time labels (one per subplot) ----
        time_text = {}
        for side in ("R", "L"):
            ax = side_to_ax[side]
            time_text[side] = ax.text(
                0.02, 0.98, "",
                transform=ax.transAxes,
                ha="left", va="top",
                fontsize=11,
                alpha=0.9,
            )

        # shared legend (static)
        fig.legend(
            legend_handles, legend_labels,
            title="rel_day bins",
            loc="center left",
            bbox_to_anchor=(0.80, 0.52),
            frameon=False,
            ncol=1,
            handlelength=2.2,
            handletextpad=0.6,
            labelspacing=0.4,
        )

        title = (
            f"{MOUSE} {CAM} | interp={INTERP_VERSION} | "
            f"window={-PRE_MS:.0f}..{POST_MS:.0f} ms"
        )
        title += f" | rel_day bin={REL_DAY_BIN_SIZE_D}d"
        if DO_TIME_SMOOTH:
            title += f" | time-smooth movavg {TIME_SMOOTH_MOVAVG_MS:.0f}ms"
        if DO_X_RANGE_FILTER:
            title += f" | x∈[{X_RANGE[0]},{X_RANGE[1]}]"
        fig.suptitle(title, y=0.995)

        # artists
        artists = []
        for tr in traces:
            ax = side_to_ax.get(tr["side"], None)
            if ax is None:
                continue

            if anim_mode == "cumulative":
                (ln,) = ax.plot([], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"])
                artists.append(("line", ln, tr))

            elif anim_mode == "dot":
                (tail_ln,) = ax.plot([], [], color=tr["color"], lw=tr["lw"], alpha=tr["alpha"])
                (dot,) = ax.plot([], [], marker="o", markersize=4.0, linestyle="None",
                                 color=tr["color"], alpha=min(1.0, tr["alpha"] + 0.25))
                artists.append(("tail", tail_ln, tr))
                artists.append(("dot", dot, tr))
            else:
                raise ValueError("anim_mode must be 'cumulative' or 'dot'.")

        # static SEM tubes (optional; not animated)
        if SHOW_SEM_TUBE:
            for tr in traces:
                ax = side_to_ax.get(tr["side"], None)
                if ax is None:
                    continue
                x = tr["x"]
                y = tr["y"]
                sx = tr["sx"]
                sy = tr["sy"]
                col = tr["color"]
                _plot_xy_mean(ax, x, y, sx, sy, color=col, lw=0.8, alpha=0.0,
                              show_tube=True, tube_alpha=TUBE_ALPHA)

        def _init():
            for kind, artist, tr in artists:
                artist.set_data([], [])
            for side in ("R", "L"):
                time_text[side].set_text("")
            return [a[1] for a in artists] + [time_text["R"], time_text["L"]]

        def _update(frame_idx):
            k = int(np.clip(np.round(frame_idx * float(ANIM_SPEED)), 0, T - 1))

            # ---- update frame time labels ----
            t_here_ms = float(tms0[k]) if k < len(tms0) else (k * dt_ms)
            for side in ("R", "L"):
                time_text[side].set_text(f"t = {t_here_ms:,.0f} ms")

            # ---- update geometry artists ----
            for kind, artist, tr in artists:
                x = tr["x"]
                y = tr["y"]
                if anim_mode == "cumulative":
                    if kind == "line":
                        artist.set_data(x[:k+1], y[:k+1])
                else:  # dot
                    if kind == "tail":
                        lo = max(0, k - tail_frames)
                        artist.set_data(x[lo:k+1], y[lo:k+1])
                    elif kind == "dot":
                        artist.set_data([x[k]], [y[k]])

            return [a[1] for a in artists] + [time_text["R"], time_text["L"]]

        n_frames = int(np.ceil((T - 1) / max(1e-6, float(ANIM_SPEED)))) + 1
        ani = animation.FuncAnimation(
            fig,
            _update,
            frames=n_frames,
            init_func=_init,
            blit=False,
            interval=1000.0 / float(ANIM_FPS),
        )

        return fig, ani

    # ---------------- show + save ----------------
    modes_to_make = [ANIM_MODE]
    if SAVE_BOTH_MODES:
        modes_to_make = ["cumulative", "dot"]

    for mode in modes_to_make:
        fig, ani = make_animation(anim_mode=mode)
        plt.show()

        # save static PNG of the first frame (optional)
        if SAVE_FIG:
            png_name = _build_outname("sessionMeanXY_BINNED_STATIC", PRE_MS, POST_MS, ext="png")
            png_path = FIG_DIR / png_name
            fig.savefig(png_path, dpi=FIG_DPI, bbox_inches="tight")
            print(f"[save] {png_path}")

        if MAKE_VIDEO:
            if VIDEO_FORMAT.lower() == "mp4":
                out_path = FIG_DIR / _build_outname("sessionMeanXY_BINNED_VIDEO", PRE_MS, POST_MS, anim_mode=mode, ext="mp4")
                try:
                    writer = animation.FFMpegWriter(fps=ANIM_FPS, bitrate=12000)
                    ani.save(out_path, writer=writer, dpi=VIDEO_DPI)
                    print(f"[save] {out_path}")
                except Exception as e:
                    print("[warn] MP4 save failed (ffmpeg likely missing). Error:\n", e)
                    print("       Try: conda install -c conda-forge ffmpeg")
                    print("       Or set VIDEO_FORMAT='gif'.")
            elif VIDEO_FORMAT.lower() == "gif":
                out_path = FIG_DIR / _build_outname("sessionMeanXY_BINNED_VIDEO", PRE_MS, POST_MS, anim_mode=mode, ext="gif")
                writer = animation.PillowWriter(fps=ANIM_FPS)
                ani.save(out_path, writer=writer, dpi=VIDEO_DPI)
                print(f"[save] {out_path}")
            else:
                raise ValueError("VIDEO_FORMAT must be 'mp4' or 'gif'.")

        plt.close(fig)

print("[ok] done")
