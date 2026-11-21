"""Two-tone cohort (#1-#8): treadmill push / walking, running + stillness, GLM-HMM engagement, the confound check and
the within-engaged-trials check, with the cohort-1 aligned statistics (c1_stats.run_family). Review output only.

Inputs (written by c1_extract_sessions.py, c1_running.py, c1_glmhmm.py in this folder):
  data/trials.parquet, data/traces.npz, data/running_sessions.parquet, data/running_trials.parquet,
  data/running_meta.json (N), glmhmm/<variant>_K5_states.csv.gz.
Time matching: trials with t_min < N (first cue -> + N min), N = 10th-percentile session length; "_unmatched" = all.
Sides: cue side in the mouse frame; every cohort-1 stroke is LEFT, so L = ipsilesional cue, R = contralesional cue.
Angles: per-trial first-lick peak angle stored + = ipsilesional (cohort-1 convention); reported x -1 (+ = contra,
vls_style.ANGLE_SIGN_C1).

Families (each its own BH-FDR over all its grade x side x epoch rows):
  treadmill_primary      push cue minus control, walking 2-3.5 s; per cue side; all trials, time-matched
  treadmill_secondary    push rate, control push rate, push peak, push latency, walk control, any-walk
  treadmill_lickperiod   primary pair on lick-working-period trials (six-position gate; sensitivity)
  running                session-scope speed / bouts / fraction running / bout duration / stillness, window-scope
                         stillness + forward speed (ITI -3..-2, pre-cue -2..0, response 0..3.5); time-matched
  engagement_<variant>   fraction of trials in engaged / partial / disengaged states, mean P(engaged); time-matched
  confound_<variant>     P(disengaged | contra cue) - P(disengaged | ipsi cue)
  within_all / within_engaged_<variant>   first-lick accuracy, correct licks / trial (response window), first-lick
                         peak angle (+ = contra), per cue side + contra-minus-ipsi; all vs engaged-only trials
Usage: python c1_analysis.py <c1_dir> [--stats-only] [--figs-only]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import c1_stats as CS  # noqa: E402

VARIANTS = ('primary', 'ipsi_only', 'no_cue', 'jaw3', 'init')
WHOLE = False   # --trialset whole (Priya 2026-11-20 decision 1): every trial of every session, no time match
K = 5


def load(c1: Path):
    T = pd.read_parquet(c1 / 'data/trials.parquet')
    meta = json.loads((c1 / 'data/running_meta.json').read_text())
    N = meta['N_min']
    T['matched'] = True if WHOLE else (T.t_min < N)
    jf = c1 / 'data/jaw_trials.parquet'
    if jf.exists():
        T = T.merge(pd.read_parquet(jf), on=['label', 'trial'], how='left')
    T['angle_contra'] = -T.peak_angle_deg
    st = {}
    for v in VARIANTS:
        f = c1 / f'glmhmm/{v}_K{K}_states.csv.gz'
        if f.exists():
            S = pd.read_csv(f, usecols=['label', 'trial', 'state', 'role', 'p_engaged', 'p_partial', 'p_disengaged'])
            st[v] = S
    return T, meta, N, st


def sess_side(T, cols, sides=True, agg='mean'):
    """Per session (x cue side, + 'both') means of cols -> long (animal, date, label, grade, epoch, side, measure,
    value)."""
    keys = ['animal', 'date', 'label', 'grade', 'epoch']
    out = []
    if sides:
        g = T.groupby(keys + ['side'])[cols].agg(agg).reset_index()
        out.append(g)
    g = T.groupby(keys)[cols].agg(agg).reset_index().assign(side='both')
    out.append(g)
    D = pd.concat(out, ignore_index=True)
    return D.melt(id_vars=keys + ['side'], value_vars=cols, var_name='measure', value_name='value')


def treadmill_long(T):
    X = T.copy()
    X['push_rate'] = X.push.astype(float); X['push_control_rate'] = X.push_control.astype(float)
    X['push_cue_minus_control'] = X.push_rate - X.push_control_rate
    X['push_peak_on_push'] = np.where(X.push, X.push_peak, np.nan)
    X['push_latency_on_push'] = X.push_latency_s
    X['walk_cue_any_rate'] = X.walk_cue_any.astype(float)
    return X


def run_all(c1: Path, part: str = 'all'):
    T, meta, N, st = load(c1)
    od = c1 / ('tables_whole' if WHOLE else 'tables'); od.mkdir(exist_ok=True)
    res = {}
    if part == 'engagement':
        X = None
    else:
        res.update(movement(c1, T, N, od))
    if part == 'movement':
        st = {}
    res.update(engagement(c1, T, N, od, st))
    return res


def movement(c1, T, N, od):
    res = {}
    X = treadmill_long(T)
    prim = ['push_cue_minus_control', 'walk_cue']
    sec = ['push_rate', 'push_control_rate', 'push_peak_on_push', 'push_latency_on_push', 'walk_control',
           'walk_cue_any_rate']
    L = sess_side(X[X.matched], prim + sec)
    res['treadmill_primary'] = CS.run_family(L[L.measure.isin(prim) & (L.side != 'both')], 'treadmill_primary')
    res['treadmill_primary_sidepooled'] = CS.run_family(L[L.measure.isin(prim) & (L.side == 'both')],
                                                        'treadmill_primary_sidepooled')
    res['treadmill_secondary'] = CS.run_family(L[L.measure.isin(sec) & (L.side != 'both')], 'treadmill_secondary')
    if not WHOLE:
        Lu = sess_side(X, prim)
        res['treadmill_primary_unmatched'] = CS.run_family(Lu[Lu.side != 'both'], 'treadmill_primary_unmatched')
    Ll = sess_side(X[X.matched & X.lick_period], prim)
    res['treadmill_lickperiod'] = CS.run_family(Ll[Ll.side != 'both'], 'treadmill_lickperiod')
    L.to_csv(od / 'session_values_treadmill.csv', index=False)

    # ---- running / stillness (side-free)
    R = pd.read_parquet(c1 / 'data/running_sessions.parquet')
    info = T.drop_duplicates('label')[['label', 'animal', 'date', 'grade', 'epoch']]
    R = R.merge(info, on='label')
    meas = ['mean_fwd_speed', 'mean_speed_in_bouts', 'bouts_per_min', 'frac_fwd_gt3', 'bout_dur_median_s',
            'still_frac']
    RL = R.melt(id_vars=['label', 'animal', 'date', 'grade', 'epoch', 'span', 'scope'], value_vars=meas,
                var_name='m', value_name='value').dropna(subset=['value'])
    RL = RL[(RL.scope == 'session') | RL.m.isin(['still_frac', 'mean_fwd_speed', 'frac_fwd_gt3'])]
    RL['measure'] = RL.scope + ':' + RL.m
    RL['side'] = 'both'
    RL.to_csv(od / 'session_values_running.csv', index=False)
    if WHOLE:     # whole session = first cue -> last cue + 8 s (c1_running span 'all')
        RL = RL[RL.span == 'all']
        RL.to_csv(od / 'session_values_running.csv', index=False)
        res['running'] = CS.run_family(RL, 'running')
    else:
        res['running'] = CS.run_family(RL[RL.span == 'matched'], 'running')
        res['running_unmatched'] = CS.run_family(RL[RL.span == 'all'], 'running_unmatched')
    return res


def engagement(c1, T, N, od, st):
    res = {}

    # ---- engagement, confound, within-engaged, running by state
    RT = pd.read_parquet(c1 / 'data/running_trials.parquet')
    for v, S in st.items():
        TS = T.merge(S, on=['label', 'trial'], how='left')
        for r in ('engaged', 'partial', 'disengaged'):
            TS[f'occ_{r}'] = (TS.role == r).astype(float)
        occ = ['occ_engaged', 'occ_partial', 'occ_disengaged', 'p_engaged']
        E = sess_side(TS[TS.matched], occ)
        E.to_csv(od / f'session_values_engagement_{v}.csv', index=False)
        res[f'engagement_{v}'] = CS.run_family(E[E.side == 'both'], f'engagement_{v}')
        if WHOLE:     # occupancy on ipsilesional-cue (L) and contralesional-cue (R) trials, own BH family
            res[f'engagement_{v}_bycue'] = CS.run_family(E[E.side.isin(['L', 'R'])], f'engagement_{v}_bycue')
        else:
            Eu = sess_side(TS, occ)
            res[f'engagement_{v}_unmatched'] = CS.run_family(Eu[Eu.side == 'both'], f'engagement_{v}_unmatched')
        if 'jaw_open' in TS:  # jaw opening on no-lick trials, by role x grade x epoch (x cue side)
            nl = TS[TS.matched & ~TS.responded]
            for by, nm in ((['role', 'grade', 'epoch'], ''), (['role', 'grade', 'epoch', 'side'], '_byside')):
                nl.groupby(by).agg(n_nolick_trials=('jaw_open', 'size'), jaw_open_rate=('jaw_open', 'mean'),
                                   jaw_only_candidate_rate=('jaw_only_candidate', 'mean')).round(3).to_csv(
                    od / f'jaw_on_nolick_trials_by_role{nm}_{v}.csv')
            TS[TS.matched].groupby(['role', 'grade', 'epoch']).agg(
                n=('responded', 'size'), lick_rate=('responded', 'mean'),
                jaw_only_rate=('jaw_open', lambda x: float(np.nanmean(np.where(TS.loc[x.index, 'responded'], 0, x))))
            ).round(3).to_csv(od / f'role_rates_by_grade_epoch_{v}.csv')
        # confound: disengaged at the contra vs ipsi cue
        es = E[E.measure.isin(['occ_disengaged', 'occ_engaged']) & E.side.isin(['L', 'R'])]
        w = es.pivot_table(index=['animal', 'date', 'label', 'grade', 'epoch', 'measure'], columns='side',
                           values='value').reset_index()
        w['value'] = w.R - w.L
        w['side'] = 'contra_minus_ipsi'
        res[f'confound_{v}'] = CS.run_family(w, f'confound_{v}')
        w.to_csv(od / f'session_values_confound_{v}.csv', index=False)
        # within-engaged
        wm = ['first_correct_all', 'n_correct_rw', 'angle_contra']
        for name, sel in (('all', TS.matched), ('engaged', TS.matched & (TS.role == 'engaged'))):
            if name == 'all' and 'within_all' in res:
                continue
            W = sess_side(TS[sel], wm)
            W = W[W.side != 'both']
            d = W.pivot_table(index=['animal', 'date', 'label', 'grade', 'epoch', 'measure'], columns='side',
                              values='value').reset_index()
            d['value'] = d.R - d.L; d['side'] = 'contra_minus_ipsi'
            W = pd.concat([W, d[W.columns]], ignore_index=True)
            key = 'within_all' if name == 'all' else f'within_engaged_{v}'
            W.to_csv(od / f'session_values_{key}.csv', index=False)
            res[key] = CS.run_family(W, key)
        # running / stillness within trials, split by state (descriptive family)
        RS = RT.merge(TS[['label', 'cue_s', 'trial', 'role', 'matched', 'animal', 'date', 'grade', 'epoch']],
                      left_on=['label', 'trial_cue_s'], right_on=['label', 'cue_s'], how='inner')
        cols = [c for c in RS.columns if c.endswith(('_still', '_fwd', '_gt3'))]
        rows = []
        for role in ('engaged', 'disengaged'):
            Z = sess_side(RS[RS.matched & (RS.role == role)], cols, sides=False)
            Z['measure'] = role + ':' + Z.measure
            rows.append(Z)
        Z = pd.concat(rows, ignore_index=True)
        Z.to_csv(od / f'session_values_running_by_state_{v}.csv', index=False)
        res[f'running_by_state_{v}'] = CS.run_family(Z, f'running_by_state_{v}')
        # state-level descriptives: window running per role, pre vs post (pooled)
        desc = RS[RS.matched].assign(post=lambda x: np.where(x.epoch == 'pre', 'pre', 'post')).groupby(
            ['post', 'role'])[cols].mean()
        desc.to_csv(od / f'running_by_role_descriptive_{v}.csv')
        # per-animal time course: disengaged occupancy vs contra first-lick accuracy (change from pre), sessions
        tc = TS[TS.matched].groupby(['animal', 'label', 'epoch', 'rel_day']).apply(
            lambda x: pd.Series({'diseng': (x.role == 'disengaged').mean(),
                                 'acc_contra': x[x.side == 'R'].first_correct_all.mean(),
                                 'acc_ipsi': x[x.side == 'L'].first_correct_all.mean()}),
            include_groups=False).reset_index()
        from scipy.stats import spearmanr
        out = []
        for an, g in tc.groupby('animal'):
            pre = g[g.epoch == 'pre']
            g = g.assign(d_acc_contra=g.acc_contra - pre.acc_contra.mean(),
                         d_acc_ipsi=g.acc_ipsi - pre.acc_ipsi.mean(), d_diseng=g.diseng - pre.diseng.mean())
            post = g[g.epoch != 'pre']
            rho_c = spearmanr(post.d_diseng, post.d_acc_contra).statistic if post.d_diseng.std() > 0 else np.nan
            rho_i = spearmanr(post.d_diseng, post.d_acc_ipsi).statistic if post.d_diseng.std() > 0 else np.nan
            first_rec = lambda s: (post.rel_day[s].min() if s.any() else np.nan)  # noqa: E731
            out.append({'animal': an, 'n_post': len(post), 'rho_diseng_vs_dacc_contra': rho_c,
                        'rho_diseng_vs_dacc_ipsi': rho_i,
                        'last_day_diseng_gt_0.2': post.rel_day[post.diseng > 0.2].max() if (post.diseng > 0.2).any()
                        else np.nan,
                        'last_day_dacc_contra_lt_-0.2': post.rel_day[post.d_acc_contra < -0.2].max()
                        if (post.d_acc_contra < -0.2).any() else np.nan})
        pd.DataFrame(out).to_csv(od / f'timecourse_diseng_vs_contra_acc_{v}.csv', index=False)
        tc.to_csv(od / f'timecourse_sessions_{v}.csv', index=False)
        # where do disengaged trials sit (pooled counts by grade x epoch x side)
        TS[TS.matched].groupby(['grade', 'epoch', 'side']).role.value_counts(normalize=True).unstack().round(3).to_csv(
            od / f'role_by_grade_epoch_side_{v}.csv')
    if st:
        res['within_all'] = res.get('within_all')
    # shrinkage: engaged-only vs all effects (same cell)
    for v in st:
        a, e = res['within_all'], res[f'within_engaged_{v}']
        key = ['measure', 'grade', 'side', 'post_epoch']
        m = a[key + ['nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh', 'star']].merge(
            e[key + ['nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh', 'star', 'n_post_sessions']], on=key,
            suffixes=('_all', '_engaged'))
        m['ratio_engaged_over_all'] = m.nb_effect_engaged / m.nb_effect_all
        m.to_csv(od / f'within_engaged_shrinkage_{v}.csv', index=False)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('c1', type=Path)
    ap.add_argument('--part', default='all', choices=('all', 'movement', 'engagement'))
    ap.add_argument('--trialset', default='matched', choices=('matched', 'whole'),
                    help='whole (Priya 2026-11-20): all trials of every session -> tables_whole/')
    a = ap.parse_args()
    WHOLE = a.trialset == 'whole'
    r = run_all(a.c1, a.part)
    for k, df in r.items():
        f = a.c1 / ('tables_whole' if WHOLE else 'tables') / f'tests_{k}.csv'
        if f.exists():
            print('exists, not overwritten:', f); continue
        df.to_csv(f, index=False)
        print(f'== {k}: {len(df)} rows, {int(df.star.sum())} starred')
