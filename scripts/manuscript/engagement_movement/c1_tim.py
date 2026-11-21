"""Two-tone TASK-INDEPENDENT MOVEMENT (TIM; prompt items 4 / 8 / 10b) with the six-position model, from the DLC
keypoints. STATUS: prepared and tested on 2 sessions; the full run is DEFERRED with the two-tone motion energy
(Priya 2026-11-20 00:05). Nothing here needs FaceRhythm.

Model = widefield_pipeline `wfield_local.task_independent_movement` (VERSION 2) functions imported UNCHANGED:
`within_predictions` (one ridge-OLS per (period, 100-ms time bin), RIDGE 2 on all but the intercept, MIN_TRAIN 12;
WORKING trials predicted cross-validated over 5 GroupKFold folds, every other trial predicted by the fit on all working
trials) and `per_trial` (per trial x period x part: mean Euclidean residual = TIM px; mean deviation from the
intercept-only CV fit = total px). Only the two-tone inputs are built here:
  * parts (x, y pairs, px): tongue, jaw (pipeline interpolated traces, mouth frame; tongue in the mouth = origin),
    nose (raw DLC, eye-midpoint frame, likelihood >= 0.5), whisker_L / whisker_R (mean of the 3 whisker points per side,
    raw DLC, likelihood >= 0.5) -> 5 parts (module PARTS / TRACES set to these);
  * frames binned to 40 ms (10 frames at 250 fps) on the wavesurfer clock (cam2 alignment template);
  * periods (Priya 2026-11-20 00:25, cue at 0): iti -3..-2 s, precue -2..0 s, response 0..3.5 s; 100-ms cue-locked
    time bins in each (a separate fit per bin, so side x time interactions are free, as in the paper);
  * regressors (two-tone task): precue / iti = intercept + previous cue side (contra = 1) + previous outcome (first
    lick correct); response = intercept + current cue side + previous cue side + previous outcome + CURRENT outcome
    (the outcome happens in the response period). The cue side is not a pre-cue regressor (the tone has not played);
  * working trials = responded (spout lick 70 ms - 8 s) inside the lick working period; folds = GroupKFold(5) over
    contiguous 8-trial blocks (no spout blocks in the two-tone task).
Output per trial x period x part (tim_px, total_px, n_bins) -> data/tim_trials.parquet. Cohort step (--stage stats):
session mean of tim_px over working trials in the first N min, per period x part, change from the animal's own pre
(c1_stats.run_family, family 'tim'); engagement checks: (i) pre-stroke, engaged vs disengaged trials within session
(paired over sessions); (ii) post-stroke TIM change within ENGAGED trials only (family 'tim_engaged') vs all trials.

Commands:
  python c1_tim.py <c1> --stage trials --jobs 6         # -> data/tim_trials.parquet (~1 min / session / job)
  python c1_tim.py <c1> --stage stats                   # -> tables/tests_tim*.csv
Test: python c1_tim.py <c1> --stage trials --only PS46_20250310,PS46_20250315 --jobs 2 (prints, writes nothing)
"""
from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
WF = 'C:/Users/SabatiniLab/Github/widefield_pipeline_c2stats'
BIN_S = 0.040
PERIODS = {'iti': (-3.0, -2.0), 'precue': (-2.0, 0.0), 'response': (0.0, 3.5)}
TBIN_S = 0.100
PARTS = ('tongue', 'jaw', 'nose', 'whisker_L', 'whisker_R')
BLOCK = 8
N_FOLDS = 5


def _tim_module():
    if WF not in sys.path:
        sys.path.insert(0, WF)
    from wfield_local import task_independent_movement as M
    M.PARTS = PARTS
    M.TRACES = [f'{p}_{a}' for p in PARTS for a in 'xy']
    return M


