"""Single-animal cells of the two-tone (cohort 1) scalar figures get a dagger (Priya 2026-11-23).

Rule: a cell whose grade has data from only ONE animal (nested animals -> sessions bootstrap = NaN, nb_n_animals == 1)
gets a dagger instead of a star when
  (1) its session rank test (MWU) q < 0.05, q taken UNCHANGED from its BH family, and
  (2) a within-animal bootstrap 95% CI excludes 0: that animal's post-epoch and pre-stroke sessions are resampled
      with replacement (4,000 draws, seed 0, post drawn before pre as in the nested bootstrap), effect = mean(post)
      - mean(pre) of the change from that animal's own pre-stroke mean (the nested bootstrap's effect with one animal).
BH is not redone and no other cell's star changes.

Families covered:
  - two-tone scalar family (518 cells) and the two phase-aligned endpoint families (Fig 2F, 2G; S6E, F) of
    pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123.csv;
  - S8 recovery-mechanics families (c1rm_within_lick, c1rm_across_lick; review/c1_recovery_mechanics_2026-11-21_r2).
For every single-animal cell the per-session values are rebuilt from the same inputs the sheet used and the MWU p is
recomputed; it must equal the sheet's p (asserted), which pins the data to the sheet.

Writes NEW files only (refuses to overwrite):
  <stats>/results/phenotype_pooled/3_tier/pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123_dagger.csv
      (final sheet + columns single_animal, sole_animal, wa1_effect, wa1_ci_lo, wa1_ci_hi, wa1_excludes_zero, dagger,
      mark ('**', the dagger or ''))
  <out>/tests_within_lick_dagger.csv, <out>/tests_across_lick_dagger.csv  (S8 tests + the same columns)
  <out>/dagger_cells.csv  (one row per single-animal cell, all families)
Usage: python scripts/manuscript/c1_dagger_single_animal.py <tables_out_dir>
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label  # noqa: E402

DAGGER = "\u2020"
N_BOOT = 4000
SEED = 0
STATS = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/stats")
R3 = STATS / "results/phenotype_pooled/3_tier"
FINAL = "pooled_phenotype_stats_c2aligned_v3_ps47d5_final_ccB1123"
RM = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/review/"
          "c1_recovery_mechanics_2026-11-21_r2/tables")
SESSMEAN = {"tongue_sessmean_xy_peak", "tongue_alllicks_onsetpeak_sessmean_vxy_peak",
            "tongue_lick1_onsetpeak_vxy_peak", "tongue_sessmean_vxy_peak", "tongue_alllicks_sessmean_vxy_peak"}
MS_NUM = {"PS47": "#1", "PS48": "#2", "PS49": "#3", "PS50": "#4", "PS46": "#5", "PS51": "#6", "PS54": "#7",
          "PS55": "#8"}
AMAP = load_animals()


def relabel(df: pd.DataFrame) -> pd.DataFrame:
    """epoch_label re-derived from (animal, date) with this checkout's animals.yaml (PS47 chronic from day 5)."""
    days = pd.to_datetime(df["date"].astype(str), format="mixed").dt.date
    new = [assign_epoch_label(int(AMAP[a].day_relative_to_stroke(d)), AMAP[a]) if a in AMAP else o
           for a, d, o in zip(df["animal"], days, df["epoch_label"])]
    return df.assign(epoch_label=new)


def per_session(family: str, ep: str) -> pd.DataFrame:
    """animal, date, side, value, epoch_label: the per-session values the sheet's cell was computed from."""
    if family == "scalar":
        if ep in SESSMEAN:
            d = pd.read_csv(STATS / "inputs/sessmean_licks" / f"{ep}_per_session.csv")
            d = d[d.passes_min_licks]
        else:
            src = STATS / "inputs/filtered_v1" / ep
            if not src.is_dir():
                src = STATS / "inputs/no_filter" / ep
            d = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(str(src / "*.parquet")))], ignore_index=True)
            if "is_sentinel" in d:
                d = d[~d.is_sentinel.astype(bool)]
            d = d.dropna(subset=["value"])
            d = d.groupby(["animal", "date", "side"], as_index=False).agg(value=("value", "mean"),
                                                                       epoch_label=("epoch_label", "first"))
    else:
        d = pd.read_csv(STATS / "results/phenotype_pooled" / family / "3_tier/v3/per_session_means.csv")
        d = d[d.endpoint == ep].rename(columns={"mean": "value"})
        d["side"] = d.side.map({"ipsi": "L", "contra": "R"}).fillna(d.side)
    return relabel(d[["animal", "date", "side", "value", "epoch_label"]].copy())


