"""Stage the plot-ready tables of the six-position scalar panels drawn by c2_matched.endpoint with the v26 star band
(CC-B, 2026-11-25; render kit for CC-A). Covers S11A (C2_reach_first) and S11B (C2_speed_first), and the same
chain's Fig 4B (C2_speed_all) and Fig 4C (C2_reach_all) for reference.

For each panel it writes, from the FINAL wide session table and the FINAL 180-cell family:
  <stem>_sessions.csv   one row per session x spout cell with >= 20 licks (first licks for the first-lick metrics):
                        animal, date, epoch, pos (lesion-signed), value, chg = value minus the animal's mean over its
                        pre sessions at that spout. Row order = the drawing order (sets the per-session jitter).
  <stem>_stats.csv      the 18 family rows of the metric: boot_change, boot_lo, boot_hi (nested bootstrap, 4,000 draws),
                        q_family, star_aligned (1 = '**')
  <stem>_spec.json      y label, metric, n column
The data step is c2_scalar_aligned_render.lick3d_changes (unchanged), as scripts/sixpos_final_render_1123.py ran it.

Usage: stage_c2_scalar_tables.py <c2_lick3d_session_summary_FINAL_ccB1123.csv> <c2_scalar_family_FINAL_ccB1123_boot4000_cam3on.csv> <out_dir>
"""
import json
import os
import sys

import pandas as pd

POS = ['close_ipsi', 'close_mid', 'close_contra', 'far_ipsi', 'far_mid', 'far_contra']
POS3 = dict(zip(['close_L', 'close_center', 'close_R', 'far_L', 'far_center', 'far_R'], POS))
#: metric -> (stem, n column, y label, panel)
PANELS = {
    'speed_all': ('C2_speed_all', 'n_speed_all', 'peak speed,\nall licks (Δ mm/s)', 'Fig 4B'),
    'reach_all': ('C2_reach_all', 'n_reach_all', '3-D reach,\nall licks (Δ mm)', 'Fig 4C'),
    'reach_first': ('C2_reach_first', 'n_reach_first', 'first-lick 3-D\nreach (Δ mm)', 'S11A'),
    'speed_first': ('C2_speed_first', 'n_speed_first', 'first-lick\npeak speed (Δ mm/s)', 'S11B'),
}


def lick3d_changes(sx, col, ncol):
    """= c2_scalar_aligned_render.lick3d_changes (session x spout cells with >= 20 licks; change vs own pre mean)."""
    d = sx[sx[ncol] >= 20].copy(); d['v'] = d[col]
    b = d[d.epoch == 'pre'].groupby(['animal', 'pos']).v.mean()
    d['chg'] = d.v - [b.get((a, p), None) for a, p in zip(d.animal, d.pos)]
    return d.dropna(subset=['chg'])


def main(wide, family, out):
    os.makedirs(out, exist_ok=True)
    W = pd.read_csv(wide); W['pos'] = W.position.map(POS3)
    F = pd.read_csv(family)
    for metric, (stem, ncol, ylab, panel) in PANELS.items():
        dd = lick3d_changes(W, metric, ncol)
        fam = F[F.metric == metric].copy()
        n = dd[dd.epoch != 'pre'].groupby(['pos', 'epoch']).size()
        bad = [(k, int(n.get(k, 0)), int(v)) for k, v in fam.set_index(['pos', 'epoch']).n_sessions.items() if int(n.get(k, 0)) != int(v)]
        assert not bad, (stem, bad)
        pdir = os.path.join(out, stem); os.makedirs(pdir, exist_ok=True)
        dd[['animal', 'mouse', 'date', 'session', 'epoch', 'position', 'pos', ncol, 'v', 'chg']].rename(columns={'v': 'value'}) \
            .to_csv(os.path.join(pdir, f'{stem}_sessions.csv'), index=False, float_format='%.17g')
        fam.to_csv(os.path.join(pdir, f'{stem}_stats.csv'), index=False, float_format='%.17g')
        with open(os.path.join(pdir, f'{stem}_spec.json'), 'w', encoding='utf-8') as fh:
            json.dump({'metric': metric, 'n_column': ncol, 'ylabel': ylab, 'panel': panel, 'stars': int(fam.star_aligned.sum())}, fh, ensure_ascii=False, indent=1)
        print(stem, panel, len(dd), 'session rows,', int(fam.star_aligned.sum()), 'stars')


if __name__ == '__main__':
    main(*sys.argv[1:4])
