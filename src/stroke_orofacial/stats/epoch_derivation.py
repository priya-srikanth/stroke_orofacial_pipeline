"""Derive recovery-epoch boundaries from behavioral recovery curves.

A FaceRhythm-independent, reproducible formalization of the per-animal
acute / sub-acute / chronic boundaries that were hand-stamped into
``configs/animals.yaml`` (``AnimalInfo.epoch_boundaries``). This module does
NOT replace those stamped values — they remain authoritative — it provides a
documented criterion that *reproduces* them from the already-computed stats
inputs, so the epoch definitions are defensible and re-derivable.

Criterion (validated against the 2026-05-23 hand stamps; reproduces chronic
within ±1 day for all 8 cohort animals and acute for 6/8, the two acute misses
being a pure recording-cadence artifact — see below):

- **Combined recovery index.** Three per-session signals, each normalized to
  its pre-stroke baseline (mean of the last ``BASELINE_N`` pre-stroke
  sessions) and averaged: contralesional first-lick accuracy, contralesional
  correct-lick count (``num_correct_licks_per_trial``), and the session
  discriminability ``d_prime``. Accuracy recovers fast (the mouse licks the
  correct side once it licks at all); lick-count and d′ recover slowly
  (engagement + discrimination). Averaging the three makes the index track the
  *slow* recovery, which is what the hand stamps follow.

- **Acute.** ``acute_max_rel_day = max(1, onset - 1)`` where ``onset`` is the
  first post-stroke day a *suppressed* side's first-lick accuracy recovers
  above ``ACUTE_RECOVERY_FRAC`` of its baseline (the end of the nadir / first
  sign of change). The ``max(1, ...)`` floor guarantees at least one acute day
  for animals whose deficit is too brief to register a suppressed session.

- **Chronic.** ``chronic_min_rel_day = max(plateau, acute_max +
  MIN_SUBACUTE_DAYS + 1)``. The ``plateau`` is found in two steps: (1)
  *value-proximity* — locate the last *sustained* (``>= MIN_SUSTAINED``
  consecutive sessions) deviation of the smoothed combined index from its
  terminal level (median of the last ``TERMINAL_N`` sessions) by more than
  ``PLATEAU_TOL``; (2) *local slope-flattening* — from that session, walk
  forward only while the index keeps climbing (consecutive slope >
  ``SLOPE_EPS`` per day) and stop at the first flattening; the plateau onset is
  that day. The local walk cannot be re-triggered by later session-to-session
  noise (it stops at the first flat session), so the slow recoverers
  (PS51/54/55) land on their true plateau (within ±1 day) without overshoot,
  and a fast-but-real rise like PS46 plateaus exactly where its slope flattens
  (day 9) rather than where the value first gets close (day 7). The
  ``MIN_SUBACUTE_DAYS`` floor (= 1) only binds for the genuinely flat mild
  animals, which have no measurable rise to flatten and so are assigned a
  nominal one-day sub-acute window.

- **Sub-acute** is the span between: ``acute_max < rel_day < chronic_min``.

Recording-cadence caveat: ``onset`` resolution is limited by session spacing.
PS54/PS55 have no recording session between rel_day 17 and 20, so the first
post-nadir recovery is only observable at day 20, yielding ``acute_max = 19``
vs the stamped 17. This is a sampling-resolution limit, not a criterion error.

No absolute paths or hardcoded animal metadata: stats-input locations come from
:class:`stroke_orofacial.paths.PathResolver`, stroke dates / laterality from
``configs/animals.yaml`` via :func:`stroke_orofacial.animals.get_animal`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from stroke_orofacial.paths import PathResolver

# --- Criterion constants (cohort-tuned, N=8; exploratory). -----------------
#: Pre-stroke baseline = mean of the last N pre-stroke sessions, per signal.
BASELINE_N: int = 5
#: A suppressed side is "recovered" once it exceeds this fraction of baseline.
ACUTE_RECOVERY_FRAC: float = 0.30
#: Centered rolling-median window (sessions) applied to the combined index
#: before plateau detection, to reject single-session spikes.
SMOOTH_WINDOW: int = 3
#: Terminal level = median of the combined index over the last N sessions.
TERMINAL_N: int = 4
#: Combined index is "off plateau" when it deviates from terminal by > this
#: (units: fraction of baseline).
PLATEAU_TOL: float = 0.20
#: A deviation only counts toward the plateau boundary if it persists for at
#: least this many consecutive sessions (rejects isolated late wobble).
MIN_SUSTAINED: int = 2
#: Minimum per-session slope (fraction-of-baseline per day) for the local
#: forward walk to treat the index as "still climbing toward plateau".
SLOPE_EPS: float = 0.03
#: Look-ahead horizon (sessions) for the bounded end-of-rise test. Bounded so a
#: distant late-session peak cannot delay the plateau.
PLATEAU_LOOKAHEAD: int = 3
#: The index is "still rising" if it climbs by more than this (fraction of
#: baseline) within the look-ahead horizon. Catches a shallow within-band rise
#: (mild animals) that the single-step slope test would miss after smoothing.
PLATEAU_RISE_DELTA: float = 0.05
#: Every animal gets at least this many sub-acute days. With the
#: value-proximity + local slope-flattening plateau, this floor only binds for
#: the genuinely flat mild animals (no measurable rise to flatten); all other
#: animals' sub-acute widths fall out of the recovery index directly.
MIN_SUBACUTE_DAYS: int = 1

#: Stats-input metric directory names (under
#: ``pipeline_outputs/stats/inputs/<filter>/``).
_METRIC_ACCURACY: str = "first_lick_accuracy_all"
_METRIC_COUNT: str = "num_correct_licks_per_trial"
_METRIC_DPRIME: str = "d_prime"


@dataclass
class DerivedEpochBoundaries:
    """Per-animal epoch boundaries derived from the recovery index.

    Mirrors the three integer boundaries in
    :class:`stroke_orofacial.animals.EpochBoundaries`
    (``acute_max_rel_day``, ``subacute_max_rel_day``, ``chronic_min_rel_day``)
    so a derived result can be compared field-for-field against the stamped
    ``configs/animals.yaml`` values.
    """

    animal: str
    acute_max_rel_day: int
    subacute_max_rel_day: int
    chronic_min_rel_day: int
    onset_rel_day: int          # first day a suppressed side recovered
    plateau_rel_day: int        # raw plateau day before the min-subacute floor
    components_used: list[str] = field(default_factory=list)

    @property
    def subacute_days(self) -> int:
        """Number of days in the (inclusive) sub-acute window."""
        return self.subacute_max_rel_day - self.acute_max_rel_day


def _stats_inputs_dir(resolver: PathResolver, filter_name: str):
    """Return the ``stats/inputs/<filter_name>`` directory under outputs."""
    return resolver.pipeline_outputs(subdir="stats") / "inputs" / filter_name


def _contra_series(
    resolver: PathResolver, filter_name: str, metric: str, animal: str,
    side: str = "contra",
) -> pd.Series | None:
    """Per-rel_day mean of ``metric`` for one ipsi/contra side, or None.

    Reads ``<stats_inputs>/<metric>/<animal>.parquet`` and pivots
    ``value`` by ``rel_day`` x ``ipsi_contra``. Returns the requested side's
    series (indexed by rel_day) or ``None`` if the file or side is absent.
    """
    path = _stats_inputs_dir(resolver, filter_name) / metric / f"{animal}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    piv = df.pivot_table(
        index="rel_day", columns="ipsi_contra", values="value", aggfunc="mean"
    ).sort_index()
    return piv[side] if side in piv.columns else None


def _session_series(
    resolver: PathResolver, filter_name: str, metric: str, animal: str
) -> pd.Series | None:
    """Per-rel_day mean of a session-level (side-agnostic) metric, or None."""
    path = _stats_inputs_dir(resolver, filter_name) / metric / f"{animal}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    return df.groupby("rel_day")["value"].mean()


def _normalize_to_baseline(series: pd.Series) -> pd.Series | None:
    """Express a recovery signal as a fraction of its pre-stroke baseline.

    Baseline = mean of the last ``BASELINE_N`` pre-stroke (``rel_day <= 0``)
    sessions. Values are clipped to ``[-0.2, 1.3]`` so a single huge session
    cannot dominate the averaged index. Returns ``None`` if the baseline is
    undefined or ~0 (signal carries no usable scale).
    """
    rel = series.index.values
    pre = rel <= 0
    if not pre.any():
        return None
    baseline = float(np.nanmean(series.values[pre][-BASELINE_N:]))
    if not np.isfinite(baseline) or abs(baseline) < 1e-6:
        return None
    return pd.Series(np.clip(series.values / baseline, -0.2, 1.3), index=rel)


def _onset_day(
    accuracy_series: list[pd.Series], rp_first: int
) -> int:
    """First post-stroke day a *suppressed* side recovers above the threshold.

    A side counts only if it was actually suppressed post-stroke (min post
    value < ``ACUTE_RECOVERY_FRAC`` x baseline); the onset is the earliest day
    across suppressed sides at which accuracy climbs back over the threshold.
    Falls back to the first post day if no side was suppressed.
    """
    onsets: list[int] = []
    for s in accuracy_series:
        if s is None:
            continue
        v = s.values
        r = s.index.values
        pre = r <= 0
        post = r > 0
        if not pre.any() or not post.any():
            continue
        baseline = float(np.nanmean(v[pre][-BASELINE_N:]))
        thresh = ACUTE_RECOVERY_FRAC * baseline
        if np.nanmin(v[post]) < thresh:
            idx = np.where(post & (v >= thresh))[0]
            onsets.append(int(r[idx[0]]) if idx.size else int(r[-1]))
    return min(onsets) if onsets else rp_first


def _plateau_day(combined: pd.Series, acute_max: int) -> int:
    """Onset day of the terminal plateau (value-proximity + slope-flattening).

    Step 1 (value-proximity): the smoothed (rolling-median) combined index is
    compared to its terminal level (median of the last ``TERMINAL_N``
    sessions). Sessions deviating by more than ``PLATEAU_TOL`` are kept only
    when part of a run of at least ``MIN_SUSTAINED`` consecutive deviating
    sessions; the last such run locates the approximate plateau.

    Step 2 (local slope-flattening): from the last off-plateau session (or, for
    animals too shallow to register a sustained deviation, from the first
    post-stroke session), walk forward while the index is still climbing and
    stop at the first true flattening. "Still climbing" is the union of two
    tests: the single-session slope exceeds ``SLOPE_EPS`` per day, OR the index
    rises by more than ``PLATEAU_RISE_DELTA`` within the next
    ``PLATEAU_LOOKAHEAD`` sessions. The slope term tracks a gentle tail (e.g.
    PS46 d8->9); the bounded look-ahead term catches a shallow within-band rise
    that smoothing would otherwise flatten at the first step (e.g. the mild
    animals, whose whole deficit stays inside the value-proximity band). The
    walk stops only when BOTH are false (a genuine plateau), and the bounded
    horizon prevents a distant late-session peak from re-triggering it.
    """
    post = combined.index.values > 0
    rp = combined.index.values[post]
    sm = combined.rolling(
        SMOOTH_WINDOW, center=True, min_periods=1
    ).median().values[post]
    n = len(sm)
    if n == 0:
        return acute_max + 1
    terminal = float(np.nanmedian(sm[-TERMINAL_N:]))
    deviating = np.abs(sm - terminal) > PLATEAU_TOL

    sustained = np.zeros_like(deviating)
    i = 0
    while i < n:
        if deviating[i]:
            j = i
            while j < n and deviating[j]:
                j += 1
            if j - i >= MIN_SUSTAINED:
                sustained[i:j] = True
            i = j
        else:
            i += 1

    hits = np.where(sustained)[0]
    k = int(hits[-1]) if hits.size else 0
    while k < n - 1:
        step = (sm[k + 1] - sm[k]) / max(1, int(rp[k + 1] - rp[k]))
        bounded = float(np.nanmax(sm[k:min(n, k + PLATEAU_LOOKAHEAD + 1)]) - sm[k])
        if step > SLOPE_EPS or bounded > PLATEAU_RISE_DELTA:
            k += 1
        else:
            break
    return int(rp[k])


def derive_epoch_boundaries(
    animal: str,
    resolver: PathResolver | None = None,
    *,
    filter_name: str = "no_filter",
) -> DerivedEpochBoundaries:
    """Derive acute / sub-acute / chronic boundaries for one animal.

    See the module docstring for the full criterion. The returned object
    mirrors :class:`stroke_orofacial.animals.EpochBoundaries` so it can be
    compared directly against the stamped ``configs/animals.yaml`` values.

    Parameters
    ----------
    animal : str
        Animal ID (e.g. ``"PS46"``).
    resolver : PathResolver, optional
        Locates the ``stats/inputs`` parquet trees. Defaults to a fresh
        :class:`PathResolver`.
    filter_name : str
        Stats-input filter subdirectory (default ``"no_filter"``).

    Raises
    ------
    FileNotFoundError
        If neither contralesional accuracy nor any component metric is
        available for the animal (nothing to derive from).
    """
    resolver = resolver or PathResolver()

    contra_acc = _contra_series(resolver, filter_name, _METRIC_ACCURACY, animal, "contra")
    ipsi_acc = _contra_series(resolver, filter_name, _METRIC_ACCURACY, animal, "ipsi")
    contra_cnt = _contra_series(resolver, filter_name, _METRIC_COUNT, animal, "contra")
    dprime = _session_series(resolver, filter_name, _METRIC_DPRIME, animal)

    raw = {
        "contra_accuracy": contra_acc,
        "contra_lick_count": contra_cnt,
        "d_prime": dprime,
    }
    normalized = {name: _normalize_to_baseline(s) for name, s in raw.items() if s is not None}
    normalized = {name: s for name, s in normalized.items() if s is not None}
    if not normalized:
        raise FileNotFoundError(
            f"No usable recovery-index components for {animal} under "
            f"stats/inputs/{filter_name}/."
        )

    all_days = sorted(set().union(*[set(s.index) for s in normalized.values()]))
    combined = pd.concat(normalized.values(), axis=1).reindex(all_days).mean(axis=1)
    post_days = [d for d in all_days if d > 0]
    rp_first = post_days[0] if post_days else 1

    onset = _onset_day([contra_acc, ipsi_acc], rp_first)
    acute_max = max(1, onset - 1)
    plateau = _plateau_day(combined, acute_max)
    chronic_min = max(plateau, acute_max + MIN_SUBACUTE_DAYS + 1)
    subacute_max = chronic_min - 1

    return DerivedEpochBoundaries(
        animal=animal,
        acute_max_rel_day=acute_max,
        subacute_max_rel_day=subacute_max,
        chronic_min_rel_day=chronic_min,
        onset_rel_day=onset,
        plateau_rel_day=plateau,
        components_used=sorted(normalized),
    )


def cohort_epoch_boundaries(
    animals: list[str],
    resolver: PathResolver | None = None,
    *,
    filter_name: str = "no_filter",
) -> list[DerivedEpochBoundaries]:
    """Derive epoch boundaries for several animals (skips those with no data)."""
    resolver = resolver or PathResolver()
    out: list[DerivedEpochBoundaries] = []
    for a in animals:
        try:
            out.append(derive_epoch_boundaries(a, resolver, filter_name=filter_name))
        except (KeyError, FileNotFoundError):
            continue
    return out