def wa1_boot(pre: np.ndarray, post: np.ndarray) -> tuple[float, float, float]:
    """One-animal session bootstrap of mean(post) - mean(pre) (values = change from the animal's pre mean)."""
    rng = np.random.default_rng(SEED)
    draws = np.empty(N_BOOT)
    for i in range(N_BOOT):
        qa = post[rng.integers(0, post.size, post.size)].mean()
        pa = pre[rng.integers(0, pre.size, pre.size)].mean()
        draws[i] = qa - pa
    lo, hi = np.percentile(draws, SUITE.NESTED_PCTL)
    return float(post.mean() - pre.mean()), float(lo), float(hi)


def cell_result(norm: pd.DataFrame, post_epoch: str, p_sheet: float, tag: str) -> dict:
    """norm: one grade x side, columns animal, epoch_label, value_norm. Checks the MWU p, runs the one-animal boot."""
    sub = norm[norm.epoch_label.isin(("pre", post_epoch))].dropna(subset=["value_norm"])
    pre_all = sub.loc[sub.epoch_label == "pre", "value_norm"].to_numpy(float)
    post_all = sub.loc[sub.epoch_label == post_epoch, "value_norm"].to_numpy(float)
    p = mannwhitneyu(post_all, pre_all, alternative="two-sided").pvalue
    assert abs(p - p_sheet) < 1e-9, f"{tag}: MWU p {p} != sheet {p_sheet}"
    animals = sorted(sub.loc[sub.epoch_label == post_epoch, "animal"].unique())
    assert len(animals) == 1, f"{tag}: post animals {animals}"
    a = animals[0]
    pre = sub.loc[(sub.animal == a) & (sub.epoch_label == "pre"), "value_norm"].to_numpy(float)
    post = sub.loc[(sub.animal == a) & (sub.epoch_label == post_epoch), "value_norm"].to_numpy(float)
    eff, lo, hi = wa1_boot(pre, post)
    pre_animals = sorted(sub.loc[sub.epoch_label == "pre", "animal"].unique())
    return dict(sole_animal=a, sole_animal_ms=MS_NUM.get(a, a), wa1_n_pre=int(pre.size), wa1_n_post=int(post.size),
                mwu_n_pre=int(pre_all.size), mwu_pre_animals="+".join(MS_NUM.get(x, x) for x in pre_animals),
                wa1_effect=eff, wa1_ci_lo=lo, wa1_ci_hi=hi, wa1_excludes_zero=bool(lo > 0 or hi < 0))


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    sheet_out = R3 / f"{FINAL}_dagger.csv"
    targets = [sheet_out, out / "tests_within_lick_dagger.csv", out / "tests_across_lick_dagger.csv",
               out / "dagger_cells.csv"]
    for t in targets:
        if t.exists():
            sys.exit(f"refusing to overwrite {t}")

    # ---- two-tone final sheet: scalar + phase-aligned families
    sh = pd.read_csv(R3 / f"{FINAL}.csv")
    sh["single_animal"] = (sh.nb_n_animals == 1) & sh.family.isin(
        ["scalar", "phase_aligned_endpoints", "phase_aligned_endpoints_all_licks"])
    extra = {}
    cache = {}
    for idx, r in sh[sh.single_animal].iterrows():
        key = (r.family, r.endpoint)
        if key not in cache:
            cache[key] = SUITE.normalize_to_pre_baseline(per_session(*key), group_cols=("animal", "side"),
                                                         value_col="value")
        norm = cache[key]
        norm = norm[norm.animal.map(lambda a: AMAP[a].recovery_phenotype if a in AMAP else None)
                    .map(lambda p: {"moderate-severe": "moderate"}.get(p, p)) == r.recovery_phenotype]
        norm = norm[norm.side == r.side]
        extra[idx] = cell_result(norm, r.post_epoch, r.mwu_session_p, f"{r.family}/{r.endpoint}/{r.recovery_phenotype}"
                                 f"/{r.side}/{r.post_epoch}")
        print("ok", r.family, r.endpoint, r.side, r.post_epoch, extra[idx]["sole_animal"], flush=True)
    ex = pd.DataFrame.from_dict(extra, orient="index")
    sh = sh.join(ex)
    sh["dagger"] = sh.single_animal & (sh.mwu_session_p_fdr < 0.05) & sh.wa1_excludes_zero.fillna(False).astype(bool)
    sh["mark"] = np.where(sh.headline_and_bootstrap_sig, "**", np.where(sh.dagger, DAGGER, ""))
    assert not (sh.headline_and_bootstrap_sig & sh.single_animal).any()
    sh.to_csv(sheet_out, index=False, encoding="utf-8")

    # ---- S8 recovery-mechanics tests
    S = pd.read_csv(RM / "session_cells_within_lick.csv")
    A = pd.read_csv(RM / "across_lick_cells.csv")
    s8_rows = []
    for name, R, frame, zero in (("tests_within_lick", pd.read_csv(RM / "tests_within_lick.csv"), S, True),
                                 ("tests_across_lick", pd.read_csv(RM / "tests_across_lick.csv"), A, None)):
        R["single_animal"] = R.nb_n_animals == 1
        extra = {}
        for idx, r in R[R.single_animal].iterrows():
            g = frame[(frame.grade == r.grade) & (frame.side == r.side)].dropna(subset=[r.measure])
            z = (r.measure != "xcorr") if zero is None else zero   # S8: xcorr is miss - hit (not zeroed); others vs own pre
            base = g[g.epoch == "pre"].groupby("animal")[r.measure].mean() if z else 0
            g = g.assign(value_norm=g[r.measure] - (g.animal.map(base) if z else 0),
                         epoch_label=g.epoch)
            try:
                extra[idx] = cell_result(g, r.post_epoch, r.mwu_p, f"S8/{r.measure}/{r.grade}/{r.side}/{r.post_epoch}")
            except AssertionError as e:
                print("S8 CHECK FAILED", e, flush=True)
                raise
        R = R.join(pd.DataFrame.from_dict(extra, orient="index"))
        R["dagger"] = R.single_animal & (R.q_bh < 0.05) & R.wa1_excludes_zero.fillna(False).astype(bool)
        R["mark"] = np.where(R.star, "**", np.where(R.dagger, DAGGER, ""))
        R.to_csv(out / f"{name}_dagger.csv", index=False, encoding="utf-8")
        s8_rows.append(R[R.single_animal].assign(table=name))

    # ---- one table of all single-animal cells
    a = sh[sh.single_animal].rename(columns={"recovery_phenotype": "grade", "mwu_session_p_fdr": "q",
                                             "mwu_session_p": "mwu_p", "endpoint": "measure"})
    a["side"] = a.side.map({"L": "ipsilesional", "R": "contralesional"})
    b = pd.concat(s8_rows, ignore_index=True).rename(columns={"q_bh": "q"})
    b["side"] = b.side.map({"ipsi": "ipsilesional", "contra": "contralesional"})
    cols = ["family", "measure", "grade", "side", "post_epoch", "sole_animal", "sole_animal_ms", "wa1_n_pre",
            "wa1_n_post", "mwu_n_pre", "mwu_pre_animals", "n_post_sessions", "mwu_p", "q", "wa1_effect", "wa1_ci_lo",
            "wa1_ci_hi", "wa1_excludes_zero", "dagger"]
    allc = pd.concat([a[cols], b[cols]], ignore_index=True)
    allc.to_csv(out / "dagger_cells.csv", index=False, encoding="utf-8")
    print(allc.groupby("family")[["dagger"]].agg(["size", "sum"]))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
    raise SystemExit(main())
