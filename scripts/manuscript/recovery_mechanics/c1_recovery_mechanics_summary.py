"""Summary, statistics, and panels for c1_recovery_mechanics.py (definitions in that module's docstring).

cmd_summarize(out): reads <out>/data/{cued_licks.pkl, spont_licks.pkl, block_decay.npz} + the review trials table,
  writes <out>/tables/*.csv (calibration, gate, session cells, family tests, T1 thirds / mixed models / overnight pairs,
  across-lick cells, spontaneous cells, per-animal counts) and <out>/tables/summary.json. Refuses to overwrite.
cmd_plot(out): manuscript-style panels -> <out>/figures/*.pdf (3.25 x 1.55 in two-cue panels, Arial 7.5 / 8 pt).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import c1_recovery_mechanics as RM

GRADES = ['mild', 'moderate', 'severe']
EPOCHS = ['pre', 'acute', 'sub_acute', 'chronic']
EP_NAME = {'pre': 'pre', 'acute': 'acute', 'sub_acute': 'subacute', 'chronic': 'chronic'}
COLORS = {'mild': '#f2c12e', 'moderate': '#f0822e', 'severe': '#b4001e'}
MARKERS = {'mild': 'o', 'moderate': 's', 'severe': 'D'}
MIN_N = 10            # licks per session x cue-side cell (angles, CSM)
MIN_T1 = 15           # scored contralesional-cue first licks per session for thirds (>= 5 per third)
MIN_MISS = 8          # miss pairs per session x side for the across-lick contrast
MIN_SPONT = 5         # spontaneous licks per session x spout cell
PAIR_MAX_MS = 300.0
EBIN = 5.0


def _side_ic(c):
    return np.where(np.asarray(c) == 'R', 'contra', 'ipsi')      # all fibers left VLS: right = contralesional


def load(out: Path):
    L = pd.read_pickle(out / 'data/cued_licks.pkl')
    T = pd.read_parquet(RM.TRIALS, columns=['label', 'animal', 'rel_day', 'epoch', 'grade', 'trial', 'side',
                                            'first_correct', 'cue_s'])
    L = L.merge(T[['label', 'trial', 'animal', 'rel_day', 'epoch', 'grade']], on=['label', 'trial'], how='left')
    L['side'] = _side_ic(L.cue)
    return L, T


def add_errors(L: pd.DataFrame) -> pd.DataFrame:
    """e_E / e_L vs the animal's pre-stroke HIT mean per cue side; corr; toward-target correction."""
    pre = L[(L.epoch == 'pre') & L.hit]
    rE = pre.groupby(['animal', 'cue']).theta_E.mean().rename('refE')
    rL = pre[pre.onset_ok].groupby(['animal', 'cue']).theta_L.mean().rename('refL')
    L = L.join(rE, on=['animal', 'cue']).join(rL, on=['animal', 'cue'])
    L['e_E'] = L.theta_E - L.refE
    L['e_L'] = L.theta_L - L.refL
    L['corr'] = L.e_E - L.e_L
    L['corr_toward'] = L['corr'] * np.where(L.side == 'contra', 1.0, -1.0)
    return L


def calibrate(L: pd.DataFrame) -> dict:
    C = L[(L.epoch == 'pre') & L.full_ok & L.sur_sm_sp.notna() & L.pk_sp.notna()]
    tab = []
    for th in RM.GRID:
        sm = np.array([RM.csm_count(*x, th) for x in C.sur_sm_sp])
        nz = np.array([RM.csm_count(*x, th) for x in C.sur_nz_sp])
        ob = np.array([RM.csm_count(*x, th) for x in C.pk_sp])
        tab.append({'theta': th, 'false': float(np.mean(nz > sm)), 'obs_share': float(np.mean(ob >= 1)),
                    'sur_smooth_share': float(np.mean(sm >= 1))})
    ok = [r['theta'] for r in tab if r['false'] <= RM.FALSE_MAX]
    return {'n_licks': int(len(C)), 'grid': tab, 'theta_sp': float(min(ok)) if ok else None}


