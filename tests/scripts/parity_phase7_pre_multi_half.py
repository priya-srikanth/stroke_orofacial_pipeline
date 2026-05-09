"""Phase 7-pre-multi-half live parity gate (Task 9).

Runs the new multi-half pipeline end-to-end on PS48 20250314 and
compares each output layer against the legacy on-disk artefacts that
were the parity targets when the architecture was specified
(2026-01-11 originals). Three layers, exit-code-driven verdict per
the kickoff Task 9 spec.

Layers
------

  Layer 1 (Phase 2 — licks_and_rewards NPZ).
    Generate new pipeline's merged licks NPZ at
    ``<microscope_pipeline_outputs>/spout_behavior/licks_and_rewards/PS48/_parity/20250314_merged.npz``
    by:
      a) running ``process_session`` on a multi-half manifest →
         emits 14 per-half NPZs (7 output types × 2 halves) under
         ``...spout_behavior/<output_type>/PS48/20250314ab/``.
      b) calling ``merge_licks_and_rewards([per_half_a, per_half_b],
         ...)`` directly to produce the merged NPZ.
    The harness writes the merged result to a
    ``_parity/`` subdir (NOT the canonical parent-level path) so
    repeated runs don't fight any parallel pipeline writes.
    Compare to legacy at
    ``\\research...\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\licks_and_rewards\PS48\20250314.npz``.
    Per-key value equality with ``atol=1e-12`` for numeric arrays;
    exact match for object arrays + provenance keys.

    Note: ``merge_licks_and_rewards`` is NOT yet wired into
    ``process_session_multi_half`` (deferred from Task 4 per its
    commit message). The harness invokes the merge function directly,
    matching what the future production wiring will do.

  Layer 2 (Phase 3 — alignment template).
    Generate new pipeline's merged alignment template at
    ``<microscope_pipeline_outputs>/dlc_analysis/alignment_templates/cam2/PS48/20250314.npz``
    by calling ``load_or_compute_alignment(manifest, resolver, params,
    force_recompute=True)`` with a multi-half manifest. The Step 1
    dispatch routes through ``compute_and_merge_alignment_multi_half``
    (writes per-half templates under the ``_new`` resolver path, then
    merges at parent level). Compare to legacy at
    ``\\research...\DeepLabCut\O2_analysis\alignment_templates\cam2\PS48\20250314.npz``
    (just-restored 43.9 MB file; mtime 2026-05-09 14:27).
    ``Fs_ws_input`` exact; sig_* arrays ``atol=1e-12``; provenance
    keys (``merged_from_A`` / ``merged_from_B`` / ``ws_offset_samples``
    / ``cam_offset_frames``) exact match.

  Layer 3 (Phase 4 — centered DLC parquets).
    Generate new pipeline's per-half centered parquets under
    ``<microscope_pipeline_outputs>/dlc_analysis/centered_spout_midpoint/PS48/20250314ab/``
    by calling ``_center_one_h5`` directly on each half's DLC H5 file
    (using the manifest's per-half ``dlc_h5_file`` paths). The merged
    parquet is intentionally NOT written to disk via
    ``build_centered_parquet`` — that would overwrite the legacy
    parent-level parquet at ``video2_2025-03-14T12_31_07*.parquet``.
    Instead, the merged is computed in-memory via ``pd.concat`` for
    the row-count consistency check.

    Legacy comparison targets (already on disk in ``pipeline_outputs/``
    from the original 2026-01-11 run, which generated per-half
    parquets at parent level for all 4 cameras):
      - ``video2_2025-03-14T12_31_07DLC_*.intermediate.2a6efb6a.parquet``
      - ``video2_2025-03-14T13_09_29DLC_*.intermediate.2a6efb6a.parquet``
    Per-half DataFrame equality (column order + dtypes + per-cell
    ``atol=1e-12`` on numeric columns).
    Merged row count: ``len(new_per_half_a) + len(new_per_half_b) ==
    sum(legacy lengths)``.

Skip-no-legacy
--------------

Each layer independently checks for its legacy artefact at the start;
if missing, the layer status is ``skip_no_legacy`` and the layer is
NOT counted as a failure. Useful for validating the harness on a Mac
host that has only a subset of MICROSCOPE mounts visible.

Exit codes
----------

  0 — all 3 layers PASS or SKIP (no FAILs).
  1 — Layer 1 (licks NPZ) FAIL.
  2 — Layer 2 (alignment template) FAIL.
  3 — Layer 3 (centered parquets) FAIL.
  4 — multiple layers FAIL (verdict log lists each).
  5 — preflight error (manifest build, env, path resolver).

Forensic log
------------

Every run writes ``.scratch_phase_7_pre/parity_run_<timestamp>.log``
with the full stdout + per-layer detail (pre-run paths, deltas, key
mismatches, etc.). The log path is also printed to stdout for the
operator. Logs are intentionally NOT git-committed — they are
transient run artefacts; the durable verdict is the exit code +
markdown summary the operator captures.

CLI
---

  python tests/scripts/parity_phase7_pre_multi_half.py
      # Default: runs all 3 layers on PS48 20250314.
      # Writes log to .scratch_phase_7_pre/parity_run_<ts>.log.

  python tests/scripts/parity_phase7_pre_multi_half.py --layer 2
      # Run only one specific layer (1, 2, or 3). Useful for
      # iterating on a single layer's comparison logic.

  python tests/scripts/parity_phase7_pre_multi_half.py --animal PS48 --date 20250314
      # Override the target session. Default is PS48 20250314 (the
      # only Pattern A multi-half session in the current cohort).
      # Future Pattern A sessions added to multi_half_sessions: can
      # be parity-checked here without code changes.

  python tests/scripts/parity_phase7_pre_multi_half.py --no-write-log
      # Skip the forensic log; only print to stdout. Useful for
      # CI / one-off debug runs.
"""
from __future__ import annotations

