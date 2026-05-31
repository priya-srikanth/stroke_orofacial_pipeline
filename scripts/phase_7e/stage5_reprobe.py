"""Stage 5 re-probe (CC #6, read-only): confirm the substrate fix drove the
v7-rejected artifact contribution to ~0 cohort-wide.

Two measures, per (phenotype, epoch, side=contra=R), signal=y_centered:
  (A) Cell membership v2 (pre-fix) vs v3 (post-fix) from
      per_trial_trajectory_scalar.csv. The pre-fix diagnostic (PR #162) showed
      the suspect acute cells were ~92-94% v7-rejected protrusions; if the fix
      worked those trials drop out -> v3 counts collapse for severe/mod-severe
      acute, while mild/moderate stay ~stable.
  (B) v7-rejected% among the SURVIVING v3 trials: build the (now-fixed) bundle,
      take each trial's first v7 peak, and check whether that peak's session
      frame is is_baseline_fill in the v7 cleaned trace. Post-fix the bundle
      reads the cleaned trace, so survivors' peaks should be on kept (non-fill)
      frames -> v7-rejected% ~0. Sampled to bound runtime.

Writes stats/sensitivity/stage5_reprobe_report.md. No writes elsewhere.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
    _trial_arrays,
    build_tongue_visual_bundle_by_animal_date,
)
from stroke_orofacial.paths import PathResolver

PHENO_ANIMALS = {
    "mild": ["PS47", "PS48", "PS49", "PS50"], "moderate": ["PS46"],
    "moderate-severe": ["PS51"], "severe": ["PS54", "PS55"],
}
ANIMAL_PHENO = {a: p for p, ans in PHENO_ANIMALS.items() for a in ans}
SIDE = "R"
SIGNAL = "y_centered"
FPS = 250.0
SAMPLE_PER_CELL = 40       # cap survivors checked per cell (bundle build cost)
RNG_SEED = 0
# PR #162 pre-fix v7-rejected% (contra acute), for the before/after table.
PREFIX_REJECTED = {"moderate-severe": "92% (11/12)", "severe": "94% (120/127)",
                   "mild": "0.5%", "moderate": "2%"}


def _roster(resolver, version):
    csv = (resolver.pipeline_outputs().parent
           / "stats/results/phenotype_pooled/phase_aligned_trajectories/4_tier"
           / version / "per_trial_trajectory_scalar.csv")
    if not csv.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv)
    df = df[(df["side"] == SIDE) & (df["signal"] == SIGNAL)][
        ["animal", "date", "trial_index", "epoch_label"]].drop_duplicates()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["phenotype"] = df["animal"].map(ANIMAL_PHENO)
    return df


def _first_peak_rejected(session_cache, resolver, animal, date, trial):
    """Return True if the trial's first v7 peak frame is baseline-fill in the
    cleaned trace (i.e. a v7-rejected protrusion still feeding the bundle)."""
    key = (animal, date)
    if key not in session_cache:
        bundle = build_tongue_visual_bundle_by_animal_date(animal, date, resolver)
        cleaned = pd.read_parquet(
            resolver.cleaned_trace("tongue", animal, date)
        ).set_index("frame_idx").sort_index()
        # tone frame via the bundle's df_trials t_ms axis is relative; use the
        # peak's session frame from cleaned trace alignment: derive tone frame
        # by matching the bundle build (reuse trial_events).
        from stroke_orofacial.animals import get_animal
        from stroke_orofacial.manifest import build_manifest
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            _derive_trial_events_from_spout_behavior,
        )
        info = get_animal(animal)
        man = build_manifest(animal, date, resolver, info,
                             analysis_context="dlc.kinematics.tongue_pertrial")
        ev = _derive_trial_events_from_spout_behavior(
            animal=animal, date=date, resolver=resolver, manifest=man)
        tone = {(e.trial_index, e.side): e.tone_frame_idx for e in ev}
        session_cache[key] = (bundle, cleaned, tone)
    bundle, cleaned, tone = session_cache[key]
    pk = bundle.df_bouts[(bundle.df_bouts.trial_index == trial)
                         & (bundle.df_bouts.side == SIDE)
                         & (bundle.df_bouts.peak_t_ms.notna())]
    peaks = sorted(float(v) for v in pk.peak_t_ms.to_numpy())
    if not peaks:
        return None  # no bundle peak -> trial drops (not a rejected contributor)
    t0 = tone.get((trial, SIDE))
    if t0 is None:
        return None
    pf = int(t0 + round(peaks[0] / 1000.0 * FPS))
    if not (cleaned.index.min() <= pf <= cleaned.index.max()):
        return None
    return bool(cleaned.loc[pf, "is_baseline_fill"])


def main():
    resolver = PathResolver()
    out = resolver.pipeline_outputs().parent / "stats" / "sensitivity"
    out.mkdir(parents=True, exist_ok=True)
    v2 = _roster(resolver, "v2")
    v3 = _roster(resolver, "v3")

    cells = ["mild", "moderate", "moderate-severe", "severe"]
    rng = np.random.default_rng(RNG_SEED)
    session_cache: dict = {}
    rows = []
    for pheno in cells:
        for epoch in ["pre", "acute", "sub_acute", "chronic"]:
            v2n = len(v2[(v2.phenotype == pheno) & (v2.epoch_label == epoch)]) if len(v2) else 0
            sub = v3[(v3.phenotype == pheno) & (v3.epoch_label == epoch)] if len(v3) else pd.DataFrame()
            v3n = len(sub)
            rej = checked = nopeak = 0
            if v3n:
                take = sub if v3n <= SAMPLE_PER_CELL else sub.iloc[
                    np.sort(rng.choice(v3n, SAMPLE_PER_CELL, replace=False))]
                for _, r in take.iterrows():
                    res = _first_peak_rejected(session_cache, resolver,
                                               r.animal, r.date, int(r.trial_index))
                    if res is None:
                        nopeak += 1
                        continue
                    checked += 1
                    rej += int(res)
            rows.append({
                "phenotype": pheno, "epoch": epoch,
                "v2_trials": v2n, "v3_trials": v3n,
                "v3_checked": checked, "v3_rejected": rej,
                "v3_rejected_pct": (100.0 * rej / checked) if checked else np.nan,
            })
            print(f"{pheno:16s} {epoch:9s} v2={v2n:4d} v3={v3n:4d} "
                  f"checked={checked:3d} rejected={rej:3d}")
    df = pd.DataFrame(rows)
    df.to_csv(out / "stage5_reprobe_table.csv", index=False)

    L = ["# Stage 5 re-probe — substrate fix v7-rejected% verdict\n",
         "Read-only. Contra (side R), signal y_centered. Per (phenotype, epoch):\n",
         "v2_trials = pre-fix cell membership; v3_trials = post-fix; "
         "v3_rejected_pct = % of SAMPLED v3 survivors whose first v7 peak is "
         "is_baseline_fill in the cleaned trace (should be ~0 post-fix).\n",
         "## Acute cells (the diagnostic targets)\n",
         "| phenotype | v2 trials | v3 trials | pre-fix v7-rejected% (PR#162) | post-fix v3-survivor v7-rejected% |",
         "|---|---|---|---|---|"]
    for _, r in df[df.epoch == "acute"].iterrows():
        pct = "n/a (0 trials)" if not r.v3_checked else f"{r.v3_rejected_pct:.0f}%"
        L.append(f"| {r.phenotype} | {int(r.v2_trials)} | {int(r.v3_trials)} | "
                 f"{PREFIX_REJECTED.get(r.phenotype,'?')} | {pct} |")
    L.append("\n## All epochs — cell membership v2 -> v3 + v3-survivor rejected%\n")
    L.append("```\n" + df.to_string(index=False) + "\n```\n")
    (out / "stage5_reprobe_report.md").write_text("\n".join(L), encoding="utf-8")
    print("WROTE", out / "stage5_reprobe_report.md")


if __name__ == "__main__":
    main()