def add_csm(L: pd.DataFrame, th: float) -> pd.DataFrame:
    m = L.full_ok & L.pk_sp.notna()
    L['csm'] = np.nan
    L.loc[m, 'csm'] = [RM.csm_count(*x, th) for x in L.loc[m, 'pk_sp']]
    L['csm_any'] = (L.csm >= 1).where(m)
    ms = m & L.sur_sm_sp.notna()
    L['csm_false'] = np.nan
    L.loc[ms, 'csm_false'] = [float(RM.csm_count(*a, th) > RM.csm_count(*b, th))
                              for a, b in zip(L.loc[ms, 'sur_nz_sp'], L.loc[ms, 'sur_sm_sp'])]
    return L


def gate(L: pd.DataFrame) -> pd.DataFrame:
    """Pre-stroke: real CSM share vs the noise-surrogate false rate per session (paired), and the miss / hit and
    contra / ipsi contrasts (Bollu: corrections are more frequent on licks that miss / harder targets)."""
    P = L[(L.epoch == 'pre') & L.csm_any.notna()]
    S = P.groupby(['label', 'animal']).agg(real=('csm_any', 'mean'), false=('csm_false', 'mean'),
                                           n=('csm_any', 'size')).reset_index()
    S = S[S.n >= MIN_N]
    rng = np.random.default_rng(0)
    diff = (S.real - S.false).to_numpy()
    an = S.animal.to_numpy()
    boot = []
    ua = np.unique(an)
    for _ in range(4000):
        a = rng.choice(ua, len(ua))
        boot.append(np.mean([rng.choice(diff[an == x], (an == x).sum()).mean() for x in a]))
    rows = [{'test': 'pre real - surrogate CSM share (sessions)', 'n_sessions': len(S), 'real': S.real.mean(),
             'false': S.false.mean(), 'diff': diff.mean(), 'lo': np.percentile(boot, 2.5),
             'hi': np.percentile(boot, 97.5),
             'animals_real_gt_false': int((S.groupby('animal').apply(lambda g: (g.real - g.false).mean()) > 0).sum()),
             'n_animals': int(S.animal.nunique())}]
    for nm, col in (('miss - hit', 'hit'), ('contra - ipsi cue', 'side')):
        g = P.groupby(['label', 'animal', col]).csm_any.mean().unstack()
        if col == 'hit':
            dd = (g.get(False) - g.get(True)).dropna()
        else:
            dd = (g.get('contra') - g.get('ipsi')).dropna()
        pa = dd.groupby(level='animal').mean()
        rows.append({'test': f'pre CSM share {nm}', 'n_sessions': len(dd), 'diff': float(dd.mean()),
                     'animals_pos': int((pa > 0).sum()), 'n_animals': int(len(pa))})
    return pd.DataFrame(rows)


def session_cells(L: pd.DataFrame) -> pd.DataFrame:
    keys = ['label', 'animal', 'grade', 'epoch', 'rel_day', 'side']
    rows = []
    for k, g in L.groupby(keys):
        r = dict(zip(keys, k))
        for m, sub in (('e_E', g.e_E), ('e_L', g.e_L), ('corr_toward', g.corr_toward), ('csm_share', g.csm_any),
                       ('csm_false', g.csm_false)):
            v = sub.dropna()
            r[f'n_{m}'] = len(v)
            r[m] = float(v.mean()) if len(v) >= MIN_N else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def to_long(S: pd.DataFrame, measures) -> pd.DataFrame:
    return S.melt(id_vars=['label', 'animal', 'grade', 'epoch', 'rel_day', 'side'], value_vars=measures,
                  var_name='measure', value_name='value').dropna(subset=['value'])


# ------------------------------------------------------------------------------------------------ T1
def first_licks(L: pd.DataFrame) -> pd.DataFrame:
    F = L.sort_values(['label', 'trial', 't_ms']).groupby(['label', 'trial']).head(1)
    return F


