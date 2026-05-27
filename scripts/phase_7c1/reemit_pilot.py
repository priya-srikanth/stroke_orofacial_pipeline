"""Phase 7c.1 Task 3 — 3-session pilot re-emit on PS46/2025-03-07 +
PS54/2025-05-03 + PS50/2025-03-25 per Q1.A.

Pilot output scope per kickoff Addendum #1: ALL per-session DLC
categories (A through D + D-supplements). Cross-session aggregates
(Category E) are excluded and belong to Phase 7c.2.

Categories executed per session (in dependency order):

  B. Kinematics interpolated traces (Phase 7a.2)
     - interpolated_traces/tongue/<animal>/<YYYYMMDD>.parquet
     - interpolated_traces/jaw/<animal>/<YYYYMMDD>.parquet

  A. Spatial heatmap NPZs (Phase 6) — sweep 3 bodyparts × 3 center_modes
     × 3 trial_groups × 2 windows = 54 NPZs per session.
     - spatial_tone_aligned/<bp>_<cm>/trials-<tg>_<win>/<animal>/heatmap_<date>.npz

  C. Per-trial features (Phase 7a.3)
     - dlc_kinematics/features/tongue/<animal>/<YYYYMMDD>.parquet
     - dlc_kinematics/licking_dynamics/traces/<animal>/<YYYYMMDD>.parquet
     - dlc_kinematics/endpoints/<animal>/<YYYYMMDD>.json
     - dlc_kinematics/jaw_pertrial/endpoints/<animal>/<YYYYMMDD>.json (D-supplement-2)

  D. Tongue angle within-session 9-PNG bundle (Phase 7a.4)
     - dlc_kinematics/tongue_angle/within_session/<animal>/<YYYYMMDD>/*.png

  D-supplement. Tongue-jaw mismatch per-session (Phase 7a.5)
     - dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<YYYYMMDD>.parquet
     - dlc_kinematics/tongue_jaw_mismatch/within_session/<animal>/<YYYYMMDD>/*.png

Manifest schema per Addendum #1: per-session row with per-category
runtime_seconds_* breakdowns + output_sha256s dict (parquet/JSON/NPZ
only; PNGs excluded since matplotlib rasterization can be slightly
non-deterministic). Manifest path: `.scratch_phase_7c1/pilot_manifest.csv`.

Order: PS46 → PS54 → PS50 (fastest predicted first; gives early signal).

Anomaly handling per kickoff:
  - Unexpected per-session failure → STOP-and-report immediately.
  - PS50 visibly-broken outputs → STOP-and-report (real signal, not bug).
  - 2+ session failures → STOP for re-scope.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.dlc_kinematics import (
    build_interpolated_trace_by_animal_date,
    build_tongue_pertrial_by_animal_date,
    build_jaw_pertrial_by_animal_date,
    render_tongue_qc_figures,
    classify_tongue_jaw_mismatch_by_animal_date,
    render_within_session_figures,
)
from stroke_orofacial.dlc_spatial.tone_aligned import (
    build_tone_aligned_analysis_by_animal_date,
    save_tone_aligned_npz,
)


SESSIONS = [
    ("PS46", dt.date(2025, 3, 7)),
    ("PS54", dt.date(2025, 5, 3)),
    ("PS50", dt.date(2025, 3, 25)),
]

PHASE6_BODYPARTS = ("tongue", "jaw", "nose")
PHASE6_CENTER_MODES = ("nose", "spout_midpoint", "eye_midpoint")
PHASE6_TRIAL_GROUPS = ("all", "L", "R")
PHASE6_WINDOWS_MS = ((-500.0, 5000.0), (-100.0, 1000.0))

MANIFEST_PATH = Path(".scratch_phase_7c1/pilot_manifest.csv")
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c1.pilot")


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
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


def _hash_parquet_json_npz_in(directory: Path) -> dict[str, str]:
    """Compute sha256s for every .parquet/.json/.npz file under `directory`.
    PNGs intentionally excluded (matplotlib rasterization can be slightly
    non-deterministic; not in sha256 verdict per Addendum #1)."""
    out = {}
    if not directory.exists():
        return out
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix in (".parquet", ".json", ".npz"):
            out[str(p)] = _sha256(p)
    return out


def _run_session(
    animal: str, date: dt.date, resolver: PathResolver,
    spatial_config, tone_config, output_root: Path,
) -> tuple[bool, dict]:
    log.info(f"=== {animal}/{date.isoformat()} ===")
    session_t0 = time.perf_counter()
    date_str = date.strftime("%Y%m%d")
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
        log.info(f"  [B] interpolation: {rt_B:.1f}s ({len(outputs_sha)} files)")
    except Exception as ex:
        anomalies.append(f"B-interpolation: {ex!r}")
        log.error(f"  [B] interpolation: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    # ----- Category A: spatial heatmaps (sweep) -----
    t0 = time.perf_counter()
    n_a_ok = n_a_skip = n_a_err = 0
    spatial_root_under = resolver.pipeline_outputs("dlc_analysis") / "spatial_tone_aligned"
    spatial_outputs_before = set(outputs_sha.keys())
    try:
        for bp in PHASE6_BODYPARTS:
            for cm in PHASE6_CENTER_MODES:
                for tg in PHASE6_TRIAL_GROUPS:
                    for w in PHASE6_WINDOWS_MS:
                        win_tag = f"{int(w[0])}to{int(w[1])}ms"
                        out_dir = spatial_root_under / f"{bp}_{cm}" / f"trials-{tg}_{win_tag}" / animal
                        npz_path = out_dir / f"heatmap_{date_str}.npz"
                        # Phase 7e.4: pilot is a one-off baseline-snapshot
                        # script (executed once for the Phase 7c.1
                        # 3-session pilot). Explicit use_v7_cleaned=False
                        # so re-running this pilot regenerates the
                        # historical legacy outputs byte-identically;
                        # cleaned_trace re-emissions go through the
                        # Phase 7c.2 cohort driver instead.
                        result = build_tone_aligned_analysis_by_animal_date(
                            animal=animal, date_str=date_str,
                            bodypart=bp, center_mode=cm,
                            trial_group=tg, window_ms=w,
                            resolver=resolver,
                            spatial_config=spatial_config,
                            tone_config=tone_config,
                            use_v7_cleaned=False,
                        )
                        if result is None or result["histogram"] is None:
                            n_a_skip += 1
                            continue
                        out_dir.mkdir(parents=True, exist_ok=True)
                        save_tone_aligned_npz(result, npz_path)
                        outputs_sha[str(npz_path)] = _sha256(npz_path)
                        n_a_ok += 1
        rt_A = time.perf_counter() - t0
        log.info(f"  [A] spatial sweep: {rt_A:.1f}s ({n_a_ok} OK, {n_a_skip} skip, {n_a_err} err)")
    except Exception as ex:
        anomalies.append(f"A-spatial: {ex!r}")
        log.error(f"  [A] spatial: ERR {ex!r}")
        return False, _build_failed_row(animal, date, session_t0, anomalies)

    # ----- Category C: per-trial features (tongue_pertrial + jaw_pertrial endpoints = D-supp-2) -----
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
        # qc_paths is dict[family_name → list[Path]]; PNGs not sha256'd per manifest spec.
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


def main() -> int:
    # Wipe prior manifest (this is the Addendum #1 revised schema, supersedes prior).
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()
        log.info(f"Wiped prior manifest at {MANIFEST_PATH}")

    resolver = PathResolver()
    defaults = load_defaults()
    spatial_config = defaults["dlc_spatial"]
    tone_config = defaults["dlc_spatial_tone_aligned"]
    output_root = resolver.pipeline_outputs("dlc_analysis") / "spatial_tone_aligned"

    log.info(f"output_root: {output_root}")
    log.info(f"manifest: {MANIFEST_PATH.resolve()}")

    n_session_fail = 0
    for animal, date in SESSIONS:
        ok, row = _run_session(animal, date, resolver, spatial_config, tone_config, output_root)
        _append_manifest(row)
        if not ok:
            n_session_fail += 1
            if n_session_fail >= 2:
                log.error("2+ session failures — STOP per kickoff anomaly trigger")
                return 1

    log.info(f"\nDONE. Sessions OK: {len(SESSIONS) - n_session_fail}/{len(SESSIONS)}")
    return 0 if n_session_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
