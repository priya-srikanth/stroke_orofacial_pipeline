"""Two-tone KEYPOINT MOTION ENERGY (prompt item 11a) and keypoint STILLNESS (11c), Yin et al. 2025 STAR Methods
definition, from the DLC keypoints (c1_dlc_common: tongue, jaw, nose, L/R whiskers 1-3, L/R eyes = 11 parts).

STATUS: prepared and tested on 2 sessions; the full run is DEFERRED (Priya 2026-11-20 00:05: two-tone motion energy
waits for the colleague's FaceRhythm data so all ME measures are run together). Nothing here needs FaceRhythm.

Definition:
  1. per part, positions more than 5 SD from the part's session mean (x or y) -> NaN (Yin: "drop > 5 SD");
  2. frame-to-frame displacement d = |p(f) - p(f-1)| (px), NaN if either frame is NaN;
  3. CUMULATIVE over 40 ms bins (10 frames at 250 fps): bin ME = nansum of d (NaN if no valid frame);
  4. z per part against the ANIMAL'S OWN PRE-STROKE bins (mean / SD over all its pre sessions' bins), so epochs are
     comparable (Yin z-score within session; within-session z would remove the level change this item looks for);
  5. bin ME = mean of the parts' z (parts with data); window / trial value = mean over its bins.
Windows (Priya 2026-11-20 00:25, cue at 0): iti -3..-2 s, precue -2..0 s, response 0..3.5 s.
Stillness: fraction of bins whose ME is below the animal's PRE-STROKE 10th percentile of BETWEEN-TRIAL bins
  (between trials = outside [cue - 2 s, cue + 8 s]); reported whole-session (first cue -> + N min, all bins), between
  trials (same span) and within trials (the three windows).

Stage 1 (--stage cache): per session, bin ME per part over the whole session -> <cache>/<label>.npz
  (t_bin_s, me [bins, 11] float32, parts). ~4 MB / session; default cache = <c1>/cache_me (or --cache).
Stage 2 (--stage measures): per-animal pre moments + P10, per-trial window ME, per-session measures ->
  <c1>/data/me_trials.parquet, me_sessions.parquet (then c1_analysis-style stats: `--stage stats` writes
  tables/tests_keypoint_me*.csv with c1_stats.run_family, family 'keypoint_me', and the engagement split).

Commands (after the data decision):
  python c1_keypoint_me.py <c1> --stage cache --jobs 6 [--cache D:/scratch/me]
  python c1_keypoint_me.py <c1> --stage measures [--cache ...]
  python c1_keypoint_me.py <c1> --stage stats
Test: python c1_keypoint_me.py <c1> --stage cache --only PS46_20250310,PS54_20250505 --cache <scratch>
Inputs: data/trials.parquet + data/running_meta.json (N) from this folder, glmhmm/primary_K5_states.csv.gz (split),
  the DLC sources in c1_dlc_common.
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
from c1_dlc_common import load_session  # noqa: E402

BIN_S = 0.040
WINDOWS = {'iti': (-3.0, -2.0), 'precue': (-2.0, 0.0), 'response': (0.0, 3.5)}
TRIAL_SPAN = (-2.0, 8.0)
PARTS = ['tongue', 'jaw', 'nose', 'L_whiskers_1', 'L_whiskers_2', 'L_whiskers_3', 'R_whiskers_1', 'R_whiskers_2',
         'R_whiskers_3', 'L_eye', 'R_eye']


def session_cache(item):
    label, cache = item
    out = Path(cache) / f'{label}.npz'
    if out.exists():
        return label, 'exists'
    animal, date = label.split('_')
    S = load_session(animal, date)
    if S is None:
        return label, 'missing source'
    t, parts = S
    ok_t = np.isfinite(t)
    t0, t1 = np.nanmin(t), np.nanmax(t)
    edges = np.arange(t0, t1 + BIN_S, BIN_S)
    bi = np.where(ok_t, np.floor((t - t0) / BIN_S), -1).astype(np.int64)
    nb = len(edges) - 1
    ME = np.full((nb, len(PARTS)), np.nan, np.float32)
    for j, p in enumerate(PARTS):
        x, y = parts[p]
        x, y = x.copy(), y.copy()
        for v in (x, y):
            m, s = np.nanmean(v), np.nanstd(v)
            v[np.abs(v - m) > 5 * s] = np.nan
        d = np.r_[np.nan, np.hypot(np.diff(x), np.diff(y))]
        good = np.isfinite(d) & (bi >= 0) & (bi < nb)
        ME[:, j] = np.where(np.bincount(bi[good], minlength=nb)[:nb] > 0,
                            np.bincount(bi[good], weights=d[good], minlength=nb)[:nb], np.nan)
    np.savez_compressed(out, t_bin_s=(edges[:-1] + BIN_S / 2).astype(np.float64), me=ME, parts=np.array(PARTS))
    return label, 'ok'


def measures(c1: Path, cache: Path):
    T = pd.read_parquet(c1 / 'data/trials.parquet')
    N = json.loads((c1 / 'data/running_meta.json').read_text())['N_min']
    labs = sorted(T.label.unique())
    have = {l: cache / f'{l}.npz' for l in labs if (cache / f'{l}.npz').exists()}
    info = T.drop_duplicates('label').set_index('label')
    # pass 1: per-animal pre moments per part
    mom = {}
    for l, f in have.items():
        if info.loc[l, 'epoch'] != 'pre':
            continue
        me = np.load(f)['me'].astype(float)
        a = info.loc[l, 'animal']
        s = mom.setdefault(a, [np.zeros(len(PARTS)), np.zeros(len(PARTS)), np.zeros(len(PARTS))])
        s[0] += np.nansum(me, 0); s[1] += np.nansum(me ** 2, 0); s[2] += np.isfinite(me).sum(0)
    mu = {a: s[0] / s[2] for a, s in mom.items()}
    sd = {a: np.sqrt(s[1] / s[2] - mu[a] ** 2) for a, s in mom.items()}

    def zbin(l):
        Z = np.load(have[l]); a = info.loc[l, 'animal']
        z = (Z['me'].astype(float) - mu[a]) / sd[a]
        return Z['t_bin_s'], np.nanmean(z, 1)
    # pass 2: per-animal P10 of between-trial pre bins
    p10 = {}
    for a in mu:
        vals = []
        for l in have:
            if info.loc[l, 'animal'] != a or info.loc[l, 'epoch'] != 'pre':
                continue
            tb, z = zbin(l)
            cues = T[T.label == l].cue_s.to_numpy()
            inside = np.zeros(len(tb), bool)
            for c in cues:
                inside[np.searchsorted(tb, c + TRIAL_SPAN[0]):np.searchsorted(tb, c + TRIAL_SPAN[1])] = True
            vals.append(z[~inside & np.isfinite(z)])
        p10[a] = float(np.percentile(np.concatenate(vals), 10)) if vals else np.nan
    rows, srows = [], []
    for l in have:
        a = info.loc[l, 'animal']
        if a not in mu:
            continue
        tb, z = zbin(l)
        Tl = T[T.label == l]
        cues = Tl.cue_s.to_numpy()
        inside = np.zeros(len(tb), bool)
        for c in cues:
            inside[np.searchsorted(tb, c + TRIAL_SPAN[0]):np.searchsorted(tb, c + TRIAL_SPAN[1])] = True
        for _, r in Tl.iterrows():
            rr = {'label': l, 'trial': r.trial}
            for w, (a0, b0) in WINDOWS.items():
                s = z[np.searchsorted(tb, r.cue_s + a0):np.searchsorted(tb, r.cue_s + b0)]
                rr[f'{w}_me'] = float(np.nanmean(s)) if np.isfinite(s).any() else np.nan
                rr[f'{w}_still'] = float(np.mean(s[np.isfinite(s)] < p10[a])) if np.isfinite(s).any() else np.nan
            rows.append(rr)
        for span, t_end in (('matched', min(cues[0] + N * 60, cues[-1] + 8)), ('all', cues[-1] + 8)):
            m = (tb >= cues[0]) & (tb < t_end) & np.isfinite(z)
            srows.append({'label': l, 'span': span, 'session_me': float(z[m].mean()),
                          'session_still': float((z[m] < p10[a]).mean()),
                          'between_me': float(z[m & ~inside].mean()), 'between_still': float((z[m & ~inside] < p10[a]).mean()),
                          'p10_pre': p10[a]})
    MT, MS = pd.DataFrame(rows), pd.DataFrame(srows)
    return MT, MS


def stats(c1: Path, whole: bool = False):
    import c1_stats as CS
    T = pd.read_parquet(c1 / 'data/trials.parquet')
    N = np.inf if whole else json.loads((c1 / 'data/running_meta.json').read_text())['N_min']
    span = 'all' if whole else 'matched'
    MT = pd.read_parquet(c1 / 'data/me_trials.parquet').merge(T, on=['label', 'trial'])
    MS = pd.read_parquet(c1 / 'data/me_sessions.parquet').merge(T.drop_duplicates('label')[
        ['label', 'animal', 'date', 'grade', 'epoch']], on='label')
    cols = [c for c in MT.columns if c.endswith(('_me', '_still'))]
    keys = ['animal', 'date', 'label', 'grade', 'epoch']
    W = MT[MT.t_min < N].groupby(keys)[cols].mean().reset_index().melt(id_vars=keys, var_name='measure')
    S = MS[MS.span == span].melt(id_vars=keys + ['span'], value_vars=['session_me', 'session_still',
                                                                         'between_me', 'between_still'],
                                      var_name='measure')
    L = pd.concat([W, S.drop(columns='span')], ignore_index=True).assign(side='both')
    od = c1 / ('tables_whole' if whole else 'tables'); od.mkdir(exist_ok=True)
    CS.run_family(L, 'keypoint_me').to_csv(od / 'tests_keypoint_me.csv', index=False)
    st = c1 / 'glmhmm/primary_K5_states.csv.gz'
    if st.exists():
        R = MT.merge(pd.read_csv(st, usecols=['label', 'trial', 'role', 'p_engaged']), on=['label', 'trial'])
        Z = []
        for role in ('engaged', 'disengaged'):
            z = R[(R.t_min < N) & (R.role == role)].groupby(keys)[cols].mean().reset_index().melt(id_vars=keys,
                                                                                                var_name='measure')
            z['measure'] = role + ':' + z.measure
            Z.append(z)
        CS.run_family(pd.concat(Z).assign(side='both'), 'keypoint_me_by_state').to_csv(
            od / 'tests_keypoint_me_by_state.csv', index=False)
        pe = R[R.t_min < N].groupby(keys).agg(p_engaged=('p_engaged', 'mean'),
                                             me_precue=('precue_me', 'mean'), me_iti=('iti_me', 'mean')).reset_index()
        pe.to_csv(od / 'keypoint_me_vs_p_engaged_sessions.csv', index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--stage', required=True, choices=('cache', 'measures', 'stats'))
    ap.add_argument('--cache', type=Path, default=None)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--only', default=None)
    ap.add_argument('--trialset', default='matched', choices=('matched', 'whole'),
                    help='stats stage: whole (Priya 2026-11-20) = all trials / whole session -> tables_whole/')
    a = ap.parse_args()
    cache = a.cache or (a.c1 / 'cache_me')
    if a.stage == 'cache':
        cache.mkdir(parents=True, exist_ok=True)
        labs = sorted(pd.read_parquet(a.c1 / 'data/trials.parquet', columns=['label']).label.unique())
        if a.only:
            labs = [l for l in labs if l in a.only.split(',')]
        items = [(l, str(cache)) for l in labs]
        if a.jobs > 1 and len(items) > 1:
            with Pool(a.jobs) as p:
                res = p.map(session_cache, items, chunksize=1)
        else:
            res = [session_cache(i) for i in items]
        print(pd.Series(dict(res)).value_counts().to_string())
        print([r for r in res if r[1] != 'ok'][:20])
    elif a.stage == 'measures':
        outs = [a.c1 / 'data/me_trials.parquet', a.c1 / 'data/me_sessions.parquet']
        if any(p.exists() for p in outs) and not a.only:
            sys.exit(f'refusing to overwrite {outs}')
        MT, MS = measures(a.c1, cache)
        if a.only:
            print(MT.describe().T.to_string()); print(MS.to_string()); return
        MT.to_parquet(outs[0]); MS.to_parquet(outs[1])
    else:
        td = 'tables_whole' if a.trialset == 'whole' else 'tables'
        if (a.c1 / td / 'tests_keypoint_me.csv').exists():
            sys.exit(f'refusing to overwrite {td}/tests_keypoint_me.csv')
        stats(a.c1, a.trialset == 'whole')


if __name__ == '__main__':
    main()
