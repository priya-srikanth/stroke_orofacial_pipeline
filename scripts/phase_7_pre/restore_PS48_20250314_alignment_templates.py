"""Restore the 3 corrupted PS48 20250314 alignment templates.

Phase 7-pre-multi-half 2026-05-05 incident response — Option B
restore script. Five steps, cam2-scoped, post-run diff with
3-files-changed assertion.

DOCUMENTED WRITEGUARD EXCEPTION
================================

This script INTENTIONALLY writes to deny-listed legacy MICROSCOPE
paths under
``\\\\research...\\Priya\\DeepLabCut\\O2_analysis\\alignment_templates\\``
to restore three legacy NPZs that were corrupted by a buggy test
fixture (mtime 2026-05-05 19:46:37; sizes shrunk from 44/68/70 MB
to 4/1/2 KB). The corruption was caused by
``PathResolver(output_root=tmp_path)`` failing to redirect the
old ``alignment_template`` resolver — fixed in Commit 4 (resolver
split into ``_legacy_read`` / ``_new``).

The three-layer guard system added in Commits 1-5
(``_writeguard.py`` module + ``tests/conftest.py`` autouse fixture
+ ``paths.py`` resolver split) is designed to PREVENT
unintentional writes to legacy paths. This script is the
**documented exception** — a one-off CLI tool the user runs
manually with explicit approval, NOT invoked from any pipeline
path. Specifically:

  - Layer 1 (resolver split): bypassed because this script
    constructs target paths directly from on-disk inputs, not via
    the resolver. Intentional.
  - Layer 2 (writeguard module): bypassed because the script does
    NOT call ``assert_safe_write_path`` on the destination. The
    writeguard is opt-in at production write sites; this script
    explicitly opts out.
  - Layer 3 (conftest autouse fixture): irrelevant — the script
    runs as a CLI tool outside pytest. The fixture only fires
    during ``pytest`` invocation.

The script is single-session, cam2-only, idempotent (running
twice with --execute is harmless after the first restore
succeeds). Source inputs (per-half WS-processed NPZs on
MICROSCOPE + per-half camera CSVs in Rich's tree) are read-only.

Five steps
----------

  1. **Pre-run inventory walk.** Walk
     ``cam{1-4}/PS48/`` filtered to ``20250314*.npz`` + the
     ``20250314ab/`` subdir. Capture rel-path / size / mtime for
     every match. Write CSV to
     ``docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv``.
     Under ``--inventory-only`` (default), print summary and exit.

  2. **Regenerate per-half templates** (cam2 only). Calls
     :func:`make_alignment_templates_20251216.main` (legacy module
     loaded via importlib from the repo's read-only path) twice —
     once for half-a, once for half-b — using the per-half WS-
     processed NPZs and per-half camera CSVs as inputs. Writes
     ``cam2/PS48/20250314a.npz`` and ``cam2/PS48/20250314b.npz``
     at parent level (legacy notebook convention).

  3. **Merge per-half → parent-level merged.** Calls
     :func:`stroke_orofacial.spout_behavior.multi_half_merge.merge_alignment_templates`
     on the two per-half files. Writes ``cam2/PS48/20250314.npz``
     at parent level — overwriting the corrupted 3920-byte file.
     Faithful port of legacy cell 16; same provenance keys.

  4. **Move per-half files into the ``20250314ab/`` subdir.**
     Moves ``cam2/PS48/20250314a.npz`` and ``cam2/PS48/20250314b.npz``
     into ``cam2/PS48/20250314ab/`` — overwriting the corrupted
     1342 / 1604 byte files. Restores the on-disk Decision-3
     layout that Priya established post-merge cleanup 2026-01-11.

  5. **Post-run diff + 3-files-changed assertion.** Re-walk the
     same paths as step 1, compute diff, assert exactly three
     files changed and the three sizes match the Task 1a
     inventory:
       - cam2/PS48/20250314.npz                : 43,873,994 bytes
       - cam2/PS48/20250314ab/20250314a.npz    : 68,512,651 bytes
       - cam2/PS48/20250314ab/20250314b.npz    : 69,808,659 bytes

CLI
---

  python scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py
      # Default: --inventory-only. Steps 1 only. Writes inventory
      # CSV; no destructive action.

  python scripts/phase_7_pre/restore_PS48_20250314_alignment_templates.py --execute
      # Runs all 5 steps. Irreversible from step 2 onwards.
      # Use only after Priya's explicit greenlight.

Exit codes
----------

  0 — success (inventory-only completed, OR all 5 steps completed
      with the 3-file diff assertion passing).
  1 — assertion failure (post-run diff didn't match expected
      restored sizes, or wrong number of files changed).
  2 — preflight error (input file missing, legacy module import
      failed, etc.).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---- Constants (paths, expected sizes) ----

# Legacy module that does the per-half alignment computation. Loaded
# from MICROSCOPE on the fly so we don't need to vendor it.
LEGACY_MODULE_PATH = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Github"
    r"\facerhythm_stroke_biomarker_exp\analysis\alignment"
    r"\make_alignment_templates_20251216.py"
)

# Output root: legacy alignment_templates tree.
ALIGN_TEMPLATES_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\DeepLabCut"
    r"\O2_analysis\alignment_templates"
)
PS48_CAM2_DIR = ALIGN_TEMPLATES_ROOT / "cam2" / "PS48"

# Per-half WS-processed NPZs (legacy session_processing3 tree on MICROSCOPE).
WS_PROCESSED_DIR = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya"
    r"\facerhythm_stroke_biomarker_exp\analysis\session_processing3"
    r"\wavesurfer_signals_processed\PS48"
)

# Per-half camera CSVs (Rich's tree).
CAM_RAW_ROOT = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Rich\data\2pRAM"
    r"\facerhythm_stroke_biomarker_exp\camera"
)

# Pre-run inventory CSV (committed to repo as audit artefact).
INVENTORY_CSV = Path("docs/phase-7-pre/restore_PS48_20250314_pre_run_inventory.csv")

# Task 1a expected post-restore sizes — load-bearing assertion in step 5.
EXPECTED_RESTORED_SIZES: dict[str, int] = {
    "cam2/PS48/20250314.npz": 43_873_994,
    "cam2/PS48/20250314ab/20250314a.npz": 68_512_651,
    "cam2/PS48/20250314ab/20250314b.npz": 69_808_659,
}

# Per-half spec: half_id -> (ws_filename, cam_subdir, video_timestamp_for_csv_glob)
# The cam-side timestamp differs from the video by 1 second on half-b
# (T13_09_28 csv vs T13_09_29 avi — observed on PS48 20250314 half-b);
# so we use a HH_MM-prefix glob to catch both.
PER_HALF_INPUTS: list[dict[str, str]] = [
    {
        "half_id": "a",
        "ws_npz_name": "20250314a.npz",
        "cam_subdir": "20250314a",
        "csv_prefix_for_glob": "timestamp2_2025-03-14T12_31",
    },
    {
        "half_id": "b",
        "ws_npz_name": "20250314b.npz",
        "cam_subdir": "20250314b",
        "csv_prefix_for_glob": "timestamp2_2025-03-14T13_09",
    },
]

# Match the params dict in cell 2 of the legacy notebook.
PARAMS_MAKE_ALIGN: dict[str, Any] = {
    "csv_idx_sync": 2,
    "csv_idx_time": 0,
    "key_sync": "Sync_signal",
    "fps_cam": 250.0,
}


# ---- Inventory helpers ----


def _walk_inventory_targets() -> list[Path]:
    """Return the list of paths the inventory step should examine.

    Broad enough to catch unexpected side effects: includes all four
    cam{1-4}/PS48/ trees filtered to 20250314* names, plus the
    20250314ab/ subdirs in each cam. Single-(animal, date) scope —
    no risk of touching other sessions.
    """
    paths: list[Path] = []
    for cam_idx in (1, 2, 3, 4):
        cam_dir = ALIGN_TEMPLATES_ROOT / f"cam{cam_idx}" / "PS48"
        if cam_dir.exists():
            for entry in sorted(cam_dir.iterdir()):
                if entry.name.startswith("20250314"):
                    if entry.is_file():
                        paths.append(entry)
                    elif entry.is_dir():
                        # Walk the subdir (e.g. 20250314ab/)
                        for child in sorted(entry.iterdir()):
                            if child.is_file():
                                paths.append(child)
    return paths


def _stat_inventory(paths: list[Path]) -> list[dict[str, Any]]:
    """Capture size + mtime for each path. Missing files report
    size=None / mtime=None (so the diff can detect created/deleted)."""
    rows: list[dict[str, Any]] = []
    for p in paths:
        try:
            st = p.stat()
            rows.append({
                "path": str(p),
                "rel_path": str(p.relative_to(ALIGN_TEMPLATES_ROOT)).replace("\\", "/"),
                "exists": True,
                "size": st.st_size,
                "mtime_iso": datetime.datetime.fromtimestamp(
                    st.st_mtime, tz=datetime.timezone.utc,
                ).isoformat(),
            })
        except OSError as e:
            rows.append({
                "path": str(p),
                "rel_path": str(p.relative_to(ALIGN_TEMPLATES_ROOT)).replace("\\", "/"),
                "exists": False,
                "size": None,
                "mtime_iso": None,
                "stat_error": repr(e),
            })
    return rows


def _write_inventory_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out_path.write_text(
            "path,rel_path,exists,size,mtime_iso\n# (no matching paths)\n",
            encoding="utf-8",
        )
        return
    cols = ["path", "rel_path", "exists", "size", "mtime_iso"]
    if any("stat_error" in r for r in rows):
        cols.append("stat_error")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _print_inventory_summary(rows: list[dict[str, Any]]) -> None:
    print(f"Inventory walk: {len(rows)} matching files under "
          f"{ALIGN_TEMPLATES_ROOT}/cam[1-4]/PS48/20250314*")
    print()
    for row in rows:
        sz = f"{row['size']:>14,}" if row["size"] is not None else "      MISSING"
        print(f"  {row['rel_path']:50s}  size={sz}  mtime={row['mtime_iso']}")
    print()


# ---- Step 2: regenerate per-half templates ----


def _import_legacy_module() -> Any:
    if not LEGACY_MODULE_PATH.exists():
        raise FileNotFoundError(
            f"Legacy module not found at {LEGACY_MODULE_PATH}. "
            f"Cannot regenerate per-half templates."
        )
    spec = importlib.util.spec_from_file_location(
        "make_alignment_templates_20251216", LEGACY_MODULE_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolve_camera_csv(spec: dict[str, str]) -> Path:
    """Pick the timestamp2 CSV for one half via HH_MM-prefix glob.

    Off-by-1-second handling: half-b csv filename uses T13_09_28 while
    the .avi files use T13_09_29. We glob by the HH_MM portion so both
    halves work uniformly.
    """
    cam_dir = CAM_RAW_ROOT / spec["cam_subdir"] / "PS48"
    matches = sorted(cam_dir.glob(f"{spec['csv_prefix_for_glob']}*.csv"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one camera CSV for half {spec['half_id']!r} "
            f"under {cam_dir} matching {spec['csv_prefix_for_glob']}*.csv, "
            f"got {len(matches)}: {[m.name for m in matches]}"
        )
    return matches[0]


def _regenerate_per_half_templates() -> list[Path]:
    legacy = _import_legacy_module()
    out_paths: list[Path] = []
    for spec in PER_HALF_INPUTS:
        ws_npz = WS_PROCESSED_DIR / spec["ws_npz_name"]
        cam_csv = _resolve_camera_csv(spec)
        out_path = PS48_CAM2_DIR / f"20250314{spec['half_id']}.npz"

        # Build temp JSON files for path_data + path_params
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump({"path_camCSV": str(cam_csv), "path_ws": str(ws_npz)}, f)
            path_data_json = f.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump(PARAMS_MAKE_ALIGN, f)
            path_params_json = f.name

        print(f"  step 2 half {spec['half_id']!r}:")
        print(f"    ws_npz: {ws_npz}")
        print(f"    cam_csv: {cam_csv}")
        print(f"    out:     {out_path}")
        legacy.main(
            path_data=path_data_json,
            path_params=path_params_json,
            path_save=str(out_path),
        )
        # Clean up temp files
        Path(path_data_json).unlink(missing_ok=True)
        Path(path_params_json).unlink(missing_ok=True)
        out_paths.append(out_path)

    return out_paths


# ---- Step 3: merge per-half → merged (parent level) ----


def _merge_per_half_into_parent(per_half_paths: list[Path]) -> Path:
    from stroke_orofacial.spout_behavior.multi_half_merge import (
        merge_alignment_templates,
    )
    merged_path = PS48_CAM2_DIR / "20250314.npz"
    print(f"  step 3 merge -> {merged_path}")
    merge_alignment_templates(per_half_paths, merged_path)
    return merged_path


# ---- Step 4: move per-halves into 20250314ab/ ----


def _move_per_halves_into_subdir(per_half_paths: list[Path]) -> list[Path]:
    subdir = PS48_CAM2_DIR / "20250314ab"
    subdir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for src in per_half_paths:
        dst = subdir / src.name
        print(f"  step 4 move {src.name} -> {dst}")
        # shutil.move handles the cross-direntry atomic-ish replacement.
        # If dst already exists (from the corruption), it's overwritten.
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        moved.append(dst)
    return moved


# ---- Step 5: post-run diff + assertion ----


def _diff_inventories(
    pre: list[dict[str, Any]],
    post: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return per-rel_path diff records. Status one of:
    'unchanged', 'created', 'modified', 'deleted'.
    """
    pre_by_rel = {r["rel_path"]: r for r in pre}
    post_by_rel = {r["rel_path"]: r for r in post}
    all_rels = sorted(set(pre_by_rel) | set(post_by_rel))
    out: list[dict[str, Any]] = []
    for rel in all_rels:
        p = pre_by_rel.get(rel)
        q = post_by_rel.get(rel)
        if p is None:
            status = "created"
        elif q is None:
            status = "deleted"
        elif (p.get("size") != q.get("size")
              or p.get("mtime_iso") != q.get("mtime_iso")):
            status = "modified"
        else:
            status = "unchanged"
        out.append({
            "rel_path": rel,
            "status": status,
            "size_pre": (p or {}).get("size"),
            "size_post": (q or {}).get("size"),
            "mtime_pre": (p or {}).get("mtime_iso"),
            "mtime_post": (q or {}).get("mtime_iso"),
        })
    return out


