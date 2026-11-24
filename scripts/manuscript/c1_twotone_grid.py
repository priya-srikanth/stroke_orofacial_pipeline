"""Two-tone (cohort 1, mice #1-#8) STAR GRID for Fig 2D / 2E (CC-B, 2026-11-23; suffix _grid_ccB1123).

Measures: speed = peak 2-D tongue speed from lick onset to full extension (speed_onsetpeak per-lick table, the adopted
2E definition); xy = peak protrusion, hypot(x, y) at each lick's peak (lick_events, the Fig 2D measure).
Lick sets (post-cue v7-kept licks in [70, 3000] ms, filtered_v1 trials, as the existing cells):
  all = every lick; l15 = licks 1-5 of each trial (by peak time); first = lick 1 of each trial.
Session summaries: mean = session mean over licks; median = session median over licks; trialmed = per-trial median,
then the session mean (the live 2D/2E form). For first lick, mean / median are over trials; trialmed does not apply.
Minimum: >= 5 licks (first lick: >= 5 trials) per session x side, as before.
Trials: speed = trials of tongue_median_vxy_peak_per_trial; xy all / l15 = tongue_median_xy_peak_per_trial;
xy first = tongue_lick1_xy_peak (so the first-lick mean reproduces the live S6D cells).

Stats per VERSION (lick set x summary; both measures, 32 cells): the final 518-cell two-tone scalar family
(pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv) with that lick set's adopted cells REPLACED by the
version's cells (all / l15: tongue_sessmean_xy_peak + tongue_alllicks_onsetpeak_sessmean_vxy_peak; first:
tongue_lick1_xy_peak + tongue_lick1_onsetpeak_vxy_peak), BH once over the 518 cells; star = q < 0.05 AND nested
bootstrap CI excludes 0. Single-animal cells (moderate acute, #5 only) get a dagger if q < 0.05 AND the within-animal
bootstrap CI excludes 0 (c1_dagger_single_animal.cell_result, unchanged).
Checks: all/mean, l15/mean, first/mean per-session values reproduce the existing sessmean_licks tables.
Writes NEW files only under <out>: per_session/, tables/.
Usage: python scripts/manuscript/c1_twotone_grid.py <out_dir>"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import MIN_LICKS, REMAP3, kept_trials, run_cells  # noqa: E402
from scripts.manuscript.c1_dagger_single_animal import DAGGER, cell_result  # noqa: E402

r = PathResolver()
st = r.pipeline_outputs(subdir="stats")
R3 = st / "results/phenotype_pooled/3_tier"
SM = st / "inputs/sessmean_licks"
OUT = Path(sys.argv[1])
(OUT / "per_session").mkdir(parents=True, exist_ok=True)
(OUT / "tables").mkdir(parents=True, exist_ok=True)
KEY = ["animal", "date", "trial_idx", "side"]
SUFFIX = "_grid_ccB1123"
VERSIONS = [(ls, sm) for ls in ("all", "l15", "first") for sm in ("mean", "median", "trialmed")
            if not (ls == "first" and sm == "trialmed")]
ADOPTED = {"all": {"speed": "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "xy": "tongue_sessmean_xy_peak"},
           "l15": {"speed": "tongue_alllicks_onsetpeak_sessmean_vxy_peak", "xy": "tongue_sessmean_xy_peak"},
           "first": {"speed": "tongue_lick1_onsetpeak_vxy_peak", "xy": "tongue_lick1_xy_peak"}}
REPRO = {("speed", "all"): "tongue_alllicks_onsetpeak_sessmean_vxy_peak", ("xy", "all"): "tongue_sessmean_xy_peak",
         ("speed", "l15"): "tongue_licks15_onsetpeak_vxy_peak", ("xy", "l15"): "tongue_licks15_xy_peak",
         ("speed", "first"): "tongue_lick1_onsetpeak_vxy_peak"}


def ep_name(meas, ls, sm):
    return f"tt_{meas}_{ls}_{sm}{SUFFIX}"


def trials(slug):
    t = kept_trials(r, slug)
    t["date"] = pd.to_datetime(t["date"]).dt.date
    return t[KEY + ["epoch_label"]].drop_duplicates()


# ---- per-lick tables: animal, date, trial_idx, side, k, value, epoch_label
V = pd.concat([pd.read_parquet(p) for p in sorted((SM / "speed_onsetpeak_per_lick").glob("speed_onsetpeak_PS*.parquet"))])
V["date"] = pd.to_datetime(V["date"]).dt.date
V = V[np.isfinite(V.vxy_peak)].rename(columns={"vxy_peak": "value", "lick_k": "k"})
SPD = V.merge(trials("tongue_median_vxy_peak_per_trial"), on=KEY)


def xy_licks(T):
    rows = []
    for (animal, date), tr in T.groupby(["animal", "date"]):
        le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                             / f"{date.strftime('%Y%m%d')}.parquet", columns=["trial", "side", "t_ms", "x", "y"])
        le = le.rename(columns={"trial": "trial_idx"}).assign(animal=animal, date=date)
        le["value"] = np.hypot(le.x.astype(float), le.y.astype(float))
        le = le[np.isfinite(le.value)].sort_values(["trial_idx", "side", "t_ms"])
        le["k"] = le.groupby(["trial_idx", "side"]).cumcount()
        rows.append(le.merge(tr, on=KEY))
    return pd.concat(rows, ignore_index=True)


XY = xy_licks(trials("tongue_median_xy_peak_per_trial"))
XY1 = xy_licks(trials("tongue_lick1_xy_peak"))
LICKS = {"speed": {"all": SPD, "l15": SPD[SPD.k < 5], "first": SPD[SPD.k == 0]},
         "xy": {"all": XY, "l15": XY[XY.k < 5], "first": XY1[XY1.k == 0]}}


def summarize(L, sm):
    g = ["animal", "date", "side"]
    if sm == "trialmed":
        L = L.groupby(g + ["trial_idx"], as_index=False).agg(value=("value", "median"), n=("value", "size"),
                                                             epoch_label=("epoch_label", "first"))
        s = L.groupby(g, as_index=False).agg(value=("value", "mean"), n_licks=("n", "sum"),
                                             n_trials=("trial_idx", "nunique"), epoch_label=("epoch_label", "first"))
    else:
        s = L.groupby(g, as_index=False).agg(value=("value", sm), n_licks=("value", "size"),
                                             n_trials=("trial_idx", "nunique"), epoch_label=("epoch_label", "first"))
    s["passes_min_licks"] = s.n_licks >= MIN_LICKS
    return s


sess, counts = {}, []
for meas in ("speed", "xy"):
    for ls, sm in VERSIONS:
        s = summarize(LICKS[meas][ls], sm).assign(endpoint=ep_name(meas, ls, sm))
        p = OUT / "per_session" / f"{ep_name(meas, ls, sm)}_per_session.csv"
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
        s.to_csv(p, index=False)
        sess[(meas, ls, sm)] = s
        counts.append(dict(measure=meas, lick_set=ls, summary=sm, session_side_cells=len(s),
                           excluded=int((~s.passes_min_licks).sum()), licks=int(s.n_licks.sum()),
                           licks_median=float(s.n_licks.median()), licks_min=int(s.n_licks.min())))
        if sm == "mean" and (meas, ls) in REPRO:   # reproduce the existing per-session tables
            o = pd.read_csv(SM / f"{REPRO[(meas, ls)]}_per_session.csv")
            o["date"] = pd.to_datetime(o["date"]).dt.date
            m = s.merge(o, on=["animal", "date", "side"], suffixes=("", "_o"))
            assert len(m) == len(s) == len(o), (meas, ls, len(m), len(s), len(o))
            print("repro", meas, ls, "max |dv|", float(np.abs(m.value - m.value_o).max()),
                  "n_licks equal", bool((m.n_licks == m.n_licks_o).all()), flush=True)
pd.DataFrame(counts).to_csv(OUT / "tables" / f"lick_counts{SUFFIX}.csv", index=False)
print(pd.DataFrame(counts).to_string(), flush=True)
# first-lick xy mean vs the live per-session S6D values (filtered_v1 tongue_lick1_xy_peak session mean)
t1 = kept_trials(r, "tongue_lick1_xy_peak"); t1["date"] = pd.to_datetime(t1["date"]).dt.date
o = t1.groupby(["animal", "date", "side"], as_index=False).value.mean()
m = sess[("xy", "first", "mean")].merge(o, on=["animal", "date", "side"], suffixes=("", "_o"))
print("repro xy first: sessions", len(m), len(o), "max |dv|", float(np.abs(m.value - m.value_o).max()), flush=True)

# ---- cells for all 16 combinations (one engine call)
long = pd.concat([s[s.passes_min_licks] for s in sess.values()], ignore_index=True)
cells = run_cells(long[["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
cells.to_csv(OUT / "tables" / f"grid_cells_unadjusted{SUFFIX}.csv", index=False)

# ---- per-version family + BH + marks
fin = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv")
finsc = fin[fin.family == "scalar"]
assert len(finsc) == 518
amap = {a: REMAP3.get(i.recovery_phenotype, i.recovery_phenotype) for a, i in load_animals().items()}
norm_cache = {}
grid = []
for ls, sm in VERSIONS:
    eps = [ep_name("speed", ls, sm), ep_name("xy", ls, sm)]
    base = finsc[~finsc.endpoint.isin(ADOPTED[ls].values())]
    cols = list(cells.columns)
    m = pd.concat([base[cols], cells[cells.endpoint.isin(eps)][cols]], ignore_index=True)
    assert len(m) == 518, (ls, sm, len(m))
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        m = m.rename(columns={pcol: "p_value"})
        m = apply_correction_to_results_df(m, group_cols=("family",))
        m = m.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    m["headline_and_bootstrap_sig"] = (m.mwu_session_p_fdr < 0.05) & m.nb_excludes_zero.astype(bool)
    m["version"] = f"{ls}_{sm}"
    o = base.merge(m, on=["endpoint", "recovery_phenotype", "side", "post_epoch"], suffixes=("_f", "_v"))
    print(ls, sm, "other cells", len(o), "max |dq|", float((o.mwu_session_p_fdr_f - o.mwu_session_p_fdr_v).abs().max()),
          "star changes", int((o.headline_and_bootstrap_sig_f != o.headline_and_bootstrap_sig_v).sum()), flush=True)
    m.to_csv(OUT / "tables" / f"family_{ls}_{sm}{SUFFIX}.csv", index=False)
    g = m[m.endpoint.isin(eps)].copy()
    g["single_animal"] = g.nb_n_animals == 1
    for c in ("wa1_effect", "wa1_ci_lo", "wa1_ci_hi", "sole_animal_ms"):
        g[c] = np.nan if c != "sole_animal_ms" else ""
    g["wa1_excludes_zero"] = False
    for idx, row in g[g.single_animal].iterrows():
        if row.endpoint not in norm_cache:
            norm_cache[row.endpoint] = SUITE.normalize_to_pre_baseline(
                long[long.endpoint == row.endpoint], group_cols=("animal", "side"), value_col="value")
        nm = norm_cache[row.endpoint]
        nm = nm[(nm.animal.map(amap) == row.recovery_phenotype) & (nm.side == row.side)]
        res = cell_result(nm, row.post_epoch, row.mwu_session_p, f"{row.endpoint}/{row.side}/{row.post_epoch}")
        for c in ("wa1_effect", "wa1_ci_lo", "wa1_ci_hi", "wa1_excludes_zero", "sole_animal_ms"):
            g.at[idx, c] = res[c]
    g["dagger"] = g.single_animal & (g.mwu_session_p_fdr < 0.05) & g.wa1_excludes_zero.astype(bool)
    g["mark"] = np.where(g.headline_and_bootstrap_sig, "*", np.where(g.dagger, DAGGER, ""))
    g["measure"] = g.endpoint.str.split("_").str[1]
    g["lick_set"], g["summary"] = ls, sm
    grid.append(g)
G = pd.concat(grid, ignore_index=True)
G.to_csv(OUT / "tables" / f"grid_cells{SUFFIX}.csv", index=False, encoding="utf-8")
print(G.groupby(["measure", "lick_set", "summary"]).agg(stars=("headline_and_bootstrap_sig", "sum"),
                                                        daggers=("dagger", "sum")).to_string())
