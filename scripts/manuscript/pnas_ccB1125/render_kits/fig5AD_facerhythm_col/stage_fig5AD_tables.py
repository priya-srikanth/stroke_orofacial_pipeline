"""Stage the plot-ready inputs of Fig 5A-D (CC-B, 2026-11-25; render kit for CC-A).

Converts the panel-B map cache (a pickle of pandas / numpy objects, which needs the pipeline's pandas version) into
one CSV that render_fig5AD.py reads, with the ring override already applied as fr_fig5_col_v26b_ptsv2.py applies it
(rings = sig_cluster of the per-point permutation table, align 'lick', position 'far_R'):

  fig5B_far_contra_lick_maps.csv   epoch, point, log2_ratio, ring   (one row per mesh point and epoch)

The other inputs (master.npz, master_face.png, fr_pre_timecourses_abs npz, session_maps_scaled_lick_points.csv) are
copied unchanged; the renderer reads them as the live script did.

Usage: stage_fig5AD_tables.py <aligned_maps_cache_point.pkl> <aligned_maps_perm_points.csv> <out_dir>
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

EPS = ['acute', 'subacute', 'chronic']


def main(pkl, perm, out):
    os.makedirs(out, exist_ok=True)
    MAPS, MASK = pickle.load(open(pkl, 'rb'))[2:4]
    PP = pd.read_csv(perm)
    PP = PP[(PP['align'] == 'lick') & (PP['position'] == 'far_R')]
    for e, g in PP.groupby('epoch'):
        g = g.sort_values('point')
        assert len(g) == len(MASK[('lick', 'far_R', e)]) and (g.point.to_numpy() == np.arange(len(g))).all()
        MASK[('lick', 'far_R', e)] = g.sig_cluster.astype(bool).to_numpy()
    rows = []
    for e in EPS:
        v = np.asarray(MAPS[('lick', 'far_R', e)], dtype=np.float64); mk = np.asarray(MASK[('lick', 'far_R', e)], dtype=bool)
        rows.append(pd.DataFrame(dict(epoch=e, point=np.arange(len(v)), log2_ratio=v, ring=mk)))
    T = pd.concat(rows, ignore_index=True)
    T.to_csv(os.path.join(out, 'fig5B_far_contra_lick_maps.csv'), index=False, float_format='%.17g')
    print('wrote', len(T), 'rows;', {e: int(T[T.epoch == e].ring.sum()) for e in EPS}, 'ringed points')


if __name__ == '__main__':
    main(*sys.argv[1:4])
