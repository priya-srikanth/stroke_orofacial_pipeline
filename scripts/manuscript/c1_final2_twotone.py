"""FINAL2 two-tone scalar family (CC-B, 2026-11-23; sheet _FINALall2_ccB1123), Priya's decisions of 11-23 (late) on
top of the FINAL family (pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123.csv):
  (1) item 30 YES: camera licks per responded trial (tongue_n_licks_per_responded_trial; every v7-kept camera lick
      70-5000 ms after the cue, mean over trials with >= 1 lick; stats/inputs/sessmedian_times/) joins the family
      (16 cells; recomputed here and checked against the _timesmedian_lpr sheet's cells);
  (2) decision 6 YES: DROP the duplicate tongue_lick1_t_peak_ms_sessmedian (identical to Fig 2C's
      tongue_first_peak_t_ms_sessmedian in every cell) and the family-only per-trial endpoints in no figure:
      tongue_median_angle_at_peak_velocity, tongue_median_angle_max_signed_per_lick (per-trial medians) and
      tongue_max_vxy_peak_first5, tongue_mean_vxy_peak_first5, tongue_max_vy_peak_first5 (first-5 max / mean);
  (3) item 33 (weight baseline) is a separate panel family (Fig 1K), not in this sheet.
BH once over the new scalar family; star = q < 0.05 AND nested bootstrap CI excludes 0; dagger rule unchanged
(c1_dagger_single_animal.cell_result, q from this family). Other families copied from the FINAL sheet.
Writes NEW only: <stats>/results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123.csv
Usage: python scripts/manuscript/c1_final2_twotone.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import run_cells  # noqa: E402
from scripts.manuscript import c1_dagger_single_animal as DG  # noqa: E402
from scripts.manuscript import c1_final_twotone as F1  # noqa: E402

R3 = F1.R3
PREV = "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123"
LPR_SHEET = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian_lpr"
OUT_SHEET = "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall2_ccB1123"
LPR = "tongue_n_licks_per_responded_trial"
DROP = ["tongue_lick1_t_peak_ms_sessmedian", "tongue_median_angle_at_peak_velocity",
        "tongue_median_angle_max_signed_per_lick", "tongue_max_vxy_peak_first5", "tongue_mean_vxy_peak_first5",
        "tongue_max_vy_peak_first5"]
KEY = F1.KEY


def per_session(ep: str) -> pd.DataFrame:
    if ep == LPR:
        d = pd.read_csv(F1.SMT / f"{LPR}_per_session.csv")
        return DG.relabel(d[["animal", "date", "side", "value", "epoch_label"]].copy())
    return F1.per_session_final(ep)


def main() -> int:
    out = R3 / f"{OUT_SHEET}.csv"
    if out.exists():
        sys.exit(f"refusing to overwrite {out}")
    prev = pd.read_csv(R3 / f"{PREV}.csv", encoding="utf-8", keep_default_na=False, na_values=[""])
    sc = prev[prev.family == "scalar"]
    assert set(DROP) <= set(sc.endpoint), set(DROP) - set(sc.endpoint)
    ndrop = int(sc.endpoint.isin(DROP).sum())
    # item 30 cells, recomputed and checked against the lpr sheet
    ls = per_session(LPR)
    cells = run_cells(ls.assign(endpoint=LPR), "scalar")
    lpr = pd.read_csv(R3 / f"{LPR_SHEET}.csv")
    a = cells.merge(lpr[lpr.endpoint == LPR], on=KEY, suffixes=("", "_l"))
    assert len(a) == len(cells) == 16, (len(a), len(cells))
    for c in ("mwu_session_p", "nb_effect", "nb_ci_lo", "nb_ci_hi"):
        assert np.nanmax(np.abs(a[c] - a[c + "_l"])) < 1e-12, c
    print("item 30 cells reproduce the _timesmedian_lpr sheet exactly", flush=True)
    cols = list(cells.columns)
    fam = pd.concat([sc[~sc.endpoint.isin(DROP)][cols], cells[cols]], ignore_index=True)
    print(f"scalar family: {len(sc)} - {ndrop} dropped + {len(cells)} item 30 = {len(fam)} cells", flush=True)
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        fam = fam.rename(columns={pcol: "p_value"})
        fam = apply_correction_to_results_df(fam, group_cols=("family",))
        fam = fam.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    fam["headline_test"] = "mwu_session+nested_bootstrap"
    fam["headline_p_fdr"] = fam["mwu_session_p_fdr"]
    fam["headline_sig"] = fam["headline_p_fdr"] < 0.05
    fam["headline_and_bootstrap_sig"] = fam["headline_sig"] & fam["nb_excludes_zero"].astype(bool)
    fam["single_animal"] = fam.nb_n_animals == 1
    cache, extra = {}, {}
    for idx, r in fam[fam.single_animal].iterrows():
        if r.endpoint not in cache:
            cache[r.endpoint] = SUITE.normalize_to_pre_baseline(per_session(r.endpoint), group_cols=("animal", "side"),
                                                                value_col="value")
        norm = cache[r.endpoint]
        ph = norm.animal.map(lambda x: DG.AMAP[x].recovery_phenotype if x in DG.AMAP else None).map(
            lambda p: {"moderate-severe": "moderate"}.get(p, p))
        norm = norm[(ph == r.recovery_phenotype) & (norm.side == r.side)]
        extra[idx] = DG.cell_result(norm, r.post_epoch, r.mwu_session_p,
                                    f"scalar/{r.endpoint}/{r.recovery_phenotype}/{r.side}/{r.post_epoch}")
    fam = fam.join(pd.DataFrame.from_dict(extra, orient="index"))
    fam["dagger"] = fam.single_animal & (fam.mwu_session_p_fdr < 0.05) & fam.wa1_excludes_zero.fillna(False).astype(bool)
    assert not (fam.headline_and_bootstrap_sig & fam.single_animal).any()
    full = pd.concat([fam, prev[prev.family != "scalar"]], ignore_index=True)
    full["single_animal"] = full.single_animal.fillna(False).astype(bool)
    full["dagger"] = full.dagger.fillna(False).astype(bool)
    full["mark"] = np.where(full.headline_and_bootstrap_sig.fillna(False).astype(bool), "**",
                            np.where(full.dagger, DG.DAGGER, ""))
    full.to_csv(out, index=False, encoding="utf-8")
    s2 = full[full.family == "scalar"]
    print("wrote", out, len(full), "rows;", len(s2), "scalar cells;", int(s2.headline_and_bootstrap_sig.sum()),
          "stars;", int(s2.dagger.sum()), "scalar daggers", flush=True)
    # vs the previous FINAL, cells present in both
    m = s2.merge(sc, on=KEY, suffixes=("", "_p"))
    print("cells in both:", len(m), "max |dq|", float((m.mwu_session_p_fdr - m.mwu_session_p_fdr_p).abs().max()),
          "mark changes:", int((m.mark != m.mark_p.fillna("")).sum()), flush=True)
    print(m[m.mark != m.mark_p.fillna("")][KEY + ["mwu_session_p_fdr_p", "mwu_session_p_fdr", "mark_p", "mark"]]
          .to_string(index=False))
    print(s2[s2.endpoint == LPR][KEY[1:] + ["nb_effect", "nb_ci_lo", "nb_ci_hi", "wa1_effect", "wa1_ci_lo", "wa1_ci_hi",
                                         "mwu_session_p_fdr", "mark"]].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
    raise SystemExit(main())
