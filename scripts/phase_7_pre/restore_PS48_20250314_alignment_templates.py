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

  5. **Post-run diff + layered validation.** Re-walk the same paths
     as step 1, compute diff, and run the layered post-run check.

     Tier A (size, per file):
       |delta| <= 0.1%  -> PASS  (likely deterministic re-run)
       |delta| <= 5%    -> WARN  (env drift since 2026-01-11; continue)
       |delta|  > 5%    -> FAIL  (exit 1)

       Strict byte-equality vs Task 1a (43,873,994 / 68,512,651 /
       69,808,659) was relaxed 2026-05-09 after the Phase 7a.0
       baseline-seed probe observed scipy 1.15.1 -> 1.17.1 drift in
       Y0 retune (PS49/PS50 tongue): exact byte-equal NPZ output
       across versions is not guaranteed even from identical inputs,
       so the strict assertion would spuriously fail on benign
       library drift since the 2026-01-11 originals.

     Tier B (structural, ALL must pass or step 5 fails):
       - Each per-half NPZ loads via np.load.
       - Each per-half NPZ contains the 5 REQ_KEYS (cell-16
         `Fs_ws_input` + 4 `sig_*` arrays).
       - Merged NPZ contains the 5 REQ_KEYS + 4 provenance keys
         (`merged_from_A`, `merged_from_B`, `ws_offset_samples`,
         `cam_offset_frames`) per cell-16 lines 168-178.
       - Length consistency: merged sig_wsIdx__idx_cam length ==
         n_cam_A + n_cam_B (and analogous for ws-axis arrays).
       - Fs_ws_input matches across both per-half NPZs and the
         merged NPZ.

     Tier C (diff shape):
       - Exactly the 3 expected rel_paths show 'modified' status;
         cam{1,3,4} cohort all 'unchanged'.

     Step 5 returns rc=0 on PASS or WARN (with WARN printed for
     audit trail), rc=1 on any FAIL.

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

import numpy as np

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


# Size-tolerance tiers for the layered post-run check (relaxed from
# strict byte-equality after Cowork's 2026-05-09 review). Phase 7a.0
# baseline-seed probe observed scipy 1.15.1 -> 1.17.1 drift in Y0 retune
# (PS49/PS50 tongue) — exact byte-equal NPZ output across versions is
# not guaranteed even from identical inputs. Strict equality would
# spuriously fail the restore on benign env drift since 2026-01-11.
_SIZE_TOLERANCE_PASS_FRAC = 0.001    # ±0.1% -> PASS (likely deterministic)
_SIZE_TOLERANCE_WARN_FRAC = 0.05     # ±5%   -> WARN (continue); above -> FAIL

# Required keys per the cell-16 vendor (REQ_KEYS list at line 41 of
# docs/legacy_snippets/multi_half_merge/cell_16_merge_alignment_templates.py).
_REQ_KEYS_PER_HALF = (
    "Fs_ws_input",
    "sig_wsIdx__idx_cam",
    "sig_camIdx__idx_ws",
    "sig_camTimes__idx_cam",
    "sig_wsTimes__idx_ws",
)
# Provenance keys cell 16 bakes into the merged NPZ (verified by
# multi_half_merge.merge_alignment_templates emitting these for N==2;
# byte-identical with legacy schema).
_REQ_KEYS_MERGED_PROVENANCE = (
    "merged_from_A",
    "merged_from_B",
    "ws_offset_samples",
    "cam_offset_frames",
)


def _classify_size_delta(actual: int, expected: int) -> tuple[str, float]:
    """Return ('pass'|'warn'|'fail', relative_delta).

    Tiers:
      |delta| <= 0.1%   -> 'pass'  (likely deterministic re-run)
      |delta| <= 5%     -> 'warn'  (env drift; continue)
      |delta|  > 5%     -> 'fail'  (suspicious; exit 1)
    """
    if expected <= 0:
        return ("fail", float("inf"))
    delta = abs(actual - expected) / expected
    if delta <= _SIZE_TOLERANCE_PASS_FRAC:
        return ("pass", delta)
    if delta <= _SIZE_TOLERANCE_WARN_FRAC:
        return ("warn", delta)
    return ("fail", delta)


