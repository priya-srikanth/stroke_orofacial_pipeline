"""Two-tone DLC keypoints on the wavesurfer clock (shared by c1_keypoint_me.py and c1_tim.py).

Sources (read-only, stroke_orofacial_pipeline outputs):
  * tongue, jaw: dlc_analysis/interpolated_traces/<part>/<animal>/<YYYYMMDD>.parquet (x_final, y_final; pipeline
    v5p3 interpolation: tongue in the mouth = baseline fill at the mouth origin, so "no tongue" = 0 movement);
  * nose, whiskers (L/R 1-3), eyes (L/R): dlc_analysis/centered_eye_midpoint/<animal>/video2_<YYYY-MM-DD>T*.parquet
    (raw DLC px, eye-midpoint centred), likelihood < MIN_P -> NaN;
  * clock: dlc_analysis/alignment_templates/cam2/<animal>/<YYYYMMDD>.npz `sig_wsIdx__idx_cam` (camera frame ->
    wavesurfer sample; 250 fps camera, 1 kHz wavesurfer). Frame f is at sig_wsIdx__idx_cam[f] / 1000 s.
Multi-half sessions (PS48 2025-03-14) are not handled here (returns None).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/dlc_analysis')
MIN_P = 0.5
RAW_PARTS = ['nose', 'L_whiskers_1', 'L_whiskers_2', 'L_whiskers_3', 'R_whiskers_1', 'R_whiskers_2', 'R_whiskers_3',
             'L_eye', 'R_eye']


def load_session(animal: str, date: str):
    """(t_s [n_frames], {part: (x, y)}) or None. Tongue / jaw from the interpolated traces; the others raw."""
    tf = ROOT / 'alignment_templates/cam2' / animal / f'{date}.npz'
    if not tf.exists():
        return None
    t = np.load(tf)['sig_wsIdx__idx_cam'].astype(float) / 1000.0
    iso = f'{date[:4]}-{date[4:6]}-{date[6:]}'
    raw = sorted((ROOT / 'centered_eye_midpoint' / animal).glob(f'video2_{iso}T*.parquet'))
    if len(raw) != 1:
        return None
    R = pd.read_parquet(raw[0], columns=[f'{p}_{c}' for p in RAW_PARTS for c in ('x', 'y', 'likelihood')])
    parts = {}
    for p in ('tongue', 'jaw'):
        f = ROOT / 'interpolated_traces' / p / animal / f'{date}.parquet'
        if not f.exists():
            return None
        D = pd.read_parquet(f, columns=['x_final', 'y_final'])
        parts[p] = (D.x_final.to_numpy(float), D.y_final.to_numpy(float))
    for p in RAW_PARTS:
        ok = R[f'{p}_likelihood'].to_numpy(float) >= MIN_P
        parts[p] = (np.where(ok, R[f'{p}_x'].to_numpy(float), np.nan), np.where(ok, R[f'{p}_y'].to_numpy(float), np.nan))
    n = min(len(t), *(len(v[0]) for v in parts.values()))
    return t[:n], {k: (x[:n], y[:n]) for k, (x, y) in parts.items()}
