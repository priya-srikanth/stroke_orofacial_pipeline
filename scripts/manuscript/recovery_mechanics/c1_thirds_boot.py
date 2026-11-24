"""S8E (two-tone, cohort 1): within- vs between-session recovery of contralesional-cue first-lick angle on session
thirds, change from each animal's own pre-stroke value (Priya 11-23; the same analysis as the six-position S12F,
`thirds_recovery_core.py`).

Input: `t1_sessions.csv` of c1_recovery_mechanics_summary (review/c1_recovery_mechanics_2026-11-21_r2): first-lick
endpoint angle e_E on contralesional-cue trials, sessions with >= 15 scored first licks split into thirds; post =
acute + subacute (chronic not in this analysis; the severe animals therefore enter only on subacute days 20-50).
Bootstrap: stroke_orofacial.stats.pooled_endpoint_suite.nested_animal_bootstrap_ci (the c2-aligned scalar family's
paired animals -> sessions bootstrap, 4,000 draws, seed 0). Groups: mild, moderate, severe; mild + moderate added as
the grouping the current S8E mixed model used.

    python c1_thirds_boot.py <t1_sessions.csv> <out_dir> <fig_stem>
Refuses to overwrite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thirds_recovery_core as TC

FIG_LABEL = {'PS47': 1, 'PS48': 2, 'PS49': 3, 'PS50': 4, 'PS46': 5, 'PS51': 6, 'PS54': 7, 'PS55': 8}
NUM = {a: f'#{n}' for a, n in FIG_LABEL.items()}
COLORS = {'mild': '#f2c12e', 'moderate': '#f0822e', 'severe': '#b4001e'}
MARKERS = {'mild': 'o', 'moderate': 's', 'severe': 'D'}
GROUPS = [('mild+moderate', ['mild', 'moderate']), ('mild', ['mild']), ('moderate', ['moderate']),
          ('severe', ['severe'])]


def boot(post: dict, pre: dict):
    from stroke_orofacial.stats.pooled_endpoint_suite import nested_animal_bootstrap_ci
    rows = [{'animal': a, 'epoch_label': 'pre', 'v': v} for a, vs in pre.items() for v in vs]
    rows += [{'animal': a, 'epoch_label': 'post', 'v': v} for a, vs in post.items() for v in vs]
    r = nested_animal_bootstrap_ci(pd.DataFrame(rows), post_epoch='post', value_col='v', seed=0)
    return r['nb_effect'], r['nb_ci_lo'], r['nb_ci_hi']


def load(path: str) -> pd.DataFrame:
    S = pd.read_csv(path).dropna(subset=['W_eE'])
    S = S[S.epoch.isin(['pre', 'acute', 'sub_acute'])]
    return pd.DataFrame({'animal': S.animal, 'grade': S.grade, 'label': S.label, 'epoch': S.epoch, 'day': S.day,
                         'post': (S.epoch != 'pre').astype(int), 'early': S.early_eE, 'mid': S.mid_eE,
                         'late': S.late_eE, 'M': S.M_eE})


def render(S: pd.DataFrame, stem: str, yshare: str = 'none'):
    """S8E, all eight animals (Priya 11-23: the figure shows the animals in the statistic), 4 rows x 2 columns grouped
    by grade (mild #1-#4, moderate #5-#6, severe #7-#8), 3.17 in wide (the width of the S8 right-column block) x
    4.63 in (0.85 in panels). Drawing style = the S12F style (thirds_recovery_core.STYLE); fonts as the S8 compact page (Arial 6.5 pt
    ticks / labels, 7 pt titles); ink kept inside the page."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mt
    plt.rcdefaults()
    plt.rcParams.update({'font.family': 'Arial', 'font.size': 6.5, 'axes.linewidth': 0.6, 'xtick.major.width': 0.6,
                         'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
                         'pdf.fonttype': 42, 'svg.fonttype': 'none', 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.labelpad': 1.5, 'xtick.labelsize': 6.5,
                         'ytick.labelsize': 6.5})
    # panel height 0.85 in = the S12F per-animal panel (1.35 in x (0.86 - 0.24) = 0.84 in); Priya 11-23: a taller
    # block is fine, width stays the S8 right-column block
    eL, eR, eB, eT, eWS, eHS, ah = 0.47, 0.04, 0.2, 0.13, 0.28, 0.3, 0.85
    W, H = 3.17, eB + eT + 3 * eHS + 4 * ah
    aw = (W - eL - eR - eWS) / 2
    fig = plt.figure(figsize=(W, H))
    an = sorted(S.animal.unique(), key=lambda a: FIG_LABEL[a])
    axs = []
    for k, a in enumerate(an):
        r, c = divmod(k, 2)
        ax = fig.add_axes([(eL + c * (aw + eWS)) / W, (H - eT - (r + 1) * ah - r * eHS) / H, aw / W, ah / H])
        d = S[S.animal == a]
        gr = d.grade.iloc[0]
        TC.draw_animal(ax, d, lambda _r, g=gr: COLORS[g], MARKERS[gr], pre_label_fs=6.0)
        ax.set_title(f'{NUM[a]} ({gr})', fontsize=7, pad=2)
        axs.append(ax)
    # y scale: 'none' = each panel its own (default), 'grade' = shared within a grade, 'all' = one scale for all 8
    grp = {a: (S[S.animal == a].grade.iloc[0] if yshare == 'grade' else 'all') for a in an}
    if yshare != 'none':
        for g in set(grp.values()):
            ks = [k for k, a in enumerate(an) if grp[a] == g]
            lo = min(axs[k].get_ylim()[0] for k in ks)
            hi = max(axs[k].get_ylim()[1] for k in ks)
            for k in ks:
                axs[k].set_ylim(lo, hi)
    for ax in axs:
        lo, hi = ax.get_ylim()
        ax.yaxis.set_major_locator(mt.MultipleLocator(20 if hi - lo > 30 else 10))
    for ax in axs[-2:]:
        ax.set_xlabel('sessions (thirds)', fontsize=6.5, labelpad=5)
    fig.text(0.085 / W, (eB + (H - eB - eT) / 2) / H, '$\Delta$ contralesional-cue first-lick angle (deg)',
             rotation=90, ha='center', va='center', fontsize=6.5)
    for x in ('pdf', 'svg', 'png'):
        fig.savefig(f'{stem}.{x}', dpi=600 if x == 'png' else None)
    plt.close(fig)


def main(t1: str, out: str, stem: str):
    o = Path(out)
    if o.exists() and any(o.iterdir()):
        sys.exit(f'refusing to write into non-empty {o}')
    for x in ('pdf', 'svg', 'png'):
        if Path(f'{stem}.{x}').exists():
            sys.exit(f'refusing to overwrite {stem}.{x}')
    o.mkdir(parents=True, exist_ok=True)
    S = load(t1)
    S.to_csv(o / 'thirds_sessions_twotone.csv', index=False)
    summ, pa = [], []
    for g, grades in GROUPS:
        a, b = TC.analyze(S[S.grade.isin(grades)], g, boot, NUM)
        summ.append(a)
        pa.append(b)
    R, A = pd.concat(summ, ignore_index=True), pd.concat(pa, ignore_index=True)
    R.to_csv(o / 'thirds_boot_lmm_twotone.csv', index=False)
    A.to_csv(o / 'thirds_per_animal_twotone.csv', index=False)
    TC.pairs(S, None).to_csv(o / 'pairs_anygap_twotone.csv', index=False)
    G = pd.concat([TC.gap_table(S[S.grade.isin(gr)], g) for g, gr in GROUPS], ignore_index=True)
    G.to_csv(o / 'pair_gaps_twotone.csv', index=False)
    print(G.pivot_table(index=['group', 'post'], columns='gap', values='n_pairs', fill_value=0))
    w = S[S.post == 1].groupby('animal').day.agg(['min', 'max', 'size'])
    w.to_csv(o / 'post_window_per_animal_twotone.csv')
    print(w)
    with open(o / 'tables_twotone.md', 'w', encoding='utf-8') as f:
        for g, _ in GROUPS:
            f.write(f'\n### {g}\n\n| Quantity | Pre | Post | Stroke effect, bootstrap [95% CI] | Mixed model [95% CI], p '
                    '| Per animal: pre -> post (effect) | Same sign |\n|---|---|---|---|---|---|---|\n')
            for _, r in R[R.group == g].iterrows():
                f.write(TC.fmt_row(r) + '\n')
    print((o / 'tables_twotone.md').read_text(encoding='utf-8'))
    render(S, stem)


def render_variant(sessions_csv: str, stem: str, yshare: str):
    """Re-render S8E from the written thirds_sessions_twotone.csv with another y-scale rule (refuses to overwrite)."""
    for x in ('pdf', 'svg', 'png'):
        if Path(f'{stem}.{x}').exists():
            sys.exit(f'refusing to overwrite {stem}.{x}')
    render(pd.read_csv(sessions_csv), stem, yshare)


if __name__ == '__main__':
    np.seterr(all='ignore')
    if sys.argv[1] == '--render-variant':
        render_variant(*sys.argv[2:5])
    else:
        main(*sys.argv[1:4])
