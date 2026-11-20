"""Two-tone cohort, treadmill + running TIME-MATCHED to the 60-min recording (Priya 2026-11-20: "two tone should be 60 min
time-matched (beginning to end of sync pulse)"). Replaces, for the treadmill / running figure, the earlier two-tone
choices ("whole" = first cue -> last cue + 8 s; "matched" = first cue + 50.5 min).

Window per session = first to last edge of wavesurfer `Sync_signal` (spout_behavior/wavesurfer_signals_processed),
capped at 60 min after the first edge (only PS48 2025-03-14, two recordings joined as halves a + b like every other
two-tone table, exceeds it). Every session is then ~60 min (reported in sync_windows.csv).
  * trials: cue inside the window and cue + 3.5 s (end of the response window) <= window end;
  * running / stillness: c1_running.process definitions (bouts > 3 mm/s, gaps < 0.3 s filled, >= 2 s; stillness
    |v| < 1 mm/s; ITI -3..-2, pre-cue -2..0, response 0..3.5 s) over the sync window instead of the cue span;
  * treadmill trial measures (push cue - control, walking 2-3.5 s): trials.parquet values, restricted to the window;
  * statistics: c1_stats.run_family (session MWU + BH within the family + nested animal -> session bootstrap; star =
    q < .05 AND CI excludes 0), the same families as c1_analysis.movement: treadmill_primary_sidepooled, running.
Inputs are read only; outputs go to <out_dir> (refuses to overwrite).
Usage: python scripts/manuscript/engagement_movement/c1_sync60.py <c1_dir> <out_dir> [--only LABEL] [--jobs 6] [--stats-only]
  <c1_dir> = the c1_* review folder (data/trials.parquet from c1_extract_sessions.py); spout_behavior from PathResolver
  (override with SPOUT_BEHAVIOR=<dir>). Manuscript copy: vls_stroke_paper/review/c2_treadmill_2026-11-20/combined_mac_2026-11-20/.
"""
from __future__ import annotations

import argparse
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling c1_* modules


def _spout() -> Path:
    if os.environ.get('SPOUT_BEHAVIOR'):
        return Path(os.environ['SPOUT_BEHAVIOR'])
    from stroke_orofacial.paths import PathResolver
    return Path(PathResolver().pipeline_outputs(subdir='spout_behavior'))


SPOUT = _spout()
FS = 1000.0
CAP_S = 3600.0
WINDOWS = {'iti': (-3.0, -2.0), 'precue': (-2.0, 0.0), 'response': (0.0, 3.5)}
STILL, WALK = 1.0, 3.0


def _sync(animal, date):
    f = SPOUT / 'wavesurfer_signals_processed' / animal / f'{date}.npz'
    files = [f] if f.exists() else sorted((SPOUT / 'wavesurfer_signals_processed' / animal).glob(f'{date}*/{date}?.npz'))
    if not files:
        return None
    s = np.concatenate([np.load(x, allow_pickle=True)['Sync_signal'].astype(float) for x in files])
    hi = s > (np.nanmin(s) + np.nanmax(s)) / 2
    d = np.diff(hi.astype(np.int8))
    up, down = np.flatnonzero(d == 1), np.flatnonzero(d == -1)   # a channel that starts HIGH gives a spurious fall at 0
    if len(up) < 2 or len(down) < 2:
        return None
    s0 = (up[0] + 1) / FS                                          # first pulse onset
    return s0, min((down[-1] + 1) / FS, s0 + CAP_S), len(files)    # last pulse offset, capped at 60 min