def _assert_three_files_restored(diff: list[dict[str, Any]]) -> None:
    changed = [d for d in diff if d["status"] != "unchanged"]
    print(f"  step 5 diff: {len(diff)} entries, {len(changed)} changed")
    for d in changed:
        sz_pre = d["size_pre"]
        sz_post = d["size_post"]
        print(
            f"    {d['status']:9s} {d['rel_path']:48s}  "
            f"size {sz_pre} -> {sz_post}"
        )

    # Strict assertion: exactly the 3 expected paths changed AND each is
    # restored to the Task 1a inventory size.
    if len(changed) != 3:
        raise AssertionError(
            f"Expected exactly 3 file changes, got {len(changed)}. "
            f"Changed: {[d['rel_path'] for d in changed]}"
        )
    changed_by_rel = {d["rel_path"]: d for d in changed}
    for expected_rel, expected_size in EXPECTED_RESTORED_SIZES.items():
        if expected_rel not in changed_by_rel:
            raise AssertionError(
                f"Expected change at {expected_rel} not present in diff. "
                f"Changes were: {sorted(changed_by_rel.keys())}"
            )
        actual_size = changed_by_rel[expected_rel]["size_post"]
        if actual_size != expected_size:
            raise AssertionError(
                f"Post-restore size mismatch at {expected_rel}: "
                f"expected {expected_size:,} bytes (Task 1a inventory), "
                f"got {actual_size:,} bytes."
            )
    print(
        "  step 5 PASS — exactly 3 files changed, all sizes match "
        "Task 1a inventory."
    )


