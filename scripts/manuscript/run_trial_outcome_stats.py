#!/usr/bin/env python
"""Two-tone cohort: cued-trial outcome classes and their change from pre-stroke (Figure 2B).

Writes under ``pipeline_outputs/stats/results/trial_outcomes/``:

- ``c1_trial_classes<tag>.csv``: one row per cued trial (class definitions in
  ``stroke_orofacial.stats.trial_outcomes``), with ``epoch`` (from
  ``configs/animals.yaml``) and 3-tier ``grp``;
- ``c1_trial_outcome_mwu_bh<tag>.csv``: session MWU vs pre, BH over all
  grade x side x epoch x class tests;
- ``c1_trial_outcome_fractions<tag>.csv``: mean over animals of each animal's
  per-epoch class fractions (the bar heights) with n animals.

Reads ``spout_behavior/licks_and_rewards`` and
``dlc_kinematics/tongue_jaw_mismatch/candidate_trials`` (read-only). Refuses to
overwrite.

Usage:
    python scripts/manuscript/run_trial_outcome_stats.py [--out-suffix S]
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import trial_outcomes as to
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label

PHENOTYPE_REMAP_3TIER = {"moderate-severe": "moderate"}
CUE_SIDE_TO_LESION = {"R": "contra", "L": "ipsi"}   # left-hemisphere strokes: right cue = contralesional
EPOCH_NAME = {"pre": "pre", "acute": "acute", "sub_acute": "subacute", "chronic": "chronic"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-suffix", default="")
    a = ap.parse_args(argv)
    tag = f"_{a.out_suffix}" if a.out_suffix else ""
    r = PathResolver()
    out_dir = r.pipeline_outputs(subdir="stats") / "results" / "trial_outcomes"
    outs = [out_dir / f"c1_trial_classes{tag}.csv", out_dir / f"c1_trial_outcome_mwu_bh{tag}.csv",
            out_dir / f"c1_trial_outcome_fractions{tag}.csv"]
    clash = [str(p) for p in outs if p.exists()]
    if clash:
        sys.exit(f"refusing to overwrite {', '.join(clash)}")

    info = load_animals()
    cand_root = r.pipeline_outputs(subdir="dlc_kinematics") / "tongue_jaw_mismatch" / "candidate_trials"
    lr_root = r.pipeline_outputs(subdir="spout_behavior") / "licks_and_rewards"
    frames = []
    for pq in sorted(cand_root.glob("PS*/*.parquet")):
        animal, date = pq.parent.name, pq.name[:8]
        nz = lr_root / animal / f"{date}.npz"
        if not nz.exists():
            continue
        d = to.classify_session(nz, pd.read_parquet(pq), animal, date)
        if d is None:
            print("SKIP trial-count mismatch", animal, date)
            continue
        frames.append(d)
    trials = pd.concat(frames, ignore_index=True)
    trials = trials[trials.animal.map(lambda an: an in info and info[an].epoch_boundaries is not None)]
    trials["epoch"] = [EPOCH_NAME.get(assign_epoch_label(int(d), info[an])) for an, d in zip(trials.animal, trials.rel_day)]
    trials = trials[trials.epoch.notna()].copy()
    trials["side"] = trials.cue_side.map(CUE_SIDE_TO_LESION)
    trials["grp"] = trials.animal.map(lambda an: PHENOTYPE_REMAP_3TIER.get(info[an].recovery_phenotype,
                                                                            info[an].recovery_phenotype))
    stats = to.mwu_vs_pre(trials)

    fr = []
    for (g, s, e), d in trials.groupby(["grp", "side", "epoch"]):
        pa = d.groupby("animal").cls.value_counts(normalize=True).unstack().reindex(columns=list(to.CLASSES)).fillna(0)
        fr.append({"group": g, "side": s, "epoch": e, "n_animals": len(pa), **pa.mean(axis=0).to_dict()})

    out_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(outs[0], index=False)
    stats.to_csv(outs[1], index=False)
    pd.DataFrame(fr).to_csv(outs[2], index=False)
    print(stats[stats.star == "*"].to_string(index=False))
    for p in outs:
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