import argparse
import datetime
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from stroke_orofacial.alignment.timebase import load_or_compute_alignment
from stroke_orofacial.animals import get_animal
from stroke_orofacial.config_loader import load_defaults, load_session_overrides
from stroke_orofacial.dlc_io.parquet import _center_one_h5, _param_sig
from stroke_orofacial.manifest import build_manifest
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.spout_behavior.multi_half_merge import (
    merge_licks_and_rewards,
)
from stroke_orofacial.spout_behavior.session_processing import (
    process_session,
)


# ---- Constants ----

ATOL_NUMERIC = 1e-12
DEFAULT_ANIMAL = "PS48"
DEFAULT_DATE = datetime.date(2025, 3, 14)

# Layer 2: cell 16 / merge_alignment_templates provenance keys to compare exactly.
_ALIGNMENT_PROVENANCE_KEYS = (
    "merged_from_A",
    "merged_from_B",
    "ws_offset_samples",
    "cam_offset_frames",
)
_ALIGNMENT_FS_KEY = "Fs_ws_input"
_ALIGNMENT_SIG_KEYS = (
    "sig_wsIdx__idx_cam",
    "sig_camIdx__idx_ws",
    "sig_camTimes__idx_cam",
    "sig_wsTimes__idx_ws",
)

# Layer 1: legacy licks NPZ provenance keys (cell 17 schema; emitted
# by merge_licks_and_rewards for N=2). Compared exact-match.
_LICKS_PROVENANCE_KEYS = (
    "merged_from_A",
    "merged_from_B",
    "cam_frame_offset_for_B",
    "merged_n_cam_A",
    "merged_n_cam_B",
)


# ---- Data structures ----

LayerStatus = Literal["pass", "fail", "skip_no_legacy", "error"]


@dataclass
class LayerResult:
    """Per-layer verdict + diagnostic detail."""

    layer: int
    name: str
    status: LayerStatus
    summary: str
    failures: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    traceback_str: str | None = None


# ---- Output writer (forensic log + stdout tee) ----


class _ForensicLog:
    """Tee-style writer: prints every line to stdout AND appends to a log file.

    The log lives at .scratch_phase_7_pre/parity_run_<timestamp>.log when
    enabled; otherwise stdout-only. Used by all 3 layers + the dispatcher.
    """

    def __init__(self, log_path: Path | None) -> None:
        self.log_path = log_path
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(log_path, "w", encoding="utf-8")
            self._fh.write(
                f"# parity_phase7_pre_multi_half log\n"
                f"# started: {datetime.datetime.now().isoformat()}\n"
            )
        else:
            self._fh = None

    def __call__(self, msg: str = "") -> None:
        print(msg)
        if self._fh is not None:
            self._fh.write(msg + "\n")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.write(
                f"# ended: {datetime.datetime.now().isoformat()}\n"
            )
            self._fh.close()


# ---- Layer 1: licks_and_rewards NPZ ----


