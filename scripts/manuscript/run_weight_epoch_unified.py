#!/usr/bin/env python
"""Two-tone cohort: body weight by recovery epoch with the behavior-panel statistics (Figure 1K, 2026-11-23).

Same animal-days, ``pct`` and epochs as ``run_weight_epoch_lmm.py``; the test is the c2-aligned rule of the two-tone
behavior panels (Fig 1E-I), via ``body_weight_epoch.epoch_tests_c2_aligned``: session (animal-day) Mann-Whitney U vs
pre within grade, BH-FDR over the 9 grade x epoch cells (the weight panel's own family), AND the paired nested
animals -> days bootstrap interval excluding 0 (``--n-boot`` resamples, required). The LMM table of
``run_weight_epoch_lmm.py`` is joined alongside (``lmm_*`` columns) for comparison.

Writes under ``--out-dir`` (refuses to overwrite):
- ``c1_weight_epoch_unified<tag>.csv``: one row per grade x epoch.

Usage:
    python scripts/manuscript/run_weight_epoch_unified.py <Stroke_quantification.xlsx> --out-dir DIR --n-boot 4000
        [--epoch-table CSV] [--out-suffix S]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from stroke_orofacial.animals import load_animals
from stroke_orofacial.stats import body_weight_epoch as bw

PHENOTYPE_REMAP_3TIER = {"moderate-severe": "moderate"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--n-boot", required=True, type=int)
    ap.add_argument("--epoch-table", default=None)
    ap.add_argument("--out-suffix", default="")
    a = ap.parse_args(argv)
    tag = f"_{a.out_suffix}" if a.out_suffix else ""
    out = a.out_dir / f"c1_weight_epoch_unified{tag}.csv"
    if out.exists():
        sys.exit(f"refusing to overwrite {out}")

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
    t = bw.epoch_tests_c2_aligned(df, n_boot=a.n_boot)
    lmm = bw.lmm_epoch_by_grade(df).rename(columns={"diff_pct": "lmm_diff_pct", "ci_lo": "lmm_ci_lo",
                                                     "ci_hi": "lmm_ci_hi", "p": "lmm_p", "q": "lmm_q",
                                                     "stars": "lmm_stars"})
    t = t.merge(lmm, on=["group", "epoch"], how="left")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    t.to_csv(out, index=False)
    cols = ["group", "epoch", "n_animals", "nb_effect", "nb_ci_lo", "nb_ci_hi", "mwu_p", "mwu_q", "star", "boot_only",
            "lmm_q", "lmm_stars"]
    print(t[cols].round(4).to_string(index=False))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
