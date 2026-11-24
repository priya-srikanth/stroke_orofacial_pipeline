"""FINAL consolidated two-tone (cohort 1, mice #1-#8) scalar family (CC-B, 2026-11-23; suffix _FINAL_ccB1123).

Combines every change Priya decided on 11-23, applied ONCE:
  (1) Fig 2D / 2E all-lick kinematics: ALL post-cue licks (peaks 70-3000 ms after the cue), PER-TRIAL MEDIAN, then the
      SESSION MEAN ("all licks (iii)" of the two-tone grid). 2E speed = peak 2-D tip speed from lick onset to full
      extension (speed_onsetpeak per-lick table). Endpoints:
        tongue_alllicks_trialmed_xy_peak            (replaces tongue_sessmean_xy_peak)
        tongue_alllicks_onsetpeak_trialmed_vxy_peak (replaces tongue_alllicks_onsetpeak_sessmean_vxy_peak)
  (2) First-lick supplement panels: SESSION MEDIAN over trials of the first lick ("first lick (ii)" of the grid):
        tongue_lick1_sessmedian_xy_peak             (replaces tongue_lick1_xy_peak, S6D)
        tongue_lick1_onsetpeak_sessmedian_vxy_peak  (replaces tongue_lick1_onsetpeak_vxy_peak, first-lick speed)
  (3) in-mouth frames = 0: trajectory clusters were already rerun (_ps47d5_inmouth0); nothing to redo here.
  (4) ONE merged scalar family (518 cells), the xy pair in it.
  (5) times as session MEDIANS over trials (Fig 1G, Fig 2C, lick-1 / lick-2 peak times, S6A ILI): taken from
      pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_timesmedian.csv (stats/inputs/sessmedian_times/).
  (6) angles stay session means (unchanged cells).
  (7) dagger for single-animal cells (c1_dagger_single_animal.cell_result, unchanged rule).
NOT applied (pending): item 30 licks per responded trial; dropping tongue_lick1_t_peak_ms; the family-only per-trial
endpoints; the weight baseline (Fig 1K). Family membership for these is unchanged.

Per-session values for (1) and (2) are the two-tone grid tables (twotone_grid/per_session/, same trials and licks);
they are copied, not recomputed, and their cells are recomputed with the same engine (c1_sessmean_scalars.run_cells)
and checked against the grid's unadjusted cells (must be identical). BH runs once over the 518 scalar cells; star =
q < 0.05 AND nested bootstrap CI excludes 0. Daggers: scalar single-animal cells recomputed on this sheet (q from it);
the phase-aligned families are not touched by any change, so their dagger columns are copied from
pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_dagger.csv (checked: same p, same q).

Writes NEW files only (refuses to overwrite):
  <stats>/results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123.csv
  <stats>/inputs/final_ccB1123/<endpoint>_per_session.csv  (the four new kinematic endpoints)
  <out>/tables/per_session/<endpoint>_per_session.csv    (all nine changed endpoints, for the deliverable)
Usage: python scripts/manuscript/c1_final_twotone.py <FINAL_twotone_dir>
"""
from __future__ import annotations

import os
import shutil
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

STATS = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = STATS / "results/phenotype_pooled/3_tier"
GRID = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/ccB_caption_review_2026-11-23/"
            "twotone_grid")
BASE = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123"
TIMES = BASE + "_timesmedian"
DAGSHEET = BASE + "_dagger"
OUT_SHEET = "pooled_phenotype_stats_c2aligned_v3_ps47d5_FINALall_ccB1123"   # not _FINAL_ccB1123: on Windows that IS the existing _final_ccB1123 file (case-insensitive)
SMT = STATS / "inputs/sessmedian_times"
FIN_IN = STATS / "inputs/final_ccB1123"
KEY = ["endpoint", "recovery_phenotype", "side", "post_epoch"]
# new endpoint -> (grid per-session stem, grid endpoint, replaced endpoint)
NEW = {"tongue_alllicks_trialmed_xy_peak": ("tt_xy_all_trialmed_grid_ccB1123", "tongue_sessmean_xy_peak"),
       "tongue_alllicks_onsetpeak_trialmed_vxy_peak": ("tt_speed_all_trialmed_grid_ccB1123",
                                                       "tongue_alllicks_onsetpeak_sessmean_vxy_peak"),
       "tongue_lick1_sessmedian_xy_peak": ("tt_xy_first_median_grid_ccB1123", "tongue_lick1_xy_peak"),
       "tongue_lick1_onsetpeak_sessmedian_vxy_peak": ("tt_speed_first_median_grid_ccB1123",
                                                      "tongue_lick1_onsetpeak_vxy_peak")}
