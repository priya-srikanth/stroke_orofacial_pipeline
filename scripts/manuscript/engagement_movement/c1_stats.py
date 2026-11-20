"""Cohort-1 aligned statistics for the two-tone review measures (shared by the c1_*.py scripts).

Rule (cohort-1 scalar family, --test-set c2_aligned, Priya 2026-11-19): per-session value -> change from the animal's
OWN pre-stroke mean (per animal x cue side, or per animal for cross-cue measures) -> per grade x side x post epoch:
session Mann-Whitney U (post vs pre deltas) + nested animals -> sessions bootstrap CI
(`stroke_orofacial.stats.pooled_endpoint_suite.compute_endpoint_cell_suite(test_set="c2_aligned")`, 4,000 draws,
95 % percentile); BH-FDR over the rows of ONE family (`multiple_comparisons.apply_correction_to_results_df`);
star = q < 0.05 AND the bootstrap CI excludes 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GRADES = ('mild', 'moderate', 'severe')
POST = ('acute', 'sub_acute', 'chronic')


def deltas(df: pd.DataFrame, measure_col='measure', side_col='side', value_col='value') -> pd.DataFrame:
    """Add value_norm = value - mean of the animal's own pre sessions (per measure x side)."""
    b = (df[df.epoch == 'pre'].groupby(['animal', side_col, measure_col])[value_col].mean().rename('pre_mean'))
    out = df.merge(b.reset_index(), on=['animal', side_col, measure_col], how='left')
    out['value_norm'] = out[value_col] - out.pre_mean
    return out


def run_family(df: pd.DataFrame, family: str, measure_col='measure', side_col='side', grades=GRADES,
               value_col='value') -> pd.DataFrame:
    """df: one row per session x side x measure with animal, grade, epoch, value. Returns one row per
    measure x grade x side x post epoch with effect, CI, MWU p, BH q (this family), star."""
    from stroke_orofacial.stats import pooled_endpoint_suite as SUITE
    from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df
    d = deltas(df.dropna(subset=[value_col]), measure_col, side_col, value_col)
    rows = []
    for (m, s), g in d.groupby([measure_col, side_col], sort=False):
        for gr in grades:
            gg = g[g.grade == gr] if gr != 'all' else g
            for ep in POST:
                if ep not in set(gg.epoch):
                    continue
                r = SUITE.compute_endpoint_cell_suite(gg, post_epoch=ep, value_col='value_norm', epoch_col='epoch',
                                                      animal_col='animal', test_set='c2_aligned')
                an = gg[gg.epoch.isin(('pre', ep))]
                per_an = an.groupby(['animal', 'epoch']).value_norm.mean().unstack()
                n_down = int((per_an.get(ep, pd.Series(dtype=float)) < 0).sum()) if ep in per_an else 0
                r.update({'family': family, 'measure': m, 'side': s, 'grade': gr,
                          'session_mean_delta': float(gg[gg.epoch == ep].value_norm.mean()),
                          'pre_level': float(gg[gg.epoch == 'pre'][value_col].mean()),
                          'n_animals_down': n_down})
                rows.append(r)
    R = pd.DataFrame(rows)
    if R.empty:
        return R
    R = R.rename(columns={'mwu_session_p': 'p_value'})
    R = apply_correction_to_results_df(R, group_cols=('family',))
    R = R.rename(columns={'p_value': 'mwu_p', 'p_adj': 'q_bh'}).drop(columns=['reject'], errors='ignore')
    R['star'] = (R.q_bh < 0.05) & R.nb_excludes_zero.astype(bool)
    cols = ['family', 'measure', 'grade', 'side', 'post_epoch', 'nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'mwu_p', 'q_bh',
            'star', 'nb_n_animals', 'n_pre_sessions', 'n_post_sessions', 'n_animals_down', 'session_mean_delta',
            'pre_level']
    return R[cols + [c for c in R.columns if c not in cols]]
