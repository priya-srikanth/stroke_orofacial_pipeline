"""Phase 7f Step 1 — jaw v3.4 cleaned_traces cohort re-emit.

Reconstructed producer (chore substrate-routing-and-secondary-spout-per-half-fix
Stage 0b, 2026-05-31). The original Step-1 script was gitignored scratch and
lost; the algorithm was lifted into
``src/stroke_orofacial/dlc_kinematics/jaw_cleanup_v34.py`` (faithful port of the
scratch v3.4 sim, validated 0-diff). This driver loops the cohort and writes
``dlc_kinematics/cleaned_traces/jaw/<animal>/<YYYYMMDD>.parquet``.

This producer is the canonical v3.4 jaw cleanup. The PRE-EXISTING on-disk jaw
cleaned_traces were written by an older over-aggressive version that wiped real
jaw deflections to baseline (cross-cohort review 2026-05-31: 16 real licks
saved by v3.4 vs 5 noise blips; up to 116px/156ms). Re-running this driver with
``overwrite="force"`` replaces them with the corrected v3.4 output.

Cohort enumeration:
  - Primary: yaml_driven_session_dates(animal, analysis_context="dlc"). INCLUDES
    secondary-spout (Pattern B) bare halves — they are normal DLC sessions. No
    per-date secondary_spout skip (the per-half fix; the b half is never
    enumerated here). Excluded dates are dropped upstream by the dlc filter.
  - Runtime pre-check: the producer returns None when the v5p3
    interpolated_traces/jaw parquet is missing or the session has no usable
    baseline => manifest status="SKIP".

Manifest: .scratch_chore_phase_7f/jaw_cleaned_traces_manifest.csv (append-only;
resume skips rows with status="OK").

CLI:
  --animal PS54         single animal (default: full COHORT_ORDER)
  --date 2025-05-05     single date (pilot scope; requires --animal)
  --limit N             cap fresh sessions this invocation
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.dlc_kinematics import build_jaw_cleaned_trace_by_animal_date
from stroke_orofacial.paths import PathResolver

COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
MAX_PER_ANIMAL_FAILURES = 2
MAX_COHORT_FAILURES = 5

SCRATCH_DIR = Path(".scratch_chore_phase_7f")
MANIFEST_PATH = SCRATCH_DIR / "jaw_cleaned_traces_manifest.csv"
MANIFEST_HEADER = [
    "animal", "date", "runtime_seconds", "sha256", "status", "anomaly_notes",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phase_7f.reemit_jaw_cleaned_traces")


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_existing_manifest() -> dict[tuple[str, str], dict[str, str]]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[(row["animal"], row["date"])] = row  # latest row wins
    return out


def _append_manifest(row: dict[str, Any]) -> None:
    write_header = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_HEADER})


def _process_one_session(
    animal: str, date: dt.date, resolver: PathResolver,
) -> dict[str, Any]:
    date_iso = date.isoformat()
    row: dict[str, Any] = {
        "animal": animal, "date": date_iso, "runtime_seconds": "",
        "sha256": "", "status": "", "anomaly_notes": "",
    }
    t0 = time.perf_counter()
    try:
        out_path = build_jaw_cleaned_trace_by_animal_date(
            animal, date, resolver, overwrite="force",
        )
    except Exception as exc:
        row["runtime_seconds"] = f"{time.perf_counter() - t0:.3f}"
        row["status"] = "FAIL"
        row["anomaly_notes"] = f"build_raised:{type(exc).__name__}:{exc!s}"
        return row
    row["runtime_seconds"] = f"{time.perf_counter() - t0:.3f}"
    if out_path is None:
        row["status"] = "SKIP"
        row["anomaly_notes"] = "no_input_or_baseline"
        return row
    row["sha256"] = _sha256(Path(out_path))
    row["status"] = "OK"
    return row


def _iter_planned_sessions(
    animals: tuple[str, ...], only_date: dt.date | None,
) -> list[tuple[str, dt.date]]:
    plan: list[tuple[str, dt.date]] = []
    for animal in animals:
        for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
            if only_date is not None and date != only_date:
                continue
            plan.append((animal, date))
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--animal", choices=COHORT_ORDER, default=None)
    parser.add_argument(
        "--date", default=None,
        help="ISO date (YYYY-MM-DD); requires --animal. Pilot/single-session.",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    only_date = dt.date.fromisoformat(args.date) if args.date else None
    if only_date is not None and not args.animal:
        parser.error("--date requires --animal")

    animals = (args.animal,) if args.animal else COHORT_ORDER
    resolver = PathResolver()
    prior = _read_existing_manifest()
    log.info("Prior manifest rows: %d", len(prior))

    planned = _iter_planned_sessions(animals, only_date)
    log.info(
        "Planned sessions: %d across %s%s",
        len(planned), ",".join(animals),
        f" (date={only_date})" if only_date else "",
    )

    cohort_failures = sum(
        1 for r in prior.values() if r["status"] == "FAIL"
    )
    per_animal_failures: dict[str, int] = {a: 0 for a in animals}
    for r in prior.values():
        if r["status"] == "FAIL" and r["animal"] in per_animal_failures:
            per_animal_failures[r["animal"]] += 1

    processed = new_ok = new_fail = new_skip = 0
    for animal, date in planned:
        key = (animal, date.isoformat())
        if key in prior and prior[key]["status"] == "OK":
            continue
        if cohort_failures >= MAX_COHORT_FAILURES:
            log.error("STOP: cohort failures %d", cohort_failures)
            return 2
        if per_animal_failures.get(animal, 0) >= MAX_PER_ANIMAL_FAILURES:
            log.error("STOP: %s failures %d", animal, per_animal_failures[animal])
            return 2
        if args.limit is not None and processed >= args.limit:
            log.info("Hit --limit %d; stopping.", args.limit)
            break

        row = _process_one_session(animal, date, resolver)
        _append_manifest(row)
        processed += 1
        if row["status"] == "OK":
            new_ok += 1
            log.info("[%s %s] OK in %ss", animal, date.isoformat(),
                     row["runtime_seconds"])
        elif row["status"] == "SKIP":
            new_skip += 1
            log.info("[%s %s] SKIP (%s)", animal, date.isoformat(),
                     row["anomaly_notes"])
        else:
            new_fail += 1
            cohort_failures += 1
            per_animal_failures[animal] = per_animal_failures.get(animal, 0) + 1
            log.error("[%s %s] FAIL (%s)", animal, date.isoformat(),
                      row["anomaly_notes"])

    log.info(
        "Invocation summary: processed=%d (OK=%d SKIP=%d FAIL=%d)",
        processed, new_ok, new_skip, new_fail,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
