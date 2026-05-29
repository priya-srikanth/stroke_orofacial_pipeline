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
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

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


# ============================================================================
# DLC tongue-kinematics filters (chore/dlc-session-and-trial-filtering,
# Addendum #1, 2026-05-29).
#
# SEPARATE from the v1 ``SessionFilter`` above. The v1 filter counts NPZ
# spout-licks (``compute_session_lick_stats`` → Phase 2 NPZ); these filters
# count DLC tongue-kinematics detected licks ("v7-kept" provenance:
# ``tongue.n_licks_family.n_licks`` from the per-trial tongue endpoints JSON).
# Different data source, hence a separate class hierarchy (single
# responsibility; zero regression risk for the shipped Q-lock 12/12a/12b
# consumers of v1). Validated against the sensitivity-probe thresholds
# (PR #157): SessionFilter min_trials_with_detected_lick=10 leaves no
# phenotype-pool cell at zero.
# ============================================================================

# Column-name contract for the DataFrames these filters consume / emit. Kept
# identical to the sensitivity-probe CSV schema (PR #157) so the same per-
# session / per-trial frames flow straight through without renaming.
DLC_SESSION_KEY_COLS: tuple[str, ...] = ("animal", "date", "side")
DLC_SESSION_N_TRIALS_TOTAL_COL = "n_trials_of_side"
DLC_SESSION_N_TRIALS_WITH_LICK_COL = "n_trials_with_detected_lick"
DLC_SESSION_N_KEPT_LICKS_COL = "n_kept_licks"
DLC_TRIAL_N_LICKS_COL = "n_licks_per_trial"


@dataclass(frozen=True)
class DlcSessionLickStats:
    """Per-(session, side) DLC v7-kept lick statistics.

    ``side`` is the *tone* side of the trial (``json["sides"][i]``), not the
    lick direction. ``n_kept_licks`` / ``n_trials_with_detected_lick`` are
    computed over the trials of that tone side using
    ``tongue.n_licks_family.n_licks`` (the per-trial count of detected tongue
    protrusions in the tone-aligned window).
    """

    animal: str
    date: datetime.date
    side: str
    n_trials_of_side: int
    n_trials_with_detected_lick: int
    n_kept_licks: int


@dataclass(frozen=True)
class DlcSessionFilterResult:
    """Output of :meth:`DlcSessionFilter.filter`.

    ``dropped`` carries ``((animal, date, side), reason)`` for every dropped
    session-side; ``kept_df`` is also returned alongside by ``filter``.
    """

    n_sessions_in: int
    n_sessions_kept: int
    dropped: list[tuple[tuple, str]] = field(default_factory=list)
    filter_spec: "DlcSessionFilter | None" = None

    def report(self) -> dict[str, Any]:
        """Counts dict for the SessionFilter manifest CSV."""
        return {
            "n_sessions_in": self.n_sessions_in,
            "n_sessions_kept": self.n_sessions_kept,
            "n_sessions_dropped": self.n_sessions_in - self.n_sessions_kept,
            "dropped": list(self.dropped),
        }