def _legacy_licks_path(
    resolver: PathResolver, animal: str, date: datetime.date,
) -> Path:
    """Legacy parity target for licks_and_rewards: under the
    ``local_processed_spout`` root which paths.yaml points at the
    MICROSCOPE-mounted ``session_processing3/`` tree (post-Task-2
    fix; the Mac-only-null bug is gone)."""
    return (
        resolver.root("local_processed_spout")
        / "session_processing3"
        / "licks_and_rewards"
        / animal
        / f"{date.strftime('%Y%m%d')}.npz"
    )


def _new_per_half_licks_paths(
    resolver: PathResolver, animal: str, date: datetime.date,
    halves_concat_label: str,
) -> list[Path]:
    """Per-half licks NPZ paths emitted by process_session_multi_half
    under pipeline_outputs/spout_behavior/licks_and_rewards/{ANIMAL}/{date}{label}/."""
    date_str = date.strftime("%Y%m%d")
    base = (
        resolver.pipeline_outputs(subdir="spout_behavior")
        / "licks_and_rewards" / animal / f"{date_str}{halves_concat_label}"
    )
    return [base / f"{date_str}{half_id}.npz" for half_id in halves_concat_label]


def _new_merged_licks_parity_path(
    resolver: PathResolver, animal: str, date: datetime.date,
) -> Path:
    """Where the harness writes its merged licks NPZ for parity.

    Uses a ``_parity/`` subdir under licks_and_rewards/{ANIMAL}/ so
    repeated harness runs don't conflict with any parallel pipeline
    writer that targets the canonical parent-level path. The legacy
    parity target lives in a different tree
    (session_processing3/), so this subdir choice is purely for
    harness-local cleanliness.
    """
    date_str = date.strftime("%Y%m%d")
    base = (
        resolver.pipeline_outputs(subdir="spout_behavior")
        / "licks_and_rewards" / animal / "_parity"
    )
    return base / f"{date_str}_merged.npz"


def _compare_licks_npz(
    new_path: Path, legacy_path: Path,
) -> list[str]:
    """Compare two licks NPZs key-by-key.

    - Numeric arrays: ``np.allclose(..., atol=ATOL_NUMERIC, rtol=0)``.
    - Object arrays / scalars: ``np.array_equal``.
    - Schema: union of keys; missing on either side is a failure.

    Returns a list of human-readable failure strings (empty list = PASS).
    """
    failures: list[str] = []
    new_npz = np.load(new_path, allow_pickle=True)
    legacy_npz = np.load(legacy_path, allow_pickle=True)

    new_keys = set(new_npz.files)
    legacy_keys = set(legacy_npz.files)
    missing_in_new = legacy_keys - new_keys
    missing_in_legacy = new_keys - legacy_keys
    if missing_in_new:
        failures.append(
            f"keys present in legacy but missing in new: {sorted(missing_in_new)}"
        )
    if missing_in_legacy:
        failures.append(
            f"keys present in new but missing in legacy: {sorted(missing_in_legacy)}"
        )

    common = sorted(new_keys & legacy_keys)
    for key in common:
        a = new_npz[key]
        b = legacy_npz[key]
        # Provenance keys: exact match (str / int)
        if key in _LICKS_PROVENANCE_KEYS:
            if not np.array_equal(a, b):
                failures.append(
                    f"provenance key {key!r} differs: new={a!r} legacy={b!r}"
                )
            continue
        # Shape check
        try:
            a_arr = np.asarray(a)
            b_arr = np.asarray(b)
        except Exception as e:
            failures.append(f"key {key!r}: array conversion failed: {e!r}")
            continue
        if a_arr.shape != b_arr.shape:
            failures.append(
                f"key {key!r}: shape mismatch new={a_arr.shape} legacy={b_arr.shape}"
            )
            continue
        if a_arr.dtype != b_arr.dtype:
            # dtype mismatch on numeric: try comparing values anyway
            # (e.g., int32 vs int64 may still match by value); record as info-only
            failures.append(
                f"key {key!r}: dtype mismatch new={a_arr.dtype} legacy={b_arr.dtype} "
                f"(values still compared below)"
            )
        # Value comparison
        if np.issubdtype(a_arr.dtype, np.number) and np.issubdtype(b_arr.dtype, np.number):
            if not np.allclose(a_arr, b_arr, atol=ATOL_NUMERIC, rtol=0, equal_nan=True):
                # Quantify the worst case for triage
                diff = np.abs(a_arr.astype(np.float64) - b_arr.astype(np.float64))
                max_diff = float(np.nanmax(diff)) if diff.size > 0 else float("nan")
                failures.append(
                    f"key {key!r}: numeric arrays differ "
                    f"(max|new-legacy|={max_diff} > atol={ATOL_NUMERIC})"
                )
        else:
            if not np.array_equal(a_arr, b_arr):
                failures.append(
                    f"key {key!r}: non-numeric arrays differ"
                )
    return failures


