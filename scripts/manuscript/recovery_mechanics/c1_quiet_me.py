"""Two-tone face motion energy (ME) in the NON-REWARD (quiet) blocks (secondary; Priya 2026-11-21).

Same ME as the manuscript's two-tone keypoint ME (c1_keypoint_me.py, used by c1_engmove_sync60.py / S17): the cached
40-ms bins of per-keypoint cumulative frame-to-frame displacement (11 DLC keypoints: tongue, jaw, nose, L/R whiskers
1-3, L/R eyes; positions > 5 SD from the session mean dropped), each keypoint z-scored to the ANIMAL'S OWN pre-stroke
bins (mean / SD over all its pre sessions), then averaged over keypoints. Restricted to the 60-min recording
(c1_sync60/sync_windows.csv) and to quiet-block bins: inter-cue gaps > 60 s, from the block's last cue + B to the next
cue - 2 s, B = the post-cue buffer chosen for the spontaneous-lick analysis (c1_recovery_mechanics tables/summary.json,
from the pre-stroke lick-rate decay). Split: licking bins (a lick-sensor contact, either spout, within +-250 ms of the
bin centre) vs non-licking bins. Session value = mean over bins; side = 'both'. No TIM (no trials to regress).
Statistics: c1_stats.run_family, family 'quiet_me' (its own family).
Usage: PYTHONPATH=src:scripts/manuscript/engagement_movement:scripts/manuscript/recovery_mechanics
       python c1_quiet_me.py <rm_out> <c1_dir> <c1_sync60_dir>
Writes <rm_out>/tables/quiet_me_sessions.csv, tests_quiet_me.csv, figures/S17_quiet_me.pdf (refuses to overwrite).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LICK_HALF_S = 0.25
BLOCK_GAP_S = 60.0


def main(out: Path, c1: Path, sy: Path):
    import datetime
    import c1_stats as CS
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.spout_behavior.visual_gate import load_session_plot_data
    td = out / 'tables'
    f_s, f_t = td / 'quiet_me_sessions.csv', td / 'tests_quiet_me.csv'
    if f_s.exists() or f_t.exists():
        sys.exit('refusing to overwrite quiet_me tables')
    Bs = float(json.loads((td / 'summary.json').read_text())['spont_buffer_s'])
    T = pd.read_parquet(c1 / 'data/trials.parquet', columns=['label', 'animal', 'date', 'grade', 'epoch', 'cue_s'])
    info = T.drop_duplicates('label').set_index('label')
    W = pd.read_csv(sy / 'sync_windows.csv').set_index('label')
    cache = c1 / 'cache_me'
    labs = [l for l in info.index if (cache / f'{l}.npz').exists() and l in W.index and W.loc[l, 'status'] == 'ok']
    # per-animal pre moments per keypoint over all pre bins (c1_keypoint_me.measures, pass 1)
    mom = {}
    for l in labs:
        if info.loc[l, 'epoch'] != 'pre':
            continue
        me = np.load(cache / f'{l}.npz')['me'].astype(float)
        s = mom.setdefault(info.loc[l, 'animal'], [0, 0, 0])
        s[0] = s[0] + np.nansum(me, 0); s[1] = s[1] + np.nansum(me ** 2, 0); s[2] = s[2] + np.isfinite(me).sum(0)
    mu = {a: s[0] / s[2] for a, s in mom.items()}
    sd = {a: np.sqrt(s[1] / s[2] - mu[a] ** 2) for a, s in mom.items()}
    r = PathResolver()
    rows = []
    for l in labs:
        a = info.loc[l, 'animal']
        if a not in mu:
            continue
        Z = np.load(cache / f'{l}.npz')
        tb = Z['t_bin_s']
        z = np.nanmean((Z['me'].astype(float) - mu[a]) / sd[a], 1)
        cues = np.sort(T[T.label == l].cue_s.to_numpy())
        w0, w1 = W.loc[l, 'sync_start_s'], W.loc[l, 'sync_end_s']
        quiet = np.zeros(len(tb), bool)
        for gi in np.flatnonzero(np.diff(cues) > BLOCK_GAP_S):
            quiet |= (tb >= cues[gi] + Bs) & (tb < cues[gi + 1] - 2.0)
        quiet &= (tb >= w0) & (tb <= w1) & np.isfinite(z)
        d = info.loc[l, 'date']
        sdat = load_session_plot_data(a, str(d), r)
        lk = np.sort(np.r_[sdat.lick_idx['Lick_L'], sdat.lick_idx['Lick_R']]).astype(float) / float(sdat.sample_rate)
        j = np.searchsorted(lk, tb)
        near = np.minimum(np.abs(tb - lk[np.clip(j, 0, len(lk) - 1)]), np.abs(tb - lk[np.clip(j - 1, 0, len(lk) - 1)])) \
            if len(lk) else np.full(len(tb), np.inf)
        licking = near <= LICK_HALF_S
        base = dict(label=l, animal=a, date=str(d), grade=info.loc[l, 'grade'], epoch=info.loc[l, 'epoch'], side='both')
        for nm, m in (('quiet_all', quiet), ('quiet_nolick', quiet & ~licking), ('quiet_lick', quiet & licking)):
            rows.append({**base, 'measure': nm, 'value': float(z[m].mean()) if m.sum() >= 25 else np.nan,
                         'n_bins': int(m.sum())})
        rows.append({**base, 'measure': 'quiet_lick_frac', 'value': float(licking[quiet].mean()) if quiet.any()
                     else np.nan, 'n_bins': int(quiet.sum())})
    S = pd.DataFrame(rows)
    S.to_csv(f_s, index=False)
    R = CS.run_family(S.dropna(subset=['value']), 'quiet_me')
    R.to_csv(f_t, index=False)
    print('B =', Bs, 's;', S.label.nunique(), 'sessions')
    print(R[['measure', 'grade', 'post_epoch', 'nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh', 'star', 'n_animals_down',
             'nb_n_animals']].round(3).to_string(index=False))
    # panel matching the S17 ME panels: change from pre, by grade; columns all / no-lick quiet bins
    import c1_recovery_mechanics_summary as SM
    P = S.pivot_table(index=['label', 'animal', 'grade', 'epoch'], columns='measure', values='value').reset_index()
    P = P.melt(id_vars=['label', 'animal', 'grade', 'epoch'], value_vars=['quiet_all', 'quiet_nolick'],
               var_name='side', value_name='me')
    P['rel_day'] = 0
    RR = R.assign(side=R.measure, measure='me')
    SM.epoch_panel(P, RR, 'me', '$\\Delta$ motion energy (z)', 'S17_quiet_me', out, zero=True,
                   sides=('quiet_all', 'quiet_nolick'),
                   titles={'quiet_all': 'non-reward blocks', 'quiet_nolick': 'non-reward, no licking'})


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
