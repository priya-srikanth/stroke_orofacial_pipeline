"""Multi-half merge functions (Phase 7-pre-multi-half).

Faithful ports of the canonical tongue notebook's `# PS48 30350314 merge`
section (cells 13/16/17). This module hosts Architecture X's three
post-process merge functions — one per coordinated layer:

  - :func:`merge_licks_and_rewards` (Layer 1; cell 17 port). Currently
    implemented; this Task-4 commit.
  - :func:`merge_alignment_templates` (Layer 3; cell 16 port). Task 5.
  - :func:`merge_centered_parquet` (Layer 2; cell 13 port). Task 6.

All three operate on per-half artefacts emitted by the upstream
per-half loops (Phase 2/3/4 respectively) and produce the merged
parent-level output that downstream consumers read.

**Scope (locked Phase 7-pre-multi-half Task 1 verdict 2026-05-05):**
Pattern A only — PS48 20250314 is the sole session in scope. The
function generalizes from 2-half to N-half where the per-layer
algorithm naturally extends, but the only production caller is
2-half. Pattern B sessions stay on the existing single-half path
by design.

**Vendor reference:** legacy cells live byte-identically at
``docs/legacy_snippets/multi_half_merge/cell_{13,14,15,16,17}_*.py``
(captured by Task 1c with notebook SHA256 + per-cell SHA256 in each
file's header).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants ported verbatim from cell 17 (`_infer_n_cam` keys
# and `_looks_like_frame_indices` heuristics). Kept module-private because
# these match upstream convention rather than user-tunable behavior — the
# canonical `defaults.yaml multi_half:` block exposes them via cohort-wide
# config for parity with the kickoff Task-2 schema, but the function
# defaults to these constants when the kwargs are omitted (so unit tests
# don't need to plumb a defaults dict for every call).
# ---------------------------------------------------------------------------

# Keys in priority order whose 1D array length gives n_cam (cell 17 verbatim).
_DEFAULT_CAM_COUNT_KEYS: tuple[str, ...] = (
    "cam_times",
    "sig_camTimes__idx_cam",
    "t_cam",
    "frame_times_s",
    "camTimes",
)

# Keys in priority order whose scalar value gives n_cam (cell 17 verbatim).
_DEFAULT_CAM_COUNT_INT_KEYS: tuple[str, ...] = (
    "n_frames",
    "n_cam",
    "nFrames",
)

# Threshold below which a 1D numeric array is too short to be a "cam-frame
# timeseries" candidate in the fallback path (cell 17 line 134, > 1000).
_FALLBACK_CAM_TIMESERIES_MIN_SIZE = 1000

# Slack on the upper bound for the frame-index heuristic (cell 17 line 156:
# `mx < (n_cam_hint + 5)`). Sentinel/clamp values at exactly n_cam are
# common enough that a few-element slack avoids false negatives.
_FRAME_INDEX_MAX_SLACK = 5

# Quantization tolerance for the integer-ish check on candidate frame
# indices (cell 17 line 148). Frame indices may be stored as floats
# (NaN-padded sentinel for missing); checking `|x - round(x)| <= tol`
# in the finite subset preserves int detection without dropping
# the NaN-tolerance the heuristic provides.
_FRAME_INDEX_INTEGER_TOL = 1e-6


def _as_array(x: Any) -> np.ndarray | None:
    """Try to convert ``x`` to a numpy array; return None on failure.

    Object-array values (e.g. dict-typed entries from
    :func:`numpy.savez(..., allow_pickle=True)`) are returned with
    ``dtype=object``. Returning None on failure mirrors cell 17's
    ``except Exception: return None`` guard.
    """
    try:
        return np.asarray(x)
    except Exception:
        return None


def _is_numeric_array(x: Any) -> bool:
    """Return True iff ``x`` is convertible to a numeric numpy array.

    Verbatim from cell 17 (line 110-111). A scalar wrapped via
    np.asarray counts as numeric; an object-array does not.
    """
    arr = _as_array(x)
    return (arr is not None) and np.issubdtype(arr.dtype, np.number)


def _infer_n_cam(
    npz_files: dict[str, Any],
    *,
    cam_count_keys: tuple[str, ...] | list[str] = _DEFAULT_CAM_COUNT_KEYS,
    cam_count_int_keys: tuple[str, ...] | list[str] = _DEFAULT_CAM_COUNT_INT_KEYS,
) -> int | None:
    """Infer the wavesurfer-frame n_cam count from a per-half NPZ payload.

    Tier 1 (cell 17 lines 113-119): the first 1D array among
    ``cam_count_keys`` whose .size is positive — return its size.

    Tier 2 (cell 17 lines 120-125): the first scalar-coercible value
    among ``cam_count_int_keys``.

    Tier 3 (cell 17 lines 127-135): the largest 1D numeric array of
    size > :data:`_FALLBACK_CAM_TIMESERIES_MIN_SIZE` — assumed to be a
    cam-aligned timeseries.

    Returns None when no signal yields a count. Callers must check;
    cell 17 raises a RuntimeError in that case (line 165-169) which
    :func:`merge_licks_and_rewards` does too.

    Parameters
    ----------
    npz_files : dict-like
        Mapping of key -> array. In the production path this is the
        ``np.lib.npyio.NpzFile`` returned by :func:`np.load`. Tests pass
        a plain dict with the same access shape.
    """
    # Tier 1: known cam-aligned timeseries
    for k in cam_count_keys:
        if k in npz_files:
            arr = np.asarray(npz_files[k])
            if arr.ndim == 1 and arr.size > 0:
                return int(arr.size)

    # Tier 2: known scalar n_cam keys
    for k in cam_count_int_keys:
        if k in npz_files:
            try:
                return int(npz_files[k])
            except Exception:
                pass

    # Tier 3: largest 1D numeric array > size threshold
    best: int | None = None
    file_keys = (
        npz_files.files if hasattr(npz_files, "files") else list(npz_files.keys())
    )
    for k in file_keys:
        arr = _as_array(npz_files[k])
        if arr is None:
            continue
        if (
            arr.ndim == 1
            and arr.size > _FALLBACK_CAM_TIMESERIES_MIN_SIZE
            and _is_numeric_array(arr)
        ):
            best = max(best or 0, int(arr.size))
    return best


def _looks_like_frame_indices(arr: Any, n_cam_hint: int | None) -> bool:
    """Return True iff ``arr`` looks like a per-frame index array.

    Heuristics (cell 17 lines 137-157):
      - 1D, non-empty, numeric.
      - All finite values are integer-ish within
        :data:`_FRAME_INDEX_INTEGER_TOL`.
      - All finite values are non-negative (allowing -1 as a sentinel
        is intentionally NOT supported by the legacy heuristic; this
        port preserves that strict bound).
      - Max finite value is below ``n_cam_hint + _FRAME_INDEX_MAX_SLACK``
        when a hint is supplied.

    Used by :func:`merge_licks_and_rewards` to decide whether to
    offset a B-half array by the cam-frame offset before concatenation.
    """
    a = np.asarray(arr)
    if a.ndim != 1 or a.size == 0:
        return False
    if not np.issubdtype(a.dtype, np.number):
        return False
    aa = a[np.isfinite(a)]
    if aa.size == 0:
        return False
    # integer-ish
    if np.nanmax(np.abs(aa - np.round(aa))) > _FRAME_INDEX_INTEGER_TOL:
        return False
    mn = float(np.nanmin(aa))
    mx = float(np.nanmax(aa))
    if mn < -1:
        return False
    if n_cam_hint is not None and np.isfinite(n_cam_hint) and n_cam_hint > 0:
        return mx < (n_cam_hint + _FRAME_INDEX_MAX_SLACK)
    return True


def _shift_frame_indices(arr: np.ndarray, offset: int) -> np.ndarray:
    """Add ``offset`` to finite entries of ``arr``, preserving NaNs.

    Verbatim from cell 17 lines 198-200 / 222-224 — the same shift
    code appears twice in the legacy cell (common-key and only-B
    branches). NaN sentinels stay NaN; finite values shift by ``offset``.
    Returns a copy.
    """
    shifted = arr.copy()
    mask = np.isfinite(shifted)
    shifted[mask] = shifted[mask] + offset
    return shifted


def merge_licks_and_rewards(
    per_half_npz_paths: list[Path],
    output_path: Path,
    *,
    cam_count_keys: tuple[str, ...] | list[str] | None = None,
    cam_count_int_keys: tuple[str, ...] | list[str] | None = None,
) -> Path:
    """Merge N per-half ``licks_and_rewards`` NPZs into a single combined
    NPZ at ``output_path`` — faithful port of legacy cell 17.

    The merge follows cell 17's three-tier per-key strategy applied to
    every key present in any of the per-half NPZs:

      1. **1D timeseries of length n_cam[i]** in every half →
         :func:`numpy.concatenate` along axis 0.
      2. **Frame-index arrays** (per :func:`_looks_like_frame_indices`)
         → offset half ``i`` by the cumulative cam-frame count of
         halves ``0..i-1``, then concatenate.
      3. **Same-shape arrays beyond first axis** → concatenate along
         axis 0 (event-style stacking).

    Default fallback (cell 17 line 211): keep half ``0``'s value
    verbatim. Keys present in only some halves are carried over from
    whichever half holds them, with frame-index detection still applied
    to half-i-only arrays so their indices land in the merged frame.

    **N-half generalization:** legacy cell 17 hardcodes 2 halves
    (``A`` / ``B``). This port accepts ``N >= 2``. For ``N == 2`` the
    emitted provenance keys are byte-identical to legacy
    (``merged_from_A``, ``merged_from_B``, ``cam_frame_offset_for_B``,
    ``merged_n_cam_A``, ``merged_n_cam_B``) so any downstream reader
    of legacy-merged NPZs sees the same shape. For ``N >= 3`` the
    legacy A/B keys are NOT emitted (no canonical mapping for >2 halves);
    list-style provenance keys (``merged_from_paths``,
    ``merged_n_cam_per_half``, ``cam_frame_offsets_per_half``) are
    always emitted.

    Parameters
    ----------
    per_half_npz_paths : list[Path]
        Per-half NPZ paths in acquisition order. ``len >= 2``.
    output_path : Path
        Destination for the merged NPZ. Parent directories are created
        as needed. Existing files are overwritten unconditionally —
        upstream callers should gate on overwrite.
    cam_count_keys, cam_count_int_keys : sequences of str, optional
        Override the default :func:`_infer_n_cam` key lists. None →
        use the module-level defaults sourced from cell 17. The
        canonical ``configs/defaults.yaml multi_half:`` block exposes
        these for cohort-wide configuration; the merge function
        defaults to the ported constants so unit tests don't need a
        defaults dict.

    Returns
    -------
    Path
        The ``output_path`` (same value, returned for chaining).

    Raises
    ------
    ValueError
        If fewer than 2 per-half paths are supplied.
    FileNotFoundError
        If any per-half input path is missing.
    RuntimeError
        If :func:`_infer_n_cam` returns None for any half (no signal
        yielded a count) — same fail-loud semantics as cell 17 line
        165-169.
    """
    if len(per_half_npz_paths) < 2:
        raise ValueError(
            f"merge_licks_and_rewards requires N >= 2 per-half NPZs, got "
            f"{len(per_half_npz_paths)}"
        )
    for p in per_half_npz_paths:
        if not Path(p).exists():
            raise FileNotFoundError(f"per-half licks NPZ not found: {p}")

    keys_a = cam_count_keys if cam_count_keys is not None else _DEFAULT_CAM_COUNT_KEYS
    keys_int = (
        cam_count_int_keys
        if cam_count_int_keys is not None
        else _DEFAULT_CAM_COUNT_INT_KEYS
    )

    # Load each half. allow_pickle=True matches cell 17 line 87-88 — the
    # licks NPZ may contain object-array entries (dict-typed sub-results).
    loaded = [np.load(p, allow_pickle=True) for p in per_half_npz_paths]
    n_halves = len(loaded)

    # Infer n_cam per half (Tier 1/2/3 from _infer_n_cam).
    n_cam_per_half: list[int | None] = []
    for i, npz in enumerate(loaded):
        n = _infer_n_cam(npz, cam_count_keys=keys_a, cam_count_int_keys=keys_int)
        if n is None:
            raise RuntimeError(
                f"Could not infer n_cam (frame count) from per-half NPZ "
                f"{per_half_npz_paths[i]}. Add one of the cam_count_keys "
                f"({list(keys_a)}) or cam_count_int_keys ({list(keys_int)}) "
                f"to the upstream Phase 2 emit, or pass an override via "
                f"the kwargs."
            )
        n_cam_per_half.append(n)

    # Cumulative cam-frame offsets: offsets[0]=0, offsets[i]=sum(n_cam[0..i-1]).
    offsets: list[int] = [0]
    for n in n_cam_per_half[:-1]:
        offsets.append(offsets[-1] + int(n))

    # Per-half key sets and the union over all halves.
    keysets = [set(npz.files) for npz in loaded]
    union_keys = set().union(*keysets)
    common = sorted(set.intersection(*keysets))
    only_in_half: list[list[str]] = [
        sorted(keysets[i] - set.intersection(*keysets)) for i in range(n_halves)
    ]

    logger.info(
        "merge_licks_and_rewards: n_halves=%d n_cam_per_half=%s offsets=%s "
        "common_keys=%d union_keys=%d",
        n_halves, n_cam_per_half, offsets, len(common), len(union_keys),
    )

    out: dict[str, Any] = {}

    # ---- Common keys ----
    for k in common:
        arrs = [loaded[i][k] for i in range(n_halves)]
        np_arrs = [_as_array(a) for a in arrs]

        # If any half failed to convert, fall back to half-0's value.
        if any(a is None for a in np_arrs):
            out[k] = arrs[0]
            continue

        # Tier 1: 1D numeric timeseries of length n_cam[i] in every half
        if all(
            a.ndim == 1
            and _is_numeric_array(a)
            and a.size == n_cam_per_half[i]
            for i, a in enumerate(np_arrs)
        ):
            out[k] = np.concatenate(np_arrs, axis=0)
            continue

        # Tier 2: frame-index arrays — offset each half by its cumulative
        # n_cam, then concatenate.
        if all(
            _looks_like_frame_indices(a, n_cam_per_half[i])
            for i, a in enumerate(np_arrs)
        ):
            shifted = [
                _shift_frame_indices(a, offsets[i]) for i, a in enumerate(np_arrs)
            ]
            out[k] = np.concatenate(shifted, axis=0)
            continue

        # Tier 3: same-shape-after-axis-0 numeric arrays → event-style concat
        if (
            all(_is_numeric_array(a) for a in np_arrs)
            and all(a.ndim == np_arrs[0].ndim for a in np_arrs)
            and all(a.dtype == np_arrs[0].dtype for a in np_arrs)
            and all(a.shape[1:] == np_arrs[0].shape[1:] for a in np_arrs)
            and all(a.ndim >= 1 for a in np_arrs)
        ):
            out[k] = np.concatenate(np_arrs, axis=0)
            continue

        # Default: keep half-0's value (cell 17 line 211).
        out[k] = arrs[0]

    # ---- Only-in-half keys ----
    for i in range(n_halves):
        for k in only_in_half[i]:
            arr_i = _as_array(loaded[i][k])
            if arr_i is not None and _looks_like_frame_indices(
                arr_i, n_cam_per_half[i]
            ):
                out[k] = _shift_frame_indices(arr_i, offsets[i])
            else:
                out[k] = loaded[i][k]

    # ---- Provenance keys ----
    # Always emitted: list-style keys for the N-half general case.
    out["merged_from_paths"] = np.array(
        [str(p) for p in per_half_npz_paths], dtype=object
    )
    out["merged_n_cam_per_half"] = np.array(n_cam_per_half, dtype=np.int64)
    out["cam_frame_offsets_per_half"] = np.array(offsets, dtype=np.int64)

    # 2-half byte-identical legacy keys: emit ONLY when N=2 so the
    # merged NPZ for Pattern A (PS48 20250314) matches legacy cell 17
    # output schema exactly. For N>=3 the A/B framing has no canonical
    # mapping; readers fall back to the list-style keys above.
    if n_halves == 2:
        out["merged_from_A"] = str(per_half_npz_paths[0])
        out["merged_from_B"] = str(per_half_npz_paths[1])
        out["cam_frame_offset_for_B"] = np.int64(offsets[1])
        out["merged_n_cam_A"] = np.int64(n_cam_per_half[0])
        out["merged_n_cam_B"] = np.int64(n_cam_per_half[1])

    # ---- Save ----
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Compressed save matches cell 17 line 238 (np.savez_compressed) so
    # the merged file is byte-comparable with legacy outputs in the
    # parity gate (Task 9).
    np.savez_compressed(str(output_path), **out)
    logger.info("merge_licks_and_rewards: wrote %s", output_path)

    return output_path