def _layer1_licks(
    log: _ForensicLog,
    manifest: Any,
    resolver: PathResolver,
) -> LayerResult:
    """Layer 1 — Phase 2 licks_and_rewards parity gate."""
    log("=" * 70)
    log("Layer 1 — Phase 2 licks_and_rewards NPZ")
    log("=" * 70)

    legacy_path = _legacy_licks_path(resolver, manifest.animal, manifest.date)
    log(f"  legacy parity target: {legacy_path}")
    if not legacy_path.exists():
        log("  legacy artefact missing — skip_no_legacy")
        return LayerResult(
            layer=1, name="licks_and_rewards",
            status="skip_no_legacy",
            summary=f"legacy NPZ not found at {legacy_path}",
        )

    halves_concat_label = "".join(h.id for h in manifest.halves)
    per_half_paths = _new_per_half_licks_paths(
        resolver, manifest.animal, manifest.date, halves_concat_label,
    )
    new_merged_path = _new_merged_licks_parity_path(
        resolver, manifest.animal, manifest.date,
    )
    log("  new per-half paths:")
    for p in per_half_paths:
        log(f"    {p}")
    log(f"  new merged path (parity-only subdir): {new_merged_path}")

    try:
        # Step 1: process_session multi-half (writes 14 per-half NPZs).
        log("  generating new per-half NPZs via process_session(...)...")
        process_session(manifest, resolver, overwrite="force")

        # Step 2: confirm per-half licks NPZs exist
        for p in per_half_paths:
            if not p.exists():
                return LayerResult(
                    layer=1, name="licks_and_rewards", status="error",
                    summary=f"per-half NPZ not produced: {p}",
                )

        # Step 3: merge per-halves into the parity-subdir merged path
        log(f"  merging per-half NPZs into {new_merged_path}...")
        merge_licks_and_rewards(per_half_paths, new_merged_path)
        if not new_merged_path.exists():
            return LayerResult(
                layer=1, name="licks_and_rewards", status="error",
                summary=f"merged NPZ not written: {new_merged_path}",
            )

        # Step 4: compare to legacy
        log(f"  comparing new merged ↔ legacy ({ATOL_NUMERIC} atol)...")
        failures = _compare_licks_npz(new_merged_path, legacy_path)

    except Exception as e:
        log(f"  ERROR during Layer 1 generation/comparison: {e!r}")
        return LayerResult(
            layer=1, name="licks_and_rewards", status="error",
            summary=f"exception: {e!r}",
            traceback_str=traceback.format_exc(),
        )

    if failures:
        log(f"  FAIL — {len(failures)} key/shape/value mismatch(es):")
        for f in failures:
            log(f"    - {f}")
        return LayerResult(
            layer=1, name="licks_and_rewards", status="fail",
            summary=f"{len(failures)} mismatch(es) vs legacy",
            failures=failures,
            info={"new_path": str(new_merged_path), "legacy_path": str(legacy_path)},
        )
    log(f"  PASS — all keys match within atol={ATOL_NUMERIC}")
    return LayerResult(
        layer=1, name="licks_and_rewards", status="pass",
        summary=f"all keys match (atol={ATOL_NUMERIC})",
        info={"new_path": str(new_merged_path), "legacy_path": str(legacy_path)},
    )


# ---- Layer 2: alignment template ----


def _legacy_alignment_path(
    resolver: PathResolver, animal: str, date: datetime.date, cam: str = "cam2",
) -> Path:
    """Legacy parity target = restored alignment_template_legacy_read path
    (under O2_analysis/alignment_templates/cam2/{animal}/{date}.npz)."""
    return resolver.alignment_template_legacy_read(animal, date, cam=cam)


def _new_alignment_path(
    resolver: PathResolver, animal: str, date: datetime.date, cam: str = "cam2",
) -> Path:
    """New pipeline merged template path under pipeline_outputs/dlc_analysis/."""
    return resolver.alignment_template_new(animal, date, cam=cam)


