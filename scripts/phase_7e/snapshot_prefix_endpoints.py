"""Snapshot PRE-FIX tongue per-trial endpoints across the cohort, BEFORE the
substrate-fix cohort re-emit overwrites the JSONs in place.

Captures per (animal, date, trial_index, side): n_licks_family.n_licks +
phase_aligned_endpoints.peak_y_px, with epoch_label + phenotype attached.
Feeds the step-1-complete pre-vs-post delta report (Priya 2026-05-30 answer 2:
n_licks delta per (animal, epoch, side) + predicted SessionFilter pass/fail +
expected severe-acute cell-loss).

Writes ONE CSV to stats/sensitivity/substrate_fix_pilot/. Reads only.

Usage:
  python scripts/phase_7e/snapshot_prefix_endpoints.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label

COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
PHENO = {
    "PS46": "moderate", "PS47": "mild", "PS48": "mild", "PS49": "mild",
    "PS50": "mild", "PS51": "moderate-severe", "PS54": "severe", "PS55": "severe",
}


def main() -> int:
    resolver = PathResolver()
    out = (resolver.pipeline_outputs().parent / "stats" / "sensitivity"
           / "substrate_fix_pilot")
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for animal in COHORT_ORDER:
        info = get_animal(animal)
        jdir = resolver.tongue_pertrial_endpoints_dir(animal)
        if not Path(jdir).exists():
            continue
        for jp in sorted(Path(jdir).glob("*.json")):
            date = dt.datetime.strptime(jp.stem[:8], "%Y%m%d").date()
            try:
                rel_day = (date - info.stroke_date).days
                epoch = assign_epoch_label(rel_day, info)
            except Exception:  # noqa: BLE001
                epoch = None
            obj = json.load(open(jp))
            t = obj["tongue"]
            ti = obj["trial_indices"]
            sides = obj["sides"]
            nl = t["n_licks_family"]["n_licks"]
            py = t["phase_aligned_endpoints"]["peak_y_px"]
            for i, tr in enumerate(ti):
                rows.append({
                    "animal": animal,
                    "phenotype": PHENO[animal],
                    "date": date.isoformat(),
                    "epoch_label": epoch,
                    "trial_index": int(tr),
                    "side": sides[i],
                    "n_licks_pre": nl[i] if i < len(nl) else None,
                    "peak_y_px_pre": py[i] if i < len(py) else None,
                })
        print(f"  {animal}: snapshot {sum(1 for r in rows if r['animal']==animal)} trial rows")

    df = pd.DataFrame(rows)
    dst = out / "prefix_endpoints_snapshot.csv"
    df.to_csv(dst, index=False)
    print(f"WROTE {dst} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
