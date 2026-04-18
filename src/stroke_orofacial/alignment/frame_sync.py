"""Frame synchronization: align wavesurfer samples to camera frames.

Faithfully ported from legacy ``make_alignment_templates_20251216.py``
(Rich's upstream repo, only version, Rule 1 trivially resolved).

The algorithm:
  1. Detect rising edges in both sync signals (robust min-max normalize,
     threshold at 0.5).
  2. Normalize edge times to [0,1] for pattern matching.
  3. Match edge sequences via sliding-window L-p norm on inter-edge intervals.
  4. Fit affine mappings via np.polyfit on matched edges.
  5. Interpolate full sample-by-sample mappings via scipy.interpolate.interp1d.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import scipy.interpolate


def _normalize_minmax_robust(
    x: np.ndarray, p_lo: float = 5, p_hi: float = 95
) -> np.ndarray:
    """Robust min-max normalization using percentiles."""
    x = np.asarray(x, dtype=np.float64)
    lo = np.nanpercentile(x, p_lo)
    hi = np.nanpercentile(x, p_hi)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = np.nanmin(x)
        hi = np.nanmax(x)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(x, dtype=np.float64)
    return (x - lo) / (hi - lo)


def _find_rising_edges(arr: np.ndarray, thr: float = 0.5) -> np.ndarray:
    """Return indices of rising edges in a robust-normalized analog signal."""
    a = _normalize_minmax_robust(arr)
    above = a > thr
    rising = np.flatnonzero((~above[:-1]) & (above[1:])) + 1
    return rising.astype(np.int64)


def _align_edge_sequences(
    s1: np.ndarray,
    s2: np.ndarray,
    window: int = 20,
    p: float = 0.1,
) -> dict[int, int]:
    """Match two monotonic edge-time sequences via local pattern matching.

    Uses sliding-window L-p norm on inter-edge intervals, then prunes
    to a strictly monotonic mapping.

    Returns dict mapping s1 edge index -> s2 edge index.
    """
    s1 = np.asarray(s1, dtype=np.float64)
    s2 = np.asarray(s2, dtype=np.float64)
    if s1.size < (window * 4 + 5) or s2.size < (window * 4 + 5):
        raise ValueError(
            f"Not enough edges for alignment with window={window}: "
            f"s1={s1.size}, s2={s2.size}"
        )

    ds1 = np.diff(s1)
    ds2 = np.diff(s2)
    shift_vals = np.arange(-window, window + 1, dtype=np.int64)

    matches: dict[int, int] = {}
    start = window * 2
    stop = min(len(ds1), len(ds2)) - window * 2 - 1

    for ii in range(start, stop):
        # Forward window comparison
        v1_f = ds1[ii : ii + window]
        v2s_f = np.stack(
            [ds2[ii + jj : ii + jj + window] for jj in shift_vals], axis=0
        )
        dr = np.nanmean(np.abs(v1_f[None, :] - v2s_f) ** p, axis=1) ** (1 / p)

        # Backward window comparison
        v1_b = ds1[ii - window : ii]
        v2s_b = np.stack(
            [ds2[ii + jj - window : ii + jj] for jj in shift_vals], axis=0
        )
        dl = np.nanmean(np.abs(v1_b[None, :] - v2s_b) ** p, axis=1) ** (1 / p)

        # Pick best match direction
        use_forward = np.nanmin(dr) <= np.nanmin(dl)
        j_best = int(np.nanargmin(dr)) if use_forward else int(np.nanargmin(dl))

        shift = int(shift_vals[j_best])
        jj = ii + shift
        if 0 <= jj < len(s2):
            matches[int(ii)] = int(jj)

    # Prune to strictly monotonic (greedy)
    keys = np.array(sorted(matches.keys()), dtype=np.int64)
    vals = np.array([matches[k] for k in keys], dtype=np.int64)

    keep_k: list[int] = []
    keep_v: list[int] = []
    last_v = -1
    for k, v in zip(keys, vals):
        if v > last_v:
            keep_k.append(int(k))
            keep_v.append(int(v))
            last_v = v

    return dict(zip(keep_k, keep_v))


def _safe_interp1d(
    x: np.ndarray, y: np.ndarray, xq: np.ndarray
) -> np.ndarray:
    """Interpolate y(x) at xq, guarding against non-finite/non-monotonic x."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xq = np.asarray(xq, dtype=np.float64)

    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 2:
        return np.full_like(xq, np.nan, dtype=np.float64)

    order = np.argsort(x)
    x, y = x[order], y[order]
    uniq = np.concatenate([[True], np.diff(x) > 0])
    x, y = x[uniq], y[uniq]
    if x.size < 2:
        return np.full_like(xq, np.nan, dtype=np.float64)

    f = scipy.interpolate.interp1d(
        x=x, y=y, kind="linear", bounds_error=False,
        fill_value=np.nan, assume_sorted=True,
    )
    return f(xq)