def _compare_alignment_npz(
    new_path: Path, legacy_path: Path,
) -> list[str]:
    """Compare two alignment templates per the cell-16 schema rules:

      - Fs_ws_input: exact (np.isclose with default rtol/atol; legacy
        was generated with float64 so exact equality is the norm).
      - sig_* arrays: atol=1e-12.
      - provenance keys (merged_from_A/B + ws_offset_samples +
        cam_offset_frames): exact via np.array_equal.

    The new pipeline's merged template MAY include additional list-
    style provenance keys (merged_from_paths, ws_offsets_per_half,
    cam_offsets_per_half) that the legacy doesn't have — those are
    'present in new but missing in legacy' and reported as INFO,
    not failures (legacy schema is a subset of the new schema by
    design; merged_from_paths is the N-half-general form).
    """
    failures: list[str] = []
    new_npz = np.load(new_path, allow_pickle=True)
    legacy_npz = np.load(legacy_path, allow_pickle=True)

    new_keys = set(new_npz.files)
    legacy_keys = set(legacy_npz.files)
    missing_new = legacy_keys - new_keys
    # NB: keys in (new - legacy) are NOT a failure for alignment templates —
    # the new pipeline emits additional list-style provenance keys
    # (merged_from_paths, ws_offsets_per_half, cam_offsets_per_half) that
    # legacy lacks. Schema is intentionally a superset.
    if missing_new:
        # Anything legacy has but new is missing IS a real failure.
        failures.append(
            f"keys present in legacy but missing in new: {sorted(missing_new)}"
        )

    # Fs_ws_input exact
    if _ALIGNMENT_FS_KEY in new_keys and _ALIGNMENT_FS_KEY in legacy_keys:
        a = float(new_npz[_ALIGNMENT_FS_KEY])
        b = float(legacy_npz[_ALIGNMENT_FS_KEY])
        if not np.isclose(a, b):
            failures.append(
                f"{_ALIGNMENT_FS_KEY!r}: new={a} vs legacy={b}"
            )

    # sig_* arrays atol=1e-12
    for key in _ALIGNMENT_SIG_KEYS:
        if key not in new_keys or key not in legacy_keys:
            continue  # missing-key already reported above
        a = np.asarray(new_npz[key], dtype=np.float64)
        b = np.asarray(legacy_npz[key], dtype=np.float64)
        if a.shape != b.shape:
            failures.append(
                f"{key!r}: shape mismatch new={a.shape} legacy={b.shape}"
            )
            continue
        if not np.allclose(a, b, atol=ATOL_NUMERIC, rtol=0, equal_nan=True):
            diff = np.abs(a - b)
            max_diff = float(np.nanmax(diff)) if diff.size > 0 else float("nan")
            failures.append(
                f"{key!r}: arrays differ "
                f"(max|new-legacy|={max_diff} > atol={ATOL_NUMERIC})"
            )

    # Legacy provenance keys exact-match
    for key in _ALIGNMENT_PROVENANCE_KEYS:
        if key not in new_keys or key not in legacy_keys:
            continue  # missing-key already reported above
        a = new_npz[key]
        b = legacy_npz[key]
        if not np.array_equal(a, b):
            failures.append(
                f"provenance {key!r}: new={a!r} vs legacy={b!r}"
            )

    return failures


def _layer2_alignment(
    log: _ForensicLog,
    manifest: Any,
    resolver: PathResolver,
    params: dict[str, Any],
) -> LayerResult:
    """Layer 2 — Phase 3 alignment template parity gate."""
    log("=" * 70)
    log("Layer 2 — Phase 3 alignment template")
    log("=" * 70)

    legacy_path = _legacy_alignment_path(resolver, manifest.animal, manifest.date)
    log(f"  legacy parity target: {legacy_path}")
    if not legacy_path.exists():
        log("  legacy artefact missing — skip_no_legacy")
        return LayerResult(
            layer=2, name="alignment_template",
            status="skip_no_legacy",
            summary=f"legacy NPZ not found at {legacy_path}",
        )

    new_path = _new_alignment_path(resolver, manifest.animal, manifest.date)
    log(f"  new merged template path: {new_path}")

    try:
        log("  generating new merged template via load_or_compute_alignment(...)...")
        result = load_or_compute_alignment(
            manifest, resolver, params, force_recompute=True,
        )
        log(f"  AlignmentResult source: {result.source}")
        if not new_path.exists():
            return LayerResult(
                layer=2, name="alignment_template", status="error",
                summary=f"merged template not produced at {new_path}",
            )

        log(f"  comparing new ↔ legacy (Fs_ws_input exact, "
            f"sig_* atol={ATOL_NUMERIC}, provenance exact)...")
        failures = _compare_alignment_npz(new_path, legacy_path)

    except Exception as e:
        log(f"  ERROR during Layer 2 generation/comparison: {e!r}")
        return LayerResult(
            layer=2, name="alignment_template", status="error",
            summary=f"exception: {e!r}",
            traceback_str=traceback.format_exc(),
        )

    if failures:
        log(f"  FAIL — {len(failures)} mismatch(es):")
        for f in failures:
            log(f"    - {f}")
        return LayerResult(
            layer=2, name="alignment_template", status="fail",
            summary=f"{len(failures)} mismatch(es) vs legacy",
            failures=failures,
            info={"new_path": str(new_path), "legacy_path": str(legacy_path)},
        )
    log("  PASS — Fs_ws_input + sig_* arrays + provenance all match")
    return LayerResult(
        layer=2, name="alignment_template", status="pass",
        summary=f"all checks pass (atol={ATOL_NUMERIC} on sig_*)",
        info={"new_path": str(new_path), "legacy_path": str(legacy_path)},
    )


