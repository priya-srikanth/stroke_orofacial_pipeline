#!/usr/bin/env python
"""Session-level trajectory tables for the manuscript (two-tone cohort).

Writes under ``pipeline_outputs/stats/results/trajectory_sessions/``:

- ``traj``: ``c1_traj_sessions<tag>.csv`` (angle / x / y, raw and delta, first
  and all licks) from the cached ``trial_bin_substrate<tag>.parquet`` of
  ``run_within_animal_cluster_perm.py``;
- ``xy``:   ``c1_traj_xy_sessions<tag>.csv`` (xy distance from the mouth,
  computed per frame before phase binning) from the xy substrate cache
  ``v3_xy_dist/_xy_session_cache<tag>/xy_trial_bin_substrate_{first,all}.parquet``,
  rebuilt (30-60 min per lick set) and cached only when absent;
- ``path``: ``c1_path_session_sem<tag>.csv`` (first-lick 2-D path SEM across
  sessions).

``--substrate-suffix S`` selects the ``_S`` substrates (e.g. ``ps47d5``: PS47
chronic from day 5, 2026-11-19) and names the outputs ``..._S.csv``.
Summaries: ``stroke_orofacial.stats.trajectory_session_summary``. Refuses to
overwrite an existing output (checked before any computation).

Usage:
    python scripts/manuscript/run_trajectory_session_tables.py [--tables traj xy path] [--substrate-suffix S]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from stroke_orofacial.figures.phase_aligned_trajectories import RESULTS_SUBDIR
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import trajectory_session_summary as tss

log = logging.getLogger("manuscript.trajectory_session_tables")
OUT_SUBDIR = "stats/results/trajectory_sessions"
LICK_SETS = {"first": ("first_lick", ""), "all": ("all_multi", "_all_licks")}   # tag -> (lick_set, results suffix)


def _xy_substrate(lick_set: str, resolver: PathResolver) -> pd.DataFrame:
    """xy_dist trial x bin substrate (same steps as build_substrate, xy signal only)."""
    from scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit import (
        COHORT_8,
        add_xy_dist,
        filter_phase_rows,
    )
    from scripts.phase_9_1_q13.emit_cohort import (
        attach_metadata,
        remap_animals_to_3tier,
        walk_cohort,
    )

    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.stats.aggregators import (
        apply_phase_bin_baseline_delta,
        compute_per_animal_phase_bin_baseline,
        densify_phase_rows_via_interp,
    )

    sig = ("xy_dist",)
    animals = list(COHORT_8)
    amap = remap_animals_to_3tier({a: i for a, i in load_animals().items() if a in animals})
    cohort, _ = walk_cohort(animals=animals, resolver=resolver, logger=log, lick_set=lick_set)
    cohort, report = filter_phase_rows(cohort, animals=animals, resolver=resolver, defaults=load_defaults())
    log.info("filter report: %s", report)
    cohort = add_xy_dist(attach_metadata(cohort, amap))
    dense = densify_phase_rows_via_interp(cohort, signals=sig)
    base = compute_per_animal_phase_bin_baseline(dense, signals=sig)
    return apply_phase_bin_baseline_delta(dense, base, signals=sig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tables", nargs="+", choices=["traj", "xy", "path"], default=["traj", "xy", "path"])
    ap.add_argument("--substrate-suffix", default="")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    tag = f"_{a.substrate_suffix}" if a.substrate_suffix else ""
    r = PathResolver()
    out_dir = r.pipeline_outputs(subdir=OUT_SUBDIR)
    outs = {"traj": out_dir / f"c1_traj_sessions{tag}.csv", "xy": out_dir / f"c1_traj_xy_sessions{tag}.csv",
            "path": out_dir / f"c1_path_session_sem{tag}.csv"}
    clash = [str(outs[t]) for t in a.tables if outs[t].exists()]
    if clash:
        log.error("refusing to overwrite %s", ", ".join(clash))
        return 2

    def v3(sfx: str) -> Path:
        return r.pipeline_outputs(subdir=RESULTS_SUBDIR + sfx) / "3_tier" / "v3"

    out_dir.mkdir(parents=True, exist_ok=True)
    if "traj" in a.tables:
        frames = []
        for t, (_, sfx) in LICK_SETS.items():
            d = pd.read_parquet(v3(sfx) / f"trial_bin_substrate{tag}.parquet")
            s = tss.summarise_sessions(d)
            s.insert(0, "lick_set", t)
            frames.append(s)
            log.info("traj %s: %d trial-bin rows -> %d rows", t, len(d), len(s))
        pd.concat(frames, ignore_index=True).to_csv(outs["traj"], index=False)
        log.info("wrote %s", outs["traj"])
    if "path" in a.tables:
        d = pd.read_parquet(v3("") / f"trial_bin_substrate{tag}.parquet",
                            columns=["animal", "date", "side", "phase_bin", "x_centered", "y_centered",
                                     "epoch_label", "recovery_phenotype"])
        tss.path_session_sem(d).to_csv(outs["path"], index=False)
        log.info("wrote %s", outs["path"])
    if "xy" in a.tables:
        cache = v3("").parent / "v3_xy_dist" / f"_xy_session_cache{tag}"
        frames = []
        for t, (lset, _) in LICK_SETS.items():
            cp = cache / f"xy_trial_bin_substrate_{t}.parquet"
            if cp.exists():
                d = pd.read_parquet(cp)
            else:
                log.info("xy %s: rebuilding substrate (30-60 min) -> %s", t, cp)
                d = _xy_substrate(lset, r)
                cache.mkdir(parents=True, exist_ok=True)
                d.to_parquet(cp, index=False)
            s = tss.summarise_xy_sessions(d)
            s.insert(0, "lick_set", t)
            frames.append(s)
            log.info("xy %s: %d trial-bin rows -> %d rows", t, len(d), len(s))
        pd.concat(frames, ignore_index=True)[tss.OUT_COLUMNS].to_csv(outs["xy"], index=False)
        log.info("wrote %s", outs["xy"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
