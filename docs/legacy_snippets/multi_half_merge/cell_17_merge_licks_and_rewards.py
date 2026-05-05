"""Vendored from legacy tongue notebook — DO NOT modify in place.

Source notebook: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Notebook SHA256: ed12c54cd4cf348470cbd0fc05ee2fe20548195a52be9832c1164737dabdb643
Cell index: 17
Cell SHA256: b2819b791668e18c236517fda44e8f83ab71d13e2477f071cf9ac5563a546c53
Classification: production
Title: licks_and_rewards NPZ merge — Architecture X Layer 1

Concatenates 1D timeseries axis-0; offsets frame-index arrays by n_cam_A; carries over only-in-A/only-in-B keys (offsets B-only frame-index keys); bakes merged_from_A, merged_from_B, cam_frame_offset_for_B, merged_n_cam_A, merged_n_cam_B provenance.

This file is a byte-identical vendor of the cell source for audit
reference (Task 1c of Phase 7-pre-multi-half). Re-implementations
in src/stroke_orofacial/spout_behavior/multi_half_merge.py port from
this snippet rather than the live notebook (which may evolve).
"""

# ===================== ORIGINAL CELL SOURCE BELOW =====================

# Merge licks_and_rewards NPZ files that were split across multiple sessions

import re
import numpy as np
from pathlib import Path

# ===================== USER SETTINGS =====================
ROOT_LR = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\licks_and_rewards")

MOUSE = "PS48"
DATE  = "20250314"   # YYYYMMDD

OVERWRITE = True

# If you *know* the frame count of the merged session, you can set it.
# If None, we'll infer n_cam_A from the first file.
N_CAM_OVERRIDE = None
# =========================================================

lr_dir = ROOT_LR / MOUSE
lr_dir.mkdir(parents=True, exist_ok=True)

dst = lr_dir / f"{DATE}.npz"

if dst.exists() and not OVERWRITE:
    print(f"[skip] Destination exists and OVERWRITE=False:\n  {dst}")
    raise SystemExit

# ---- find candidates ----
# Common patterns:
#   20250314a.npz / 20250314b.npz
#   20250314_*.npz
#   20250314T*.npz
cands = sorted(lr_dir.glob(f"{DATE}*.npz"))

# if the exact output file is in candidates, remove it from inputs
cands = [p for p in cands if p.name != f"{DATE}.npz"]

if len(cands) == 0:
    raise FileNotFoundError(f"No licks_and_rewards NPZs found matching {DATE} in:\n  {lr_dir}")

if len(cands) != 2:
    print("[found] candidates:")
    for p in cands:
        print(" ", p.name)
    raise RuntimeError(
        f"Expected exactly 2 NPZ parts for {MOUSE} {DATE}, found {len(cands)}.\n"
        "If you have extra versions (csv-derived, old runs, etc.), move them out or set a more specific glob."
    )

# ---- sort order: prefer 'a' before 'b' if present; else by name ----
def sort_key(p: Path):
    name = p.name.lower()
    # a/b suffix priority
    m = re.search(rf"{DATE}([ab])\.npz$", name)
    if m:
        return (0, m.group(1))  # a then b
    return (1, name)

cands = sorted(cands, key=sort_key)
srcA, srcB = cands[0], cands[1]

print("[merge licks_and_rewards] inputs:")
print("  A:", srcA.name)
print("  B:", srcB.name)
print("  ->", dst)

A = np.load(srcA, allow_pickle=True)
B = np.load(srcB, allow_pickle=True)

keysA = set(A.files)
keysB = set(B.files)

common = sorted(keysA & keysB)
onlyA  = sorted(keysA - keysB)
onlyB  = sorted(keysB - keysA)

print(f"[info] keys: common={len(common)}  onlyA={len(onlyA)}  onlyB={len(onlyB)}")
if onlyA:
    print("  onlyA:", onlyA[:25], "..." if len(onlyA) > 25 else "")
if onlyB:
    print("  onlyB:", onlyB[:25], "..." if len(onlyB) > 25 else "")

def _as_array(x):
    try:
        return np.asarray(x)
    except Exception:
        return None

def _is_numeric_array(x):
    arr = _as_array(x)
    return (arr is not None) and np.issubdtype(arr.dtype, np.number)