def _validate_per_half_npz(path: Path, half_id: str) -> list[str]:
    """Return a list of validation errors for a per-half template.

    Empty list = passes all structural checks (NPZ loads + has all
    REQ_KEYS). Non-empty = each entry is a human-readable error.
    """
    errors: list[str] = []
    try:
        with np.load(path, allow_pickle=False) as npz:
            files = set(npz.files)
            for k in _REQ_KEYS_PER_HALF:
                if k not in files:
                    errors.append(
                        f"per-half {half_id}: missing required key {k!r} "
                        f"in {path.name}"
                    )
    except Exception as e:
        errors.append(
            f"per-half {half_id}: failed to load {path}: {e!r}"
        )
    return errors


def _validate_merged_npz(merged_path: Path) -> list[str]:
    """Return a list of validation errors for the merged template.

    Checks REQ_KEYS plus the cell-16 provenance keys.
    """
    errors: list[str] = []
    try:
        with np.load(merged_path, allow_pickle=False) as npz:
            files = set(npz.files)
            for k in _REQ_KEYS_PER_HALF:
                if k not in files:
                    errors.append(
                        f"merged: missing required key {k!r} in {merged_path.name}"
                    )
            for k in _REQ_KEYS_MERGED_PROVENANCE:
                if k not in files:
                    errors.append(
                        f"merged: missing provenance key {k!r} in "
                        f"{merged_path.name}"
                    )
    except Exception as e:
        errors.append(f"merged: failed to load {merged_path}: {e!r}")
    return errors


def _validate_length_consistency(
    merged_path: Path, half_a_path: Path, half_b_path: Path,
) -> list[str]:
    """Per cell 16 lines 145-153: merged sig_wsIdx__idx_cam length must
    equal n_cam_A + n_cam_B; same axis for camIdx_ws / wsTimes /
    camTimes pairs.

    Also verifies Fs_ws_input matches across the two halves (cell 16
    lines 64-68 — mismatch raises ValueError in the merge function).
    """
    errors: list[str] = []
    try:
        with np.load(half_a_path, allow_pickle=False) as a, \
             np.load(half_b_path, allow_pickle=False) as b, \
             np.load(merged_path, allow_pickle=False) as m:
            # Half-A / half-B base sizes (cam-axis = wsIdx_cam length;
            # ws-axis = camIdx_ws length).
            n_cam_a = int(len(a["sig_wsIdx__idx_cam"]))
            n_cam_b = int(len(b["sig_wsIdx__idx_cam"]))
            n_ws_a = int(len(a["sig_camIdx__idx_ws"]))
            n_ws_b = int(len(b["sig_camIdx__idx_ws"]))

            # Merged cam-axis arrays: should have length n_cam_a + n_cam_b
            for key in ("sig_wsIdx__idx_cam", "sig_camTimes__idx_cam"):
                got = int(len(m[key]))
                want = n_cam_a + n_cam_b
                if got != want:
                    errors.append(
                        f"length consistency: merged {key!r} = {got:,} "
                        f"!= n_cam_A + n_cam_B = {n_cam_a:,} + {n_cam_b:,}"
                    )
            # Merged ws-axis arrays: should have length n_ws_a + n_ws_b
            for key in ("sig_camIdx__idx_ws", "sig_wsTimes__idx_ws"):
                got = int(len(m[key]))
                want = n_ws_a + n_ws_b
                if got != want:
                    errors.append(
                        f"length consistency: merged {key!r} = {got:,} "
                        f"!= n_ws_A + n_ws_B = {n_ws_a:,} + {n_ws_b:,}"
                    )

            # Fs_ws_input cross-half match (cell 16 lines 64-68).
            fs_a = float(a["Fs_ws_input"])
            fs_b = float(b["Fs_ws_input"])
            if not np.isclose(fs_a, fs_b):
                errors.append(
                    f"Fs_ws_input mismatch across halves: a={fs_a} vs b={fs_b}"
                )
            fs_m = float(m["Fs_ws_input"])
            if not np.isclose(fs_a, fs_m):
                errors.append(
                    f"Fs_ws_input mismatch merged vs half-a: "
                    f"a={fs_a} vs merged={fs_m}"
                )
    except Exception as e:
        errors.append(f"length-consistency check raised: {e!r}")
    return errors


