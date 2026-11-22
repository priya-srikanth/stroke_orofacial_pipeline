"""Compare two-tone CSM tables between runs (2026-11-22 peaks-v2 fix; Priya: re-run the two-tone CSM check with the
fixed peak finder and confirm the old numbers with a control run).

    python c1_csm_fix_compare.py <cited_out> <control_out> <fixed_out> <dest>

<cited_out>  : the cited run (review/c1_recovery_mechanics_2026-11-21_r2: old peaks, cited 5.5 % vs 5.1 %)
<control_out>: the current code with --peaks-version 1 (should reproduce <cited_out>)
<fixed_out>  : the current code with --peaks-version 2

Writes to <dest> (refuses to overwrite): cmp_control_lick_prominences.csv (per-lick equality of pk_sp / sur_*_sp with
the cited pickle), cmp_control_<table>.csv and cmp_fix_<table>.csv for csm_gate / tests_csm (flags: star flips,
shift > 0.02, n changes), and cmp_summary.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ['family', 'measure', 'grade', 'side', 'post_epoch']
TOL = 0.02     # rates / fractions


def cmp_tests(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Join two run_family tables on their cell key and flag star flips, effect shifts > TOL and n changes."""
    m = a.merge(b, on=KEY, how='outer', suffixes=('_a', '_b'), indicator='src')
    fl = []
    for r in m.itertuples():
        f = []
        if r.src != 'both':
            f.append(f'ONLY_{r.src}')
        else:
            if bool(r.star_a) != bool(r.star_b):
                f.append('STAR_LOST' if r.star_a else 'STAR_GAINED')
            if np.isfinite(r.nb_effect_a) != np.isfinite(r.nb_effect_b) or (
                    np.isfinite(r.nb_effect_a) and abs(r.nb_effect_a - r.nb_effect_b) > TOL):
                f.append('SHIFT')
            if (r.n_pre_sessions_a, r.n_post_sessions_a) != (r.n_pre_sessions_b, r.n_post_sessions_b):
                f.append('N')
        fl.append(';'.join(f))
    m['flags'] = fl
    keep = KEY + [c for c in m if c.startswith(('nb_effect', 'nb_ci_lo', 'nb_ci_hi', 'q_bh', 'star', 'n_pre',
                                                     'n_post'))] + ['flags']
    return m[keep]


def cmp_gate(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side gate rows (real, false, diff, CI, animal counts)."""
    return a.merge(b, on='test', how='outer', suffixes=('_a', '_b'))


def main(cited: Path, control: Path, fixed: Path, dest: Path) -> None:
    """See the module docstring."""
    if dest.exists() and any(dest.glob('cmp_*')):
        sys.exit(f'refusing to overwrite cmp_* in {dest}')
    dest.mkdir(parents=True, exist_ok=True)
    lines = []
    # 1. per-lick prominences, control vs cited pickle
    key = ['label', 'trial', 'lick_idx']
    cols = ['pk_sp', 'sur_sm_sp', 'sur_nz_sp']
    A = pd.read_pickle(cited / 'data/cued_licks.pkl')[key + cols]
    B = pd.read_pickle(control / 'data/cued_licks.pkl')[key + cols]
    M = A.merge(B, on=key, how='outer', suffixes=('_a', '_b'), indicator='src')
    rows = [{'what': 'licks', 'cited': int((M.src != 'right_only').sum()),
             'control': int((M.src != 'left_only').sum()), 'both': int((M.src == 'both').sum())}]
    both = M[M.src == 'both']
    for c in cols:
        x, y = both[f'{c}_a'], both[f'{c}_b']
        same = [(isinstance(p, float) and isinstance(q, float)) or p == q for p, q in zip(x, y)]
        rows.append({'what': c, 'both': len(both), 'identical': int(np.sum(same))})
    P = pd.DataFrame(rows)
    P.to_csv(dest / 'cmp_control_lick_prominences.csv', index=False)
    lines.append('control vs cited, per-lick prominences:\n' + P.to_string(index=False))
    # 2. tables
    for tag, other in (('control', control), ('fix', fixed)):
        for t in ('tests_csm.csv',):
            C = cmp_tests(pd.read_csv(cited / 'tables' / t), pd.read_csv(other / 'tables' / t))
            C.to_csv(dest / f'cmp_{tag}_{t}', index=False)
            fl = C['flags'][C['flags'] != '']
            lines.append(f'{tag} {t}: {len(C)} cells, {len(fl)} flagged; '
                         f'star flips {int(fl.str.contains("STAR").sum())}')
        G = cmp_gate(pd.read_csv(cited / 'tables/csm_gate.csv'), pd.read_csv(other / 'tables/csm_gate.csv'))
        G.to_csv(dest / f'cmp_{tag}_csm_gate.csv', index=False)
        lines.append(f'{tag} csm_gate:\n' + G.round(4).to_string(index=False))
    (dest / 'cmp_summary.txt').write_text('\n\n'.join(lines) + '\n')
    print('\n\n'.join(lines))


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*map(Path, sys.argv[1:]))