# ---- Layer 3: centered DLC parquets ----


def _legacy_centered_parquet_paths(
    resolver: PathResolver, animal: str, date: datetime.date,
    half_specs: list[Any],
    center_mode: str = "spout_midpoint",
    likelihood_threshold: float = 0.7,
) -> list[Path | None]:
    """Resolve the legacy per-half parquet paths (parent-level convention).

    Returns one Path per half_spec, or None if a particular half's
    legacy parquet is missing. Format follows
    ``{output_root}/centered_{mode}/{animal}/video2_{file_timestamp}DLC*.intermediate.{sig}.parquet``
    where {sig} is the param hash.
    """
    sig = _param_sig(center_mode, likelihood_threshold)
    base = (
        resolver.pipeline_outputs(subdir="dlc_analysis")
        / f"centered_{center_mode}"
        / animal
    )
    out: list[Path | None] = []
    for half in half_specs:
        if half.dlc_h5_file is None:
            out.append(None)
            continue
        # Legacy path uses the same H5-filename-as-stem convention as
        # _build_centered_parquet_multi_half — the new pipeline writes
        # per-half parquets with the same name in the 20250314ab/ subdir.
        legacy_name = f"{half.dlc_h5_file.name}.intermediate.{sig}.parquet"
        candidate = base / legacy_name
        out.append(candidate if candidate.exists() else None)
    return out


def _compare_dataframes(
    new_df: pd.DataFrame, legacy_df: pd.DataFrame, label: str,
) -> list[str]:
    """Compare two DataFrames row-by-row with column-set + dtype + value checks.

    Numeric columns: atol=1e-12. Non-numeric: exact equality.
    """
    failures: list[str] = []

    if list(new_df.columns) != list(legacy_df.columns):
        failures.append(
            f"{label}: column sets differ — "
            f"new={list(new_df.columns)[:5]}... vs "
            f"legacy={list(legacy_df.columns)[:5]}..."
        )
        return failures  # short-circuit; column-by-column compare is meaningless

    if len(new_df) != len(legacy_df):
        failures.append(
            f"{label}: row count differs — new={len(new_df)} vs legacy={len(legacy_df)}"
        )

    common_n_rows = min(len(new_df), len(legacy_df))
    if common_n_rows == 0:
        return failures

    for col in new_df.columns:
        a = new_df[col].iloc[:common_n_rows].to_numpy()
        b = legacy_df[col].iloc[:common_n_rows].to_numpy()
        if a.dtype != b.dtype:
            failures.append(
                f"{label} col {col!r}: dtype mismatch new={a.dtype} legacy={b.dtype}"
            )
        if np.issubdtype(a.dtype, np.number) and np.issubdtype(b.dtype, np.number):
            if not np.allclose(a, b, atol=ATOL_NUMERIC, rtol=0, equal_nan=True):
                diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
                max_diff = float(np.nanmax(diff)) if diff.size > 0 else float("nan")
                failures.append(
                    f"{label} col {col!r}: numeric values differ "
                    f"(max|new-legacy|={max_diff} > atol={ATOL_NUMERIC})"
                )
        else:
            if not np.array_equal(a, b):
                failures.append(
                    f"{label} col {col!r}: non-numeric values differ"
                )
    return failures


