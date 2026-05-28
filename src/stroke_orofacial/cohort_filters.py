"""Reusable per-session filtering for cohort drivers.

Declarative threshold spec for session-level inclusion based on lick
counts + trials-with-licks counts derived from the Phase 2
``spout_licks_and_rewards/<animal>/<YYYYMMDD>.npz`` files.

Consumed initially by the Q-lock 12a per-session W-2 boxplots (a
session with very few licks produces a sparse histogram → noisy W-2);
reusable as-is by every future Q-lock 12+ figure or stats analysis
that wants to drop unreliably-sparse sessions.

Default thresholds live in ``configs/defaults.yaml`` under
``cohort_filters.default`` so consumers don't have to memorize the
threshold values; CLI / kwarg overrides take precedence over the
config.

Q12-N (locked 2026-05-28): "trials with licks" uses the tone-aligned
window ``TASK5_TONE_WINDOW_MS = (0, 8000)`` ms post-tone (Q-lock 12
convention). A trial counts as "with licks" if at least one same-side
lick (mouse-frame, post-side-convention) falls in the window.

The Pre-epoch "bias toward 0" caveat (Q-lock 12 Addendum #5 v2) is
orthogonal to filtering — filter thresholds apply uniformly across
pre + post sessions.
"""
from __future__ import annotations

import datetime
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from stroke_orofacial.paths import PathResolver

logger = logging.getLogger(__name__)


# Q-lock 12 tone window — locked at this constant rather than imported
# from ``dlc_spatial.render_on_demand`` so consumers needn't pull the
# whole spatial substrate just to use the filter.
DEFAULT_TONE_WINDOW_MS: tuple[float, float] = (0.0, 8000.0)


@dataclass(frozen=True)
class SessionLickStats:
    """Per-session lick statistics from the Phase 2 NPZ.

    ``n_*_trials_with_licks`` is computed against the
    ``DEFAULT_TONE_WINDOW_MS`` post-tone window per Q12-N. Same-side
    matching: ``L`` trial counts a lick only if it falls in the L-tone
    window AND it's an ``Lick_L`` event.
    """

    animal: str
    date: datetime.date
    n_licks_L: int
    n_licks_R: int
    n_licks_total: int
    n_L_trials: int
    n_R_trials: int
    n_L_trials_with_licks: int
    n_R_trials_with_licks: int


@dataclass(frozen=True)
class SessionFilter:
    """Declarative threshold spec.

    All fields are minimums; ``None`` = no filter on that dimension.
    A session is kept iff every non-None threshold is satisfied
    (AND semantic). When every field is None the filter is
    pass-through (used as the default).
    """

    min_licks_total: int | None = None
    min_licks_per_side: int | None = None
    min_trials_with_licks_per_side: int | None = None

    def is_pass_through(self) -> bool:
        return (
            self.min_licks_total is None
            and self.min_licks_per_side is None
            and self.min_trials_with_licks_per_side is None
        )

    def check(self, stats: SessionLickStats) -> tuple[bool, str | None]:
        """Return (kept, drop_reason).

        ``drop_reason`` is None when kept; otherwise a short string
        like ``"min_licks_total=50 not met (n=12)"``.
        """
        if self.min_licks_total is not None and stats.n_licks_total < self.min_licks_total:
            return False, (
                f"min_licks_total={self.min_licks_total} "
                f"not met (n={stats.n_licks_total})"
            )
        if self.min_licks_per_side is not None:
            if stats.n_licks_L < self.min_licks_per_side:
                return False, (
                    f"min_licks_per_side={self.min_licks_per_side} "
                    f"L not met (n_L={stats.n_licks_L})"
                )
            if stats.n_licks_R < self.min_licks_per_side:
                return False, (
                    f"min_licks_per_side={self.min_licks_per_side} "
                    f"R not met (n_R={stats.n_licks_R})"
                )
        if self.min_trials_with_licks_per_side is not None:
            if stats.n_L_trials_with_licks < self.min_trials_with_licks_per_side:
                return False, (
                    f"min_trials_with_licks_per_side="
                    f"{self.min_trials_with_licks_per_side} "
                    f"L not met (n={stats.n_L_trials_with_licks})"
                )
            if stats.n_R_trials_with_licks < self.min_trials_with_licks_per_side:
                return False, (
                    f"min_trials_with_licks_per_side="
                    f"{self.min_trials_with_licks_per_side} "
                    f"R not met (n={stats.n_R_trials_with_licks})"
                )
        return True, None


@dataclass(frozen=True)
class SessionFilterResult:
    """Output of :func:`apply_session_filter`.

    Carries kept dates + dropped (date, reason) pairs + per-date stats
    (for both kept AND dropped) so downstream audit CSVs can surface
    the underlying numbers without re-reading NPZ files.
    """

    kept_dates: list[datetime.date]
    dropped: list[tuple[datetime.date, str]]
    stats_by_date: dict[datetime.date, SessionLickStats] = field(default_factory=dict)
    filter_spec: SessionFilter = field(default_factory=SessionFilter)


def _count_trials_with_licks(
    tone_samples: np.ndarray,
    lick_samples: np.ndarray,
    window_samples: int,
) -> int:
    """Count tones with at least one lick in ``[t, t + window_samples)``.

    O(n_tones * log n_licks) via searchsorted; suitable for the
    cohort's typical 50-200 tones × 1000-3000 licks per session.
    """
    if tone_samples.size == 0 or lick_samples.size == 0:
        return 0
    lo = np.searchsorted(lick_samples, tone_samples, side="left")
    hi = np.searchsorted(lick_samples, tone_samples + window_samples, side="left")
    # Each tone has licks in window iff hi > lo (at least one lick in [t, t+win)).
    return int((hi > lo).sum())


