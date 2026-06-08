#!/usr/bin/env python
"""Generate the composite severity-grade figures for BOTH grading schemes.

Produces, for the 3-tier and 4-tier schemes (see
:func:`stroke_orofacial.severity._grade`), a reproducible figure set from the
spout ``licks_and_rewards`` data — replacing the earlier ad-hoc Cowork figures
that had no committed producer:

  - ``severity_composite_axes_{scheme}.png`` : the three grading axes
    (A = bilateral-cessation days, B = contra-absent days, C = contra
    persistence) per animal, bars coloured by grade.
  - ``severity_2axis_map_{scheme}.png``      : the 2-axis severity map
    (x = bilateral cessation, y = contra-only deficit, marker size = contra
    persistence), coloured by grade.
  - ``severity_clusters_{scheme}.png``       : unsupervised k-means clustering of
    animals in the standardized severity-axis + burden space, to compare the
    data-driven grouping against the rule-based grade.

Writes to ``pipeline_outputs/severity/`` (a new output dir; never overwrites
existing trees). The stamped ``animals.yaml`` ``recovery_phenotype`` field is the
authoritative 4-tier label; this figure set visualizes the *behavioral*
grade for both schemes.

Usage:
    conda activate stroke_orofacial
    python scripts/run_severity_figures.py
"""
from __future__ import annotations

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.cluster.vq import kmeans2, whiten

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.severity import (
    GRADING_SCHEMES,
    cohort_burden,
    cohort_grade,
)

# Stable grade -> colour map (covers both schemes; "mod-severe" only in 4-tier).
GRADE_COLOR = {
    "mild": "#4575b4",
    "moderate": "#fdae61",
    "mod-severe": "#f46d43",
    "severe": "#d73027",
}
GRADE_ORDER = {"mild": 0, "moderate": 1, "mod-severe": 2, "severe": 3}


