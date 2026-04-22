# ruff: noqa
# fmt: off
r"""
Legacy reference snippet — READ-ONLY.

Purpose
-------
Read-only reference for Phase 7a (DLC-kinematics interpolation port, tongue).
Captured here so the Windows VSCode workstation (which does not have a
local clone of the Mac-side legacy Github repo) can perform byte-identical
parity validation of the v5p3 interpolation algorithm against the canonical
legacy implementation.

Source provenance
-----------------
Canonical source file:
    \\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Cell index (0-indexed): 23
Cell line count captured: 763
Cell SHA256 at capture time: 41f54f0d04371622e3838f93785e8c051d506109cf448215b7ffdc203f9067b3

Disambiguation
--------------
Per CLAUDE.md §"Legacy code version disambiguation" 3-tier rule, the
canonical version was selected as follows within the notebook family at
\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\code\:

Tongue family:
    Candidate                                                             mtime                   resolution
    -----                                                                 -----                   ----------
    20260111_DLC_analysis_build-parquet_tongue.ipynb                      2026-03-23 15:06:35     SIBLING (distinct scope: `build-parquet_tongue`)
    20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb           2026-04-20 02:31:54     CANONICAL (Priya-named; newest mtime; `ws_aligned_parquet_input_tongue` scope is the v5p3 interpolation notebook)
    20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb            2026-03-23 17:32:49     SIBLING (distinct scope: `reward-aligned_tongue_jaw` builder, not interp)

Jaw family:
    Candidate                                                             mtime                   resolution
    -----                                                                 -----                   ----------
    20251117_DLC_analysis_jaw.ipynb                                       2025-12-02 11:15:24     SUPERSEDED (older mtime; narrower scope `DLC_analysis_jaw` — 20260416 filename is a scope-superset)
    20260416_DLC_analysis_ws_aligned_parquet_input_jaw.ipynb              2026-04-17 16:57:22     CANONICAL (Priya-named; newest mtime; `ws_aligned_parquet_input_jaw` scope is the v5p3 interpolation notebook)
    20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb            2026-03-23 17:32:49     SIBLING (distinct scope: `reward-aligned_tongue_jaw` builder, not interp)

The canonical version for this snippet is 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
(Priya-named canonical; newest mtime; full scope marker `ws_aligned_parquet_input_tongue` matches the v5p3 interpolation pipeline).

No _v0 / _mod / _old / -Copy1 suffixes were present in either family.

Legacy-era scipy version
------------------------
These notebooks ran in Priya's local `deeplabcut` conda env on the same
Windows workstation (confirmed by Priya, 2026-04-22). That env's
scipy is pinned to 1.15.1 (`conda run -n deeplabcut python -c
'import scipy; print(scipy.__version__)'` → 1.15.1). The current
`stroke_orofacial` env carries scipy 1.17.1 — parity script in 7a.1
must decide whether to pin 1.15.1 or widen the tolerance per
docs/phase-7/interpolation-strategy.md §6. NPZ files do not carry an
explicit scipy-version metadata key.

CLAUDE.md compliance
--------------------
- This file is a NEW read-only reference committed into the consolidation
  repo. It does NOT modify, overwrite, rename, or delete the canonical
  legacy source. (CLAUDE.md Ground Rules §1, §2.)
- `# ruff: noqa` and `# fmt: off` ensure the legacy source is NEVER
  linted, reformatted, or auto-fixed by this repo's tooling. The source
  must stay byte-identical to capture time.
- DO NOT EXECUTE THIS FILE. It is a read-only reference for parity
  validation of src/stroke_orofacial/dlc_kinematics/interpolation.py in
  Phase 7a.1.
"""

# === BEGIN VERBATIM CELL 23 SOURCE ===
# ======= Tongue interpolation [v5p3] (baseline from NON-interpolated data in post-reward window) =====
# Baseline definition (UPDATED: separate LK thresholds + separate Y-percentiles for Y0 vs X0):
#   - Define a post-reward window (e.g., 0..1000 ms) around each reward center (WS→cam aligned).
#   - From NON-interpolated data (stage="drop" recommended):
#       * Y0: use points in window with lk >= BASELINE_Y_LK_THR, then take lowest BASELINE_Y0_PERCENTILE of Y.
#             Y0 = median(Y among those low-Y points)
#       * X0: use points in window with lk >= BASELINE_X_LK_THR, then take lowest BASELINE_X0_FROM_Y_PERCENTILE of Y.
#             X0 = median(X among those low-Y points)
# Final:
#   - Fill NaNs in interpolated arrays with X0/Y0
#   - Subtract X0/Y0 from all values to produce x_final/y_final
# Saves intermediate stages (raw, xrange, thr, drop, interp, interp_filled, final) + diagnostics.

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from scipy.interpolate import PchipInterpolator

# ---------------- roots ----------------
ALIGN_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\alignment_templates")
LICK_ROOT  = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\licks_and_rewards")
OUT_ROOT   = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis")

OVERWRITE = True  # if False, skip sessions already saved

CENTER_MODE = "centered_spout_midpoint"     # override any earlier global, "nose", "spout_midpoint", "eye_midpoint"

