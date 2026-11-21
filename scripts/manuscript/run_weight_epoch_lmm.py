#!/usr/bin/env python
"""Two-tone cohort: body weight by recovery epoch, linear mixed model (Figure 1F).

Writes under ``pipeline_outputs/stats/results/body_weight/``:

- ``c1_weight_epoch_days<tag>.csv``: animal-days with ``pct`` (% of pre-stroke
  mean), ``epoch`` and grade;
- ``c1_weight_epoch_lmm<tag>.csv``: the 9 epoch-vs-pre contrasts (BH q, stars);
- ``c1_weight_epoch_summary<tag>.csv``: mean +- SEM of the animals' epoch means.

Epoch boundaries: the stamped boundaries of ``configs/animals.yaml`` by
default, or the ``*_stamped`` columns of ``--epoch-table`` (e.g.
``epochs/derived_epoch_boundaries_ps47d5.csv``, as the manuscript). Stroke
dates and grades: ``configs/animals.yaml``. Refuses to overwrite.

Usage:
    python scripts/manuscript/run_weight_epoch_lmm.py <Stroke_quantification.xlsx> [--epoch-table CSV] [--out-suffix S]
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import body_weight_epoch as bw

PHENOTYPE_REMAP_3TIER = {"moderate-severe": "moderate"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx")
    ap.add_argument("--epoch-table", default=None)
    ap.add_argument("--out-suffix", default="")
    a = ap.parse_args(argv)
    tag = f"_{a.out_suffix}" if a.out_suffix else ""
    out_dir = PathResolver().pipeline_outputs(subdir="stats") / "results" / "body_weight"
    outs = [out_dir / f"c1_weight_epoch_{k}{tag}.csv" for k in ("days", "lmm", "summary")]
    clash = [str(p) for p in outs if p.exists()]
    if clash:
        sys.exit(f"refusing to overwrite {', '.join(clash)}")

    info = load_animals()
    animals = [an for _, mice in bw.WEIGHTS_BLOCKS for _, an in mice]
    df = bw.read_weights_sheet(a.xlsx, {an: info[an].stroke_date for an in animals})
    if a.epoch_table:
        eb = pd.read_csv(a.epoch_table).set_index("animal")
        bounds = {an: (int(eb.loc[an, "acute_max_stamped"]), int(eb.loc[an, "chronic_min_stamped"])) for an in animals}
    else:
        bounds = {an: (info[an].epoch_boundaries.acute_max_rel_day, info[an].epoch_boundaries.chronic_min_rel_day)
                  for an in animals}
    df["epoch"] = bw.assign_epochs(df, bounds)
    df["group"] = df.animal.map(lambda an: PHENOTYPE_REMAP_3TIER.get(info[an].recovery_phenotype,
                                                                      info[an].recovery_phenotype))
    st = bw.lmm_epoch_by_grade(df)
    am = df.groupby(["group", "animal", "epoch"]).pct.mean().reset_index()
    sm = am.groupby(["group", "epoch"]).pct.agg(["mean", "sem", "count"]).reset_index().rename(columns={"count": "n_animals"})

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(outs[0], index=False)
    st.to_csv(outs[1], index=False)
    sm.to_csv(outs[2], index=False)
    print(st.round(4).to_string(index=False))
    for p in outs:
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
