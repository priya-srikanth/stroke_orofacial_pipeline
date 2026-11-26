"""Stage the plot-ready tables of Fig 3D (CC-B, 2026-11-25; render kit for CC-A).

Reproduces, with pandas only, the cohort-2 part of manuscript_code/figures/trial_class_distribution.py (the class
filter, the last-lick cut, the epoch mapping and the per-animal fractions), as fig3_def_row_v28.py ran it on 11-23 for
FigureS11_trial_classes_c2_4cam_v28b_jaw3dmouth_new_wp_ccB1123. Writes three tables that render_fig3D.py reads:

  fig3D_per_animal_fractions.csv  position, epoch, animal, complete, incomplete, jaw_only, no_resp
                                  (each animal's class fractions over its trials of that position x epoch;
                                  rows in the order the renderer uses for the whisker SEM)
  fig3D_bars.csv                  position, epoch, n_animals, complete, incomplete, jaw_only, no_resp, star
                                  (bar = mean over animals of the per-animal fractions; star from the
                                  distribution test, '**' where star_dist == 1)
  fig3D_animal_markers.csv        position, epoch, animal, complete
                                  (the open per-animal markers: epoch_complete of the per-animal test table, plus
                                  pre_complete for the pre bars)

Usage: stage_fig3D_tables.py <s1_trial_classes_cue_stop.csv.gz> <distribution_test.csv> <per_animal.csv> <out_dir>
"""
import datetime as dt
import os
import sys

import pandas as pd

CLS = ['complete', 'incomplete', 'jaw_only', 'no_resp']
EPS = ['pre', 'acute', 'subacute', 'chronic']
STROKE = {'PS92': '0817', 'PS93': '0817', 'PS94': '0816', 'PS95': '0816'}
C2EP = {'PS92': (5, 7, 11), 'PS93': (4, 5, 11), 'PS94': (7, 9, 25), 'PS95': (1, 2, 15)}   # (acute last, subacute first, chronic first)
EXCL = {'PS92': {'0817'}, 'PS93': {'0817'}}


def day(a, m):
    return (dt.date(2026, int(m[:2]), int(m[2:])) - dt.date(2026, int(STROKE[a][:2]), int(STROKE[a][2:]))).days


def ep2(a, m):
    d = day(a, m); al, sf, cf = C2EP[a]
    if d <= 0: return 'pre'
    if d <= al: return 'acute'
    if d < sf: return None
    return 'subacute' if d < cf else 'chronic'


def load_classes(path):
    """trial_class_distribution.py, cohort-2 block, unchanged."""
    c2 = pd.read_csv(path)
    c2 = c2[c2.cls.isin(['contact', 'incomplete', 'jaw_only', 'no_response']) & (c2.position != 'unknown')].copy()
    last = c2[c2.cls.isin(['contact', 'incomplete'])].groupby('label').cue_idx.max()
    c2 = c2[c2.cue_idx <= c2.label.map(last)].copy()
    c2['animal'] = c2.label.str[:4]; c2['mmdd'] = c2.label.str[5:9]
    c2 = c2[~c2.apply(lambda r: r.mmdd in EXCL.get(r.animal, set()), axis=1) & (c2.mmdd >= '0806')]
    c2['epoch'] = [ep2(a, m) for a, m in zip(c2.animal, c2.mmdd)]; c2 = c2[c2.epoch.notna()]
    c2['cls'] = c2.cls.replace({'contact': 'complete', 'no_response': 'no_resp'})
    return c2


def frac(df, keys):
    """mean over animals of per-animal class fractions; {key: (mean fractions, n animals, per-animal frame)}"""
    out = {}
    for k, g in df.groupby(keys):
        pa = g.groupby('animal').cls.value_counts(normalize=True).unstack().reindex(columns=CLS).fillna(0)
        out[k] = (pa.mean(axis=0).values, len(pa), pa)
    return out


def main(cls_path, dist_path, pa_path, out):
    os.makedirs(out, exist_ok=True)
    c2 = load_classes(cls_path)
    F2 = frac(c2, ['position', 'epoch'])
    D = pd.read_csv(dist_path)
    STAR2 = {(r.position, r.epoch): ('**' if int(r.star_dist) == 1 else '') for r in D.itertuples()}
    rows_pa, rows_bar = [], []
    for (p, e), (f, n, pa) in F2.items():
        for an, r in pa.iterrows():
            rows_pa.append(dict(position=p, epoch=e, animal=an, **{c: r[c] for c in CLS}))
        rows_bar.append(dict(position=p, epoch=e, n_animals=n, **{c: f[i] for i, c in enumerate(CLS)}, star=STAR2.get((p, e), '')))
    pd.DataFrame(rows_pa).to_csv(os.path.join(out, 'fig3D_per_animal_fractions.csv'), index=False, float_format='%.17g')
    pd.DataFrame(rows_bar).to_csv(os.path.join(out, 'fig3D_bars.csv'), index=False, float_format='%.17g')
    # open per-animal markers (trial_class_distribution._pa): epoch_complete per row, pre_complete once per animal
    P = pd.read_csv(pa_path); mk = {}
    for r in P.itertuples():
        mk.setdefault((r.position, r.epoch), []).append((r.animal, r.epoch_complete))
        pre = mk.setdefault((r.position, 'pre'), [])
        if r.animal not in [a for a, _ in pre]:
            pre.append((r.animal, r.pre_complete))
    rows = [dict(position=p, epoch=e, animal=a, complete=v) for (p, e), L in mk.items() for a, v in L]
    pd.DataFrame(rows).to_csv(os.path.join(out, 'fig3D_animal_markers.csv'), index=False, float_format='%.17g')
    print('wrote', out, len(rows_pa), 'per-animal rows,', len(rows_bar), 'bars,', len(rows), 'markers')


if __name__ == '__main__':
    main(*sys.argv[1:5])