# ===================== RUN MODE =====================
RUN_MODE = "batch"   # "single" or "batch"
# SINGLE_MOUSE = "PS50"
# SINGLE_DATE  = "20250310"
# ====================================================

# ===================== USER KNOBS (BATCH) =====================
ANIMALS = ["PS54"]
DATE_START = "20250416"     # eg PS46-48 20250307, PS49 20250310, PS50 20250319, PS51-55 20250416
DATE_END   = "20250710"    # eg PS46-48 20250328, PS49 20250401, PS50 20250407, PS51-55 20250709

INCLUDE_DATES = {}
EXCLUDE_DATES = {
                # "PS51": ["20250426", "20250517"], 
                "PS54": ["20250426"], 
                #  "PS55": ["20250427", "20250428"],
                 }  # e.g. exclude a bad session for a specific mouse; use "_all" key to exclude dates across all mice  

CAM = "cam2"
FPS = 250.0

# ===================== USER KNOBS (PROCESSING) =====================
# (0) X-range sanity filter (apply before LK thresholding)
X_RANGE_MODE = "median_pm"        # "median_pm" | "fixed" | "off"
X_RANGE_PM   = 150.0              # median ± X_RANGE_PM px
X_RANGE_FIXED = (-150.0, 150.0)
X_RANGE_MEDIAN_SOURCE = "lk"      # "finite" | "lk"

# (1) likelihood thresholding (main kinematics gate)
LK_THR = 0.5

# (2) isolated hi-lk rejection
neighbor_ms = 16.0
N_NEIGH = 2

# (3) interpolate short NaN gaps
DO_INTERP = True
max_gap_ms = 56.0
REQUIRE_BRACKETED_BY_HILK = True

# interpolation method toggles
INTERP_METHOD = "pchip"           # "linear" or "pchip"
INTERP_N_SIDE = 6                 # points to include from each side (context)
INTERP_MIN_TOTAL_CONTEXT = 6      # minimum total context points
INTERP_FALLBACK = "linear"        # "linear" or "none"

# (4) baseline definition (UPDATED: separate LK + separate percentiles)
BASELINE_POST_WIN_MS = (0, 5000.0)   # window relative to reward center (ms)
BASELINE_SOURCE_STAGE = "drop"         # "thr" or "drop" (non-interpolated); recommend "drop"
BASELINE_REQUIRE_FINITE_X = True       # X0 computed only where X is finite (recommended)

# Y0 definition (example: lk>=0.7, lowest 5th percentile Y)
# If True, force Y0 to a fixed value instead of estimating from data.
FORCE_Y0 = True
Y0_FORCED_VALUE = -110.0
BASELINE_Y_LK_THR = 0.7
BASELINE_Y0_PERCENTILE = 1.0

# X0 definition (example: lk>=0.5, median X of lowest 20th percentile Y)
# If True, force X0 to a fixed value (e.g., 0 for spout midpoint) instead of estimating from data.
FORCE_X0 = True
X0_FORCED_VALUE = 0.0
BASELINE_X_LK_THR = 0.4
BASELINE_X0_FROM_Y_PERCENTILE = 25.0

# save version tag (used in filename)
VERSION_TAG = "v5p3"
# ================================================================


# ---------- helpers ----------
def load_session_paths(mouse: str, date_yyyymmdd: str, cam: str = "cam2"):
    path_lick = LICK_ROOT / mouse / f"{date_yyyymmdd}.npz"
    path_aln  = ALIGN_ROOT / cam / mouse / f"{date_yyyymmdd}.npz"
    if not path_lick.exists():
        raise FileNotFoundError(f"Missing licks_and_rewards: {path_lick}")
    if not path_aln.exists():
        raise FileNotFoundError(f"Missing alignment template: {path_aln}")
    return path_lick, path_aln

def pick_dlc_df_for_session(intermediate_data_frames: dict, date_yyyymmdd: str, cam: str):
    """
    Pick the parquet-loaded DF for the requested date+cam by matching video basename.
    Example basenames contain e.g. 'video2_YYYY-MM-DD...'
    """
    yyyy_mm_dd = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    video_token = {"cam1": "video1_", "cam2": "video2_", "cam3": "video3_", "cam4": "video4_"}.get(cam, None)
    if video_token is None:
        raise ValueError(f"Unknown cam={cam!r}. Expected one of cam1/cam2/cam3/cam4.")
    for k, df in intermediate_data_frames.items():
        base = Path(str(k)).name.lower()
        if (video_token in base) and (yyyy_mm_dd in base):
            return k, df
    raise FileNotFoundError(f"No DLC df found for {video_token}{yyyy_mm_dd} in intermediate_data_frames")

def daterange_yyyymmdd(start_yyyymmdd, end_yyyymmdd):
    d0 = datetime.strptime(start_yyyymmdd, "%Y%m%d").date()
    d1 = datetime.strptime(end_yyyymmdd, "%Y%m%d").date()
    out = []
    d = d0
    while d <= d1:
        out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out

def is_excluded(mouse, date):
    if "_all" in EXCLUDE_DATES and date in EXCLUDE_DATES["_all"]:
        return True
    if mouse in EXCLUDE_DATES and date in EXCLUDE_DATES[mouse]:
        return True
    return False

