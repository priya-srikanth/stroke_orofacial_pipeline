"""FINAL two-tone family vs the LIVE sheets of the v28 manuscript, cell by cell (CC-B, 2026-11-23, _FINAL_ccB1123).

LIVE = pooled_phenotype_stats_c2aligned_v3_ps47d5.csv (scalar + phase-aligned families) + its separate xy family
pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv; S8 = review/c1_recovery_mechanics_2026-11-21_r2 tests (live).
FINAL = pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123.csv; S8 = the v29dag2 dagger test tables (same
stars, daggers added).
Writes (new only) under <out>/tables/:
  final_vs_live_cells_FINAL_ccB1123.csv   every cell of every drawn panel, live vs final (effect, CI, q, mark)
  final_vs_live_changes_FINAL_ccB1123.csv every star gained / lost and every dagger added (drawn panels)
  final_vs_live_counts_FINAL_ccB1123.csv  stars and daggers per panel, live vs final
  final_vs_live_family_FINAL_ccB1123.csv  star changes in family-only (not drawn) scalar cells
Usage: python scripts/manuscript/c1_final_compare.py <FINAL_twotone_dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STATS = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = STATS / "results/phenotype_pooled/3_tier"
V = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper")
RM = V / "review/c1_recovery_mechanics_2026-11-21_r2/tables"
DAGT = V / "ccB_caption_review_2026-11-23/twotone_rerun/v29dag/tables"
SFX = "_FINAL_ccB1123"
DAGGER = "\u2020"
# panel -> (live endpoint, final endpoint, family)
PANELS = [
    ("Fig 1E", "first_lick_accuracy_all", "first_lick_accuracy_all", "scalar"),
    ("Fig 1F", "num_correct_licks_per_trial_rw", "num_correct_licks_per_trial_rw", "scalar"),
    ("Fig 1G", "latency_to_first_correct_lick_s", "latency_to_first_correct_lick_s_sessmedian", "scalar"),
    ("Fig 1H", "d_prime", "d_prime", "scalar"),
    ("Fig 1I", "criterion_c", "criterion_c", "scalar"),
    ("Fig 2C", "tongue_first_peak_t_ms", "tongue_first_peak_t_ms_sessmedian", "scalar"),
    ("Fig 2D", "tongue_median_xy_peak_per_trial", "tongue_alllicks_trialmed_xy_peak", "scalar"),
    ("Fig 2E", "tongue_median_vxy_peak_per_trial", "tongue_alllicks_onsetpeak_trialmed_vxy_peak", "scalar"),
    ("Fig 2F", "peak_angle_deg", "peak_angle_deg", "phase_aligned_endpoints"),
    ("Fig 2G", "peak_angle_deg", "peak_angle_deg", "phase_aligned_endpoints_all_licks"),
    ("S6A ILI", "tongue_mean_within_bout_ili_ms", "tongue_sessmedian_within_bout_ili_ms", "scalar"),
    ("S6D first-lick xy", "tongue_lick1_xy_peak", "tongue_lick1_sessmedian_xy_peak", "scalar"),
    ("S6E", "signed_x_at_max_abs_phase_0_075_px", "signed_x_at_max_abs_phase_0_075_px", "phase_aligned_endpoints"),
    ("S6F", "signed_x_at_max_abs_phase_0_075_px", "signed_x_at_max_abs_phase_0_075_px",
     "phase_aligned_endpoints_all_licks"),
    ("S6 first-lick speed (new)", None, "tongue_lick1_onsetpeak_sessmedian_vxy_peak", "scalar"),
]
S8P = [("S8A", "R1", "e_L"), ("S8B", "R1", "e_E"), ("S8C", "R1", "corr_toward"), ("S8D", "R3", "xcorr")]
EPO = {"acute": 1, "sub_acute": 2, "chronic": 3}
GR = {"mild": 0, "moderate": 1, "severe": 2}
SIDE = {"L": "ipsilesional", "R": "contralesional", "ipsi": "ipsilesional", "contra": "contralesional"}
# family-only endpoints renamed between live and final
REN = {"latency_to_first_correct_lick_s": "latency_to_first_correct_lick_s_sessmedian",
       "tongue_first_peak_t_ms": "tongue_first_peak_t_ms_sessmedian",
       "tongue_lick1_t_peak_ms": "tongue_lick1_t_peak_ms_sessmedian",
       "tongue_lick2_t_peak_ms": "tongue_lick2_t_peak_ms_sessmedian",
       "tongue_mean_within_bout_ili_ms": "tongue_sessmedian_within_bout_ili_ms",
       "tongue_median_xy_peak_per_trial": "tongue_alllicks_trialmed_xy_peak",
       "tongue_median_vxy_peak_per_trial": "tongue_alllicks_onsetpeak_trialmed_vxy_peak",
       "tongue_lick1_xy_peak": "tongue_lick1_sessmedian_xy_peak"}


def mark_live(r):
    return "**" if bool(r.headline_and_bootstrap_sig) else ""


def main():
    out = Path(sys.argv[1]) / "tables"
    out.mkdir(parents=True, exist_ok=True)
    names = [f"final_vs_live_{k}{SFX}.csv" for k in ("cells", "changes", "counts", "family")]
    for n in names:
        if (out / n).exists():
            sys.exit(f"refusing to overwrite {out / n}")
    live = pd.concat([pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5.csv"),
                      pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_xy_dist_ps47d5.csv")], ignore_index=True)
    fin = pd.read_csv(R3 / "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123.csv", encoding="utf-8",
                      keep_default_na=False, na_values=[""])
    fin["mark"] = fin["mark"].fillna("")
    k = ["recovery_phenotype", "side", "post_epoch"]
    rows = []
    for panel, lep, fep, fam in PANELS:
        f = fin[(fin.endpoint == fep) & (fin.family == fam)]
        if lep is None:
            l = pd.DataFrame(columns=k)
        else:
            l = live[(live.endpoint == lep) & (live.family == fam)]
            l = l.assign(mark=[mark_live(r) for r in l.itertuples()])
        m = f[k + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "mark", "nb_n_animals", "wa1_effect",
                   "wa1_ci_lo", "wa1_ci_hi"]].merge(
            l[k + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "mark"]] if len(l) else
            pd.DataFrame(columns=k + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr", "mark"]),
            on=k, how="outer", suffixes=("", "_live"))
        m.insert(0, "panel", panel)
        rows.append(m)
    # S8: live tests vs dagger tests
    for panel, key, meas in S8P:
        name = "tests_within_lick" if key == "R1" else "tests_across_lick"
        l = pd.read_csv(RM / f"{name}.csv")
        d = pd.read_csv(DAGT / f"{name}_dagger.csv", encoding="utf-8", keep_default_na=False, na_values=[""])
        l, d = l[l.measure == meas], d[d.measure == meas]
        kk = ["grade", "side", "post_epoch"]
        assert (l.set_index(kk).star.sort_index() == d.set_index(kk).star.sort_index()).all()
        m = d[kk + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "q_bh", "mark", "nb_n_animals", "wa1_effect", "wa1_ci_lo",
                    "wa1_ci_hi"]].merge(l[kk + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "q_bh", "star"]], on=kk,
                                        suffixes=("", "_live"))
        m["mark"] = m["mark"].fillna("")
        m["mark_live"] = np.where(m.star, "**", "")
        m = m.drop(columns="star").rename(columns={"grade": "recovery_phenotype", "q_bh": "mwu_session_p_fdr",
                                                    "q_bh_live": "mwu_session_p_fdr_live"})
        m.insert(0, "panel", panel)
        rows.append(m)
    C = pd.concat(rows, ignore_index=True)
    C["mark"] = C["mark"].fillna("")
    C["mark_live"] = C["mark_live"].fillna("")
    C["side"] = C.side.map(SIDE).fillna(C.side)
    C["post_epoch"] = C.post_epoch.replace({"sub_acute": "subacute"})
    C["change"] = np.select(
        [(C.mark == "**") & (C.mark_live != "**"), (C.mark != "**") & (C.mark_live == "**"),
         (C.mark == DAGGER) & (C.mark_live != DAGGER)],
        ["star GAINED", "star LOST", "dagger ADDED"], "")
    C = C.sort_values(["panel", "side", "recovery_phenotype", "post_epoch"],
                      key=lambda s: s.map(GR) if s.name == "recovery_phenotype" else
                      (s.map({"acute": 1, "subacute": 2, "chronic": 3}) if s.name == "post_epoch" else s))
    C.to_csv(out / names[0], index=False, encoding="utf-8")
    ch = C[C.change != ""]
    ch.to_csv(out / names[1], index=False, encoding="utf-8")
    cnt = C.groupby("panel", sort=False).agg(stars_live=("mark_live", lambda s: int((s == "**").sum())),
                                              stars_final=("mark", lambda s: int((s == "**").sum())),
                                              daggers_final=("mark", lambda s: int((s == DAGGER).sum())),
                                              gained=("change", lambda s: int((s == "star GAINED").sum())),
                                              lost=("change", lambda s: int((s == "star LOST").sum()))).reset_index()
    cnt.to_csv(out / names[2], index=False)
    pd.set_option("display.width", 250)
    print(cnt.to_string(index=False))
    print(ch[["panel", "recovery_phenotype", "side", "post_epoch", "nb_effect_live", "nb_ci_lo_live", "nb_ci_hi_live",
              "mwu_session_p_fdr_live", "nb_effect", "nb_ci_lo", "nb_ci_hi", "wa1_effect", "wa1_ci_lo", "wa1_ci_hi",
              "mwu_session_p_fdr", "change"]].round(4).to_string(index=False))
    # whole scalar family (not drawn): star changes with the renames
    drawn = {p[2] for p in PANELS if p[3] == "scalar"}
    ls = live[live.family == "scalar"].copy()
    ls["endpoint"] = ls.endpoint.replace(REN)
    fs = fin[fin.family == "scalar"]
    m = fs.merge(ls[["endpoint"] + k + ["headline_and_bootstrap_sig", "mwu_session_p_fdr"]], on=["endpoint"] + k,
                 how="left", suffixes=("", "_live"))
    m["live_star"] = m.headline_and_bootstrap_sig_live.fillna(False).astype(bool)
    m["chg"] = np.select([m.headline_and_bootstrap_sig & ~m.live_star, ~m.headline_and_bootstrap_sig & m.live_star,
                          m.dagger.astype(bool)], ["star GAINED", "star LOST", "dagger"], "")
    m["in_live"] = m.headline_and_bootstrap_sig_live.notna()
    fo = m[~m.endpoint.isin(drawn)]
    fo[fo.chg != ""][["endpoint"] + k + ["in_live", "nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_session_p_fdr_live",
                                         "mwu_session_p_fdr", "chg"]].to_csv(out / names[3], index=False,
                                                                             encoding="utf-8")
    print("family-only cells:", fo.groupby("chg").size().to_dict())
    print("scalar family stars: live (470 + 32 xy)", int(live[live.family == "scalar"].headline_and_bootstrap_sig.sum()),
          "final", int(fs.headline_and_bootstrap_sig.sum()), "; scalar daggers", int(fs.dagger.sum()))


if __name__ == "__main__":
    main()
