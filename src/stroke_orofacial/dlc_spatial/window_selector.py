"""Window selector: defines which frames to include in a spatial analysis.

Phase 5 implements only ``WholeSessionWindow`` (all frames).
Phase 6 will extend with ``RewardAlignedWindow`` and ``CueAlignedWindow``
without requiring changes to Phase 5 code — the spatial analysis functions
accept a ``WindowSelector`` and call ``select_frames()``.
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
        """Short label for output filenames (e.g. 'whole', 'reward_0_6000ms')."""


class WholeSessionWindow(WindowSelector):
    """Select all frames in the session (no windowing)."""

    def select_frames(self, df: pd.DataFrame) -> np.ndarray:
        return np.ones(len(df), dtype=bool)

    @property
    def label(self) -> str:
        return "whole"
