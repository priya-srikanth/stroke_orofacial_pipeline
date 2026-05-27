"""Phase 7f Step 2 — jaw_pertrial cohort re-emit (reads v3.4 cleaned_traces).

Surgical driver dedicated to the jaw_pertrial re-emit described in
docs/prompts/phase-7f-jaw-cleanup-cohort-reemit-kickoff.md. Equivalent
in spirit to scripts/phase_7e/reemit_tongue_pertrial_cohort.py but
narrowed to the single jaw_pertrial output per session.

With ``configs/defaults.yaml`` setting
``dlc_kinematics.jaw.use_cleaned_traces: true`` (Phase 7f default),
``build_jaw_pertrial_by_animal_date`` will load
``cleaned_traces/jaw/<animal>/<date>.parquet`` (Phase 7f Step 1 output)
in place of ``interpolated_traces/jaw/...`` (v5p3 raw), and stamp
``interpolation_version="v3.4-cleaned"`` + ``use_cleaned_traces=true``
into the JSON metadata block.

Per-session writes (overwrite="force"):
  - pipeline_outputs/dlc_kinematics/per_trial/jaw/<animal>/<YYYYMMDD>.json

Cohort enumeration (mirrors Phase 7e Addendum #1):
  - Primary: yaml_driven_session_dates(animal, analysis_context="dlc")
  - (b) Defensive pre-filter: skip (animal, date) entries listed in
    configs/session_overrides.yaml secondary_spout_sessions: — those
    sessions lack DLC inference inputs upstream of any per-trial driver.
  - (c) Runtime pre-check: resolver.cleaned_trace(bodypart="jaw",
    animal, date).exists() — missing => manifest status="SKIP" with
    anomaly_notes="no_jaw_cleaned_trace"; NOT counted toward failure
    anomaly thresholds. (Cleaned-trace coverage matches Phase 7f Step 1's
    231/352 OK set — sessions outside that set were already SKIPed by
    Step 1 and the same set is SKIPed here.)

Manifest:
  .scratch_phase_7f_step2/cohort_manifest.csv
  Columns: animal, date, runtime_seconds_total, n_outputs_written,
           output_sha256s_json, status, anomaly_notes
  Append-only. Resume-on-relaunch skips rows with status="OK".

Anomaly thresholds (per kickoff Failure-recovery pattern):
  - Per-session FAIL: stop immediately.
  - >=2 FAIL within the same animal: stop after the second.
  - >=5 FAIL cohort-wide (tracked across invocations via manifest):
    stop and re-scope.
  - SKIP rows do NOT count toward these thresholds.

CLI:
  python scripts/phase_7f/reemit_jaw_pertrial_cohort.py
  python scripts/phase_7f/reemit_jaw_pertrial_cohort.py --animal PS46
  python scripts/phase_7f/reemit_jaw_pertrial_cohort.py --limit 10  # pilot
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

import yaml

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.dlc_kinematics import build_jaw_pertrial_by_animal_date
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
SCRATCH_DIR = Path(".scratch_phase_7f_step2")
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
log = logging.getLogger("phase_7f.reemit_jaw_pertrial_cohort")


def _load_secondary_spout_exclusion_set(
    session_overrides_yaml: Path = Path("configs/session_overrides.yaml"),
) -> set[tuple[str, dt.date]]:
    """Read secondary_spout_sessions: as a set of (animal, date)."""
    cfg = yaml.safe_load(session_overrides_yaml.read_text())
    out: set[tuple[str, dt.date]] = set()
    for animal, dates in (cfg.get("secondary_spout_sessions") or {}).items():
        for iso in dates or {}:
            out.add((animal, dt.date.fromisoformat(iso)))
    return out


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_existing_manifest() -> dict[tuple[str, str], dict[str, str]]:
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
    """Gate (a): jaw_pertrial JSON loads + schema intact + metadata stamps
    confirm v3.4-cleaned trace source.

    Schema-broken => FAIL. Biology-empty (zero kept trials, all-NaN
    baselines) => OK with anomaly_notes="zero_eligible_trials_session"
    by analogy with the Phase 7e tongue smoke relaxation 2026-05-26.
    """
    try:
        payload = json.loads(endpoints_json_path.read_text())
    except Exception as exc:
        return False, f"endpoints_json_unparseable:{exc!r}"
    if not isinstance(payload, dict):
        return False, "endpoints_json_not_dict"
    n_trials = payload.get("n_trials")
    if not isinstance(n_trials, int) or n_trials < 0:
        return False, f"n_trials_invalid:{n_trials!r}"
    meta = payload.get("metadata")
    if not isinstance(meta, dict):
        return False, "metadata_missing"
    interp_v = meta.get("interpolation_version")
    if interp_v != "v3.4-cleaned":
        return False, f"interpolation_version_unexpected:{interp_v!r}"
    if meta.get("use_cleaned_traces") is not True:
        return False, f"use_cleaned_traces_unexpected:{meta.get('use_cleaned_traces')!r}"
    try:
        baselines = payload["jaw_pertrial"]["jaw_baseline_mean"]
    except Exception as exc:
        return False, f"jaw_baseline_mean_missing:{exc!r}"
    if not isinstance(baselines, list):
        return False, "jaw_baseline_mean_not_list"
    if n_trials == 0:
        return True, "zero_trial_session"
    has_non_null = any(
        isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))
        for v in baselines
    )
    if not has_non_null:
        return True, "zero_eligible_trials_session"
    return True, ""


def _process_one_session(
    animal: str,
    date: dt.date,
    resolver: PathResolver,
    exclusion_set: set[tuple[str, dt.date]],
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

    if (animal, date) in exclusion_set:
        row["status"] = "SKIP"
        row["anomaly_notes"] = "secondary_spout_session_no_dlc"
        return row

    cleaned_path = resolver.cleaned_trace(
        bodypart="jaw", animal=animal, date=date,
    )
    if not cleaned_path.exists():
        row["status"] = "SKIP"
        row["anomaly_notes"] = "no_jaw_cleaned_trace"
        return row

    t0 = time.perf_counter()
    try:
        out_path = build_jaw_pertrial_by_animal_date(
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

    if out_path is None or not Path(out_path).exists():
        row["status"] = "FAIL"
        row["anomaly_notes"] = "endpoints_json_missing_after_build"
        return row

    ok, smoke_reason = _per_session_smoke(Path(out_path))
    if not ok:
        row["status"] = "FAIL"
        row["anomaly_notes"] = f"smoke_fail:{smoke_reason}"
        return row

    shas = {"endpoints_json": _sha256(Path(out_path))}
    row["n_outputs_written"] = 1
    row["output_sha256s_json"] = json.dumps(shas, sort_keys=True)
    row["status"] = "OK"
    row["anomaly_notes"] = smoke_reason  # "" or "zero_eligible_trials_session"
    return row


def _iter_planned_sessions(
    animals: tuple[str, ...],
    exclusion_set: set[tuple[str, dt.date]],
) -> list[tuple[str, dt.date]]:
    plan: list[tuple[str, dt.date]] = []
    for animal in animals:
        for date in yaml_driven_session_dates(animal, analysis_context="dlc"):
            if (animal, date) in exclusion_set:
                continue
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
             "(for pilot calibration; resume-skip rows do not count).",
    )
    args = parser.parse_args(argv)

    animals = (args.animal,) if args.animal else COHORT_ORDER
    resolver = PathResolver()
    exclusion_set = _load_secondary_spout_exclusion_set()
    log.info("Loaded secondary_spout exclusion set: %d entries", len(exclusion_set))

    prior = _read_existing_manifest()
    log.info("Prior manifest rows: %d (OK + FAIL + SKIP)", len(prior))

    planned = _iter_planned_sessions(animals, exclusion_set)
    log.info(
        "Planned fresh-cohort sessions (after (b) pre-filter): %d across %s",
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
        row = _process_one_session(animal, date, resolver, exclusion_set)
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
