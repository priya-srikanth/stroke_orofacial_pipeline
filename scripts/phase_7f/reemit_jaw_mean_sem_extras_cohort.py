"""Phase 7f / CC #9 chore — re-emit jaw individual_sessions + trial_overlays
mean+SEM siblings (jaw-only counterpart to the tongue Stage 4b extras driver).

`build_mean_sem_cohort` (the jaw mean_sem cohort driver) emits only
session_overlays + binned_overlays + mean_trace (mean_xy_overlays) +
mean_video. It does NOT emit the two per-session families:

  build_individual_sessions_animal -> mean_sem/jaw/<center>/<win>/individual_sessions/
  build_trial_overlays_animal      -> mean_sem/jaw/<center>/<win>/trial_overlays/

Both read the jaw **v3.4 cleaned_traces** parquet — `_use_cleaned_traces`
defaults True for jaw, so `build_cohort_aggregates` routes through
`resolver.cleaned_trace(...)`. (The tongue sibling's older docstring claims
`interpolated_traces`; that predates the 2026-05-30 cleaned-trace flip and is
stale for both bodyparts.) The jaw v3.4 re-emit therefore changes these
families, so they must be re-rendered — they were missed by the cohort driver.

NOT in scope (DO NOT re-emit here):
  - session_overlays / binned_overlays / mean_trace / mean_xy_overlays /
    mean_video (covered by reemit_jaw_mean_sem_cohort.py)
  - tongue (phase_7e territory)

Per-half: `yaml_driven_session_dates` yields one entry per calendar date; the
bare half's cleaned_traces parquet is read by date. A secondary-spout `b` half
has no DLC trace, so it never enters the cohort — per-half-safe by construction.

CLI:
  python scripts/phase_7f/reemit_jaw_mean_sem_extras_cohort.py
  python scripts/phase_7f/reemit_jaw_mean_sem_extras_cohort.py --animal PS54
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.dlc_kinematics import (
    build_individual_sessions_animal,
    build_trial_overlays_animal,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
# Same window pairs as the tongue extras driver / Phase 7c.2 aggregates.
MEAN_SEM_TIME_WINDOWS_MS = ((100, 1000), (500, 5000))

SCRATCH_DIR = Path(".scratch_chore_phase_7e_reemit")
MANIFEST_PATH = SCRATCH_DIR / "jaw_stage4b_manifest.csv"
MANIFEST_HEADER = [
    "animal", "stage", "window_ms",
    "runtime_seconds", "n_paths_written",
    "status", "anomaly_notes",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phase_7f.reemit_jaw_mean_sem_extras_cohort")


def _read_prior_manifest() -> dict[tuple[str, str, str], str]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[tuple[str, str, str], str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[(row["animal"], row["stage"], row["window_ms"])] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    write_header = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_HEADER})


def _run_one(
    animal: str, stage: str, pre_ms: int, post_ms: int,
    dates: list, resolver: PathResolver,
) -> dict:
    key_win = f"{pre_ms}pre_{post_ms}post"
    t0 = time.perf_counter()
    try:
        if stage == "individual_sessions":
            paths = build_individual_sessions_animal(
                "jaw", animal, dates, resolver,
                tone_pre_ms=pre_ms, tone_post_ms=post_ms,
                overwrite="force",
            )
        elif stage == "trial_overlays":
            paths = build_trial_overlays_animal(
                "jaw", animal, dates, resolver,
                tone_pre_ms=pre_ms, tone_post_ms=post_ms,
                overwrite="force",
            )
        else:
            raise ValueError(f"unknown stage: {stage!r}")
    except Exception as exc:
        return {
            "animal": animal, "stage": stage, "window_ms": key_win,
            "runtime_seconds": f"{time.perf_counter() - t0:.3f}",
            "n_paths_written": 0,
            "status": "FAIL",
            "anomaly_notes": f"{type(exc).__name__}:{exc!s}",
        }
    elapsed = time.perf_counter() - t0
    n_paths = len(paths) if paths else 0
    log.info("[%s %s %s] OK in %.1fs (%d paths)",
             animal, stage, key_win, elapsed, n_paths)
    return {
        "animal": animal, "stage": stage, "window_ms": key_win,
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
    args = parser.parse_args(argv)

    resolver = PathResolver()
    prior = _read_prior_manifest()
    log.info("Prior manifest rows: %d", len(prior))

    animals = (args.animal,) if args.animal else COHORT_ORDER
    n_ok = n_fail = n_skip = 0
    for animal in animals:
        dates = list(yaml_driven_session_dates(animal))
        for pre_ms, post_ms in MEAN_SEM_TIME_WINDOWS_MS:
            key_win = f"{pre_ms}pre_{post_ms}post"
            for stage in ("individual_sessions", "trial_overlays"):
                key = (animal, stage, key_win)
                if prior.get(key) == "OK":
                    log.info("[%s %s %s] skip (prior OK)", animal, stage, key_win)
                    n_skip += 1
                    continue
                log.info("[%s %s %s] starting (%d dates)",
                         animal, stage, key_win, len(dates))
                row = _run_one(animal, stage, pre_ms, post_ms, dates, resolver)
                _append_manifest(row)
                if row["status"] == "OK":
                    n_ok += 1
                else:
                    n_fail += 1
                    log.error("[%s %s %s] FAIL: %s",
                              animal, stage, key_win, row["anomaly_notes"])
                    return 2

    log.info("Jaw Stage 4b summary: OK=%d SKIP=%d FAIL=%d", n_ok, n_skip, n_fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
