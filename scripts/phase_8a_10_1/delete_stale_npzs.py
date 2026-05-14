"""Phase 8a.10.1 Task 3.5 Step 2 — stale-NPZ cleanup driver.

Consumes the audit CSV at
``.scratch_phase_8a_10_1/task_3_5_stale_npz_audit.csv`` and deletes
every row whose ``verdict`` is in ``DELETE_TARGETS`` (default: all
DELETE_* + AMBIGUOUS classes, per Priya 2026-05-14 "OK to delete all").

Pre-delete capture (recorded to ``scripts/phase_8a_10_1/deletion_manifest.json``):
- sha256 + file size — for the audit trail.
- The full path being deleted.
- The audit verdict + reason that justifies the deletion.

Safety guards:
- Every target path is required to resolve under
  ``resolver.pipeline_outputs("spout_behavior") / <subtree>``.
  Anything outside that tree raises ``ValueError`` and aborts the
  driver before any deletion.
- Files that already disappeared between audit + delete are logged
  with ``status="ALREADY_GONE"`` and don't count as failures.
- Pattern-A nested subdirs (``<animal>/<YYYYMMDD><concat>/``) get
  ``rmdir``-cleaned at the end if they're empty after per-half file
  deletion. The cleanup never recurses into non-empty dirs.

Run::

    conda activate stroke_orofacial
    python scripts/phase_8a_10_1/delete_stale_npzs.py

CLAUDE.md compliance: writes are scoped to
``pipeline_outputs/spout_behavior/`` only. Raw wavesurfer .h5 files,
camera output, DLC inference outputs, and other roots are NEVER
touched.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from stroke_orofacial.paths import PathResolver

AUDIT_CSV = Path(".scratch_phase_8a_10_1/task_3_5_stale_npz_audit.csv")
DELETION_MANIFEST = Path("scripts/phase_8a_10_1/deletion_manifest.json")

# Verdict classes to delete. Priya 2026-05-14: "OK to delete all".
DELETE_TARGETS = frozenset({
    "DELETE_EXCLUDED",
    "DELETE_OUTSIDE_CANONICAL",
    "AMBIGUOUS",
})

OUTPUT_TYPES = (
    "wavesurfer_signals_processed",
    "treadmill_signals_preprocessed",
    "licks_and_rewards",
    "running_bouts",
    "grooming_bouts",
    "quiet_bouts",
    "peri_reward_periods",
)


def _sha256_size(path: Path) -> tuple[str | None, int | None]:
    if not path.exists():
        return None, None
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _assert_under_safe_tree(target: Path, safe_root: Path) -> None:
    """Raise ValueError if target doesn't resolve under safe_root."""
    try:
        target_resolved = Path(target).resolve(strict=False)
        safe_resolved = Path(safe_root).resolve(strict=False)
    except OSError:
        raise ValueError(f"Cannot resolve path for safety check: {target}")
    # Use os.path.commonpath equivalent via parts-prefix check.
    try:
        target_resolved.relative_to(safe_resolved)
    except ValueError:
        raise ValueError(
            f"REFUSING TO DELETE: {target} does not resolve under "
            f"safe root {safe_root}. This is a safety abort to prevent "
            f"deletions outside pipeline_outputs/spout_behavior/."
        )


def main() -> None:
    if not AUDIT_CSV.exists():
        raise FileNotFoundError(f"Audit CSV missing: {AUDIT_CSV}")

    resolver = PathResolver()
    safe_root = resolver.pipeline_outputs("spout_behavior")
    print(f"Safe-tree root: {safe_root}")

    # Load audit rows.
    with AUDIT_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Audit CSV: {len(rows)} total rows")
    target_rows = [r for r in rows if r["verdict"] in DELETE_TARGETS]
    print(f"DELETE-target rows: {len(target_rows)}")

    # Phase 1: safety-check every target path resolves under safe_root.
    # Abort BEFORE any deletion if any path escapes the safe tree.
    for r in target_rows:
        _assert_under_safe_tree(Path(r["path"]), safe_root)
    print("All target paths confirmed under safe tree ✓")

    # Phase 2: delete with sha256 + size capture.
    deletion_records: list[dict] = []
    n_deleted = 0
    n_already_gone = 0
    n_error = 0
    total_bytes_freed = 0
    pattern_a_subdirs: set[Path] = set()

    for i, r in enumerate(target_rows):
        target = Path(r["path"])
        record = {
            "subtree": r["subtree"],
            "animal": r["animal"],
            "date_str": r["date_str"],
            "half_suffix": r["half_suffix"],
            "layout": r["layout"],
            "audit_verdict": r["verdict"],
            "audit_reason": r["reason"],
            "path": str(target),
            "pre_delete_sha256": None,
            "pre_delete_size_bytes": None,
            "status": "OK",
            "error_msg": "",
        }
        if not target.exists():
            record["status"] = "ALREADY_GONE"
            n_already_gone += 1
            deletion_records.append(record)
            continue
        sha, size = _sha256_size(target)
        record["pre_delete_sha256"] = sha
        record["pre_delete_size_bytes"] = size
        try:
            target.unlink()
        except OSError as exc:
            record["status"] = f"ERROR_{type(exc).__name__}"
            record["error_msg"] = str(exc)
            n_error += 1
            deletion_records.append(record)
            print(f"  [{i+1}/{len(target_rows)}] ERROR: {target}: {exc}")
            continue
        n_deleted += 1
        total_bytes_freed += size or 0
        if r["layout"] == "patternA_nested":
            pattern_a_subdirs.add(target.parent)
        deletion_records.append(record)
        if (i + 1) % 50 == 0:
            print(
                f"  [{i+1}/{len(target_rows)}] deleted "
                f"{n_deleted} so far, {total_bytes_freed/1e9:.2f} GB freed"
            )

    # Phase 3: remove empty Pattern-A nested subdirs.
    removed_dirs: list[str] = []
    for d in sorted(pattern_a_subdirs):
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                removed_dirs.append(str(d))
        except OSError as exc:
            print(f"  Could not rmdir {d}: {exc}")

    # Also check the `_parity/` subdir if the AMBIGUOUS file lived there.
    parity_dirs_to_check: set[Path] = set()
    for r in target_rows:
        if r["verdict"] == "AMBIGUOUS":
            parity_dirs_to_check.add(Path(r["path"]).parent)
    for d in sorted(parity_dirs_to_check):
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                removed_dirs.append(str(d))
        except OSError as exc:
            print(f"  Could not rmdir {d}: {exc}")

    # Phase 4: write deletion manifest.
    DELETION_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    out_summary = {
        "audit_csv": str(AUDIT_CSV),
        "safe_root": str(safe_root),
        "delete_targets": sorted(DELETE_TARGETS),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_total_target_rows": len(target_rows),
        "n_deleted": n_deleted,
        "n_already_gone": n_already_gone,
        "n_error": n_error,
        "total_bytes_freed": total_bytes_freed,
        "total_mb_freed": round(total_bytes_freed / 1e6, 2),
        "empty_subdirs_removed": removed_dirs,
        "records": deletion_records,
    }
    DELETION_MANIFEST.write_text(
        json.dumps(out_summary, indent=2, default=str), encoding="utf-8",
    )

    print(
        f"\nDone. {n_deleted} deleted, {n_already_gone} already-gone, "
        f"{n_error} errored. {total_bytes_freed/1e9:.2f} GB freed."
    )
    print(f"Empty subdirs removed: {len(removed_dirs)}")
    print(f"Manifest: {DELETION_MANIFEST}")


if __name__ == "__main__":
    main()
