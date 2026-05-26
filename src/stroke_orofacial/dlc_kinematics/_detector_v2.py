"""Phase 7e — v7 lick detector (find_peaks based) + cross-detector dedupe (SKELETON).

Ports the v7 local-maxima detector from
``.scratch_phase_9_1/inv_p3a_step2j_unified_preclean.py`` (lines 441-521)
plus the cross-detector dedupe logic (lines 709-732).

This module is the canonical Stage 2 detector that runs AFTER
:mod:`.preclean` and BEFORE the post-detection gates in :mod:`.gates`.
Designed to run ALONGSIDE the existing legacy slope detector
(:mod:`._detector.\\_slope_detect_lick_peaks`) and bounded-fall detector
(also in scratch ref), with cross-detector dedupe collapsing overlapping
peaks (find_peaks wins on overlap because its local-max location is most
accurate).

Algorithm (Decisions 14-15):

  Step 1 — :func:`detect_local_maxima` runs
    ``scipy.signal.find_peaks`` with ``distance=lm_min_distance_ms`` (50
    ms) and ``height=min_peak_y_abs``. Each local max is validated by
    ``consec_rise >= rise_min_n`` AND (``consec_fall >= fall_min_n`` OR
    immediate baseline retraction). See Decision 15.

  Step 2 — cross-detector dedupe via :func:`merge_detector_outputs`.
    Processes peak lists in order ``lmax → bounded → legacy``; collapses
    peaks within ``dedupe_radius_ms`` (50 ms) of an already-added peak.
    find_peaks wins on overlap. See Decision 14.

All numeric constants from ``configs/defaults.yaml:
dlc_kinematics.tongue_pertrial.detector_v2`` (no magic numbers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class _DetectedPeak:
    """Single detected peak with provenance.

    The ``source`` field tracks which detector emitted the peak
    (informational; survives into the per-trial-per-lick parquet's
    ``source`` column per Decision 4).
    """

    frame: int
    t_ms: float
    y: float
    x: float
    likelihood: float
    source: str  # "lmax" | "bounded" | "legacy"
    rise_start_frame: int | None = None
    fall_end_frame: int | None = None


@dataclass
class _PeakList:
    """Output of :func:`detect_local_maxima` and the legacy/bounded
    detectors. Same shape as
    :class:`stroke_orofacial.dlc_kinematics._detector._LickPeaks` for
    cross-detector dedupe compatibility.
    """

    peak_times_ms: np.ndarray
    peak_y: np.ndarray
    peak_x: np.ndarray
    peak_indices: np.ndarray
    rise_start_indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    fall_end_indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))


def detect_local_maxima(
    y: np.ndarray,
    x: np.ndarray,
    t_ms: np.ndarray,
    fps: float,
    *,
    is_baseline_fill: np.ndarray,
    n_max: int | None = None,
    params: dict[str, Any],
) -> _PeakList | None:
    """find_peaks-based local-maxima detector.

    Runs ``scipy.signal.find_peaks`` on the smoothed y signal with a
    ``distance`` constraint (``lm_min_distance_ms`` = 50 ms). Each
    candidate peak is then validated by:

      - ``consec_rise >= rise_min_n`` consecutive rising frames before
        the peak (slope > ``slope_thr_px_per_s``)
      - ``consec_fall >= fall_min_n`` consecutive falling frames after
        the peak, OR immediate baseline retraction (``is_baseline_fill``
        True at peak+1)

    Returns a :class:`_PeakList` with rise_start/fall_end frame
    delineations (NEW vs the legacy/bounded detectors — feeds the per-
    trial-per-lick parquet's rise_start_ms / fall_end_ms columns per
    Decision 4).

    Returns ``None`` if no detection window in t_ms.

    Direct port of scratch lines 441-521.
    """
    raise NotImplementedError("Port body in Phase 7e Task 3")


def merge_detector_outputs(
    peak_lists: list[tuple[str, _PeakList | None]],
    fps: float,
    *,
    params: dict[str, Any],
) -> list[_DetectedPeak]:
    """Cross-detector dedupe (Decision 14).

    Input: list of ``(source_name, peak_list)`` tuples, processed in the
    order given. Caller is expected to pass them in the order
    ``[("lmax", ...), ("bounded", ...), ("legacy", ...)]`` so find_peaks
    wins on overlap (most-accurate peak location).

    For each peak, skip if its frame is within ``dedupe_radius_ms`` (50
    ms) of any already-added peak. Otherwise add it with its source tag.

    Returns the merged peak list sorted by frame index.

    Direct port of scratch lines 709-732.
    """
    raise NotImplementedError("Port body in Phase 7e Task 3")