def _layer3_parquet(
    log: _ForensicLog,
    manifest: Any,
    resolver: PathResolver,
    params: dict[str, Any],
) -> LayerResult:
    """Layer 3 — Phase 4 centered parquet parity gate.

    Computes per-half centered parquets in-memory via _center_one_h5,
    compares them to the legacy parent-level parquets without writing
    new parquets to disk (avoids overwriting the legacy parent-level
    files which are themselves the parity targets).
    """
    log("=" * 70)
    log("Layer 3 — Phase 4 centered parquets")
    log("=" * 70)

    center_mode = "spout_midpoint"  # Phase 4 default; matches Task 6 wiring
    lik_thr = float(
        params.get("dlc_centering", {}).get("likelihood_threshold", 0.7)
    )
    log(f"  center_mode={center_mode!r} likelihood_threshold={lik_thr}")

    legacy_per_half = _legacy_centered_parquet_paths(
        resolver, manifest.animal, manifest.date,
        manifest.halves, center_mode=center_mode,
        likelihood_threshold=lik_thr,
    )
    log("  legacy per-half parquets:")
    for h, p in zip(manifest.halves, legacy_per_half, strict=True):
        log(f"    half {h.id}: {p if p is not None else '(MISSING)'}")

    # Skip if any legacy is missing (graceful)
    missing_halves = [h.id for h, p in zip(manifest.halves, legacy_per_half, strict=True) if p is None]
    if missing_halves:
        log(f"  legacy missing for half(s) {missing_halves} — skip_no_legacy")
        return LayerResult(
            layer=3, name="centered_parquets",
            status="skip_no_legacy",
            summary=f"legacy parquet missing for halves {missing_halves}",
        )

    failures: list[str] = []
    new_dfs: list[pd.DataFrame] = []
    try:
        # Step 1: compute new per-half centered parquets in-memory
        for half in manifest.halves:
            if half.dlc_h5_file is None:
                return LayerResult(
                    layer=3, name="centered_parquets", status="error",
                    summary=f"half {half.id}: dlc_h5_file is None on manifest",
                )
            log(f"  centering half {half.id} from {half.dlc_h5_file}...")
            df_new = _center_one_h5(half.dlc_h5_file, center_mode, lik_thr)
            new_dfs.append(df_new)
            log(f"    -> {len(df_new)} rows × {len(df_new.columns)} cols")

        # Step 2: compare each per-half DataFrame to legacy parquet
        for half, df_new, legacy_path in zip(
            manifest.halves, new_dfs, legacy_per_half, strict=True,
        ):
            log(f"  comparing half {half.id}: new ↔ {legacy_path.name}...")
            df_legacy = pd.read_parquet(legacy_path)
            half_failures = _compare_dataframes(
                df_new, df_legacy, label=f"half {half.id}",
            )
            failures.extend(half_failures)

        # Step 3: merged-row-count consistency check
        n_new_total = sum(len(df) for df in new_dfs)
        n_legacy_total = sum(
            len(pd.read_parquet(p)) for p in legacy_per_half if p is not None
        )
        log(f"  merged row count: new sum={n_new_total} legacy sum={n_legacy_total}")
        if n_new_total != n_legacy_total:
            failures.append(
                f"merged row count: new sum={n_new_total} vs legacy sum={n_legacy_total}"
            )

    except Exception as e:
        log(f"  ERROR during Layer 3 generation/comparison: {e!r}")
        return LayerResult(
            layer=3, name="centered_parquets", status="error",
            summary=f"exception: {e!r}",
            traceback_str=traceback.format_exc(),
        )

    if failures:
        log(f"  FAIL — {len(failures)} mismatch(es):")
        for f in failures:
            log(f"    - {f}")
        return LayerResult(
            layer=3, name="centered_parquets", status="fail",
            summary=f"{len(failures)} mismatch(es) vs legacy",
            failures=failures,
            info={
                "n_halves": len(manifest.halves),
                "legacy_paths": [str(p) for p in legacy_per_half if p is not None],
            },
        )
    log(f"  PASS — per-half DataFrames byte-equal at atol={ATOL_NUMERIC}; "
        f"merged row count consistent")
    return LayerResult(
        layer=3, name="centered_parquets", status="pass",
        summary=f"all per-half DataFrames match (atol={ATOL_NUMERIC}); "
                f"merged row count consistent",
        info={
            "n_halves": len(manifest.halves),
            "n_rows_total": sum(len(df) for df in new_dfs),
        },
    )


# ---- Top-level dispatcher + exit-code logic ----


