"""Phase 7c.2 Task 2 Step 6 (Addendum #2 Option A) — Force-emit Phase 4
multi-half merged centered parquet for PS48/2025-03-14.

Closes the F-P-4 production data gap surfaced by the Task 2 spot-check:
Phase 7-pre-multi-half (closed 2026-05-12) shipped `merge_centered_parquet`
+ multi-half routing in `dlc_io.parquet.build_centered_parquet`, but the
3-layer parity gate was scratch-path-only — production's PS48/20250314
centered parquets were never overwritten with the multi-half-merged
version. They sit as separate half-A + half-B single-half parquets
from the pre-multi-half emit on 2026-04-21.

This driver invokes `build_centered_parquet_by_animal_date` with
`overwrite="force"` for all 3 standard center modes:
  - centered_nose
  - centered_spout_midpoint
  - centered_eye_midpoint

Output layout (per `_build_centered_parquet_multi_half`):
  - Per-half:   pipeline_outputs/dlc_analysis/centered_{mode}/PS48/20250314ab/{half_h5_name}.intermediate.{sig}.parquet
  - Merged:     pipeline_outputs/dlc_analysis/centered_{mode}/PS48/{half_a_h5_name}.intermediate.{sig}.parquet
                  (parent level, OVERWRITES the pre-multi-half single-half
                   half-A parquet — that's the design; consumer at
                   interpolation._load_centered_df / dlc_spatial.tone_aligned
                   reads from this parent-level path via
                   manifest.dlc_h5_files[0].name, which after the F-P-5
                   wiring fix in commit e11fe90 resolves to half-A's name.)

The pre-fix half-B parent-level parquet
(centered_{mode}/PS48/video2_2025-03-14T13_09_29...intermediate.{sig}.parquet)
is NOT cleaned up by this driver — it becomes a leftover artifact from
the pre-multi-half single-half emit. Task 7 legacy-tree cleanup will
decide whether to garbage-collect it.

Expected row counts:
  - Per-half parquets: 571,147 (half-A) + 577,365 (half-B)
  - Merged parquet (parent): 1,148,512 = sum of halves

Runs in <1 min wall-time (file I/O bound; ~50 MB total per mode).
"""
from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd

from stroke_orofacial.dlc_io.parquet import (
    _param_sig,
    build_centered_parquet_by_animal_date,
)
from stroke_orofacial.config_loader import load_defaults
from stroke_orofacial.paths import PathResolver


ANIMAL = "PS48"
DATE = dt.date(2025, 3, 14)
DATE_STR = DATE.strftime("%Y%m%d")
CENTER_MODES = ("nose", "spout_midpoint", "eye_midpoint")
EXPECTED_HALF_A_ROWS = 571_147
EXPECTED_HALF_B_ROWS = 577_365
EXPECTED_MERGED_ROWS = EXPECTED_HALF_A_ROWS + EXPECTED_HALF_B_ROWS  # 1,148,512


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("phase_7c2.force_emit_phase4_PS48_20250314")


def _verify_merged_layout(
    resolver: PathResolver, mode: str, half_a_h5_name: str, half_b_h5_name: str
) -> dict:
    """Return mtime + row counts at the per-half subdir AND parent-level merged path."""
    output_root = resolver.pipeline_outputs("dlc_analysis")
    defaults = load_defaults()
    lik_thr = float(defaults["dlc_centering"]["likelihood_threshold"])
    sig = _param_sig(mode, lik_thr)
    parent_a = output_root / f"centered_{mode}" / ANIMAL / f"{half_a_h5_name}.intermediate.{sig}.parquet"
    parent_b = output_root / f"centered_{mode}" / ANIMAL / f"{half_b_h5_name}.intermediate.{sig}.parquet"
    subdir = output_root / f"centered_{mode}" / ANIMAL / f"{DATE_STR}ab"
    sub_a = subdir / f"{half_a_h5_name}.intermediate.{sig}.parquet"
    sub_b = subdir / f"{half_b_h5_name}.intermediate.{sig}.parquet"

    def _info(p: Path) -> dict:
        if not p.exists():
            return {"exists": False}
        df = pd.read_parquet(p)
        return {
            "exists": True,
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "size_bytes": p.stat().st_size,
            "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
        }

    return {
        "sig": sig,
        "parent_merged_half_a_name": _info(parent_a),
        "parent_leftover_half_b_name": _info(parent_b),
        "subdir_per_half_a": _info(sub_a),
        "subdir_per_half_b": _info(sub_b),
    }