def compute_session_lick_stats(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    tone_window_ms: tuple[float, float] = DEFAULT_TONE_WINDOW_MS,
) -> SessionLickStats | None:
    """Read the Phase 2 NPZ; return lick statistics.

    Returns ``None`` if the NPZ file is missing for that session
    (no exception — caller treats as a missing-session skip).

    ``tone_window_ms`` overrides the Q-lock 12 default ``(0, 8000)``
    if downstream callers want a different definition of "trial with
    licks".
    """
    npz_path = resolver.spout_licks_and_rewards_npz(animal, date)
    if not Path(npz_path).exists():
        return None
    data = np.load(str(npz_path), allow_pickle=True)
    fs = float(data["Fs"])
    licks_L = np.asarray(data.get("Lick_L", np.array([], dtype=np.int64)), dtype=np.int64)
    licks_R = np.asarray(data.get("Lick_R", np.array([], dtype=np.int64)), dtype=np.int64)
    tones_L = np.asarray(data.get("Tone_L", np.array([], dtype=np.int64)), dtype=np.int64)
    tones_R = np.asarray(data.get("Tone_R", np.array([], dtype=np.int64)), dtype=np.int64)
    licks_L.sort()
    licks_R.sort()
    tones_L.sort()
    tones_R.sort()

    pre_ms, post_ms = tone_window_ms
    # Q12-N convention: post-tone window only — count licks in
    # ``[tone, tone + post_ms)`` ignoring any negative pre_ms component
    # (Q-lock 12 default ``(0, 8000)`` has pre_ms = 0 anyway).
    win_samples = int(round((post_ms - max(pre_ms, 0.0)) * fs / 1000.0))
    n_L_with = _count_trials_with_licks(tones_L, licks_L, win_samples)
    n_R_with = _count_trials_with_licks(tones_R, licks_R, win_samples)

    return SessionLickStats(
        animal=animal,
        date=date,
        n_licks_L=int(licks_L.size),
        n_licks_R=int(licks_R.size),
        n_licks_total=int(licks_L.size + licks_R.size),
        n_L_trials=int(tones_L.size),
        n_R_trials=int(tones_R.size),
        n_L_trials_with_licks=int(n_L_with),
        n_R_trials_with_licks=int(n_R_with),
    )


def apply_session_filter(
    animal: str,
    dates: Sequence[datetime.date],
    resolver: PathResolver,
    filter_spec: SessionFilter,
    *,
    tone_window_ms: tuple[float, float] = DEFAULT_TONE_WINDOW_MS,
) -> SessionFilterResult:
    """Apply a filter spec to a list of (animal, dates).

    Sessions whose NPZ is missing are dropped with reason
    ``"npz_missing"``. Sessions whose stats fall below any threshold
    are dropped with the matching threshold reason. Pass-through
    filters (every field None) skip the per-session NPZ read entirely
    and short-circuit to keep all dates.
    """
    if filter_spec.is_pass_through():
        # Avoid the NPZ I/O when the caller has no filter active.
        return SessionFilterResult(
            kept_dates=list(dates),
            dropped=[],
            stats_by_date={},
            filter_spec=filter_spec,
        )

    kept: list[datetime.date] = []
    dropped: list[tuple[datetime.date, str]] = []
    stats_by_date: dict[datetime.date, SessionLickStats] = {}
    for d in dates:
        stats = compute_session_lick_stats(
            animal, d, resolver, tone_window_ms=tone_window_ms,
        )
        if stats is None:
            dropped.append((d, "npz_missing"))
            continue
        stats_by_date[d] = stats
        ok, reason = filter_spec.check(stats)
        if ok:
            kept.append(d)
        else:
            dropped.append((d, reason or "unknown"))
    return SessionFilterResult(
        kept_dates=kept, dropped=dropped,
        stats_by_date=stats_by_date, filter_spec=filter_spec,
    )


def load_filter_spec_from_defaults(
    defaults: dict[str, Any] | None = None,
    *,
    section: str = "default",
) -> SessionFilter:
    """Load a :class:`SessionFilter` from ``configs/defaults.yaml``.

    Reads ``cohort_filters.<section>`` (default: ``"default"``).
    Returns a pass-through filter if the section is absent.
    """
    if defaults is None:
        from stroke_orofacial.config_loader import load_defaults
        defaults = load_defaults()
    block = (defaults.get("cohort_filters", {}) or {}).get(section, {}) or {}
    return SessionFilter(
        min_licks_total=block.get("min_licks_total"),
        min_licks_per_side=block.get("min_licks_per_side"),
        min_trials_with_licks_per_side=block.get("min_trials_with_licks_per_side"),
    )


# Convenience alias for the pass-through filter.
PASS_THROUGH_FILTER: SessionFilter = SessionFilter()


__all__ = [
    "DEFAULT_TONE_WINDOW_MS",
    "PASS_THROUGH_FILTER",
    "SessionFilter",
    "SessionFilterResult",
    "SessionLickStats",
    "apply_session_filter",
    "compute_session_lick_stats",
    "load_filter_spec_from_defaults",
]
