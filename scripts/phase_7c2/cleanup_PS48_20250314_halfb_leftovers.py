"""Phase 7c.2 Task 3 fix (Addendum #4) — pre-Task-7 surgical cleanup of
PS48/2025-03-14 half-B leftover parent-level parquets.

Unblocks the ``dlc_centered_spout_midpoint_parquet`` resolver glob at
``paths.py:792`` which raises ``RuntimeError`` when >1 parquet matches
``video2_{date.isoformat()}T*.parquet`` for the (animal, date). For PS48
2025-03-14 the production tree has TWO parent-level parquets per center
mode (3 modes × 2 = 6 conflicting files): half-A merged (1,148,512 rows;
canonical post-Phase-4 Task 2 Option A force-emit) + half-B single-half
leftover (577,365 rows; pre-Phase-7-pre-multi-half emit 2026-04-21).
The half-B leftovers are dead artifacts under Addendum #3's spatial
pivot (merge-at-parent + per-half-subdir architecture) and were
already queued for deletion in Task 7's expanded cleanup scope per
Q5.B; this driver just pulls forward 3 of those deletions to unblock
Task 3's PS48/2025-03-14 kinematics emit.

Defensive verification per Addendum #4 spec — every target path must
match ALL of:

  1. File exists at the expected canonical path.
  2. mtime falls in the pre-7c.1 era (≤ 2026-05-12) — confirms this
     is the pre-multi-half single-half emit from 2026-04-21, not the
     merged-at-parent post-Task-2-Option-A output (mtime 2026-05-15).
  3. Row count is exactly 577,365 (half-B's frame count from
     Phase 7-pre-multi-half's reported verdict; distinct from the
     1,148,512 merged row count). This is the strongest signal —
     it guarantees we never delete the canonical merged parquet
     (which has 2× the rows).

Only when all 3 checks pass does the driver delete the file. Any
divergence aborts with a non-zero exit + diagnostic.

Targets:

  centered_{nose,spout_midpoint,eye_midpoint}/PS48/video2_2025-03-14T13_09_29DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5.intermediate.{sig}.parquet

3 paths total; param_sig per centering mode embedded as a constant.

Post-deletion verification: re-glob each center mode's parent dir for
``video2_2025-03-14T*.parquet``; assert exactly 1 match remaining
(the merged half-A canonical at 1,148,512 rows).
"""
from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd

from stroke_orofacial.dlc_io.parquet import _param_sig
from stroke_orofacial.paths import PathResolver


ANIMAL = "PS48"
DATE = dt.date(2025, 3, 14)
DATE_ISO = DATE.isoformat()

# Half-B's H5 filename (from pre-Phase-7-pre-multi-half single-half emit).
# Half-A's H5 (which is now the merged parquet name) is the 12_31_07 file.
HALF_B_H5_NAME = (
    "video2_2025-03-14T13_09_29DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
)

# The merged canonical parquet (which we MUST NOT delete) is the 12_31_07
# file. This filename is referenced only in the post-cleanup verification
# (to confirm exactly one remaining file with the expected merged row count).
MERGED_HALF_A_H5_NAME = (
    "video2_2025-03-14T12_31_07DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
)

CENTER_MODES = ("nose", "spout_midpoint", "eye_midpoint")

# Defensive thresholds (Addendum #4 lock).
EXPECTED_HALF_B_ROWS = 577_365
EXPECTED_MERGED_ROWS = 1_148_512
PRE_7C1_MTIME_CUTOFF = dt.datetime(2026, 5, 12, 23, 59, 59)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.cleanup_PS48_20250314_halfb")