@dataclass(frozen=True)
class DlcSessionFilter:
    """Declarative DLC per-(session, side) threshold spec.

    All thresholds are minimums; ``None`` disables that criterion. ``combine``
    is consulted ONLY when both criteria are non-null (a single active
    criterion needs no combine). When every threshold is ``None`` the filter
    is pass-through.

    Operates on a per-(animal, date, side) DataFrame whose columns include
    :data:`DLC_SESSION_N_TRIALS_WITH_LICK_COL` and
    :data:`DLC_SESSION_N_KEPT_LICKS_COL` (the sensitivity-probe schema).
    """

    min_trials_with_detected_lick: int | None = None
    min_kept_licks: int | None = None
    combine: Literal["and", "or"] = "and"
    lick_window: str = "tone_aligned"
    lick_provenance: str = "v7_kept"
    apply_to_bodyparts: tuple[str, ...] = ("tongue",)

    def __post_init__(self) -> None:
        if self.combine not in ("and", "or"):
            raise ValueError(
                f"combine must be 'and' or 'or', got {self.combine!r}"
            )

    def is_pass_through(self) -> bool:
        return (
            self.min_trials_with_detected_lick is None
            and self.min_kept_licks is None
        )

    def check(self, stats: DlcSessionLickStats) -> tuple[bool, str | None]:
        """Return ``(kept, drop_reason)`` for one session-side.

        ``drop_reason`` is ``None`` when kept. Combine semantics: with both
        criteria active, AND requires both met / OR requires either met.
        """
        results: list[tuple[bool, str]] = []
        if self.min_trials_with_detected_lick is not None:
            ok = (
                stats.n_trials_with_detected_lick
                >= self.min_trials_with_detected_lick
            )
            results.append((
                ok,
                f"min_trials_with_detected_lick="
                f"{self.min_trials_with_detected_lick} not met "
                f"(n={stats.n_trials_with_detected_lick})",
            ))
        if self.min_kept_licks is not None:
            ok = stats.n_kept_licks >= self.min_kept_licks
            results.append((
                ok,
                f"min_kept_licks={self.min_kept_licks} not met "
                f"(n={stats.n_kept_licks})",
            ))
        if not results:
            return True, None
        passes = [ok for ok, _ in results]
        kept = any(passes) if self.combine == "or" else all(passes)
        if kept:
            return True, None
        failed = "; ".join(reason for ok, reason in results if not ok)
        prefix = "[OR] all criteria failed: " if self.combine == "or" else ""
        return False, prefix + failed

    def filter(
        self, df_sessions: pd.DataFrame,
    ) -> tuple[pd.DataFrame, DlcSessionFilterResult]:
        """Drop session-side rows failing the spec.

        Returns ``(kept_df, result)``. Pass-through specs short-circuit and
        return the frame unchanged. ``check`` is applied row-wise so it is the
        single source of truth for keep/drop + reasons.
        """
        n_in = len(df_sessions)
        if self.is_pass_through():
            return (
                df_sessions.copy(),
                DlcSessionFilterResult(
                    n_sessions_in=n_in, n_sessions_kept=n_in,
                    dropped=[], filter_spec=self,
                ),
            )
        keep_flags: list[bool] = []
        dropped: list[tuple[tuple, str]] = []
        for _, row in df_sessions.iterrows():
            stats = self._row_to_stats(row)
            kept, reason = self.check(stats)
            keep_flags.append(kept)
            if not kept:
                dropped.append((
                    (stats.animal, stats.date, stats.side),
                    reason or "unknown",
                ))
        mask = pd.Series(keep_flags, index=df_sessions.index)
        kept_df = df_sessions[mask].copy()
        return kept_df, DlcSessionFilterResult(
            n_sessions_in=n_in, n_sessions_kept=int(mask.sum()),
            dropped=dropped, filter_spec=self,
        )

    @staticmethod
    def _row_to_stats(row: "pd.Series") -> DlcSessionLickStats:
        n_total = row.get(DLC_SESSION_N_TRIALS_TOTAL_COL, None)
        return DlcSessionLickStats(
            animal=row["animal"],
            date=row["date"],
            side=row["side"],
            n_trials_of_side=(
                int(n_total) if n_total is not None and not pd.isna(n_total)
                else int(row[DLC_SESSION_N_TRIALS_WITH_LICK_COL])
            ),
            n_trials_with_detected_lick=int(
                row[DLC_SESSION_N_TRIALS_WITH_LICK_COL]
            ),
            n_kept_licks=int(row[DLC_SESSION_N_KEPT_LICKS_COL]),
        )


@dataclass(frozen=True)
class DlcTrialFilterResult:
    """Output of :meth:`DlcTrialFilter.filter`."""

    n_trials_in: int
    n_trials_kept: int
    min_licks_per_trial: int | None
    metric_family: str | None = None

    def report(self) -> dict[str, Any]:
        """Counts dict for the TrialFilter manifest CSV."""
        return {
            "metric_family": self.metric_family,
            "min_licks_per_trial": self.min_licks_per_trial,
            "n_trials_in": self.n_trials_in,
            "n_trials_kept": self.n_trials_kept,
            "n_trials_dropped": self.n_trials_in - self.n_trials_kept,
        }


