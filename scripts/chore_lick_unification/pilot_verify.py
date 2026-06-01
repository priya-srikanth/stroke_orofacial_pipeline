"""Lick-definition unification pilot (NON-DESTRUCTIVE).

Computes the per-trial tongue endpoints IN-MEMORY with the unified code (bout /
phase / first_peak now derive from v7 kept_licks, not raw re-detection) and
verifies INTERNAL consistency: the bout-scalar ``first_peak_t_ms`` (cell50) now
agrees with the per-lick ``lick1_t_peak_ms`` (cell33) — they were divergent
before (raw re-detect vs kept_licks). Also reports the change vs the on-disk
pre-fix endpoints. Writes only a report under stats/sensitivity/lick_unification_pilot/.

Usage:
  python scripts/chore_lick_unification/pilot_verify.py --animal PS51
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver

REPO = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from scripts.phase_7e.pilot_substrate_fix_verify import _compute_fixed_core  # noqa: E402


def _arr(d: dict, *keys) -> np.ndarray:
    cur: Any = d
    for k in keys:
        cur = cur[k]
    return np.asarray([np.nan if v is None else v for v in cur], dtype=float)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--animal", default="PS51")
    args = p.parse_args(argv)
    animal = args.animal

    resolver = PathResolver()
    params = load_defaults()
    out = (resolver.pipeline_outputs().parent / "stats" / "sensitivity"
           / "lick_unification_pilot")
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
        jpath = resolver.tongue_pertrial_endpoints_json(animal, date)
        pre = json.load(open(jpath)) if jpath.exists() else None
        try:
            core, _ = _compute_fixed_core(animal, date, resolver, params)
        except Exception as exc:  # noqa: BLE001
            print(f"  {animal} {date}: core FAILED {type(exc).__name__}: {exc}")
            continue
        new_t = core.tongue_pertrial.endpoints["tongue"]
        # NEW run: bout first_peak (cell50) vs per-lick lick1 (cell33).
        fp_new = _arr(new_t, "cell50_own_bout_scalars", "first_peak_t_ms")
        l1_new = _arr(new_t, "lick1_lick2_metrics", "lick1_t_peak_ms")
        npk_new = _arr(new_t, "cell50_own_bout_scalars", "n_peaks")
        nl_new = _arr(new_t, "n_licks_family", "n_licks")
        # PRE on-disk: bout first_peak (raw) vs the same per-lick lick1.
        fp_pre = _arr(pre["tongue"], "cell50_own_bout_scalars",
                      "first_peak_t_ms") if pre else np.full_like(fp_new, np.nan)
        n = len(fp_new)
        for i in range(n):
            rows.append({
                "animal": animal, "date": date.isoformat(), "trial": i,
                "first_peak_new": fp_new[i], "lick1_new": l1_new[i] if i < len(l1_new) else np.nan,
                "first_peak_pre": fp_pre[i] if i < len(fp_pre) else np.nan,
                "n_peaks_new": npk_new[i] if i < len(npk_new) else np.nan,
                "n_licks_new": nl_new[i] if i < len(nl_new) else np.nan,
            })
        print(f"  {animal} {date}: {n} trials computed")

    df = pd.DataFrame(rows)
    df.to_csv(out / f"pilot_{animal}.csv", index=False)

    # Consistency where lick1 is finite (first lick within cell33's [70,500] win).
    both = df.dropna(subset=["first_peak_new", "lick1_new"])
    agree_new = (both["first_peak_new"] - both["lick1_new"]).abs() < 1.0
    prev = df.dropna(subset=["first_peak_pre", "lick1_new"])
    agree_pre = (prev["first_peak_pre"] - prev["lick1_new"]).abs() < 1.0
    print(f"\n=== {animal} unification consistency ===")
    print(f"  trials (lick1 finite): {len(both)}")
    print(f"  NEW first_peak==lick1 (<1ms): {agree_new.mean()*100:.1f}%  "
          f"({int(agree_new.sum())}/{len(both)})")
    print(f"  PRE first_peak==lick1 (<1ms): {agree_pre.mean()*100:.1f}%  "
          f"({int(agree_pre.sum())}/{len(prev)})  <- raw re-detect, divergent")
    print(f"  wrote {out}/pilot_{animal}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
