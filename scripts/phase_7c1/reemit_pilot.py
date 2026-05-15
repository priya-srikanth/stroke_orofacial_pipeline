"""Phase 7c.1 Task 3 — 3-session pilot re-emit on PS46/2025-03-07 +
PS54/2025-05-03 + PS50/2025-03-25 per Q1.A.

Runs DLC kinematics + spatial pipeline under POST-rename source state.
Writes to:
  - NEW spatial outputs: `pipeline_outputs/dlc_analysis/spatial_tone_aligned/...`
    (post-C5 output_root rename; legacy `spatial_reward_aligned/` untouched
    per Q3.A).
  - Existing kinematics paths: `pipeline_outputs/dlc_analysis/interpolated_traces/{bp}/{animal}/{date}.parquet`
    (path unchanged; internal schema renamed `reward_centers_cam` →
    `tone_centers_cam` per Cat D1). LEGACY parquets at these paths get
    OVERWRITTEN for the 3 pilot sessions only. Pre-Task-3 sanity check
    confirmed legacy parquets exist; snapshot their sha256 in pre_run.txt
    if precise byte-equality verification is needed at Task 4. The
    post-rename parquet column-set differs (`tone_centers_cam` instead
    of `reward_centers_cam`), so byte-level sha256 will NOT match
    legacy — Task 4 verification compares structurally (per-column
    array equality modulo renamed column name).

Per-session manifest written incrementally to
`.scratch_phase_7c1/pilot_manifest.csv` after each session completes
(don't batch). If interrupted, the partial manifest is the recovery
state for a fresh CC session.

Order: PS46 → PS54 → PS50 (fastest predicted first; gives early signal).

Anomaly handling:
  - Unexpected per-session failure → STOP-and-report immediately;
    do not continue.
  - PS50 specifically: if pipeline fails or visibly broken outputs
    (zero trials, NaN-poisoning, off-by-orders axes), STOP-and-report
    — that's a real signal, not a bug.
  - 2+ of 3 sessions fail → STOP for re-scope.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import logging
import sys
import time
from pathlib import Path

import numpy as np

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.dlc_kinematics import build_interpolated_trace_by_animal_date
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_analysis_by_animal_date,
    save_tone_aligned_npz,
)


SESSIONS = [
    ("PS46", dt.date(2025, 3, 7)),
    ("PS54", dt.date(2025, 5, 3)),
    ("PS50", dt.date(2025, 3, 25)),
]

# Pilot Phase 6 sweep: 3 bodyparts × 3 center modes × 3 trial groups × 2 windows = 54 per session.
PHASE6_BODYPARTS = ("tongue", "jaw", "nose")
PHASE6_CENTER_MODES = ("nose", "spout_midpoint", "eye_midpoint")
PHASE6_TRIAL_GROUPS = ("all", "L", "R")
PHASE6_WINDOWS_MS = ((-500.0, 5000.0), (-100.0, 1000.0))

MANIFEST_PATH = Path(".scratch_phase_7c1/pilot_manifest.csv")
MANIFEST_HEADER = [
    "animal", "date", "step", "output_path", "runtime_seconds",
    "sha256", "status", "anomaly_notes",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c1.pilot")


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_manifest(row: dict) -> None:
    is_new = not MANIFEST_PATH.exists()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_HEADER)
        if is_new:
            w.writeheader()
        w.writerow(row)


def _run_phase7a2(animal: str, date: dt.date, resolver: PathResolver) -> list[dict]:
    """Phase 7a.2 interpolated_traces (tongue + jaw)."""
    rows: list[dict] = []
    for bp in ("tongue", "jaw"):
        t0 = time.perf_counter()
        try:
            out_path = build_interpolated_trace_by_animal_date(
                animal=animal, date=date, bodypart=bp,
                resolver=resolver, overwrite="force",
            )
            rt = time.perf_counter() - t0
            sha = _sha256(out_path)
            rows.append({
                "animal": animal, "date": date.isoformat(),
                "step": f"phase7a2/{bp}",
                "output_path": str(out_path),
                "runtime_seconds": f"{rt:.3f}",
                "sha256": sha, "status": "OK", "anomaly_notes": "",
            })
            log.info(f"  phase7a2/{bp}: {rt:.1f}s -> {out_path.name}")
        except Exception as ex:
            rt = time.perf_counter() - t0
            rows.append({
                "animal": animal, "date": date.isoformat(),
                "step": f"phase7a2/{bp}",
                "output_path": "", "runtime_seconds": f"{rt:.3f}",
                "sha256": "", "status": "ERR",
                "anomaly_notes": repr(ex),
            })
            log.error(f"  phase7a2/{bp}: ERR -- {ex!r}")
    return rows


def _run_phase6_one(
    animal: str, date: dt.date, resolver: PathResolver,
    spatial_config, tone_config, output_root: Path,
    bodypart: str, center_mode: str, trial_group: str,
    window_ms: tuple[float, float],
) -> dict:
    """Phase 6 spatial heatmap for one (bp, center, trial_group, window)."""
    date_str = date.strftime("%Y%m%d")
    win_tag = f"{int(window_ms[0])}to{int(window_ms[1])}ms"
    out_dir = (
        output_root / f"{bodypart}_{center_mode}"
        / f"trials-{trial_group}_{win_tag}" / animal
    )
    npz_path = out_dir / f"heatmap_{date_str}.npz"
    step_label = f"phase6/{bodypart}/{center_mode}/{trial_group}/{win_tag}"

    t0 = time.perf_counter()
    try:
        result = build_tone_aligned_analysis_by_animal_date(
            animal=animal, date_str=date_str,
            bodypart=bodypart, center_mode=center_mode,
            trial_group=trial_group, window_ms=window_ms,
            resolver=resolver,
            spatial_config=spatial_config,
            tone_config=tone_config,
        )
        if result is None:
            rt = time.perf_counter() - t0
            return {
                "animal": animal, "date": date.isoformat(),
                "step": step_label, "output_path": "",
                "runtime_seconds": f"{rt:.3f}",
                "sha256": "", "status": "SKIP_NO_TONES",
                "anomaly_notes": "zero events for this trial_group",
            }
        if result["histogram"] is None:
            rt = time.perf_counter() - t0
            return {
                "animal": animal, "date": date.isoformat(),
                "step": step_label, "output_path": "",
                "runtime_seconds": f"{rt:.3f}",
                "sha256": "", "status": "SKIP_NO_FRAMES",
                "anomaly_notes": "no DLC frames passed likelihood threshold",
            }
        out_dir.mkdir(parents=True, exist_ok=True)
        save_tone_aligned_npz(result, npz_path)
        rt = time.perf_counter() - t0
        sha = _sha256(npz_path)
        return {
            "animal": animal, "date": date.isoformat(),
            "step": step_label, "output_path": str(npz_path),
            "runtime_seconds": f"{rt:.3f}",
            "sha256": sha, "status": "OK",
            "anomaly_notes": f"n_tones={result['n_tones']}",
        }
    except Exception as ex:
        rt = time.perf_counter() - t0
        return {
            "animal": animal, "date": date.isoformat(),
            "step": step_label, "output_path": "",
            "runtime_seconds": f"{rt:.3f}",
            "sha256": "", "status": "ERR", "anomaly_notes": repr(ex),
        }


def _run_session(animal: str, date: dt.date, resolver: PathResolver,
                 spatial_config, tone_config, output_root: Path) -> bool:
    """Returns True on success, False on failure."""
    log.info(f"=== {animal}/{date.isoformat()} ===")
    session_t0 = time.perf_counter()

    # Phase 7a.2 interpolated_traces (tongue + jaw)
    phase7a2_rows = _run_phase7a2(animal, date, resolver)
    for row in phase7a2_rows:
        _append_manifest(row)
    if any(r["status"] == "ERR" for r in phase7a2_rows):
        log.error(f"{animal}/{date.isoformat()}: Phase 7a.2 failures — STOP-and-report")
        return False

    # Phase 6 spatial heatmaps (sweep 3 × 3 × 3 × 2 = 54)
    log.info(f"  phase6 sweep: {len(PHASE6_BODYPARTS)*len(PHASE6_CENTER_MODES)*len(PHASE6_TRIAL_GROUPS)*len(PHASE6_WINDOWS_MS)} combos")
    n_ok = n_skip = n_err = 0
    for bp in PHASE6_BODYPARTS:
        for cm in PHASE6_CENTER_MODES:
            for tg in PHASE6_TRIAL_GROUPS:
                for w in PHASE6_WINDOWS_MS:
                    row = _run_phase6_one(
                        animal, date, resolver, spatial_config,
                        tone_config, output_root, bp, cm, tg, w,
                    )
                    _append_manifest(row)
                    if row["status"] == "OK":
                        n_ok += 1
                    elif row["status"].startswith("SKIP"):
                        n_skip += 1
                    else:
                        n_err += 1

    session_rt = time.perf_counter() - session_t0
    log.info(f"  phase6 totals: ok={n_ok} skip={n_skip} err={n_err}")
    log.info(f"  SESSION TOTAL: {session_rt:.1f}s ({session_rt/60:.1f} min)")
    _append_manifest({
        "animal": animal, "date": date.isoformat(),
        "step": "SESSION_TOTAL", "output_path": "",
        "runtime_seconds": f"{session_rt:.3f}",
        "sha256": "", "status": "OK" if n_err == 0 else "PARTIAL_ERR",
        "anomaly_notes": f"phase7a2 outputs:{len(phase7a2_rows)} phase6 ok/skip/err:{n_ok}/{n_skip}/{n_err}",
    })
    return n_err == 0


def main() -> int:
    resolver = PathResolver()  # Q4.A: bare resolver; writes to MICROSCOPE production.
    defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    output_root = resolver.pipeline_outputs("dlc_analysis") / "spatial_tone_aligned"

    log.info(f"output_root: {output_root}")
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")

    n_session_fail = 0
    for animal, date in SESSIONS:
        ok = _run_session(animal, date, resolver, spatial_config, tone_config, output_root)
        if not ok:
            n_session_fail += 1
            if n_session_fail >= 2:
                log.error("2+ session failures — STOP per kickoff anomaly trigger")
                return 1

    log.info(f"\nDONE. Sessions OK: {len(SESSIONS) - n_session_fail}/{len(SESSIONS)}")
    return 0 if n_session_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
