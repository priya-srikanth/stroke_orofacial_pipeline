#!/usr/bin/env python
"""Compute per-animal stroke-severity (integrated deficit burden) and plot it.

FaceRhythm-independent severity from the spout ``licks_and_rewards`` outputs.
Writes a CSV + a log-log contra-vs-ipsi burden figure to
``pipeline_outputs/severity/`` (a new output dir; never overwrites existing trees).

Usage:
    conda activate stroke_orofacial
    python scripts/run_severity_burden.py
"""
from __future__ import annotations

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.severity import cohort_burden, cohort_grade


def main() -> None:
    resolver = PathResolver()
    animals = [a for a, info in load_animals().items() if info.stroke_date is not None]
    results = cohort_burden(animals, resolver)

    out_dir = resolver.pipeline_outputs(subdir="severity")
    out_dir.mkdir(parents=True, exist_ok=True)

    # CSV (null-floor-corrected burdens + focal contralesional-specific deficit)
    with open(out_dir / "deficit_burden.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["animal", "laser_mW", "contra_burden", "ipsi_burden",
                    "contra_burden_raw", "ipsi_burden_raw", "focal_deficit",
                    "lateralization", "n_post"])
        for r in sorted(results, key=lambda r: -r.focal_deficit):
            w.writerow([r.animal, r.stroke_laser_power_mW, round(r.contra_burden, 2),
                        round(r.ipsi_burden, 2), round(r.contra_burden_raw, 2),
                        round(r.ipsi_burden_raw, 2), round(r.focal_deficit, 2),
                        round(r.lateralization, 2), r.n_post])

    floor = 0.3
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    # A: corrected contra vs ipsi burden (severity space)
    ax = axes[0]
    for r in results:
        lp = r.stroke_laser_power_mW or 2.0
        ax.scatter(max(r.ipsi_burden, floor), max(r.contra_burden, floor),
                   s=80 + (lp - 2) * 70, color=plt.cm.viridis((lp - 2.2) / 2.8),
                   edgecolor="k", zorder=3)
        ax.annotate(f"{r.animal} ({lp}mW)", (max(r.ipsi_burden, floor), max(r.contra_burden, floor)),
                    fontsize=8.5, xytext=(5, 4), textcoords="offset points")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.plot([floor, 90], [floor, 90], ":", color="gray", label="contra=ipsi (bilateral)")
    ax.set_xlim(floor, 100); ax.set_ylim(floor, 100)
    ax.set_xlabel("ipsilesional deficit burden (deficit-days, log)")
    ax.set_ylabel("contralesional deficit burden (deficit-days, log)")
    ax.set_title("A. Null-floor-corrected deficit burden per side\n"
                 "above diagonal = focal contra; on diagonal = bilateral", fontsize=10)
    ax.legend(loc="lower right")
    # B: focal (contralesional-specific) deficit ranking
    ax = axes[1]
    rs = sorted(results, key=lambda r: r.focal_deficit)
    ax.barh(range(len(rs)), [r.focal_deficit for r in rs],
            color=[plt.cm.viridis(((r.stroke_laser_power_mW or 2.0) - 2.2) / 2.8) for r in rs])
    ax.set_yticks(range(len(rs)))
    ax.set_yticklabels([f"{r.animal} ({r.stroke_laser_power_mW}mW)" for r in rs])
    ax.set_xlabel("focal contralesional-specific deficit (contra − ipsi, deficit-days)")
    ax.set_title("B. Stroke-specific (lateralized) severity\nbilateral/engagement cancels → PS49 ≈ 0", fontsize=10)
    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(2.2, 5.0))
    plt.colorbar(sm, ax=axes, label="laser power (mW)", fraction=0.025)
    fig.savefig(out_dir / "severity_deficit_burden_log.png", dpi=140, bbox_inches="tight")

    # Composite clinical grade (3 spout axes) — reproduces the clinical grading
    grades = cohort_grade(animals, resolver)
    order = {"mild": 0, "moderate": 1, "mod-severe": 2, "severe": 3}
    with open(out_dir / "severity_grade.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["animal", "bilateral_cessation_days", "contra_absent_days",
                    "contra_persistence", "grade"])
        for g in sorted(grades, key=lambda g: (order[g.grade], g.contra_absent_days)):
            w.writerow([g.animal, g.bilateral_cessation_days, g.contra_absent_days,
                        round(g.contra_persistence, 2), g.grade])
            print(f"  {g.animal}: {g.grade} (cessation={g.bilateral_cessation_days}d, "
                  f"contra-absent={g.contra_absent_days}d, persistence={g.contra_persistence:.2f})")
    print(f"wrote {out_dir}/deficit_burden.csv, severity_grade.csv, severity_deficit_burden_log.png")


if __name__ == "__main__":
    main()
