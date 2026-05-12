"""Vendored from legacy tongue notebook — DO NOT modify in place.

Source notebook: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Notebook SHA256: ed12c54cd4cf348470cbd0fc05ee2fe20548195a52be9832c1164737dabdb643
Cell index: 13
Cell SHA256: b5f07ef61c31f80c101f0006b8901082c36c9221a1fe3daef80522088f29e7dd
Classification: production
Title: DLC parquet (intermediate_data_frames) merge — Architecture X Layer 2

Concatenates two video{cam}_* parquet entries (sorted by acquisition timestamp) into one combined entry; keeps keyA, drops keyB.

This file is a byte-identical vendor of the cell source for audit
reference (Task 1c of Phase 7-pre-multi-half). Re-implementations
in src/stroke_orofacial/spout_behavior/multi_half_merge.py port from
this snippet rather than the live notebook (which may evolve).
"""

# ===================== ORIGINAL CELL SOURCE BELOW =====================

# Merge parquet sessions that were split across multiple video files

import re
import numpy as np
import pandas as pd
from pathlib import Path

# ===== USER SETTINGS =====
TARGET_MOUSE = "PS48"
TARGET_CAM   = "cam2"
TARGET_DATE_ISO = "2025-03-14"   # YYYY-MM-DD
# =========================

if "intermediate_data_frames" not in globals() or not intermediate_data_frames:
    raise RuntimeError("intermediate_data_frames missing/empty. Run your parquet loader first.")

re_video = re.compile(r"^(video(?P<vid>\d))_", re.IGNORECASE)
re_date  = re.compile(r"video\d_(?P<date>\d{4}-\d{2}-\d{2})", re.IGNORECASE)
re_ts    = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<h>\d{2})[-_:]?(?P<m>\d{2})[-_:]?(?P<s>\d{2})", re.IGNORECASE)

def parse_session_from_key(key: str):
    p = Path(str(key))
    base = p.name

    mvid = re_video.search(base)
    mdat = re_date.search(base)
    if (mvid is None) or (mdat is None):
        return None

    vid = int(mvid.group("vid"))
    cam = f"cam{vid}"
    date_iso = mdat.group("date")

    mouse = p.parent.name

    mts = re_ts.search(base)
    ts_tuple = None
    if mts:
        ts_tuple = (mts.group("date"), int(mts.group("h")), int(mts.group("m")), int(mts.group("s")))

    return dict(
        key=str(key),
        mouse=mouse,
        cam=cam,
        date_iso=date_iso,
        basename=base,
        ts_tuple=ts_tuple,
        n_frames=int(len(intermediate_data_frames[key])),
    )

# find candidates
rows = []
for k in intermediate_data_frames.keys():
    d = parse_session_from_key(k)
    if not d:
        continue
    if d["mouse"] == TARGET_MOUSE and d["cam"] == TARGET_CAM and d["date_iso"] == TARGET_DATE_ISO:
        rows.append(d)

if len(rows) < 2:
    raise RuntimeError(f"Expected 2 entries for {TARGET_MOUSE} {TARGET_CAM} {TARGET_DATE_ISO}, found {len(rows)}.\n"
                       f"Matches:\n{pd.DataFrame(rows).to_string(index=False) if rows else '(none)'}")

df = pd.DataFrame(rows).copy()
# sort by timestamp in filename if present; else by basename
df["sort_key"] = df["ts_tuple"].apply(lambda x: x if x is not None else ("9999-99-99", 99, 99, 99))
df = df.sort_values(["sort_key", "basename"]).reset_index(drop=True)

print("[merge parquet] order:")
print(df[["basename","n_frames","key"]].to_string(index=False))

keyA = df.loc[0, "key"]
keyB = df.loc[1, "key"]

A = intermediate_data_frames[keyA]
B = intermediate_data_frames[keyB]

# sanity: same columns
if list(A.columns) != list(B.columns):
    raise ValueError(f"Column mismatch:\nA cols={list(A.columns)}\nB cols={list(B.columns)}")

M = pd.concat([A, B], axis=0, ignore_index=True)

# write back: keep keyA as the merged session, delete keyB
intermediate_data_frames[keyA] = M
del intermediate_data_frames[keyB]

print(f"[ok] merged intermediate_data_frames:\n  kept: {Path(keyA).name} (now n_frames={len(M)})\n  removed: {Path(keyB).name}")
