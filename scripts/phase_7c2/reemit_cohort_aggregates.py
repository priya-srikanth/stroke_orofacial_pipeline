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

from stroke_orofacial.cohort_enumeration import yaml_driven_session_dates
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.dlc_kinematics import (
    build_individual_sessions_animal,
    build_mean_sem_cohort,
    build_tongue_angle_cohort,
    build_trial_overlays_animal,
    render_cross_session_figures,
)
from stroke_orofacial.paths import PathResolver


COHORT_ORDER = ("PS46", "PS47", "PS48", "PS49", "PS50", "PS51", "PS54", "PS55")

MEAN_SEM_BODYPARTS = ("tongue", "jaw")
MEAN_SEM_TIME_WINDOWS_MS = ((100, 1000), (500, 5000))

MANIFEST_PATH = Path(".scratch_phase_7c2/cohort_aggregates_manifest.csv")
MANIFEST_HEADER = [
    "animal",
    "runtime_seconds_total",
    "runtime_seconds_tongue_angle_cohort",
    "runtime_seconds_mismatch_cross_session",
    "runtime_seconds_mean_sem_cohort",
    "runtime_seconds_individual_sessions",
    "runtime_seconds_trial_overlays",
    "runtime_seconds_day_binned",
    "n_tongue_angle_paths",
    "n_mismatch_paths",
    "n_mean_sem_paths",
    "n_individual_sessions_paths",
    "n_trial_overlays_paths",
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
        "runtime_seconds_individual_sessions": "",
        "runtime_seconds_trial_overlays": "",
        "runtime_seconds_day_binned": "",
        "n_tongue_angle_paths": "0",
        "n_mismatch_paths": "0",
        "n_mean_sem_paths": "0",
        "n_individual_sessions_paths": "0",
        "n_trial_overlays_paths": "0",
        "n_day_binned_paths": "0",
        "status": "ERR",
        "anomaly_notes": "; ".join(anomalies),
    }


def _enumerate_yaml_filtered_dates(animal: str, resolver: PathResolver) -> list[dt.date]:
    """Q67 (Addendum #57) — YAML-driven session-date enumeration.

    ``resolver`` retained for signature compatibility with prior callers
    but unused after the refactor: enumeration is pure YAML, no
    filesystem dependency on the legacy ``spatial_reward_aligned/``
    tree (which Q69 deletes).
    """
    del resolver  # no longer needed after Q67 refactor
    return yaml_driven_session_dates(animal)


def _resolve_mean_video_windows() -> list[tuple[int, int]] | None:
    """Read ``mean_sem_visual.mean_video.mean_video_windows_subset`` from
    defaults.yaml. Returns the per-window allow-list as ``(pre, post)``
    tuples, or ``None`` if the config doesn't define a subset.

    Per Phase 7a.6 C7.7: defaults.yaml ships ``[[100, 1000]]`` so videos
    render only for the short window. The longer window's mean_video
    render is skipped (proportional render cost vs marginal analytical
    value; Priya 2026-05-02). The caller forwards this to
    ``build_mean_sem_cohort(..., mean_video_windows=...)``.
    """
    defaults = load_defaults()
    subset = (
        defaults
        .get("dlc_kinematics", {})
        .get("mean_sem_visual", {})
        .get("mean_video", {})
        .get("mean_video_windows_subset")
    )
    if subset is None:
        return None
    return [(int(a), int(b)) for a, b in subset]


