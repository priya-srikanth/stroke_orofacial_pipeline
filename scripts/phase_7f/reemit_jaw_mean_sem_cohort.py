"""Phase 7f Step 4 — jaw mean+SEM cohort re-emit (reads v3.4 cleaned_traces).

Surgical driver dedicated to the jaw-only mean+SEM + mean_video re-emit
described in docs/prompts/phase-7f-jaw-cleanup-cohort-reemit-kickoff.md
Step 4. Equivalent in spirit to
scripts/phase_7e/reemit_tongue_mean_sem_cohort.py but for the jaw
bodypart branch.

With ``configs/defaults.yaml`` setting
``dlc_kinematics.jaw.use_cleaned_traces: true`` (Phase 7f default), all
loaders inside mean_sem_visual now route through
``resolver.cleaned_trace(bodypart="jaw", ...)`` (Phase 7f Step 1 output)
in place of ``resolver.interpolated_trace(bodypart="jaw", ...)`` (v5p3
raw). Plot title source labels show ``v3.4-cleaned`` instead of
``v5p3``; per-frame numerics reflect the cleanup.

Outputs land at:
  pipeline_outputs/dlc_kinematics/mean_sem/jaw/<center_mode>/<window>/
      <plot_family>/<animal>/...
  pipeline_outputs/dlc_kinematics/mean_sem/jaw/<center_mode>/<window>/
      mean_video/<animal>/...   (videos per Q-2)

Per-animal call: build_mean_sem_cohort(bodypart="jaw", animal=...,
                                       include_mean_video=True,
                                       overwrite="force").

Manifest at .scratch_phase_7f_step4/mean_sem_manifest.csv (separate
from Step 2's cohort_manifest.csv so per-animal rows don't intermix).

NOT in scope: tongue mean+SEM (Phase 7e territory, already re-emitted)
+ cross-session tongue_jaw_mismatch (handled in a separate CC session
per Priya 2026-05-26).

CLI:
  python scripts/phase_7f/reemit_jaw_mean_sem_cohort.py
  python scripts/phase_7f/reemit_jaw_mean_sem_cohort.py --animal PS46
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

from stroke_orofacial.dlc_kinematics import build_mean_sem_cohort
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")
SCRATCH_DIR = Path(".scratch_phase_7f_step4")
MANIFEST_PATH = SCRATCH_DIR / "mean_sem_manifest.csv"
MANIFEST_HEADER = [
    "animal", "runtime_seconds_total", "n_paths_written",
    "status", "anomaly_notes",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phase_7f.reemit_jaw_mean_sem_cohort")


def _read_prior_manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[str, str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["animal"]] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    write_header = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in MANIFEST_HEADER})


def _process_animal(animal: str, resolver: PathResolver) -> dict:
    t0 = time.perf_counter()
    log.info("[%s] starting mean+SEM cohort emit (bodypart=jaw)", animal)
    try:
        paths = build_mean_sem_cohort(
            bodypart="jaw",
            animal=animal,
            resolver=resolver,
            include_mean_video=True,
            allow_gif_fallback=False,
            overwrite="force",
        )
    except Exception as exc:
        return {
            "animal": animal,
            "runtime_seconds_total": f"{time.perf_counter() - t0:.3f}",
            "n_paths_written": 0,
            "status": "FAIL",
            "anomaly_notes": f"{type(exc).__name__}:{exc!s}",
        }
    elapsed = time.perf_counter() - t0
    n_paths = sum(
        len(v) if isinstance(v, list) else 1 for v in (paths or {}).values()
    )
    log.info("[%s] OK in %.1fs (%d paths)", animal, elapsed, n_paths)
    return {
        "animal": animal,
        "runtime_seconds_total": f"{elapsed:.3f}",
        "n_paths_written": n_paths,
        "status": "OK",
        "anomaly_notes": "",
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
        if prior.get(animal) == "OK":
            log.info("[%s] skip (prior OK)", animal)
            n_skip += 1
            continue
        row = _process_animal(animal, resolver)
        _append_manifest(row)
        if row["status"] == "OK":
            n_ok += 1
        else:
            n_fail += 1
            log.error("[%s] FAIL: %s", animal, row["anomaly_notes"])
            return 2

    log.info("Step 4 summary: OK=%d SKIP=%d FAIL=%d", n_ok, n_skip, n_fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
