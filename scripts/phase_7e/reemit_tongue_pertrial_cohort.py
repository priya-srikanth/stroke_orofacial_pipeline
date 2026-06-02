"""Phase 7e Event B (Chore) — tongue_pertrial cohort re-emit (v7 pipeline).

Surgical driver dedicated to the tongue-only re-emit described in
docs/prompts/chore-phase-7e-cohort-reemit-kickoff.md and its
Addendum #1 (secondary-spout exclusion + output path corrections).

This driver intentionally does NOT call interpolation, jaw, spatial,
or figure renderers — Phase 7e ships at the pre-clean + detector
stage and only invalidates tongue_pertrial outputs. Re-using the
Phase 7c.2 reemit_cohort.py would bundle ~70 s/session of unrelated
work; this script runs ~5-15 s/session per CC's 2026-05-26 audit.

Per-session writes (via build_tongue_pertrial_by_animal_date,
overwrite="force"):
  - pipeline_outputs/dlc_kinematics/per_frame/tongue/<animal>/<YYYYMMDD>.parquet
  - pipeline_outputs/dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet
  - pipeline_outputs/dlc_kinematics/per_trial/tongue/<animal>/<YYYYMMDD>.json
  - pipeline_outputs/dlc_kinematics/cleaned_traces/tongue/<animal>/<YYYYMMDD>.parquet  [v7]
  - pipeline_outputs/dlc_kinematics/lick_events/tongue/<animal>/<YYYYMMDD>.parquet     [v7]

Cohort enumeration:
  - Primary: yaml_driven_session_dates(animal, analysis_context="dlc"). This
    INCLUDES the bare half of secondary-spout (Pattern B) dates — the bare
    half is a normal primary-spout session WITH DLC. The chore
    substrate-routing-and-secondary-spout-per-half-fix (2026-05-31) removed
    the prior per-date secondary_spout skip, which wrongly dropped the bare
    half along with the b half. The b half is never enumerated here (no
    session_suffix fan-out at this driver).
  - Runtime pre-check: resolver.interpolated_trace(bodypart="tongue",
    animal, date).exists() — missing => manifest status="SKIP" with
    anomaly_notes="no_tongue_interpolated_trace"; NOT counted toward
    failure anomaly thresholds. This is the sole guard for genuinely
    DLC-less dates (already dropped upstream by the dlc exclusion filter).

Manifest:
  .scratch_chore_phase_7e_reemit/cohort_manifest.csv
  Columns: animal, date, runtime_seconds_total, n_outputs_written,
           output_sha256s_json, status, anomaly_notes
  Append-only. Resume-on-relaunch skips rows with status="OK".

Anomaly thresholds (per kickoff Failure-recovery pattern):
  - Per-session FAIL: stop immediately.
  - ≥2 FAIL within the same animal: stop after the second.
  - ≥5 FAIL cohort-wide (tracked across invocations via manifest):
    stop and re-scope.
  - SKIP rows do NOT count toward these thresholds.

CLI:
  python scripts/phase_7e/reemit_tongue_pertrial_cohort.py
  python scripts/phase_7e/reemit_tongue_pertrial_cohort.py --animal PS54
  python scripts/phase_7e/reemit_tongue_pertrial_cohort.py --limit 50  # calibration
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.dlc_kinematics import build_tongue_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
SCRATCH_DIR = Path(".scratch_chore_phase_7e_reemit")
MANIFEST_PATH = SCRATCH_DIR / "cohort_manifest.csv"
MANIFEST_HEADER = [
    "animal",
    "date",
    "runtime_seconds_total",
    "n_outputs_written",
    "output_sha256s_json",
    "status",
    "anomaly_notes",
]

MAX_PER_ANIMAL_FAILURES = 2
MAX_COHORT_FAILURES = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phase_7e.reemit_tongue_pertrial_cohort")


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_existing_manifest() -> dict[tuple[str, str], dict[str, str]]:
    """Return {(animal, date_iso): row_dict} for prior runs."""
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            out[(row["animal"], row["date"])] = row
    return out


def _append_manifest_row(row: dict[str, Any]) -> None:
    write_header = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_HEADER})


def _per_session_smoke(endpoints_json_path: Path) -> tuple[bool, str]:
    """Gate (a): endpoints JSON loads + schema intact.

    Schema-broken => FAIL. Biology-empty (all-null lick1_y_peak from a
    session with no kept licks post v7 gates F/D/E/M) => OK with
    anomaly_notes="zero_kept_licks_session". Relaxed 2026-05-26 after
    PS55/2025-05-07 (severe acute, 6 raw events across 97 trials, all
    rejected by gates — biologically valid, not a schema anomaly).
    """
    try:
        payload = json.loads(endpoints_json_path.read_text())
    except Exception as exc:
        return False, f"endpoints_json_unparseable:{exc!r}"
    if not isinstance(payload, dict):
        return False, "endpoints_json_not_dict"
    n_trials = payload.get("n_trials")
    if not isinstance(n_trials, int) or n_trials < 1:
        return False, f"n_trials_invalid:{n_trials!r}"
    try:
        y_peaks = payload["tongue"]["lick1_lick2_metrics"]["lick1_y_peak"]
    except Exception as exc:
        return False, f"lick1_y_peak_missing:{exc!r}"
    if not isinstance(y_peaks, list):
        return False, "lick1_y_peak_not_list"
    has_non_null = any(
        isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))
        for v in y_peaks
    )
    if not has_non_null:
        return True, "zero_kept_licks_session"
    return True, ""


def _process_one_session(
    animal: str,
    date: dt.date,
    resolver: PathResolver,
) -> dict[str, Any]:
    """Returns a manifest row dict (status in {OK, FAIL, SKIP})."""
    date_iso = date.isoformat()
    row: dict[str, Any] = {
        "animal": animal,
        "date": date_iso,
        "runtime_seconds_total": "",
        "n_outputs_written": 0,
        "output_sha256s_json": "",
        "status": "",
        "anomaly_notes": "",
    }

    interp_path = resolver.interpolated_trace(
        bodypart="tongue", animal=animal, date=date,
    )
    if not interp_path.exists():
        row["status"] = "SKIP"
        row["anomaly_notes"] = "no_tongue_interpolated_trace"
        return row

    t0 = time.perf_counter()
    try:
        paths = build_tongue_pertrial_by_animal_date(
            animal=animal,
            date=date,
            resolver=resolver,
            overwrite="force",
        )
    except Exception as exc:
        row["runtime_seconds_total"] = f"{time.perf_counter() - t0:.3f}"
        row["status"] = "FAIL"
        row["anomaly_notes"] = f"build_raised:{type(exc).__name__}:{exc!s}"
        return row
    elapsed = time.perf_counter() - t0
    row["runtime_seconds_total"] = f"{elapsed:.3f}"

    if not paths:
        row["status"] = "FAIL"
        row["anomaly_notes"] = "build_returned_none"
        return row

    endpoints_json = paths.get("endpoints_json")
    if endpoints_json is None or not Path(endpoints_json).exists():
        row["status"] = "FAIL"
        row["anomaly_notes"] = "endpoints_json_missing_after_build"
        return row

    ok, smoke_reason = _per_session_smoke(Path(endpoints_json))
    if not ok:
        row["status"] = "FAIL"
        row["anomaly_notes"] = f"smoke_fail:{smoke_reason}"
        return row

    shas: dict[str, str] = {}
    for key, path in paths.items():
        p = Path(path)
        shas[key] = _sha256(p)
    row["n_outputs_written"] = len(paths)
    row["output_sha256s_json"] = json.dumps(shas, sort_keys=True)
    row["status"] = "OK"
    row["anomaly_notes"] = smoke_reason  # "" or "zero_kept_licks_session"
    return row


def _iter_planned_sessions(
    animals: tuple[str, ...],
) -> list[tuple[str, dt.date]]:
    plan: list[tuple[str, dt.date]] = []
    for animal in animals:
        for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
            plan.append((animal, date))
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal (default: full cohort, COHORT_ORDER).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on number of fresh sessions processed this invocation "
             "(for first-50 calibration; resume-skip rows do not count).",
    )
    args = parser.parse_args(argv)

    animals = (args.animal,) if args.animal else COHORT_ORDER
    resolver = PathResolver()

    prior = _read_existing_manifest()
    log.info("Prior manifest rows: %d (OK + FAIL + SKIP)", len(prior))

    planned = _iter_planned_sessions(animals)
    log.info(
        "Planned fresh-cohort sessions: %d across %s",
        len(planned),
        ",".join(animals),
    )

    cohort_failures = sum(
        1 for r in prior.values() if r["status"] == "FAIL"
    )
    per_animal_failures: dict[str, int] = {a: 0 for a in animals}
    for r in prior.values():
        if r["status"] == "FAIL" and r["animal"] in per_animal_failures:
            per_animal_failures[r["animal"]] += 1

    processed_this_invocation = 0
    new_ok = new_fail = new_skip = 0

    for animal, date in planned:
        key = (animal, date.isoformat())
        if key in prior and prior[key]["status"] == "OK":
            continue

        if cohort_failures >= MAX_COHORT_FAILURES:
            log.error(
                "STOP: cohort failures %d >= threshold %d (across invocations)",
                cohort_failures, MAX_COHORT_FAILURES,
            )
            return 2
        if per_animal_failures.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
            log.error(
                "STOP: %s failures %d >= per-animal threshold %d",
                animal, per_animal_failures[animal], MAX_PER_ANIMAL_FAILURES,
            )
            return 2

        if args.limit is not None and processed_this_invocation >= args.limit:
            log.info(
                "Limit %d reached for this invocation; stopping cleanly.",
                args.limit,
            )
            break

        log.info("[%s %s] starting", animal, date.isoformat())
        row = _process_one_session(animal, date, resolver)
        _append_manifest_row(row)
        processed_this_invocation += 1

        if row["status"] == "OK":
            new_ok += 1
            log.info(
                "[%s %s] OK in %ss (%d outputs)",
                animal, date.isoformat(),
                row["runtime_seconds_total"], row["n_outputs_written"],
            )
        elif row["status"] == "SKIP":
            new_skip += 1
            log.info("[%s %s] SKIP (%s)", animal, date.isoformat(), row["anomaly_notes"])
        else:
            new_fail += 1
            cohort_failures += 1
            per_animal_failures[animal] = per_animal_failures.get(animal, 0) + 1
            log.error(
                "[%s %s] FAIL: %s",
                animal, date.isoformat(), row["anomaly_notes"],
            )
            log.error("STOP: per-session failure (single FAIL halts invocation).")
            return 2

    log.info(
        "Invocation summary: processed=%d (new_OK=%d, new_SKIP=%d, new_FAIL=%d)",
        processed_this_invocation, new_ok, new_skip, new_fail,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
