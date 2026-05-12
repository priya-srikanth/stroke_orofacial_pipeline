"""Vendored from legacy tongue notebook — DO NOT modify in place.

Source notebook: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Notebook SHA256: ed12c54cd4cf348470cbd0fc05ee2fe20548195a52be9832c1164737dabdb643
Cell index: 16
Cell SHA256: 0c25043bb9ab95d8e876d0244db09777c24e196f4759c249648720defb24b068
Classification: production
Title: Alignment-template merge — Architecture X Layer 3

Concatenates two per-half templates: asserts Fs_ws_input match; offsets wsIdx_cam_B by ws_offset=n_ws_A and camIdx_ws_B by cam_offset=n_cam_A; shifts camTimes_B / wsTimes_B to be continuous; sanity-checks lengths + monotonicity; bakes provenance keys.

This file is a byte-identical vendor of the cell source for audit
reference (Task 1c of Phase 7-pre-multi-half). Re-implementations
in src/stroke_orofacial/spout_behavior/multi_half_merge.py port from
this snippet rather than the live notebook (which may evolve).
"""

# ===================== ORIGINAL CELL SOURCE BELOW =====================

# Merge alignment templates that were split across multiple sessions

import numpy as np
from pathlib import Path

# ===== USER SETTINGS =====
ALIGN_TEMPLATE_ROOT = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\alignment_templates")

MOUSE = "PS48"
CAM   = "cam2"
DATE  = "20250314"

# your split template names
SRC_A = ALIGN_TEMPLATE_ROOT / CAM / MOUSE / f"{DATE}a.npz"
SRC_B = ALIGN_TEMPLATE_ROOT / CAM / MOUSE / f"{DATE}b.npz"

DST   = ALIGN_TEMPLATE_ROOT / CAM / MOUSE / f"{DATE}.npz"   # merged output

OVERWRITE = True
# =========================

REQ_KEYS = [
    "Fs_ws_input",
    "sig_wsIdx__idx_cam",   # cam -> ws index (len = #cam frames)
    "sig_camIdx__idx_ws",   # ws -> cam index (len = #ws samples)
    "sig_camTimes__idx_cam",
    "sig_wsTimes__idx_ws",
]

for p in [SRC_A, SRC_B]:
    if not p.exists():
        raise FileNotFoundError(f"Missing: {p}")

if DST.exists() and (not OVERWRITE):
    raise RuntimeError(f"Destination exists and OVERWRITE=False:\n  {DST}")

A = np.load(SRC_A, allow_pickle=False)
B = np.load(SRC_B, allow_pickle=False)

missingA = [k for k in REQ_KEYS if k not in A.files]
missingB = [k for k in REQ_KEYS if k not in B.files]
if missingA or missingB:
    raise KeyError(f"Missing keys.\nA missing: {missingA}\nB missing: {missingB}")

FsA = float(A["Fs_ws_input"])
FsB = float(B["Fs_ws_input"])
if not np.isclose(FsA, FsB):
    raise ValueError(f"Fs mismatch: A={FsA} vs B={FsB}")
Fs = FsA
dt_ws = 1.0 / Fs

wsIdx_cam_A = A["sig_wsIdx__idx_cam"].astype(np.float64, copy=False)
wsIdx_cam_B = B["sig_wsIdx__idx_cam"].astype(np.float64, copy=False)

camTimes_A  = A["sig_camTimes__idx_cam"].astype(np.float64, copy=False)
camTimes_B  = B["sig_camTimes__idx_cam"].astype(np.float64, copy=False)

camIdx_ws_A = A["sig_camIdx__idx_ws"].astype(np.float64, copy=False)
camIdx_ws_B = B["sig_camIdx__idx_ws"].astype(np.float64, copy=False)

wsTimes_A   = A["sig_wsTimes__idx_ws"].astype(np.float64, copy=False)
wsTimes_B   = B["sig_wsTimes__idx_ws"].astype(np.float64, copy=False)

n_cam_A = int(len(wsIdx_cam_A))
n_cam_B = int(len(wsIdx_cam_B))
n_ws_A  = int(len(camIdx_ws_A))
n_ws_B  = int(len(camIdx_ws_B))

print(f"[A] n_cam={n_cam_A:,}  n_ws={n_ws_A:,}")
print(f"[B] n_cam={n_cam_B:,}  n_ws={n_ws_B:,}")

# ---- offsets ----
ws_offset  = n_ws_A
cam_offset = n_cam_A

