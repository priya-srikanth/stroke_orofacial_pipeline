"""S7 I-J (first-lick xy protrusion distance): the same within-animal cluster test as every other trajectory panel
(stroke_orofacial_pipeline compute_trajectory_cluster_permutation_c2_aligned: per-bin Welch t, two-sided p < .05 bin
threshold, labels shuffled within animal, 5000 permutations, seed 42, BH within the signal), run on the cached per-trial
xy substrate (v3_xy_dist/_xy_session_cache_ps47d5/xy_trial_bin_substrate_first.parquet; PS47 chronic from day 5), signal
xy_dist (delta variant). Until now no cluster test had been run for xy distance (S7 legend). Refuses to overwrite.
Usage: PYTHONPATH=src:. python scripts/manuscript/xy_cluster_c2aligned.py <v3_xy_dist dir>"""
import sys
from pathlib import Path
import pandas as pd
from stroke_orofacial.stats.trajectory_within_animal_cluster import compute_trajectory_cluster_permutation_c2_aligned
from scripts.phase_9_1_q13.emit_cohort import PHENOTYPE_ORDER_3TIER

V = Path(sys.argv[1])
out = V / 'trajectory_cluster_permutation_c2aligned_bh_fdr_ps47d5.csv'
if out.exists():
    sys.exit(f'refusing to overwrite {out}')
d = pd.read_parquet(V / '_xy_session_cache_ps47d5' / 'xy_trial_bin_substrate_first.parquet')
res = compute_trajectory_cluster_permutation_c2_aligned(d, phenotype_order=PHENOTYPE_ORDER_3TIER, signals=('xy_dist',),
                                                         n_permutations=5000, rng_seed=42)
res.to_csv(out, index=False)
print('wrote', out, len(res), 'rows;', int(res['reject'].fillna(False).sum()), 'significant clusters')
