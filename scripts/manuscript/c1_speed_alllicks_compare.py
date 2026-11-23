"""Fig 2E: capped (licks 1-5, session mean) vs all-lick (session mean) cells, and q movement of the other cells of the
502-cell family (CC-B, 2026-11-23). Writes <out>/fig2e_alllicks_vs_capped.csv and prints a markdown table.
Usage: python scripts/manuscript/c1_speed_alllicks_compare.py <out_dir>"""
import sys
from pathlib import Path
import pandas as pd
from stroke_orofacial.paths import PathResolver

r3 = PathResolver().pipeline_outputs(subdir="stats") / "results/phenotype_pooled/3_tier"
a = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_sessmean.csv").query("family == 'scalar'")
b = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_sessmean.csv").query("family == 'scalar'")
k = ["recovery_phenotype", "side", "post_epoch"]
cols = k + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "headline_and_bootstrap_sig"]
m = a[a.endpoint == "tongue_sessmean_vxy_peak"][cols].merge(
    b[b.endpoint == "tongue_alllicks_sessmean_vxy_peak"][cols], on=k, suffixes=("_capped", "_all"))
m["change"] = ""
m.loc[m.headline_and_bootstrap_sig_all & ~m.headline_and_bootstrap_sig_capped, "change"] = "GAINED"
m.loc[~m.headline_and_bootstrap_sig_all & m.headline_and_bootstrap_sig_capped, "change"] = "LOST"
out = Path(sys.argv[1]); m.to_csv(out / "fig2e_alllicks_vs_capped.csv", index=False)
S = {"L": "ipsilesional", "R": "contralesional"}; E = {"acute": "acute", "sub_acute": "subacute", "chronic": "chronic"}
f = lambda x: "" if pd.isna(x) else f"{x:.0f}"
print("| Grade | Cue | Epoch | Licks 1-5, mean [95% CI] | q | star | All licks, mean [95% CI] | q | star | Change |")
print("|---|---|---|---|---|---|---|---|---|---|")
for _, r in m.sort_values(k).iterrows():
    ci = lambda s: f"{f(r['nb_effect_' + s])} [{f(r['nb_ci_lo_' + s])}, {f(r['nb_ci_hi_' + s])}]".replace(" [, ]", "")
    print(f"| {r.recovery_phenotype} | {S[r.side]} | {E[r.post_epoch]} | {ci('capped')} | {r.mwu_session_p_fdr_capped:.4f} | "
          f"{'**' if r.headline_and_bootstrap_sig_capped else ''} | {ci('all')} | {r.mwu_session_p_fdr_all:.4f} | "
          f"{'**' if r.headline_and_bootstrap_sig_all else ''} | {r.change} |")
o = a[a.endpoint != "tongue_sessmean_vxy_peak"].merge(b[b.endpoint != "tongue_alllicks_sessmean_vxy_peak"],
                                                       on=["endpoint"] + k, suffixes=("_a", "_b"))
dq = (o.mwu_session_p_fdr_a - o.mwu_session_p_fdr_b).abs()
print(f"\nother {len(o)} cells: max |dq| {dq.max():.5f}; star changes "
      f"{int((o.headline_and_bootstrap_sig_a != o.headline_and_bootstrap_sig_b).sum())}")
