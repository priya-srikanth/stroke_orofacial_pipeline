#!/usr/bin/env python
"""Derive recovery-epoch boundaries and validate them against the hand stamps.

Reproduces the per-animal acute / sub-acute / chronic boundaries stamped in
``configs/animals.yaml`` from the already-computed stats inputs, using
:func:`stroke_orofacial.stats.epoch_derivation.derive_epoch_boundaries`.
Writes a comparison CSV and a per-animal criterion figure to
``pipeline_outputs/epochs/`` (a new output dir; never overwrites existing
trees). The stamped ``animals.yaml`` values remain authoritative — this is a
documented re-derivation / cross-check.

Usage:
    conda activate stroke_orofacial
    python scripts/run_epoch_derivation.py
"""
from __future__ import annotations

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import epoch_derivation as ed

_COMPONENT_STYLE = {
    "contra_accuracy": ("contra accuracy", "-"),
    "contra_lick_count": ("contra lick count", "--"),
    "d_prime": ("d′", ":"),
}
_REGION = {"pre": "#d9d9d9", "acute": "#fb8072", "sub": "#ffd92f", "chr": "#66c2a5"}


def _combined_index(animal: str, resolver: PathResolver, filter_name: str):
    """Recompute the (per-component, combined) normalized index for plotting."""
    raw = {
        "contra_accuracy": ed._contra_series(resolver, filter_name, ed._METRIC_ACCURACY, animal, "contra"),
        "contra_lick_count": ed._contra_series(resolver, filter_name, ed._METRIC_COUNT, animal, "contra"),
        "d_prime": ed._session_series(resolver, filter_name, ed._METRIC_DPRIME, animal),
    }
    comps = {k: ed._normalize_to_baseline(v) for k, v in raw.items() if v is not None}
    comps = {k: v for k, v in comps.items() if v is not None}
    all_days = sorted(set().union(*[set(s.index) for s in comps.values()]))
    combined = pd.concat(comps.values(), axis=1).reindex(all_days).mean(axis=1)
    return comps, combined


def main() -> None:
    resolver = PathResolver()
    filter_name = "no_filter"
    animals_info = {a: i for a, i in load_animals().items() if i.stroke_date is not None}
    animals = sorted(animals_info)

    out_dir = resolver.pipeline_outputs(subdir="epochs")
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- comparison CSV ----------------------------------------------------
    rows = []
    for a in animals:
        try:
            d = ed.derive_epoch_boundaries(a, resolver, filter_name=filter_name)
        except FileNotFoundError:
            continue
        eb = animals_info[a].epoch_boundaries
        rows.append({
            "animal": a,
            "phenotype": animals_info[a].recovery_phenotype,
            "acute_max_stamped": eb.acute_max_rel_day,
            "acute_max_derived": d.acute_max_rel_day,
            "subacute_max_stamped": eb.subacute_max_rel_day,
            "subacute_max_derived": d.subacute_max_rel_day,
            "chronic_min_stamped": eb.chronic_min_rel_day,
            "chronic_min_derived": d.chronic_min_rel_day,
            "subacute_days_derived": d.subacute_days,
            "onset": d.onset_rel_day,
            "plateau": d.plateau_rel_day,
        })
    with open(out_dir / "derived_epoch_boundaries.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"  {r['animal']} ({r['phenotype']}): "
              f"acute {r['acute_max_stamped']}->{r['acute_max_derived']}, "
              f"chronic {r['chronic_min_stamped']}->{r['chronic_min_derived']} "
              f"(subacute {r['subacute_days_derived']}d)")

    # --- per-animal criterion figure --------------------------------------
    n = len(rows)
    ncol = 4
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(5 * ncol, 4.75 * nrow), sharey=True)
    for ax, r in zip(axes.flat, rows):
        a = r["animal"]
        comps, combined = _combined_index(a, resolver, filter_name)
        rd = combined.index.values
        am, sc = r["acute_max_derived"], r["chronic_min_derived"]
        sa, ssc = r["acute_max_stamped"], r["chronic_min_stamped"]
        xmax = rd.max() + 2
        ax.axvspan(rd.min() - 1, 0, color=_REGION["pre"], alpha=.5)
        ax.axvspan(0, am + 0.5, color=_REGION["acute"], alpha=.45)
        ax.axvspan(am + 0.5, sc - 0.5, color=_REGION["sub"], alpha=.45)
        ax.axvspan(sc - 0.5, xmax, color=_REGION["chr"], alpha=.4)
        # Plot the full trajectory including the pre-stroke baseline (rel_day
        # <= 0); normalized to baseline it sits ~1.0 pre-stroke, then drops and
        # recovers, showing deficit depth in context.
        for key, (label, style) in _COMPONENT_STYLE.items():
            if key not in comps:
                continue
            p = comps[key]
            ax.plot(p.index, p.values, style, color="#555", lw=1, alpha=.5)
        ax.plot(combined.index, combined.values, "-", color="#08306b", lw=2.6)
        ax.axhline(ed.ACUTE_RECOVERY_FRAC, color="r", lw=.8, ls=":", alpha=.5)
        ax.axhline(1.0, color="#777", lw=.7, alpha=.35)
        ax.axvline(0, color="k", lw=.8, alpha=.5)
        ax.axvline(sa + 0.5, color="k", lw=1.5)
        ax.axvline(ssc - 0.5, color="k", lw=1.5)
        ax.set_title(f"{a} ({r['phenotype']})\nacute≤{am} (stamp {sa}) · "
                     f"chronic≥{sc} (stamp {ssc})", fontsize=10.5)
        ax.set_xlim(rd.min() - 1, xmax)
        ax.set_ylim(-0.25, 1.35)
        ax.set_xlabel("days from stroke")
    for ax in axes[:, 0] if nrow > 1 else [axes[0]]:
        ax.set_ylabel("recovery (fraction of baseline)")
    for ax in axes.flat[n:]:
        ax.axis("off")
    legend = [
        Patch(fc=_REGION["pre"], label="pre"),
        Patch(fc=_REGION["acute"], label="acute (derived)"),
        Patch(fc=_REGION["sub"], label="subacute (derived)"),
        Patch(fc=_REGION["chr"], label="chronic (derived)"),
        plt.Line2D([], [], color="k", lw=1.5, label="stamped boundary"),
        plt.Line2D([], [], color="#08306b", lw=2.6, label="combined index"),
        plt.Line2D([], [], color="#777", lw=.7, label="baseline (1.0)"),
        plt.Line2D([], [], color="#555", lw=1, ls="-", label="contra accuracy"),
        plt.Line2D([], [], color="#555", lw=1, ls="--", label="contra lick count"),
        plt.Line2D([], [], color="#555", lw=1, ls=":", label="d′"),
        plt.Line2D([], [], color="r", lw=.8, ls=":", label="30% acute threshold"),
    ]
    fig.legend(handles=legend, loc="upper center", ncol=5, fontsize=10,
               bbox_to_anchor=(0.5, 1.01))
    fig.suptitle("Recovery-epoch criteria — combined recovery index "
                 "(contra accuracy + contra lick-count + d′) with derived epoch "
                 "regions vs hand-stamped boundaries (black lines)",
                 y=1.04, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_dir / "epoch_criteria.png", dpi=145, bbox_inches="tight")
    print(f"wrote {out_dir}/derived_epoch_boundaries.csv, epoch_criteria.png")


if __name__ == "__main__":
    main()