def _infer_n_cam(npz):
    # try common keys first
    for k in ["cam_times", "sig_camTimes__idx_cam", "t_cam", "frame_times_s", "camTimes"]:
        if k in npz.files:
            arr = np.asarray(npz[k])
            if arr.ndim == 1 and arr.size > 0:
                return int(arr.size)
    for k in ["n_frames", "n_cam", "nFrames"]:
        if k in npz.files:
            try:
                return int(npz[k])
            except Exception:
                pass

    # fallback: infer from the largest "timeseries-like" 1D array
    best = None
    for k in npz.files:
        arr = _as_array(npz[k])
        if arr is None:
            continue
        if arr.ndim == 1 and arr.size > 1000 and _is_numeric_array(arr):
            best = max(best or 0, int(arr.size))
    return best

def _looks_like_frame_indices(arr, n_cam_hint):
    # heuristics: integer-ish 1D array, nonnegative, max within [0..n_cam_hint)
    a = np.asarray(arr)
    if a.ndim != 1 or a.size == 0:
        return False
    if not np.issubdtype(a.dtype, np.number):
        return False
    aa = a[np.isfinite(a)]
    if aa.size == 0:
        return False
    # integer-ish
    if np.nanmax(np.abs(aa - np.round(aa))) > 1e-6:
        return False
    mn = float(np.nanmin(aa))
    mx = float(np.nanmax(aa))
    if mn < -1:
        return False
    if n_cam_hint is not None and np.isfinite(n_cam_hint) and n_cam_hint > 0:
        # allow a little slack because some arrays might include sentinel values
        return mx < (n_cam_hint + 5)
    return True

n_cam_A = _infer_n_cam(A)
n_cam_B = _infer_n_cam(B)

if N_CAM_OVERRIDE is not None:
    n_cam_A = int(N_CAM_OVERRIDE)

if n_cam_A is None:
    raise RuntimeError(
        "Could not infer n_cam (frame count) from the licks_and_rewards NPZ.\n"
        "Set N_CAM_OVERRIDE to your merged frame count (e.g., 1148512)."
    )

print(f"[info] inferred n_cam_A={n_cam_A:,}  n_cam_B={n_cam_B if n_cam_B is None else f'{n_cam_B:,}'}")

offset = int(n_cam_A)

out = {}

# ---- merge common keys ----
for k in common:
    a = A[k]
    b = B[k]

    arrA = _as_array(a)
    arrB = _as_array(b)

    # keep scalars/strings/objects from A unless we can merge arrays meaningfully
    if arrA is None or arrB is None:
        out[k] = a
        continue

    # If both are 1D timeseries of length n_cam, concatenate
    if (arrA.ndim == 1) and (arrB.ndim == 1) and (_is_numeric_array(arrA)) and (_is_numeric_array(arrB)):
        if arrA.size == n_cam_A and (n_cam_B is None or arrB.size == n_cam_B):
            out[k] = np.concatenate([arrA, arrB], axis=0)
            continue

    # If looks like frame indices, offset B and concatenate
    if _looks_like_frame_indices(arrA, n_cam_A) and _looks_like_frame_indices(arrB, n_cam_B or arrB.size + 10):
        b_shift = arrB.copy()
        m = np.isfinite(b_shift)
        b_shift[m] = b_shift[m] + offset
        out[k] = np.concatenate([arrA, b_shift], axis=0)
        continue

    # If both arrays have same dtype/ndim and first dimension is "events", just concat on axis 0
    if _is_numeric_array(arrA) and _is_numeric_array(arrB) and (arrA.ndim == arrB.ndim) and (arrA.dtype == arrB.dtype):
        if arrA.ndim >= 1 and arrA.shape[1:] == arrB.shape[1:]:
            out[k] = np.concatenate([arrA, arrB], axis=0)
            continue

    # default: keep A
    out[k] = a

# ---- bring along keys unique to A/B ----
for k in onlyA:
    out[k] = A[k]

for k in onlyB:
    # if it's a frame-index array, offset it before adding
    arrB = _as_array(B[k])
    if arrB is not None and _looks_like_frame_indices(arrB, n_cam_B or None):
        b_shift = arrB.copy()
        m = np.isfinite(b_shift)
        b_shift[m] = b_shift[m] + offset
        out[k] = b_shift
    else:
        out[k] = B[k]

# ---- helpful metadata ----
out["merged_from_A"] = str(srcA)
out["merged_from_B"] = str(srcB)
out["cam_frame_offset_for_B"] = np.int64(offset)
out["merged_n_cam_A"] = np.int64(n_cam_A)
if n_cam_B is not None:
    out["merged_n_cam_B"] = np.int64(n_cam_B)

# ---- save ----
dst.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(str(dst), **out)

print(f"[save] {dst}")
