"""PS51 pilot verification for the tongue substrate-routing fix (chore
tongue-substrate-v7-routing-fix, Stage 1 -> Stage 3 pilot gate).

NON-DESTRUCTIVE: computes the FIXED per-trial endpoints IN-MEMORY (via
_build_tongue_pertrial_core, the same core the emit uses) and diffs them
against the on-disk PRE-FIX endpoints JSON. Writes nothing to the production
tree — only a delta report + CSV under
``stats/sensitivity/substrate_fix_pilot/``.

Verification scope (per Priya 2026-05-30, answer 1):
  - per-trial JSON delta: phase_aligned_endpoints + cell50_own_bout_scalars
    + n_licks_family counts
  - cleaned_traces value-equality (the v7 pipeline is unchanged, so the
    in-memory cleaned trace must equal the on-disk cleaned_traces parquet)
  - lick_events value-equality (same reason)
  - eyeball: per-trial peak_y_px before/after for every PS51 session

PS51 is the diagnostic artifact case (PR #162): mod-severe acute contra,
11/12 contributing trials were v7-rejected protrusions. After the fix the
bundle reads the v7-cleaned trace, so those protrusions (wiped to baseline)
no longer produce phase-aligned peaks -> peak_y_px should drop to NaN /
the trial drops.

Usage:
  python scripts/phase_7e/pilot_substrate_fix_verify.py --animal PS51
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stroke_orofacial.animals import get_animal
from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    _build_cleaned_trace_df,
    _build_lick_events_df,
    _build_tongue_pertrial_core,
    _derive_trial_events_from_spout_behavior,
    _load_tongue_centered_trace,
    get_pre_stroke_median_ili_ms,
)
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver


def _compute_fixed_core(animal: str, date: dt.date, resolver: PathResolver, params):
    """Replicate build_tongue_*_by_animal_date setup, call core (no writes)."""
    animal_info = get_animal(animal)
    manifest = build_manifest(
        animal, date, resolver, animal_info,
        analysis_context="dlc.kinematics.tongue_pertrial",
    )
    trial_events = _derive_trial_events_from_spout_behavior(
        animal=animal, date=date, resolver=resolver, manifest=manifest,
    )
    pre_ili = get_pre_stroke_median_ili_ms(
        animal, resolver=resolver, animal_info=animal_info, params=params,
    )
    core = _build_tongue_pertrial_core(
        manifest=manifest, resolver=resolver, trial_events=trial_events,
        params=params, animal_info=animal_info,
        pre_stroke_median_ili_ms=pre_ili,
    )
    return core, manifest


def _arr(d: dict, *keys):
    cur: Any = d
    for k in keys:
        cur = cur[k]
    return np.asarray([np.nan if v is None else v for v in cur], dtype=float)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--animal", default="PS51")
    args = parser.parse_args(argv)
    animal = args.animal

    resolver = PathResolver()
    params = load_defaults()
    out = (resolver.pipeline_outputs().parent / "stats" / "sensitivity"
           / "substrate_fix_pilot")
    out.mkdir(parents=True, exist_ok=True)

    dates = yaml_driven_session_dates(animal, analysis_context="dlc")
    rows: list[dict[str, Any]] = []
    cleaned_equal: list[tuple[str, bool]] = []
    lick_events_equal: list[tuple[str, bool]] = []

    for date in dates:
        jpath = resolver.tongue_pertrial_endpoints_json(animal, date)
        if not jpath.exists():
            print(f"  {animal} {date}: no pre-fix JSON, skip")
            continue
        prefix = json.load(open(jpath))
        try:
            core, manifest = _compute_fixed_core(animal, date, resolver, params)
        except Exception as exc:  # noqa: BLE001
            print(f"  {animal} {date}: core FAILED {type(exc).__name__}: {exc}")
            rows.append({"animal": animal, "date": date.isoformat(),
                         "status": f"core_fail:{type(exc).__name__}"})
            continue
        new = core.tongue_pertrial.endpoints

        pre_t = prefix["tongue"]
        new_t = new["tongue"]
        ti = prefix["trial_indices"]
        sides = prefix["sides"]

        # phase_aligned_endpoints.peak_y_px before/after, per trial
        pre_py = _arr(pre_t, "phase_aligned_endpoints", "peak_y_px")
        new_py = _arr(new_t, "phase_aligned_endpoints", "peak_y_px")
        pre_nl = _arr(pre_t, "n_licks_family", "n_licks")
        new_nl = _arr(new_t, "n_licks_family", "n_licks")
        pre_fp = _arr(pre_t, "cell50_own_bout_scalars", "first_peak_t_ms")
        new_fp = _arr(new_t, "cell50_own_bout_scalars", "first_peak_t_ms")

        n = min(len(ti), len(pre_py), len(new_py))
        for i in range(n):
            py_pre, py_new = pre_py[i], new_py[i]
            changed = not (np.isnan(py_pre) and np.isnan(py_new)) and (
                np.isnan(py_pre) != np.isnan(py_new)
                or (np.isfinite(py_pre) and np.isfinite(py_new)
                    and abs(py_pre - py_new) > 1e-6)
            )
            rows.append({
                "animal": animal, "date": date.isoformat(),
                "trial_index": int(ti[i]), "side": sides[i],
                "peak_y_px_pre": py_pre, "peak_y_px_new": py_new,
                "peak_y_dropped_to_nan": bool(np.isfinite(py_pre) and np.isnan(py_new)),
                "n_licks_pre": pre_nl[i] if i < len(pre_nl) else np.nan,
                "n_licks_new": new_nl[i] if i < len(new_nl) else np.nan,
                "first_peak_t_ms_pre": pre_fp[i] if i < len(pre_fp) else np.nan,
                "first_peak_t_ms_new": new_fp[i] if i < len(new_fp) else np.nan,
                "peak_y_changed": changed,
            })

        # cleaned_traces / lick_events value-equality (v7 pipeline unchanged).
        interp_df, _ = _load_tongue_centered_trace(manifest, resolver)
        new_cleaned = _build_cleaned_trace_df(interp_df, core.v7_trial_results)
        prod_cleaned = pd.read_parquet(resolver.cleaned_trace("tongue", animal, date))
        c_eq = (
            new_cleaned[["x_final", "y_final", "is_baseline_fill"]]
            .reset_index(drop=True)
            .equals(
                prod_cleaned[["x_final", "y_final", "is_baseline_fill"]]
                .reset_index(drop=True)
            )
        )
        cleaned_equal.append((date.isoformat(), bool(c_eq)))

        new_le = _build_lick_events_df(animal, date, core.v7_trial_results)
        le_path = resolver.lick_events("tongue", animal, date)
        prod_le = pd.read_parquet(le_path) if le_path.exists() else pd.DataFrame()
        le_eq = len(new_le) == len(prod_le)
        lick_events_equal.append((date.isoformat(), bool(le_eq)))

        n_drop = sum(
            1 for r in rows
            if r.get("date") == date.isoformat() and r.get("peak_y_dropped_to_nan")
        )
        print(f"  {animal} {date}: {n} trials | peak_y dropped->NaN: {n_drop} "
              f"| cleaned== {c_eq} | lick_events== {le_eq}")

    df = pd.DataFrame(rows)
    df.to_csv(out / f"pilot_{animal}_per_trial_delta.csv", index=False)

    # Summary report.
    trial_rows = df[df.get("trial_index").notna()] if "trial_index" in df else df
    n_trials = len(trial_rows)
    n_changed = int(trial_rows.get("peak_y_changed", pd.Series(dtype=bool)).sum())
    n_dropped = int(trial_rows.get("peak_y_dropped_to_nan", pd.Series(dtype=bool)).sum())
    lines = [
        f"# PS{animal[2:]} substrate-fix pilot verification (NON-DESTRUCTIVE)\n",
        f"Animal: {animal} | sessions: {len(dates)} | trials compared: {n_trials}\n",
        "## peak_y_px (phase_aligned_endpoints) delta\n",
        f"- trials with changed peak_y_px: **{n_changed}/{n_trials}**\n",
        f"- trials whose peak_y_px dropped finite->NaN (v7-rejected protrusion "
        f"no longer a peak): **{n_dropped}/{n_trials}**\n",
        "\n## cleaned_traces value-equality (must be ALL True — v7 unchanged)\n",
        "".join(f"- {d}: {eq}\n" for d, eq in cleaned_equal),
        "\n## lick_events row-count equality (must be ALL True)\n",
        "".join(f"- {d}: {eq}\n" for d, eq in lick_events_equal),
        "\nPer-trial detail: `pilot_" + animal + "_per_trial_delta.csv`.\n",
    ]
    (out / f"pilot_{animal}_report.md").write_text("".join(lines), encoding="utf-8")
    print(f"\nWROTE {out}")
    print(f"  peak_y changed: {n_changed}/{n_trials}; dropped->NaN: {n_dropped}/{n_trials}")
    print(f"  cleaned== all True: {all(eq for _, eq in cleaned_equal)}")
    print(f"  lick_events== all True: {all(eq for _, eq in lick_events_equal)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
