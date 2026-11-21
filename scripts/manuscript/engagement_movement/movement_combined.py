"""One TIM and one motion-energy (ME) measure per window, keypoints + FaceRhythm combined, both cohorts (Priya 2026-11-20:
"can we combine keypoints and FR together for TIM and ME?"). Windows: response (0-3.5 s) and ITI.

  TIM  each modality's session TIM (keypoints: mean over keypoints, px, tim_combined_px.py; FaceRhythm: whole-face TIM,
       20 point PCs, px) is z-scored against the animal's own pre-stroke sessions (mean / SD over its pre sessions), then
       the modalities are averaged (the desktop composite index's rule, s5 zpre, applied per window)
  ME   keypoint ME and FaceRhythm whole-face ME are both already z-scored to the animal's own pre-stroke frames; the
       modalities are averaged
  two-tone      keypoints only until the two-tone FaceRhythm outputs exist (marked in the figure); TIM z as above
  six-position  keypoints + FaceRhythm (desktop review tables, first 95 min)
Statistics: two-tone c1_stats.run_family ('movement_combined_sync60'); six-position wfield_local.orofacial_stats.
session_change_tests(fdr_scope='all'), star = q < .05 AND bootstrap CI excludes 0.
Usage: PYTHONPATH=src WF_REPO=<widefield_pipeline> python scripts/manuscript/engagement_movement/movement_combined.py
       <review/c2_treadmill_2026-11-20> <combined_mac dir> <out_dir>
  (<combined_mac dir> holds c1_engmove_sync60/ and tim_combined_px/; manuscript copy in
   vls_stroke_paper/review/c2_treadmill_2026-11-20/combined_mac_2026-11-20/)
"""
import os
import sys
from pathlib import Path

import pandas as pd

R0, CM, OUT = (Path(a) for a in sys.argv[1:4])
if OUT.exists() and any(OUT.iterdir()):
    sys.exit(f'refusing to overwrite {OUT}')
OUT.mkdir(parents=True, exist_ok=True)


def zpre(D, col, by='animal'):
    """z of a session value against the animal's own pre-stroke sessions (mean / SD over its pre sessions)."""
    pre = D[D.epoch == 'pre'].groupby(by)[col].agg(['mean', 'std'])
    return (D[col] - D[by].map(pre['mean'])) / D[by].map(pre['std'])


# ---- two-tone (keypoints only for now)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import c1_stats as CS  # noqa: E402
keys = ['animal', 'date', 'label', 'grade', 'epoch']
K = pd.read_csv(CM / 'tim_combined_px' / 'session_values_tim_combined_c1.csv')
M = pd.read_csv(CM / 'c1_engmove_sync60' / 'session_values_me_sync60.csv')
L = []
for per in ('response', 'iti'):
    k = K[K.measure == f'tim:{per}:all'].copy()
    k['value'] = zpre(k, 'value')
    L.append(k[keys + ['value']].assign(measure=f'tim_all:{per}', side='both'))
    m = M[M.measure == f'me:{per}_me'].copy()
    L.append(m[keys + ['value']].assign(measure=f'me_all:{per}', side='both'))
L = pd.concat(L, ignore_index=True)
L.to_csv(OUT / 'session_values_movement_combined_c1.csv', index=False)
CS.run_family(L, 'movement_combined_sync60').to_csv(OUT / 'tests_movement_combined_c1.csv', index=False)

# ---- six-position (keypoints + FaceRhythm)
sys.path.insert(0, os.path.expanduser(os.environ.get('WF_REPO', '~/Github/widefield_pipeline')))
from wfield_local import orofacial_stats as st  # noqa: E402
C2 = R0 / 'c2_engagement_tim'
k2 = ['label', 'animal', 'epoch', 'date', 'pos']
KP = pd.read_csv(CM / 'tim_combined_px' / 'session_values_tim_combined_c2.csv')
N = pd.read_csv(C2 / 'sessions_tim_new.csv')
N = N[(N['match'] == 'first95') & (N.state == 'all') & (N.trials == 'working')][k2 + ['timFR_response_face', 'timFR_iti_face']]
MO = pd.read_csv(C2 / 'sessions_motion.csv')
MO = MO[(MO['match'] == 'first95') & (MO.state == 'all')][['label', 'me_kp_response', 'me_kp_iti', 'me_fr_all_response', 'me_fr_all_iti']]
S = KP.merge(N.drop(columns=['animal', 'epoch', 'date', 'pos']), on='label', how='left').merge(MO, on='label', how='left')
for per in ('response', 'iti'):
    S[f'tim_all_{per}'] = pd.concat([zpre(S, f'timDLC_{per}_all'), zpre(S, f'timFR_{per}_face')], axis=1).mean(axis=1, skipna=False)
    S[f'me_all_{per}'] = S[[f'me_kp_{per}', f'me_fr_all_{per}']].mean(axis=1, skipna=False)
S.to_csv(OUT / 'session_values_movement_combined_c2.csv', index=False)
r = st.session_change_tests(S, ['tim_all_response', 'tim_all_iti', 'me_all_response', 'me_all_iti'], fdr_scope='all')
r['star'] = (r.q_fdr < 0.05) & ((r.boot_lo > 0) | (r.boot_hi < 0))
r.to_csv(OUT / 'tests_movement_combined_c2.csv', index=False)
print(pd.read_csv(OUT / 'tests_movement_combined_c1.csv').query('star')[['measure', 'grade', 'post_epoch']].to_string(index=False))
print(r[['metric', 'epoch', 'boot_change', 'boot_lo', 'boot_hi', 'q_fdr', 'star']].round(3).to_string(index=False))
