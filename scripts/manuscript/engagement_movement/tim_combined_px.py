"""Combined keypoint task-independent movement (TIM), both cohorts (Priya 2026-11-20: "I don't want tongue, jaw, nose TIM
independently ... all keypoints + FR TIM and all keypoints + FR ME").

Per session and window (response 0-3.5 s; ITI), the keypoints' TIM (mean over WORKING trials, px) is AVERAGED over the
keypoints (equal weight, px). Not z-scored: the first version (tim_combined.py) z-scored each keypoint to the animal's
pre-stroke sessions, but tongue TIM between trials is ~0 before the stroke, so its tiny pre SD blew the ITI z up (+16 /
+24 z in the six-position cohort):
  two-tone      tongue, jaw, nose, left and right whisker pads (every part of c1_tim.py), trials inside the 60-min
                recording (c1_sync60/trials_in_sync60.csv)
  six-position  tongue, jaw, nose (every part of the DLC TIM table), c2_engagement_tim/sessions_tim_new.csv (match first95,
                state all, trials working)
Statistics (each cohort's own code, unchanged): two-tone c1_stats.run_family ('tim_combined_sync60'); six-position
wfield_local.orofacial_stats.session_change_tests(fdr_scope='all') + star = q < .05 AND bootstrap CI excludes 0.
The six-position half reads the desktop's widefield review table and calls widefield_pipeline's session_change_tests
(WF_REPO); the six-position inputs are produced by widefield_pipeline, not this repo.
Usage: PYTHONPATH=src WF_REPO=<widefield_pipeline> python scripts/manuscript/engagement_movement/tim_combined_px.py
       <review/c2_treadmill_2026-11-20> <c1_sync60 dir> <out_dir>
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

R0, SY, OUT = (Path(a) for a in sys.argv[1:4])
if OUT.exists() and any(OUT.iterdir()):
    sys.exit(f'refusing to overwrite {OUT}')
OUT.mkdir(parents=True, exist_ok=True)


def zmean(D, unit, keys, parts, value='value'):
    """D long (keys + part + value) -> per session mean over the parts of the value (px); sessions missing a part dropped."""
    D = D[D.part.isin(parts)].dropna(subset=[value])
    g = D.groupby(keys)[value].agg(['mean', 'size']).reset_index()
    g = g[g['size'] == len(parts)]
    return g.drop(columns='size').rename(columns={'mean': unit})


# ---- two-tone
C1 = R0 / 'c1'
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling c1_stats
import c1_stats as CS  # noqa: E402
T = pd.read_parquet(C1 / 'data/trials.parquet').merge(pd.read_csv(SY / 'trials_in_sync60.csv'), on=['label', 'trial'])
T = T[T.in_sync60]
keys = ['animal', 'date', 'label', 'grade', 'epoch']
X = pd.read_parquet(C1 / 'data/tim_trials.parquet').rename(columns={'trial_id': 'trial'})
X = X[X.working & X.period.isin(['response', 'iti'])].drop(columns=['animal']).merge(T[keys + ['trial']], on=['label', 'trial'])
P1 = sorted(X.part.unique())
S = X.groupby(keys + ['period', 'part']).tim_px.mean().rename('value').reset_index()
L = []
for per in ('response', 'iti'):
    z = zmean(S[S.period == per], 'value', keys, P1)
    L.append(z.assign(measure=f'tim:{per}:all', side='both'))
L = pd.concat(L, ignore_index=True)
L.to_csv(OUT / 'session_values_tim_combined_c1.csv', index=False)
CS.run_family(L, 'tim_combined_sync60').to_csv(OUT / 'tests_tim_combined_c1.csv', index=False)
print('two-tone parts', P1, 'sessions', L.label.nunique(), flush=True)

# ---- six-position
sys.path.insert(0, os.path.expanduser(os.environ.get('WF_REPO', '~/Github/widefield_pipeline')))
from wfield_local import orofacial_stats as st  # noqa: E402
N = pd.read_csv(R0 / 'c2_engagement_tim/sessions_tim_new.csv')
N = N[(N['match'] == 'first95') & (N.state == 'all') & (N.trials == 'working')]
k2 = ['label', 'animal', 'epoch', 'date', 'pos']
out = N[k2].drop_duplicates().copy()
for per in ('response', 'iti'):
    cols = [c for c in N.columns if c.startswith(f'timDLC_{per}_')]
    D = N[k2 + cols].melt(id_vars=k2, var_name='part', value_name='value')
    z = zmean(D, f'timDLC_{per}_all', k2, cols)
    out = out.merge(z, on=k2, how='left')
out.to_csv(OUT / 'session_values_tim_combined_c2.csv', index=False)
r = st.session_change_tests(out, ['timDLC_response_all', 'timDLC_iti_all'], fdr_scope='all')
r['star'] = (r.q_fdr < 0.05) & ((r.boot_lo > 0) | (r.boot_hi < 0))
r.to_csv(OUT / 'tests_tim_combined_c2.csv', index=False)
print('six-position parts', cols, 'sessions', out.label.nunique(), flush=True)
print(pd.read_csv(OUT / 'tests_tim_combined_c1.csv').query('star')[['measure', 'grade', 'post_epoch']].to_string(index=False))
print(r[['metric', 'epoch', 'boot_change', 'boot_lo', 'boot_hi', 'q_fdr', 'star']].round(3).to_string(index=False))