def t1(L: pd.DataFrame, T: pd.DataFrame):
    import statsmodels.formula.api as smf
    F = first_licks(L)
    X = T[T.side == 'R'].merge(F[['label', 'trial', 'e_E', 'e_L']], on=['label', 'trial'], how='left')
    X = X[X.epoch.isin(['pre', 'acute', 'sub_acute'])].sort_values(['label', 'trial'])
    X['post'] = (X.epoch != 'pre').astype(int)
    rows = []
    for (lab, an, gr, ep, day), g in X.groupby(['label', 'animal', 'grade', 'epoch', 'rel_day']):
        r = {'label': lab, 'animal': an, 'grade': gr, 'epoch': ep, 'day': int(day)}
        for nm, col in (('eE', 'e_E'), ('eL', 'e_L'), ('acc', 'first_correct')):
            v = g[col].dropna().to_numpy(float)
            r[f'n_{nm}'] = len(v)
            if len(v) >= MIN_T1:
                p = [float(np.mean(x)) for x in np.array_split(v, 3)]
                r.update({f'early_{nm}': p[0], f'mid_{nm}': p[1], f'late_{nm}': p[2], f'W_{nm}': p[2] - p[0],
                          f'M_{nm}': float(v.mean())})
        rows.append(r)
    S = pd.DataFrame(rows).sort_values(['animal', 'day'])
    # overnight pairs (consecutive calendar days, same period)
    pr = []
    for an, g in S.groupby('animal'):
        g = g.reset_index(drop=True)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if b.day - a.day != 1 or (a.epoch == 'pre') != (b.epoch == 'pre'):
                continue
            r = {'animal': an, 'grade': a.grade, 'day_d': a.day, 'post': int(a.epoch != 'pre'), 'label_d': a.label,
                 'label_d1': b.label}
            for nm in ('eE', 'eL', 'acc'):
                if np.isfinite(a.get(f'late_{nm}', np.nan)) and np.isfinite(b.get(f'early_{nm}', np.nan)):
                    r[f'O_{nm}'] = b[f'early_{nm}'] - a[f'late_{nm}']
                    r[f'S_{nm}'] = b[f'M_{nm}'] - a[f'M_{nm}']
                    r[f'W_{nm}'] = a[f'W_{nm}']
            pr.append(r)
    Pp = pd.DataFrame(pr)
    mixed = []
    for scope, grades in (('moderate+severe', ['moderate', 'severe']), ('all grades', GRADES)):
        for col, nm in (('e_E', 'first-lick e_E'), ('e_L', 'first-lick e_L'), ('first_correct', 'accuracy')):
            d = X[X.grade.isin(grades)].dropna(subset=[col]).copy()
            n = d.groupby('label')[col].transform('size')
            d = d[n >= MIN_T1].copy()
            d['x'] = d.groupby('label').cumcount() / (d.groupby('label')[col].transform('size') - 1)
            d['y'] = d[col].astype(float)
            d['session'] = d.label
            try:
                m = smf.mixedlm('y ~ x * post', d, groups=d['animal'], vc_formula={'session': '0 + C(session)'},
                                re_formula='1').fit(reml=True, method=['lbfgs', 'powell'])
                ci = m.conf_int()
                for t in ('x', 'x:post', 'post'):
                    mixed.append({'scope': scope, 'readout': nm, 'model': 'within-session y ~ x * post', 'term': t,
                                  'coef': m.params[t], 'lo': ci.loc[t, 0], 'hi': ci.loc[t, 1], 'p': m.pvalues[t],
                                  'n_trials': len(d), 'n_sessions': d.session.nunique(),
                                  'n_animals': d.animal.nunique()})
            except Exception as ex:  # noqa: BLE001
                mixed.append({'scope': scope, 'readout': nm, 'term': 'ERROR', 'error': str(ex)[:150]})
            # overnight trial-level pairs
            q = []
            Pg = Pp[Pp.grade.isin(grades)] if len(Pp) else Pp
            for k, r in enumerate(Pg.itertuples()):
                for lab, part, sec in ((r.label_d, 2, 0), (r.label_d1, 0, 1)):
                    v = X[X.label == lab][col].dropna().to_numpy(float)
                    if len(v) < MIN_T1:
                        continue
                    q += [{'animal': r.animal, 'pair': k, 'second': sec, 'post': r.post, 'y': y}
                          for y in np.array_split(v, 3)[part]]
            if q:
                Q = pd.DataFrame(q)
                try:
                    m = smf.mixedlm('y ~ second * post', Q, groups=Q['animal'], vc_formula={'pair': '0 + C(pair)'},
                                    re_formula='1').fit(reml=True, method=['lbfgs', 'powell'])
                    ci = m.conf_int()
                    for t in ('second', 'second:post'):
                        mixed.append({'scope': scope, 'readout': nm, 'model': 'overnight y ~ second * post', 'term': t,
                                      'coef': m.params[t], 'lo': ci.loc[t, 0], 'hi': ci.loc[t, 1], 'p': m.pvalues[t],
                                      'n_trials': len(Q), 'n_sessions': int(Q.pair.nunique()),
                                      'n_animals': int(Q.animal.nunique())})
                except Exception as ex:  # noqa: BLE001
                    mixed.append({'scope': scope, 'readout': nm, 'model': 'overnight', 'term': 'ERROR',
                                  'error': str(ex)[:150]})
    return S, Pp, pd.DataFrame(mixed)


