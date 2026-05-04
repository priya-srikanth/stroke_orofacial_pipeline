"""Move existing on-disk PNGs from the pre-Addendum-#17 flat layout
into the new ``within_session/`` + ``cross_session/`` subdirs.

Phase 7a.4-cross-session-angle Addendum #17 item 5 (2026-05-04):
restructures the tongue-angle output tree for symmetry with the
``tongue_jaw_mismatch/`` layout (within_session + cross_session
siblings, locked Phase 7a.4-paths-cleanup 2026-05-03).

Layout transitions:

  OLD (pre-#17):
    dlc_kinematics/tongue_angle/{animal}/{date}/...        per-session
    dlc_kinematics/tongue_angle_cohort/{animal}/...        cross-session

  NEW (post-#17):
    dlc_kinematics/tongue_angle/within_session/{animal}/{date}/...
    dlc_kinematics/tongue_angle/cross_session/{animal}/...

The mover does TWO independent moves:

  (1) Per-session tree:
      dlc_kinematics/tongue_angle/{animal}/{date}/
      → dlc_kinematics/tongue_angle/within_session/{animal}/{date}/

      Distinguishes legitimate within-session content (a top-level
      ``{animal}`` dir containing ``{YYYYMMDD}`` date subdirs) from
      the new ``within_session/`` + ``cross_session/`` siblings
      (which are NOT animal IDs — they're the new layout markers).
      Skips any top-level dir named ``within_session`` or
      ``cross_session``.

  (2) Cross-session tree:
      dlc_kinematics/tongue_angle_cohort/{animal}/...
      → dlc_kinematics/tongue_angle/cross_session/{animal}/...

      Walks every animal subdir and merges into the new layout.

Idempotent: re-running after a successful move is a no-op (no
source paths remain). ``--dry-run`` (default) reports planned
moves without executing. ``--execute`` runs the moves.

Usage::

    python scripts/phase_7a/move_tongue_angle_to_subdirs.py            # dry-run
    python scripts/phase_7a/move_tongue_angle_to_subdirs.py --execute  # actually move

Mirrors the
:func:`scripts/phase_7a/move_figures_qc_to_new_layout.py` pattern
from Phase 7a.4-paths-cleanup.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from stroke_orofacial.paths import PathResolver


_DATE_DIR_RE = re.compile(r"^\d{8}$")
_LAYOUT_MARKERS: frozenset[str] = frozenset({
    "within_session", "cross_session",
})


def _enumerate_within_session_moves(
    flat_root: Path,
    new_root: Path,
) -> list[tuple[Path, Path]]:
    """Plan within-session moves: ``{flat_root}/{animal}/{date}/`` →
    ``{new_root}/{animal}/{date}/``. Skips top-level dirs named
    ``within_session`` / ``cross_session`` (= the new layout
    markers; not animal IDs).
    """
    moves: list[tuple[Path, Path]] = []
    if not flat_root.exists():
        return moves
    for animal_dir in sorted(flat_root.iterdir()):
        if not animal_dir.is_dir():
            continue
        if animal_dir.name in _LAYOUT_MARKERS:
            continue
        # Confirm this is an animal dir (= contains date subdirs).
        date_subdirs = [
            d for d in animal_dir.iterdir()
            if d.is_dir() and _DATE_DIR_RE.match(d.name)
        ]
        if not date_subdirs:
            continue
        # Move the whole animal subtree (preserves any non-date
        # children alongside).
        moves.append((animal_dir, new_root / animal_dir.name))
    return moves


def _enumerate_cross_session_moves(
    cohort_root: Path,
    new_root: Path,
) -> list[tuple[Path, Path]]:
    """Plan cross-session moves: ``{cohort_root}/{animal}/`` →
    ``{new_root}/{animal}/``."""
    moves: list[tuple[Path, Path]] = []
    if not cohort_root.exists():
        return moves
    for animal_dir in sorted(cohort_root.iterdir()):
        if not animal_dir.is_dir():
            continue
        moves.append((animal_dir, new_root / animal_dir.name))
    return moves


def _execute_moves(
    moves: list[tuple[Path, Path]], *, label: str, dry_run: bool,
) -> None:
    print(f"\n--- {label} ({len(moves)} moves) ---", flush=True)
    if not moves:
        print("  (no moves planned)", flush=True)
        return
    for src, dst in moves:
        if dry_run:
            print(f"  DRY-RUN: {src} → {dst}", flush=True)
        else:
            if dst.exists():
                # Merge non-destructively: walk src files and move
                # each into dst, preserving subdir structure. Skip
                # files that already exist at dst (idempotent).
                print(
                    f"  MERGE: {src} → {dst} (dst already exists)",
                    flush=True,
                )
                for src_file in src.rglob("*"):
                    if not src_file.is_file():
                        continue
                    rel = src_file.relative_to(src)
                    dst_file = dst / rel
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    if dst_file.exists():
                        print(f"    skip (exists): {dst_file}", flush=True)
                        continue
                    shutil.move(str(src_file), str(dst_file))
                # After merging files, attempt to remove now-empty
                # source tree.
                _rmtree_empty(src)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                print(f"  moved: {src} → {dst}", flush=True)


def _rmtree_empty(p: Path) -> None:
    """Recursively remove empty dirs rooted at ``p``. Skips non-empty
    leaves. Best-effort cleanup after a merge move."""
    if not p.exists() or not p.is_dir():
        return
    for child in list(p.iterdir()):
        if child.is_dir():
            _rmtree_empty(child)
    if p.exists() and p.is_dir() and not any(p.iterdir()):
        try:
            p.rmdir()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually run the moves. Default is dry-run.",
    )
    args = parser.parse_args()

    resolver = PathResolver()
    base = resolver.pipeline_outputs(subdir="dlc_kinematics")

    flat_root = base / "tongue_angle"
    cohort_root = base / "tongue_angle_cohort"
    new_within = flat_root / "within_session"
    new_cross = flat_root / "cross_session"

    print(f"Tongue-angle root: {flat_root}", flush=True)
    print(f"Cohort root:       {cohort_root}", flush=True)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}", flush=True)

    within_moves = _enumerate_within_session_moves(flat_root, new_within)
    _execute_moves(
        within_moves, label="within_session moves",
        dry_run=not args.execute,
    )

    cross_moves = _enumerate_cross_session_moves(cohort_root, new_cross)
    _execute_moves(
        cross_moves, label="cross_session moves",
        dry_run=not args.execute,
    )

    if args.execute and cohort_root.exists():
        # Remove the now-empty old tongue_angle_cohort/ root if all
        # animal subdirs were successfully relocated.
        _rmtree_empty(cohort_root)
        if not cohort_root.exists():
            print(
                f"\nRemoved empty {cohort_root}", flush=True,
            )

    print("\nDONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
