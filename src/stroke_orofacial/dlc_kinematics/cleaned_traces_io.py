"""Phase 7e.4 cleaned-traces loader helpers.

Shared helpers that read v7 ``cleaned_traces/{tongue,jaw}/<animal>/<date>.parquet``
artefacts. Extracted in Phase 7e.4 so that ``dlc_spatial`` callers
(``compute_animal_aggregated_histogram``, ``build_tone_aligned_analysis``,
the cohort drivers in ``scripts/phase_7c2/``) share one entry point with
the kinematic consumers (``tongue_jaw_mismatch._load_bodypart_y_final``,
``mean_sem_visual``, etc.) instead of each module re-implementing the
parquet read + frame-count validation.

For Phase 7e.4 spatial routing the only column needed is
``is_baseline_fill`` (boolean per-frame mask); for kinematic consumers
``y_final`` / ``x_final`` are pulled with NaN-substitution at
``is_baseline_fill=True`` rows. Only the spatial helper landed in
Phase 7e.4; the kinematic loaders stay inline pending a follow-on
extraction pass.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from stroke_orofacial.paths import PathResolver


def load_baseline_fill_mask(
    bodypart: str,
    animal: str,
    date: dt.date,
    resolver: PathResolver,
    *,
    expected_n_frames: int,
) -> np.ndarray:
    """Return the ``is_baseline_fill`` boolean column from cleaned_traces.

    Reads only the ``frame_idx`` and ``is_baseline_fill`` columns (avoids
    materializing the full parquet for the spatial-filter use case), then
    validates:

    1. ``len(cleaned_df) == expected_n_frames`` — cleaned_traces is dense
       per-frame, 1:1 with the Phase 4 centered parquet. If the lengths
       disagree, the (animal, date) tuple may be referencing a stale
       cleanup against a different DLC h5 frame count; raises ValueError
       with both lengths in the message so triage can find the source.
    2. ``frame_idx == arange(N)`` — frame_idx is the dense 0..N-1
       cleanup-order index that lets the caller AND the returned mask
       directly into a centered-parquet-row-aligned boolean array
       without a join. Validated 2026-05-27 on PS54/2025-05-06 across
       both bodyparts (see F-P-1 audit kickoff §3).

    Parameters
    ----------
    bodypart : str
        ``"tongue"`` or ``"jaw"`` (the two bodyparts Phase 7e cleanup
        applies to). Other bodyparts have no cleaned_traces parquet on
        disk; this function raises FileNotFoundError for them.
    animal : str
    date : dt.date
    resolver : PathResolver
    expected_n_frames : int
        Centered-parquet row count. The returned mask MUST match this
        length so callers can AND it into the centered-parquet-aligned
        membership mask via ``~baseline_fill_mask``.

    Returns
    -------
    np.ndarray
        Boolean array of length ``expected_n_frames``. True where the
        bodypart was not detected (placeholder ``y_final = 0.0`` row).

    Raises
    ------
    FileNotFoundError
        If the cleaned_traces parquet does not exist (e.g. bodypart
        outside the Phase 7e cohort, or pre-cleanup session).
    ValueError
        If the parquet length or ``frame_idx`` semantics disagree with
        ``expected_n_frames`` / dense 0..N-1 (signals a stale cleanup or
        an alignment-template mismatch).
    """
    path = resolver.cleaned_trace(bodypart=bodypart, animal=animal, date=date)
    if not path.exists():
        raise FileNotFoundError(
            f"{animal}/{date.isoformat()}/{bodypart}: cleaned_traces parquet "
            f"missing at {path}. Phase 7e cleanup applies only to tongue + "
            f"jaw; other bodyparts have no parquet on disk. If this IS "
            f"tongue or jaw, run the Phase 7e cohort re-emit for the missing "
            f"session before re-trying."
        )
    cdf = pd.read_parquet(path, columns=["frame_idx", "is_baseline_fill"])
    if len(cdf) != expected_n_frames:
        raise ValueError(
            f"{animal}/{date.isoformat()}/{bodypart}: cleaned_traces length "
            f"{len(cdf)} != expected (centered parquet) length "
            f"{expected_n_frames}. This usually means the cleaned_traces "
            f"was produced from a different DLC h5 frame count — re-run "
            f"the Phase 7e cleanup against the current centered parquet."
        )
    frame_idx = cdf["frame_idx"].to_numpy()
    if not np.array_equal(frame_idx, np.arange(expected_n_frames)):
        raise ValueError(
            f"{animal}/{date.isoformat()}/{bodypart}: cleaned_traces "
            f"frame_idx is not dense 0..N-1 (first 5: {frame_idx[:5]}). "
            f"The Phase 7e cleanup writer is supposed to emit one row per "
            f"camera frame with frame_idx=row_index; if you're seeing this, "
            f"the parquet is malformed."
        )
    return cdf["is_baseline_fill"].to_numpy(dtype=bool, copy=False)
