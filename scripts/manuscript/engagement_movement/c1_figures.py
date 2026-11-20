"""Cohort-1 (two-tone, #1-#8) rows for the engagement / movement supplementary figure, manuscript style
(vls_style; the c1_panels.py scalar format: severity colours, faded session dots, mean +- SEM marker per grade x epoch,
'**' = session MWU q < 0.05 in the panel's BH family AND nested bootstrap CI excludes 0).

Rows (each one figure file, to sit under the matching six-position row):
  C1_treadmill_row   A-B cue-aligned forward speed / backward velocity by epoch (all eight animals, time-matched
                     trials; session mean, +- SEM across sessions, bins with >= 3 sessions), C-D push rate (cue minus
                     control) and walking (2-3.5 s) by cue side (ipsi | contra), change from own pre
  C1_running_row     bouts / min, fraction of time running (> 3 mm/s), mean forward speed, ITI stillness (< 1 mm/s)
  C1_engagement_row  engaged occupancy, disengaged occupancy, disengaged contra-minus-ipsi (confound), contra-minus-
                     ipsi first-lick accuracy: all vs engaged-only trials (primary GLM-HMM)
Usage: MC=<manuscript_code> python c1_figures.py <c1_dir>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(os.environ.get('MC', 'M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/'
                                           'vls_stroke_paper/manuscript_code')) / 'figures'))
import vls_style as S  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

EPOCHS = [('pre', 'pre'), ('acute', 'acute'), ('sub_acute', 'subacute'), ('chronic', 'chronic')]
GR = ['mild', 'moderate', 'severe']
WHOLE = False   # argv '--whole' (Priya 2026-11-20): all trials of every session, tables_whole/ -> figures_whole/
TB = 'tables'


def deltas(L):
    b = L[L.epoch == 'pre'].groupby(['animal', 'side', 'measure']).value.mean().rename('b').reset_index()
    L = L.merge(b, on=['animal', 'side', 'measure'], how='left')
    L['delta'] = L.value - L.b
    return L.dropna(subset=['delta'])


def panel(ax, d, tests, ylab, title=None, sign=1.0, show_x=True):
    S.zero_line(ax)
    for k, g in enumerate(GR):
        dg = d[d.grade == g]
        xs, ms, es = [], [], []
        for i, (e, _) in enumerate(EPOCHS):
            v = sign * dg[dg.epoch == e].delta
            if v.empty:
                continue
            off = (k - 1) * 0.09
            ax.scatter(i + off + np.random.default_rng(i + 10 * k).uniform(-.03, .03, len(v)), v, s=4, color=S.SEV[g],
                       alpha=0.18, lw=0, zorder=1)
            xs.append(i + off); ms.append(v.mean()); es.append(v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0)
        ax.errorbar(xs, ms, yerr=es, color=S.SEV[g], marker=S.SEV_MK[g], ms=3.6, mec='k', mew=0.35, lw=0,
                    elinewidth=0.9, capsize=0, zorder=3)
        ax.plot(xs, ms, '-', color=S.SEV[g], lw=1.0, zorder=2)
    ax.set_xticks(range(4))
    ax.set_xticklabels([n for _, n in EPOCHS] if show_x else [], rotation=32, ha='right', rotation_mode='anchor')
    ax.set_xlim(-0.5, 3.5)
    v = sign * d.delta
    lo, hi = v.quantile(0.01), v.quantile(0.99)
    span = (hi - lo) or 1.0
    ax.set_ylim(lo - 0.08 * span, hi + 0.42 * span)
    y0, y1 = ax.get_ylim()
    if tests is not None:
        for row, g in enumerate(['severe', 'moderate', 'mild']):
            for i, (e, _) in enumerate(EPOCHS[1:], start=1):
                m = tests[(tests.grade == g) & (tests.post_epoch == e)]
                if len(m) and bool(m.iloc[0].star):
                    ax.text(i, y1 - (0.07 + 0.085 * row) * (y1 - y0), '**', color=S.SEV[g], ha='center',
                            va='center', fontsize=8, fontweight='bold')
    ax.set_ylabel(ylab, fontsize=6.8)
    if title:
        ax.set_title(title, fontsize=7, pad=2)


def treadmill_row(c1, od):
    tb = c1 / TB
    L = deltas(pd.read_csv(tb / 'session_values_treadmill.csv'))
    R = pd.read_csv(tb / 'tests_treadmill_primary.csv')
    T = pd.read_parquet(c1 / 'data/trials.parquet', columns=['label', 'trial', 'epoch', 't_min'])
    N = json.loads((c1 / 'data/running_meta.json').read_text())['N_min']
    Z = np.load(c1 / 'data/traces.npz', allow_pickle=True)
    t = Z['t']
    key = pd.DataFrame({'label': Z['label'], 'trial': Z['trial']}).merge(T, on=['label', 'trial'], how='left')
    keep = np.ones(len(key), bool) if WHOLE else (key.t_min < N).to_numpy()
    tw = (t >= -1.0) & (t <= 3.0)
    fig, ax = plt.subplots(1, 6, figsize=(7.6, 1.85), gridspec_kw={'width_ratios': [1.25, 1.25, 1, 1, 1, 1]})
    for i, (ch, ylab, sgn) in enumerate((('fwd', 'forward speed (mm/s)', 1), ('back', 'backward velocity (mm/s)', -1))):
        a = ax[i]
        for (w0, w1), lab in (((-2, -1), 'control'), ((-0.25, 0.75), 'cue'), ((2.0, 3.5), 'walk')):
            a.axvspan(max(w0, -1.0), min(w1, 3.0), color='0.92', lw=0, zorder=0)
            a.text((max(w0, -1.0) + min(w1, 3.0)) / 2, 1.0, lab, transform=a.get_xaxis_transform(), ha='center',
                   va='bottom', fontsize=6)
        a.axvline(0, color='0.6', lw=0.6, ls='--', zorder=0)
        X = pd.DataFrame(Z[ch][keep][:, tw])
        X['label'] = key.label[keep].to_numpy(); X['epoch'] = key.epoch[keep].to_numpy()
        sess = X.groupby(['label', 'epoch']).mean()
        for e, nm in EPOCHS:
            if e not in sess.index.get_level_values('epoch'):
                continue
            Y = sgn * sess.xs(e, level='epoch').to_numpy(float)
            n = np.isfinite(Y).sum(0)
            mu = np.where(n >= S.TRAJ_MIN_SESSIONS, np.nanmean(Y, 0), np.nan)
            se = np.where(n >= S.TRAJ_MIN_SESSIONS, np.nanstd(Y, 0, ddof=1) / np.sqrt(np.maximum(n, 1)), np.nan)
            col = '#222222' if e == 'pre' else S.EP[nm]
            a.fill_between(t[tw], mu - se, mu + se, color=col, alpha=S.TRAJ_BAND, lw=0)
            a.plot(t[tw], mu, color=col, lw=S.TRAJ_LW, label=nm)
        a.set_xlim(-1, 3); a.set_xlabel('s from cue'); a.set_ylabel(ylab, fontsize=6.8)
    ax[0].legend(loc='upper left', fontsize=5.6, handlelength=1.0)
    j = 2
    for m, ylab in (('push_cue_minus_control', 'Δ push rate,\ncue − control'), ('walk_cue', 'Δ walking 2-3.5 s\n(fraction)')):
        for sd, ttl in (('L', 'ipsi cue'), ('R', 'contra cue')):
            panel(ax[j], L[(L.measure == m) & (L.side == sd)], R[(R.measure == m) & (R.side == sd)],
                  ylab if sd == 'L' else '', ttl)
            j += 1
    fig.subplots_adjust(left=0.065, right=0.995, bottom=0.27, top=0.86, wspace=1.0)
    S.save(fig, str(od / 'C1_treadmill_row'))


def running_row(c1, od):
    tb = c1 / TB
    L = pd.read_csv(tb / 'session_values_running.csv')
    L = deltas(L[L.span == ('all' if WHOLE else 'matched')])
    R = pd.read_csv(tb / 'tests_running.csv')
    spec = [('session:bouts_per_min', 'Δ running bouts / min'), ('session:frac_fwd_gt3', 'Δ fraction of time\nrunning (> 3 mm/s)'),
            ('session:mean_fwd_speed', 'Δ mean forward\nspeed (mm/s)'), ('iti:still_frac', 'Δ ITI stillness\n(fraction < 1 mm/s)')]
    fig, ax = plt.subplots(1, 4, figsize=(5.6, 1.75))
    for a, (m, ylab) in zip(ax, spec):
        panel(a, L[L.measure == m], R[R.measure == m], ylab)
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.27, top=0.95, wspace=0.75)
    S.save(fig, str(od / 'C1_running_row'))


def engagement_row(c1, od, v='primary'):
    tb = c1 / TB
    if not (tb / f'tests_engagement_{v}.csv').exists():
        print('no engagement tables yet'); return
    E = deltas(pd.read_csv(tb / f'session_values_engagement_{v}.csv'))
    RE = pd.read_csv(tb / f'tests_engagement_{v}.csv')
    C = pd.read_csv(tb / f'session_values_confound_{v}.csv')
    C = deltas(C[['animal', 'date', 'label', 'grade', 'epoch', 'measure', 'side', 'value']])
    RC = pd.read_csv(tb / f'tests_confound_{v}.csv')
    WA = deltas(pd.read_csv(tb / 'session_values_within_all.csv'))
    WE = deltas(pd.read_csv(tb / f'session_values_within_engaged_{v}.csv'))
    RA = pd.read_csv(tb / 'tests_within_all.csv'); RW = pd.read_csv(tb / f'tests_within_engaged_{v}.csv')
    fig, ax = plt.subplots(1, 5, figsize=(7.0, 1.8))
    panel(ax[0], E[(E.measure == 'occ_engaged') & (E.side == 'both')], RE[RE.measure == 'occ_engaged'],
          'Δ engaged occupancy')
    panel(ax[1], E[(E.measure == 'occ_disengaged') & (E.side == 'both')], RE[RE.measure == 'occ_disengaged'],
          'Δ disengaged occupancy')
    panel(ax[2], C[C.measure == 'occ_disengaged'], RC[RC.measure == 'occ_disengaged'],
          'Δ disengaged,\ncontra − ipsi cue')
    m = 'first_correct_all'
    panel(ax[3], WA[(WA.measure == m) & (WA.side == 'R')], RA[(RA.measure == m) & (RA.side == 'R')],
          'Δ first-lick accuracy,\ncontra cue', 'all trials')
    panel(ax[4], WE[(WE.measure == m) & (WE.side == 'R')], RW[(RW.measure == m) & (RW.side == 'R')], '',
          'engaged trials')
    lo = min(ax[3].get_ylim()[0], ax[4].get_ylim()[0]); hi = max(ax[3].get_ylim()[1], ax[4].get_ylim()[1])
    for a in ax[3:]:
        a.set_ylim(lo, hi)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.27, top=0.88, wspace=0.75)
    S.save(fig, str(od / f'C1_engagement_row{"" if v == "primary" else "_" + v}'))
    if not WHOLE:
        return
    # occupancy per cue side (Priya 2026-11-20 decision 2): engaged / partial / disengaged x ipsi | contra cue
    RB = pd.read_csv(tb / f'tests_engagement_{v}_bycue.csv')
    fig, ax = plt.subplots(1, 6, figsize=(8.2, 1.85), sharey=False)
    j = 0
    for m, nm in (('occ_engaged', 'engaged'), ('occ_partial', 'partial'), ('occ_disengaged', 'disengaged')):
        for sd, ttl in (('L', 'ipsi cue'), ('R', 'contra cue')):
            panel(ax[j], E[(E.measure == m) & (E.side == sd)], RB[(RB.measure == m) & (RB.side == sd)],
                  f'Δ {nm} occupancy' if sd == 'L' else '', ttl)
            j += 1
        lo = min(ax[j - 2].get_ylim()[0], ax[j - 1].get_ylim()[0]); hi = max(ax[j - 2].get_ylim()[1], ax[j - 1].get_ylim()[1])
        ax[j - 2].set_ylim(lo, hi); ax[j - 1].set_ylim(lo, hi)
    fig.subplots_adjust(left=0.06, right=0.995, bottom=0.27, top=0.86, wspace=0.6)
    S.save(fig, str(od / f'C1_engagement_bycue_row{"" if v == "primary" else "_" + v}'))


def key(od):
    fig, ax = plt.subplots(figsize=(4.4, 0.3)); ax.axis('off')
    h = [plt.Line2D([], [], color=S.SEV[p], marker=S.SEV_MK[p], mec='k', mew=0.35, ms=4, lw=1,
                    label=f'{p} (n = {S.SEV_N[p]})') for p in GR]
    h.append(plt.Line2D([], [], color='0.2', marker='$**$', ls='none', ms=7, label='q < 0.05 & CI'))
    ax.legend(handles=h, ncol=4, loc='center', fontsize=6.6, columnspacing=0.8, handlelength=1.4)
    S.save(fig, str(od / 'C1_severity_key'))


if __name__ == '__main__':
    c1 = Path(sys.argv[1])
    WHOLE = '--whole' in sys.argv
    TB = 'tables_whole' if WHOLE else 'tables'
    od = c1 / ('figures_whole' if WHOLE else 'figures')
    if WHOLE and od.exists():
        sys.exit(f'refusing to overwrite {od}')
    od.mkdir(exist_ok=True)
    S.apply()
    which = [w for w in sys.argv[2:] if w != '--whole'] or ['treadmill', 'running', 'engagement', 'key']
    if 'treadmill' in which: treadmill_row(c1, od)
    if 'running' in which: running_row(c1, od)
    if 'engagement' in which:
        for v in ('primary', 'ipsi_only') + (('jaw3', 'init') if WHOLE else ()):
            engagement_row(c1, od, v)
    if 'key' in which: key(od)