def process(item):
    import c1_extract_sessions as X
    from stroke_orofacial.spout_behavior.bouts import find_running_bouts
    X.SPOUT = str(SPOUT)
    lab, cues = item
    animal, date = lab.split('_')
    sw = _sync(animal, date)
    v = X.load_treadmill(animal, date)
    if sw is None or v is None:
        return {'label': lab, 'status': 'no sync' if sw is None else 'no treadmill'}, None
    s0, s1, nf = sw
    n = len(v)
    i0, i1 = int(round(s0 * FS)), min(int(round(s1 * FS)), n)
    rm = find_running_bouts(v, FS, X.RUN)
    rs, rp = X.bouts(rm)
    x = v[i0:i1]; inb = rm[i0:i1]
    keep = (rs >= i0) & (rs < i1)
    minutes = (i1 - i0) / FS / 60.0
    S = [{'label': lab, 'span': 'sync60', 'minutes': minutes, 'scope': 'session',
          'mean_fwd_speed': float(np.maximum(x, 0).mean()),
          'mean_speed_in_bouts': float(x[inb].mean()) if inb.any() else np.nan,
          'bouts_per_min': int(keep.sum()) / minutes, 'frac_fwd_gt3': float((x > WALK).mean()),
          'frac_in_bouts': float(inb.mean()),
          'bout_dur_median_s': float(np.median((rp - rs)[keep] / FS)) if keep.any() else np.nan,
          'still_frac': float((np.abs(x) < STILL).mean())}]
    cues = np.sort(np.asarray(cues, float))
    cues = cues[(cues >= s0) & (cues + 3.5 <= s1)]
    for w, (a, b) in WINDOWS.items():
        vals = []
        for c in cues:
            j0, j1 = int(round((c + a) * FS)), int(round((c + b) * FS))
            if j0 >= i0 and j1 <= i1:
                y = v[j0:j1]
                vals.append(((np.abs(y) < STILL).mean(), np.maximum(y, 0).mean(), (y > WALK).mean()))
        vals = np.array(vals) if vals else np.full((1, 3), np.nan)
        S.append({'label': lab, 'span': 'sync60', 'minutes': minutes, 'scope': w, 'still_frac': np.nanmean(vals[:, 0]),
                  'mean_fwd_speed': np.nanmean(vals[:, 1]), 'frac_fwd_gt3': np.nanmean(vals[:, 2])})
    meta = {'label': lab, 'status': 'ok', 'sync_start_s': s0, 'sync_end_s': s1, 'minutes': minutes, 'n_files': nf,
            'n_cues_in_window': len(cues)}
    return meta, pd.DataFrame(S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path); ap.add_argument('out', type=Path)
    ap.add_argument('--only', default=None); ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--stats-only', action='store_true', help='reuse sync_windows.csv + running_sessions_sync60.parquet in <out_dir>')
    a = ap.parse_args()
    T = pd.read_parquet(a.c1 / 'data/trials.parquet')
    items = [(lab, g.cue_s.to_numpy()) for lab, g in T.groupby('label') if a.only in (None, lab)]
    if a.only:
        m, S = process(items[0]); print(m); print(S); return
    if a.stats_only:
        for f in ('tests_treadmill_primary_sidepooled_sync60.csv', 'tests_running_sync60.csv', 'session_values_running_sync60.csv'):
            if (a.out / f).exists():
                sys.exit(f'refusing to overwrite {a.out / f}')
        M = pd.read_csv(a.out / 'sync_windows.csv'); R = pd.read_parquet(a.out / 'running_sessions_sync60.parquet')
    else:
        if a.out.exists() and any(a.out.iterdir()):
            sys.exit(f'refusing to overwrite {a.out}')
        a.out.mkdir(parents=True, exist_ok=True)
        with Pool(a.jobs) as p:
            res = p.map(process, items, chunksize=2)
        M = pd.DataFrame([r[0] for r in res]); M.to_csv(a.out / 'sync_windows.csv', index=False)
        R = pd.concat([r[1] for r in res if r[1] is not None], ignore_index=True)
        R.to_parquet(a.out / 'running_sessions_sync60.parquet')
    print(M.status.value_counts().to_dict(), 'minutes', M.minutes.describe().round(3).to_dict(), flush=True)

    import c1_analysis as A
    import c1_stats as CS
    win = M[M.status == 'ok'].set_index('label')
    T = T[T.label.isin(win.index)].copy()
    s0, s1 = T.label.map(win.sync_start_s), T.label.map(win.sync_end_s)
    T['in_sync60'] = (T.cue_s >= s0) & (T.cue_s + 3.5 <= s1)
    print('trials in window:', int(T.in_sync60.sum()), 'of', len(T), flush=True)
    if not a.stats_only:
        T[['label', 'trial', 'in_sync60']].to_csv(a.out / 'trials_in_sync60.csv', index=False)
    X = A.treadmill_long(T[T.in_sync60])
    L = A.sess_side(X, ['push_cue_minus_control', 'walk_cue'])
    L = L[L.side == 'both']
    if not a.stats_only:
        L.to_csv(a.out / 'session_values_treadmill_sync60.csv', index=False)
    CS.run_family(L, 'treadmill_primary_sidepooled_sync60').to_csv(a.out / 'tests_treadmill_primary_sidepooled_sync60.csv',
                                                                    index=False)
    info = T.drop_duplicates('label')[['label', 'animal', 'date', 'grade', 'epoch']]
    meas = ['mean_fwd_speed', 'mean_speed_in_bouts', 'bouts_per_min', 'frac_fwd_gt3', 'bout_dur_median_s', 'still_frac']
    RL = R.merge(info, on='label').melt(id_vars=['label', 'animal', 'date', 'grade', 'epoch', 'span', 'scope'],
                                        value_vars=meas, var_name='m', value_name='value').dropna(subset=['value'])
    RL = RL[(RL.scope == 'session') | RL.m.isin(['still_frac', 'mean_fwd_speed', 'frac_fwd_gt3'])]
    RL['measure'] = RL.scope + ':' + RL.m; RL['side'] = 'both'
    RL.to_csv(a.out / 'session_values_running_sync60.csv', index=False)
    CS.run_family(RL, 'running_sync60').to_csv(a.out / 'tests_running_sync60.csv', index=False)
    print('done', flush=True)


if __name__ == '__main__':
    main()
