"""Two-tone cohort, engagement + movement on the 60-min recording (first to last sync pulse), for the combined two-cohort
engagement / movement supplement (Priya 2026-11-20: "combined C1/2 engagement and motion figure, with C1 no FR TIM and ME
for now"; time-matched like the treadmill figure).

Trials = those inside each session's sync window (c1_sync60/trials_in_sync60.csv, from c1_sync60.py). Per session:
  engagement   mean posterior of the engaged / partial / disengaged roles (glmhmm/primary_K5_states.csv.gz p_engaged,
               p_partial, p_disengaged) - the six-position cohort's occupancy is also the per-session mean posterior
  TIM          keypoint task-independent movement (data/tim_trials.parquet, c1_tim.py), response (0-3.5 s) and ITI
               (-3 to -2 s), tongue / jaw / nose, mean over WORKING trials (as c1_tim.stats)
  keypoint ME  keypoint motion energy (data/me_trials.parquet, c1_keypoint_me.py), response and ITI, mean over trials
               (as c1_keypoint_me.stats)
Statistics: c1_stats.run_family (session MWU, BH within the family; star = q < .05 AND nested CI excludes 0), one family
each: engagement_sync60, tim_sync60, keypoint_me_sync60.
Usage: PYTHONPATH=src python scripts/manuscript/engagement_movement/c1_engmove_sync60.py <c1_dir> <c1_sync60_dir> <out_dir>
  (<c1_sync60_dir> = output of c1_sync60.py; manuscript copy in vls_stroke_paper/review/c2_treadmill_2026-11-20/combined_mac_2026-11-20/)
"""
import sys
from pathlib import Path

import pandas as pd

C1, SY, OUT = (Path(a) for a in sys.argv[1:4])
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling c1_stats
import c1_stats as CS  # noqa: E402

if OUT.exists() and any(OUT.iterdir()):
    sys.exit(f'refusing to overwrite {OUT}')
OUT.mkdir(parents=True, exist_ok=True)
T = pd.read_parquet(C1 / 'data/trials.parquet')
W = pd.read_csv(SY / 'trials_in_sync60.csv')
T = T.merge(W, on=['label', 'trial'], how='inner')
T = T[T.in_sync60]
keys = ['animal', 'date', 'label', 'grade', 'epoch']
print('trials in window', len(T), 'sessions', T.label.nunique(), flush=True)

# engagement: mean posterior per role
S = pd.read_csv(C1 / 'glmhmm/primary_K5_states.csv.gz', usecols=['label', 'trial', 'p_engaged', 'p_partial', 'p_disengaged'])
E = T[keys + ['trial']].merge(S, on=['label', 'trial'], how='inner')
E = E.groupby(keys)[['p_engaged', 'p_partial', 'p_disengaged']].mean().reset_index().melt(id_vars=keys, var_name='measure')
E['measure'] = E.measure.str.replace('p_', 'occ_', regex=False); E['side'] = 'both'
E.to_csv(OUT / 'session_values_engagement_sync60.csv', index=False)
CS.run_family(E, 'engagement_sync60').to_csv(OUT / 'tests_engagement_sync60.csv', index=False)

# keypoint TIM: working trials, response / ITI, tongue / jaw / nose
X = pd.read_parquet(C1 / 'data/tim_trials.parquet').rename(columns={'trial_id': 'trial'})
X = X[X.working & X.period.isin(['response', 'iti']) & X.part.isin(['tongue', 'jaw', 'nose'])]
X = X.drop(columns=['animal']).merge(T[keys + ['trial']], on=['label', 'trial'], how='inner')
L = X.groupby(keys + ['period', 'part']).tim_px.mean().reset_index()
L['measure'] = 'tim:' + L.period + ':' + L.part
L = L.rename(columns={'tim_px': 'value'}).drop(columns=['period', 'part']).assign(side='both')
L.to_csv(OUT / 'session_values_tim_sync60.csv', index=False)
CS.run_family(L, 'tim_sync60').to_csv(OUT / 'tests_tim_sync60.csv', index=False)

# keypoint motion energy: all trials, response / ITI
M = pd.read_parquet(C1 / 'data/me_trials.parquet')[['label', 'trial', 'response_me', 'iti_me']]
M = M.merge(T[keys + ['trial']], on=['label', 'trial'], how='inner')
M = M.groupby(keys)[['response_me', 'iti_me']].mean().reset_index().melt(id_vars=keys, var_name='measure')
M['measure'] = 'me:' + M.measure; M['side'] = 'both'
M.to_csv(OUT / 'session_values_me_sync60.csv', index=False)
CS.run_family(M, 'keypoint_me_sync60').to_csv(OUT / 'tests_me_sync60.csv', index=False)
for f in ('engagement', 'tim', 'me'):
    t = pd.read_csv(OUT / f'tests_{f}_sync60.csv')
    print(f, 'cells', len(t), 'stars', int(t.star.sum()), flush=True)
