"""Phase 7e Event B Stage 5b — tongue_angle PNG bundle re-emit (within-
session + cross-session) on v7-routed per_trial JSONs.

Per Addendum #2 (Priya override): within-session 9-10 PNG bundle is
explicitly IN-scope. Per Stage 5b spec:
  - Within-session: 10 PNGs/session via render_tongue_qc_figures
  - Cross-session:  14 PNGs/animal via build_tongue_angle_cohort

Stage 5 (tongue-jaw mismatch) is on EXECUTION HOLD per Addendum #2;
this driver does NOT call mismatch outputs.

Outputs land at:
  pipeline_outputs/dlc_kinematics/tongue_angle/within_session/<animal>/<YYYYMMDD>/*.png
  pipeline_outputs/dlc_kinematics/tongue_angle/cross_session/<animal>/*.png

Manifest at .scratch_chore_phase_7e_reemit/stage5b_manifest.csv (separate
from Stage 1's cohort_manifest.csv).

CLI:
  python scripts/phase_7e/reemit_tongue_followons_cohort.py
  python scripts/phase_7e/reemit_tongue_followons_cohort.py --animal PS54
  python scripts/phase_7e/reemit_tongue_followons_cohort.py --skip-within-session
  python scripts/phase_7e/reemit_tongue_followons_cohort.py --skip-cross-session
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
    build_tongue_angle_cohort,
    render_tongue_qc_figures,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
SCRATCH_DIR = Path(".scratch_chore_phase_7e_reemit")
MANIFEST_PATH = SCRATCH_DIR / "stage5b_manifest.csv"
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
log = logging.getLogger("phase_7e.reemit_tongue_followons_cohort")


def _read_prior_manifest() -> dict[tuple[str, str, str], str]:
    """Return {(animal, stage, key): status} for prior runs."""
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


def _process_within_session(
    animal: str, date: dt.date, resolver: PathResolver,
) -> dict:
    date_iso = date.isoformat()
    interp_path = resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    if not interp_path.exists():
        return {
            "animal": animal, "stage": "within_session", "key": date_iso,
            "runtime_seconds": "", "n_paths_written": 0,
            "status": "SKIP", "anomaly_notes": "no_tongue_interpolated_trace",
        }
    t0 = time.perf_counter()
    try:
        paths = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver, overwrite="force",
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
    n_paths = (
        sum(len(v) if isinstance(v, list) else 1 for v in (paths or {}).values())
        if isinstance(paths, dict)
        else (len(paths) if paths else 0)
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
        paths = build_tongue_angle_cohort(
            animal=animal, resolver=resolver, overwrite="force",
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
    n_paths = (
        sum(len(v) if isinstance(v, list) else 1 for v in (paths or {}).values())
        if isinstance(paths, dict)
        else (len(paths) if paths else 0)
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
        "--skip-within-session", action="store_true",
        help="Skip per-session within_session PNG bundle re-render.",
    )
    parser.add_argument(
        "--skip-cross-session", action="store_true",
        help="Skip per-animal cross_session tongue-angle composite re-render.",
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
        if not args.skip_within_session:
            for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
                key = (animal, "within_session", date.isoformat())
                if prior.get(key) == "OK":
                    continue
                if cohort_failures >= MAX_COHORT_FAILURES:
                    log.error("STOP: cohort failures %d >= %d", cohort_failures, MAX_COHORT_FAILURES)
                    return 2
                if per_animal_fail.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
                    log.error("STOP: %s failures %d >= %d", animal, per_animal_fail[animal], MAX_PER_ANIMAL_FAILURES)
                    return 2
                log.info("[%s %s within_session] starting", animal, date.isoformat())
                row = _process_within_session(animal, date, resolver)
                _append_manifest(row)
                if row["status"] == "OK":
                    log.info(
                        "[%s %s within_session] OK in %ss (%s paths)",
                        animal, date.isoformat(), row["runtime_seconds"], row["n_paths_written"],
                    )
                elif row["status"] == "SKIP":
                    log.info(
                        "[%s %s within_session] SKIP (%s)",
                        animal, date.isoformat(), row["anomaly_notes"],
                    )
                else:
                    log.error(
                        "[%s %s within_session] FAIL: %s",
                        animal, date.isoformat(), row["anomaly_notes"],
                    )
                    cohort_failures += 1
                    per_animal_fail[animal] = per_animal_fail.get(animal, 0) + 1
                    return 2

        if not args.skip_cross_session:
            key = (animal, "cross_session", "all")
            if prior.get(key) == "OK":
                log.info("[%s cross_session] skip (prior OK)", animal)
            else:
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

    log.info("Stage 5b done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
