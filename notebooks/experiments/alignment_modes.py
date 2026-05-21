"""Q64 (Addendum #54): test-only port of the 4 alignment regimes from
``notebooks/experiments/cross_session_alignment_sweep.ipynb`` (cells
4-7). Math is verbatim:

  - eye_affine: 2-point similarity fit (translation + rotation +
    uniform scale) of (L_eye, R_eye) to the per-animal reference.
  - eye_rigid: 2-point overdetermined rigid fit (rotation +
    translation; no scale).
  - eye_centered: translation only — eye-midpoint to reference.
  - spout_centered: translation only — spout-midpoint to reference.

Test-only scratch module. Production ``dlc_io/centering.py`` stays at
eye_midpoint + spout_midpoint translation per Phase 4.5-lite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EYE_LIKELIHOOD_THRESHOLD: float = 0.9
SPOUT_LIKELIHOOD_THRESHOLD: float = 0.7
BODYPART_LIKELIHOOD_THRESHOLD: float = 0.7


def gated_xy(
    df: pd.DataFrame, bodypart: str, threshold: float,
) -> np.ndarray:
    """(N, 2) array of (x, y) for frames with likelihood >= threshold +
    finite coords. Matches the sweep notebook's ``gated_xy`` verbatim.
    """
    x = df[f"{bodypart}_x"].to_numpy(dtype=np.float64)
    y = df[f"{bodypart}_y"].to_numpy(dtype=np.float64)
    lik = df[f"{bodypart}_likelihood"].to_numpy(dtype=np.float64)
    mask = (lik >= threshold) & np.isfinite(x) & np.isfinite(y)
    return np.column_stack([x[mask], y[mask]])


def median_xy(
    df: pd.DataFrame, bodypart: str, threshold: float,
) -> np.ndarray | None:
    pts = gated_xy(df, bodypart, threshold)
    if len(pts) == 0:
        return None
    return np.median(pts, axis=0)


def median_midpoint(
    df: pd.DataFrame, left_bp: str, right_bp: str, threshold: float,
) -> np.ndarray | None:
    lx = df[f"{left_bp}_x"].to_numpy(dtype=np.float64)
    ly = df[f"{left_bp}_y"].to_numpy(dtype=np.float64)
    rx = df[f"{right_bp}_x"].to_numpy(dtype=np.float64)
    ry = df[f"{right_bp}_y"].to_numpy(dtype=np.float64)
    llik = df[f"{left_bp}_likelihood"].to_numpy(dtype=np.float64)
    rlik = df[f"{right_bp}_likelihood"].to_numpy(dtype=np.float64)
    mask = (
        (llik >= threshold) & (rlik >= threshold)
        & np.isfinite(lx) & np.isfinite(ly)
        & np.isfinite(rx) & np.isfinite(ry)
    )
    if not mask.any():
        return None
    mx = 0.5 * (lx[mask] + rx[mask])
    my = 0.5 * (ly[mask] + ry[mask])
    return np.array([float(np.median(mx)), float(np.median(my))])


def fit_similarity_2pt(
    src_pts: np.ndarray, dst_pts: np.ndarray,
) -> dict:
    """eye_affine — 2-point exact similarity fit via complex arithmetic.
    Verbatim port of sweep cell 5."""
    s = src_pts[:, 0] + 1j * src_pts[:, 1]
    d = dst_pts[:, 0] + 1j * dst_pts[:, 1]
    a = (d[0] - d[1]) / (s[0] - s[1])
    b = d[0] - a * s[0]
    scale = float(np.abs(a))
    theta_rad = float(np.angle(a))
    tx, ty = float(b.real), float(b.imag)
    c, sn = np.cos(theta_rad), np.sin(theta_rad)
    M = np.array(
        [[scale * c, -scale * sn, tx], [scale * sn, scale * c, ty]],
    )
    return {"scale": scale, "theta_rad": theta_rad, "tx": tx, "ty": ty, "M": M}


def fit_rigid_2pt(
    src_pts: np.ndarray, dst_pts: np.ndarray,
) -> dict:
    """eye_rigid — 2-point overdetermined rigid fit. Verbatim port of
    sweep cell 5."""
    src_mid = src_pts.mean(axis=0)
    dst_mid = dst_pts.mean(axis=0)
    src_dir = src_pts[1] - src_pts[0]
    dst_dir = dst_pts[1] - dst_pts[0]
    theta_rad = float(
        np.arctan2(dst_dir[1], dst_dir[0])
        - np.arctan2(src_dir[1], src_dir[0])
    )
    c, sn = np.cos(theta_rad), np.sin(theta_rad)
    R = np.array([[c, -sn], [sn, c]])
    t = dst_mid - R @ src_mid
    M = np.array(
        [[c, -sn, float(t[0])], [sn, c, float(t[1])]],
    )
    return {"scale": 1.0, "theta_rad": theta_rad,
            "tx": float(t[0]), "ty": float(t[1]), "M": M}


def apply_affine(pts: np.ndarray, M: np.ndarray) -> np.ndarray:
    pts_h = np.column_stack([pts, np.ones(len(pts))])
    return (M @ pts_h.T).T


def translate(pts: np.ndarray, shift: np.ndarray) -> np.ndarray:
    return pts + shift


def per_session_fiducials(df: pd.DataFrame) -> dict | None:
    """L_eye / R_eye medians + spout midpoint for one session. None if
    eyes not detectable."""
    L = median_xy(df, "L_eye", EYE_LIKELIHOOD_THRESHOLD)
    R = median_xy(df, "R_eye", EYE_LIKELIHOOD_THRESHOLD)
    if L is None or R is None:
        return None
    eye_mid = (L + R) / 2
    spout_mid = median_midpoint(
        df, "L_spout", "R_spout", SPOUT_LIKELIHOOD_THRESHOLD,
    )
    return {"L_eye": L, "R_eye": R, "eye_mid": eye_mid, "spout_mid": spout_mid}


def build_reference_from_sessions(
    pre_stroke_dfs: list[pd.DataFrame],
) -> dict | None:
    """Mean-of-baseline reference per the sweep cell 6 default."""
    Ls, Rs, eye_mids, spout_mids = [], [], [], []
    for df in pre_stroke_dfs:
        L = median_xy(df, "L_eye", EYE_LIKELIHOOD_THRESHOLD)
        R = median_xy(df, "R_eye", EYE_LIKELIHOOD_THRESHOLD)
        if L is None or R is None:
            continue
        Ls.append(L)
        Rs.append(R)
        eye_mids.append((L + R) / 2)
        sp = median_midpoint(
            df, "L_spout", "R_spout", SPOUT_LIKELIHOOD_THRESHOLD,
        )
        if sp is not None:
            spout_mids.append(sp)
    if not Ls:
        return None
    return {
        "L_eye_ref": np.mean(Ls, axis=0),
        "R_eye_ref": np.mean(Rs, axis=0),
        "eye_mid_ref": np.mean(eye_mids, axis=0),
        "spout_mid_ref": (
            np.mean(spout_mids, axis=0) if spout_mids else None
        ),
        "n_sessions_used": len(Ls),
    }


def compute_session_transforms(
    session_fid: dict, reference: dict,
) -> dict[str, dict | None]:
    """Build the 4 transforms for one session. ``spout_centered`` is
    None when spout fiducials are missing."""
    src = np.array([session_fid["L_eye"], session_fid["R_eye"]])
    dst = np.array([reference["L_eye_ref"], reference["R_eye_ref"]])
    transforms: dict[str, dict | None] = {}
    transforms["eye_affine"] = {"params": fit_similarity_2pt(src, dst)}
    transforms["eye_rigid"] = {"params": fit_rigid_2pt(src, dst)}
    shift_eye = reference["eye_mid_ref"] - session_fid["eye_mid"]
    transforms["eye_centered"] = {"params": {"shift": shift_eye}}
    if (
        session_fid["spout_mid"] is not None
        and reference.get("spout_mid_ref") is not None
    ):
        shift_spout = reference["spout_mid_ref"] - session_fid["spout_mid"]
        transforms["spout_centered"] = {"params": {"shift": shift_spout}}
    else:
        transforms["spout_centered"] = None
    return transforms


def apply_transform_to_pts(
    pts: np.ndarray, regime: str, transform_entry: dict | None,
) -> np.ndarray | None:
    """Apply one regime's transform to (N, 2) points. Returns None if
    the entry is None (e.g., spout_centered when spouts missing)."""
    if transform_entry is None:
        return None
    params = transform_entry["params"]
    if regime in ("eye_affine", "eye_rigid"):
        return apply_affine(pts, params["M"])
    if regime in ("eye_centered", "spout_centered"):
        return translate(pts, params["shift"])
    raise ValueError(f"unknown regime: {regime}")


REGIME_ORDER = ["eye_affine", "eye_rigid", "eye_centered", "spout_centered"]
REGIME_COLORS = {
    "eye_affine": "tab:blue",
    "eye_rigid": "tab:purple",
    "eye_centered": "tab:orange",
    "spout_centered": "tab:green",
}
