"""CANDIDATE two-tone 'licks 1-5' set (CC-B, 2026-11-23 late; Priya weighing it, nothing replaced).

For each kept trial (filtered_v1), the first five v7-kept licks in the [70, 3000] ms window (by peak time), session
MEAN over those licks (>= 5 licks per session x side):
  (a) peak speed from lick onset to extension peak (speed_onsetpeak per-lick table, lick_k < 5)  -> Fig 2E candidate
  (b) peak protrusion, hypot(x, y) at each lick's peak (lick_events parquet, first 5 by t_ms)   -> Fig 2D candidate
Family: the final 518-cell family (pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv) with the adopted
all-lick 2D (tongue_sessmean_xy_peak) and 2E (tongue_alllicks_onsetpeak_sessmean_vxy_peak) cells REPLACED by these
candidate cells (still 518 cells), BH within it, star rule unchanged.
Writes (new only): pooled_phenotype_stats_c2aligned_v3_ps47d5_licks15_candidate.csv,
stats/inputs/sessmean_licks/tongue_licks15_{xy,onsetpeak_vxy}_peak_per_session.csv, <out>/licks15_candidate_cells.csv
Usage: python scripts/manuscript/c1_licks15_candidate.py <tables_out_dir>"""
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
SM = st / "inputs/sessmean_licks"
out_csv = r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_licks15_candidate.csv"
outs = {"xy": SM / "tongue_licks15_xy_peak_per_session.csv", "vxy": SM / "tongue_licks15_onsetpeak_vxy_peak_per_session.csv"}
for p in [out_csv, *outs.values()]:
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
KEY = ["animal", "date", "trial_idx", "side"]


def trials(slug):
    t = kept_trials(r, slug)
    t["date"] = pd.to_datetime(t["date"]).dt.date
    return t[KEY + ["epoch_label"]].drop_duplicates()


def session(L, name):
    s = L.groupby(["animal", "date", "side"], as_index=False).agg(value=("value", "mean"), n_licks=("value", "size"),
                                                                 epoch_label=("epoch_label", "first"))
    s["endpoint"] = name
    s["passes_min_licks"] = s.n_licks >= MIN_LICKS
    print(name, "sessions", len(s), "excluded", int((~s.passes_min_licks).sum()), "licks", int(s.n_licks.sum()),
          "median/min", s.n_licks.median(), s.n_licks.min())
    return s


# (a) speed, licks 1-5 (lick_k counts the kept licks in the window in time order)
V = pd.concat([pd.read_parquet(p) for p in sorted((SM / "speed_onsetpeak_per_lick").glob("speed_onsetpeak_PS*.parquet"))])
V["date"] = pd.to_datetime(V["date"]).dt.date
V = V[(V.lick_k < 5) & np.isfinite(V.vxy_peak)].merge(trials("tongue_median_vxy_peak_per_trial"), on=KEY)
sv = session(V.rename(columns={"vxy_peak": "value"}), "tongue_licks15_onsetpeak_vxy_peak")
# (b) xy, licks 1-5 by peak time within the trial, lick_events window [70, 3000] ms
T = trials("tongue_median_xy_peak_per_trial")
rows = []
for (animal, date), tr in T.groupby(["animal", "date"]):
    le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                         / f"{date.strftime('%Y%m%d')}.parquet", columns=["trial", "side", "t_ms", "x", "y"])
    le = le.rename(columns={"trial": "trial_idx"}).assign(animal=animal, date=date)
    le["value"] = np.hypot(le.x.astype(float), le.y.astype(float))
    le = le[np.isfinite(le.value)].sort_values(["trial_idx", "side", "t_ms"])
    le["k"] = le.groupby(["trial_idx", "side"]).cumcount()
    rows.append(le[le.k < 5].merge(tr, on=KEY))
sx = session(pd.concat(rows, ignore_index=True), "tongue_licks15_xy_peak")
sv.to_csv(outs["vxy"], index=False); sx.to_csv(outs["xy"], index=False)
cells = run_cells(pd.concat([s[s.passes_min_licks] for s in (sv, sx)])[["animal", "date", "side", "value", "epoch_label",
                                                                        "endpoint"]], "scalar")
fin = pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv")
fam = fin[(fin.family == "scalar") & ~fin.endpoint.isin(["tongue_sessmean_xy_peak",
                                                           "tongue_alllicks_onsetpeak_sessmean_vxy_peak"])]
cols = list(cells.columns)
m = pd.concat([fam[cols], cells[cols]], ignore_index=True)
for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
    m = m.rename(columns={pcol: "p_value"})
    m = apply_correction_to_results_df(m, group_cols=("family",))
    m = m.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
m["headline_test"] = "mwu_session+nested_bootstrap"
m["headline_p_fdr"] = m["mwu_session_p_fdr"]
m["headline_sig"] = m["headline_p_fdr"] < 0.05
m["headline_and_bootstrap_sig"] = m["headline_sig"] & m["nb_excludes_zero"].astype(bool)
pd.concat([m, fin[fin.family != "scalar"]], ignore_index=True).to_csv(out_csv, index=False)
print("wrote", out_csv, len(m), "scalar cells")
# per-cell: live, adopted all-lick, licks 1-5
live = pd.concat([pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv").query("family == 'scalar'"),
                  pd.read_csv(r3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")])
k = ["recovery_phenotype", "side", "post_epoch"]
c = ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "headline_and_bootstrap_sig"]
out = []
for meas, le, ae, ce in (("speed", "tongue_median_vxy_peak_per_trial", "tongue_alllicks_onsetpeak_sessmean_vxy_peak",
                          "tongue_licks15_onsetpeak_vxy_peak"),
                         ("xy", "tongue_median_xy_peak_per_trial", "tongue_sessmean_xy_peak", "tongue_licks15_xy_peak")):
    x = (live[live.endpoint == le][k + c].add_suffix("_live").rename(columns={f"{q}_live": q for q in k})
         .merge(fin[fin.endpoint == ae][k + c].add_suffix("_all").rename(columns={f"{q}_all": q for q in k}), on=k)
         .merge(m[m.endpoint == ce][k + c].add_suffix("_15").rename(columns={f"{q}_15": q for q in k}), on=k))
    x.insert(0, "measure", meas)
    out.append(x)
X = pd.concat(out, ignore_index=True)
X.to_csv(Path(sys.argv[1]) / "licks15_candidate_cells.csv", index=False)
o = fin[(fin.family == "scalar") & ~fin.endpoint.isin(["tongue_sessmean_xy_peak", "tongue_alllicks_onsetpeak_sessmean_vxy_peak"])]
z = o.merge(m, on=["endpoint"] + k, suffixes=("_f", "_c"))
print("other cells:", len(z), "max |dq|", (z.mwu_session_p_fdr_f - z.mwu_session_p_fdr_c).abs().max(), "star changes",
      int((z.headline_and_bootstrap_sig_f != z.headline_and_bootstrap_sig_c).sum()))
