"""Pre-stroke two-tone CSM share by tracked-run length and hit / miss (2026-11-22 peaks-v2 check: are the submovements
the fixed measure finds carried by long tracked runs, i.e. spout dwell or merged licks, rather than typical licks?).

    python c1_csm_by_length.py <run_out> <dest.csv>     (refuses to overwrite dest)

<run_out> is a summarized c1_recovery_mechanics output (reads data/cued_licks_scored.pkl). Prints the share of CSM licks
from runs longer than 22 frames (88 ms at 250 Hz) and the CSM / surrogate rates below and above that length.
"""
import sys
from pathlib import Path

import pandas as pd

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
assert not dst.exists(), dst
L = pd.read_pickle(src / 'data/cued_licks_scored.pkl')
P = L[(L.epoch == 'pre') & L.csm_any.notna()].copy()
P['lenbin'] = pd.cut(P.n_run, [9, 12, 15, 18, 22, 30, 200]).astype(str)
T = P.groupby(['lenbin', 'hit']).agg(n=('csm_any', 'size'), csm_share=('csm_any', 'mean'),
                                     false_rate=('csm_false', 'mean'), n_csm=('csm_any', 'sum')).reset_index()
T.to_csv(dst, index=False)
long = P.n_run > 22
print('pre licks', len(P), 'median n_run', P.n_run.median(), 'share long', round(long.mean(), 3))
print('share of CSM licks with n_run > 22:', round(P.loc[long, 'csm_any'].sum() / P.csm_any.sum(), 3))
print('csm share n_run<=22:', round(P.loc[~long, 'csm_any'].mean(), 4), 'false', round(P.loc[~long, 'csm_false'].mean(), 4))
print('csm share n_run>22:', round(P.loc[long, 'csm_any'].mean(), 4), 'false', round(P.loc[long, 'csm_false'].mean(), 4))
print('hit share among long:', round(P.loc[long, 'hit'].mean(), 3), 'among short:', round(P.loc[~long, 'hit'].mean(), 3))
