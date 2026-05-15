"""Window selector: defines which frames to include in a spatial analysis.

Phase 5 implements ``WholeSessionWindow`` (all frames).
Phase 6 adds ``EventAlignedWindow`` and ``ToneAlignedWindow`` for
peri-event spatial analyses. The spatial analysis functions accept a
``WindowSelector`` and call ``select_frames()``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class WindowSelector(ABC):
    """Abstract base for frame-selection strategies."""

    @abstractmethod
    def select_frames(self, df: pd.DataFrame) -> np.ndarray:
        """Return a boolean mask of frames to include.

        Parameters
        ----------
        df : pd.DataFrame
            Centered DLC DataFrame (one row per frame).

        Returns
        -------
        np.ndarray
            Boolean mask, same length as df.
        """

    @property
    @abstractmethod
    def label(self) -> str:
        """Short label for output filenames (e.g. 'whole', 'tone_-500_5000ms').

        Note on the ``tone_*`` token: this literal was preserved as the
        on-disk filename suffix through Phase 7b-light (per Addendum #1
        bifurcation rule which deferred on-disk-layout-affecting strings
        to Phase 7c). **Phase 7c.1 (2026-05-15) renamed `reward_*` →
        `tone_*`** in lockstep with the 3-session pilot re-emit; legacy
        outputs at the `reward_*` suffix remain untouched on disk and are
        retired in Phase 7c.2 alongside the cohort completion.
        """


class WholeSessionWindow(WindowSelector):
    """Select all frames in the session (no windowing)."""

    def select_frames(self, df: pd.DataFrame) -> np.ndarray:
        return np.ones(len(df), dtype=bool)

    @property
    def label(self) -> str:
        return "whole"


class EventAlignedWindow(WindowSelector):
    """Window around each occurrence of an event, with deduplication.

    Given event centers (in frame indices) and a (pre, post) window in frames,
    builds a boolean mask marking all frames within any event window. Overlapping
    snippets are deduplicated (each frame counted once).

    Parameters
    ----------
    event_frame_indices : np.ndarray
        Frame indices of event onsets (e.g. tone-onset frames under
        Case-2 universal; the auditory cue is the temporal anchor for
        DLC peri-event windows).
    pre_frames : int
        Number of frames before each event to include (positive = before).
    post_frames : int
        Number of frames after each event to include (positive = after).
    n_frames : int
        Total number of frames in the session.
    label_str : str
        Label for filenames.
    """

    def __init__(
        self,
        event_frame_indices: np.ndarray,
        pre_frames: int,
        post_frames: int,
        n_frames: int,
        label_str: str = "event",
    ) -> None:
        self._n_frames = n_frames
        self._label = label_str

        # Build the boolean mask with deduplication
        mask = np.zeros(n_frames, dtype=bool)
        for center in event_frame_indices:
            center = int(center)
            if center < 0:
                continue
            lo = max(0, center - pre_frames)
            hi = min(n_frames, center + post_frames + 1)
            mask[lo:hi] = True

        self._mask = mask
        self._n_events = len(event_frame_indices)
        self._n_selected = int(mask.sum())

    def select_frames(self, df: pd.DataFrame) -> np.ndarray:
        if len(df) != self._n_frames:
            raise ValueError(
                f"DataFrame length {len(df)} != expected {self._n_frames}"
            )
        return self._mask

    @property
    def label(self) -> str:
        return self._label

    @property
    def n_events(self) -> int:
        """Number of event centers used."""
        return self._n_events

    @property
    def n_selected(self) -> int:
        """Number of unique frames selected (after deduplication)."""
        return self._n_selected


class ToneAlignedWindow(EventAlignedWindow):
    """Window around tone events, converting from WS samples to frames.

    Under Case-2 universal (Phase 8a.10.1), every DLC peri-event window
    is scientifically tone-anchored — the auditory cue marks trial onset
    and the WS sample indices supplied here come from Phase 2's
    ``Tone_L`` / ``Tone_R`` NPZ keys (post-swap-fix). The class was
    formerly named ``RewardAlignedWindow``; renamed in Phase 7b-light
    per Addendum #1 source-side narrative cleanup.

    Parameters
    ----------
    tone_ws_samples : np.ndarray
        Tone-onset indices in wavesurfer sample space.
    sig_camIdx__idx_ws : np.ndarray
        Alignment lookup: camera frame index for each WS sample.
        From ``AlignmentResult.sig_camIdx__idx_ws``.
    window_ms : tuple[float, float]
        (pre_ms, post_ms) window in milliseconds. Pre is typically negative
        (before tone) or zero. Post is positive (after tone).
    fps : float
        Camera frame rate (Hz). Default 250.
    n_frames : int
        Total number of DLC/camera frames in the session.
    """

    def __init__(
        self,
        tone_ws_samples: np.ndarray,
        sig_camIdx__idx_ws: np.ndarray,
        window_ms: tuple[float, float],
        fps: float = 250.0,
        n_frames: int = 0,
    ) -> None:
        # Convert WS sample indices → camera frame indices
        tone_frames = _ws_to_cam_frames(tone_ws_samples, sig_camIdx__idx_ws, n_frames)

        # Convert ms window to frame counts
        pre_ms, post_ms = window_ms
        pre_frames = int(np.round(abs(pre_ms) / 1000.0 * fps))
        post_frames = int(np.round(post_ms / 1000.0 * fps))

        # Filename label: ``tone_…ms`` token. Phase 7c.1 (2026-05-15)
        # renamed `reward_*` → `tone_*` in lockstep with the 3-session
        # pilot re-emit (Addendum #1 deferrals discharged here). Legacy
        # outputs at the `reward_*` suffix remain on disk; retired in
        # Phase 7c.2 cohort completion.
        label_str = f"tone_{int(pre_ms)}_{int(post_ms)}ms"

        super().__init__(tone_frames, pre_frames, post_frames, n_frames, label_str)


def _ws_to_cam_frames(
    ws_samples: np.ndarray,
    sig_camIdx__idx_ws: np.ndarray,
    n_cam_frames: int,
) -> np.ndarray:
    """Convert wavesurfer sample indices to camera frame indices.

    Uses the alignment template's ``sig_camIdx__idx_ws`` lookup table.
    Invalid indices (out of range, NaN) are returned as -1.
    """
    ws_samples = np.asarray(ws_samples, dtype=int)
    lut = np.asarray(sig_camIdx__idx_ws, dtype=float)

    good = (ws_samples >= 0) & (ws_samples < len(lut))
    out_float = np.full(ws_samples.shape, np.nan, dtype=float)
    out_float[good] = lut[ws_samples[good]]

    out_int = np.full(ws_samples.shape, -1, dtype=int)
    finite = np.isfinite(out_float)
    out_int[finite] = np.round(out_float[finite]).astype(int)

    if n_cam_frames > 0:
        bad = (out_int < 0) | (out_int >= n_cam_frames)
        out_int[bad] = -1

    return out_int