# ------------------------------------------------------------------------------------------------ across-lick
def across_lick(L: pd.DataFrame) -> pd.DataFrame:
    L = L.sort_values(['label', 'trial', 't_ms'])
    rows = []
    for (lab, tr), g in L.groupby(['label', 'trial'], sort=False):
        if len(g) < 2:
            continue
        v = g[['t_ms', 'theta_E', 'e_E', 'hit']].to_numpy(object)
        for i in range(len(g) - 1):
            a, b = v[i], v[i + 1]
            if b[0] - a[0] > PAIR_MAX_MS or not (np.isfinite(a[2]) and np.isfinite(b[1])):
                continue
            rows.append((lab, tr, float(a[2]), float(b[1] - a[1]), bool(a[3])))
    Pp = pd.DataFrame(rows, columns=['label', 'trial', 'e_k', 'dang', 'hit_k'])
    Pp = Pp.merge(L.groupby(['label', 'trial'])[['animal', 'grade', 'epoch', 'rel_day', 'side']].first().reset_index(),
                  on=['label', 'trial'])
    Pp['toward'] = np.sign(-Pp.e_k) * Pp.dang
    Pp['ebin'] = np.minimum((np.abs(Pp.e_k) // EBIN), 8)
    out = []
    for k, g in Pp.groupby(['label', 'animal', 'grade', 'epoch', 'rel_day', 'side']):
        miss = g[~g.hit_k]
        r = dict(zip(['label', 'animal', 'grade', 'epoch', 'rel_day', 'side'], k))
        r['n_miss'], r['n_hit'] = len(miss), int(g.hit_k.sum())
        r['toward_after_miss'] = float(miss.toward.mean()) if len(miss) >= MIN_MISS else np.nan
        num, den = 0.0, 0
        for b, gb in g.groupby('ebin'):
            mm, hh = gb[~gb.hit_k], gb[gb.hit_k]
            if len(mm) >= 2 and len(hh) >= 2:
                num += len(mm) * (mm.toward.mean() - hh.toward.mean())
                den += len(mm)
        r['xcorr'] = num / den if den >= MIN_MISS else np.nan
        out.append(r)
    return pd.DataFrame(out)


# ------------------------------------------------------------------------------------------------ spontaneous
def choose_buffer(out: Path, T: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Pre-stroke contact rate (licks / s per block gap) by second after the block's last cue; B = first second >= 8
    from which the rate stays within 1.5x of the 30-60 s plateau."""
    z = np.load(out / 'data/block_decay.npz', allow_pickle=True)
    ep = T.groupby('label').epoch.first()
    pre = np.array([ep.get(x) == 'pre' for x in z['labels']])
    rate = z['rate'][pre].sum(0) / max(z['n_gaps'][pre].sum(), 1)
    plateau = float(np.median(rate[30:60]))
    Bs = 8
    for b in range(8, 40):
        if np.all(rate[b:40] <= 1.5 * plateau):
            Bs = b
            break
    D = pd.DataFrame({'sec_after_last_cue': np.arange(60), 'pre_rate_per_s': rate})
    return float(max(Bs, 8)), D.assign(plateau=plateau, chosen_B=max(Bs, 8))


def spontaneous(out: Path, L: pd.DataFrame, T: pd.DataFrame, Bs: float):
    S = pd.read_pickle(out / 'data/spont_licks.pkl')
    S = S.merge(T.groupby('label')[['animal', 'grade', 'epoch', 'rel_day']].first().reset_index(), on='label')
    S = S[(S.since_cue >= Bs) & (S.to_cue >= 2.0) & np.isfinite(S.theta_E)].copy()
    S['side'] = _side_ic(S.spout)
    ref = S[S.epoch == 'pre'].groupby(['animal', 'spout']).theta_E.mean().rename('ref_sp')
    S = S.join(ref, on=['animal', 'spout'])
    S['D'] = S.theta_E - S.ref_sp
    F = first_licks(L)
    F = F[F.hit]
    cued = F.groupby(['label', 'cue']).e_E.mean().rename('cued_hit_eE').reset_index().rename(columns={'cue': 'spout'})
    rows = []
    for scope, sub in (('bout_first', S[S.bout_first]), ('all', S)):
        for k, g in sub.groupby(['label', 'animal', 'grade', 'epoch', 'rel_day', 'spout', 'side']):
            r = dict(zip(['label', 'animal', 'grade', 'epoch', 'rel_day', 'spout', 'side'], k))
            r.update({'scope': scope, 'n': len(g), 'D': float(g.D.mean()) if len(g) >= MIN_SPONT else np.nan})
            rows.append(r)
    C = pd.DataFrame(rows).merge(cued, on=['label', 'spout'], how='left')
    C['GAP'] = C.D - C.cued_hit_eE
    counts = (S.groupby(['animal', 'grade', 'epoch', 'spout']).agg(n_all=('D', 'size'), n_bout_first=('bout_first', 'sum'))
              .reset_index())
    return C, counts


def cmd_summarize(out: Path):
    td = out / 'tables'
    if td.exists() and any(td.iterdir()):
        sys.exit(f'refusing to overwrite {td}')
    td.mkdir(parents=True, exist_ok=True)
    import c1_stats as CS
    L, T = load(out)
    s_check = L[(L.epoch == 'pre') & L.hit].groupby('cue').theta_E.mean().to_dict()
    L = add_errors(L)
    cal = calibrate(L)
    summ = {'pre_hit_theta_E_by_cue': s_check, 'csm_threshold_px_s': cal['theta_sp'], 'calibration_n': cal['n_licks']}
    pd.DataFrame(cal['grid']).to_csv(td / 'csm_calibration.csv', index=False)
    if cal['theta_sp'] is not None:
        L = add_csm(L, cal['theta_sp'])
        G = gate(L)
        G.to_csv(td / 'csm_gate.csv', index=False)
        summ['gate'] = G.to_dict('records')
    # launch quality: pre correlation of theta_L with theta_E, and L / R separation
    pre = L[(L.epoch == 'pre') & L.theta_L.notna()]
    summ['launch_quality'] = {'n': int(len(pre)), 'r_launch_endpoint': float(np.corrcoef(pre.theta_L, pre.theta_E)[0, 1]),
                              'launch_mean_by_cue': pre.groupby('cue').theta_L.mean().to_dict(),
                              'launch_sd': float(pre.theta_L.std()), 'endpoint_sd': float(pre.theta_E.std())}
    S = session_cells(L)
    S.to_csv(td / 'session_cells_within_lick.csv', index=False)
    meas = ['e_L', 'e_E', 'corr_toward'] + (['csm_share', 'csm_false'] if 'csm_any' in L else [])
    R1 = CS.run_family(to_long(S, meas[:3]), 'c1rm_within_lick')
    R1.to_csv(td / 'tests_within_lick.csv', index=False)
    if 'csm_any' in L:
        R2 = CS.run_family(to_long(S, meas[3:]), 'c1rm_csm')
        R2.to_csv(td / 'tests_csm.csv', index=False)
    # T1
    S1, P1, M1 = t1(L, T)
    S1.to_csv(td / 't1_sessions.csv', index=False)
    P1.to_csv(td / 't1_overnight_pairs.csv', index=False)
    M1.to_csv(td / 't1_mixed.csv', index=False)
    pa = []
    for (an, gr), g in S1[S1.epoch != 'pre'].groupby(['animal', 'grade']):
        pp = P1[(P1.animal == an) & (P1.post == 1)] if len(P1) else pd.DataFrame()
        pa.append({'animal': an, 'grade': gr, 'n_post_sessions_thirds': int(g.W_eE.notna().sum()),
                   'mean_W_eE': g.W_eE.mean(), 'mean_O_eE': pp.O_eE.mean() if 'O_eE' in pp else np.nan,
                   'mean_S_eE': pp.S_eE.mean() if 'S_eE' in pp else np.nan,
                   'n_pairs': int(pp.O_eE.notna().sum()) if 'O_eE' in pp else 0,
                   'mean_W_acc': g.W_acc.mean() if 'W_acc' in g else np.nan,
                   'mean_O_acc': pp.O_acc.mean() if 'O_acc' in pp else np.nan})
    pd.DataFrame(pa).to_csv(td / 't1_per_animal.csv', index=False)
    # across-lick
    A = across_lick(L)
    A.to_csv(td / 'across_lick_cells.csv', index=False)
    R3 = CS.run_family(to_long(A.rename(columns={}), ['xcorr', 'toward_after_miss']), 'c1rm_across_lick')
    R3.to_csv(td / 'tests_across_lick.csv', index=False)
    # spontaneous (secondary)
    Bs, D = choose_buffer(out, T)
    D.to_csv(td / 'spont_block_decay.csv', index=False)
    C, cnt = spontaneous(out, L, T, Bs)
    C.to_csv(td / 'spont_cells.csv', index=False)
    cnt.to_csv(td / 'spont_counts.csv', index=False)
    summ['spont_buffer_s'] = Bs
    lg = C[C.scope == 'bout_first'].rename(columns={})
    R4 = CS.run_family(to_long(lg.assign(side=lg.side), ['D', 'GAP']), 'c1rm_spont')
    R4.to_csv(td / 'tests_spont.csv', index=False)
    L.drop(columns=[c for c in L if c.startswith(('pk_', 'sur_'))]).to_pickle(out / 'data/cued_licks_scored.pkl')
    json.dump(summ, open(td / 'summary.json', 'w'), indent=1, default=float)
    print(json.dumps(summ, indent=1, default=float))
    for nm, R in (('within_lick', R1), ('csm', R2 if 'csm_any' in L else None), ('across_lick', R3), ('spont', R4)):
        if R is not None and len(R):
            print('==', nm)
            print(R[['measure', 'grade', 'side', 'post_epoch', 'nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh', 'star',
                     'nb_n_animals', 'n_animals_down']].round(3).to_string(index=False))
    print('== T1 mixed'); print(M1.round(4).to_string(index=False))
    print('== T1 per animal'); print(pd.DataFrame(pa).round(3).to_string(index=False))


# ------------------------------------------------------------------------------------------------ plots
def _style():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Arial', 'font.size': 7.5, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
                         'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none', 'axes.spines.top': False,
                         'axes.spines.right': False})
    return plt


def epoch_panel(S, R, measure, ylabel, fname, out: Path, zero=True, sides=('ipsi', 'contra'), ylim=None,
                surrogate=None, titles=None):
    plt = _style()
    fig, axs = plt.subplots(1, len(sides), figsize=(3.25, 1.55), sharey=True)
    axs = np.atleast_1d(axs)
    off = {'mild': -0.12, 'moderate': 0.0, 'severe': 0.12}
    for ax, sd in zip(axs, sides):
        d = S[(S.side == sd)].dropna(subset=[measure])
        for gr in GRADES:
            g = d[d.grade == gr]
            if g.empty:
                continue
            base = g[g.epoch == 'pre'].groupby('animal')[measure].mean() if zero else None
            v = g[measure] - (g.animal.map(base) if zero else 0)
            g = g.assign(v=v)
            xs, ms, es = [], [], []
            for i, ep in enumerate(EPOCHS):
                gg = g[g.epoch == ep].v.dropna()
                if len(gg):
                    ax.scatter(np.full(len(gg), i + off[gr]) + np.random.default_rng(i).uniform(-.05, .05, len(gg)),
                               gg, s=4, color=COLORS[gr], alpha=0.18, linewidths=0, zorder=1)
                    xs.append(i + off[gr]); ms.append(gg.mean()); es.append(gg.std(ddof=1) / np.sqrt(len(gg)) if len(gg) > 1 else 0)
            xs, ms, es = map(np.array, (xs, ms, es))
            if len(xs):
                full = [i + off[gr] for i in range(4)]
                solid = len(xs) == 4
                if solid:
                    ax.plot(xs, ms, color=COLORS[gr], lw=1.1, zorder=2)
                else:
                    for a in range(len(xs) - 1):
                        gap = round(xs[a + 1] - xs[a]) > 1
                        ax.plot(xs[a:a + 2], ms[a:a + 2], '--' if gap else '-', color=COLORS[gr], lw=1.1, zorder=2)
                ax.errorbar(xs, ms, yerr=es, fmt=MARKERS[gr], ms=3.6 if gr != 'severe' else 3.2, color=COLORS[gr],
                            mec='k', mew=0.4, elinewidth=0.8, capsize=0, zorder=3)
        if surrogate is not None:
            sg = S[(S.side == sd)].dropna(subset=[surrogate]).groupby('epoch')[surrogate].mean().reindex(EPOCHS)
            ax.plot(range(4), sg.to_numpy(), ':', color='0.45', lw=0.8, zorder=1)
        if zero:
            ax.axhline(0, color='0.6', lw=0.6, ls='--', zorder=0)
        ax.set_xticks(range(4), [EP_NAME[e] for e in EPOCHS], rotation=30, ha='right')
        ax.set_xlim(-0.45, 3.45)
        ttl = titles[sd] if titles else f'{"ipsilesional" if sd == "ipsi" else "contralesional"} cue'
        ax.set_title(ttl, fontsize=8, pad=2)
        if R is not None and len(R):
            rr = R[(R.measure == measure) & (R.side == sd) & R.star]
            for _, r in rr.iterrows():
                i = EPOCHS.index(r.post_epoch)
                k = ['mild', 'moderate', 'severe'].index(r.grade)
                ax.annotate('**', (i, 1.0), xycoords=('data', 'axes fraction'), xytext=(0, -2 - 7 * (2 - k)),
                            textcoords='offset points', ha='center', va='top', color=COLORS[r.grade], fontsize=7.5,
                            fontweight='bold')
        if ylim is not None:
            ax.set_ylim(*ylim)
    axs[0].set_ylabel(ylabel, fontsize=7.5)
    fig.subplots_adjust(left=0.2, right=0.99, bottom=0.27, top=0.86, wspace=0.12)
    fd = out / 'figures'
    fd.mkdir(parents=True, exist_ok=True)
    fig.savefig(fd / f'{fname}.pdf')
    fig.savefig(fd / f'{fname}.png', dpi=300)
    plt.close(fig)


def daycourse(S1: pd.DataFrame, out: Path):
    """Per animal (moderate, severe): first-lick e_E on contralesional-cue trials by session thirds over recovery."""
    plt = _style()
    an = sorted(S1[S1.grade.isin(['moderate', 'severe'])].animal.unique())
    fig, axs = plt.subplots(1, len(an), figsize=(6.5, 1.55), sharey=False)
    for ax, a in zip(np.atleast_1d(axs), an):
        g = S1[(S1.animal == a)].dropna(subset=['W_eE']).sort_values('day')
        gr = g.grade.iloc[0]
        b0 = g[g.epoch == 'pre'].M_eE.mean()          # change from the animal's own pre-stroke first-lick mean
        g = g.assign(early_eE=g.early_eE - b0, mid_eE=g.mid_eE - b0, late_eE=g.late_eE - b0)
        pre = g[g.epoch == 'pre'].tail(3)
        post = g[g.epoch != 'pre']
        x = 0
        prev = None
        for _, r in pd.concat([pre, post]).iterrows():
            xs = [x, x + 0.5, x + 1.0]
            ys = [r.early_eE, r.mid_eE, r.late_eE]
            col = '0.3' if r.epoch == 'pre' else COLORS[gr]
            ax.plot(xs, ys, '-', color=col, lw=0.9)
            ax.plot(xs, ys, MARKERS[gr], color=col, ms=2.2, mec='none')
            if prev is not None:
                ax.plot([prev[0], xs[0]], [prev[1], ys[0]], ':' if r.day - prev[2] > 1 else '--', color='0.55', lw=0.7)
            prev = (xs[-1], ys[-1], r.day)
            x += 1.6
        ax.axhline(0, color='0.6', lw=0.6, ls='--')
        ax.set_title(f'#{_num(a)} ({gr})', fontsize=8, pad=2)
        ax.set_xticks([])
        ax.set_xlabel('sessions (thirds)', fontsize=7.5)
    np.atleast_1d(axs)[0].set_ylabel('$\\Delta$ contralesional-cue\nfirst-lick angle (deg)', fontsize=7.5)
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.17, top=0.86, wspace=0.35)
    fig.savefig(out / 'figures/c1rm_t1_daycourse.pdf')
    fig.savefig(out / 'figures/c1rm_t1_daycourse.png', dpi=300)
    plt.close(fig)


def _num(a):
    key = {'PS47': 1, 'PS48': 2, 'PS49': 3, 'PS50': 4, 'PS46': 5, 'PS51': 6, 'PS54': 7, 'PS55': 8}
    return key.get(a, a)


def cmd_plot(out: Path):
    td = out / 'tables'
    S = pd.read_csv(td / 'session_cells_within_lick.csv')
    R1 = pd.read_csv(td / 'tests_within_lick.csv')
    epoch_panel(S, R1, 'e_L', 'launch error $e_L$\n(deg, + = contra)', 'c1rm_launch_error', out)
    epoch_panel(S, R1, 'e_E', 'endpoint error $e_E$\n(deg, + = contra)', 'c1rm_endpoint_error', out)
    epoch_panel(S, R1, 'corr_toward', 'within-lick correction\n(deg toward target)', 'c1rm_within_lick_corr', out)
    if (td / 'tests_csm.csv').exists():
        R2 = pd.read_csv(td / 'tests_csm.csv')
        epoch_panel(S, R2, 'csm_share', 'share of licks with\n$\\geq$1 submovement', 'c1rm_csm_share', out,
                    zero=False, surrogate='csm_false')
    A = pd.read_csv(td / 'across_lick_cells.csv')
    R3 = pd.read_csv(td / 'tests_across_lick.csv')
    epoch_panel(A, R3, 'xcorr', 'next-lick correction,\nmiss $-$ hit (deg)', 'c1rm_across_lick', out, zero=False)
    S1 = pd.read_csv(td / 't1_sessions.csv')
    daycourse(S1, out)
    C = pd.read_csv(td / 'spont_cells.csv')
    R4 = pd.read_csv(td / 'tests_spont.csv')
    epoch_panel(C[C.scope == 'bout_first'], R4, 'D', 'spontaneous lick angle\n$\\Delta$ vs pre (deg)',
                'c1rm_spont_angle', out, zero=False, sides=('ipsi', 'contra'),
                titles={'ipsi': 'ipsilesional spout', 'contra': 'contralesional spout'})


def cmd_t1_by_grade(out: Path):
    """T1 mixed models split mild + moderate vs severe (the severe animals' post-stroke within-session pattern differs;
    added after the pooled run). Writes tables/t1_mixed_by_grade.csv (refuses to overwrite)."""
    import statsmodels.formula.api as smf
    f = out / 'tables/t1_mixed_by_grade.csv'
    if f.exists():
        sys.exit(f'refusing to overwrite {f}')
    L = pd.read_pickle(out / 'data/cued_licks_scored.pkl')
    T = pd.read_parquet(RM.TRIALS, columns=['label', 'animal', 'rel_day', 'epoch', 'grade', 'trial', 'side',
                                            'first_correct'])
    F = first_licks(L)
    X = T[T.side == 'R'].merge(F[['label', 'trial', 'e_E']], on=['label', 'trial'], how='left')
    X = X[X.epoch.isin(['pre', 'acute', 'sub_acute'])].sort_values(['label', 'trial'])
    X['post'] = (X.epoch != 'pre').astype(int)
    rows = []
    for scope, gr in (('mild+moderate', ['mild', 'moderate']), ('severe', ['severe'])):
        for col in ('e_E', 'first_correct'):
            d = X[X.grade.isin(gr)].dropna(subset=[col]).copy()
            d = d[d.groupby('label')[col].transform('size') >= MIN_T1].copy()
            d['x'] = d.groupby('label').cumcount() / (d.groupby('label')[col].transform('size') - 1)
            d['y'] = d[col].astype(float)
            m = smf.mixedlm('y ~ x * post', d, groups=d['animal'], vc_formula={'session': '0 + C(label)'},
                            re_formula='1').fit(reml=True, method=['lbfgs', 'powell'])
            ci = m.conf_int()
            for t in ('x', 'x:post'):
                rows.append({'scope': scope, 'readout': col, 'term': t, 'coef': m.params[t], 'lo': ci.loc[t, 0],
                             'hi': ci.loc[t, 1], 'p': m.pvalues[t], 'n_sessions': d.label.nunique()})
    R = pd.DataFrame(rows)
    R.to_csv(f, index=False)
    print(R.round(4).to_string(index=False))