def _process_animal(animal: str, resolver: PathResolver) -> tuple[bool, dict]:
    """Run all 6 cohort-aggregate plot families for one animal. Returns (ok, row).

    Plot families (Addendum #6 Q11 expanded):
      E1. tongue_angle cohort (12 PNGs/animal)
      E2. tongue_jaw_mismatch cross_session figures
      E3. mean_sem cohort × 2 bodyparts (session_overlays + binned_overlays
          + mean_trace + mean_video per (bodypart, window))
      E3b. individual_sessions × 2 bodyparts × 2 windows × N dates
      E3c. trial_overlays × 2 bodyparts × 2 windows × N dates
      E4. day_binned licking_dynamics
    """
    log.info(f"=== animal={animal}: cohort-aggregate re-emit ===")
    animal_t0 = time.perf_counter()
    anomalies: list[str] = []

    # Pre-fetch YAML-filtered date list (used by E3b + E3c per-date renderers).
    dates = _enumerate_yaml_filtered_dates(animal, resolver)
    log.info(f"  Animal date count (YAML-filtered): {len(dates)}")
    mean_video_windows = _resolve_mean_video_windows()
    log.info(f"  mean_video_windows (C7.7 gate): {mean_video_windows}")

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

    # ----- E3: mean/SEM cohort (session_overlays + binned_overlays +
    #         mean_trace + mean_video) per bodypart -----
    # Per Addendum #6 Q11: include_mean_video=True (was unscoped False in
    # 275d922; restored). allow_gif_fallback=False per Phase 7a.6 C7.5
    # fail-loud convention (ffmpeg verified present in env). Per-window
    # gating via mean_video_windows from defaults.yaml C7.7 config:
    # short (100, 1000) window only renders MP4; longer (500, 5000) stays
    # PNG-only.
    t0 = time.perf_counter()
    n_ms = 0
    try:
        for bp in MEAN_SEM_BODYPARTS:
            ms_paths = build_mean_sem_cohort(
                bodypart=bp,
                animal=animal,
                resolver=resolver,
                include_mean_video=True,
                mean_video_windows=mean_video_windows,
                allow_gif_fallback=False,
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

    # ----- E3b: individual_sessions per (bodypart × time window) — Addendum #6 Q11 add -----
    # build_mean_sem_cohort does NOT call build_individual_sessions_animal;
    # invoke explicitly here so individual_sessions/<animal>/ gets per-date
    # PNGs at uniform animal-wide bounds.
    t0 = time.perf_counter()
    n_is = 0
    try:
        for bp in MEAN_SEM_BODYPARTS:
            for pre_ms, post_ms in MEAN_SEM_TIME_WINDOWS_MS:
                is_paths = build_individual_sessions_animal(
                    bp, animal, dates, resolver,
                    tone_pre_ms=pre_ms, tone_post_ms=post_ms,
                    overwrite="force",
                )
                n_is += len(is_paths) if is_paths else 0
        rt_is = time.perf_counter() - t0
        log.info(f"  [E3b] individual_sessions: {rt_is:.1f}s ({n_is} paths)")
    except Exception as ex:
        anomalies.append(f"E3b-individual_sessions: {ex!r}")
        log.error(f"  [E3b] individual_sessions: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    # ----- E3c: trial_overlays per (bodypart × time window) — Addendum #6 Q11 add -----
    # Same omission shape as E3b; explicit per-date invocation.
    t0 = time.perf_counter()
    n_to = 0
    try:
        for bp in MEAN_SEM_BODYPARTS:
            for pre_ms, post_ms in MEAN_SEM_TIME_WINDOWS_MS:
                to_paths = build_trial_overlays_animal(
                    bp, animal, dates, resolver,
                    tone_pre_ms=pre_ms, tone_post_ms=post_ms,
                    overwrite="force",
                )
                n_to += len(to_paths) if to_paths else 0
        rt_to = time.perf_counter() - t0
        log.info(f"  [E3c] trial_overlays: {rt_to:.1f}s ({n_to} paths)")
    except Exception as ex:
        anomalies.append(f"E3c-trial_overlays: {ex!r}")
        log.error(f"  [E3c] trial_overlays: ERR {ex!r}")
        return False, _build_err_row(animal, animal_t0, anomalies)

    # ----- E4: day-binned licking-dynamics — DEPRECATED (disabled) -----
    # The day_binned parquet (dlc_kinematics/licking_dynamics/day_binned/) is a
    # write-only ORPHAN — no code reads it. The binned figure renderers in
    # mean_sem_visual + tongue_angle_cohort do their OWN rel-day binning from
    # the trace (they only import the `_compute_rel_day_bin_label` helper, not
    # this parquet). The stale output dir was deleted and this producer stage
    # disabled in chore substrate-routing-and-secondary-spout-per-half-fix
    # (2026-05-31, Priya-approved) so it cannot silently recreate the orphan.
    # See src/stroke_orofacial/dlc_kinematics/_day_binned.py module docstring.
    rt_db, n_db = 0.0, 0

    animal_rt = time.perf_counter() - animal_t0
    log.info(f"=== animal={animal}: complete — runtime {animal_rt:.1f}s "
             f"({animal_rt/60:.1f} min); paths E1={n_ta} E2={n_mm} "
             f"E3={n_ms} E3b={n_is} E3c={n_to} E4={n_db} ===")
    return True, {
        "animal": animal,
        "runtime_seconds_total": f"{animal_rt:.3f}",
        "runtime_seconds_tongue_angle_cohort": f"{rt_ta:.3f}",
        "runtime_seconds_mismatch_cross_session": f"{rt_mm:.3f}",
        "runtime_seconds_mean_sem_cohort": f"{rt_ms:.3f}",
        "runtime_seconds_individual_sessions": f"{rt_is:.3f}",
        "runtime_seconds_trial_overlays": f"{rt_to:.3f}",
        "runtime_seconds_day_binned": f"{rt_db:.3f}",
        "n_tongue_angle_paths": str(n_ta),
        "n_mismatch_paths": str(n_mm),
        "n_mean_sem_paths": str(n_ms),
        "n_individual_sessions_paths": str(n_is),
        "n_trial_overlays_paths": str(n_to),
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
