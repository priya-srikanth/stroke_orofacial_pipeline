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
GROUPS = [('mild', ['mild']), ('moderate', ['moderate']), ('severe', ['severe']),
          ('mild+moderate', ['mild', 'moderate'])]


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


def render(S: pd.DataFrame, stem: str):
    """S8E block at its size in S8_aim_recovery_v28_compact_4in (3.17 x 1.34 in; 2 x 2: moderate, severe), fonts as
    the compact page (Arial 6.5 pt ticks / labels, 7 pt titles); ink kept inside the page."""
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
    W, H = 3.17, 1.34
    eL, eR, eB, eT, eWS, eHS = 0.47, 0.04, 0.17, 0.13, 0.28, 0.25
    aw, ah = (W - eL - eR - eWS) / 2, (H - eB - eT - eHS) / 2
    fig = plt.figure(figsize=(W, H))
    an = sorted(S[S.grade.isin(['moderate', 'severe'])].animal.unique())
    axs = []
    for k, a in enumerate(an):
        r, c = divmod(k, 2)
        ax = fig.add_axes([(eL + c * (aw + eWS)) / W, (H - eT - (r + 1) * ah - r * eHS) / H, aw / W, ah / H])
        d = S[S.animal == a]
        gr = d.grade.iloc[0]
        TC.draw_animal(ax, d, lambda _r, g=gr: COLORS[g], MARKERS[gr], 2.2, pre_label_fs=6.0)
        ax.set_title(f'{NUM[a]} ({gr})', fontsize=7, pad=2)
        ax.yaxis.set_major_locator(mt.MultipleLocator(20))
        axs.append(ax)
    for ax in axs[2:]:
        ax.set_xlabel('sessions (thirds)', fontsize=6.5, labelpad=5)
    fig.text(0.085 / W, (H - eT - ah - eHS / 2) / H, '$\\Delta$ contralesional-cue\nfirst-lick angle (deg)',
             rotation=90, ha='center', va='center', fontsize=6.5, multialignment='center')
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
    for nm, gap in (('pairs_gap2_twotone.csv', TC.MAX_GAP), ('pairs_gap1_twotone.csv', 1)):
        TC.pairs(S, gap).to_csv(o / nm, index=False)
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


if __name__ == '__main__':
    np.seterr(all='ignore')
    main(*sys.argv[1:4])
