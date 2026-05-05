"""Vendored from legacy tongue notebook — DO NOT modify in place.

Source notebook: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Notebook SHA256: ed12c54cd4cf348470cbd0fc05ee2fe20548195a52be9832c1164737dabdb643
Cell index: 15
Cell SHA256: 6adb3d6ef63c9b7ba2800a78eadfa16c819979c3d85b3596343cddaa2df0d932
Classification: out_of_scope
Title: Trim alignment-template to parquet length — DIFFERENT PROBLEM

Sister of cell 14; tracked as forward-pointer Phase 7-pre-length-trim.

This file is a byte-identical vendor of the cell source for audit
reference (Task 1c of Phase 7-pre-multi-half). Re-implementations
in src/stroke_orofacial/spout_behavior/multi_half_merge.py port from
this snippet rather than the live notebook (which may evolve).
"""

# ===================== ORIGINAL CELL SOURCE BELOW =====================

# ===== Trim alignment template to match DLC dataframe length =====
import numpy as np
from pathlib import Path

KEY = r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS55\video2_2025-05-02T12_36_36DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
TEMPLATE = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\alignment_templates\cam2\PS55\20250502.npz")

# Load
aln = np.load(TEMPLATE, allow_pickle=False)
df = intermediate_data_frames[KEY]

n_df = len(df)
n_template = len(aln["sig_wsIdx__idx_cam"])

print(f"df length: {n_df:,}")
print(f"template length: {n_template:,}")

if n_template <= n_df:
    print("[ok] template already <= df; nothing to trim.")
else:
    n_trim = n_template - n_df
    print(f"[trim template] dropping last {n_trim} frame(s)")

    # Keys indexed by camera frames (must match DLC length)
    cam_indexed_keys = [
        "sig_wsIdx__idx_cam",
        "sig_camTimes__idx_cam",
        "sig_camTimesCommon__idx_cam",
    ]

    # Create trimmed copy
    new_data = {}

    for k in aln.files:
        arr = aln[k]

        if k in cam_indexed_keys:
            if len(arr) == n_template:
                new_data[k] = arr[:n_df]
                print(f"  trimmed: {k}")
            else:
                new_data[k] = arr  # unexpected shape, leave unchanged
                print(f"  [warn] unexpected length for {k}: {len(arr)}")
        else:
            new_data[k] = arr  # untouched

    # Save new template (do NOT overwrite original yet)
    out_path = TEMPLATE.with_name(TEMPLATE.stem + "_trimmed.npz")
    np.savez(out_path, **new_data)

    print(f"[save] trimmed template → {out_path}")