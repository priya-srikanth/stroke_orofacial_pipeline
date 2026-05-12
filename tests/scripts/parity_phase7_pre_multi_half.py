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
         ..., index_space="ws_sample")`` directly to produce the
         merged NPZ.

    The harness writes the merged result to a ``_parity/`` subdir
    (NOT the canonical parent-level path) so repeated runs don't fight
    any parallel pipeline writes.

    **Comparison is structural + offset-correctness, NOT byte-identity.**
    Legacy cell-17 stored half-B indices unshifted (an emergent
    heuristic side-effect: cell-17's ``_looks_like_frame_indices``
    returned False on WS-sample arrays because max values >>
    n_cam_hint+5, so they fell through to events-concat with no
    offset). That produced overlapping half-A and half-B ranges on
    the merged time axis with no separator — ambiguous downstream.
    The new ws_sample-mode merge corrects this by offsetting half-B
    by ``n_samples_A``. Byte-equality to legacy would be the wrong
    parity goal.

    Six structural checks (see ``_compare_licks_npz`` docstring):
      1. Schema correctness — new NPZ has all expected ws_sample keys.
      2. Count parity vs legacy — len(merged.X) == len(legacy.X) for
         Lick_L/R + Reward_L/R (Tone_* skipped; legacy didn't have).
      3. Half-A preservation — first n_per_half_A entries match half-A
         exactly (no offset on half-A).
      4. Half-B offset — trailing entries equal half-B + n_samples_A;
         plus no-overlap check: min(half-B) >= max(half-A).
      5. Provenance round-trip — merged_n_samples_A == half_A.n_samples;
         ws_sample_offset_for_B == merged_n_samples_A; merged_from_*
         paths resolve on disk.
      6. Stamp inheritance — side-convention stamps match per-halves.

    Path-string provenance keys (merged_from_A/B) legitimately differ
    from legacy by design (Task-5R resolver split) — surfaced as INFO,
    never block PASS.

    Compare to legacy at
    ``\\research...\Priya\facerhythm_stroke_biomarker_exp\analysis\session_processing3\licks_and_rewards\PS48\20250314.npz``.

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
from stroke_orofacial.lr_convention import to_mouse_frame
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

# Layer 2: cell 16 / merge_alignment_templates provenance keys.
#
# Split into path-string keys vs numeric keys because the resolver
# split (Phase 7-pre-multi-half Task 5R) makes path-string provenance
# DIFFER BY DESIGN between new and legacy: the new pipeline emits
# pipeline_outputs/-rooted paths while legacy was rooted under
# O2_analysis/. That divergence is the resolver split working as
# intended, NOT a parity failure. The harness reports path-string
# diffs as INFO so an operator can see them, but they don't move
# Layer 2 from PASS to FAIL.
#
# Numeric provenance keys (ws_offset_samples / cam_offset_frames)
# are scalars produced by the merge algorithm itself — those still
# exact-match against legacy because the merge math is unchanged.
_ALIGNMENT_PROVENANCE_PATH_KEYS = (
    "merged_from_A",
    "merged_from_B",
)
_ALIGNMENT_PROVENANCE_NUMERIC_KEYS = (
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

# Layer 1: ws_sample-mode event index arrays. The first 4 also exist in
# legacy (count-parity check applies); Tone_* are new-pipeline-only
# (legacy cell-17 vintage predated tone capture, so legacy NPZs have
# no Tone_*).
_LICKS_EVENT_ARRAYS_LEGACY_COMPATIBLE: tuple[str, ...] = (
    "Lick_L", "Lick_R", "Reward_L", "Reward_R",
)
_LICKS_EVENT_ARRAYS_NEW_ONLY: tuple[str, ...] = ("Tone_L", "Tone_R")
_LICKS_EVENT_ARRAYS_ALL: tuple[str, ...] = (
    *_LICKS_EVENT_ARRAYS_LEGACY_COMPATIBLE,
    *_LICKS_EVENT_ARRAYS_NEW_ONLY,
)

# Layer 1: ws_sample-mode merged-NPZ schema. The new merged file must
# carry these keys (per merge_licks_and_rewards index_space='ws_sample'
# docstring). Missing any of these is a schema-correctness FAIL.
_LICKS_WS_REQUIRED_KEYS: tuple[str, ...] = (
    "Fs", "n_samples",
    "Lick_L", "Lick_R", "Reward_L", "Reward_R", "Tone_L", "Tone_R",
    "side_convention_version", "wavesurfer_sides_match_mouse_sides",
    "merged_from_A", "merged_from_B",
    "merged_n_samples_A", "merged_n_samples_B",
    "ws_sample_offset_for_B",
)

# Layer 1: path-string provenance keys that legitimately differ from
# legacy by design (Task-5R resolver split). Surfaced as INFO not FAIL.
_LICKS_PATH_PROVENANCE_KEYS: tuple[str, ...] = ("merged_from_A", "merged_from_B")

# Layer 1: side-convention stamp keys carried forward by the ws_sample
# merge. Inheritance-check compares merged stamps against per-half
# stamps (must match for the merge to have happened at all).
_LICKS_STAMP_KEYS: tuple[str, ...] = (
    "side_convention_version",
    "wavesurfer_sides_match_mouse_sides",
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
    new_path: Path, legacy_path: Path, per_half_paths: list[Path],
) -> tuple[list[str], list[str]]:
    """Compare two licks NPZs structurally + offset-correctness.

    Phase 7-pre-multi-half reframed Layer 1: NOT byte-identity to legacy.
    Legacy cell-17 stored half-B indices unshifted on the merged time
    axis (an emergent heuristic side-effect — see DECISIONS), producing
    half-A and half-B in overlapping WS-sample ranges with no separator.
    The new ws_sample-mode merge applies the n_samples_A offset to
    half-B so the merged time axis is unified and unambiguous. Byte-
    equality is the wrong parity goal — the new schema is BY DESIGN
    different (and more correct) than legacy.

    Six checks:

      1. **Schema correctness** — new NPZ has all expected ws_sample-mode
         keys (:data:`_LICKS_WS_REQUIRED_KEYS`). Missing keys = FAIL.
      2. **Count parity vs legacy (side-aware)** — for each of the 4
         legacy-compatible event arrays
         (:data:`_LICKS_EVENT_ARRAYS_LEGACY_COMPATIBLE`), compare
         ``len(merged.X_<new_side>)`` against
         ``len(legacy.X_<legacy_side>)`` where the side mapping accounts
         for the side-convention stamp:

           - New NPZ carries
             ``wavesurfer_sides_match_mouse_sides`` (mouse-frame labels
             when False, ws-frame-equivalent when True).
           - Legacy NPZ predates the stamp (assumed ws-frame).
           - When stamp = True → direct side comparison.
           - When stamp = False → L↔R swap (use
             :func:`stroke_orofacial.lr_convention.to_mouse_frame`,
             which is involutive on L/R so it works in either direction).

         Tone_* skipped (legacy cell-17 vintage predated tone capture).
      3. **Half-A preservation** — first ``n_per_half_A`` entries of
         ``merged.X`` equal ``half-A.X`` exactly (no offset on half-A).
         Same-frame comparison (both in mouse frame); no side translation.
      4. **Half-B offset** — trailing entries equal
         ``half-B.X + merged_n_samples_A``. Plus no-overlap check:
         ``min(half-B portion) >= max(half-A portion)``. Same-frame.
      5. **Provenance round-trip** —
         ``merged_n_samples_A == per_half_A.n_samples``;
         ``ws_sample_offset_for_B == merged_n_samples_A``;
         ``merged_from_A`` / ``merged_from_B`` strings resolve to existing
         on-disk per-half paths.
      6. **Stamp inheritance** — side-convention stamps on the merged
         NPZ match the per-half stamps (must be identical or the merge
         would have raised before writing).

    INFO (not failures):
      - **Convention decision** (always emitted, first INFO line): which
        frame each NPZ is in, whether translation was applied to count
        parity, and the per-side mapping used. Future readers chasing
        a parity surprise should see this immediately.
      - Path-string provenance differences vs legacy (the Task-5R
        resolver split makes new merged_from_* paths legitimately
        differ from legacy O2_analysis paths).

    Returns ``(failures, info)`` — failures are real parity blockers;
    info is by-design divergences surfaced to the operator.
    """
    failures: list[str] = []
    info: list[str] = []
    new_npz = np.load(new_path, allow_pickle=True)
    legacy_npz = np.load(legacy_path, allow_pickle=True)
    per_half_npzs = [np.load(p, allow_pickle=True) for p in per_half_paths]

    new_keys = set(new_npz.files)

    # ---- Check 1: schema correctness ----
    missing = [k for k in _LICKS_WS_REQUIRED_KEYS if k not in new_keys]
    if missing:
        failures.append(
            f"schema: new merged NPZ missing required ws_sample keys: {missing}"
        )

    # ---- Check 2: count parity vs legacy (side-aware) ----
    #
    # The new pipeline stamps the side-convention scalar
    # `wavesurfer_sides_match_mouse_sides` on every emitted licks NPZ
    # (per stroke_orofacial.lr_convention.stamp_side_convention). The
    # legacy NPZ predates the stamp and is assumed to hold ws-frame
    # labels. So the side mapping for count parity depends on the
    # stamp value:
    #
    #   - stamp True  → new emits ws-frame-equivalent labels → direct
    #     L↔L / R↔R count comparison against legacy.
    #   - stamp False → new emits mouse-frame labels (L/R swapped on
    #     emit) → must compare new.L against legacy.R (and vice versa)
    #     to align semantics.
    #
    # We use lr_convention.to_mouse_frame(side, matches) as the per-
    # side translator. Mathematically it's "give me the mouse-frame
    # equivalent of a ws-frame side"; because L↔R swap is involutive,
    # the same function answers "give me the ws-frame equivalent of a
    # mouse-frame side" when called with the new pipeline's stamp.
    if "wavesurfer_sides_match_mouse_sides" in new_keys:
        ws_matches_mouse = bool(
            np.asarray(new_npz["wavesurfer_sides_match_mouse_sides"])
        )
    else:
        # Schema check above will have flagged this as a missing key;
        # default to True for the count check so we don't crash trying
        # to compute the mapping.
        ws_matches_mouse = True
    if ws_matches_mouse:
        info.append(
            "convention: new NPZ stamp wavesurfer_sides_match_mouse_sides=True "
            "→ new labels match legacy ws-frame labels → direct L↔L / R↔R "
            "count comparison (no translation applied)"
        )
    else:
        info.append(
            "convention: new NPZ stamp wavesurfer_sides_match_mouse_sides=False "
            "→ new emits mouse-frame labels (L↔R swap on emit); legacy NPZ "
            "predates stamp (ws-frame default) → count parity translates "
            "new.L↔legacy.R, new.R↔legacy.L via lr_convention.to_mouse_frame"
        )

    for new_key in _LICKS_EVENT_ARRAYS_LEGACY_COMPATIBLE:
        if new_key not in new_keys:
            continue  # already reported as schema-missing above
        # Translate the trailing _L / _R suffix using to_mouse_frame.
        # Keys are formatted "{stem}_{side}" where side ∈ {"L", "R"}.
        stem, _, new_side = new_key.rpartition("_")
        legacy_side = to_mouse_frame(new_side, ws_matches_mouse)
        legacy_key = f"{stem}_{legacy_side}"
        if legacy_key not in legacy_npz.files:
            failures.append(
                f"count parity: legacy NPZ missing event array "
                f"{legacy_key!r} (translated from new {new_key!r} "
                f"under ws_matches_mouse={ws_matches_mouse})"
            )
            continue
        n_new = int(np.asarray(new_npz[new_key]).size)
        n_legacy = int(np.asarray(legacy_npz[legacy_key]).size)
        if n_new != n_legacy:
            failures.append(
                f"count parity new {new_key!r} ↔ legacy {legacy_key!r}: "
                f"new len={n_new} vs legacy len={n_legacy}"
            )

    # ---- Check 3-4: half-A preservation + half-B offset + no-overlap ----
    # Only meaningful for N=2 halves (the production scope).
    if len(per_half_npzs) == 2 and "merged_n_samples_A" in new_keys:
        n_samples_A = int(np.asarray(new_npz["merged_n_samples_A"]))
        for key in _LICKS_EVENT_ARRAYS_ALL:
            if key not in new_keys:
                continue
            merged_arr = np.asarray(new_npz[key])
            half_A_arr = (
                np.asarray(per_half_npzs[0][key])
                if key in per_half_npzs[0].files else None
            )
            half_B_arr = (
                np.asarray(per_half_npzs[1][key])
                if key in per_half_npzs[1].files else None
            )
            if half_A_arr is None or half_B_arr is None:
                failures.append(
                    f"half-A/B preservation {key!r}: missing on per-half "
                    f"(A_present={half_A_arr is not None}, "
                    f"B_present={half_B_arr is not None})"
                )
                continue
            n_A = int(half_A_arr.size)
            n_B = int(half_B_arr.size)
            if merged_arr.size != n_A + n_B:
                failures.append(
                    f"half-A/B count {key!r}: merged size={merged_arr.size} "
                    f"!= A({n_A}) + B({n_B}) = {n_A + n_B}"
                )
                continue

            # Check 3: half-A preservation (no offset applied to half-A)
            if not np.array_equal(merged_arr[:n_A], half_A_arr):
                failures.append(
                    f"half-A preservation {key!r}: merged[:{n_A}] != half-A "
                    f"(first divergence at idx "
                    f"{int(np.where(merged_arr[:n_A] != half_A_arr)[0][0])})"
                )

            # Check 4: half-B offset == half-B + n_samples_A
            if not np.array_equal(merged_arr[n_A:], half_B_arr + n_samples_A):
                failures.append(
                    f"half-B offset {key!r}: merged[{n_A}:] != "
                    f"half-B + n_samples_A ({n_samples_A})"
                )
                continue

            # Check 4b: no-overlap between half-A portion and half-B portion
            if n_A > 0 and n_B > 0:
                a_max = int(merged_arr[:n_A].max())
                b_min = int(merged_arr[n_A:].min())
                if b_min < a_max:
                    failures.append(
                        f"no-overlap {key!r}: half-B min ({b_min}) < "
                        f"half-A max ({a_max}); merged time axis is not "
                        f"monotone-partitioned at n_samples_A"
                    )

    # ---- Check 5: provenance round-trip ----
    if (
        len(per_half_npzs) == 2
        and "merged_n_samples_A" in new_keys
        and "n_samples" in per_half_npzs[0].files
    ):
        merged_n_A = int(np.asarray(new_npz["merged_n_samples_A"]))
        half_n_A = int(np.asarray(per_half_npzs[0]["n_samples"]))
        if merged_n_A != half_n_A:
            failures.append(
                f"provenance: merged_n_samples_A ({merged_n_A}) != "
                f"per-half[0].n_samples ({half_n_A})"
            )
    if (
        "merged_n_samples_A" in new_keys
        and "ws_sample_offset_for_B" in new_keys
    ):
        merged_n_A = int(np.asarray(new_npz["merged_n_samples_A"]))
        offset_B = int(np.asarray(new_npz["ws_sample_offset_for_B"]))
        if offset_B != merged_n_A:
            failures.append(
                f"provenance: ws_sample_offset_for_B ({offset_B}) != "
                f"merged_n_samples_A ({merged_n_A})"
            )
    for key in ("merged_from_A", "merged_from_B"):
        if key not in new_keys:
            continue
        path_str = str(new_npz[key])
        if not Path(path_str).exists():
            failures.append(
                f"provenance: {key!r} path does not resolve on disk: "
                f"{path_str}"
            )

    # ---- Check 6: stamp inheritance ----
    if len(per_half_npzs) >= 1:
        for key in _LICKS_STAMP_KEYS:
            if key not in new_keys:
                continue  # already reported as schema-missing
            merged_val = np.asarray(new_npz[key]).item()
            for i, half_npz in enumerate(per_half_npzs):
                if key not in half_npz.files:
                    continue
                half_val = np.asarray(half_npz[key]).item()
                if merged_val != half_val:
                    failures.append(
                        f"stamp inheritance {key!r}: merged={merged_val!r} "
                        f"vs half[{i}]={half_val!r}"
                    )

    # ---- INFO: path-string differences vs legacy ----
    for key in _LICKS_PATH_PROVENANCE_KEYS:
        if key not in new_keys or key not in legacy_npz.files:
            continue
        a = str(new_npz[key])
        b = str(legacy_npz[key])
        if a != b:
            info.append(
                f"provenance path {key!r} differs (expected — resolver "
                f"split): new={a!r} legacy={b!r}"
            )

    return failures, info


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

        # Step 3: merge per-halves into the parity-subdir merged path.
        # ws_sample mode: the per-half NPZs emitted by process_session
        # live in WS-sample coordinates (n_samples scalar + WS-indexed
        # event arrays), so the merge must use ws_sample semantics —
        # cam_frame mode would fail to infer n_cam (no cam-frame keys
        # in the new schema) and apply the wrong offset to half-B.
        log(f"  merging per-half NPZs into {new_merged_path} "
            f"(index_space='ws_sample')...")
        merge_licks_and_rewards(
            per_half_paths, new_merged_path, index_space="ws_sample",
        )
        if not new_merged_path.exists():
            return LayerResult(
                layer=1, name="licks_and_rewards", status="error",
                summary=f"merged NPZ not written: {new_merged_path}",
            )

        # Step 4: structural + offset-correctness comparison vs legacy.
        # NOT byte-identity — legacy stored half-B unshifted (emergent
        # cell-17 heuristic side-effect; see DECISIONS). See
        # _compare_licks_npz docstring for the 6-check breakdown.
        log("  comparing new merged ↔ legacy + per-halves "
            "(structural + offset-correctness, NOT byte-identity)...")
        failures, info_lines = _compare_licks_npz(
            new_merged_path, legacy_path, per_half_paths,
        )

    except Exception as e:
        log(f"  ERROR during Layer 1 generation/comparison: {e!r}")
        return LayerResult(
            layer=1, name="licks_and_rewards", status="error",
            summary=f"exception: {e!r}",
            traceback_str=traceback.format_exc(),
        )

    # Surface INFO lines (by-design divergences) at every verdict.
    if info_lines:
        log(f"  INFO — {len(info_lines)} by-design divergence(s):")
        for line in info_lines:
            log(f"    - {line}")

    if failures:
        log(f"  FAIL — {len(failures)} structural/offset mismatch(es):")
        for f in failures:
            log(f"    - {f}")
        return LayerResult(
            layer=1, name="licks_and_rewards", status="fail",
            summary=f"{len(failures)} structural/offset mismatch(es)",
            failures=failures,
            info={
                "new_path": str(new_merged_path),
                "legacy_path": str(legacy_path),
                "per_half_paths": [str(p) for p in per_half_paths],
                "info_lines": info_lines,
            },
        )
    log("  PASS — schema correct, count parity vs legacy, half-A "
        "preservation + half-B offset, provenance + stamps consistent")
    return LayerResult(
        layer=1, name="licks_and_rewards", status="pass",
        summary="structural + offset-correctness all green",
        info={
            "new_path": str(new_merged_path),
            "legacy_path": str(legacy_path),
            "per_half_paths": [str(p) for p in per_half_paths],
            "info_lines": info_lines,
        },
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
) -> tuple[list[str], list[str]]:
    """Compare two alignment templates per the cell-16 schema rules.

    Returns ``(failures, info)``:

      - ``failures``: real parity-blocking mismatches.
      - ``info``: by-design divergences worth surfacing to the operator
        but NOT moving the layer verdict from PASS to FAIL.

    Rules:

      - Fs_ws_input: exact (np.isclose with default rtol/atol; legacy
        was generated with float64 so exact equality is the norm). FAIL.
      - sig_* arrays: atol=1e-12. FAIL.
      - **Numeric provenance keys** (ws_offset_samples /
        cam_offset_frames): exact via np.array_equal. These are merge-
        algorithm scalars and still exact-match. FAIL on diff.
      - **Path-string provenance keys** (merged_from_A / merged_from_B):
        treated as INFO, not FAIL. The Task-5R resolver split (Phase
        7-pre-multi-half) routes new writes through pipeline_outputs/
        while legacy lived under O2_analysis/, so the merged_from_*
        path strings DIFFER BY DESIGN. Surfacing them as INFO lets an
        operator see the resolver split is working without polluting
        the parity verdict.

    The new pipeline's merged template MAY include additional list-
    style provenance keys (merged_from_paths, ws_offsets_per_half,
    cam_offsets_per_half) that the legacy doesn't have — those are
    'present in new but missing in legacy' and reported as INFO,
    not failures (legacy schema is a subset of the new schema by
    design; merged_from_paths is the N-half-general form).
    """
    failures: list[str] = []
    info: list[str] = []
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

    # Numeric provenance keys: exact-match → FAIL on diff
    for key in _ALIGNMENT_PROVENANCE_NUMERIC_KEYS:
        if key not in new_keys or key not in legacy_keys:
            continue  # missing-key already reported above
        a = new_npz[key]
        b = legacy_npz[key]
        if not np.array_equal(a, b):
            failures.append(
                f"provenance {key!r}: new={a!r} vs legacy={b!r}"
            )

    # Path-string provenance keys: differences are by-design → INFO not FAIL
    for key in _ALIGNMENT_PROVENANCE_PATH_KEYS:
        if key not in new_keys or key not in legacy_keys:
            continue  # missing-key already reported above
        a = new_npz[key]
        b = legacy_npz[key]
        if not np.array_equal(a, b):
            info.append(
                f"provenance path {key!r} differs (expected — resolver "
                f"split): new={str(a)!r} legacy={str(b)!r}"
            )

    return failures, info


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
            f"sig_* atol={ATOL_NUMERIC}, numeric provenance exact, "
            f"path-string provenance INFO-only)...")
        failures, info_lines = _compare_alignment_npz(new_path, legacy_path)

    except Exception as e:
        log(f"  ERROR during Layer 2 generation/comparison: {e!r}")
        return LayerResult(
            layer=2, name="alignment_template", status="error",
            summary=f"exception: {e!r}",
            traceback_str=traceback.format_exc(),
        )

    # Surface INFO lines (path-string provenance diffs) at every verdict.
    # They never block PASS — they're the resolver split working as intended.
    if info_lines:
        log(f"  INFO — {len(info_lines)} by-design divergence(s):")
        for line in info_lines:
            log(f"    - {line}")

    if failures:
        log(f"  FAIL — {len(failures)} mismatch(es):")
        for f in failures:
            log(f"    - {f}")
        return LayerResult(
            layer=2, name="alignment_template", status="fail",
            summary=f"{len(failures)} mismatch(es) vs legacy",
            failures=failures,
            info={
                "new_path": str(new_path),
                "legacy_path": str(legacy_path),
                "info_lines": info_lines,
            },
        )
    log("  PASS — Fs_ws_input + sig_* arrays + numeric provenance all match")
    return LayerResult(
        layer=2, name="alignment_template", status="pass",
        summary=f"all checks pass (atol={ATOL_NUMERIC} on sig_*)",
        info={
            "new_path": str(new_path),
            "legacy_path": str(legacy_path),
            "info_lines": info_lines,
        },
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