def _composite_axes_fig(grades, scheme: str, out_dir) -> None:
    """Per-animal A / B / C bars, coloured by grade."""
    gs = sorted(grades, key=lambda g: (GRADE_ORDER[g.grade], g.contra_absent_days))
    names = [g.animal for g in gs]
    colors = [GRADE_COLOR[g.grade] for g in gs]
    y = np.arange(len(gs))
    fig, axes = plt.subplots(1, 3, figsize=(13, 0.5 * len(gs) + 2), sharey=True)
    for ax, (vals, title) in zip(axes, [
        ([g.bilateral_cessation_days for g in gs], "A — bilateral cessation (days)"),
        ([g.contra_absent_days for g in gs], "B — contra-absent (days)"),
        ([g.contra_persistence for g in gs], "C — contra persistence (end deficit)"),
    ]):
        ax.barh(y, vals, color=colors, edgecolor="k", linewidth=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(names)
        ax.set_title(title, fontsize=10)
        ax.invert_yaxis()
    handles = [plt.Line2D([], [], marker="s", ls="", color=GRADE_COLOR[g],
                          label=g) for g in GRADE_ORDER if any(x.grade == g for x in gs)]
    fig.legend(handles=handles, loc="upper center", ncol=4, fontsize=9,
               bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(f"Severity grading axes — {scheme}", y=1.06, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_dir / f"severity_composite_axes_{scheme}.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def _2axis_map_fig(grades, scheme: str, out_dir) -> None:
    """x = bilateral cessation, y = contra-absent, size = persistence, colour = grade."""
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    for g in grades:
        ax.scatter(g.bilateral_cessation_days, g.contra_absent_days,
                   s=60 + 320 * g.contra_persistence, color=GRADE_COLOR[g.grade],
                   edgecolor="k", alpha=0.85, zorder=3)
        ax.annotate(g.animal, (g.bilateral_cessation_days, g.contra_absent_days),
                    fontsize=9, xytext=(5, 4), textcoords="offset points")
    ax.set_xlabel("A — bilateral cessation days (→ severe)")
    ax.set_ylabel("B — contra-only deficit days (→ moderate)")
    ax.set_title(f"Severity 2-axis map — {scheme}\n(marker size ∝ contra persistence C)", fontsize=11)
    handles = [plt.Line2D([], [], marker="o", ls="", color=GRADE_COLOR[g], label=g,
                          markeredgecolor="k")
               for g in GRADE_ORDER if any(x.grade == g for x in grades)]
    ax.legend(handles=handles, loc="lower right", title="grade")
    ax.margins(0.12)
    fig.tight_layout()
    fig.savefig(out_dir / f"severity_2axis_map_{scheme}.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def _clusters_fig(grades, burdens, scheme: str, out_dir) -> None:
    """Unsupervised k-means in [A, B, C, contra_burden, focal_deficit] space.

    Compares the data-driven clustering (marker shape) against the rule-based
    grade (colour). k = number of tiers present in the scheme.
    """
    bmap = {b.animal: b for b in burdens}
    gs = [g for g in grades if g.animal in bmap]
    feats = np.array([[g.bilateral_cessation_days, g.contra_absent_days,
                       g.contra_persistence, bmap[g.animal].contra_burden,
                       bmap[g.animal].focal_deficit] for g in gs], dtype=float)
    k = len({g.grade for g in gs})
    W = whiten(feats) if feats.shape[0] > k else feats
    _, labels = kmeans2(W, k, minit="++", seed=0) if feats.shape[0] >= k else (None, np.zeros(len(gs), int))
    markers = ["o", "s", "^", "D", "v"]
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    for g, lab in zip(gs, labels):
        ax.scatter(g.bilateral_cessation_days, g.contra_absent_days,
                   marker=markers[int(lab) % len(markers)], s=140,
                   color=GRADE_COLOR[g.grade], edgecolor="k", zorder=3)
        ax.annotate(g.animal, (g.bilateral_cessation_days, g.contra_absent_days),
                    fontsize=9, xytext=(5, 4), textcoords="offset points")
    ax.set_xlabel("A — bilateral cessation days")
    ax.set_ylabel("B — contra-only deficit days")
    ax.set_title(f"Severity clustering — {scheme}\ncolour = rule grade, marker = k-means cluster (k={k})",
                 fontsize=11)
    handles = [plt.Line2D([], [], marker="o", ls="", color=GRADE_COLOR[g], label=g,
                          markeredgecolor="k")
               for g in GRADE_ORDER if any(x.grade == g for x in gs)]
    ax.legend(handles=handles, loc="lower right", title="grade")
    ax.margins(0.12)
    fig.tight_layout()
    fig.savefig(out_dir / f"severity_clusters_{scheme}.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    resolver = PathResolver()
    animals = [a for a, info in load_animals().items() if info.stroke_date is not None]
    burdens = cohort_burden(animals, resolver)
    out_dir = resolver.pipeline_outputs(subdir="severity")
    out_dir.mkdir(parents=True, exist_ok=True)

    for scheme in GRADING_SCHEMES:
        grades = cohort_grade(animals, resolver, scheme=scheme)
        # comparison CSV per scheme
        with open(out_dir / f"severity_grade_{scheme}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["animal", "bilateral_cessation_days", "contra_absent_days",
                        "contra_persistence", "grade"])
            for g in sorted(grades, key=lambda g: (GRADE_ORDER[g.grade], g.contra_absent_days)):
                w.writerow([g.animal, g.bilateral_cessation_days, g.contra_absent_days,
                            round(g.contra_persistence, 2), g.grade])
        _composite_axes_fig(grades, scheme, out_dir)
        _2axis_map_fig(grades, scheme, out_dir)
        _clusters_fig(grades, burdens, scheme, out_dir)
        print(f"[{scheme}] " + ", ".join(f"{g.animal}:{g.grade}" for g in
                                          sorted(grades, key=lambda g: GRADE_ORDER[g.grade])))
    print(f"wrote severity_{{composite_axes,2axis_map,clusters}}_{{3tier,4tier}}.png "
          f"+ severity_grade_{{3tier,4tier}}.csv to {out_dir}")


if __name__ == "__main__":
    main()
