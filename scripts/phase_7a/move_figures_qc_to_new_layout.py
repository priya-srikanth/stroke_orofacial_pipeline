"""One-shot mover: relocate Phase 7a.4 / 7a.5 outputs to the new layout.

Phase 7a.4-orientation-and-paths-cleanup (2026-05-03) renamed two
output trees and DELETED a third under
``<pipeline_outputs>/dlc_kinematics/``:

| Old path                                            | New path / action                                        |
|-----------------------------------------------------|----------------------------------------------------------|
| ``figures_qc/tongue/<animal>/<date>/``              | ``tongue_angle/<animal>/<date>/``                        |
| ``tongue_jaw_mismatch/figures_qc/<animal>/<date>/`` | ``tongue_jaw_mismatch/within_session/<animal>/<date>/``  |
| ``figures_qc/tongue_comparison/<animal>/<date>/``   | DELETE (visual gate retired; comparison renderer gone)   |

This script handles all three for an existing emit tree on
MICROSCOPE so that historical PNGs stay associated with the new
canonical paths instead of being abandoned at the old location.

Behaviour
---------

- ``--dry-run`` (default): prints what would happen; no filesystem
  changes.
- ``--execute``: actually performs the moves and (with explicit typed
  confirmation) the comparison-grid delete.
- Refuses to clobber an existing destination directory — if any
  per-(animal, date) target already exists at the new path, that
  particular pair is reported as ``CONFLICT`` and skipped (no
  silent overwrite of either side).
- Iterates per-(animal, date) so partial moves are possible if
  interrupted; each per-(animal, date) move is atomic via
  ``shutil.move``.
- Logs every action (or planned action under ``--dry-run``) to
  stdout.

Usage
-----
::

    # Dry-run (default) — print plan, no changes
    python scripts/phase_7a/move_figures_qc_to_new_layout.py

    # Apply the moves; comparison-grid delete prompts for typed confirm
    python scripts/phase_7a/move_figures_qc_to_new_layout.py --execute

    # Skip the comparison-grid delete entirely (safer one-shot)
    python scripts/phase_7a/move_figures_qc_to_new_layout.py --execute --keep-comparison

The script reads ``<pipeline_outputs>`` from the live ``PathResolver``
configuration so the same script works on Mac and Windows hosts
without modification.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from stroke_orofacial.paths import PathResolver


def _iter_per_session_dirs(parent: Path) -> list[tuple[str, str, Path]]:
    """Walk a ``<root>/<animal>/<date>/`` tree and yield each (animal, date, path).

    Returns an empty list if ``parent`` doesn't exist. Skips entries
    that aren't 8-digit date directories (defends against stray files).
    """
    out: list[tuple[str, str, Path]] = []
    if not parent.exists():
        return out
    for animal_dir in sorted(parent.iterdir()):
        if not animal_dir.is_dir():
            continue
        for date_dir in sorted(animal_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            name = date_dir.name
            # 8-digit YYYYMMDD only.
            if not (name.isdigit() and len(name) == 8):
                continue
            out.append((animal_dir.name, name, date_dir))
    return out


def _move_tree(
    label: str,
    old_root: Path,
    new_root: Path,
    *,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Move every per-(animal, date) subtree from ``old_root`` to ``new_root``.

    Returns ``(n_moved, n_conflict, n_skipped)``.
    """
    n_moved = n_conflict = n_skipped = 0
    pairs = _iter_per_session_dirs(old_root)
    if not pairs:
        print(f"[{label}] no per-(animal, date) dirs at {old_root}")
        return (0, 0, 0)
    print(f"[{label}] {len(pairs)} (animal, date) pairs found at {old_root}")
    for animal, date_str, src in pairs:
        dst = new_root / animal / date_str
        if dst.exists():
            n_conflict += 1
            print(
                f"  CONFLICT {animal}/{date_str}: dest exists ({dst}); "
                f"manual review needed"
            )
            continue
        if dry_run:
            print(f"  WOULD MOVE {animal}/{date_str}: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  MOVED {animal}/{date_str}: -> {dst}")
        n_moved += 1
    # If old_root is empty after all moves, prune the (now-empty) animal
    # subdirs and the root itself (best-effort; ignore non-empty cases).
    if not dry_run and n_moved > 0 and n_conflict == 0:
        for animal_dir in list(old_root.iterdir()):
            if animal_dir.is_dir() and not any(animal_dir.iterdir()):
                animal_dir.rmdir()
                print(f"  PRUNED empty {animal_dir}")
        if old_root.exists() and not any(old_root.iterdir()):
            old_root.rmdir()
            print(f"  PRUNED empty {old_root}")
    return (n_moved, n_conflict, n_skipped)