@dataclass(frozen=True)
class DlcTrialFilter:
    """Per-trial DLC v7-kept lick-count threshold (one metric family).

    ``min_licks_per_trial`` is the per-trial minimum of detected tongue licks
    (``n_licks_family.n_licks``). ``None`` = pass-through. ``metric_family`` is
    an informational label carried into the manifest (e.g.
    ``"first_5_lick_velocity"``).
    """

    min_licks_per_trial: int | None = None
    metric_family: str | None = None

    def is_pass_through(self) -> bool:
        return self.min_licks_per_trial is None

    def check(self, n_licks_per_trial: int) -> tuple[bool, str | None]:
        if self.min_licks_per_trial is None:
            return True, None
        if n_licks_per_trial >= self.min_licks_per_trial:
            return True, None
        return False, (
            f"min_licks_per_trial={self.min_licks_per_trial} not met "
            f"(n={n_licks_per_trial})"
        )

    def filter(
        self, df_trials: pd.DataFrame,
    ) -> tuple[pd.DataFrame, DlcTrialFilterResult]:
        """Drop per-trial rows below the threshold. Returns ``(kept_df, result)``."""
        n_in = len(df_trials)
        if self.is_pass_through():
            return (
                df_trials.copy(),
                DlcTrialFilterResult(
                    n_trials_in=n_in, n_trials_kept=n_in,
                    min_licks_per_trial=None, metric_family=self.metric_family,
                ),
            )
        mask = df_trials[DLC_TRIAL_N_LICKS_COL] >= self.min_licks_per_trial
        kept_df = df_trials[mask].copy()
        return kept_df, DlcTrialFilterResult(
            n_trials_in=n_in, n_trials_kept=int(mask.sum()),
            min_licks_per_trial=self.min_licks_per_trial,
            metric_family=self.metric_family,
        )


def apply_dlc_trial_filter_with_session_rollup(
    df_trials: pd.DataFrame,
    trial_filter: DlcTrialFilter,
    *,
    session_key_cols: Sequence[str] = DLC_SESSION_KEY_COLS,
) -> tuple[pd.DataFrame, list[tuple[tuple, str]], DlcTrialFilterResult]:
    """Apply a :class:`DlcTrialFilter`, then flag sessions emptied to 0 trials.

    A (session, side) that retains 0 trials after the trial filter cannot form
    a per-session statistic, so it is "not kept" — rolled up here as a
    ``(key_tuple, "trial_filter_emptied_session")`` entry that the caller folds
    into the SessionFilter manifest's exclusion count (locked interpretation,
    chore kickoff §Locked design decisions).

    Returns ``(kept_trials_df, emptied_sessions, trial_result)``.
    """
    key_cols = list(session_key_cols)
    kept_df, trial_result = trial_filter.filter(df_trials)

    def _keys(frame: pd.DataFrame) -> set[tuple]:
        if frame.empty:
            return set()
        return {tuple(r) for r in frame[key_cols].itertuples(index=False, name=None)}

    emptied = sorted(_keys(df_trials) - _keys(kept_df))
    emptied_sessions = [(k, "trial_filter_emptied_session") for k in emptied]
    return kept_df, emptied_sessions, trial_result


# --- v7-kept stats helpers (read the per-trial tongue endpoints JSON) --------


def compute_dlc_session_lick_stats(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    sides: Sequence[str] = ("L", "R"),
) -> list[DlcSessionLickStats] | None:
    """Per-(side) DLC v7-kept lick stats for one session.

    Reads ``tongue.n_licks_family.n_licks`` (v7-kept provenance) from the
    per-trial tongue endpoints JSON and aggregates per tone side. Returns
    ``None`` if the JSON is missing (caller treats as missing-session skip).
    """
    path = resolver.tongue_pertrial_endpoints_json(animal, date)
    if not Path(path).exists():
        return None
    with open(path) as fh:
        payload = json.load(fh)
    trial_sides = payload["sides"]
    n_licks = payload["tongue"]["n_licks_family"]["n_licks"]
    out: list[DlcSessionLickStats] = []
    for side in sides:
        idxs = [i for i, s in enumerate(trial_sides) if s == side]
        kept = sum(int(n_licks[i]) for i in idxs)
        with_lick = sum(1 for i in idxs if int(n_licks[i]) >= 1)
        out.append(DlcSessionLickStats(
            animal=animal, date=date, side=side,
            n_trials_of_side=len(idxs),
            n_trials_with_detected_lick=with_lick,
            n_kept_licks=kept,
        ))
    return out