# ---- Main ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Restore the 3 corrupted PS48 20250314 alignment templates "
            "(cam2 only) by re-running the legacy alignment computation "
            "and re-merging."
        ),
    )
    parser.add_argument(
        "--execute", action="store_true",
        help=(
            "Run all 5 steps (irreversible from step 2 onwards). "
            "Without this flag (default): inventory-only mode — runs "
            "step 1 only and exits."
        ),
    )
    parser.add_argument(
        "--inventory-csv", type=Path, default=INVENTORY_CSV,
        help=f"Path for the pre-run inventory CSV (default: {INVENTORY_CSV})",
    )
    args = parser.parse_args(argv)

    print("=" * 70)
    print("PS48 20250314 alignment-template restore")
    print(f"  mode: {'EXECUTE (irreversible)' if args.execute else 'inventory-only'}")
    print("=" * 70)
    print()

    # Preflight
    if not ALIGN_TEMPLATES_ROOT.exists():
        print(f"ERROR: alignment_templates root unreachable: {ALIGN_TEMPLATES_ROOT}")
        return 2
    if args.execute and not LEGACY_MODULE_PATH.exists():
        print(f"ERROR: legacy module unreachable: {LEGACY_MODULE_PATH}")
        return 2

    # ---- Step 1: pre-run inventory ----
    print("Step 1 — pre-run inventory walk")
    pre_paths = _walk_inventory_targets()
    pre_rows = _stat_inventory(pre_paths)
    _print_inventory_summary(pre_rows)
    _write_inventory_csv(pre_rows, args.inventory_csv)
    print(f"  wrote inventory CSV: {args.inventory_csv}")
    print()

    if not args.execute:
        print("Inventory-only mode — exiting (no destructive actions taken).")
        return 0

    # ---- Step 2: regenerate per-half templates ----
    print("Step 2 — regenerate per-half templates (cam2 only)")
    per_half_paths = _regenerate_per_half_templates()
    print()

    # ---- Step 3: merge per-half → parent-level merged ----
    print("Step 3 — merge per-half templates into parent-level merged file")
    _merge_per_half_into_parent(per_half_paths)
    print()

    # ---- Step 4: move per-halves into 20250314ab/ ----
    print("Step 4 — move per-half templates into 20250314ab/ subdir")
    _move_per_halves_into_subdir(per_half_paths)
    print()

    # ---- Step 5: post-run diff + assertion ----
    print("Step 5 — post-run diff + 3-files-changed assertion")
    post_paths = _walk_inventory_targets()
    post_rows = _stat_inventory(post_paths)
    diff = _diff_inventories(pre_rows, post_rows)
    try:
        _assert_three_files_restored(diff)
    except AssertionError as e:
        print(f"ASSERTION FAILED: {e}")
        return 1
    print()
    print("RESTORE COMPLETE — all 5 steps succeeded; assertion passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
