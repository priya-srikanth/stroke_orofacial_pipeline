"""Old vs new star table for caption review items 19-20 (CC-B, 2026-11-23). Reads the ps47d5 sheets and the
_sessmean sheet; writes <out>/items19_20_star_changes.csv (every merged-family cell) and prints changed cells.
Usage: python scripts/manuscript/c1_sessmean_compare.py <out_dir>"""
import sys
from pathlib import Path
import pandas as pd
from stroke_orofacial.paths import PathResolver

r3 = PathResolver().pipeline_outputs(subdir="stats") / "results/phenotype_pooled/3_tier"
old = pd.concat([pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv").query("family == 'scalar'"),
                 pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv").assign(family="xy_own")])
new = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv").query("family == 'scalar'")
MAP = {"tongue_sessmean_xy_peak": "tongue_median_xy_peak_per_trial", "tongue_sessmean_vxy_peak": "tongue_median_vxy_peak_per_trial"}
new = new.assign(old_endpoint=new.endpoint.map(MAP).fillna(new.endpoint))
k = ["recovery_phenotype", "side", "post_epoch"]
cols = ["endpoint", *k, "n_pre_sessions", "n_post_sessions", "nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p",
        "mwu_session_p_fdr", "headline_and_bootstrap_sig"]
m = new[cols + ["old_endpoint"]].merge(old[cols].rename(columns={"endpoint": "old_endpoint"}), on=["old_endpoint", *k],
                                       how="outer", suffixes=("_new", "_old"))
m["change"] = "same"
m.loc[m.headline_and_bootstrap_sig_new.eq(True) & ~m.headline_and_bootstrap_sig_old.eq(True), "change"] = "GAINED"
m.loc[~m.headline_and_bootstrap_sig_new.eq(True) & m.headline_and_bootstrap_sig_old.eq(True), "change"] = "LOST"
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
m.to_csv(out / "items19_20_star_changes.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(m.change.value_counts())
show = ["old_endpoint", *k, "nb_effect_old", "nb_effect_new", "mwu_session_p_fdr_old", "mwu_session_p_fdr_new", "change"]
print(m[m.change != "same"][show].to_string())
print(m[m.old_endpoint.isin(list(MAP.values()) + ["tongue_lick1_xy_peak"])][show + ["nb_ci_lo_new", "nb_ci_hi_new"]].round(4).to_string())
