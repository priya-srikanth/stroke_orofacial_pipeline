"""BASELINE (false-positive) rate of the jaw-opening detector outside the cue, two-tone cohort (overnight check,
coordinator 2026-11-20). Review output only.

The pipeline's per-trial `jaw_pass_qc` (stroke_orofacial.dlc_kinematics.jaw_pertrial._compute_per_trial, imported
UNCHANGED, configs/defaults.yaml dlc_kinematics.jaw_pertrial: baseline -500..0 ms, detect 0..5000 ms, threshold
max(4 SD, 4 px), >= 5 of 8 consecutive frames over threshold; cleaned_traces/jaw y_final) is applied twice per trial:
  * cue     anchor = the cue frame (candidate_trials tone_frame_idx) -> reproduces the stored jaw_pass_qc (validation);
  * sham    anchor = cue - 8 s (baseline -8.5..-8 s, detect -8..-3 s before the cue): no cue inside (kept only if
            the previous cue is >= 16 s before the cue, i.e. the sham window starts >= 8 s after the previous cue, the
            end of its response window) and NO spout lick (DAQ, either spout) from anchor - 0.5 s to anchor + 5 s.
Sham rate = the detector's rate with no cue and no lick (chance level for "jaw opened" on no-lick trials).
Compared with the cue-anchored rate on (a) no-lick trials (no spout lick 70 ms - 8 s) and (b) responded trials.

Writes data/jaw_baseline_trials.parquet, tables_whole/jaw_baseline_by_session.csv, jaw_baseline_by_grade_epoch.csv,
jaw_baseline_summary.csv. Refuses to overwrite. Usage: python c1_jaw_baseline.py <c1_dir> [--jobs 8] [--only LABEL]
"""
from __future__ import annotations

import argparse
import datetime
import sys
from multiprocessing import Pool
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

OUT = 'M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs'
SHAM_S = 8.0
MIN_PREV_CUE_S = 16.0


def process(item):
    label, cues = item
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.dlc_kinematics import jaw_pertrial as JP
    from stroke_orofacial.paths import PathResolver
    an, d = label.split('_')
    cf = Path(OUT) / 'dlc_kinematics/tongue_jaw_mismatch/candidate_trials' / an / f'{d}.parquet'
    if not cf.exists():
        return None
    C = pd.read_parquet(cf, columns=['trial_index', 'tone_frame_idx', 'fps', 'jaw_pass_qc'])
    r = PathResolver()
    jp = load_defaults()['dlc_kinematics']['jaw_pertrial']
    p = r.cleaned_trace(bodypart='jaw', animal=an, date=datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])))
    if not Path(p).exists():
        return None
    y = pd.read_parquet(p, columns=['y_final']).y_final.to_numpy(float)
    L = np.load(Path(OUT) / 'spout_behavior/licks_and_rewards' / an / f'{d}.npz')
    fs = float(L['Fs'])
    licks = np.sort(np.r_[L['Lick_L'], L['Lick_R']]) / fs
    kw = dict(detect_win_ms=tuple(jp['detect_win_ms']), baseline_win_ms=tuple(jp['baseline_win_ms']),
              sd_mult=float(jp['deflection_threshold_sd_multiplier']), min_px=float(jp['deflection_threshold_min_px']),
              density_thr=float(jp['sustained_density_threshold']), window_n=int(jp['sustained_window_n_frames']))
    cues = np.asarray(cues, float)
    rows = []
    for _, c in C.iterrows():
        t = int(c.trial_index)
        if t >= len(cues):
            continue
        fps = float(c.fps)
        cue_s = cues[t]
        real = JP._compute_per_trial(SimpleNamespace(trial_index=t, side='', tone_frame_idx=int(c.tone_frame_idx)),
                                     y, fps, len(y), **kw)['jaw_pass_qc']
        a_s = cue_s - SHAM_S
        prev_ok = (t == 0 and cue_s > MIN_PREV_CUE_S) or (t > 0 and cue_s - cues[t - 1] >= MIN_PREV_CUE_S)
        lick_free = not np.any((licks >= a_s - 0.5) & (licks <= a_s + 5.0))
        sham = np.nan
        if prev_ok and lick_free:
            sf = int(c.tone_frame_idx) - int(round(SHAM_S * fps))
            if sf > int(round(0.5 * fps)):
                sham = float(JP._compute_per_trial(SimpleNamespace(trial_index=t, side='', tone_frame_idx=sf),
                                                   y, fps, len(y), **kw)['jaw_pass_qc'])
        rows.append({'label': label, 'trial': t, 'cue_qc_recomputed': float(real), 'cue_qc_stored': float(c.jaw_pass_qc),
                     'sham_qc': sham, 'sham_eligible': bool(prev_ok and lick_free)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    outs = [a.c1 / 'data/jaw_baseline_trials.parquet'] + [a.c1 / 'tables_whole' / f'jaw_baseline_{k}.csv'
                                                         for k in ('by_session', 'by_grade_epoch', 'summary')]
    if not a.only and any(p.exists() for p in outs):
        sys.exit('refusing to overwrite: ' + ', '.join(str(p) for p in outs if p.exists()))
    T = pd.read_parquet(a.c1 / 'data/trials.parquet', columns=['label', 'animal', 'grade', 'epoch', 'trial', 'cue_s',
                                                              'responded'])
    items = [(l, g.sort_values('trial').cue_s.to_numpy()) for l, g in T.groupby('label') if a.only in (None, l)]
    if a.jobs > 1 and len(items) > 1:
        with Pool(a.jobs) as p:
            res = p.map(process, items, chunksize=1)
    else:
        res = [process(i) for i in items]
    B = pd.concat([r for r in res if r is not None], ignore_index=True).merge(T, on=['label', 'trial'])
    print('sessions', B.label.nunique(), 'trials', len(B), 'recomputed == stored:',
          float((B.cue_qc_recomputed == B.cue_qc_stored).mean()))
    B['post'] = np.where(B.epoch == 'pre', 'pre', 'post')

    def summ(g):
        return pd.Series({'sham_rate': g.sham_qc.mean(), 'n_sham': int(g.sham_qc.notna().sum()),
                          'cue_rate_nolick': g.loc[~g.responded, 'cue_qc_stored'].mean(),
                          'n_nolick': int((~g.responded).sum()),
                          'cue_rate_responded': g.loc[g.responded, 'cue_qc_stored'].mean(),
                          'n_responded': int(g.responded.sum())})
    S = B.groupby(['label', 'animal', 'grade', 'epoch']).apply(summ, include_groups=False).reset_index()
    G = B.groupby(['grade', 'epoch']).apply(summ, include_groups=False).reset_index()
    A = pd.concat([B.groupby('post').apply(summ, include_groups=False).reset_index().rename(columns={'post': 'set'}),
                   summ(B).to_frame().T.assign(set='all')], ignore_index=True)
    if a.only:
        print(S.round(3).to_string()); return
    B.to_parquet(outs[0]); S.to_csv(outs[1], index=False); G.round(4).to_csv(outs[2], index=False)
    A.round(4).to_csv(outs[3], index=False)
    print(G.round(3).to_string(index=False)); print(A.round(3).to_string(index=False))


if __name__ == '__main__':
    main()