def make_alignment_template(
    ws_signals: dict[str, np.ndarray],
    cam_csv: pd.DataFrame,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Align camera and wavesurfer signals using sync signal.

    Faithfully ports ``make_alignment_templates_20251216.make_alignment_templates``.

    Parameters
    ----------
    ws_signals : dict
        Wavesurfer signals dict (from ``load_wavesurfer_signals`` or NPZ).
        Must contain the sync channel (default ``Sync_signal``) and
        ``sample_rate_input`` or ``Fs``.
    cam_csv : pd.DataFrame
        Camera timestamp CSV (no header). Columns indexed by position.
    params : dict
        The ``alignment`` section from defaults.yaml. Required keys:
        ``csv_idx_sync``, ``csv_idx_time``, ``key_sync``, ``fps_cam``,
        ``window``, ``p``, ``min_matched_edges``.

    Returns
    -------
    dict[str, Any]
        The 22-key alignment template result dict (same schema as legacy NPZ).
    """
    key_sync = str(params["key_sync"])
    csv_idx_sync = int(params["csv_idx_sync"])
    csv_idx_time = int(params["csv_idx_time"])
    window = int(params["window"])
    p_val = float(params["p"])
    fps_cam = float(params["fps_cam"]) if params.get("fps_cam") else None
    min_matched = int(params.get("min_matched_edges", 5))

    # Infer Fs
    Fs_ws_input = float(ws_signals.get("Fs", ws_signals.get("sample_rate_input", 1000.0)))

    # Extract sync signals
    if key_sync not in ws_signals:
        raise KeyError(
            f"WS signals missing key_sync='{key_sync}'. "
            f"Available keys: {list(ws_signals.keys())}"
        )
    wsSyncSignal = np.asarray(ws_signals[key_sync], dtype=np.float64)
    N_ws = int(wsSyncSignal.size)
    if N_ws < 10:
        raise ValueError(f"WS sync signal too short: N_ws={N_ws}")

    cam_arr = cam_csv.to_numpy()
    if cam_arr.ndim != 2 or cam_arr.shape[0] < 10:
        raise ValueError(f"camCSV is too small or not 2D: shape={cam_arr.shape}")

    camSyncSignal = cam_arr[:, csv_idx_sync].astype(np.float64)
    camTime = cam_arr[:, csv_idx_time].astype(np.float64)
    N_cam = int(camSyncSignal.size)

    # WS time in seconds from sample index
    wsTime = np.arange(N_ws, dtype=np.float64) / Fs_ws_input

    # Find rising edges
    thr = float(params.get("edge_threshold", 0.5))
    idxCam_edges = _find_rising_edges(camSyncSignal, thr=thr)
    idxWS_edges = _find_rising_edges(wsSyncSignal, thr=thr)

    if idxCam_edges.size < 2 or idxWS_edges.size < 2:
        raise ValueError(
            f"Not enough rising edges: cam={idxCam_edges.size}, ws={idxWS_edges.size}"
        )

    # Edge times in native time bases
    camEdge_t = camTime[idxCam_edges]
    wsEdge_t = wsTime[idxWS_edges]

    # Normalize to [0,1] for pattern matching
    def norm_to_01(t: np.ndarray, fl: np.ndarray) -> np.ndarray:
        denom = fl[1] - fl[0]
        if not np.isfinite(denom) or denom == 0:
            return np.zeros_like(t, dtype=np.float64)
        return (t - fl[0]) / denom

    cam_fl = np.array([camEdge_t[0], camEdge_t[-1]], dtype=np.float64)
    ws_fl = np.array([wsEdge_t[0], wsEdge_t[-1]], dtype=np.float64)
    camEdge_tN = norm_to_01(camEdge_t, cam_fl)
    wsEdge_tN = norm_to_01(wsEdge_t, ws_fl)

    # Match edge sequences
    matches = _align_edge_sequences(camEdge_tN, wsEdge_tN, window=window, p=p_val)
    if len(matches) < min_matched:
        raise ValueError(
            f"Too few matched edges ({len(matches)}). Alignment unreliable."
        )

    cam_edge_i = np.array(sorted(matches.keys()), dtype=np.int64)
    ws_edge_i = np.array([matches[k] for k in cam_edge_i], dtype=np.int64)

    cam_edge_idx = idxCam_edges[cam_edge_i].astype(np.float64)
    ws_edge_idx = idxWS_edges[ws_edge_i].astype(np.float64)

    # FIT 1: index affine mapping
    a_idx, b_idx = np.polyfit(cam_edge_idx, ws_edge_idx, deg=1)

    # FIT 2: time affine mapping
    cam_edge_time = camTime[idxCam_edges[cam_edge_i]]
    ws_edge_time = wsTime[idxWS_edges[ws_edge_i]]
    a_t, b_t = np.polyfit(cam_edge_time, ws_edge_time, deg=1)

    # Common time representations
    camTime_common = a_t * camTime + b_t
    wsTime_common = wsTime

    # Interpolate full mappings
    sig_camIdx__idx_ws = _safe_interp1d(
        camTime_common, np.arange(N_cam, dtype=np.float64), wsTime_common
    )
    sig_wsIdx__idx_cam = _safe_interp1d(
        wsTime_common, np.arange(N_ws, dtype=np.float64), camTime_common
    )

    result: dict[str, Any] = {
        "Fs_ws_input": Fs_ws_input,
        "slope_ws_per_camFrame": float(a_idx),
        "intercept_ws_samples": float(b_idx),
        "slope_wsTime_per_camTime": float(a_t),
        "intercept_wsTime": float(b_t),
        # Deprecated aliases (kept for backward compat)
        "slope": float(a_idx),
        "intercept": float(b_idx),
        # Edge data
        "idxCam_edges": idxCam_edges.astype(np.int64),
        "idxWS_edges": idxWS_edges.astype(np.int64),
        "camEdge_time": camEdge_t.astype(np.float64),
        "wsEdge_time": wsEdge_t.astype(np.float64),
        "camEdge_time_norm01": camEdge_tN.astype(np.float64),
        "wsEdge_time_norm01": wsEdge_tN.astype(np.float64),
        "matched_camEdge_i": cam_edge_i.astype(np.int64),
        "matched_wsEdge_i": ws_edge_i.astype(np.int64),
        # Time representations
        "sig_camTimes__idx_cam": camTime.astype(np.float64),
        "sig_wsTimes__idx_ws": wsTime.astype(np.float64),
        "sig_camTimesCommon__idx_cam": camTime_common.astype(np.float64),
        "sig_wsTimesCommon__idx_ws": wsTime_common.astype(np.float64),
        # Core deliverables
        "sig_camIdx__idx_ws": sig_camIdx__idx_ws.astype(np.float64),
        "sig_wsIdx__idx_cam": sig_wsIdx__idx_cam.astype(np.float64),
    }

    if fps_cam is not None and np.isfinite(fps_cam) and fps_cam > 0:
        result["expected_ws_samples_per_camFrame"] = float(Fs_ws_input / fps_cam)

    return result