def get_dates_for_mouse(mouse):
    if INCLUDE_DATES:
        if mouse in INCLUDE_DATES:
            return list(INCLUDE_DATES[mouse])
        if "_all" in INCLUDE_DATES:
            return list(INCLUDE_DATES["_all"])
        return []
    return daterange_yyyymmdd(DATE_START, DATE_END)

def ws_samples_to_cam_frames(ws_idx, sig_camIdx__idx_ws):
    ws_idx = np.asarray(ws_idx).astype(np.int64)
    ws_idx = ws_idx[(ws_idx >= 0) & (ws_idx < len(sig_camIdx__idx_ws))]
    fr = sig_camIdx__idx_ws[ws_idx].astype(float)
    good = np.isfinite(fr)
    return ws_idx[good], fr[good]

def out_dir_for_animal(mouse):
    # preserve convention: nested in a center_mode folder
    d = OUT_ROOT / mouse / f"{mouse}_tongue_kinematics" / "processed_interpolated_data" / f"{CENTER_MODE}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def out_path_for_session(mouse, date, cam):
    # preserve convention: filename includes interp_version tag
    return out_dir_for_animal(mouse) / f"{mouse}_{date}_{cam}_tongue_interp_{VERSION_TAG}.npz"

def summary_csv_path_for_animal(mouse):
    return out_dir_for_animal(mouse) / f"{mouse}_tongue_interp_summary_{VERSION_TAG}.csv"

def compute_session_x_range(x_raw, y_raw, lk_raw):
    if X_RANGE_MODE == "off":
        return None, None, np.nan
    if X_RANGE_MODE == "fixed":
        return float(X_RANGE_FIXED[0]), float(X_RANGE_FIXED[1]), np.nan
    if X_RANGE_MODE != "median_pm":
        raise ValueError(f"Unknown X_RANGE_MODE={X_RANGE_MODE!r}")

    finite_xy = np.isfinite(x_raw) & np.isfinite(y_raw)

    if X_RANGE_MEDIAN_SOURCE == "finite":
        m = finite_xy
    elif X_RANGE_MEDIAN_SOURCE == "lk":
        m = finite_xy & np.isfinite(lk_raw) & (lk_raw >= LK_THR)
    else:
        raise ValueError(f"Unknown X_RANGE_MEDIAN_SOURCE={X_RANGE_MEDIAN_SOURCE!r}")

    if not np.any(m):
        m = finite_xy
    if not np.any(m):
        return None, None, np.nan

    med_x = float(np.nanmedian(x_raw[m]))
    x_lo = med_x - float(X_RANGE_PM)
    x_hi = med_x + float(X_RANGE_PM)
    return x_lo, x_hi, med_x

def _fill_nan_with(arr: np.ndarray, fill_value: float):
    out = arr.copy().astype(float)
    out[~np.isfinite(out)] = float(fill_value)
    return out

# ---------- gap interpolation with linear vs PCHIP ----------
def interp_small_gaps_method(arr, hi_mask, max_gap_f, require_bracketed_by_hi,
                            method="linear",
                            n_side=6,
                            min_total_context=6,
                            fallback="linear"):
    """
    Fill NaN runs of length <= max_gap_f.
    Requires bracketed by finite endpoints; optionally requires endpoints hi_mask True.
    method:
      - "linear": np.interp between endpoints
      - "pchip": PCHIP using local context points around the gap (shape-preserving)
    fallback (only used for method="pchip" when context insufficient):
      - "linear" or "none"
    """
    out = arr.copy().astype(float)
    n = len(out)

    def collect_context(left_end, right_end):
        left_pts = []
        i = left_end
        while i >= 0 and len(left_pts) < n_side:
            if hi_mask[i] and np.isfinite(out[i]):
                left_pts.append(i)
            i -= 1
        left_pts = left_pts[::-1]

        right_pts = []
        i = right_end
        while i < n and len(right_pts) < n_side:
            if hi_mask[i] and np.isfinite(out[i]):
                right_pts.append(i)
            i += 1

        pts = np.array(left_pts + right_pts, dtype=int)
        return np.unique(pts)

    i = 0
    while i < n:
        if np.isfinite(out[i]):
            i += 1
            continue

        j = i
        while j < n and (not np.isfinite(out[j])):
            j += 1

        run_len = j - i
        left = i - 1
        right = j

        if run_len <= max_gap_f and left >= 0 and right < n and np.isfinite(out[left]) and np.isfinite(out[right]):

            if require_bracketed_by_hi and (not (hi_mask[left] and hi_mask[right])):
                i = j
                continue

            if method == "linear":
                out[i:j] = np.interp(np.arange(i, j), [left, right], [out[left], out[right]])
                i = j
                continue

            if method == "pchip":
                ctx = collect_context(left, right)
                if (left not in ctx) or (right not in ctx):
                    ctx = np.unique(np.r_[ctx, [left, right]]).astype(int)

                if ctx.size < int(min_total_context):
                    if fallback == "linear":
                        out[i:j] = np.interp(np.arange(i, j), [left, right], [out[left], out[right]])
                    i = j
                    continue

                x_ctx = ctx.astype(float)
                y_ctx = out[ctx].astype(float)
                good = np.isfinite(y_ctx)
                x_ctx = x_ctx[good]
                y_ctx = y_ctx[good]
                if x_ctx.size < int(min_total_context) or np.unique(x_ctx).size < 2:
                    if fallback == "linear":
                        out[i:j] = np.interp(np.arange(i, j), [left, right], [out[left], out[right]])
                    i = j
                    continue

                try:
                    f = PchipInterpolator(x_ctx, y_ctx, extrapolate=False)
                    out[i:j] = f(np.arange(i, j, dtype=float))
                except Exception:
                    if fallback == "linear":
                        out[i:j] = np.interp(np.arange(i, j), [left, right], [out[left], out[right]])
                i = j
                continue

            raise ValueError(f"Unknown interpolation method: {method!r}")

        i = j

    return out

