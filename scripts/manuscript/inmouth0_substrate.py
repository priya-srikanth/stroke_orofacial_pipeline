"""Two-tone phase substrate with the six-position in-mouth rule (CC-B, 2026-11-23, caption review item 1).

Rule (Priya 2026-11-23): frames with the tongue in the mouth count as 0 for EVERY trajectory measure
(angle, lateral position, xy distance), as in the six-position cohort.

What the existing substrate does (checked on the cached ps47d5 substrate and two bundles):
  - in-mouth frames are the baseline-filled frames of the v7-cleaned trace, which sit exactly at the mouth
    origin, x = y = 0; they are already emitted as phase rows, so lateral (x_centered), protrusion
    (y_centered) and xy distance are already 0 there (no interpolation across them);
  - angle_deg on those frames is the (8-ms Gaussian smoothed) tongue angle of the mouth origin, which is
    near 0 but not exactly 0 (smoothing leaks the protruded angle into neighbouring in-mouth frames).
This builder sets angle_deg = 0 on every in-mouth frame (x == 0 and y == 0) BEFORE densification, and
otherwise reproduces run_within_animal_cluster_perm.build_substrate (walk_cohort -> filter_phase_rows ->
attach_metadata -> densify_phase_rows_via_interp -> per-animal pre baseline -> delta). It builds each
session's bundle ONCE and emits both lick sets (first_lick, all_multi), plus xy_dist (as add_xy_dist).

Two steps (writes NEW files only; refuses to overwrite):
  frames  --animal PSxx --stage DIR   per-animal frame-level phase rows for both lick sets
  dense   --stage DIR [--suffix S]    concat, filter, metadata, densify, baseline, delta ->
                                      <v3>/trial_bin_substrate_<S>.parquet (angle/x/y, both lick sets) and
                                      v3_xy_dist/_xy_session_cache_<S>/xy_trial_bin_substrate_{first,all}.parquet
Default suffix: ps47d5_inmouth0. The cluster test then runs unchanged:
  python -m scripts.manuscript.run_within_animal_cluster_perm --test c2_aligned --use-cache \
         --out-suffix ps47d5_inmouth0 --refuse-existing
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

log = logging.getLogger("manuscript.inmouth0_substrate")
LICK_SETS = ("first_lick", "all_multi")
SIG3 = ("angle_deg", "x_centered", "y_centered")


def in_mouth_zero(rows: pd.DataFrame) -> pd.DataFrame:
    """angle_deg = 0 where the tongue is in the mouth (x == 0 and y == 0, the baseline-filled frames)."""
    m = (rows["x_centered"] == 0) & (rows["y_centered"] == 0)
    out = rows.copy()
    out["in_mouth"] = m.to_numpy()
    out.loc[m, "angle_deg"] = 0.0
    return out


def frames_one_animal(animal: str, stage: Path) -> None:
    from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
        build_all_licks_centered_phase_rows,
        build_first_lick_centered_phase_rows,
        build_tongue_visual_bundle_by_animal_date,
    )
    from stroke_orofacial.paths import PathResolver
    from scripts.phase_9_1_q13.emit_cohort import enumerate_session_dates

    r = PathResolver()
    outs = {ls: stage / f"frames_{ls}_{animal}.parquet" for ls in LICK_SETS}
    if all(p.exists() for p in outs.values()):
        log.info("[%s] frames exist; skipped", animal)
        return
    acc = {ls: [] for ls in LICK_SETS}
    for d in enumerate_session_dates(animal, r):
        t0 = time.perf_counter()
        try:
            b = build_tongue_visual_bundle_by_animal_date(animal=animal, date=d, resolver=r)
        except Exception as exc:  # same policy as emit_cohort.build_session_phase_rows
            log.exception("[%s/%s] bundle FAILED: %s", animal, d, exc)
            continue
        synth = float(b.metadata.get("pre_stroke_median_ili_ms", float("nan")))
        if not (np.isfinite(synth) and synth > 0):
            log.info("[%s/%s] SKIP_NO_ILI", animal, d)
            continue
        for ls, fn in (("first_lick", build_first_lick_centered_phase_rows),
                       ("all_multi", build_all_licks_centered_phase_rows)):
            rows = fn(b, synthetic_ili_ms=synth, ili_source="synthetic_only")
            if rows.empty:
                continue
            rows = rows.copy()
            rows["animal"] = animal
            rows["date"] = d
            acc[ls].append(rows)
        log.info("[%s/%s] %.1fs", animal, d, time.perf_counter() - t0)
    for ls in LICK_SETS:
        df = pd.concat(acc[ls], ignore_index=True) if acc[ls] else pd.DataFrame()
        df.to_parquet(outs[ls], index=False)
        log.info("[%s] %s: %d frame rows -> %s", animal, ls, len(df), outs[ls])


def dense_all(stage: Path, suffix: str) -> None:
    from scripts.chore_dlc_pooled_phenotype.q13_traj_v2_emit import COHORT_8, add_xy_dist, filter_phase_rows
    from scripts.phase_9_1_q13.emit_cohort import attach_metadata, remap_animals_to_3tier
    from stroke_orofacial.animals import load_animals
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.figures.phase_aligned_trajectories import RESULTS_SUBDIR
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.stats.aggregators import (
        apply_phase_bin_baseline_delta,
        compute_per_animal_phase_bin_baseline,
        densify_phase_rows_via_interp,
    )

    r = PathResolver()
    animals = list(COHORT_8)
    amap = remap_animals_to_3tier({a: i for a, i in load_animals().items() if a in animals})

    def v3(sfx):
        return r.pipeline_outputs(subdir=RESULTS_SUBDIR + sfx) / "3_tier" / "v3"

    xy_cache = v3("").parent / "v3_xy_dist" / f"_xy_session_cache_{suffix}"
    plan = {"first_lick": (v3("") / f"trial_bin_substrate_{suffix}.parquet", xy_cache / "xy_trial_bin_substrate_first.parquet"),
            "all_multi": (v3("_all_licks") / f"trial_bin_substrate_{suffix}.parquet", xy_cache / "xy_trial_bin_substrate_all.parquet")}
    clash = [str(p) for pair in plan.values() for p in pair if p.exists()]
    if clash:
        raise SystemExit(f"refusing to overwrite {clash}")
    xy_cache.mkdir(parents=True, exist_ok=True)
    report = []
    for ls, (out3, outxy) in plan.items():
        cohort = pd.concat([pd.read_parquet(stage / f"frames_{ls}_{a}.parquet") for a in animals], ignore_index=True)
        cohort["date"] = pd.to_datetime(cohort["date"]).dt.date
        cohort, rep = filter_phase_rows(cohort, animals=animals, resolver=r, defaults=load_defaults())
        log.info("[%s] filter report: %s", ls, rep)
        cohort = attach_metadata(cohort, amap)
        cohort = in_mouth_zero(cohort)
        n_im = int(cohort["in_mouth"].sum())
        leak = cohort.loc[cohort["in_mouth"], "angle_deg"]  # already zeroed; report from raw below
        report.append({"lick_set": ls, "frame_rows": len(cohort), "in_mouth_frames": n_im,
                       "frac_in_mouth": n_im / max(len(cohort), 1)})
        del leak
        dense = densify_phase_rows_via_interp(cohort, signals=SIG3)
        base = compute_per_animal_phase_bin_baseline(dense, signals=SIG3)
        apply_phase_bin_baseline_delta(dense, base, signals=SIG3).to_parquet(out3, index=False)
        log.info("[%s] wrote %s", ls, out3)
        cxy = add_xy_dist(cohort)
        dxy = densify_phase_rows_via_interp(cxy, signals=("xy_dist",))
        bxy = compute_per_animal_phase_bin_baseline(dxy, signals=("xy_dist",))
        apply_phase_bin_baseline_delta(dxy, bxy, signals=("xy_dist",)).to_parquet(outxy, index=False)
        log.info("[%s] wrote %s", ls, outxy)
    pd.DataFrame(report).to_csv(stage / f"inmouth_report_{suffix}.csv", index=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=("frames", "dense"))
    ap.add_argument("--animal")
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--suffix", default="ps47d5_inmouth0")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    a.stage.mkdir(parents=True, exist_ok=True)
    if a.step == "frames":
        frames_one_animal(a.animal, a.stage)
    else:
        dense_all(a.stage, a.suffix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