def session_bins(label: str, T: pd.DataFrame):
    from c1_dlc_common import load_session
    from sklearn.model_selection import GroupKFold
    M = _tim_module()
    animal, date = label.split('_')
    S = load_session(animal, date)
    if S is None:
        return None
    t, P = S
    tr = {'tongue': P['tongue'], 'jaw': P['jaw'], 'nose': P['nose']}
    for sd in 'LR':
        xs = np.nanmean(np.vstack([P[f'{sd}_whiskers_{i}'][0] for i in (1, 2, 3)]), 0)
        ys = np.nanmean(np.vstack([P[f'{sd}_whiskers_{i}'][1] for i in (1, 2, 3)]), 0)
        tr[f'whisker_{sd}'] = (xs, ys)
    Tl = T[T.label == label].sort_values('trial').reset_index(drop=True)
    contra = (Tl.side == 'R').to_numpy(float)
    hit = Tl.first_correct_all.to_numpy(float)
    work = (Tl.responded & Tl.lick_period).to_numpy(bool)
    blocks = (Tl.trial.to_numpy() // BLOCK).astype(int)
    fold = np.full(len(Tl), -1)
    wi = np.flatnonzero(work)
    if len(np.unique(blocks[wi])) >= N_FOLDS:
        for f, (_a, te) in enumerate(GroupKFold(N_FOLDS).split(wi, groups=blocks[wi])):
            fold[wi[te]] = f
    order = np.argsort(t[np.isfinite(t)])
    tt = t[np.isfinite(t)][order]
    fidx = np.flatnonzero(np.isfinite(t))[order]
    rows = []
    for j, r in Tl.iterrows():
        pc, ph = (contra[j - 1], hit[j - 1]) if j else (0.0, 0.0)
        des = {'precue': [1.0, pc, ph], 'iti': [1.0, pc, ph], 'response': [1.0, contra[j], pc, ph, hit[j]]}
        for per, (a, b) in PERIODS.items():
            i0, i1 = np.searchsorted(tt, r.cue_s + a), np.searchsorted(tt, r.cue_s + b)
            if i1 <= i0:
                continue
            fr = fidx[i0:i1]
            rel = tt[i0:i1] - r.cue_s
            b40 = np.floor(rel / BIN_S).astype(int)
            D = pd.DataFrame({'b': b40, **{f'{p}_{c}': tr[p][k][fr] for p in PARTS for k, c in enumerate('xy')}})
            G = D.groupby('b').mean().reset_index()
            G['tbin'] = np.floor((G.b + 0.5) * BIN_S / TBIN_S).astype(int)
            G['period'], G['owner'] = per, int(r.trial)
            x = np.zeros(M.NX); x[:len(des[per])] = des[per]
            G[M.XCOLS] = x
            rows.append(G.drop(columns='b'))
    G = pd.concat(rows, ignore_index=True)
    meta = pd.DataFrame({'owner': Tl.trial.to_numpy(), 'working': work, 'fold': fold, 'position': Tl.side.to_numpy(),
                         'cls': np.where(Tl.responded, np.where(hit > 0, 'correct_first', 'incorrect_first'),
                                         'no_response'), 'block': blocks})
    G = G.merge(meta, on='owner', how='left')
    G['label'] = label
    return G.reset_index(drop=True)


def session_tim(item):
    label, T = item
    M = _tim_module()
    G = session_bins(label, T)
    if G is None:
        return None
    return M.per_trial(G, *M.within_predictions(G), 'within')


def stats(c1: Path, whole: bool = False):
    import c1_stats as CS
    T = pd.read_parquet(c1 / 'data/trials.parquet')
    N = np.inf if whole else json.loads((c1 / 'data/running_meta.json').read_text())['N_min']
    R = pd.read_parquet(c1 / 'data/tim_trials.parquet').rename(columns={'trial_id': 'trial'})
    R = R.merge(T[['label', 'trial', 'grade', 'epoch', 'date', 't_min']], on=['label', 'trial'])
    R = R[R.t_min < N]
    keys = ['animal', 'date', 'label', 'grade', 'epoch']
    od = c1 / ('tables_whole' if whole else 'tables'); od.mkdir(exist_ok=True)

    def fam(D, name):
        L = D.groupby(keys + ['period', 'part']).tim_px.mean().reset_index()
        L['measure'] = L.period + ':' + L.part
        L = L.rename(columns={'tim_px': 'value'}).assign(side='both')
        CS.run_family(L, name).to_csv(od / f'tests_{name}.csv', index=False)
    fam(R[R.working], 'tim')
    fam(R, 'tim_alltrials')
    st = c1 / 'glmhmm/primary_K5_states.csv.gz'
    if st.exists():
        R = R.merge(pd.read_csv(st, usecols=['label', 'trial', 'role']), on=['label', 'trial'])
        fam(R[R.role == 'engaged'], 'tim_engaged')
        pre = R[R.epoch == 'pre'].groupby(['label', 'animal', 'period', 'part', 'role']).tim_px.mean().unstack()
        if 'disengaged' in pre and 'engaged' in pre:
            pre['dis_minus_eng'] = pre['disengaged'] - pre['engaged']
            pre.reset_index().to_csv(od / 'tim_pre_disengaged_vs_engaged.csv', index=False)
        else:   # two-tone: the GLM-HMM disengaged state never occurs before the stroke
            pd.DataFrame([{'status': 'not estimable', 'reason': 'no pre-stroke trial in a disengaged-role state',
                           'pre_roles_present': ','.join(map(str, pre.columns))}]).to_csv(
                od / 'tim_pre_disengaged_vs_engaged.csv', index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--stage', required=True, choices=('trials', 'stats'))
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--only', default=None)
    ap.add_argument('--trialset', default='matched', choices=('matched', 'whole'),
                    help='stats stage: whole (Priya 2026-11-20) = all trials -> tables_whole/')
    a = ap.parse_args()
    if a.stage == 'stats':
        td = 'tables_whole' if a.trialset == 'whole' else 'tables'
        if (a.c1 / td / 'tests_tim.csv').exists():
            sys.exit(f'refusing to overwrite {td}/tests_tim.csv')
        return stats(a.c1, a.trialset == 'whole')
    out = a.c1 / 'data/tim_trials.parquet'
    if out.exists() and not a.only:
        sys.exit(f'refusing to overwrite {out}')
    T = pd.read_parquet(a.c1 / 'data/trials.parquet')
    labs = sorted(T.label.unique())
    if a.only:
        labs = [l for l in labs if l in a.only.split(',')]
    items = [(l, T[T.label == l]) for l in labs]
    if a.jobs > 1 and len(items) > 1:
        with Pool(a.jobs) as p:
            res = p.map(session_tim, items, chunksize=1)
    else:
        res = [session_tim(i) for i in items]
    R = pd.concat([r for r in res if r is not None], ignore_index=True)
    print('sessions with TIM:', R.label.nunique(), 'of', len(labs))
    if a.only:
        print(R.groupby(['label', 'period', 'part', 'working'])[['tim_px', 'total_px']].mean().round(2).to_string())
        return
    R.to_parquet(out)


if __name__ == '__main__':
    main()