def main() -> int:
    resolver = PathResolver()
    output_root = resolver.pipeline_outputs("dlc_analysis")
    log.info(f"output_root = {output_root}")
    log.info(f"animal = {ANIMAL}, date = {DATE.isoformat()}")
    log.info(f"center modes = {CENTER_MODES}")
    log.info(f"expected merged row count = {EXPECTED_MERGED_ROWS:,}")

    half_a_h5_name = (
        "video2_2025-03-14T12_31_07DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
    )
    half_b_h5_name = (
        "video2_2025-03-14T13_09_29DLC_Resnet50_video2Jan26shuffle5_snapshot_060_filtered.h5"
    )

    for mode in CENTER_MODES:
        log.info(f"--- mode={mode} ---")
        # Pre-state probe (sanity)
        pre = _verify_merged_layout(resolver, mode, half_a_h5_name, half_b_h5_name)
        log.info(
            f"  pre-state: parent half-A {pre['parent_merged_half_a_name']}, "
            f"parent half-B {pre['parent_leftover_half_b_name']}, "
            f"subdir present={pre['subdir_per_half_a']['exists']}"
        )
        # Invoke Phase 4 multi-half merge via canonical entry point. Routes to
        # _build_centered_parquet_multi_half because manifest.halves is non-None
        # (Pattern A registry entry covers PS48/20250314).
        result_path = build_centered_parquet_by_animal_date(
            animal=ANIMAL,
            date_str=DATE_STR,
            center_mode=mode,
            resolver=resolver,
            overwrite="force",
        )
        log.info(f"  returned path: {result_path}")
        # Post-state probe
        post = _verify_merged_layout(resolver, mode, half_a_h5_name, half_b_h5_name)
        log.info(
            f"  post-state: parent half-A {post['parent_merged_half_a_name']}"
        )
        log.info(
            f"  per-half subdir: a {post['subdir_per_half_a']}, "
            f"b {post['subdir_per_half_b']}"
        )

        # Hard assertions
        assert post["parent_merged_half_a_name"]["exists"], (
            f"mode={mode}: parent-level merged parquet missing post-force-emit"
        )
        merged_rows = post["parent_merged_half_a_name"]["n_rows"]
        assert merged_rows == EXPECTED_MERGED_ROWS, (
            f"mode={mode}: parent merged parquet has {merged_rows:,} rows, "
            f"expected {EXPECTED_MERGED_ROWS:,}"
        )
        assert post["subdir_per_half_a"]["exists"], (
            f"mode={mode}: per-half subdir half-A parquet missing"
        )
        assert post["subdir_per_half_b"]["exists"], (
            f"mode={mode}: per-half subdir half-B parquet missing"
        )
        assert post["subdir_per_half_a"]["n_rows"] == EXPECTED_HALF_A_ROWS, (
            f"mode={mode}: per-half a has {post['subdir_per_half_a']['n_rows']:,} rows, "
            f"expected {EXPECTED_HALF_A_ROWS:,}"
        )
        assert post["subdir_per_half_b"]["n_rows"] == EXPECTED_HALF_B_ROWS, (
            f"mode={mode}: per-half b has {post['subdir_per_half_b']['n_rows']:,} rows, "
            f"expected {EXPECTED_HALF_B_ROWS:,}"
        )
        log.info(f"  PASS: parent-merged={merged_rows:,} rows; per-half {EXPECTED_HALF_A_ROWS:,} + {EXPECTED_HALF_B_ROWS:,}")

    log.info("ALL MODES PASS — Phase 4 multi-half production state filled for PS48/2025-03-14.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
