"""Phase 7e Event B Stage 5 — tongue-jaw mismatch cohort re-emit (post-Phase-7e.3).

Per-session re-emit of:
  - candidate_trials parquet (classifier output)
  - within_session figures (individual_trials_2col + session_overlay_grid_4x2)
  - cross_session figures per animal (cross_session_overlay + cross_session_binned)

All consumes v7 cleaned_traces (use_v7_cleaned=True) per Phase 7e.3 routing.
Baseline-fill frames NaN-masked before slope-detector + plotters.

Resumes Stage 5 EXECUTION HOLD per Addendum #2 — now unblocked since
jaw cleaned_traces are ready (231 parquets, matches tongue Stage 1 OK
count exactly).

Manifest at .scratch_chore_phase_7e_reemit/stage5_manifest.csv (separate
from Stage 1/4/4b/5b manifests so per-stage status doesn't intermix).

Anomaly thresholds (per kickoff Failure-recovery pattern):
  - Per-session FAIL: stop immediately.
  - >=2 FAIL within same animal: stop after second.
  - >=5 FAIL cohort-wide: stop and re-scope.

CLI:
  python scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py
  python scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py --animal PS54
  python scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py --skip-within-session
  python scripts/phase_7e/reemit_tongue_jaw_mismatch_cohort.py --skip-cross-session
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import sys
import time
from pathlib import Path

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.dlc_kinematics import (
    classify_tongue_jaw_mismatch_by_animal_date,
    render_cross_session_figures,
    render_within_session_figures,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
SCRATCH_DIR = Path(".scratch_chore_phase_7e_reemit")
MANIFEST_PATH = SCRATCH_DIR / "stage5_manifest.csv"
MANIFEST_HEADER = [
    "animal", "stage", "key",
    "runtime_seconds", "n_paths_written",
    "status", "anomaly_notes",
]

MAX_PER_ANIMAL_FAILURES = 2
MAX_COHORT_FAILURES = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phase_7e.reemit_tongue_jaw_mismatch_cohort")


def _read_prior_manifest() -> dict[tuple[str, str, str], str]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[tuple[str, str, str], str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[(row["animal"], row["stage"], row["key"])] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    write_header = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_HEADER})


def _process_classify(
    animal: str, date: dt.date, resolver: PathResolver,
) -> dict:
    date_iso = date.isoformat()
    # Pre-check: both tongue + jaw cleaned_traces must exist (Phase 7e.3
    # routing reads from these). This is the sole guard — the bare half of a
    # secondary-spout date is a normal DLC session and must NOT be skipped
    # per-date (chore substrate-routing-and-secondary-spout-per-half-fix).
    tongue_ct = resolver.cleaned_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    jaw_ct = resolver.cleaned_trace(
        bodypart="jaw", animal=animal, date=date,
    )
    if not (tongue_ct.exists() and jaw_ct.exists()):
        return {
            "animal": animal, "stage": "classify", "key": date_iso,
            "runtime_seconds": "", "n_paths_written": 0,
            "status": "SKIP",
            "anomaly_notes": f"missing_cleaned_trace_"
                             f"tongue={tongue_ct.exists()}_jaw={jaw_ct.exists()}",
        }
    t0 = time.perf_counter()
    try:
        out_path = classify_tongue_jaw_mismatch_by_animal_date(
            animal=animal, date=date, resolver=resolver,
            overwrite="force", use_v7_cleaned=True,
        )
    except Exception as exc:
        return {
            "animal": animal, "stage": "classify", "key": date_iso,
            "runtime_seconds": f"{time.perf_counter() - t0:.3f}",
            "n_paths_written": 0,
            "status": "FAIL",
            "anomaly_notes": f"{type(exc).__name__}:{exc!s}",
        }
    elapsed = time.perf_counter() - t0
    return {
        "animal": animal, "stage": "classify", "key": date_iso,
        "runtime_seconds": f"{elapsed:.3f}",
        "n_paths_written": 1 if out_path else 0,
        "status": "OK" if out_path else "SKIP",
        "anomaly_notes": "" if out_path else "build_returned_none",
    }


def _process_within_session(
    animal: str, date: dt.date, resolver: PathResolver,
) -> dict:
    date_iso = date.isoformat()
    candidate_path = resolver.tongue_jaw_mismatch_candidate_trials_parquet(
        animal, date,
    )
    if not candidate_path.exists():
        return {
            "animal": animal, "stage": "within_session", "key": date_iso,
            "runtime_seconds": "", "n_paths_written": 0,
            "status": "SKIP", "anomaly_notes": "no_candidate_trials_parquet",
        }
    t0 = time.perf_counter()
    try:
        paths = render_within_session_figures(
            animal=animal, date=date, resolver=resolver,
            overwrite="force", use_v7_cleaned=True,
        )
    except Exception as exc:
        return {
            "animal": animal, "stage": "within_session", "key": date_iso,
            "runtime_seconds": f"{time.perf_counter() - t0:.3f}",
            "n_paths_written": 0,
            "status": "FAIL",
            "anomaly_notes": f"{type(exc).__name__}:{exc!s}",
        }
    elapsed = time.perf_counter() - t0
    n_paths = sum(
        len(v) if isinstance(v, list) else 1 for v in (paths or {}).values()
    )
    return {
        "animal": animal, "stage": "within_session", "key": date_iso,
        "runtime_seconds": f"{elapsed:.3f}",
        "n_paths_written": n_paths,
        "status": "OK", "anomaly_notes": "",
    }


def _process_cross_session(animal: str, resolver: PathResolver) -> dict:
    t0 = time.perf_counter()
    try:
        paths = render_cross_session_figures(
            animal=animal, resolver=resolver,
            overwrite="force", use_v7_cleaned=True,
        )
    except Exception as exc:
        return {
            "animal": animal, "stage": "cross_session", "key": "all",
            "runtime_seconds": f"{time.perf_counter() - t0:.3f}",
            "n_paths_written": 0,
            "status": "FAIL",
            "anomaly_notes": f"{type(exc).__name__}:{exc!s}",
        }
    elapsed = time.perf_counter() - t0
    n_paths = sum(
        1 if not isinstance(v, list) else len(v)
        for v in (paths or {}).values()
    )
    log.info("[%s cross_session] OK in %.1fs (%d paths)", animal, elapsed, n_paths)
    return {
        "animal": animal, "stage": "cross_session", "key": "all",
        "runtime_seconds": f"{elapsed:.3f}",
        "n_paths_written": n_paths,
        "status": "OK", "anomaly_notes": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal", choices=COHORT_ORDER, default=None,
        help="Single animal; default = full Cohort A order.",
    )
    parser.add_argument(
        "--skip-classify", action="store_true",
        help="Skip the per-session candidate-trials classifier emit.",
    )
    parser.add_argument(
        "--skip-within-session", action="store_true",
        help="Skip per-session within_session figure renders.",
    )
    parser.add_argument(
        "--skip-cross-session", action="store_true",
        help="Skip per-animal cross_session figure renders.",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    prior = _read_prior_manifest()
    log.info("Prior manifest rows: %d", len(prior))

    animals = (args.animal,) if args.animal else COHORT_ORDER
    cohort_failures = sum(1 for s in prior.values() if s == "FAIL")
    per_animal_fail: dict[str, int] = {a: 0 for a in animals}
    for (a, _, _), s in prior.items():
        if s == "FAIL" and a in per_animal_fail:
            per_animal_fail[a] += 1

    for animal in animals:
        # Phase 1: per-session classify + within-session render
        if not (args.skip_classify and args.skip_within_session):
            for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
                date_iso = date.isoformat()

                # Stage 5 classify step
                if not args.skip_classify:
                    key = (animal, "classify", date_iso)
                    if prior.get(key) != "OK":
                        if cohort_failures >= MAX_COHORT_FAILURES:
                            log.error("STOP: cohort failures %d >= %d", cohort_failures, MAX_COHORT_FAILURES)
                            return 2
                        if per_animal_fail.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
                            log.error("STOP: %s failures %d >= %d", animal, per_animal_fail[animal], MAX_PER_ANIMAL_FAILURES)
                            return 2
                        log.info("[%s %s classify] starting", animal, date_iso)
                        row = _process_classify(animal, date, resolver)
                        _append_manifest(row)
                        if row["status"] == "OK":
                            log.info(
                                "[%s %s classify] OK in %ss",
                                animal, date_iso, row["runtime_seconds"],
                            )
                        elif row["status"] == "SKIP":
                            log.info(
                                "[%s %s classify] SKIP (%s)",
                                animal, date_iso, row["anomaly_notes"],
                            )
                        else:
                            log.error(
                                "[%s %s classify] FAIL: %s",
                                animal, date_iso, row["anomaly_notes"],
                            )
                            cohort_failures += 1
                            per_animal_fail[animal] = per_animal_fail.get(animal, 0) + 1
                            return 2

                # Stage 5 within-session render step
                if not args.skip_within_session:
                    key = (animal, "within_session", date_iso)
                    if prior.get(key) != "OK":
                        if cohort_failures >= MAX_COHORT_FAILURES:
                            return 2
                        if per_animal_fail.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
                            return 2
                        log.info("[%s %s within_session] starting", animal, date_iso)
                        row = _process_within_session(animal, date, resolver)
                        _append_manifest(row)
                        if row["status"] == "OK":
                            log.info(
                                "[%s %s within_session] OK in %ss (%s paths)",
                                animal, date_iso, row["runtime_seconds"], row["n_paths_written"],
                            )
                        elif row["status"] == "SKIP":
                            log.info(
                                "[%s %s within_session] SKIP (%s)",
                                animal, date_iso, row["anomaly_notes"],
                            )
                        else:
                            log.error(
                                "[%s %s within_session] FAIL: %s",
                                animal, date_iso, row["anomaly_notes"],
                            )
                            cohort_failures += 1
                            per_animal_fail[animal] = per_animal_fail.get(animal, 0) + 1
                            return 2

        # Phase 2: cross-session per animal
        if not args.skip_cross_session:
            key = (animal, "cross_session", "all")
            if prior.get(key) != "OK":
                if cohort_failures >= MAX_COHORT_FAILURES:
                    return 2
                if per_animal_fail.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
                    return 2
                log.info("[%s cross_session] starting", animal)
                row = _process_cross_session(animal, resolver)
                _append_manifest(row)
                if row["status"] == "FAIL":
                    cohort_failures += 1
                    per_animal_fail[animal] = per_animal_fail.get(animal, 0) + 1
                    return 2

    log.info("Stage 5 done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
