"""Phase 7-pre-alignment-templates Task 2 — cohort-wide alignment template emit.

Iterates the Task 1 cohort manifest (403 rows) and emits an alignment
template per session into ``pipeline_outputs/dlc_analysis/alignment_templates/cam2/``.

Dispatch per pattern column:
  - ``single_half``               → load_or_compute_alignment (force_recompute=True)
                                    writes via resolver.alignment_template_new
  - ``secondary_spout_b_half``    → same helper, session_suffix='b' on build_manifest;
                                    write lands at <root>/<animal>/<date>b.npz
  - ``multi_half_A``              → compute_and_merge_alignment_multi_half;
                                    writes per-half NPZs under <date><halves_concat_label>/
                                    + merged NPZ at <root>/<animal>/<date>.npz

SKIP_NO_INPUT semantics (Addendum #2 L4): rows where
``manifest.wavesurfer_file is None`` log SKIP_NO_INPUT with explanatory
``error_msg``, no template is written, and the cohort run continues.
Expected ~5 SKIP cases on the 403-row cohort; Task 7 acceptance criterion
is SKIP_NO_INPUT count ≤ 6.

Resumability: re-running this script with the same emit_manifest.csv
present will skip rows already tagged OK (idempotent). Re-running after
deleting the manifest re-emits every session (force_recompute=True on
the helpers).

Per-session manifest schema (.scratch_phase_7_pre_aligntmpl/emit_manifest.csv):
  animal, date, pattern, status, error_msg, output_path, output_sha256, wall_time_s

`status` is one of: OK, SKIP_NO_INPUT, FAIL.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRATCH = REPO_ROOT / ".scratch_phase_7_pre_aligntmpl"
COHORT_CSV = SCRATCH / "cohort_manifest.csv"
EMIT_CSV = SCRATCH / "emit_manifest.csv"

MANIFEST_FIELDS = [
    "animal", "date", "pattern",
    "status", "error_msg",
    "output_path", "output_sha256", "wall_time_s",
]


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_existing_manifest() -> dict[tuple[str, str, str], dict]:
    """Load (animal, date, pattern) -> row dict from existing emit_manifest.csv."""
    if not EMIT_CSV.exists():
        return {}
    out: dict[tuple[str, str, str], dict] = {}
    with open(EMIT_CSV, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["animal"], row["date"], row["pattern"])
            out[key] = row
    return out


def append_manifest_row(row: dict, *, header_written: bool) -> None:
    mode = "a" if header_written else "w"
    with open(EMIT_CSV, mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if not header_written:
            w.writeheader()
        w.writerow(row)


def emit_session(
    animal: str,
    date: datetime.date,
    pattern: str,
) -> dict:
    """Emit one session's alignment template. Returns the row dict."""
    import numpy as np

    from stroke_orofacial.alignment.frame_sync import make_alignment_template
    from stroke_orofacial.alignment.templates import (
        load_camera_csv,
        pick_camera_csv,
    )
    from stroke_orofacial.alignment.timebase import (
        compute_and_merge_alignment_multi_half,
    )
    from stroke_orofacial.animals import get_animal
    from stroke_orofacial.config_loader import load_defaults
    from stroke_orofacial.manifest import build_manifest
    from stroke_orofacial.paths import PathResolver
    from stroke_orofacial.spout_behavior.wavesurfer_io import (
        load_wavesurfer_signals,
    )

    row: dict = {
        "animal": animal,
        "date": date.isoformat(),
        "pattern": pattern,
        "status": "UNKNOWN",
        "error_msg": "",
        "output_path": "",
        "output_sha256": "",
        "wall_time_s": "",
    }
    t0 = time.time()
    try:
        resolver = PathResolver()
        animal_info = get_animal(animal)
        params = load_defaults()
        alignment_params = params["alignment"]

        session_suffix = "b" if pattern == "secondary_spout_b_half" else None

        manifest = build_manifest(
            animal, date, resolver, animal_info,
            analysis_context="alignment",
            session_suffix=session_suffix,
        )

        # SKIP_NO_INPUT per Addendum #2 L4: rows where the manifest's WS
        # file resolution returned None. Two main sources:
        #   1. secondary_spout_b_half rows with no on-disk b-half WS data
        #      (~5 expected per L4 from PS51/PS54/PS55 × 2025-04-24/25).
        #   2. single_half rows where the YAML session range extends past
        #      the last actual recording date for an animal (e.g., PS46's
        #      range goes to 2025-04-06 but recordings stopped 2025-03-27).
        # Both are legitimate "no input data on disk" cases — skip + log.
        if manifest.halves is None and manifest.wavesurfer_file is None:
            row["status"] = "SKIP_NO_INPUT"
            row["error_msg"] = (
                "manifest.wavesurfer_file is None — no on-disk WS "
                "acquisition for this (animal, date, suffix)"
            )
            row["wall_time_s"] = f"{time.time() - t0:.2f}"
            return row

        if pattern == "multi_half_A":
            if manifest.halves is None:
                raise RuntimeError(
                    f"pattern=multi_half_A but manifest.halves is None for "
                    f"{animal}/{date.isoformat()}; manifest construction "
                    f"didn't pick up the multi_half_sessions registry entry"
                )
            # compute_and_merge_alignment_multi_half writes per-half NPZs
            # via alignment_template_per_half_new + merged NPZ via
            # alignment_template_new (Phase 7-pre-multi-half + 2026-05-05
            # incident-response). Returns the merged path.
            output_path = compute_and_merge_alignment_multi_half(
                manifest, resolver, alignment_params,
                force_recompute=True,
            )
        else:
            # single_half OR secondary_spout_b_half. load_or_compute_alignment
            # does NOT write single-half templates to disk (it returns an
            # AlignmentResult only). Drive the compute + save explicitly to
            # land the template at resolver.alignment_template_new(...).
            ws_signals = load_wavesurfer_signals(manifest.wavesurfer_file)

            # Camera CSV: prefer the dir already discovered by build_manifest
            # via manifest.video_files; fall back to the suffix-aware resolver.
            if manifest.video_files:
                cam_dir = manifest.video_files[0].parent
            else:
                date_str = date.strftime("%Y%m%d")
                cam_subdir_override = (
                    f"{date_str}b" if session_suffix == "b" else None
                )
                cam_dir = resolver.camera_dir(
                    date, animal, subdir_override=cam_subdir_override,
                )
            csv_path = pick_camera_csv(cam_dir, cam_idx=2)
            cam_csv = load_camera_csv(csv_path)

            # Build the 22-key template dict + save uncompressed-but-via-
            # savez_compressed for parity with legacy emit (legacy used
            # savez_compressed too — file format equivalence is the goal).
            tmpl = make_alignment_template(
                ws_signals, cam_csv, alignment_params,
            )
            output_path = resolver.alignment_template_new(
                animal, date, cam="cam2", session_suffix=session_suffix,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(str(output_path), **tmpl)

        output_path = Path(output_path)
        if not output_path.exists():
            raise FileNotFoundError(
                f"Emit reported success but {output_path} doesn't exist"
            )
        row["output_path"] = str(output_path)
        row["output_sha256"] = sha256_of_file(output_path)
        row["status"] = "OK"
    except Exception as e:
        row["status"] = "FAIL"
        row["error_msg"] = f"{type(e).__name__}: {e}"
        # Include trimmed traceback in the error_msg for triage
        tb = traceback.format_exc().strip().splitlines()
        # Last 3 lines usually have the meaningful traceback tail
        row["error_msg"] += " | " + " // ".join(tb[-3:])
    finally:
        row["wall_time_s"] = f"{time.time() - t0:.2f}"
    return row


def main() -> int:
    if not COHORT_CSV.exists():
        print(f"ERROR: {COHORT_CSV} not found. Run Task 1 enumeration first.")
        return 2

    with open(COHORT_CSV, newline="") as f:
        cohort_rows = list(csv.DictReader(f))

    existing = load_existing_manifest()
    header_written = EMIT_CSV.exists()

    total = len(cohort_rows)
    ok_count = 0
    skip_count = 0
    fail_count = 0
    resume_skipped = 0

    print(f"Cohort manifest: {total} rows")
    print(f"Existing emit_manifest: {len(existing)} rows")
    print(f"---")

    for i, src in enumerate(cohort_rows, 1):
        animal = src["animal"]
        date_iso = src["date"]
        pattern = src["pattern"]
        key = (animal, date_iso, pattern)

        prev = existing.get(key)
        if prev is not None and prev.get("status") == "OK":
            resume_skipped += 1
            if i % 50 == 0 or i == total:
                print(
                    f"[{i:3d}/{total}] (resumed OK) {animal} {date_iso} "
                    f"{pattern}",
                )
            continue

        date = datetime.date.fromisoformat(date_iso)
        print(
            f"[{i:3d}/{total}] {animal} {date_iso} {pattern} ...",
            end="", flush=True,
        )
        row = emit_session(animal, date, pattern)
        append_manifest_row(row, header_written=header_written)
        header_written = True
        print(
            f" {row['status']} ({row['wall_time_s']}s)",
            flush=True,
        )
        if row["status"] == "OK":
            ok_count += 1
        elif row["status"] == "SKIP_NO_INPUT":
            skip_count += 1
        else:
            fail_count += 1
            print(f"    error_msg: {row['error_msg']}")

    print("---")
    print(f"Done. New OK: {ok_count}, SKIP_NO_INPUT: {skip_count}, "
          f"FAIL: {fail_count}, resumed-OK: {resume_skipped}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
