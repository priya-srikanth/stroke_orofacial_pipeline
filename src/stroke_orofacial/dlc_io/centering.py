"""Center DLC coordinates on a reference landmark.

Ported from cell 8 of canonical notebook
``20260323_DLC_build-parquet_reward-aligned_tongue_jaw.ipynb``.

Three centering modes:
  - **nose**: median of nose (x, y) from high-likelihood frames.
  - **spout_midpoint**: midpoint of median L_spout and median R_spout.
  - **eye_midpoint**: midpoint of median L_eye and median R_eye.

The likelihood threshold is used ONLY to compute the center point, NOT to
drop or overwrite any rows. All frames are kept in the output.
"""

from __future__ import annotations

import enum

import numpy as np
import pandas as pd


class CenterMode(enum.Enum):
    """Centering reference landmark."""

    NOSE = "nose"
    SPOUT_MIDPOINT = "spout_midpoint"
    EYE_MIDPOINT = "eye_midpoint"


def _median_from_lik(
    df: pd.DataFrame,
    xcol: str,
    ycol: str,
    likcol: str | None,
    thr: float,
) -> tuple[float, float]:
    """Median (x, y) using only rows with likelihood >= thr.

    If likcol is None or not in df, uses all finite rows.
    """
    if likcol is not None and likcol in df:
        sub = df[df[likcol] >= thr][[xcol, ycol]].dropna()
    else:
        sub = df[[xcol, ycol]].dropna()
    if sub.empty:
        return np.nan, np.nan
    return float(sub[xcol].median()), float(sub[ycol].median())


def compute_center(
    df: pd.DataFrame,
    mode: CenterMode | str,
    likelihood_threshold: float = 0.7,
) -> tuple[float, float, str]:
    """Compute the centering reference point for a DLC DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Raw (un-centered) DLC DataFrame with ``{bodypart}_{coord}`` columns.
    mode : CenterMode or str
        Which landmark(s) to center on.
    likelihood_threshold : float
        Minimum likelihood for frames used to compute the center.
        Does NOT drop rows from the output.

    Returns
    -------
    tuple[float, float, str]
        (center_x, center_y, mode_used_str)

    Raises
    ------
    RuntimeError
        If insufficient high-likelihood points to compute the center.
    ValueError
        If mode is not recognized.
    """
    if isinstance(mode, str):
        mode = CenterMode(mode)

    thr = likelihood_threshold

    if mode == CenterMode.NOSE:
        nx, ny = _median_from_lik(df, "nose_x", "nose_y", "nose_likelihood", thr)
        if not (np.isfinite(nx) and np.isfinite(ny)):
            raise RuntimeError(
                f"Cannot compute nose center: insufficient valid nose points "
                f"at likelihood_threshold={thr}."
            )
        return nx, ny, "nose"

    if mode == CenterMode.SPOUT_MIDPOINT:
        lx, ly = _median_from_lik(df, "L_spout_x", "L_spout_y", "L_spout_likelihood", thr)
        rx, ry = _median_from_lik(df, "R_spout_x", "R_spout_y", "R_spout_likelihood", thr)
        if not (np.isfinite(lx) and np.isfinite(ly) and np.isfinite(rx) and np.isfinite(ry)):
            raise RuntimeError(
                f"Cannot compute spout_midpoint: insufficient valid L/R spout "
                f"points at likelihood_threshold={thr}."
            )
        return 0.5 * (lx + rx), 0.5 * (ly + ry), "spout_midpoint"

    if mode == CenterMode.EYE_MIDPOINT:
        lx, ly = _median_from_lik(df, "L_eye_x", "L_eye_y", "L_eye_likelihood", thr)
        rx, ry = _median_from_lik(df, "R_eye_x", "R_eye_y", "R_eye_likelihood", thr)
        if not (np.isfinite(lx) and np.isfinite(ly) and np.isfinite(rx) and np.isfinite(ry)):
            raise RuntimeError(
                f"Cannot compute eye_midpoint: insufficient valid L/R eye "
                f"points at likelihood_threshold={thr}."
            )
        return 0.5 * (lx + rx), 0.5 * (ly + ry), "eye_midpoint"

    raise ValueError(f"Unknown center mode: {mode}")


def apply_centering(
    df: pd.DataFrame, cx: float, cy: float
) -> pd.DataFrame:
    """Subtract (cx, cy) from all ``*_x`` and ``*_y`` columns.

    Likelihoods are left untouched. All frames are kept (no rows dropped).

    Parameters
    ----------
    df : pd.DataFrame
        Raw DLC DataFrame.
    cx, cy : float
        Center coordinates to subtract.

    Returns
    -------
    pd.DataFrame
        Centered copy of the input. Same shape, same dtypes.
    """
    out = df.copy()
    for col in out.columns:
        if col.endswith("_x"):
            out[col] = (out[col] - cx).astype(np.float32)
        elif col.endswith("_y"):
            out[col] = (out[col] - cy).astype(np.float32)
    return out