def _exit_code_for_results(results: list[LayerResult]) -> int:
    """Map per-layer results to a single exit code.

    0 — all PASS or SKIP.
    1 — only Layer 1 failed.
    2 — only Layer 2 failed.
    3 — only Layer 3 failed.
    4 — multiple layers failed OR any layer ERRORed.
    5 — preflight error (handled in main(); this function never returns 5).
    """
    failed = [r for r in results if r.status == "fail"]
    errored = [r for r in results if r.status == "error"]
    if errored:
        return 4
    if not failed:
        return 0
    if len(failed) == 1:
        return failed[0].layer
    return 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 7-pre-multi-half live parity gate (Task 9). "
            "Three-layer comparison vs legacy artefacts on PS48 20250314."
        ),
    )
    parser.add_argument(
        "--animal", default=DEFAULT_ANIMAL,
        help=f"Animal id (default: {DEFAULT_ANIMAL})",
    )
    parser.add_argument(
        "--date", default=DEFAULT_DATE.strftime("%Y%m%d"),
        help=f"Session date YYYYMMDD (default: {DEFAULT_DATE.strftime('%Y%m%d')})",
    )
    parser.add_argument(
        "--layer", type=int, choices=(1, 2, 3),
        help="Run only one layer; default = all 3.",
    )
    parser.add_argument(
        "--no-write-log", action="store_true",
        help="Skip the forensic .log file under .scratch_phase_7_pre/.",
    )
    args = parser.parse_args(argv)

    date = datetime.datetime.strptime(args.date, "%Y%m%d").date()

    # ---- Forensic log setup ----
    if args.no_write_log:
        log_path: Path | None = None
    else:
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        log_path = Path(".scratch_phase_7_pre") / f"parity_run_{ts}.log"
    log = _ForensicLog(log_path)

    # ---- Preflight ----
    log("=" * 70)
    log(f"Phase 7-pre-multi-half parity gate — {args.animal} {args.date}")
    log(f"started: {datetime.datetime.now().isoformat()}")
    if log_path:
        log(f"log file: {log_path}")
    log("=" * 70)
    log("")

    try:
        log("Preflight — building manifest + loading defaults...")
        animal_info = get_animal(args.animal)
        resolver = PathResolver()
        defaults = load_defaults()
        overrides_config = load_session_overrides()
        manifest = build_manifest(
            args.animal, date, resolver, animal_info,
            analysis_context="alignment",  # Phase 3 context
            overrides_config=overrides_config,
        )
        if manifest.halves is None:
            log(
                f"ERROR: {args.animal} {args.date} is not a multi-half "
                f"session (manifest.halves is None). The parity harness only "
                f"applies to Pattern A multi-half sessions; declare in "
                f"configs/session_overrides.yaml multi_half_sessions: first."
            )
            log.close()
            return 5
        log(f"  manifest built: {len(manifest.halves)} half(s) "
            f"({[h.id for h in manifest.halves]})")
        log(f"  animal={manifest.animal} date={manifest.date} "
            f"phase={manifest.phase} day_rel={manifest.day_relative_to_stroke}")
    except Exception as e:
        log(f"ERROR during preflight: {e!r}")
        log(traceback.format_exc())
        log.close()
        return 5

    log("")

    # ---- Run layers ----
    results: list[LayerResult] = []

    layers_to_run = [args.layer] if args.layer else [1, 2, 3]

    for layer_num in layers_to_run:
        if layer_num == 1:
            results.append(_layer1_licks(log, manifest, resolver))
        elif layer_num == 2:
            results.append(
                _layer2_alignment(
                    log, manifest, resolver,
                    params=defaults.get("alignment", {"cam_idx": 2}),
                )
            )
        elif layer_num == 3:
            results.append(_layer3_parquet(log, manifest, resolver, params=defaults))
        log("")

    # ---- Verdict summary ----
    log("=" * 70)
    log("VERDICT SUMMARY")
    log("=" * 70)
    for r in results:
        log(f"  Layer {r.layer} ({r.name:24s}): {r.status:14s} — {r.summary}")
        if r.traceback_str:
            log("    traceback:")
            for line in r.traceback_str.splitlines():
                log(f"      {line}")
    log("")

    rc = _exit_code_for_results(results)
    log(f"exit code: {rc}")
    log("")
    if rc == 0:
        log("ALL LAYERS PASS (or skip_no_legacy on a missing artefact). "
            "Phase 7-pre-multi-half parity gate cleared.")
    else:
        log("PARITY GATE FAILED — see per-layer details above. Investigate "
            "before declaring Task 9 done.")
    log.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
