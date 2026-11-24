"""FINAL2 (_FINALall2_ccB1123) vs FINAL (_FINALall_ccB1123) vs LIVE, every scalar cell (CC-B, 2026-11-23).
Writes (new only) <out>/tables/final2_vs_final_cells_FINAL2_ccB1123.csv (cells in both + dropped + added, with q and
mark in each) and final2_counts_FINAL2_ccB1123.csv (stars / daggers per drawn panel: live, FINAL, FINAL2).
Usage: python scripts/manuscript/c1_final2_compare.py <FINAL_twotone_dir>"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c1_final_compare as FC  # noqa: E402

R3 = FC.R3
K = ["endpoint", "recovery_phenotype", "side", "post_epoch"]


def rd(n):
    d = pd.read_csv(R3 / f"{n}.csv", encoding="utf-8", keep_default_na=False, na_values=[""])
    d["mark"] = d["mark"].fillna("")
    return d


def main():
    out = Path(sys.argv[1]) / "tables"
    f1 = out / "final2_vs_final_cells_FINAL2_ccB1123.csv"
    f2 = out / "final2_counts_FINAL2_ccB1123.csv"
    for f in (f1, f2):
        if f.exists():
            sys.exit(f"refusing to overwrite {f}")
    a = rd("pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123")
    b = rd("pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123")
    a, b = a[a.family == "scalar"], b[b.family == "scalar"]
    c = ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "mark"]
    m = a[K + c].merge(b[K + c], on=K, how="outer", suffixes=("_final", "_final2"), indicator=True)
    m["status"] = m._merge.map({"both": "kept", "left_only": "DROPPED", "right_only": "ADDED"})
    m["mark_change"] = (m.status == "kept") & (m.mark_final.fillna("") != m.mark_final2.fillna(""))
    m.drop(columns="_merge").to_csv(f1, index=False, encoding="utf-8")
    kept = m[m.status == "kept"]
    print("kept", len(kept), "max |dq|", float((kept.mwu_session_p_fdr_final - kept.mwu_session_p_fdr_final2).abs().max()),
          "mark changes", int(kept.mark_change.sum()), "| dropped", int((m.status == "DROPPED").sum()), "added",
          int((m.status == "ADDED").sum()))
    live = pd.concat([pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv"),
                      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")], ignore_index=True)
    full_a = rd("pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123")
    full_b = rd("pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123")
    rows = []
    for panel, lep, fep, fam in FC.PANELS + [("S6 licks per responded trial (new)", None,
                                              "tongue_n_licks_per_responded_trial", "scalar")]:
        def cnt(d, ep, live_=False):
            if ep is None:
                return np.nan, np.nan
            x = d[(d.endpoint == ep) & (d.family == fam)]
            if live_:
                return int(x.headline_and_bootstrap_sig.sum()), 0
            return int((x.mark == "**").sum()), int((x.mark == FC.DAGGER).sum())
        ls, _ = cnt(live, lep, True)
        s1, d1 = cnt(full_a, fep)
        s2, d2 = cnt(full_b, fep)
        rows.append(dict(panel=panel, stars_live=ls, stars_final=s1, daggers_final=d1, stars_final2=s2,
                         daggers_final2=d2))
    t = pd.DataFrame(rows)
    t.to_csv(f2, index=False)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