TIME_EPS = ["latency_to_first_correct_lick_s_sessmedian", "tongue_first_peak_t_ms_sessmedian",
            "tongue_lick1_t_peak_ms_sessmedian", "tongue_lick2_t_peak_ms_sessmedian",
            "tongue_sessmedian_within_bout_ili_ms"]
PHASE_FAMS = ("phase_aligned_endpoints", "phase_aligned_endpoints_all_licks")
DAG_COLS = ["sole_animal", "sole_animal_ms", "wa1_n_pre", "wa1_n_post", "mwu_n_pre", "mwu_pre_animals", "wa1_effect",
            "wa1_ci_lo", "wa1_ci_hi", "wa1_excludes_zero"]


def per_session_final(ep: str) -> pd.DataFrame:
    """Per-session values the FINAL sheet's cell is computed from (animal, date, side, value, epoch_label)."""
    if ep in NEW:
        d = pd.read_csv(FIN_IN / f"{ep}_per_session.csv")
    elif ep in TIME_EPS:
        d = pd.read_csv(SMT / f"{ep}_per_session.csv")
    else:
        return DG.per_session("scalar", ep)
    return DG.relabel(d[["animal", "date", "side", "value", "epoch_label"]].copy())


def main() -> int:
    out = Path(sys.argv[1])
    (out / "tables" / "per_session").mkdir(parents=True, exist_ok=True)
    sheet_out = R3 / f"{OUT_SHEET}.csv"
    if sheet_out.exists():
        sys.exit(f"refusing to overwrite {sheet_out}")
    FIN_IN.mkdir(parents=True, exist_ok=True)

    tm_all = pd.read_csv(R3 / f"{TIMES}.csv")
    base_all = pd.read_csv(R3 / f"{BASE}.csv")
    tm = tm_all[tm_all.family == "scalar"]
    assert len(tm) == 518
    # check: outside the time endpoints the times sheet's cells equal the final sheet's (p, effect, CI)
    b = base_all[base_all.family == "scalar"]
    m = tm[~tm.endpoint.isin(TIME_EPS)].merge(b, on=KEY, suffixes=("", "_b"))
    assert len(m) == int((~tm.endpoint.isin(TIME_EPS)).sum()), len(m)
    for c in ("mwu_session_p", "nb_effect", "nb_ci_lo", "nb_ci_hi"):
        assert np.nanmax(np.abs(m[c] - m[c + "_b"])) == 0, c
    print("times sheet: other non-time cells identical to the final sheet (p, effect, CI)", flush=True)

    # per-session values of the four new kinematic endpoints (copied from the grid; never recomputed)
    sess = []
    for ep, (stem, _old) in NEW.items():
        d = pd.read_csv(GRID / "per_session" / f"{stem}_per_session.csv")
        assert d.passes_min_licks.all(), stem
        d = d.assign(endpoint=ep)
        p = FIN_IN / f"{ep}_per_session.csv"
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
        d.to_csv(p, index=False)
        sess.append(d)
        print(ep, "<-", stem, len(d), "session x side; licks", int(d.n_licks.sum()), flush=True)
    for ep in list(NEW) + TIME_EPS:
        src = FIN_IN / f"{ep}_per_session.csv" if ep in NEW else SMT / f"{ep}_per_session.csv"
        dst = out / "tables" / "per_session" / f"{ep}_per_session.csv"
        if dst.exists():
            sys.exit(f"refusing to overwrite {dst}")
        shutil.copyfile(src, dst)

    S = pd.concat(sess, ignore_index=True)
    cells = run_cells(S[["animal", "date", "side", "value", "epoch_label", "endpoint"]], "scalar")
    # check against the grid's unadjusted cells (same engine, same data)
    gu = pd.read_csv(GRID / "tables" / "grid_cells_unadjusted_grid_ccB1123.csv")
    for ep, (stem, _old) in NEW.items():
        a = cells[cells.endpoint == ep].merge(gu[gu.endpoint == stem], on=KEY[1:], suffixes=("", "_g"))
        assert len(a) == 16, (ep, len(a))
        for c in ("mwu_session_p", "nb_effect", "nb_ci_lo", "nb_ci_hi"):
            dd = np.nanmax(np.abs(a[c] - a[c + "_g"])) if a[c].notna().any() else 0.0
            assert dd < 1e-9, (ep, c, dd)
    print("new cells reproduce the grid's unadjusted cells exactly", flush=True)

    cols = list(cells.columns)
    keep = tm[~tm.endpoint.isin([v[1] for v in NEW.values()])]
    fam = pd.concat([keep[cols], cells[cols]], ignore_index=True)
    assert len(fam) == 518, len(fam)
    for pcol, adj in (("mwu_session_p", "mwu_session_p_fdr"), ("wa_p", "wa_p_fdr")):
        fam = fam.rename(columns={pcol: "p_value"})
        fam = apply_correction_to_results_df(fam, group_cols=("family",))
        fam = fam.rename(columns={"p_value": pcol, "p_adj": adj}).drop(columns=["reject"])
    fam["headline_test"] = "mwu_session+nested_bootstrap"
    fam["headline_p_fdr"] = fam["mwu_session_p_fdr"]
    fam["headline_sig"] = fam["headline_p_fdr"] < 0.05
    fam["headline_and_bootstrap_sig"] = fam["headline_sig"] & fam["nb_excludes_zero"].astype(bool)

    # ---- daggers, scalar family (q from THIS family)
    fam["single_animal"] = fam.nb_n_animals == 1
    cache, extra = {}, {}
    for idx, r in fam[fam.single_animal].iterrows():
        if r.endpoint not in cache:
            cache[r.endpoint] = SUITE.normalize_to_pre_baseline(per_session_final(r.endpoint),
                                                                group_cols=("animal", "side"), value_col="value")
        norm = cache[r.endpoint]
        ph = norm.animal.map(lambda a: DG.AMAP[a].recovery_phenotype if a in DG.AMAP else None).map(
            lambda p: {"moderate-severe": "moderate"}.get(p, p))
        norm = norm[(ph == r.recovery_phenotype) & (norm.side == r.side)]
        extra[idx] = DG.cell_result(norm, r.post_epoch, r.mwu_session_p,
                                    f"scalar/{r.endpoint}/{r.recovery_phenotype}/{r.side}/{r.post_epoch}")
    fam = fam.join(pd.DataFrame.from_dict(extra, orient="index"))
    fam["dagger"] = fam.single_animal & (fam.mwu_session_p_fdr < 0.05) & fam.wa1_excludes_zero.fillna(False).astype(bool)
    assert not (fam.headline_and_bootstrap_sig & fam.single_animal).any()

    # ---- other families: unchanged; phase-aligned dagger columns copied from the v29dag2 sheet
    other = tm_all[tm_all.family != "scalar"].copy()
    dg = pd.read_csv(R3 / f"{DAGSHEET}.csv", encoding="utf-8")
    dgo = dg[dg.family != "scalar"]
    o = other.merge(dgo[["family"] + KEY + ["mwu_session_p", "mwu_session_p_fdr", "single_animal", "dagger"] + DAG_COLS],
                    on=["family"] + KEY, how="left", suffixes=("", "_dg"))
    assert len(o) == len(other)
    assert np.nanmax(np.abs(o.mwu_session_p - o.mwu_session_p_dg)) == 0
    assert np.nanmax(np.abs(o.mwu_session_p_fdr - o.mwu_session_p_fdr_dg)) == 0
    o = o.drop(columns=["mwu_session_p_dg", "mwu_session_p_fdr_dg"])
    o["single_animal"] = o.single_animal.fillna(False).astype(bool)
    o["dagger"] = o.dagger.fillna(False).astype(bool)

    full = pd.concat([fam, o], ignore_index=True)
    full["mark"] = np.where(full.headline_and_bootstrap_sig.fillna(False).astype(bool), "**",
                            np.where(full.dagger, DG.DAGGER, ""))
    full.to_csv(sheet_out, index=False, encoding="utf-8")
    sc = full[full.family == "scalar"]
    print("wrote", sheet_out, len(full), "rows;", len(sc), "scalar cells;", int(sc.headline_and_bootstrap_sig.sum()),
          "stars;", int(sc.dagger.sum()), "scalar daggers;",
          int(full[full.family.isin(PHASE_FAMS)].dagger.sum()), "phase-aligned daggers", flush=True)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
    raise SystemExit(main())
