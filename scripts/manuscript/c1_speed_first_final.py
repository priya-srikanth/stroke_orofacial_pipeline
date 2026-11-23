"""Item 26 (two-tone half) and the final two-tone scalar family (CC-B, 2026-11-23 late).

First-lick peak tongue speed per session: the first v7-kept lick of each trial in the [70, 3000] ms window
(lick_k == 0 of the onset-to-peak per-lick table of c1_speed_alllicks.py --window onsetpeak), peak 2-D speed from
lick onset to full extension (Priya's decision for Fig 2E), session mean over first licks of the filtered_v1 trials,
>= 5 first licks per session x side.

Final family = the 502-cell family of pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_onsetpeak_sessmean.csv
(Fig 2E onset-to-peak all-lick cells) + 16 first-lick speed cells = 518 cells, BH within it, star rule unchanged.
Writes (new only): pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv,
stats/inputs/sessmean_licks/tongue_lick1_onsetpeak_vxy_peak_per_session.csv, and <out>/final_family_vs_live.csv
(every final cell vs the live sheets: ps47d5 scalar + xy family).
Usage: python scripts/manuscript/c1_speed_first_final.py <tables_out_dir>"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import MIN_LICKS, kept_trials, run_cells  # noqa: E402

r = PathResolver()
st = r.pipeline_outputs(subdir="stats")
r3 = st / "results/phenotype_pooled/3_tier"
out_csv = r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv"
sess_csv = st / "inputs/sessmean_licks/tongue_lick1_onsetpeak_vxy_peak_per_session.csv"
for p in (out_csv, sess_csv):
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
P = st / "inputs/sessmean_licks/speed_onsetpeak_per_lick"
L = pd.concat([pd.read_parquet(p) for p in sorted(P.glob("speed_onsetpeak_PS*.parquet"))], ignore_index=True)
L["date"] = pd.to_datetime(L["date"]).dt.date
L = L[L.lick_k == 0]
t = kept_trials(r, "tongue_median_vxy_peak_per_trial")
t["date"] = pd.to_datetime(t["date"]).dt.date
L = L.merge(t[["animal", "date", "trial_idx", "side", "epoch_label"]].drop_duplicates(),
            on=["animal", "date", "trial_idx", "side"], how="inner")
L = L[np.isfinite(L.vxy_peak)]
s = L.groupby(["animal", "date", "side"], as_index=False).agg(value=("vxy_peak", "mean"), n_licks=("vxy_peak", "size"),
                                                             epoch_label=("epoch_label", "first"))
s["endpoint"] = "tongue_lick1_onsetpeak_vxy_peak"
s["passes_min_licks"] = s.n_licks >= MIN_LICKS
s.to_csv(sess_csv, index=False)
print("first-lick sessions", len(s), "excluded", int((~s.passes_min_licks).sum()), "first licks", int(s.n_licks.sum()),
      "median/min per session x side", s.n_licks.median(), s.n_licks.min())
cells = run_cells(s[s.passes_min_licks][["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
prev = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_alllicks_onsetpeak_sessmean.csv")
fam = prev[prev.family == "scalar"]
cols = list(cells.columns)
merged = pd.concat([fam[cols], cells[cols]], ignore_index=True)
for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
    merged = merged.rename(columns={pcol: "p_value"})
    merged = apply_correction_to_results_df(merged, group_cols=("family",))
    merged = merged.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
merged["headline_test"] = "mwu_session+nested_bootstrap"
merged["headline_p_fdr"] = merged["mwu_session_p_fdr"]
merged["headline_sig"] = merged["headline_p_fdr"] < 0.05
merged["headline_and_bootstrap_sig"] = merged["headline_sig"] & merged["nb_excludes_zero"].astype(bool)
pd.concat([merged, prev[prev.family != "scalar"]], ignore_index=True).to_csv(out_csv, index=False)
print("wrote", out_csv, len(merged), "scalar-family cells")

# final family vs live (ps47d5 scalar family + its own xy family)
live = pd.concat([pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv").query("family == 'scalar'"),
                  pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")])
MAP = {"tongue_sessmean_xy_peak": "tongue_median_xy_peak_per_trial",
       "tongue_alllicks_onsetpeak_sessmean_vxy_peak": "tongue_median_vxy_peak_per_trial"}
k = ["recovery_phenotype", "side", "post_epoch"]
c2 = ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "headline_and_bootstrap_sig"]
f = merged.assign(live_endpoint=merged.endpoint.map(MAP).fillna(merged.endpoint))
m = f[["endpoint", "live_endpoint"] + k + c2].merge(
    live[["endpoint"] + k + c2].rename(columns={"endpoint": "live_endpoint"}), on=["live_endpoint"] + k, how="left",
    suffixes=("", "_live"))
m["change"] = np.where(m.headline_and_bootstrap_sig_live.isna(), "NEW CELL",
              np.where(m.headline_and_bootstrap_sig & ~m.headline_and_bootstrap_sig_live.astype(bool), "GAINED",
              np.where(~m.headline_and_bootstrap_sig & m.headline_and_bootstrap_sig_live.astype(bool), "LOST", "")))
out = Path(sys.argv[1]); m.to_csv(out / "final_family_vs_live.csv", index=False)
pd.set_option("display.width", 250)
print(m[m.change.isin(["GAINED", "LOST"])][["endpoint"] + k + ["nb_effect_live", "nb_effect", "mwu_session_p_fdr_live",
                                                               "mwu_session_p_fdr", "change"]].to_string())
print("stars live", int(m.headline_and_bootstrap_sig_live.fillna(False).astype(bool).sum()), "final (excl new cells)",
      int(m[m.change != "NEW CELL"].headline_and_bootstrap_sig.sum()))
# first-lick vs all-lick speed per cell (onset to peak)
fl = merged[merged.endpoint == "tongue_lick1_onsetpeak_vxy_peak"][k + c2]
al = merged[merged.endpoint == "tongue_alllicks_onsetpeak_sessmean_vxy_peak"][k + c2]
x = fl.merge(al, on=k, suffixes=("_first", "_all"))
x.to_csv(out / "speed_first_vs_all_onsetpeak.csv", index=False)
print(x.round(4).to_string())
