"""Old (ps47d5) vs new (ps47d5_inmouth0) significant trajectory clusters, both lick sets (caption review item 1).
A significant new cluster overlapping no significant old cluster of the same cell = GAINED; the reverse = LOST;
overlapping with different bins = CHANGED; identical = same. Writes <out>/item1_cluster_changes.csv.
Usage: python scripts/manuscript/c1_inmouth0_cluster_compare.py <out_dir>"""
import sys
from pathlib import Path
import pandas as pd

PP = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats/results/phenotype_pooled")
CELL = ["signal", "recovery_phenotype", "side", "post_epoch"]
rows = []
for ls, d in (("first", "phase_aligned_trajectories"), ("all", "phase_aligned_trajectories_all_licks")):
    v = PP / d / "3_tier/v3"
    o = pd.read_csv(v / "trajectory_cluster_permutation_c2aligned_bh_fdr_ps47d5.csv")
    n = pd.read_csv(v / "trajectory_cluster_permutation_c2aligned_bh_fdr_ps47d5_inmouth0.csv")
    o, n = o[o.reject == True], n[n.reject == True]  # noqa: E712
    for key in sorted(set(map(tuple, o[CELL].values)) | set(map(tuple, n[CELL].values))):
        oc = o[(o[CELL] == key).all(axis=1)]
        nc = n[(n[CELL] == key).all(axis=1)]
        used = set()
        for _, r in oc.iterrows():
            ov = nc[(nc.start_bin <= r.end_bin) & (nc.end_bin >= r.start_bin)]
            if ov.empty:
                rows.append(dict(zip(CELL, key), lick_set=ls, old=f"{r.start_bin}-{r.end_bin}", new="", old_p_adj=r.p_adj,
                                 new_p_adj=None, change="LOST"))
            for _, q in ov.iterrows():
                used.add(q.name)
                same = (q.start_bin, q.end_bin) == (r.start_bin, r.end_bin)
                rows.append(dict(zip(CELL, key), lick_set=ls, old=f"{r.start_bin}-{r.end_bin}", new=f"{q.start_bin}-{q.end_bin}",
                                 old_p_adj=r.p_adj, new_p_adj=q.p_adj, change="same" if same else "CHANGED"))
        for i, q in nc.iterrows():
            if i not in used:
                rows.append(dict(zip(CELL, key), lick_set=ls, old="", new=f"{q.start_bin}-{q.end_bin}", old_p_adj=None,
                                 new_p_adj=q.p_adj, change="GAINED"))
R = pd.DataFrame(rows)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
R.to_csv(out / "item1_cluster_changes.csv", index=False)
pd.set_option("display.width", 220)
print(R.groupby(["lick_set", "signal", "change"]).size().to_string())
print(R[R.change != "same"].to_string())