def _build_reward_aligned_pool_mask(n_frames: int, reward_centers_float: np.ndarray, fps: float, win_ms):
    """
    Build boolean mask over frames that fall within [win_ms[0], win_ms[1]] relative to ANY reward center.
    Uses rounded reward center frames for mask construction.
    """
    w0_ms, w1_ms = float(win_ms[0]), float(win_ms[1])
    if w1_ms < w0_ms:
        raise ValueError(f"win_ms must be (start,end) with end>=start. Got {win_ms}")
    w0_f = int(np.floor((w0_ms/1000.0) * fps))
    w1_f = int(np.ceil ((w1_ms/1000.0) * fps))

    centers_i = np.round(reward_centers_float).astype(int)
    centers_i = centers_i[(centers_i >= 0) & (centers_i < n_frames)]
    mask = np.zeros(n_frames, dtype=bool)
    for c in centers_i:
        lo = max(0, c + w0_f)
        hi = min(n_frames - 1, c + w1_f)
        if hi >= lo:
            mask[lo:hi+1] = True
    return mask, w0_f, w1_f


# ---------- main per-session processor ----------
def process_one_session(mouse: str, date: str, cam: str, fps: float):
    path_lick, path_aln = load_session_paths(mouse, date, cam=cam)
    lk  = np.load(path_lick, allow_pickle=False)
    aln = np.load(path_aln,  allow_pickle=False)

    dlc_key, df = pick_dlc_df_for_session(intermediate_data_frames, date, cam=cam)

    for col in ("tongue_x", "tongue_y", "tongue_likelihood"):
        if col not in df.columns:
            raise KeyError(f"Missing '{col}' in centered parquet df for {mouse} {date} ({dlc_key})")

    tongue_x  = df["tongue_x"].to_numpy(dtype=float)
    tongue_y  = df["tongue_y"].to_numpy(dtype=float)
    tongue_lk = df["tongue_likelihood"].to_numpy(dtype=float)
    n_frames  = len(df)

    def n_finite_xy(x, y):
        return int(np.sum(np.isfinite(x) & np.isfinite(y)))

    # ---- Stage 0: raw ----
    x_raw = tongue_x.copy()
    y_raw = tongue_y.copy()
    lk_raw = tongue_lk.copy()
    n0_finite = n_finite_xy(x_raw, y_raw)

    # ---- (0) X-range filter ----
    x0 = x_raw.copy()
    y0 = y_raw.copy()
    x_lo, x_hi, median_x_used = compute_session_x_range(x_raw, y_raw, lk_raw)

    n_bad_x = 0
    if (x_lo is not None) and (x_hi is not None):
        bad_x = (~np.isfinite(x0)) | (x0 < x_lo) | (x0 > x_hi)
        n_bad_x = int(np.sum(bad_x))
        x0[bad_x] = np.nan
        y0[bad_x] = np.nan
    n_after_xrange = n_finite_xy(x0, y0)

    # ---- (1) LK threshold ----
    hi = (
        np.isfinite(lk_raw) & (lk_raw >= LK_THR) &
        np.isfinite(x0)     & np.isfinite(y0)
    )
    x_thr = x0.copy(); y_thr = y0.copy()
    x_thr[~hi] = np.nan; y_thr[~hi] = np.nan
    n_after_thr = n_finite_xy(x_thr, y_thr)

    # ---- (2) drop isolated hi-lk ----
    neighbor_f = max(int(round((neighbor_ms/1000.0) * fps)), 1)
    hi_idx = np.flatnonzero(np.isfinite(x_thr) & np.isfinite(y_thr))
    keep_hi = np.zeros(n_frames, dtype=bool)

    j0 = 0
    j1 = 0
    for ii in hi_idx:
        while j0 < hi_idx.size and hi_idx[j0] < ii - neighbor_f:
            j0 += 1
        while j1 < hi_idx.size and hi_idx[j1] <= ii + neighbor_f:
            j1 += 1
        n_neighbors = (j1 - j0) - 1
        if n_neighbors >= N_NEIGH:
            keep_hi[ii] = True

    x_drop = x0.copy(); y_drop = y0.copy()
    x_drop[~keep_hi] = np.nan; y_drop[~keep_hi] = np.nan
    n_after_drop = n_finite_xy(x_drop, y_drop)

    # ---- (3) interpolate short NaN gaps ----
    if DO_INTERP:
        max_gap_f = max(int(round((max_gap_ms/1000.0) * fps)), 1)
        hi_mask_post = np.isfinite(x_drop) & np.isfinite(y_drop)
        x_interp = interp_small_gaps_method(
            x_drop, hi_mask_post, max_gap_f,
            require_bracketed_by_hi=REQUIRE_BRACKETED_BY_HILK,
            method=INTERP_METHOD,
            n_side=INTERP_N_SIDE,
            min_total_context=INTERP_MIN_TOTAL_CONTEXT,
            fallback=INTERP_FALLBACK
        )
        y_interp = interp_small_gaps_method(
            y_drop, hi_mask_post, max_gap_f,
            require_bracketed_by_hi=REQUIRE_BRACKETED_BY_HILK,
            method=INTERP_METHOD,
            n_side=INTERP_N_SIDE,
            min_total_context=INTERP_MIN_TOTAL_CONTEXT,
            fallback=INTERP_FALLBACK
        )
    else:
        max_gap_f = 0
        x_interp = x_drop.copy()
        y_interp = y_drop.copy()

    n_after_interp = n_finite_xy(x_interp, y_interp)
    n_nans_after_interp = int(np.sum(~(np.isfinite(x_interp) & np.isfinite(y_interp))))

    # ---- keep for backward-compat plotting code ----
    x_thr_interp = x_interp.copy()
    y_thr_interp = y_interp.copy()
    n_after_thr_interp = n_finite_xy(x_thr_interp, y_thr_interp)

    # ---- reward centers (WS → cam) ----
    sig_camIdx__idx_ws = aln["sig_camIdx__idx_ws"]

    ws_reward_mouseL = lk["Reward_R"].astype(np.int64)  # flip
    ws_reward_mouseR = lk["Reward_L"].astype(np.int64)  # flip

    _, fr_reward_mouseL = ws_samples_to_cam_frames(ws_reward_mouseL, sig_camIdx__idx_ws)
    _, fr_reward_mouseR = ws_samples_to_cam_frames(ws_reward_mouseR, sig_camIdx__idx_ws)

    fr_reward_all = np.concatenate([fr_reward_mouseL, fr_reward_mouseR], axis=0)
    fr_reward_all = fr_reward_all[np.isfinite(fr_reward_all)]
    n_rewards_total = int(fr_reward_all.size)

    # ---- (4) BASELINE from NON-interpolated data in post-reward window (SEPARATE Y0 vs X0 rules) ----
    pool_mask, win_start_f, win_end_f = _build_reward_aligned_pool_mask(
        n_frames=n_frames,
        reward_centers_float=fr_reward_all,
        fps=fps,
        win_ms=BASELINE_POST_WIN_MS
    )

    if BASELINE_SOURCE_STAGE == "thr":
        x_base_src = x_thr
        y_base_src = y_thr
    elif BASELINE_SOURCE_STAGE == "drop":
        x_base_src = x_drop
        y_base_src = y_drop
    else:
        raise ValueError(f"Unknown BASELINE_SOURCE_STAGE={BASELINE_SOURCE_STAGE!r}. Use 'thr' or 'drop'.")

    # --- Y0 pool: window AND lk>=BASELINE_Y_LK_THR AND finite y (and x if required) ---
    base_y_finite = np.isfinite(y_base_src)
    if BASELINE_REQUIRE_FINITE_X:
        base_y_finite &= np.isfinite(x_base_src)
    baseline_pool_Y = pool_mask & base_y_finite & np.isfinite(lk_raw) & (lk_raw >= float(BASELINE_Y_LK_THR))
    n_pool_Y = int(np.sum(baseline_pool_Y))
    if n_pool_Y == 0:
        raise RuntimeError(
            f"{mouse} {date}: baseline_pool_Y empty. stage={BASELINE_SOURCE_STAGE} "
            f"win_ms={BASELINE_POST_WIN_MS} lk_thr_Y={BASELINE_Y_LK_THR}"
        )
    y_pool_Y = y_base_src[baseline_pool_Y]
    y_cut_Y0 = float(np.nanpercentile(y_pool_Y, float(BASELINE_Y0_PERCENTILE)))
    lowY_for_Y0 = baseline_pool_Y & (y_base_src <= y_cut_Y0)
    n_lowY_for_Y0 = int(np.sum(lowY_for_Y0))
    if n_lowY_for_Y0 == 0:
        # fallback: lowest-K points by y within Y-pool
        k = max(10, int(np.ceil((float(BASELINE_Y0_PERCENTILE)/100.0) * y_pool_Y.size)))
        pool_idx = np.flatnonzero(baseline_pool_Y)
        idx_sorted = np.argsort(y_pool_Y)[:min(k, y_pool_Y.size)]
        lowY_for_Y0 = np.zeros(n_frames, dtype=bool)
        lowY_for_Y0[pool_idx[idx_sorted]] = True
        n_lowY_for_Y0 = int(np.sum(lowY_for_Y0))
    Y0 = float(np.nanmedian(y_base_src[lowY_for_Y0]))

    # --- optional override (NEW, mirrors X0) ---
    Y0_data = float(Y0)  # keep what data would have given
    if FORCE_Y0:
        Y0 = float(Y0_FORCED_VALUE)

    # --- X0 pool: window AND lk>=BASELINE_X_LK_THR AND finite y (and x if required) ---
    base_x_finite = np.isfinite(y_base_src)
    if BASELINE_REQUIRE_FINITE_X:
        base_x_finite &= np.isfinite(x_base_src)
    baseline_pool_X = pool_mask & base_x_finite & np.isfinite(lk_raw) & (lk_raw >= float(BASELINE_X_LK_THR))
    n_pool_X = int(np.sum(baseline_pool_X))
    if n_pool_X == 0:
        raise RuntimeError(
            f"{mouse} {date}: baseline_pool_X empty. stage={BASELINE_SOURCE_STAGE} "
            f"win_ms={BASELINE_POST_WIN_MS} lk_thr_X={BASELINE_X_LK_THR}"
        )
    y_pool_X = y_base_src[baseline_pool_X]
    y_cut_X0 = float(np.nanpercentile(y_pool_X, float(BASELINE_X0_FROM_Y_PERCENTILE)))
    lowY_for_X0 = baseline_pool_X & (y_base_src <= y_cut_X0)
    n_lowY_for_X0 = int(np.sum(lowY_for_X0))
    if n_lowY_for_X0 == 0:
        k = max(10, int(np.ceil((float(BASELINE_X0_FROM_Y_PERCENTILE)/100.0) * y_pool_X.size)))
        pool_idx = np.flatnonzero(baseline_pool_X)
        idx_sorted = np.argsort(y_pool_X)[:min(k, y_pool_X.size)]
        lowY_for_X0 = np.zeros(n_frames, dtype=bool)
        lowY_for_X0[pool_idx[idx_sorted]] = True
        n_lowY_for_X0 = int(np.sum(lowY_for_X0))
    # median X among low-Y-for-X0 points
    X0 = float(np.nanmedian(x_base_src[lowY_for_X0]))
    # --- optional override ---
    X0_data = float(X0)  # keep what data would have given
    if FORCE_X0:
        X0 = float(X0_FORCED_VALUE)

    # ---- Fill NaNs in interpolated with baseline, then subtract baseline for FINAL ----
    x_interp_filled = _fill_nan_with(x_interp, X0)
    y_interp_filled = _fill_nan_with(y_interp, Y0)

    x_final = x_interp_filled - X0
    y_final = y_interp_filled - Y0

    # ---- rewards as integer frames for saving ----
    fr_reward_mouseL_i = np.round(fr_reward_mouseL).astype(int)
    fr_reward_mouseR_i = np.round(fr_reward_mouseR).astype(int)
    fr_reward_mouseL_i = fr_reward_mouseL_i[(fr_reward_mouseL_i >= 0) & (fr_reward_mouseL_i < n_frames)]
    fr_reward_mouseR_i = fr_reward_mouseR_i[(fr_reward_mouseR_i >= 0) & (fr_reward_mouseR_i < n_frames)]

    dropped_by_xrange = int(n0_finite - n_finite_xy(x0, y0))
    dropped_by_thr = int(n_finite_xy(x0, y0) - n_after_thr)
    dropped_by_isolation = int(n_after_thr - n_after_drop)
    gained_by_interp = int(n_after_interp - n_after_drop)
    frac_interp = (gained_by_interp / max(1, int(n_after_drop))) if n_after_drop > 0 else np.nan

    # ---- DIAGNOSTICS ----
    print(
        f"[interp] {mouse} {date} {cam} method={INTERP_METHOD} fallback={INTERP_FALLBACK} "
        f"max_gap_ms={max_gap_ms} (f={max_gap_f}) gained={gained_by_interp} frac~{frac_interp:.3f}"
    )
    print(
        f"[baseline-Y0] stage={BASELINE_SOURCE_STAGE} win_ms={BASELINE_POST_WIN_MS} "
        f"lk_thr={BASELINE_Y_LK_THR} pool_pts={n_pool_Y:,} "
        f"pY={BASELINE_Y0_PERCENTILE:g} y_cut={y_cut_Y0:.3f} low_pts={n_lowY_for_Y0:,} Y0={Y0:.3f}"
    )
    print(
        f"[baseline-X0] stage={BASELINE_SOURCE_STAGE} win_ms={BASELINE_POST_WIN_MS} "
        f"lk_thr={BASELINE_X_LK_THR} pool_pts={n_pool_X:,} "
        f"pY_for_X0={BASELINE_X0_FROM_Y_PERCENTILE:g} y_cut={y_cut_X0:.3f} low_pts={n_lowY_for_X0:,} X0={X0:.3f}"
    )
    if FORCE_X0:
        print(f"[baseline-X0] OVERRIDE ON: using X0={X0:.3f} (forced) | would-have-been X0_data={X0_data:.3f}")
    else:
        print(f"[baseline-X0] override OFF: using X0_data={X0_data:.3f}")

    if FORCE_Y0:
        print(f"[baseline-Y0] OVERRIDE ON: using Y0={Y0:.3f} (forced) | would-have-been Y0_data={Y0_data:.3f}")
    else:
        print(f"[baseline-Y0] override OFF: using Y0_data={Y0_data:.3f}")

    summary = dict(
        mouse=mouse, date=date, cam=cam, fps=float(fps),
        dlc_key=str(dlc_key), n_frames=int(n_frames),
        n_rewards_mouseL=int(len(fr_reward_mouseL_i)),
        n_rewards_mouseR=int(len(fr_reward_mouseR_i)),

        # interp params
        INTERP_METHOD=str(INTERP_METHOD),
        INTERP_N_SIDE=int(INTERP_N_SIDE),
        INTERP_MIN_TOTAL_CONTEXT=int(INTERP_MIN_TOTAL_CONTEXT),
        INTERP_FALLBACK=str(INTERP_FALLBACK),
        REQUIRE_BRACKETED_BY_HILK=bool(REQUIRE_BRACKETED_BY_HILK),

        # x-range params
        X_RANGE_MODE=str(X_RANGE_MODE),
        X_RANGE_PM=float(X_RANGE_PM),
        X_RANGE_FIXED=np.array(X_RANGE_FIXED, dtype=float),
        X_RANGE_MEDIAN_SOURCE=str(X_RANGE_MEDIAN_SOURCE),
        median_x_used=float(median_x_used) if np.isfinite(median_x_used) else np.nan,
        x_range_low=float(x_lo) if x_lo is not None else np.nan,
        x_range_high=float(x_hi) if x_hi is not None else np.nan,

        # baseline params + results (separate)
        BASELINE_POST_WIN_MS=np.array(BASELINE_POST_WIN_MS, dtype=float),
        BASELINE_SOURCE_STAGE=str(BASELINE_SOURCE_STAGE),
        BASELINE_REQUIRE_FINITE_X=bool(BASELINE_REQUIRE_FINITE_X),

        FORCE_Y0=bool(FORCE_Y0),
        Y0_FORCED_VALUE=float(Y0_FORCED_VALUE),
        Y0_data=float(Y0_data),
        BASELINE_Y_LK_THR=float(BASELINE_Y_LK_THR),
        BASELINE_Y0_PERCENTILE=float(BASELINE_Y0_PERCENTILE),
        baseline_pool_Y_pts=int(n_pool_Y),
        baseline_lowY_Y0_pts=int(n_lowY_for_Y0),
        y_cut_Y0=float(y_cut_Y0),
        Y0=float(Y0),

        FORCE_X0=bool(FORCE_X0),
        X0_FORCED_VALUE=float(X0_FORCED_VALUE),
        X0_data=float(X0_data),
        BASELINE_X_LK_THR=float(BASELINE_X_LK_THR),
        BASELINE_X0_FROM_Y_PERCENTILE=float(BASELINE_X0_FROM_Y_PERCENTILE),
        baseline_pool_X_pts=int(n_pool_X),
        baseline_lowY_X0_pts=int(n_lowY_for_X0),
        y_cut_X0=float(y_cut_X0),
        X0=float(X0),

        # counts
        n_finite_raw=int(n0_finite),
        n_finite_after_xrange=int(n_finite_xy(x0, y0)),
        n_finite_after_thr=int(n_after_thr),
        n_finite_after_drop=int(n_after_drop),
        n_finite_after_interp=int(n_after_interp),
        n_finite_after_thr_interp=int(n_after_thr_interp),
        n_nans_after_interp=int(n_nans_after_interp),

        dropped_by_xrange=int(dropped_by_xrange),
        dropped_by_thr=int(dropped_by_thr),
        dropped_by_isolation=int(dropped_by_isolation),
        gained_by_interp=int(gained_by_interp),

        LK_THR=float(LK_THR),
        neighbor_ms=float(neighbor_ms),
        neighbor_f=int(neighbor_f),
        N_NEIGH=int(N_NEIGH),
        DO_INTERP=bool(DO_INTERP),
        max_gap_ms=float(max_gap_ms),
        max_gap_f=int(max_gap_f),
    )

    PROC = dict(
        mouse=mouse, date=date, cam=cam, fps=float(fps),
        dlc_key=str(dlc_key), n_frames=int(n_frames),

        # raw + stages
        x_raw=x_raw, y_raw=y_raw, lk=lk_raw,
        x_xrange=x0, y_xrange=y0,
        x_thr=x_thr, y_thr=y_thr,
        keep_hi=keep_hi.astype(np.uint8),
        x_drop=x_drop, y_drop=y_drop,
        x_interp=x_interp, y_interp=y_interp,
        x_interp_filled=x_interp_filled, y_interp_filled=y_interp_filled,
        x_final=x_final, y_final=y_final,
        x_thr_interp=x_thr_interp, y_thr_interp=y_thr_interp,

        # baseline scalars + cuts
        X0=float(X0), Y0=float(Y0),
        X0_data=float(X0_data),
        Y0_data=float(Y0_data),
        FORCE_X0=bool(FORCE_X0),
        X0_FORCED_VALUE=float(X0_FORCED_VALUE),
        FORCE_Y0=bool(FORCE_Y0),
        Y0_FORCED_VALUE=float(Y0_FORCED_VALUE),
        y_cut_Y0=float(y_cut_Y0),
        y_cut_X0=float(y_cut_X0),
        BASELINE_POST_WIN_MS=np.array(BASELINE_POST_WIN_MS, dtype=float),
        BASELINE_SOURCE_STAGE=str(BASELINE_SOURCE_STAGE),
        BASELINE_REQUIRE_FINITE_X=bool(BASELINE_REQUIRE_FINITE_X),
        BASELINE_Y_LK_THR=float(BASELINE_Y_LK_THR),
        BASELINE_Y0_PERCENTILE=float(BASELINE_Y0_PERCENTILE),
        baseline_pool_Y_pts=int(n_pool_Y),
        baseline_lowY_Y0_pts=int(n_lowY_for_Y0),
        BASELINE_X_LK_THR=float(BASELINE_X_LK_THR),
        BASELINE_X0_FROM_Y_PERCENTILE=float(BASELINE_X0_FROM_Y_PERCENTILE),
        baseline_pool_X_pts=int(n_pool_X),
        baseline_lowY_X0_pts=int(n_lowY_for_X0),

        # settings
        INTERP_METHOD=str(INTERP_METHOD),
        INTERP_N_SIDE=int(INTERP_N_SIDE),
        INTERP_MIN_TOTAL_CONTEXT=int(INTERP_MIN_TOTAL_CONTEXT),
        INTERP_FALLBACK=str(INTERP_FALLBACK),

        X_RANGE_MODE=str(X_RANGE_MODE),
        X_RANGE_PM=float(X_RANGE_PM),
        X_RANGE_FIXED=np.array(X_RANGE_FIXED, dtype=float),
        X_RANGE_MEDIAN_SOURCE=str(X_RANGE_MEDIAN_SOURCE),
        median_x_used=float(median_x_used) if np.isfinite(median_x_used) else np.nan,
        x_range_low=float(x_lo) if x_lo is not None else np.nan,
        x_range_high=float(x_hi) if x_hi is not None else np.nan,

        LK_THR=float(LK_THR),

        # rewards (integer frames)
        fr_reward_mouseL=fr_reward_mouseL_i,
        fr_reward_mouseR=fr_reward_mouseR_i,

        summary=summary,
    )

    return PROC, summary