def _delete_tree_with_confirm(
    label: str,
    target: Path,
    *,
    dry_run: bool,
    skip: bool,
) -> int:
    """Delete ``target`` after typed-confirm prompt. Returns count deleted."""
    if skip:
        print(f"[{label}] skipped (--keep-comparison) — {target}")
        return 0
    if not target.exists():
        print(f"[{label}] not present at {target}")
        return 0
    pairs = _iter_per_session_dirs(target)
    n = len(pairs)
    if dry_run:
        print(
            f"[{label}] WOULD DELETE {target} "
            f"({n} (animal, date) pairs inside)"
        )
        return 0
    print(
        f"[{label}] About to permanently delete {target} "
        f"({n} (animal, date) pairs inside)."
    )
    print(
        "  Comparison-grid PNGs at this path are no longer regenerable "
        "(render_comparison_grid was deleted in 7a.4-orientation-and-paths-"
        "cleanup, 2026-05-03)."
    )
    confirm = input("  Type DELETE to confirm: ").strip()
    if confirm != "DELETE":
        print("  ABORTED — typed input did not match 'DELETE'.")
        return 0
    shutil.rmtree(target)
    print(f"  DELETED {target}")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes. Without this flag the script runs in "
        "dry-run mode (prints the plan; no filesystem changes).",
    )
    parser.add_argument(
        "--keep-comparison",
        action="store_true",
        help="Skip the comparison-grid delete entirely; only perform "
        "the two renames. Safer if you want to keep the old "
        "tongue_comparison PNGs as historical reference.",
    )
    args = parser.parse_args(argv)

    dry_run = not args.execute
    mode_label = "DRY-RUN" if dry_run else "EXECUTE"
    print(f"=== Phase 7a.4-orientation-and-paths-cleanup mover ({mode_label}) ===")

    resolver = PathResolver()
    dlc_root = resolver.pipeline_outputs(subdir="dlc_kinematics")
    print(f"dlc_kinematics root: {dlc_root}")

    # 1. tongue: figures_qc/tongue/<animal>/<date>/ -> tongue_angle/<animal>/<date>/
    tongue_summary = _move_tree(
        label="tongue_angle rename",
        old_root=dlc_root / "figures_qc" / "tongue",
        new_root=dlc_root / "tongue_angle",
        dry_run=dry_run,
    )

    # 2. tongue_jaw_mismatch: figures_qc/<animal>/<date>/ -> within_session/<animal>/<date>/
    mismatch_summary = _move_tree(
        label="tongue_jaw_mismatch within_session rename",
        old_root=dlc_root / "tongue_jaw_mismatch" / "figures_qc",
        new_root=dlc_root / "tongue_jaw_mismatch" / "within_session",
        dry_run=dry_run,
    )

    # 3. comparison-grid delete (typed-confirm)
    n_deleted = _delete_tree_with_confirm(
        label="tongue_comparison delete",
        target=dlc_root / "figures_qc" / "tongue_comparison",
        dry_run=dry_run,
        skip=args.keep_comparison,
    )

    # 4. After both renames, the parent figures_qc/ may be empty — prune.
    figures_qc_root = dlc_root / "figures_qc"
    if not dry_run and figures_qc_root.exists() and not any(figures_qc_root.iterdir()):
        figures_qc_root.rmdir()
        print(f"PRUNED empty {figures_qc_root}")

    # Summary
    print()
    print("=== SUMMARY ===")
    print(
        f"tongue_angle rename: moved={tongue_summary[0]} "
        f"conflict={tongue_summary[1]}"
    )
    print(
        f"tongue_jaw_mismatch within_session rename: "
        f"moved={mismatch_summary[0]} conflict={mismatch_summary[1]}"
    )
    print(f"tongue_comparison delete: pairs_deleted={n_deleted}")
    if dry_run:
        print()
        print("DRY-RUN — no filesystem changes made. Re-run with --execute to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
