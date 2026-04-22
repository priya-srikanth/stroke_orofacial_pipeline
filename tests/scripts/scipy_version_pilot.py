"""Phase 7a.0 pilot: compare PCHIP interpolation output under scipy 1.15.1
vs 1.17.1 on one real session's tongue trace.

Input: one legacy interp NPZ at
    {MICROSCOPE}/Priya/DeepLabCut/O2_analysis/PS46/PS46_tongue_kinematics/processed_interpolated_data/centered_spout_midpoint/PS46_20250307_cam2_tongue_interp_v5p3.npz

Output: stdout summary (captured by the runner into docs/phase-7/scipy-pilot-results.md).

Approach: load the `drop`-stage arrays (post-likelihood-drop, pre-PCHIP)
from the legacy NPZ, re-run PCHIP on the non-NaN points to fill NaN
indices, compare the resulting `interp`-stage output elementwise
across two scipy versions. Runs under whichever scipy is currently
active — the runner invokes it twice, once per env.

Emits a JSON payload to stdout of the form
    {"scipy_version": "x.y.z", "x_interp": [...], "y_interp": [...]}
so the runner can diff the two JSON payloads offline without having
both scipy versions loaded in one process.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.interpolate import PchipInterpolator


def pchip_fill(x_stage_drop: np.ndarray) -> np.ndarray:
    """PCHIP-fill NaN gaps in a 1D array using non-NaN indices as anchors.

    Matches the legacy interpolation.py `_stage_interp` behavior: fit
    PCHIP on (idx_nonan, val_nonan), evaluate at idx_nan. Linear fallback
    if PCHIP raises.
    """
    n = x_stage_drop.size
    idx = np.arange(n)
    mask_nan = np.isnan(x_stage_drop)
    if not mask_nan.any():
        return x_stage_drop.copy()
    if (~mask_nan).sum() < 2:
        return x_stage_drop.copy()
    xp = idx[~mask_nan]
    fp = x_stage_drop[~mask_nan]
    try:
        interp = PchipInterpolator(xp, fp, extrapolate=False)
        filled = interp(idx)
    except Exception:
        filled = np.interp(idx, xp, fp, left=np.nan, right=np.nan)
    out = x_stage_drop.copy()
    out[mask_nan] = filled[mask_nan]
    return out


def main(npz_path: Path) -> None:
    data = np.load(npz_path, allow_pickle=True)
    keys_available = list(data.files)
    if "x_drop" not in keys_available or "y_drop" not in keys_available:
        print(
            f"FATAL: expected keys x_drop, y_drop not in NPZ. "
            f"Available: {keys_available}",
            file=sys.stderr,
        )
        sys.exit(2)

    x_drop = data["x_drop"].astype(float)
    y_drop = data["y_drop"].astype(float)

    x_interp = pchip_fill(x_drop)
    y_interp = pchip_fill(y_drop)

    payload = {
        "scipy_version": scipy.__version__,
        "npz": str(npz_path),
        "n_frames": int(x_drop.size),
        "n_nan_input_x": int(np.isnan(x_drop).sum()),
        "n_nan_input_y": int(np.isnan(y_drop).sum()),
        "n_nan_output_x": int(np.isnan(x_interp).sum()),
        "n_nan_output_y": int(np.isnan(y_interp).sum()),
        "x_interp": x_interp.tolist(),
        "y_interp": y_interp.tolist(),
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "usage: scipy_version_pilot.py <path-to-legacy-interp-npz>",
            file=sys.stderr,
        )
        sys.exit(1)
    main(Path(sys.argv[1]))
