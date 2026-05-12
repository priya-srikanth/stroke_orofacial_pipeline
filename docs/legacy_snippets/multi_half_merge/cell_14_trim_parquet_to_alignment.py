"""Vendored from legacy tongue notebook — DO NOT modify in place.

Source notebook: 20260203_DLC_analysis_ws_aligned_parquet_input_tongue.ipynb
Notebook SHA256: ed12c54cd4cf348470cbd0fc05ee2fe20548195a52be9832c1164737dabdb643
Cell index: 14
Cell SHA256: 4deb0d3abeae632ea7cabd5bae703a6e6e4b9416977b86863ffd66308cc80cc0
Classification: out_of_scope
Title: Trim parquet to alignment-template length — DIFFERENT PROBLEM

Operates on PS48 20250317 / PS55 20250502; not multi-half merge. Tracked as forward-pointer Phase 7-pre-length-trim.

This file is a byte-identical vendor of the cell source for audit
reference (Task 1c of Phase 7-pre-multi-half). Re-implementations
in src/stroke_orofacial/spout_behavior/multi_half_merge.py port from
this snippet rather than the live notebook (which may evolve).
"""

# ===================== ORIGINAL CELL SOURCE BELOW =====================

# If misaligned, trim parquet based on alignment template

# ===== Trim DLC dataframe to alignment-template length =====
import numpy as np
from pathlib import Path

# KEY = r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS48\video2_2025-03-17T11_30_25DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"  # <-- your exact key
# TEMPLATE = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250317.npz")

KEY = r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\PS55\video2_2025-05-02T12_36_36DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"  # <-- your exact key
TEMPLATE = Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut\O2_analysis\alignment_templates\cam2\PS55\20250502.npz")

aln = np.load(TEMPLATE, allow_pickle=False)
n_template = len(aln["sig_wsIdx__idx_cam"])

df = intermediate_data_frames[KEY]
n_df = len(df)

if n_df <= n_template:
    print(f"[ok] df length {n_df:,} <= template {n_template:,}; nothing to trim.")
else:
    intermediate_data_frames[KEY] = df.iloc[:n_template].reset_index(drop=True)
    print(f"[trim] {n_df:,} -> {n_template:,} (dropped {n_df - n_template:,} frames)")
