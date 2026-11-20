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

``--aligned`` (Priya 2026-11-20): instead, re-test the same Fig 2B cells under the
rule every other cohort-1 panel uses (change from each animal's own pre, session
MWU + nested animals -> sessions bootstrap, star ``**`` = BH q < 0.05 AND CI
excludes 0; ``trial_outcomes.aligned_vs_pre``). Reads the existing
``c1_trial_classes.csv`` and ``c1_trial_outcome_mwu_bh.csv`` (no re-extraction)
and writes, in the same folder, ``c1_trial_outcome_aligned<tag>.csv`` and
``c1_trial_outcome_aligned_vs_old<tag>.csv`` (old star, new star,
kept / lost / gained). Figures are not changed.

``--distribution`` (Priya 2026-11-20): ONE change-in-distribution test per Fig 2B bar
(grade x cue side x post epoch) instead of the per-class tests
(``trial_outcomes.distribution_vs_pre``: per-animal TVD of the epoch vs own-pre mean
composition, animal-weighted D, within-animal pre/epoch label permutation, exact when
<= 20,000 relabellings else 10,000 random with seed 0, BH over all bars, star_dist =
q < 0.05). Reads ``--trials-csv`` (default ``c1_trial_classes.csv``) and the aligned
per-class table ``--aligned-csv`` (default ``c1_trial_outcome_aligned.csv``) and writes
``c1_trial_outcome_distribution_test<tag>.csv`` (+ ``_per_animal``, ``_vs_aligned``).
``--jaw-flags FILE --jaw-col COL`` (with ``--distribution`` or ``--aligned``) re-splits
the no-contact, no-tongue trials into jaw_only / no_resp from a per-trial 1 / 0 / NaN
flag (parquet or csv keyed by animal, date YYYYMMDD, trial_index; NaN = unknown, the
trial is dropped; ``trial_outcomes.override_jaw_only``) before testing. With a jaw
override, pass the matching ``--aligned-csv`` to ``--distribution``.

Usage:
    python scripts/manuscript/run_trial_outcome_stats.py [--out-suffix S]
    python scripts/manuscript/run_trial_outcome_stats.py --aligned [--jaw-flags F --jaw-col C] [--out-suffix S]
    python scripts/manuscript/run_trial_outcome_stats.py --distribution [--jaw-flags F --jaw-col C]
        [--aligned-csv A] --out-suffix S
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
    ap.add_argument("--aligned", action="store_true", help="aligned-rule re-test of the existing tables")
    ap.add_argument("--trials-csv", default=None, help="--aligned input (default: c1_trial_classes.csv)")
    ap.add_argument("--old-csv", default=None, help="--aligned comparison (default: c1_trial_outcome_mwu_bh.csv)")
    ap.add_argument("--distribution", action="store_true", help="one distribution test per bar")
    ap.add_argument("--aligned-csv", default=None, help="--distribution comparison (default: c1_trial_outcome_aligned.csv)")
    ap.add_argument("--jaw-flags", default=None, help="--distribution: per-trial jaw-only flags (parquet / csv)")
    ap.add_argument("--jaw-col", default=None, help="--distribution: boolean column of --jaw-flags")
    a = ap.parse_args(argv)
    tag = f"_{a.out_suffix}" if a.out_suffix else ""
    r = PathResolver()
    out_dir = r.pipeline_outputs(subdir="stats") / "results" / "trial_outcomes"
    if (a.jaw_flags is None) != (a.jaw_col is None):
        sys.exit("--jaw-flags and --jaw-col go together")
    if a.distribution:
        return _distribution(out_dir, tag, a.trials_csv, a.aligned_csv, a.jaw_flags, a.jaw_col)
    if a.aligned:
        return _aligned(out_dir, tag, a.trials_csv, a.old_csv, a.jaw_flags, a.jaw_col)
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


def _load_trials(out_dir, trials_csv, jaw_flags, jaw_col) -> pd.DataFrame:
    """The per-trial class table, with jaw_only / no_resp re-split from --jaw-flags when given."""
    trials = pd.read_csv(trials_csv or out_dir / "c1_trial_classes.csv")
    if jaw_flags:
        fl = pd.read_parquet(jaw_flags) if str(jaw_flags).endswith(".parquet") else pd.read_csv(jaw_flags)
        n0 = len(trials)
        trials = to.override_jaw_only(trials, fl, jaw_col)
        print(f"jaw override ({jaw_col}): {n0 - len(trials)} unknown trials dropped")
        print(pd.crosstab(trials.cls_v1, trials.cls).to_string())
    return trials


def _aligned(out_dir, tag: str, trials_csv: str | None, old_csv: str | None, jaw_flags=None, jaw_col=None) -> int:
    outs = [out_dir / f"c1_trial_outcome_aligned{tag}.csv", out_dir / f"c1_trial_outcome_aligned_vs_old{tag}.csv"]
    clash = [str(p) for p in outs if p.exists()]
    if clash:
        sys.exit(f"refusing to overwrite {', '.join(clash)}")
    trials = _load_trials(out_dir, trials_csv, jaw_flags, jaw_col)
    old = pd.read_csv(old_csv or out_dir / "c1_trial_outcome_mwu_bh.csv")
    new = to.aligned_vs_pre(trials)
    cmp = to.compare_stars(old, new)
    new.to_csv(outs[0], index=False)
    cmp.to_csv(outs[1], index=False)
    print(cmp.change.value_counts().to_string())
    print(cmp[cmp.change.isin(["lost", "gained"])].to_string(index=False))
    for p in outs:
        print("wrote", p)
    return 0


def _distribution(out_dir, tag: str, trials_csv, aligned_csv, jaw_flags, jaw_col) -> int:
    base = f"c1_trial_outcome_distribution_test{tag}"
    outs = [out_dir / f"{base}.csv", out_dir / f"{base}_per_animal.csv", out_dir / f"{base}_vs_aligned.csv"]
    clash = [str(p) for p in outs if p.exists()]
    if clash:
        sys.exit(f"refusing to overwrite {', '.join(clash)}")
    trials = _load_trials(out_dir, trials_csv, jaw_flags, jaw_col)
    cells, per = to.distribution_vs_pre(trials)
    cmp = to.compare_distribution_aligned(cells, pd.read_csv(aligned_csv or out_dir / "c1_trial_outcome_aligned.csv"))
    print(per[["group", "side", "epoch", "animal", "tvd", "n_pre_sessions", "n_epoch_sessions"]].round(3).to_string(index=False))
    out_dir.mkdir(parents=True, exist_ok=True)
    cells.to_csv(outs[0], index=False)
    per.to_csv(outs[1], index=False)
    cmp.to_csv(outs[2], index=False)
    print(cmp.round(4).to_string(index=False))
    print("distribution stars:", int(cmp.star_dist.sum()), "| bars with >= 1 aligned star:",
          int(cmp.any_aligned_star.sum()), "| disagreements:", int((cmp.agree == 0).sum()))
    for p in outs:
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