# ---- shift B’s mappings into A’s index spaces ----
# cam->ws: add ws_offset to ws indices
wsIdx_cam_B_shift = wsIdx_cam_B.copy()
m = np.isfinite(wsIdx_cam_B_shift)
wsIdx_cam_B_shift[m] = wsIdx_cam_B_shift[m] + ws_offset

# ws->cam: add cam_offset to cam indices
camIdx_ws_B_shift = camIdx_ws_B.copy()
m = np.isfinite(camIdx_ws_B_shift)
camIdx_ws_B_shift[m] = camIdx_ws_B_shift[m] + cam_offset

# ---- build continuous time axes ----
# use dt_cam inferred from A camTimes if possible; fallback to median from B; else 1
def infer_dt(t):
    t = np.asarray(t, float)
    t = t[np.isfinite(t)]
    if t.size < 3:
        return None
    d = np.diff(t)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return None
    return float(np.nanmedian(d))

dt_cam = infer_dt(camTimes_A)
if dt_cam is None:
    dt_cam = infer_dt(camTimes_B)
if dt_cam is None:
    dt_cam = 1.0

# camTimes_B: shift so it starts after camTimes_A ends
camTimes_B_shift = camTimes_B.copy()
t0A = float(camTimes_A[np.isfinite(camTimes_A)][-1]) if np.any(np.isfinite(camTimes_A)) else 0.0
tB0 = float(camTimes_B[np.isfinite(camTimes_B)][0])  if np.any(np.isfinite(camTimes_B)) else 0.0
# align B start to A end + dt_cam
camTimes_B_shift[np.isfinite(camTimes_B_shift)] = (camTimes_B_shift[np.isfinite(camTimes_B_shift)] - tB0) + (t0A + dt_cam)

# wsTimes_B: shift so it starts after wsTimes_A ends
wsTimes_B_shift = wsTimes_B.copy()
w0A = float(wsTimes_A[np.isfinite(wsTimes_A)][-1]) if np.any(np.isfinite(wsTimes_A)) else 0.0
wB0 = float(wsTimes_B[np.isfinite(wsTimes_B)][0])  if np.any(np.isfinite(wsTimes_B)) else 0.0
wsTimes_B_shift[np.isfinite(wsTimes_B_shift)] = (wsTimes_B_shift[np.isfinite(wsTimes_B_shift)] - wB0) + (w0A + dt_ws)

# ---- concatenate ----
wsIdx_cam_M = np.concatenate([wsIdx_cam_A, wsIdx_cam_B_shift], axis=0)
camTimes_M  = np.concatenate([camTimes_A,  camTimes_B_shift], axis=0)

camIdx_ws_M = np.concatenate([camIdx_ws_A, camIdx_ws_B_shift], axis=0)
wsTimes_M   = np.concatenate([wsTimes_A,   wsTimes_B_shift], axis=0)

# ---- sanity checks ----
if len(wsIdx_cam_M) != (n_cam_A + n_cam_B):
    raise RuntimeError("cam length mismatch after merge")
if len(camIdx_ws_M) != (n_ws_A + n_ws_B):
    raise RuntimeError("ws length mismatch after merge")
if len(camTimes_M) != len(wsIdx_cam_M):
    raise RuntimeError("camTimes mismatch after merge")
if len(wsTimes_M) != len(camIdx_ws_M):
    raise RuntimeError("wsTimes mismatch after merge")

# basic monotonic checks (not strictly required but nice)
def monotonic_ok(t):
    t = np.asarray(t, float)
    t = t[np.isfinite(t)]
    return bool(np.all(np.diff(t) >= -1e-9)) if t.size > 2 else True

print(f"[check] camTimes monotonic: {monotonic_ok(camTimes_M)}")
print(f"[check] wsTimes monotonic:  {monotonic_ok(wsTimes_M)}")

# ---- write merged template ----
DST.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(
    str(DST),
    Fs_ws_input=np.float64(Fs),
    sig_wsIdx__idx_cam=wsIdx_cam_M.astype(np.float64, copy=False),
    sig_camIdx__idx_ws=camIdx_ws_M.astype(np.float64, copy=False),
    sig_camTimes__idx_cam=camTimes_M.astype(np.float64, copy=False),
    sig_wsTimes__idx_ws=wsTimes_M.astype(np.float64, copy=False),
    # metadata
    merged_from_A=str(SRC_A),
    merged_from_B=str(SRC_B),
    ws_offset_samples=np.int64(ws_offset),
    cam_offset_frames=np.int64(cam_offset),
)

print(f"[save] {DST}")