def build_dlc_pertrial_lick_frame(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
) -> pd.DataFrame | None:
    """Per-trial v7-kept lick counts for one session as a DataFrame.

    Columns: ``animal, date, side, trial_index,`` :data:`DLC_TRIAL_N_LICKS_COL`.
    Returns ``None`` if the per-trial tongue JSON is missing.
    """
    path = resolver.tongue_pertrial_endpoints_json(animal, date)
    if not Path(path).exists():
        return None
    with open(path) as fh:
        payload = json.load(fh)
    trial_sides = payload["sides"]
    trial_indices = payload["trial_indices"]
    n_licks = payload["tongue"]["n_licks_family"]["n_licks"]
    return pd.DataFrame({
        "animal": animal,
        "date": date,
        "side": list(trial_sides),
        "trial_index": [int(t) for t in trial_indices],
        DLC_TRIAL_N_LICKS_COL: [int(n) for n in n_licks],
    })


def load_dlc_filter_spec_from_defaults(
    defaults: dict[str, Any] | None = None,
    *,
    section: str = "dlc_tongue_trajectory_metrics",
) -> DlcSessionFilter:
    """Load a :class:`DlcSessionFilter` from ``configs/defaults.yaml``.

    Reads ``stats.dlc_session_filter.<section>``. Returns a pass-through filter
    if the block is absent, so this is safe to call before Stage 3 lands the
    config keys. The final config schema is locked in Stage 3.
    """
    if defaults is None:
        from stroke_orofacial.config_loader import load_defaults
        defaults = load_defaults()
    block = (
        ((defaults.get("stats", {}) or {}).get("dlc_session_filter", {}) or {})
        .get(section, {}) or {}
    )
    return DlcSessionFilter(
        min_trials_with_detected_lick=block.get("min_trials_with_detected_lick"),
        min_kept_licks=block.get("min_kept_licks"),
        combine=block.get("combine", "and"),
        lick_window=block.get("lick_window", "tone_aligned"),
        lick_provenance=block.get("lick_provenance", "v7_kept"),
        apply_to_bodyparts=tuple(block.get("apply_to_bodyparts", ("tongue",))),
    )


def resolve_dlc_trial_filter(
    metric_family: str,
    defaults: dict[str, Any] | None = None,
    *,
    section: str = "dlc_tongue_trajectory_metrics",
) -> DlcTrialFilter:
    """Resolve the per-metric-family :class:`DlcTrialFilter` from defaults.

    Reads ``stats.dlc_trial_filter.<section>`` with the locked
    ``defaults`` / ``overrides`` shape: the family override's
    ``min_licks_per_trial`` wins over the block default. Returns a pass-through
    filter when neither is present (safe before Stage 3 config lands).
    """
    if defaults is None:
        from stroke_orofacial.config_loader import load_defaults
        defaults = load_defaults()
    block = (
        ((defaults.get("stats", {}) or {}).get("dlc_trial_filter", {}) or {})
        .get(section, {}) or {}
    )
    base = (block.get("defaults", {}) or {}).get("min_licks_per_trial")
    override = (
        (block.get("overrides", {}) or {}).get(metric_family, {}) or {}
    ).get("min_licks_per_trial")
    return DlcTrialFilter(
        min_licks_per_trial=override if override is not None else base,
        metric_family=metric_family,
    )


# Convenience pass-through aliases for the DLC filters.
DLC_PASS_THROUGH_SESSION_FILTER: DlcSessionFilter = DlcSessionFilter()
DLC_PASS_THROUGH_TRIAL_FILTER: DlcTrialFilter = DlcTrialFilter()


__all__ = [
    "DEFAULT_TONE_WINDOW_MS",
    "DLC_PASS_THROUGH_SESSION_FILTER",
    "DLC_PASS_THROUGH_TRIAL_FILTER",
    "DLC_SESSION_KEY_COLS",
    "DLC_SESSION_N_KEPT_LICKS_COL",
    "DLC_SESSION_N_TRIALS_TOTAL_COL",
    "DLC_SESSION_N_TRIALS_WITH_LICK_COL",
    "DLC_TRIAL_N_LICKS_COL",
    "PASS_THROUGH_FILTER",
    "DlcSessionFilter",
    "DlcSessionFilterResult",
    "DlcSessionLickStats",
    "DlcTrialFilter",
    "DlcTrialFilterResult",
    "SessionFilter",
    "SessionFilterResult",
    "SessionLickStats",
    "apply_dlc_trial_filter_with_session_rollup",
    "apply_session_filter",
    "build_dlc_pertrial_lick_frame",
    "compute_dlc_session_lick_stats",
    "compute_session_lick_stats",
    "load_dlc_filter_spec_from_defaults",
    "load_filter_spec_from_defaults",
    "resolve_dlc_trial_filter",
]
