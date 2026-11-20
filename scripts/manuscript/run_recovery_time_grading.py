#!/usr/bin/env python
"""Two-tone severity grading by time to return of contralesional correct licking.

Writes, under ``pipeline_outputs/stats/results/recovery_time/``:

- ``recovery_time_per_animal.csv``: per animal, the first post-stroke day on
  which correct contralesional licks per trial (``num_correct_licks_per_trial_rw``,
  cue + 70 ms to + 8 s) reach 25 / 50 / 75 % of the mean of the last five
  pre-stroke sessions (censored flag when never reached);
- ``recovery_time_kmeans_log_days.csv``: k-means (k = 3) on log days at each
  threshold vs the 3-tier grade.

Definitions: ``stroke_orofacial.stats.recovery_time`` (manuscript v41 Fig 1D,
DECISIONS 2026-11-19). Refuses to overwrite existing outputs.

Usage:
    python scripts/manuscript/run_recovery_time_grading.py [--filter no_filter] [--out-suffix S]
"""
from __future__ import annotations

import argparse
import sys

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import recovery_time as rt

# Same 3-tier remap as the phenotype-pooled stats (moderate-severe PS51 -> moderate).
PHENOTYPE_REMAP_3TIER = {"moderate-severe": "moderate"}
GRADE_ORDER = ("mild", "moderate", "severe")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--filter", default="no_filter")
    ap.add_argument("--out-suffix", default="")
    a = ap.parse_args(argv)
    tag = f"_{a.out_suffix}" if a.out_suffix else ""

    resolver = PathResolver()
    out_dir = resolver.pipeline_outputs(subdir="stats") / "results" / "recovery_time"
    f_tab = out_dir / f"recovery_time_per_animal{tag}.csv"
    f_km = out_dir / f"recovery_time_kmeans_log_days{tag}.csv"
    for p in (f_tab, f_km):
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")

    inputs = resolver.pipeline_outputs(subdir="stats") / "inputs" / a.filter / rt.ENDPOINT_SLUG
    info = load_animals()
    grades = {an: PHENOTYPE_REMAP_3TIER.get(i.recovery_phenotype, i.recovery_phenotype)
              for an, i in info.items()
              if i.stroke_date is not None and (inputs / f"{an}.parquet").exists()}
    # Row order: grade, then stroke date, then animal id (deterministic; matches #1-#8).
    order = sorted(grades, key=lambda an: (GRADE_ORDER.index(grades[an]), str(info[an].stroke_date), an))
    table = rt.recovery_time_table(inputs, {an: grades[an] for an in order})
    km = rt.kmeans_log_days(table)

    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(f_tab, index=False)
    km.to_csv(f_km, index=False)
    print(table.to_string(index=False))
    print(km.to_string(index=False))
    print(f"wrote {f_tab}\nwrote {f_km}")


if __name__ == "__main__":
    main()
