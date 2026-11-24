#!/usr/bin/env python
"""Two-tone cohort: body weight by epoch with the BEHAVIORAL pre-stroke baseline (caption review item 33, CC-B 2026-11-23).

Priya: the weight baseline must be exactly the pre-stroke sessions that define the behavioral baseline. Fig 1K
(run_weight_epoch_unified.py) normalized to the mean of ALL pre-stroke days in the Weights sheet (day <= 0, back into
training: 68 mild-grade days). Here:

- baseline days = the Weights-sheet days whose date is a pre-stroke BEHAVIOR session of that animal, i.e. a non-sentinel
  ``epoch_label == 'pre'`` session of the Fig 1 spout-contact endpoints (``stats/inputs/no_filter/
  num_all_licks_per_trial_rw/<animal>.parquet``; the same session set as every Fig 1 / S4 behavior endpoint; the
  DLC endpoints use a subset of it, sessions with usable video);
- ``pct`` = weight as % of the mean over those baseline days; other pre-stroke days (training days before the
  behavioral baseline) are dropped from the panel and the test;
- epochs and test unchanged: ``body_weight_epoch.assign_epochs`` with the ps47d5 stamped boundaries,
  ``epoch_tests_c2_aligned`` (animal-day MWU vs pre within grade, BH over the 9 cells, AND the paired nested
  animals -> days bootstrap, 4,000 resamples, seed 0).

Writes (refuses to overwrite) under --out-dir:
  c1_weight_epoch_behavbase_ps47d5.csv   (tests; old Fig 1K columns joined as old_*)
  c1_weight_days_behavbase_ps47d5.csv    (animal-days drawn: animal, day, date, g, pct, epoch, group)
  c1_weight_baseline_days.csv            (per animal: behavior pre sessions, weight days used, days dropped)
Usage: python scripts/manuscript/c1_weight_behavior_baseline.py <Stroke_quantification.xlsx> <epoch_table.csv>
         <old_unified.csv> --out-dir DIR [--n-boot 4000]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import body_weight_epoch as bw

REMAP = {"moderate-severe": "moderate"}


def behavior_pre_dates(r: PathResolver) -> dict[str, set]:
    src = r.pipeline_outputs(subdir="stats") / "inputs" / "no_filter" / "num_all_licks_per_trial_rw"
    out = {}
    for p in sorted(src.glob("PS*.parquet")):
        d = pd.read_parquet(p)
        d = d[(d.epoch_label == "pre") & ~d.is_sentinel.astype(bool) & d.value.notna()]
        out[p.stem] = set(pd.to_datetime(d.date).dt.date)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx")
    ap.add_argument("epoch_table")
    ap.add_argument("old_unified")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--n-boot", type=int, default=4000)
    a = ap.parse_args(argv)
    outs = {k: a.out_dir / f"{k}.csv" for k in ("c1_weight_epoch_behavbase_ps47d5", "c1_weight_days_behavbase_ps47d5",
                                                 "c1_weight_baseline_days")}
    clash = [str(p) for p in outs.values() if p.exists()]
    if clash:
        sys.exit("refusing to overwrite " + ", ".join(clash))

    info = load_animals()
    animals = [an for _, mice in bw.WEIGHTS_BLOCKS for _, an in mice]
    sd = {an: info[an].stroke_date for an in animals}
    df = bw.read_weights_sheet(a.xlsx, sd)
    df["date"] = [sd[an] + dt.timedelta(days=int(d)) for an, d in zip(df.animal, df.day)]
    pre_dates = behavior_pre_dates(PathResolver())
    base = df.apply(lambda r: r.date in pre_dates[r.animal], axis=1)
    rows = []
    for an in animals:
        s = df[df.animal == an]
        used = sorted(s[base.loc[s.index]].date)
        rows.append({"animal": an, "behavior_pre_sessions": " ".join(d.strftime("%m%d") for d in sorted(pre_dates[an])),
                     "n_behavior_pre": len(pre_dates[an]),
                     "weight_days_used": " ".join(d.strftime("%m%d") for d in used), "n_weight_base": len(used),
                     "behavior_pre_without_weight": " ".join(d.strftime("%m%d") for d in sorted(pre_dates[an] - set(used))),
                     "n_old_pre_days": int((s.day <= 0).sum()),
                     "old_first_pre_day": int(s[s.day <= 0].day.min()),
                     "old_vs_new_baseline_g": float(s[s.day <= 0].g.mean() - s[base.loc[s.index]].g.mean())})
    bd = pd.DataFrame(rows)
    print(bd.to_string(index=False))
    keep = (df.day > 0) | base
    df = df[keep].copy()
    df["pct"] = 100 * df.g / df.animal.map(df[df.day <= 0].groupby("animal").g.mean())
    eb = pd.read_csv(a.epoch_table).set_index("animal")
    bounds = {an: (int(eb.loc[an, "acute_max_stamped"]), int(eb.loc[an, "chronic_min_stamped"])) for an in animals}
    df["epoch"] = bw.assign_epochs(df, bounds)
    df["group"] = df.animal.map(lambda an: REMAP.get(info[an].recovery_phenotype, info[an].recovery_phenotype))
    t = bw.epoch_tests_c2_aligned(df, n_boot=a.n_boot)
    old = pd.read_csv(a.old_unified, keep_default_na=False)
    oc = ["nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_q", "star", "n_pre_days", "n_post_days"]
    t = t.merge(old[["group", "epoch"] + oc].rename(columns={c: "old_" + c for c in oc}), on=["group", "epoch"],
                how="left")
    # nadir / chronic level (animal-mean of daily pct within grade x epoch, and lowest animal-day)
    am = df.groupby(["group", "animal", "epoch"]).pct.mean().reset_index()
    t = t.merge(am.groupby(["group", "epoch"]).pct.mean().rename("animal_mean_pct").reset_index(), on=["group", "epoch"])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    t.to_csv(outs["c1_weight_epoch_behavbase_ps47d5"], index=False)
    df.assign(date=df.date.astype(str)).to_csv(outs["c1_weight_days_behavbase_ps47d5"], index=False)
    bd.to_csv(outs["c1_weight_baseline_days"], index=False)
    pd.set_option("display.width", 250)
    print(t[["group", "epoch", "n_pre_days", "n_post_days", "nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_q", "star",
             "old_nb_effect", "old_nb_ci_lo", "old_nb_ci_hi", "old_mwu_q", "old_star", "animal_mean_pct"]].round(4)
          .to_string(index=False))
    mn = df[df.day > 0].groupby("animal").pct.min()
    print("lowest post-stroke day (% of new baseline) per animal:\n" + mn.round(1).to_string())
    print("wrote", a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
