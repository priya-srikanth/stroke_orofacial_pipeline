"""Phase 7c.2 Task 3 — Cohort-wide per-session DLC re-emit (257 sessions).

Extends scripts/phase_7c1/reemit_pilot.py to cohort scope locked Q1.B in
Addendum #1:
  - 256 cohort-A bare sessions (per Task 1 archeology audit on the
    legacy spatial_reward_aligned/ tree, canonical config
    tongue_spout_midpoint/trials-all_-100to1000ms/<animal>/heatmap_*.npz).
  - 1 PS48/2025-03-14 Pattern A multi-half session via F-P-5 wiring
    (Task 2) + Phase 4 production force-emit (Task 2 Option A).
  - Cohort B b-half sessions explicitly OUT-OF-SCOPE (Addendum #1
    Finding 2; deferred to Phase 7-pre-secondary-spout-compare-DLC).

Per-session output scope — KINEMATICS-ONLY post Addendum #3 Q2.B
(Phase 7c.2 spatial architectural pivot LOCKED 2026-05-15 mid-Task-3):

  B. Phase 7a.2 interpolated traces (tongue + jaw) at
     interpolated_traces/<bp>/<animal>/<date>.parquet
  C. Phase 7a.3 per-trial features (tongue + jaw_pertrial endpoints) +
     licking dynamics + endpoints JSON at
     dlc_kinematics/features/tongue/<animal>/<date>.parquet
     dlc_kinematics/licking_dynamics/traces/<animal>/<date>.parquet
     dlc_kinematics/endpoints/<animal>/<date>.json
     dlc_kinematics/jaw_pertrial/endpoints/<animal>/<date>.json
  D. Phase 7a.4 tongue-angle within-session 9-PNG bundle at
     dlc_kinematics/tongue_angle/within_session/<animal>/<date>/*.png
  D-supplement. Phase 7a.5 tongue-jaw mismatch per-session at
     dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<date>.parquet
     dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<date>/*.png

Category A (Phase 6 spatial heatmap NPZ sweep) DROPPED per Addendum #3
Q2.B — cohort-wide cached NPZ tree eliminated; spatial visual gate
moves to compute-on-demand via render_tone_aligned_heatmap (Task 5).
PS46's already-completed Category-A NPZs (~1,134 cached at
spatial_tone_aligned/PS46/) are dead artifacts queued for Task 7
cleanup.

Per-session manifest schema (per Addendum #1):
  animal, date, runtime_seconds_total, runtime_seconds_{interpolation,
  spatial, pertrial_features, tongue_angle_figures, tongue_jaw_mismatch},
  n_outputs_written, output_sha256s_json, status, anomaly_notes.

Manifest path: .scratch_phase_7c2/cohort_manifest.csv (append-only;
resumability via skip-if-already-success-OK).

Per-animal sub-batching per Q7.A: invoke with --animal PS46 to process
one animal at a time. CC commits a per-animal log entry after each
animal pass: "chore(phase-7c.2): cohort re-emit complete for <animal>
(N sessions, runtime X.X hr)".

Order: PS46, PS47, PS48, PS49, PS50, PS51, PS54, PS55 (Cohort A order).

Anomaly handling (per kickoff Task 3):
  - Per-session failure: STOP immediately (return non-zero).
  - Per-animal failure rate >= 2 sessions in same animal: STOP after
    the second failure within the animal.
  - Cohort-wide failure rate >= 5 sessions: STOP and re-scope (driver
    tracks across invocations via reading prior manifest).

Output writes per Q2.A:
  - Spatial: new-tree write at spatial_tone_aligned/ (legacy
    spatial_reward_aligned/ untouched).
  - Kinematics + interpolated_traces: in-place overwrite at standard
    paths.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_session_overrides
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.dlc_kinematics import (
    build_interpolated_trace_by_animal_date,
    build_tongue_pertrial_by_animal_date,
    build_jaw_pertrial_by_animal_date,
    render_tongue_qc_figures,
    classify_tongue_jaw_mismatch_by_animal_date,
    render_within_session_figures,
)


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

MANIFEST_PATH = Path(".scratch_phase_7c2/cohort_manifest.csv")
MANIFEST_HEADER = [
    "animal", "date",
    "runtime_seconds_total",
    "runtime_seconds_interpolation",
    "runtime_seconds_spatial",
    "runtime_seconds_pertrial_features",
    "runtime_seconds_tongue_angle_figures",
    "runtime_seconds_tongue_jaw_mismatch",
    "n_outputs_written",
    "output_sha256s_json",
    "status",
    "anomaly_notes",
]

# Cohort-level anomaly thresholds
MAX_PER_ANIMAL_FAILURES = 2
MAX_COHORT_FAILURES = 5

# Canonical legacy config used by Task 1 audit (and to enumerate cohort-A bare sessions).
CANON_BP_CM = "tongue_spout_midpoint"
CANON_WIN = "trials-all_-100to1000ms"


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.reemit_cohort")


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _enumerate_cohort_a_bare_dates(animal: str, resolver: PathResolver) -> list[str]:
    """Walk legacy `spatial_reward_aligned/<canon>/<animal>/heatmap_*.npz` to
    enumerate cohort-A bare-session date strings, FILTERED to in-YAML-range
    per ``configs/animals.yaml <animal>.sessions.start/end``.

    Per Phase 7c.2 Addendum #5 Q1.C: 9 sessions on the legacy tree
    (PS51/PS54/PS55 × 2025-04-16/17/18) are pre-cohort-launch baseline
    acquisitions explicitly excluded from cohort scope per F-P-6
    cohort-boundary policy + animals.yaml header comment. Phase 8a.10.1
    Phase 2 re-emit gated by YAML so their licks NPZs no longer exist,
    blocking Phase 7a kinematics consumers if processed. Filter here
    before enumeration to avoid that failure mode.

    Forward-pointer (memory
    project_cohort_enumeration_should_be_yaml_driven_forward_pointer.md):
    after Task 7 deletes the legacy spatial tree this walk won't work
    for future re-runs; enumeration should switch to YAML-driven
    (iterate ``animal_info.session_start`` to ``.session_end`` directly).
    Not in 7c.2 scope; small chore-PR post-7c.2.
    """
    output_root = resolver.pipeline_outputs("dlc_analysis")
    canon_dir = output_root / "spatial_reward_aligned" / CANON_BP_CM / CANON_WIN / animal
    if not canon_dir.exists():
        return []
    animal_info = get_animal(animal)
    start = animal_info.session_start
    end = animal_info.session_end
    dates: list[str] = []
    excluded: list[str] = []
    for npz in sorted(canon_dir.glob("heatmap_*.npz")):
        m = re.match(r"heatmap_(\d{8})\.npz", npz.name)
        if not m:
            continue
        date_str = m.group(1)
        d = dt.date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))
        if start <= d <= end:
            dates.append(date_str)
        else:
            excluded.append(date_str)
    if excluded:
        log.info(
            f"  YAML-range filter ({animal}, {start.isoformat()}..{end.isoformat()}): "
            f"excluded {len(excluded)} out-of-range dates: {excluded}"
        )
    return sorted(dates)


def _enumerate_pattern_a_dates(animal: str, overrides: dict) -> list[str]:
    """List multi_half_sessions entries for this animal."""
    mh = overrides.get("multi_half_sessions", {}) or {}
    entry = mh.get(animal, {}) or {}
    return sorted(entry.keys())


def _load_manifest_so_far() -> dict[tuple[str, str], str]:
    """Read prior manifest rows; return {(animal, date_iso): status}."""
    if not MANIFEST_PATH.exists():
        return {}
    out: dict[tuple[str, str], str] = {}
    with MANIFEST_PATH.open("r", newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            out[(row["animal"], row["date"])] = row["status"]
    return out


def _append_manifest(row: dict) -> None:
    is_new = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def _build_failed_row(animal: str, date: dt.date, session_t0: float, anomalies: list[str]) -> dict:
    return {
        "animal": animal, "date": date.isoformat(),
        "runtime_seconds_total": f"{time.perf_counter() - session_t0:.3f}",
        "runtime_seconds_interpolation": "",
        "runtime_seconds_spatial": "",
        "runtime_seconds_pertrial_features": "",
        "runtime_seconds_tongue_angle_figures": "",
        "runtime_seconds_tongue_jaw_mismatch": "",
        "n_outputs_written": "0",
        "output_sha256s_json": "{}",
        "status": "ERR",
        "anomaly_notes": "; ".join(anomalies),
    }


def _run_session(
    animal: str, date: dt.date, resolver: PathResolver,
) -> tuple[bool, dict]:
    """Run the kinematics-only per-session DLC pipeline (Categories B-D +
    supplements; Category A dropped per Addendum #3 Q2.B) on
    (animal, date). Returns (ok, manifest_row).
    """
    log.info(f"=== {animal}/{date.isoformat()} ===")
    session_t0 = time.perf_counter()
    anomalies: list[str] = []
    outputs_sha: dict[str, str] = {}

    # ----- Category B: interpolated_traces (tongue + jaw) -----
    t0 = time.perf_counter()
    try:
        for bp in ("tongue", "jaw"):
            out_path = build_interpolated_trace_by_animal_date(
                animal=animal, date=date, bodypart=bp,
                resolver=resolver, overwrite="force",
            )
            outputs_sha[str(out_path)] = _sha256(out_path)
        rt_B = time.perf_counter() - t0
        log.info(f"  [B] interpolation: {rt_B:.1f}s")
    except Exception as ex:
        anomalies.append(f"B-interpolation: {ex!r}")
        log.error(f"  [B] interpolation: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    # Category A (Phase 6 spatial heatmap NPZ sweep) DROPPED per Addendum #3
    # Q2.B — the cached spatial_tone_aligned/ tree is eliminated under
    # Interpretation 1. Visual gate now renders on-demand from Phase 4
    # centered parquets via Task 5's render_tone_aligned_heatmap wrapper.
    rt_A = 0.0

    # ----- Category C: per-trial features (tongue + jaw_pertrial endpoints = D-supp-2) -----
    t0 = time.perf_counter()
    try:
        tongue_pertrial_paths = build_tongue_pertrial_by_animal_date(
            animal=animal, date=date, resolver=resolver, overwrite="force",
        )
        if tongue_pertrial_paths:
            for label, p in tongue_pertrial_paths.items():
                if p and p.exists():
                    outputs_sha[str(p)] = _sha256(p)
        jaw_pertrial_path = build_jaw_pertrial_by_animal_date(
            animal=animal, date=date, resolver=resolver, overwrite="force",
        )
        if jaw_pertrial_path and jaw_pertrial_path.exists():
            outputs_sha[str(jaw_pertrial_path)] = _sha256(jaw_pertrial_path)
        rt_C = time.perf_counter() - t0
        log.info(f"  [C/D-supp-2] per-trial features: {rt_C:.1f}s")
    except Exception as ex:
        anomalies.append(f"C-pertrial: {ex!r}")
        log.error(f"  [C] pertrial: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    # ----- Category D: tongue angle within-session figures -----
    t0 = time.perf_counter()
    try:
        qc_paths = render_tongue_qc_figures(
            animal=animal, date=date, resolver=resolver, overwrite="force",
        )
        n_d_pngs = sum(len(paths) for paths in qc_paths.values()) if qc_paths else 0
        rt_D = time.perf_counter() - t0
        log.info(f"  [D] tongue angle figures: {rt_D:.1f}s ({n_d_pngs} PNGs)")
    except Exception as ex:
        anomalies.append(f"D-tongue_angle: {ex!r}")
        log.error(f"  [D] tongue_angle: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    # ----- Category D-supplement: tongue-jaw mismatch per-session -----
    t0 = time.perf_counter()
    try:
        cand_path = classify_tongue_jaw_mismatch_by_animal_date(
            animal=animal, date=date, resolver=resolver, overwrite="force",
        )
        if cand_path and cand_path.exists():
            outputs_sha[str(cand_path)] = _sha256(cand_path)
        mismatch_figs = render_within_session_figures(
            animal=animal, date=date, resolver=resolver, overwrite="force",
        )
        n_dsupp_pngs = sum(len(paths) for paths in mismatch_figs.values()) if mismatch_figs else 0
        rt_Dsupp = time.perf_counter() - t0
        log.info(f"  [D-supp] tongue_jaw_mismatch: {rt_Dsupp:.1f}s ({n_dsupp_pngs} PNGs)")
    except Exception as ex:
        anomalies.append(f"D-supp-tongue_jaw_mismatch: {ex!r}")
        log.error(f"  [D-supp] tongue_jaw_mismatch: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    session_rt = time.perf_counter() - session_t0
    log.info(f"  SESSION TOTAL: {session_rt:.1f}s ({session_rt/60:.1f} min)")
    return True, {
        "animal": animal, "date": date.isoformat(),
        "runtime_seconds_total": f"{session_rt:.3f}",
        "runtime_seconds_interpolation": f"{rt_B:.3f}",
        "runtime_seconds_spatial": f"{rt_A:.3f}",
        "runtime_seconds_pertrial_features": f"{rt_C:.3f}",
        "runtime_seconds_tongue_angle_figures": f"{rt_D:.3f}",
        "runtime_seconds_tongue_jaw_mismatch": f"{rt_Dsupp:.3f}",
        "n_outputs_written": str(len(outputs_sha)),
        "output_sha256s_json": json.dumps(outputs_sha, sort_keys=True),
        "status": "OK" if not anomalies else "PARTIAL",
        "anomaly_notes": "; ".join(anomalies),
    }


def _date_str_to_date(date_str: str) -> dt.date:
    return dt.date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))


def _process_animal(animal: str, resolver, overrides) -> tuple[int, int, int]:
    """Process all cohort-A bare + (PS48 only) Pattern A sessions for one animal.

    Returns (n_run, n_ok, n_fail). Stops within-animal if failure count >=
    MAX_PER_ANIMAL_FAILURES.
    """
    cohort_dates = _enumerate_cohort_a_bare_dates(animal, resolver)
    # Pattern A: PS48/20250314 has no legacy NPZ; add it for PS48 explicitly.
    pattern_a_dates = _enumerate_pattern_a_dates(animal, overrides)
    pa_set = set(pattern_a_dates)
    all_dates = sorted(set(cohort_dates) | pa_set)

    prior = _load_manifest_so_far()
    log.info(f"=== animal={animal}: {len(cohort_dates)} cohort-A bare + "
             f"{len(pa_set)} pattern-A = {len(all_dates)} total dates ===")

    n_run = n_ok = n_fail = 0
    animal_t0 = time.perf_counter()
    for date_str in all_dates:
        date = _date_str_to_date(date_str)
        key = (animal, date.isoformat())
        prior_status = prior.get(key)
        if prior_status == "OK":
            log.info(f"  [skip] {animal}/{date.isoformat()} already OK in prior manifest")
            continue
        if prior_status == "PARTIAL":
            log.info(f"  [skip] {animal}/{date.isoformat()} already PARTIAL in prior manifest")
            continue
        ok, row = _run_session(animal, date, resolver)
        _append_manifest(row)
        n_run += 1
        if ok:
            n_ok += 1
        else:
            n_fail += 1
            if n_fail >= MAX_PER_ANIMAL_FAILURES:
                log.error(f"=== animal={animal}: {n_fail} per-animal failures — "
                          f"STOP per kickoff anomaly trigger (>= {MAX_PER_ANIMAL_FAILURES}) ===")
                return n_run, n_ok, n_fail

    animal_rt = time.perf_counter() - animal_t0
    log.info(f"=== animal={animal}: complete — {n_ok}/{n_run} OK, {n_fail} failed, "
             f"runtime {animal_rt:.1f}s ({animal_rt/60:.1f} min) ===")
    return n_run, n_ok, n_fail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--animal",
        choices=COHORT_ORDER,
        help="Process a single animal. Default: iterate the full Cohort A "
             "order (PS46 → ... → PS55).",
    )
    args = parser.parse_args(argv)

    resolver = PathResolver()
    overrides = load_session_overrides()
    log.info(f"output_root: {resolver.pipeline_outputs('dlc_analysis')}")
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")

    animals = [args.animal] if args.animal else list(COHORT_ORDER)

    total_run = total_ok = total_fail = 0
    for animal in animals:
        n_run, n_ok, n_fail = _process_animal(animal, resolver, overrides)
        total_run += n_run
        total_ok += n_ok
        total_fail += n_fail
        if total_fail >= MAX_COHORT_FAILURES:
            log.error(f"COHORT STOP: {total_fail} >= {MAX_COHORT_FAILURES} "
                      f"cohort-wide failures — re-scope per kickoff anomaly trigger")
            return 1
        if n_fail >= MAX_PER_ANIMAL_FAILURES:
            log.error(f"ANIMAL STOP at {animal}: {n_fail} per-animal failures — "
                      f"see manifest for details")
            return 1

    log.info(f"=== COHORT RE-EMIT SUMMARY: {total_ok}/{total_run} OK, "
             f"{total_fail} failed across {len(animals)} animal(s) ===")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