def _verify_and_delete(target: Path) -> bool:
    """Verify the 3-check defensive contract, then delete. Returns True on
    successful delete; False on any verification failure."""
    if not target.exists():
        log.error(f"  CHECK 1 FAIL: target path does not exist — {target}")
        return False
    log.info("  CHECK 1 PASS: file exists.")

    stat = target.stat()
    mtime = dt.datetime.fromtimestamp(stat.st_mtime)
    if mtime > PRE_7C1_MTIME_CUTOFF:
        log.error(
            f"  CHECK 2 FAIL: mtime {mtime.isoformat()} is AFTER pre-7c.1 "
            f"cutoff ({PRE_7C1_MTIME_CUTOFF.isoformat()}). Refusing delete — "
            f"this looks like a post-Task-2 production artifact, not a "
            f"pre-multi-half leftover. Aborting."
        )
        return False
    log.info(f"  CHECK 2 PASS: mtime {mtime.isoformat()} <= cutoff.")

    df = pd.read_parquet(target)
    n_rows = len(df)
    if n_rows != EXPECTED_HALF_B_ROWS:
        log.error(
            f"  CHECK 3 FAIL: row count {n_rows:,} != expected half-B "
            f"{EXPECTED_HALF_B_ROWS:,}. Refusing delete — this could be the "
            f"merged canonical (which has {EXPECTED_MERGED_ROWS:,} rows) "
            f"or an unknown variant. Aborting."
        )
        return False
    log.info(f"  CHECK 3 PASS: row count {n_rows:,} == expected half-B.")

    size_bytes = stat.st_size
    log.info(f"  Deleting {target}  ({size_bytes:,} bytes)")
    target.unlink()
    if target.exists():
        log.error(f"  DELETE FAILED: file still present at {target}")
        return False
    log.info("  DELETE OK.")
    return True


def _verify_remaining_state(parent_dir: Path) -> bool:
    """Post-deletion verification: exactly 1 parquet remains for
    PS48/2025-03-14, and it's the merged canonical with 1,148,512 rows."""
    pattern = f"video2_{DATE_ISO}T*.parquet"
    matches = sorted(parent_dir.glob(pattern))
    if len(matches) != 1:
        log.error(
            f"  POST-CHECK FAIL: expected 1 remaining parquet for "
            f"{DATE_ISO} at {parent_dir}, got {len(matches)}: "
            f"{[m.name for m in matches]}"
        )
        return False
    remaining = matches[0]
    if remaining.name != f"{MERGED_HALF_A_H5_NAME}.intermediate.{remaining.name.rsplit('.intermediate.', 1)[1]}":
        log.error(
            f"  POST-CHECK FAIL: remaining parquet name {remaining.name!r} "
            f"does not start with merged canonical {MERGED_HALF_A_H5_NAME!r}"
        )
        return False
    df = pd.read_parquet(remaining)
    if len(df) != EXPECTED_MERGED_ROWS:
        log.error(
            f"  POST-CHECK FAIL: remaining parquet has {len(df):,} rows, "
            f"expected merged canonical {EXPECTED_MERGED_ROWS:,}"
        )
        return False
    log.info(
        f"  POST-CHECK PASS: 1 remaining parquet at {remaining.name} "
        f"with {len(df):,} rows (merged canonical)."
    )
    return True


def main() -> int:
    resolver = PathResolver()
    output_root = resolver.pipeline_outputs("dlc_analysis")
    log.info(f"output_root = {output_root}")
    log.info(f"target animal = {ANIMAL}, date = {DATE_ISO}")
    log.info(f"target half-B h5 name = {HALF_B_H5_NAME}")
    log.info(f"defensive checks: mtime <= {PRE_7C1_MTIME_CUTOFF.isoformat()}, "
             f"rows == {EXPECTED_HALF_B_ROWS:,} (NOT {EXPECTED_MERGED_ROWS:,})")

    # Phase 4 centering threshold from defaults.yaml (matches what
    # _build_centered_parquet_multi_half uses for the param sig).
    from stroke_orofacial.config_loader import load_defaults
    defaults = load_defaults()
    lik_thr = float(defaults["dlc_centering"]["likelihood_threshold"])

    deleted_paths: list[Path] = []
    failed_paths: list[Path] = []

    for mode in CENTER_MODES:
        sig = _param_sig(mode, lik_thr)
        parent_dir = output_root / f"centered_{mode}" / ANIMAL
        target = parent_dir / f"{HALF_B_H5_NAME}.intermediate.{sig}.parquet"
        log.info(f"\n--- mode={mode} (sig={sig}) ---")
        log.info(f"  target: {target}")
        if _verify_and_delete(target):
            deleted_paths.append(target)
        else:
            failed_paths.append(target)
            continue
        if not _verify_remaining_state(parent_dir):
            failed_paths.append(target)

    log.info("")
    log.info("=== SUMMARY ===")
    log.info(f"  Deleted: {len(deleted_paths)}/{len(CENTER_MODES)}")
    for p in deleted_paths:
        log.info(f"    {p}")
    if failed_paths:
        log.error(f"  Failed verification or post-check: {len(failed_paths)}")
        for p in failed_paths:
            log.error(f"    {p}")
        return 1
    log.info(f"  All 3 leftovers cleaned. Phase 7a.3 resolver glob now "
             f"unambiguous for PS48/{DATE_ISO}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