def _check_three_files_restored(diff: list[dict[str, Any]]) -> int:
    """Layered post-run validation. Returns 0 on PASS / WARN, 1 on FAIL.

    Replaces the original strict-byte-equality assertion (which would
    have spuriously failed on env drift since 2026-01-11). Layers:

      Tier A (size, per-file):
        - size delta <= 0.1%  -> PASS
        - size delta <= 5%    -> WARN (env drift; continue)
        - size delta  > 5%    -> FAIL

      Tier B (structural):
        - Each per-half NPZ loads and has the 5 REQ_KEYS.
        - Merged NPZ loads and has the 5 REQ_KEYS + 4 provenance keys.
        - Merged sig_wsIdx__idx_cam length == n_cam_A + n_cam_B
          (and analogous for ws-axis arrays).
        - Fs_ws_input matches across all three NPZs.

      Tier C (diff shape):
        - Exactly the 3 expected rel_paths show 'modified' status
          (with cam{1,3,4} cohort all 'unchanged').
    """
    changed = [d for d in diff if d["status"] != "unchanged"]
    print(f"  step 5 diff: {len(diff)} entries, {len(changed)} changed")
    for d in changed:
        sz_pre = d["size_pre"]
        sz_post = d["size_post"]
        print(
            f"    {d['status']:9s} {d['rel_path']:48s}  "
            f"size {sz_pre} -> {sz_post}"
        )

    # ---- Tier C: diff shape ----
    if len(changed) != 3:
        print(
            f"  step 5 FAIL — expected exactly 3 file changes, got "
            f"{len(changed)}. Changed: {[d['rel_path'] for d in changed]}"
        )
        return 1
    changed_by_rel = {d["rel_path"]: d for d in changed}
    missing = sorted(set(EXPECTED_RESTORED_SIZES) - set(changed_by_rel))
    if missing:
        print(
            f"  step 5 FAIL — expected restored paths missing from diff: "
            f"{missing}. Diff was: {sorted(changed_by_rel)}"
        )
        return 1

    # ---- Tier A: size tolerances per file ----
    overall_tier = "pass"  # promoted to 'warn' if any file warns
    for rel, expected_size in EXPECTED_RESTORED_SIZES.items():
        actual_size = changed_by_rel[rel]["size_post"]
        tier, delta = _classify_size_delta(actual_size, expected_size)
        delta_pct = delta * 100.0
        if tier == "pass":
            print(
                f"  size  PASS  {rel:48s}  "
                f"expected={expected_size:>13,} actual={actual_size:>13,} "
                f"delta={delta_pct:.4f}%"
            )
        elif tier == "warn":
            print(
                f"  size  WARN  {rel:48s}  "
                f"expected={expected_size:>13,} actual={actual_size:>13,} "
                f"delta={delta_pct:.4f}% (env drift since 2026-01-11; continuing)"
            )
            overall_tier = "warn"
        else:  # fail
            print(
                f"  size  FAIL  {rel:48s}  "
                f"expected={expected_size:>13,} actual={actual_size:>13,} "
                f"delta={delta_pct:.4f}% (>{_SIZE_TOLERANCE_WARN_FRAC * 100:.0f}%; "
                f"too far from Task 1a inventory)"
            )
            return 1

    # ---- Tier B: structural checks ----
    structural_errors: list[str] = []
    half_a_path = PS48_CAM2_DIR / "20250314ab" / "20250314a.npz"
    half_b_path = PS48_CAM2_DIR / "20250314ab" / "20250314b.npz"
    merged_path = PS48_CAM2_DIR / "20250314.npz"

    structural_errors += _validate_per_half_npz(half_a_path, "a")
    structural_errors += _validate_per_half_npz(half_b_path, "b")
    structural_errors += _validate_merged_npz(merged_path)
    structural_errors += _validate_length_consistency(
        merged_path, half_a_path, half_b_path,
    )

    if structural_errors:
        print(f"  step 5 FAIL — {len(structural_errors)} structural error(s):")
        for err in structural_errors:
            print(f"    {err}")
        return 1
    print("  structural checks: all 8 invariants pass")

    if overall_tier == "warn":
        print(
            "  step 5 WARN — sizes within ±5% but not ±0.1% of Task 1a "
            "inventory. Likely benign env drift since 2026-01-11 "
            "(scipy/numpy version delta documented in Phase 7a.0). "
            "Structural checks all pass; restore considered successful."
        )
    else:
        print(
            "  step 5 PASS — exactly 3 files restored, all sizes within "
            "±0.1% of Task 1a inventory, all structural checks pass."
        )
    return 0


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

    # ---- Step 5: post-run diff + layered validation ----
    print("Step 5 — post-run diff + layered validation (size + structural)")
    post_paths = _walk_inventory_targets()
    post_rows = _stat_inventory(post_paths)
    diff = _diff_inventories(pre_rows, post_rows)
    rc = _check_three_files_restored(diff)
    print()
    if rc == 0:
        print("RESTORE COMPLETE — all 5 steps succeeded; layered checks pass.")
    else:
        print("RESTORE INCOMPLETE — step 5 reported FAIL; investigate before declaring done.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
