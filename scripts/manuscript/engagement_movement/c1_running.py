"""Two-tone cohort: RUNNING and treadmill STILLNESS (prompt items 11d and the treadmill part of 11c), time-matched.

Windows (Priya 2026-11-20 00:25, two-tone, cue at 0): ITI = -3..-2 s (the 1 s before the pre-cue); PRE-CUE = -2..0 s;
CUE-TO-RESPONSE = 0..3.5 s. Whole-session measures = first cue -> first cue + N min, N = the cohort's 10th-percentile
session length (first -> last cue, `data/extract_meta.csv`); shorter sessions enter whole; "all" = first cue -> last
cue + 8 s (unmatched).

Treadmill = `Treadmill_smoothed` (mm/s, + forward) via c1_extract_sessions.load_treadmill. Running bouts = forward
> 3 mm/s, gaps < 0.3 s filled, >= 2 s (six-position definition). Stillness = |speed| < 1 mm/s.

Per session (span = matched | all):
  session scope   mean_fwd_speed (mean of max(v, 0)), mean_speed_in_bouts, bouts_per_min (bout onsets / min),
                  frac_fwd_gt3 (fraction of time forward > 3 mm/s), frac_in_bouts, bout_dur_median_s, still_frac;
  window scopes   iti (-3..-2), precue (-2..0), response (0..3.5) pooled over the span's trials: still_frac,
                  mean_fwd_speed, frac_fwd_gt3.
Per trial: still / mean forward speed / >3 fraction in each window (for the engagement split).

Usage: python c1_running.py <c1_dir> [--jobs 8] [--only LABEL]
Writes <c1_dir>/data/running_sessions.parquet, running_trials.parquet, running_meta.json. Refuses to overwrite.
"""
from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from c1_extract_sessions import RUN, bouts, load_treadmill  # noqa: E402

WINDOWS = {'iti': (-3.0, -2.0), 'precue': (-2.0, 0.0), 'response': (0.0, 3.5)}
STILL, WALK = 1.0, 3.0
FS = 1000.0


def process(item):
    from stroke_orofacial.spout_behavior.bouts import find_running_bouts
    lab, cues, n_min = item
    animal, date = lab.split('_')
    v = load_treadmill(animal, date)
    if v is None:
        return None, None
    n = len(v)
    rm = find_running_bouts(v, FS, RUN)
    rs, rp = bouts(rm)
    cues = np.sort(np.asarray(cues, float))
    S, TR = [], []
    for i, c in enumerate(cues):
        row = {'label': lab, 'trial_cue_s': c}
        for w, (a, b) in WINDOWS.items():
            i0, i1 = int(round((c + a) * FS)), int(round((c + b) * FS))
            x = v[i0:i1] if (i0 >= 0 and i1 <= n) else np.array([])
            row[f'{w}_still'] = float((np.abs(x) < STILL).mean()) if len(x) else np.nan
            row[f'{w}_fwd'] = float(np.maximum(x, 0).mean()) if len(x) else np.nan
            row[f'{w}_gt3'] = float((x > WALK).mean()) if len(x) else np.nan
        TR.append(row)
    TR = pd.DataFrame(TR)
    t_all = min(cues[-1] + 8.0, n / FS)
    for span, t_end in (('matched', min(cues[0] + n_min * 60.0, t_all)), ('all', t_all)):
        i0, i1 = int(cues[0] * FS), int(t_end * FS)
        x = v[i0:i1]
        on = rs[(rs >= i0) & (rs < i1)]
        dur = (rp - rs)[(rs >= i0) & (rs < i1)] / FS
        inb = rm[i0:i1]
        minutes = (i1 - i0) / FS / 60.0
        r = {'label': lab, 'span': span, 'minutes': minutes, 'scope': 'session',
             'mean_fwd_speed': float(np.maximum(x, 0).mean()),
             'mean_speed_in_bouts': float(x[inb].mean()) if inb.any() else np.nan,
             'bouts_per_min': len(on) / minutes, 'frac_fwd_gt3': float((x > WALK).mean()),
             'frac_in_bouts': float(inb.mean()), 'bout_dur_median_s': float(np.median(dur)) if len(dur) else np.nan,
             'still_frac': float((np.abs(x) < STILL).mean())}
        S.append(r)
        sel = TR[TR.trial_cue_s < t_end - 8.0 + 1e-9] if span == 'matched' else TR
        for w in WINDOWS:
            S.append({'label': lab, 'span': span, 'minutes': minutes, 'scope': w,
                      'still_frac': sel[f'{w}_still'].mean(), 'mean_fwd_speed': sel[f'{w}_fwd'].mean(),
                      'frac_fwd_gt3': sel[f'{w}_gt3'].mean()})
    return pd.DataFrame(S), TR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    od = a.c1 / 'data'
    outs = [od / 'running_sessions.parquet', od / 'running_trials.parquet', od / 'running_meta.json']
    if a.only is None and any(p.exists() for p in outs):
        sys.exit('refusing to overwrite: ' + ', '.join(map(str, [p for p in outs if p.exists()])))
    T = pd.read_parquet(od / 'trials.parquet')
    M = pd.read_csv(od / 'extract_meta.csv')
    n_min = float(np.floor(np.percentile(M.span_min, 10) * 10) / 10)
    print(f'N = {n_min} min (10th percentile of first->last cue span over {len(M)} sessions; '
          f'{int((M.span_min < n_min).sum())} shorter sessions enter whole)', flush=True)
    items = [(lab, g.cue_s.to_numpy(), n_min) for lab, g in T.groupby('label') if a.only in (None, lab)]
    if a.jobs > 1 and len(items) > 1:
        with Pool(a.jobs) as p:
            res = p.map(process, items, chunksize=1)
    else:
        res = [process(i) for i in items]
    S = pd.concat([r[0] for r in res if r[0] is not None], ignore_index=True)
    TR = pd.concat([r[1] for r in res if r[1] is not None], ignore_index=True)
    if a.only:
        print(S.to_string()); print(TR.head().to_string()); return
    S.to_parquet(outs[0]); TR.to_parquet(outs[1])
    outs[2].write_text(json.dumps({'N_min': n_min, 'p10_span_min': float(np.percentile(M.span_min, 10)),
                                   'n_sessions': len(M), 'n_shorter': int((M.span_min < n_min).sum()),
                                   'span_min_range': [float(M.span_min.min()), float(M.span_min.max())]}, indent=1))
    print('written', od, flush=True)


if __name__ == '__main__':
    main()
