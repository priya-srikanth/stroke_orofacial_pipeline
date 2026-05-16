"""Phase 7c.2 Task 4 — Cohort-aggregate kinematics re-emit.

Consumes Task 3's per-session kinematics outputs (interpolated_traces,
features/tongue, jaw_pertrial/endpoints, licking_dynamics/traces,
tongue_jaw_mismatch/candidate_trials) and produces cross-session +
day-binned + mean/SEM aggregates per (animal, bodypart-family-where-
applicable).

Per-animal aggregation entry points (kickoff Task 4 scope):

  E1. Phase 7a.4 cross-session tongue-angle composite (12 PNGs per
      mouse) via :func:`build_tongue_angle_cohort` → outputs at
      ``dlc_kinematics/tongue_angle/cross_session/<animal>/...``.

  E2. Phase 7a.5 cross-session tongue-jaw mismatch via
      :func:`render_cross_session_figures` → outputs at
      ``dlc_kinematics/tongue_jaw_mismatch/cross_session/<animal>/...``.

  E3. Phase 7a.6 mean/SEM cohort for tongue + jaw via
      :func:`build_mean_sem_cohort` per bodypart → outputs at
      ``dlc_kinematics/mean_sem/<bodypart>/<center_mode>/<window>/<plot_family>/<animal>/...``.

  E4. Phase 7a.4 day-binned licking-dynamics cross-session via
      :func:`aggregate_licking_dynamics_day_binned_by_animal` →
      outputs at
      ``dlc_kinematics/licking_dynamics/day_binned/<animal>/<rel_day_bin_label>.parquet``.

Per-animal aggregation manifest at
``.scratch_phase_7c2/cohort_aggregates_manifest.csv`` captures
runtime + per-family output counts + status for each animal.

Per-animal order matches Task 3 (PS46, PS47, PS48, PS49, PS50, PS51,
PS54, PS55). Per-animal commit after each completes; full cohort
~1-2 hr expected per kickoff Task 4 estimate.

Resumability: per-animal manifest rows skip if status=OK already
recorded. CC can re-invoke after partial cohort with no
double-compute.

Each animal's mean_sem_cohort runs across `MEAN_SEM_BODYPARTS`
(tongue + jaw); `include_mean_video=False` for cohort budget control
(mean videos are heavy renders; not required by Task 4 acceptance —
Phase 7a.6's mean_video output is per-(bodypart, animal) and can run
post-Task-4 if needed).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import sys
import time
from pathlib import Path

from stroke_orofacial.dlc_kinematics import (
    aggregate_licking_dynamics_day_binned_by_animal,
    build_mean_sem_cohort,
    build_tongue_angle_cohort,
    render_cross_session_figures,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

MEAN_SEM_BODYPARTS = ("tongue", "jaw")

MANIFEST_PATH = Path(".scratch_phase_7c2/cohort_aggregates_manifest.csv")
MANIFEST_HEADER = [
    "animal",
    "runtime_seconds_total",
    "runtime_seconds_tongue_angle_cohort",
    "runtime_seconds_mismatch_cross_session",
    "runtime_seconds_mean_sem_cohort",
    "runtime_seconds_day_binned",
    "n_tongue_angle_paths",
    "n_mismatch_paths",
    "n_mean_sem_paths",
    "n_day_binned_paths",
    "status",
    "anomaly_notes",
]


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.reemit_cohort_aggregates")


def _load_manifest_so_far() -> dict[str, str]:
    """Return {animal: status} for prior manifest rows."""
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            out[row["animal"]] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    is_new = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def _build_err_row(animal: str, t0: float, anomalies: list[str]) -> dict:
    return {
        "animal": animal,
        "runtime_seconds_total": f"{time.perf_counter() - t0:.3f}",
        "runtime_seconds_tongue_angle_cohort": "",
        "runtime_seconds_mismatch_cross_session": "",
        "runtime_seconds_mean_sem_cohort": "",
        "runtime_seconds_day_binned": "",
        "n_tongue_angle_paths": "0",
        "n_mismatch_paths": "0",
        "n_mean_sem_paths": "0",
        "n_day_binned_paths": "0",
        "status": "ERR",
        "anomaly_notes": "; ".join(anomalies),
    }


def _process_animal(animal: str, resolver: PathResolver) -> tuple[bool, dict]:
    """Run all 4 cohort-aggregate families for one animal. Returns (ok, row)."""
    log.info(f"=== animal={animal}: cohort-aggregate re-emit ===")
    animal_t0 = time.perf_counter()
    anomalies: list[str] = []

    # ----- E1: tongue-angle cross-session composite (12 PNGs) -----
    t0 = time.perf_counter()
    try:
        ta_paths = build_tongue_angle_cohort(
            animal=animal, resolver=resolver, overwrite="force",
        )
        rt_ta = time.perf_counter() - t0
        n_ta = len(ta_paths) if ta_paths else 0
        log.info(f"  [E1] tongue_angle cohort: {rt_ta:.1f}s ({n_ta} paths)")
    except Exception as ex:
        anomalies.append(f"E1-tongue_angle: {ex!r}")
        log.error(f"  [E1] tongue_angle: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    # ----- E2: mismatch cross-session figures -----
    t0 = time.perf_counter()
    try:
        mm_paths = render_cross_session_figures(
            animal=animal, resolver=resolver, overwrite="force",
        )
        rt_mm = time.perf_counter() - t0
        n_mm = sum(len(v) if isinstance(v, list) else 1 for v in (mm_paths or {}).values())
        log.info(f"  [E2] mismatch cross_session: {rt_mm:.1f}s ({n_mm} paths)")
    except Exception as ex:
        anomalies.append(f"E2-mismatch: {ex!r}")
        log.error(f"  [E2] mismatch: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    # ----- E3: mean/SEM cohort (per bodypart) -----
    t0 = time.perf_counter()
    n_ms = 0
    try:
        for bp in MEAN_SEM_BODYPARTS:
            ms_paths = build_mean_sem_cohort(
                bodypart=bp,
                animal=animal,
                resolver=resolver,
                include_mean_video=False,
                overwrite="force",
            )
            ms_count = sum(
                len(v) if isinstance(v, list) else 1 for v in (ms_paths or {}).values()
            )
            n_ms += ms_count
            log.info(f"  [E3] mean_sem cohort bp={bp}: {ms_count} paths")
        rt_ms = time.perf_counter() - t0
        log.info(f"  [E3] mean_sem total: {rt_ms:.1f}s ({n_ms} paths)")
    except Exception as ex:
        anomalies.append(f"E3-mean_sem: {ex!r}")
        log.error(f"  [E3] mean_sem: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    # ----- E4: day-binned licking-dynamics -----
    t0 = time.perf_counter()
    try:
        db_paths = aggregate_licking_dynamics_day_binned_by_animal(
            animal=animal, resolver=resolver, overwrite="force",
        )
        rt_db = time.perf_counter() - t0
        n_db = len(db_paths) if db_paths else 0
        log.info(f"  [E4] day_binned: {rt_db:.1f}s ({n_db} paths)")
    except Exception as ex:
        anomalies.append(f"E4-day_binned: {ex!r}")
        log.error(f"  [E4] day_binned: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    animal_rt = time.perf_counter() - animal_t0
    log.info(f"=== animal={animal}: complete — runtime {animal_rt:.1f}s "
             f"({animal_rt/60:.1f} min); paths E1={len(ta_paths)} "
             f"E2={n_mm} E3={n_ms} E4={n_db} ===")
    return True, {
        "animal": animal,
        "runtime_seconds_total": f"{animal_rt:.3f}",
        "runtime_seconds_tongue_angle_cohort": f"{rt_ta:.3f}",
        "runtime_seconds_mismatch_cross_session": f"{rt_mm:.3f}",
        "runtime_seconds_mean_sem_cohort": f"{rt_ms:.3f}",
        "runtime_seconds_day_binned": f"{rt_db:.3f}",
        "n_tongue_angle_paths": str(len(ta_paths)),
        "n_mismatch_paths": str(n_mm),
        "n_mean_sem_paths": str(n_ms),
        "n_day_binned_paths": str(n_db),
        "status": "OK",
        "anomaly_notes": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal. Default: iterate the full Cohort A order.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    log.info(f"output_root: {resolver.pipeline_outputs('dlc_kinematics')}")
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")

    animals = [args.animal] if args.animal else list(COHORT_ORDER)
    prior = _load_manifest_so_far()

    n_run = n_ok = n_fail = 0
    for animal in animals:
        prior_status = prior.get(animal)
        if prior_status == "OK":
            log.info(f"  [skip] {animal} already OK in prior manifest")
            continue
        ok, row = _process_animal(animal, resolver)
        _append_manifest(row)
        n_run += 1
        if ok:
            n_ok += 1
        else:
            n_fail += 1

    log.info(f"=== COHORT-AGGREGATE SUMMARY: {n_ok}/{n_run} OK, "
             f"{n_fail} failed across {len(animals)} animal(s) ===")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


_ = dt  # silence unused-import warning if dt becomes unused in future edits