# ---------- run ----------
all_rows = []
per_animal_rows = {}

n_ok = 0
n_skip = 0
n_fail = 0

if RUN_MODE == "single":
    mouse = SINGLE_MOUSE
    date  = SINGLE_DATE
    out_path = out_path_for_session(mouse, date, CAM)

    try:
        PROC, row = process_one_session(mouse, date, CAM, FPS)
        np.savez_compressed(str(out_path), **PROC)
        row = dict(row); row["out_path"] = str(out_path); row["status"] = "ok"
        all_rows.append(row)
        per_animal_rows.setdefault(mouse, []).append(row)
        n_ok += 1
        print(f"[saved] single session NPZ -> {out_path}")
    except Exception as e:
        all_rows.append(dict(mouse=mouse, date=date, cam=CAM, status="fail", error=repr(e)))
        n_fail += 1
        print(f"[fail] {mouse} {date}: {repr(e)}")

else:
    per_animal_rows = {m: [] for m in ANIMALS}
    for mouse in ANIMALS:
        dates = get_dates_for_mouse(mouse)
        for date in dates:
            if is_excluded(mouse, date):
                n_skip += 1
                continue

            out_path = out_path_for_session(mouse, date, CAM)
            if out_path.exists() and (not OVERWRITE):
                n_skip += 1
                continue

            try:
                PROC, row = process_one_session(mouse, date, CAM, FPS)
                np.savez_compressed(str(out_path), **PROC)

                row = dict(row); row["out_path"] = str(out_path); row["status"] = "ok"
                all_rows.append(row)
                per_animal_rows[mouse].append(row)
                n_ok += 1

            except Exception as e:
                all_rows.append(dict(mouse=mouse, date=date, cam=CAM, status="fail", error=repr(e)))
                n_fail += 1
                print(f"[fail] {mouse} {date}: {repr(e)}")

# ---------- write CSV summaries ----------
for mouse, rows in per_animal_rows.items():
    if not rows:
        continue
    df_sum = pd.DataFrame(rows).sort_values(["mouse", "date"])
    p_csv = summary_csv_path_for_animal(mouse)
    df_sum.to_csv(p_csv, index=False)
    print(f"[saved] {mouse} summary CSV -> {p_csv}")

df_all = pd.DataFrame(all_rows)
p_all = OUT_ROOT / f"{mouse}" / f"{mouse}_tongue_kinematics" / "processed_interpolated_data" / f"{CENTER_MODE}" / f"tongue_kinematics_processed_interpolated_summary_{VERSION_TAG}_{CENTER_MODE}.csv"
df_all.to_csv(p_all, index=False)
print(f"[saved] combined summary CSV -> {p_all}")

print(f"[done] ok={n_ok}  skipped={n_skip}  failed={n_fail}")
if n_fail and ("status" in df_all.columns):
    bad = df_all[df_all["status"] == "fail"].head(20)
    if not bad.empty:
        print("\nFailures (first 20):")
        print(bad[["mouse","date","cam","error"]].to_string(index=False))
# === END VERBATIM CELL 23 SOURCE ===
