"""Per-trial JAW OPENING for the two-tone cohort (for the jaw-based GLM-HMM variants, Priya 2026-11-20 decision 3).

Source = the pipeline's own per-trial tongue-jaw mismatch classifier output (read-only):
  dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet
  * jaw_pass_qc  = jaw opened after the cue: |jaw_y - baseline(-500..0 ms)| > max(4 SD, 4 px), sustained (>= 5 of 8
                   frames), within 0..5 s of the cue (configs/defaults.yaml tongue_jaw_mismatch / jaw_pertrial);
  * candidate_no_lick_with_jaw_move = jaw_pass_qc AND no camera-detected tongue lick 70 ms..5 s (the manuscript
                   "jaw-only" trial, endpoint mismatch_candidate_no_lick_with_jaw_move).
Matched to data/trials.parquet by the chronological trial index (sides checked). Sessions without a classifier file
get NaN (their non-responded trials are unobserved in the jaw variants).
Writes data/jaw_trials.parquet (label, trial, jaw_open, jaw_only_candidate). Refuses to overwrite.
Usage: python c1_jaw_trials.py <c1_dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/dlc_kinematics/tongue_jaw_mismatch/candidate_trials')

c1 = Path(sys.argv[1])
out = c1 / 'data/jaw_trials.parquet'
if out.exists():
    sys.exit(f'refusing to overwrite {out}')
T = pd.read_parquet(c1 / 'data/trials.parquet', columns=['label', 'animal', 'date', 'trial', 'side'])
rows, bad, miss = [], [], []
for lab, g in T.groupby('label'):
    an, d = lab.split('_')
    f = ROOT / an / f'{d}.parquet'
    if not f.exists():
        miss.append(lab)
        continue
    J = pd.read_parquet(f, columns=['trial_index', 'side', 'jaw_pass_qc', 'candidate_no_lick_with_jaw_move'])
    m = g.merge(J, left_on='trial', right_on='trial_index', how='left', suffixes=('', '_j'))
    if (m.side_j.notna() & (m.side_j != m.side)).any():
        bad.append(lab)
        continue
    rows.append(pd.DataFrame({'label': lab, 'trial': m.trial,
                              'jaw_open': m.jaw_pass_qc.astype('float'),
                              'jaw_only_candidate': m.candidate_no_lick_with_jaw_move.astype('float')}))
R = pd.concat(rows, ignore_index=True)
R.to_parquet(out)
print(f'{R.label.nunique()} sessions with jaw; missing file {len(miss)}: {miss}; side mismatch {len(bad)}: {bad}')
print('jaw_open rate', np.nanmean(R.jaw_open).round(3), 'NaN trials', int(R.jaw_open.isna().sum()))
