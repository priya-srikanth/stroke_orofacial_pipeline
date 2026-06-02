"""Phase 9.1 Q-lock 13b — phase-aligned tongue endpoint aggregators.

Two aggregator passes consumed by the Q-lock 13b stats + figure pipeline
(Addendum #2 D4 lock: stats-grain aggregators land here, NOT in
``figures/_io.py`` which is figure-private + mean-based).

Stage 2 — per-session aggregator (this module):
- :func:`load_session_phase_aligned_endpoints_long` reads ONE per-trial
  endpoints JSON and emits long-form rows (one per finite endpoint value
  per (trial, side)). Columns:
  ``animal, date, trial_index, side, endpoint, value``.
- :func:`load_cohort_phase_aligned_endpoints_long` concatenates over a
  cohort × enumerated session dates.
- :func:`aggregate_per_session_median_iqr` collapses to one row per
  (animal, date, side, endpoint) with ``median, q25, q75, iqr,
  n_trials``.

Stage 3 — phenotype-pooled aggregator:
- :func:`attach_phenotype_and_epoch` joins ``recovery_phenotype`` +
  ``epoch_label`` onto the per-session rows. ``epoch_label`` per
  ``stroke_orofacial.stats.recovery_epochs.assign_epoch_label`` (Addendum
  #2 D3 lock: epochs are pre/acute/sub_acute/chronic, NOT rel_day_bin).
- :func:`aggregate_phenotype_pooled_median_iqr` pools per-session
  medians across animals within (phenotype, epoch, side, endpoint),
  emitting cohort-level ``median, q25, q75, iqr, n_sessions, n_animals``.

NaN-aware throughout. n=1 phenotype tiers (moderate = PS46, mod-severe
= PS51) participate in pooling and produce valid summaries; downstream
Wilcoxon will surface ``status="insufficient_data"`` for those tiers
with NaN p-values that the BH-FDR correction handles correctly.
"""
from __future__ import annotations

import datetime
import json
import re
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

from stroke_orofacial.animals import AnimalInfo
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label


# Endpoint slug → human-readable label. Single source of truth for the
# three Q-lock 13b scalar endpoints (kickoff endpoint table +
# Addendum #1 Q6 refinement). Downstream figures consume these slugs.
PHASE_ALIGNED_ENDPOINT_SLUGS: tuple[str, ...] = (
    "peak_angle_deg",
    "signed_angle_at_max_abs_phase_0_075_deg",
    "signed_x_at_max_abs_phase_0_075_px",
)


# Q-lock 13 — per-phase-bin trajectory signals carried on the centered
# phase-row substrate (``build_first_lick_centered_phase_rows`` output).
# Distinct from the scalar ``PHASE_ALIGNED_ENDPOINT_SLUGS`` consumed by
# Q-lock 13b: those are session × side × endpoint scalars from the
# per-trial endpoints JSON; these are trial × phase_bin signal values
# from the in-memory bundle.
#
# Q-lock 13c Stage 2 (2026-05-29) appended ``y_centered`` — protrusion /
# amplitude axis. The downstream baseline / aggregator / trajectory-
# scalar / cluster-perm / LMM / bootstrap helpers are all parametric on
# this tuple, so the single tuple extension propagates the y signal
# through every consumer that takes ``signals=TRAJECTORY_SIGNALS``.
TRAJECTORY_SIGNALS: tuple[str, ...] = (
    "angle_deg",
    "x_centered",
    "y_centered",
)


# ---------------------------------------------------------------------------
# JSON readers
# ---------------------------------------------------------------------------


_BUNDLE_CACHE: dict = {}


def _cached_tongue_bundle(
    animal: str, date_iso: str, resolver_id: int, resolver: PathResolver,
):
    """Memoize the per-session tongue visual bundle so the all-licks endpoint
    loader doesn't rebuild it on the filtered + nofilter passes (I, 2026-06-01).
    Keyed by (animal, date, resolver identity)."""
    key = (animal, date_iso, resolver_id)
    bundle = _BUNDLE_CACHE.get(key)
    if bundle is None:
        from stroke_orofacial.dlc_kinematics.tongue_pertrial import (
            build_tongue_visual_bundle_by_animal_date,
        )
        bundle = build_tongue_visual_bundle_by_animal_date(
            animal=animal, date=datetime.date.fromisoformat(date_iso),
            resolver=resolver,
        )
        _BUNDLE_CACHE[key] = bundle
    return bundle


def _compute_all_licks_endpoints_long(
    animal: str, date: datetime.date, resolver: PathResolver,
) -> pd.DataFrame:
    """On-the-fly per-LICK all-licks phase-aligned endpoints, long-form (I).

    Builds the tongue visual bundle and computes the 3 endpoints per
    individual lick (``compute_phase_aligned_endpoints_per_trial`` with
    ``lick_set="all_multi"``), melted to the same long-form schema the JSON
    loader returns. Each lick is its own row (pooled downstream as n=licks).
    """
    from stroke_orofacial.dlc_kinematics.tongue_phase_aligned_endpoints import (
        compute_phase_aligned_endpoints_per_trial,
    )
    try:
        bundle = _cached_tongue_bundle(animal, date.isoformat(), id(resolver), resolver)
    except Exception:
        return _empty_long_df()
    df = compute_phase_aligned_endpoints_per_trial(bundle, lick_set="all_multi")
    if df.empty:
        return _empty_long_df()
    rows: list[dict[str, object]] = []
    for _, r in df.iterrows():
        for slug in PHASE_ALIGNED_ENDPOINT_SLUGS:
            v = r.get(slug)
            if v is None or not np.isfinite(float(v)):
                continue
            rows.append({
                "animal": animal, "date": date,
                "trial_index": int(r["trial_index"]), "side": str(r["side"]),
                "endpoint": slug, "value": float(v),
            })
    return pd.DataFrame(rows) if rows else _empty_long_df()


def load_session_phase_aligned_endpoints_long(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
    *,
    lick_set: str = "first_lick",
) -> pd.DataFrame:
    """Load one per-trial endpoints JSON; return long-form rows.

    ``lick_set="all_multi"`` (I) bypasses the JSON and computes the per-LICK
    all-licks endpoints on the fly (the JSON only carries the shipped
    first-lick per-trial endpoints).

    Reads ``dlc_kinematics/per_trial/tongue/<animal>/<YYYYMMDD>.json`` and
    transforms the ``tongue.phase_aligned_endpoints`` block (three NaN-
    fillable parallel lists) into long-form rows.

    Parameters
    ----------
    animal : str
    date : datetime.date
    resolver : PathResolver

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``date`` (datetime.date), ``trial_index``,
        ``side``, ``endpoint`` (slug), ``value`` (float). One row per
        (trial_index, side, endpoint) with finite ``value``; NaN-value
        rows are dropped (caller can re-emit empty bookkeeping via
        :func:`aggregate_per_session_median_iqr` which counts the input
        rows). Empty DataFrame if the JSON or the
        ``phase_aligned_endpoints`` block is missing.
    """
    if lick_set == "all_multi":
        return _compute_all_licks_endpoints_long(animal, date, resolver)
    path = resolver.tongue_pertrial_endpoints_json(animal=animal, date=date)
    if not path.exists():
        return _empty_long_df()
    with open(path) as f:
        payload = json.load(f)
    pae = (
        payload.get("tongue", {}).get("phase_aligned_endpoints")
    )
    if not pae:
        return _empty_long_df()
    trial_indices = payload.get("trial_indices", [])
    sides = payload.get("sides", [])
    n = len(trial_indices)
    if n == 0 or len(sides) != n:
        return _empty_long_df()

    rows: list[dict[str, object]] = []
    for slug in PHASE_ALIGNED_ENDPOINT_SLUGS:
        vals = pae.get(slug, [])
        if len(vals) != n:
            continue
        for ti, side, v in zip(trial_indices, sides, vals):
            if v is None:
                continue
            try:
                v_f = float(v)
            except (TypeError, ValueError):
                continue
            if not np.isfinite(v_f):
                continue
            rows.append({
                "animal": str(animal),
                "date": date,
                "trial_index": int(ti),
                "side": str(side),
                "endpoint": slug,
                "value": v_f,
            })
    if not rows:
        return _empty_long_df()
    return pd.DataFrame(rows, columns=[
        "animal", "date", "trial_index", "side", "endpoint", "value",
    ])


def enumerate_session_dates(
    animal: str, resolver: PathResolver,
) -> list[datetime.date]:
    """List session dates with on-disk per-trial endpoints JSONs for an animal.

    Mirrors :func:`stroke_orofacial.dlc_kinematics.tongue_angle_cohort._enumerate_session_dates`
    but re-exposed at the stats-package level so this module doesn't need
    to reach into dlc_kinematics internals.
    """
    endpoints_dir = resolver.tongue_pertrial_endpoints_dir(animal)
    if not endpoints_dir.exists():
        return []
    dates: list[datetime.date] = []
    for p in sorted(endpoints_dir.glob("*.json")):
        m = re.match(r"(\d{8})\.json$", p.name)
        if m is None:
            continue
        dates.append(
            datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        )
    return dates


def load_cohort_phase_aligned_endpoints_long(
    animals: Iterable[str],
    resolver: PathResolver,
) -> pd.DataFrame:
    """Concatenate :func:`load_session_phase_aligned_endpoints_long` over
    a cohort × every on-disk session date.

    Sessions with no ``phase_aligned_endpoints`` block (e.g. legacy
    JSONs predating Q-lock 13b Stage 1) contribute no rows. Empty
    DataFrame if no rows found across the cohort.
    """
    frames: list[pd.DataFrame] = []
    for animal in animals:
        for d in enumerate_session_dates(animal, resolver):
            frame = load_session_phase_aligned_endpoints_long(
                animal=animal, date=d, resolver=resolver,
            )
            if not frame.empty:
                frames.append(frame)
    if not frames:
        return _empty_long_df()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Stage 2 — per-session median + IQR + n_trials
# ---------------------------------------------------------------------------


def aggregate_per_session_median_iqr(
    long_df: pd.DataFrame,
) -> pd.DataFrame:
    """Collapse to one row per (animal, date, side, endpoint).

    Per Phase 9.1 Q-lock 13b kickoff Stage 2: ``median ± IQR ± n`` per
    (animal, date, side, endpoint). Uses linear interpolation for q25
    and q75 (scipy default, also pandas default for
    ``Series.quantile``).

    Parameters
    ----------
    long_df : pd.DataFrame
        Long-form rows from
        :func:`load_session_phase_aligned_endpoints_long` (or its cohort
        wrapper). Required columns: ``animal``, ``date``, ``side``,
        ``endpoint``, ``value``. ``trial_index`` is permitted but not
        consumed.

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``date``, ``side``, ``endpoint``,
        ``median``, ``q25``, ``q75``, ``iqr``, ``n_trials``. Empty
        (with the canonical column set) when ``long_df`` is empty.
    """
    cols = [
        "animal", "date", "side", "endpoint",
        "median", "q25", "q75", "iqr", "n_trials",
    ]
    if long_df.empty:
        return pd.DataFrame(columns=cols)

    required = {"animal", "date", "side", "endpoint", "value"}
    missing = required - set(long_df.columns)
    if missing:
        raise ValueError(
            f"long_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(long_df.columns)}.",
        )

    grouped = long_df.groupby(
        ["animal", "date", "side", "endpoint"], dropna=False, sort=True,
    )["value"]
    rows: list[dict[str, object]] = []
    for (animal, date, side, endpoint), values in grouped:
        finite = values.to_numpy(dtype=np.float64)
        finite = finite[np.isfinite(finite)]
        n_trials = int(finite.size)
        if n_trials == 0:
            median = float("nan")
            q25 = float("nan")
            q75 = float("nan")
            iqr = float("nan")
        else:
            median = float(np.median(finite))
            q25 = float(np.quantile(finite, 0.25))
            q75 = float(np.quantile(finite, 0.75))
            iqr = float(q75 - q25)
        rows.append({
            "animal": animal,
            "date": date,
            "side": side,
            "endpoint": endpoint,
            "median": median,
            "q25": q25,
            "q75": q75,
            "iqr": iqr,
            "n_trials": n_trials,
        })

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Stage 2 (mean convention) — per-session mean + SD + n
# ---------------------------------------------------------------------------


def aggregate_per_session_mean(
    long_df: pd.DataFrame,
) -> pd.DataFrame:
    """Collapse to one ``mean`` per (animal, date, side, endpoint).

    Mean-convention sibling of :func:`aggregate_per_session_median_iqr`
    (chore ``vChore-dlc-pooled-phenotype-unification`` methodology switch
    median+IQR → mean+SEM across the phenotype-pooled DLC families). The
    per-session value is the mean of that session's finite per-trial values.

    Parameters
    ----------
    long_df : pd.DataFrame
        Long-form per-trial rows. Required columns: ``animal``, ``date``,
        ``side``, ``endpoint``, ``value``.

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``date``, ``side``, ``endpoint``, ``mean``,
        ``sd``, ``n_trials``. Empty (canonical columns) when input is empty.
    """
    cols = ["animal", "date", "side", "endpoint", "mean", "sd", "n_trials"]
    if long_df.empty:
        return pd.DataFrame(columns=cols)
    required = {"animal", "date", "side", "endpoint", "value"}
    missing = required - set(long_df.columns)
    if missing:
        raise ValueError(
            f"long_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(long_df.columns)}.",
        )
    grouped = long_df.groupby(
        ["animal", "date", "side", "endpoint"], dropna=False, sort=True,
    )["value"]
    rows: list[dict[str, object]] = []
    for (animal, date, side, endpoint), values in grouped:
        finite = values.to_numpy(dtype=np.float64)
        finite = finite[np.isfinite(finite)]
        n_trials = int(finite.size)
        if n_trials == 0:
            mean = float("nan")
            sd = float("nan")
        else:
            mean = float(np.mean(finite))
            sd = float(np.std(finite, ddof=1)) if n_trials >= 2 else float("nan")
        rows.append({
            "animal": animal, "date": date, "side": side,
            "endpoint": endpoint, "mean": mean, "sd": sd,
            "n_trials": n_trials,
        })
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Stage 3 — phenotype-pooled median + IQR + n_sessions + n_animals
# ---------------------------------------------------------------------------


def attach_phenotype_and_epoch(
    per_session_df: pd.DataFrame,
    animals: Mapping[str, AnimalInfo],
) -> pd.DataFrame:
    """Add ``recovery_phenotype`` and ``epoch_label`` columns to per-session rows.

    ``recovery_phenotype`` is read from each animal's
    :class:`AnimalInfo.recovery_phenotype` (one of mild / moderate /
    moderate-severe / severe per F-P-1). ``epoch_label`` per
    :func:`stroke_orofacial.stats.recovery_epochs.assign_epoch_label`
    (one of pre / acute / sub_acute / chronic, or None in the
    transitional gap).

    Each animal's stroke_date is read from its AnimalInfo and combined
    with the session date to derive ``rel_day``. Rows whose animal
    lacks ``recovery_phenotype`` (or AnimalInfo entry) are dropped.

    Parameters
    ----------
    per_session_df : pd.DataFrame
        Output of :func:`aggregate_per_session_median_iqr`. Must have
        ``animal``, ``date`` (datetime.date), and at least one value
        column. Other columns pass through unchanged.
    animals : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo for the cohort.

    Returns
    -------
    pd.DataFrame
        Copy of ``per_session_df`` with two added columns:
        ``recovery_phenotype`` (str) and ``epoch_label`` (str or None).
        Rows for animals missing from ``animals`` (or with
        ``recovery_phenotype is None``) are dropped.
    """
    if per_session_df.empty:
        out = per_session_df.copy()
        out["recovery_phenotype"] = pd.Series(dtype=object)
        out["epoch_label"] = pd.Series(dtype=object)
        return out

    rel_days: list[int] = []
    phenotypes: list[str | None] = []
    epochs: list[str | None] = []
    keep: list[bool] = []
    for _, row in per_session_df.iterrows():
        animal_id = str(row["animal"])
        info = animals.get(animal_id)
        if info is None or info.recovery_phenotype is None:
            keep.append(False)
            rel_days.append(0)
            phenotypes.append(None)
            epochs.append(None)
            continue
        d = row["date"]
        # rel_day = days since stroke_date (negative pre-stroke; 0 = last
        # baseline session per project convention).
        rel_day = (d - info.stroke_date).days
        epoch = assign_epoch_label(rel_day, info)
        rel_days.append(int(rel_day))
        phenotypes.append(info.recovery_phenotype)
        epochs.append(epoch)
        keep.append(True)

    out = per_session_df.copy()
    out["rel_day"] = rel_days
    out["recovery_phenotype"] = phenotypes
    out["epoch_label"] = epochs
    mask = np.asarray(keep, dtype=bool)
    return out.loc[mask].reset_index(drop=True)


def aggregate_phenotype_pooled_median_iqr(
    per_session_df: pd.DataFrame,
    *,
    by_side: bool = True,
) -> pd.DataFrame:
    """Pool per-session medians within (phenotype, epoch[, side], endpoint).

    Per Phase 9.1 Q-lock 13b Addendum #2 D3 lock: pre-vs-post pairing
    uses ``epoch_label`` (pre / acute / sub_acute / chronic) — NOT
    ``rel_day_bin``. The unit of pooling is the per-session median
    (Phase 9 V5 precedent: per-session means used for cross-animal
    pooling avoids over-weighting trial-count-heavy sessions).

    Parameters
    ----------
    per_session_df : pd.DataFrame
        Output of :func:`attach_phenotype_and_epoch` (must contain
        ``recovery_phenotype`` and ``epoch_label`` columns). Rows with
        ``epoch_label is None`` are dropped (transitional gap).
    by_side : bool, default True
        When True, partitions by ``side`` (= production Q4 split-L/R
        convention). When False, pools across sides.

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``epoch_label``, [``side``],
        ``endpoint``, ``median``, ``q25``, ``q75``, ``iqr``,
        ``n_sessions``, ``n_animals``. ``median`` = median of per-session
        ``median`` values within the pool (median-of-medians). Empty
        with canonical columns when input is empty.
    """
    cols = ["recovery_phenotype", "epoch_label"]
    if by_side:
        cols.append("side")
    cols.extend([
        "endpoint", "median", "q25", "q75", "iqr",
        "n_sessions", "n_animals",
    ])
    if per_session_df.empty:
        return pd.DataFrame(columns=cols)

    required = {"recovery_phenotype", "epoch_label", "endpoint", "median", "animal"}
    if by_side:
        required.add("side")
    missing = required - set(per_session_df.columns)
    if missing:
        raise ValueError(
            f"per_session_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(per_session_df.columns)}.",
        )

    df = per_session_df.dropna(subset=["epoch_label"]).copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    keys = ["recovery_phenotype", "epoch_label"]
    if by_side:
        keys.append("side")
    keys.append("endpoint")

    rows: list[dict[str, object]] = []
    for key_tuple, sub in df.groupby(keys, dropna=False, sort=True):
        medians = sub["median"].to_numpy(dtype=np.float64)
        finite = medians[np.isfinite(medians)]
        n_sessions = int(finite.size)
        n_animals = int(sub.loc[
            np.isfinite(sub["median"].to_numpy(dtype=np.float64)),
            "animal",
        ].nunique())
        if n_sessions == 0:
            pooled_median = float("nan")
            q25 = float("nan")
            q75 = float("nan")
            iqr = float("nan")
        else:
            pooled_median = float(np.median(finite))
            q25 = float(np.quantile(finite, 0.25))
            q75 = float(np.quantile(finite, 0.75))
            iqr = float(q75 - q25)

        if not isinstance(key_tuple, tuple):
            key_tuple = (key_tuple,)
        rec = dict(zip(keys, key_tuple))
        rec.update({
            "median": pooled_median,
            "q25": q25,
            "q75": q75,
            "iqr": iqr,
            "n_sessions": n_sessions,
            "n_animals": n_animals,
        })
        rows.append(rec)

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def aggregate_phenotype_pooled_mean_sem(
    per_session_df: pd.DataFrame,
    *,
    value_col: str = "mean",
    by_side: bool = True,
) -> pd.DataFrame:
    """Pool per-session values to mean ± SEM with the **session** as the unit.

    Mean-convention sibling of :func:`aggregate_phenotype_pooled_median_iqr`,
    matching the Q14 spout-behavior convention shipped in PR #159 (chore
    ``vChore-dlc-pooled-phenotype-unification`` methodology switch median+IQR
    → mean+SEM). Within each (phenotype, epoch[, side], endpoint) cell, pooling
    is over the contributing per-session values directly (NOT a per-animal
    collapse first):

    - ``mean`` = mean across sessions of ``value_col``;
    - ``sd``   = ``SD(per-session values, ddof=1)`` (NaN for single-session);
    - ``sem``  = ``sd / sqrt(n_sessions)`` — the cell-level error bar.

    ``n_animals`` is tracked for provenance (the Wilcoxon test upstream still
    pairs per-animal means), but the SEM denominator here is ``n_sessions``.

    Parameters
    ----------
    per_session_df : pd.DataFrame
        Output of :func:`attach_phenotype_and_epoch`. Required columns:
        ``recovery_phenotype``, ``epoch_label``, ``endpoint``, ``animal``,
        ``value_col`` (and ``side`` when ``by_side``).
    value_col : str, default ``"mean"``
        Per-session value column to pool.
    by_side : bool, default True
        Partition by ``side`` (production split convention).

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``epoch_label``, [``side``],
        ``endpoint``, ``mean``, ``sem``, ``sd``, ``n_sessions``,
        ``n_animals``.
    """
    cols = ["recovery_phenotype", "epoch_label"]
    if by_side:
        cols.append("side")
    cols.extend(["endpoint", "mean", "sem", "sd", "n_sessions", "n_animals"])
    if per_session_df.empty:
        return pd.DataFrame(columns=cols)

    required = {"recovery_phenotype", "epoch_label", "endpoint", "animal", value_col}
    if by_side:
        required.add("side")
    missing = required - set(per_session_df.columns)
    if missing:
        raise ValueError(
            f"per_session_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(per_session_df.columns)}.",
        )

    df = per_session_df.dropna(subset=["epoch_label"]).copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    keys = ["recovery_phenotype", "epoch_label"]
    if by_side:
        keys.append("side")
    keys.append("endpoint")

    rows: list[dict[str, object]] = []
    for key_tuple, sub in df.groupby(keys, dropna=False, sort=True):
        vals = sub[value_col].to_numpy(dtype=np.float64)
        finite = vals[np.isfinite(vals)]
        n_sessions = int(finite.size)
        n_animals = int(sub.loc[
            np.isfinite(sub[value_col].to_numpy(dtype=np.float64)), "animal",
        ].nunique())
        if n_sessions == 0:
            pooled_mean = sd = sem = float("nan")
        else:
            pooled_mean = float(np.mean(finite))
            if n_sessions >= 2:
                sd = float(np.std(finite, ddof=1))
                sem = float(sd / np.sqrt(n_sessions))
            else:
                sd = float("nan")
                sem = float("nan")

        if not isinstance(key_tuple, tuple):
            key_tuple = (key_tuple,)
        rec = dict(zip(keys, key_tuple))
        rec.update({
            "mean": pooled_mean, "sem": sem, "sd": sd,
            "n_sessions": n_sessions, "n_animals": n_animals,
        })
        rows.append(rec)

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Baseline-delta computation (per Priya 2026-05-27)
# ---------------------------------------------------------------------------


def compute_per_animal_baseline(
    per_session_df: pd.DataFrame,
    *,
    value_col: str = "median",
) -> pd.DataFrame:
    """Per-(animal, side, endpoint) pre-stroke baseline mean of session medians.

    Baseline = mean of ``median`` for rows where ``epoch_label == "pre"``.
    Returns one row per (animal, side, endpoint) with a ``baseline_mean``
    column. Animals × sides × endpoints lacking any pre-epoch rows get
    ``baseline_mean = NaN`` — downstream ``apply_baseline_delta`` drops
    those rows (they can't contribute a meaningful delta).
    """
    required = {"animal", "side", "endpoint", "epoch_label", value_col}
    missing = required - set(per_session_df.columns)
    if missing:
        raise ValueError(
            f"per_session_df missing column(s) {sorted(missing)}.",
        )
    pre = per_session_df[per_session_df["epoch_label"] == "pre"]
    if pre.empty:
        return pd.DataFrame(
            columns=["animal", "side", "endpoint", "baseline_mean"],
        )
    agg = (
        pre.groupby(["animal", "side", "endpoint"], as_index=False)[value_col]
        .mean()
        .rename(columns={value_col: "baseline_mean"})
    )
    return agg


def apply_baseline_delta(
    per_session_df: pd.DataFrame,
    baseline: pd.DataFrame,
    *,
    value_col: str = "median",
) -> pd.DataFrame:
    """Attach ``delta_<value_col> = <value_col> − baseline_mean`` column.

    Sessions whose (animal, side, endpoint) has no baseline (pre-epoch
    absent) are dropped. Returns a copy; input is not mutated. The delta
    column name tracks ``value_col`` (``delta_median`` by default,
    ``delta_mean`` for the chore mean convention).
    """
    delta_col = f"delta_{value_col}"
    if per_session_df.empty:
        out = per_session_df.copy()
        out[delta_col] = pd.Series(dtype=float)
        return out
    joined = per_session_df.merge(
        baseline, on=["animal", "side", "endpoint"], how="inner",
    )
    joined = joined.dropna(subset=["baseline_mean"]).copy()
    joined[delta_col] = joined[value_col] - joined["baseline_mean"]
    return joined


# ---------------------------------------------------------------------------
# Q-lock 13.2 — per-trial linear-interp densification (jaggedness fix)
# ---------------------------------------------------------------------------


def relabel_pre_for_null_calibration(
    cohort_df: pd.DataFrame,
    *,
    rng_seed: int = 42,
    post_epochs: tuple[str, ...] = ("acute", "sub_acute", "chronic"),
) -> pd.DataFrame:
    """Relabel pre-stroke sessions into fake_pre + fake_post_X for null test.

    Q-lock 13.6 (2026-05-28). Per-animal × per-side: randomly partition
    pre-stroke sessions into 4 buckets (one stays "pre", three become
    "acute" / "sub_acute" / "chronic"). Drops non-pre rows. The
    resulting cohort_df has the same column schema as the input + the
    same trajectory data; only ``epoch_label`` is permuted within the
    pre-stroke pool.

    Used by the cohort emit script's ``--null-calibration`` flag to
    run the full stats family with no true pre-vs-post effect. P-values
    under H0 should be uniform; significant-rate cells indicate test
    mis-calibration (commonly due to pseudo-replication).

    Parameters
    ----------
    cohort_df : pd.DataFrame
        Output of ``densify_phase_rows_via_interp`` + ``attach_metadata``.
        Must contain ``animal``, ``date``, ``epoch_label`` columns.
    rng_seed : int, default 42.
    post_epochs : tuple[str, ...], default ``("acute", "sub_acute", "chronic")``.

    Returns
    -------
    pd.DataFrame
        Same column schema; ``epoch_label`` re-assigned within the pre
        pool; non-pre rows dropped.
    """
    if cohort_df.empty:
        return cohort_df.copy()
    required = {"animal", "date", "epoch_label"}
    missing = required - set(cohort_df.columns)
    if missing:
        raise ValueError(
            f"cohort_df missing column(s) {sorted(missing)}.",
        )
    pre_df = cohort_df[cohort_df["epoch_label"] == "pre"].copy()
    if pre_df.empty:
        return pre_df
    rng = np.random.default_rng(rng_seed)
    labels = ("pre",) + tuple(post_epochs)
    sessions = pre_df[["animal", "date"]].drop_duplicates()
    fake_label = []
    for animal, sub_df in sessions.groupby("animal", sort=False):
        n_sessions = len(sub_df)
        # Assign each session uniformly at random into the 4 buckets.
        labels_for_animal = rng.choice(labels, size=n_sessions, replace=True)
        for _, lbl in zip(sub_df.iterrows(), labels_for_animal):
            fake_label.append((animal, _[1]["date"], lbl))
    label_df = pd.DataFrame(
        fake_label, columns=["animal", "date", "_fake_epoch"],
    )
    out = pre_df.merge(label_df, on=["animal", "date"], how="left")
    out["epoch_label"] = out["_fake_epoch"]
    out = out.drop(columns=["_fake_epoch"])
    return out


def densify_phase_rows_via_interp(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    n_phase_bins: int = 72,
) -> pd.DataFrame:
    """Per-trial linear interpolation onto bin centers.

    Q-lock 13.2 (2026-05-28). Converts the substrate's frame-grained
    rows (one row per (trial, frame); ~25-50 sparse bins covered per
    trial under synthetic_only ILI mode) into trial × bin-grained rows
    (one row per (trial, bin) with linearly-interpolated signal value).

    Removes the cross-animal-pool bin-by-bin jaggedness caused by
    per-animal ILI mismatch under the frame-grained substrate: each
    animal's fixed-ILI trial hits a deterministic phase-bin lattice,
    so different animals' trials interleave bin coverage, and the
    cross-trial pool's per-bin trial count alternates animal-by-animal.
    Densification gives every trial a value at every bin within its
    phase range, removing the lattice mismatch.

    Per-trial interp recipe (using :func:`numpy.interp`):

    - Sort the trial's substrate rows by ``phase``.
    - Linear-interp the trial's ``(phase, signal_value)`` curve at
      each bin center.
    - Bins outside the trial's phase range get ``NaN`` (no
      extrapolation: ``left=NaN`` + ``right=NaN``).

    Carries per-trial metadata (``epoch_label``, ``recovery_phenotype``,
    ``rel_day``) through. Stage 1 baseline + Stage 2 aggregator + Stage
    6.1 scalar all consume the densified output unchanged — same
    column schema as the substrate, just trial × bin-grained instead
    of trial × frame-grained.

    Parameters
    ----------
    phase_rows_long : pd.DataFrame
        Output of the cohort substrate walk + ``attach_metadata``.
        Required columns: ``animal``, ``date``, ``trial_index``,
        ``side``, ``phase``, ``epoch_label``, plus one column per
        ``signals`` entry (default ``angle_deg`` + ``x_centered``).
        ``recovery_phenotype`` and ``rel_day`` carried through if
        present.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``
        Signal columns to interpolate.
    n_phase_bins : int, default 72
        Number of evenly-spaced bin centers across ``phase ∈ [0, 1]``.
        Matches the substrate's
        ``bundle.metadata["n_phase_bins"]`` default.

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``date``, ``trial_index``, ``side``,
        ``phase_bin`` (int), ``phase_bin_center`` (float), one column
        per signal (interpolated value), plus the carried metadata.
        Empty DataFrame with canonical columns when input is empty.
    """
    signals = tuple(signals)
    n_bins = int(n_phase_bins)
    if n_bins < 2:
        raise ValueError(f"n_phase_bins must be >= 2; got {n_bins!r}.")

    trial_keys = ["animal", "date", "trial_index", "side"]
    # All-licks phase rows carry one phase sweep PER LICK within a trial
    # (distinct ``peak_t_ms``); first-lick has exactly one. The interp must run
    # per-lick (each is a monotonic 0->1 sweep) — otherwise np.interp zigzags
    # across the interleaved licks' phases and the pooled trajectory is jagged
    # (F, 2026-06-01). We densify per (trial, peak) then collapse the peaks back
    # to per-(trial, bin) so the output schema + per-trial grain are unchanged.
    # For first-lick, peak_key is constant per trial -> a pure no-op.
    peak_key = ["peak_t_ms"] if "peak_t_ms" in phase_rows_long.columns else []
    group_keys = trial_keys + peak_key
    required = set(trial_keys) | {"phase", "epoch_label"} | set(signals)
    missing = required - set(phase_rows_long.columns)
    if missing:
        raise ValueError(
            f"phase_rows_long missing column(s) {sorted(missing)}; "
            f"got columns {list(phase_rows_long.columns)}.",
        )

    carry_cols = [
        c for c in ("epoch_label", "recovery_phenotype", "rel_day", "date")
        if c in phase_rows_long.columns
    ]
    # Don't double-carry trial_keys (date is in trial_keys; remove it
    # from carry_cols).
    carry_cols = [c for c in carry_cols if c not in trial_keys]

    out_cols = (
        trial_keys
        + ["phase_bin", "phase_bin_center"]
        + list(signals)
        + carry_cols
    )

    if phase_rows_long.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype=(
                "float64" if c in {"phase_bin_center"} | set(signals)
                else "int64" if c in {"trial_index", "phase_bin"}
                else "object"
            )) for c in out_cols}
        )

    bin_centers = np.linspace(
        0.5 / n_bins, 1.0 - 0.5 / n_bins, n_bins,
    )

    grouped = phase_rows_long.groupby(group_keys, sort=False)
    chunks: list[pd.DataFrame] = []
    for trial_key, trial_df in grouped:
        if len(trial_df) == 0:
            continue
        phases = trial_df["phase"].to_numpy(dtype=np.float64)
        sort_idx = np.argsort(phases)
        phases_sorted = phases[sort_idx]

        # Per-(trial, peak) metadata (same value across the group; take first).
        carry_vals = {col: trial_df[col].iloc[0] for col in carry_cols}

        chunk: dict[str, np.ndarray | list] = {}
        # group_keys broadcast across n_bins rows (peak_key carried for the
        # post-interp per-trial collapse below).
        for ki, kname in enumerate(group_keys):
            chunk[kname] = [trial_key[ki]] * n_bins
        chunk["phase_bin"] = np.arange(n_bins, dtype=np.int64)
        chunk["phase_bin_center"] = bin_centers.copy()

        for s in signals:
            vals_sorted = trial_df[s].to_numpy(
                dtype=np.float64,
            )[sort_idx]
            finite_mask = np.isfinite(vals_sorted)
            if finite_mask.sum() < 2:
                chunk[s] = np.full(n_bins, np.nan)
                continue
            ph_f = phases_sorted[finite_mask]
            v_f = vals_sorted[finite_mask]
            ph_min = float(ph_f[0])
            ph_max = float(ph_f[-1])
            interp_vals = np.interp(
                bin_centers, ph_f, v_f,
                left=np.nan, right=np.nan,
            )
            # np.interp's left/right kwargs apply when bin_center is
            # strictly outside [ph_f[0], ph_f[-1]]; tighten the mask
            # so equality edges still NaN-out cleanly.
            out_of_range = (bin_centers < ph_min) | (bin_centers > ph_max)
            interp_vals[out_of_range] = np.nan
            chunk[s] = interp_vals

        for col, val in carry_vals.items():
            chunk[col] = [val] * n_bins

        chunks.append(pd.DataFrame(chunk))

    if not chunks:
        return pd.DataFrame(
            {c: pd.Series(dtype=(
                "float64" if c in {"phase_bin_center"} | set(signals)
                else "int64" if c in {"trial_index", "phase_bin"}
                else "object"
            )) for c in out_cols}
        )
    out = pd.concat(chunks, ignore_index=True)
    if peak_key:
        # Collapse the per-lick interpolated curves back to one row per
        # (trial, bin) = mean across the trial's licks at that bin. Keeps the
        # downstream per-trial grain + "n=trials" unit; the smoothing comes from
        # interpolating EACH lick monotonically before averaging.
        agg = {s: "mean" for s in signals}
        agg["phase_bin_center"] = "first"
        for c in carry_cols:
            agg[c] = "first"
        out = out.groupby(
            trial_keys + ["phase_bin"], as_index=False, sort=False,
        ).agg(agg)
    return out[out_cols]


# ---------------------------------------------------------------------------
# Q-lock 13 — per-phase-bin trajectory baseline (Stage 1)
# ---------------------------------------------------------------------------


def compute_per_animal_phase_bin_baseline(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Per-(animal, side, phase_bin, signal) pre-stroke baseline mean.

    Q-lock 13 kickoff Stage 1 (2026-05-27); per-side keying + per-trial
    grain LOCKED 2026-05-28 (Priya pilot review): the original
    kickoff lock (animal × phase_bin pooled across sides) does NOT
    produce flat pre columns in the delta panels because (a) angle and
    x_centered have side-dependent sign conventions in mouse-frame /
    spout-midpoint-frame respectively, and (b) the per-frame baseline
    grain doesn't match Stage 2's per-trial-frame-mean aggregation
    unit. The fix mirrors Q13b's scalar
    :func:`compute_per_animal_baseline` which is per-(animal, side,
    endpoint).

    Trajectory analog of :func:`compute_per_animal_baseline` (Q13b
    scalar). The unit of aggregation is the per-(trial, side, phase_bin)
    frame-mean — same grain Stage 2 collapses to before cross-trial
    pooling. This guarantees the cross-trial pool of pre deltas sums to
    exactly 0 within each (phenotype, "pre", side, phase_bin) cell, so
    the pre column of every delta-variant panel is flat at 0 by
    construction.

    Two-pass:

    1. Within (animal, date, trial_index, side, phase_bin), take the
       frame-mean of each signal. One row per pre trial × side × bin.
    2. Across pre trials within (animal, side, phase_bin), average the
       per-trial-frame-means → ``baseline_mean``.

    NaN-aware throughout. (animal, side, phase_bin, signal) quadruples
    with no finite pre-stroke values are absent from the output;
    downstream :func:`apply_phase_bin_baseline_delta` produces NaN
    deltas for rows whose quadruple has no baseline entry.

    Parameters
    ----------
    phase_rows_long : pd.DataFrame
        Long-form centered phase rows. Required columns: ``animal``,
        ``date``, ``trial_index``, ``side``, ``phase_bin``,
        ``epoch_label``, and one column per ``signals`` entry (default
        ``angle_deg`` and ``x_centered``). One row per (trial,
        frame-in-phase-cycle); see
        :func:`stroke_orofacial.dlc_kinematics.tongue_pertrial.build_first_lick_centered_phase_rows`.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``
        Signal column names to compute baselines for. Each must be a
        column in ``phase_rows_long``.

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``side`` (str), ``phase_bin`` (int),
        ``signal`` (str), ``baseline_mean`` (float). One row per
        quadruple with at least one finite per-trial frame-mean from a
        pre-stroke trial. Canonical column set returned even when input
        is empty.
    """
    signals = tuple(signals)
    out_cols = ["animal", "side", "phase_bin", "signal", "baseline_mean"]
    required = {
        "animal", "date", "trial_index", "side", "phase_bin", "epoch_label",
    } | set(signals)
    missing = required - set(phase_rows_long.columns)
    if missing:
        raise ValueError(
            f"phase_rows_long missing column(s) {sorted(missing)}; "
            f"got columns {list(phase_rows_long.columns)}.",
        )
    if phase_rows_long.empty:
        return pd.DataFrame(columns=out_cols)
    pre = phase_rows_long[phase_rows_long["epoch_label"] == "pre"]
    if pre.empty:
        return pd.DataFrame(columns=out_cols)

    trial_keys = ["animal", "date", "trial_index", "side", "phase_bin"]
    # Pass 1: per-trial × side × bin frame-mean for each signal.
    sub = pre[trial_keys + list(signals)].copy()
    for s in signals:
        sub[s] = pd.to_numeric(sub[s], errors="coerce")
    per_trial = (
        sub.groupby(trial_keys, dropna=False, sort=False, as_index=False)[
            list(signals)
        ]
        .mean()
    )

    # Pass 2: cross-trial average within (animal, side, phase_bin) →
    # baseline_mean per signal. Melt to long form for the final
    # (animal, side, phase_bin, signal, baseline_mean) shape.
    melted = per_trial.melt(
        id_vars=["animal", "side", "phase_bin"],
        value_vars=list(signals),
        var_name="signal",
        value_name="value",
    )
    finite_mask = np.isfinite(melted["value"].to_numpy(dtype=np.float64))
    melted = melted.loc[finite_mask]
    if melted.empty:
        return pd.DataFrame(columns=out_cols)
    agg = (
        melted.groupby(
            ["animal", "side", "phase_bin", "signal"],
            as_index=False,
        )["value"]
        .mean()
        .rename(columns={"value": "baseline_mean"})
    )
    return agg[out_cols].reset_index(drop=True)


def apply_phase_bin_baseline_delta(
    phase_rows_long: pd.DataFrame,
    baseline: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Attach ``<signal>_delta`` columns to every row of ``phase_rows_long``.

    Q-lock 13 kickoff Stage 1 (2026-05-27); per-side keying LOCKED
    2026-05-28 (see :func:`compute_per_animal_phase_bin_baseline` for
    rationale). For each signal,
    ``<signal>_delta = <signal> − baseline_mean`` where
    ``baseline_mean`` is looked up at (animal, side, phase_bin, signal)
    in ``baseline``. Rows whose quadruple has no baseline entry get
    ``NaN`` for that signal's delta column.

    Delta is computed for EVERY row (pre and post) — pre rows' Stage 2
    cross-trial pool will be exactly 0 within each (phenotype, "pre",
    side, phase_bin) cell by construction (per-trial grain match
    between baseline and Stage 2 aggregator). Post rows carry the
    deviation that the delta-variant figures visualize.

    Returns a copy; input is not mutated.

    Parameters
    ----------
    phase_rows_long : pd.DataFrame
        Output of the cohort substrate walk.
    baseline : pd.DataFrame
        Output of :func:`compute_per_animal_phase_bin_baseline`.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``

    Returns
    -------
    pd.DataFrame
        Copy of ``phase_rows_long`` plus one ``<signal>_delta`` column
        per entry in ``signals``.
    """
    signals = tuple(signals)
    out = phase_rows_long.copy()
    if out.empty:
        for s in signals:
            out[f"{s}_delta"] = pd.Series(dtype=float)
        return out
    for s in signals:
        b = baseline[baseline["signal"] == s][
            ["animal", "side", "phase_bin", "baseline_mean"]
        ]
        merged = out.merge(
            b, on=["animal", "side", "phase_bin"],
            how="left", validate="many_to_one",
        )
        out[f"{s}_delta"] = (
            merged[s].to_numpy(dtype=np.float64)
            - merged["baseline_mean"].to_numpy(dtype=np.float64)
        )
    return out


# ---------------------------------------------------------------------------
# Q-lock 13.1 — per-animal trajectory scalar (for paired Wilcoxon stats)
# ---------------------------------------------------------------------------


def compute_per_trial_trajectory_scalar(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Per-(animal, date, trial, side, signal, epoch) trajectory scalar.

    Q-lock 13.5 (2026-05-28). Per-trial unit for unpaired pre-vs-post
    Mann-Whitney U tests. Scalar = mean across phase bins of the
    per-(trial × bin) frame-mean within (animal, date, trial, side,
    signal, epoch). One row per trial × side × signal × epoch.

    Same NaN-aware grain Pass 1 of Stage 2 uses; suitable for the
    densified or frame-grained substrate input.

    Returns columns: ``animal, date, trial_index, side, signal,
    epoch_label, scalar``. Empty with canonical columns when input is
    empty.
    """
    signals = tuple(signals)
    out_cols = [
        "animal", "date", "trial_index", "side",
        "signal", "epoch_label", "scalar",
    ]
    required = {
        "animal", "date", "trial_index", "side", "phase_bin", "epoch_label",
    } | set(signals)
    missing = required - set(phase_rows_long.columns)
    if missing:
        raise ValueError(
            f"phase_rows_long missing column(s) {sorted(missing)}; "
            f"got columns {list(phase_rows_long.columns)}.",
        )
    if phase_rows_long.empty:
        return pd.DataFrame(columns=out_cols)

    trial_keys = ["animal", "date", "trial_index", "side", "phase_bin"]
    sub = phase_rows_long[
        trial_keys + ["epoch_label"] + list(signals)
    ].copy()
    for s in signals:
        sub[s] = pd.to_numeric(sub[s], errors="coerce")
    per_trial_bin = (
        sub.groupby(
            trial_keys + ["epoch_label"],
            dropna=False, sort=False, as_index=False,
        )[list(signals)]
        .mean()
    )
    melted = per_trial_bin.melt(
        id_vars=[
            "animal", "date", "trial_index", "side", "epoch_label",
        ],
        value_vars=list(signals),
        var_name="signal",
        value_name="value",
    )
    finite_mask = np.isfinite(melted["value"].to_numpy(dtype=np.float64))
    melted = melted.loc[finite_mask]
    if melted.empty:
        return pd.DataFrame(columns=out_cols)
    agg = (
        melted.groupby(
            ["animal", "date", "trial_index", "side", "signal", "epoch_label"],
            as_index=False,
        )["value"]
        .mean()
        .rename(columns={"value": "scalar"})
    )
    return agg[out_cols].reset_index(drop=True)


def compute_per_session_trajectory_scalar(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Per-(animal, date, side, signal, epoch) trajectory scalar.

    Q-lock 13.5 (2026-05-28). Per-session unit for unpaired
    pre-vs-post MWU tests. Scalar = mean across (trial × bin) of the
    per-trial frame-means within each session × side × signal × epoch.

    Returns columns: ``animal, date, side, signal, epoch_label,
    scalar``. Empty with canonical columns when input is empty.
    """
    per_trial = compute_per_trial_trajectory_scalar(
        phase_rows_long, signals=signals,
    )
    out_cols = ["animal", "date", "side", "signal", "epoch_label", "scalar"]
    if per_trial.empty:
        return pd.DataFrame(columns=out_cols)
    agg = (
        per_trial.groupby(
            ["animal", "date", "side", "signal", "epoch_label"],
            as_index=False,
        )["scalar"]
        .mean()
    )
    return agg[out_cols].reset_index(drop=True)


def compute_per_animal_trajectory_scalar(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
) -> pd.DataFrame:
    """Per-(animal, side, signal, epoch_label) trajectory scalar.

    Q-lock 13.1 follow-on stats prep (2026-05-28). Collapses each
    animal's epoch-restricted trajectory to one scalar by taking the
    cross-trial × cross-bin mean of per-trial frame-means. This is
    the value column the trajectory paired Wilcoxon family consumes —
    one row per animal × side × signal × epoch, then per-(phenotype,
    side, signal, post_epoch) the existing
    :func:`stroke_orofacial.stats.models.fit_paired_pre_post_wilcoxon`
    pairs pre vs post within phenotype and tests the per-animal
    paired differences.

    Two-pass to match Stage 1 + Stage 2 grain:

    1. Per (animal, date, trial_index, side, phase_bin) frame-mean
       for each signal.
    2. Cross-trial × cross-bin mean within (animal, side, signal,
       epoch_label).

    NaN-aware throughout. (animal, side, signal, epoch_label) tuples
    with no finite per-trial frame-means are absent from the output.

    Parameters
    ----------
    phase_rows_long : pd.DataFrame
        Long-form centered phase rows. Required columns: ``animal``,
        ``date``, ``trial_index``, ``side``, ``phase_bin``,
        ``epoch_label``, and one column per ``signals`` entry.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``

    Returns
    -------
    pd.DataFrame
        Columns: ``animal``, ``side``, ``signal``, ``epoch_label``,
        ``scalar`` (float). Canonical column set returned even when
        input is empty.
    """
    signals = tuple(signals)
    out_cols = ["animal", "side", "signal", "epoch_label", "scalar"]
    required = {
        "animal", "date", "trial_index", "side", "phase_bin", "epoch_label",
    } | set(signals)
    missing = required - set(phase_rows_long.columns)
    if missing:
        raise ValueError(
            f"phase_rows_long missing column(s) {sorted(missing)}; "
            f"got columns {list(phase_rows_long.columns)}.",
        )
    if phase_rows_long.empty:
        return pd.DataFrame(columns=out_cols)

    trial_keys = ["animal", "date", "trial_index", "side", "phase_bin"]
    sub = phase_rows_long[
        trial_keys + ["epoch_label"] + list(signals)
    ].copy()
    for s in signals:
        sub[s] = pd.to_numeric(sub[s], errors="coerce")

    # Pass 1: per-trial × side × bin frame-mean for each signal.
    per_trial = (
        sub.groupby(
            trial_keys + ["epoch_label"],
            dropna=False, sort=False, as_index=False,
        )[list(signals)]
        .mean()
    )

    # Pass 2: cross-trial × cross-bin mean within (animal, side, signal,
    # epoch_label).
    melted = per_trial.melt(
        id_vars=["animal", "side", "epoch_label"],
        value_vars=list(signals),
        var_name="signal",
        value_name="value",
    )
    finite_mask = np.isfinite(melted["value"].to_numpy(dtype=np.float64))
    melted = melted.loc[finite_mask]
    if melted.empty:
        return pd.DataFrame(columns=out_cols)
    agg = (
        melted.groupby(
            ["animal", "side", "signal", "epoch_label"],
            as_index=False,
        )["value"]
        .mean()
        .rename(columns={"value": "scalar"})
    )
    return agg[out_cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Q-lock 13 — phenotype × epoch × side × phase_bin mean+SEM aggregator (Stage 2)
# ---------------------------------------------------------------------------


def aggregate_phenotype_pooled_phase_bin_mean_sem(
    phase_rows_long: pd.DataFrame,
    *,
    signals: Iterable[str] = TRAJECTORY_SIGNALS,
    variants: Iterable[str] = ("raw", "delta"),
    by_side: bool = True,
) -> pd.DataFrame:
    """Per (phenotype × epoch × [side] × phase_bin × signal × variant) mean+SEM.

    Q-lock 13 kickoff Stage 2 (2026-05-27). Trajectory analog of
    :func:`aggregate_phenotype_pooled_median_iqr` (Q13b scalar), with
    two material differences:

    - **Mean + SEM**, not median + IQR. Per Q13-B lock: per-bin averages
      across many trials within phenotype × epoch are already smoothed;
      mean+SEM is more readable + standard for trajectory figures.
    - **Per-trial unit, not per-session-median.** Each trial contributes
      one value per phase_bin (frame-mean within that trial × phase_bin
      cell — see two-pass aggregation below). The reported sample size
      ``n_trials`` is the number of distinct trials in the pool, per
      kickoff Q13-F (panel annotation = ``n=N trials``).

    Two-pass aggregation:

    1. Per-trial frame-mean within (animal, date, trial_index, side,
       phase_bin) for each signal × variant. Collapses any multi-frame
       contribution from the same trial in the same phase_bin to one
       value.
    2. Cross-trial pool within (recovery_phenotype, epoch_label,
       [side], phase_bin, signal, variant) → mean, SD
       (``std(ddof=1)``), SEM (``SD / sqrt(n)``), n_trials,
       n_sessions, n_animals. n=1 cells get ``sd = sem = NaN``.
       NaN-aware throughout.

    Parameters
    ----------
    phase_rows_long : pd.DataFrame
        Long-form rows with required columns: ``animal``, ``date``,
        ``trial_index``, ``side`` (when ``by_side``), ``phase_bin``,
        ``phase_bin_center`` (carried through; optional),
        ``recovery_phenotype``, ``epoch_label``, and one column per
        signal × variant cell — for variant=``raw`` the signal column
        itself; for variant=``delta`` the ``<signal>_delta`` column
        (output of :func:`apply_phase_bin_baseline_delta`).
        Rows with ``epoch_label is None`` (transitional gap) are
        dropped.
    signals : Iterable[str], default ``TRAJECTORY_SIGNALS``
    variants : Iterable[str], default ``("raw", "delta")``
        Subset of ``{"raw", "delta"}``.
    by_side : bool, default True

    Returns
    -------
    pd.DataFrame
        Columns: ``recovery_phenotype``, ``epoch_label``, [``side``],
        ``phase_bin``, ``phase_bin_center`` (if present in input),
        ``signal``, ``variant``, ``mean``, ``sem``, ``sd``,
        ``n_trials``, ``n_sessions``, ``n_animals``. Empty with
        canonical columns when input is empty.
    """
    signals = tuple(signals)
    variants = tuple(variants)
    bad_variants = set(variants) - {"raw", "delta"}
    if bad_variants:
        raise ValueError(
            f"variants must be subset of (raw, delta); got unexpected "
            f"{sorted(bad_variants)}.",
        )

    has_center = "phase_bin_center" in phase_rows_long.columns
    out_cols = ["recovery_phenotype", "epoch_label"]
    if by_side:
        out_cols.append("side")
    out_cols.append("phase_bin")
    if has_center:
        out_cols.append("phase_bin_center")
    out_cols.extend(
        ["signal", "variant", "mean", "sem", "sd", "n_trials",
         "n_sessions", "n_animals"],
    )

    required = {
        "animal", "date", "trial_index", "phase_bin",
        "recovery_phenotype", "epoch_label",
    }
    if by_side:
        required.add("side")
    for s in signals:
        if "raw" in variants:
            required.add(s)
        if "delta" in variants:
            required.add(f"{s}_delta")
    missing = required - set(phase_rows_long.columns)
    if missing:
        raise ValueError(
            f"phase_rows_long missing column(s) {sorted(missing)}; "
            f"got columns {list(phase_rows_long.columns)}.",
        )

    if phase_rows_long.empty:
        return pd.DataFrame(columns=out_cols)

    # Drop transitional-gap rows.
    df = phase_rows_long.dropna(subset=["epoch_label"]).copy()
    if df.empty:
        return pd.DataFrame(columns=out_cols)

    # Trial-key for per-trial collapse + n_trials counting.
    trial_keys = ["animal", "date", "trial_index"]
    if by_side:
        trial_keys.append("side")

    # Bin-key carries phase_bin (+ optional center) into the output.
    bin_keys = ["phase_bin"]
    if has_center:
        bin_keys.append("phase_bin_center")

    # Pool-key partitions cells.
    pool_keys = ["recovery_phenotype", "epoch_label"]
    if by_side:
        pool_keys.append("side")

    # Deduplicate column selection (trial_keys + pool_keys both contain
    # "side" when by_side=True; pandas refuses groupby on duplicate
    # columns).
    select_cols = list(dict.fromkeys(trial_keys + bin_keys + pool_keys))

    rows: list[dict[str, object]] = []
    for signal in signals:
        for variant in variants:
            value_col = signal if variant == "raw" else f"{signal}_delta"
            sub = df[select_cols + [value_col]].copy()
            sub["_val"] = pd.to_numeric(sub[value_col], errors="coerce")
            sub = sub.loc[np.isfinite(sub["_val"])]
            if sub.empty:
                continue
            # Pass 1: per-trial frame-mean within (trial × phase_bin).
            per_trial_keys = list(dict.fromkeys(
                trial_keys + bin_keys + pool_keys,
            ))
            per_trial = (
                sub.groupby(
                    per_trial_keys,
                    dropna=False, sort=False, as_index=False,
                )["_val"]
                .mean()
            )
            # Pass 2: cross-trial pool within (pool × phase_bin).
            for cell_key, cell_df in per_trial.groupby(
                pool_keys + bin_keys, dropna=False, sort=True,
            ):
                vals = cell_df["_val"].to_numpy(dtype=np.float64)
                n_trials = int(vals.size)
                if n_trials == 0:
                    continue
                mean_v = float(np.mean(vals))
                if n_trials >= 2:
                    sd_v = float(np.std(vals, ddof=1))
                    sem_v = float(sd_v / np.sqrt(n_trials))
                else:
                    sd_v = float("nan")
                    sem_v = float("nan")
                # Distinct sessions / animals contributing to this cell.
                session_keys = ["animal", "date"]
                n_sessions = int(cell_df[session_keys].drop_duplicates().shape[0])
                n_animals = int(cell_df["animal"].nunique())

                if not isinstance(cell_key, tuple):
                    cell_key = (cell_key,)
                rec = dict(zip(pool_keys + bin_keys, cell_key))
                rec["signal"] = signal
                rec["variant"] = variant
                rec["mean"] = mean_v
                rec["sem"] = sem_v
                rec["sd"] = sd_v
                rec["n_trials"] = n_trials
                rec["n_sessions"] = n_sessions
                rec["n_animals"] = n_animals
                rows.append(rec)

    if not rows:
        return pd.DataFrame(columns=out_cols)
    return pd.DataFrame(rows, columns=out_cols)


# ---------------------------------------------------------------------------
# Q-lock 12 — phenotype-pooled spatial proportion-diff aggregator
# ---------------------------------------------------------------------------


def aggregate_phenotype_pooled_spatial_diff(
    per_animal_records: Iterable[Mapping[str, object]],
    animals: Mapping[str, AnimalInfo],
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    """Phenotype-pooled mean-of-D-arrays across animals within phenotype.

    Phase 9.1 Q-lock 12 Stage 2. Each animal's per-``(side, bodypart,
    post_epoch)`` proportion_diff array — produced by
    :func:`stroke_orofacial.stats.spatial_proportion_diff.compute_per_animal_per_epoch_diff`
    — is mean-pooled across animals sharing the same
    ``recovery_phenotype``. NaN-aware (per-cell ``np.nanmean``): cells
    where one animal has no-data (Q12-E source-data mask) drop that
    animal's contribution from that cell's phenotype mean. Cells where
    EVERY contributing animal has NaN remain NaN in the pooled array.

    Within-phenotype mean (NOT median) per Q-lock 12 Stage 2 kickoff
    spec — contrast with :func:`aggregate_phenotype_pooled_median_iqr`
    for scalar endpoints which uses median-of-medians.

    Parameters
    ----------
    per_animal_records : Iterable[Mapping]
        Each record contains the keys:
        ``animal`` (str), ``side`` (``"L"`` or ``"R"``),
        ``bodypart`` (``"tongue"`` or ``"jaw"``), ``post_epoch``
        (``"acute"`` / ``"sub_acute"`` / ``"chronic"``),
        ``D`` (``np.ndarray`` shape ``(nx, ny)`` with NaN for no-data
        cells), ``extent`` (``list[float]`` or None — must agree across
        records within the same (side, bodypart, post_epoch) bucket),
        ``n_pre_trials`` (int), ``n_post_trials`` (int). Records with
        ``D is None`` are dropped.
    animals : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo lookup. Records whose animal is missing
        from this map, or whose AnimalInfo has
        ``recovery_phenotype is None``, are silently dropped.

    Returns
    -------
    dict[tuple[str, str, str, str], dict[str, object]]
        Keyed by ``(recovery_phenotype, side, bodypart, post_epoch)``.
        Each value contains:

        - ``D_mean`` (``np.ndarray`` shape ``(nx, ny)``): nanmean across
          contributing animals; NaN cells where every contributing
          animal had NaN at that cell.
        - ``n_contributing_animals_per_cell`` (``np.ndarray`` shape
          ``(nx, ny)`` of ``int``): per-cell count of contributing
          animals.
        - ``contributing_animals`` (``list[str]``): sorted animal IDs
          with a non-None record for this combination.
        - ``n_pre_trials_per_animal`` (``dict[str, int]``)
        - ``n_post_trials_per_animal`` (``dict[str, int]``)
        - ``extent`` (``list[float]`` or None)
        - ``n_animals`` (``int``): ``len(contributing_animals)``.

    Raises
    ------
    ValueError
        If two records in the same (side, bp, epoch) bucket disagree on
        ``D.shape`` or on a non-None ``extent`` — that indicates a bin-
        grid divergence that would silently corrupt the pooled mean.
    """
    required = {
        "animal", "side", "bodypart", "post_epoch", "D", "extent",
        "n_pre_trials", "n_post_trials",
    }
    # Bucket records by (side, bp, epoch), filtering on D-not-None +
    # phenotype-known.
    buckets: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    pheno_by_animal: dict[str, str] = {}
    for rec in per_animal_records:
        if not isinstance(rec, Mapping):
            raise TypeError(
                f"per_animal_records entries must be Mapping; got "
                f"{type(rec).__name__}.",
            )
        missing = required - set(rec.keys())
        if missing:
            raise ValueError(
                f"per-animal record missing keys {sorted(missing)}; "
                f"got {sorted(rec.keys())}.",
            )
        if rec["D"] is None:
            continue
        animal_id = str(rec["animal"])
        info = animals.get(animal_id)
        if info is None or info.recovery_phenotype is None:
            continue
        pheno_by_animal[animal_id] = info.recovery_phenotype
        bucket = (
            str(rec["side"]),
            str(rec["bodypart"]),
            str(rec["post_epoch"]),
        )
        buckets.setdefault(bucket, []).append(rec)

    out: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for (side, bp, ep), recs in buckets.items():
        # Group records within this bucket by recovery_phenotype.
        by_pheno: dict[str, list[Mapping[str, object]]] = {}
        for rec in recs:
            pheno = pheno_by_animal[str(rec["animal"])]
            by_pheno.setdefault(pheno, []).append(rec)

        for pheno, pheno_recs in by_pheno.items():
            # Verify shape + extent consistency within (pheno, side, bp, ep).
            shapes = {tuple(np.asarray(r["D"]).shape) for r in pheno_recs}
            if len(shapes) != 1:
                raise ValueError(
                    f"shape mismatch across animals in pool "
                    f"({pheno}, {side}, {bp}, {ep}): {sorted(shapes)} — "
                    "bin-grid divergence would corrupt the pooled mean.",
                )
            extents = [r["extent"] for r in pheno_recs if r["extent"] is not None]
            if extents:
                ref = tuple(extents[0])
                for ext in extents[1:]:
                    if tuple(ext) != ref:
                        raise ValueError(
                            f"extent mismatch across animals in pool "
                            f"({pheno}, {side}, {bp}, {ep}): {ref} vs "
                            f"{tuple(ext)}.",
                        )
                extent = list(ref)
            else:
                extent = None

            # nanmean across animals' D arrays for this bucket.
            stack = np.stack(
                [np.asarray(r["D"], dtype=np.float64) for r in pheno_recs],
                axis=0,
            )
            # n_contributing per cell = count of finite values across the
            # animal-axis.
            n_contrib = np.isfinite(stack).sum(axis=0)
            # nanmean of all-NaN slice yields NaN; that IS the desired
            # behavior for phenotype-pooled no-data cells (Q12-E). The
            # warning numpy emits is noise here; silence it explicitly.
            import warnings as _warnings
            with _warnings.catch_warnings():
                _warnings.filterwarnings(
                    "ignore",
                    message="Mean of empty slice",
                    category=RuntimeWarning,
                )
                D_mean = np.nanmean(stack, axis=0)

            contributing_animals = sorted(
                str(r["animal"]) for r in pheno_recs
            )
            n_pre_trials_per_animal = {
                str(r["animal"]): int(r["n_pre_trials"]) for r in pheno_recs
            }
            n_post_trials_per_animal = {
                str(r["animal"]): int(r["n_post_trials"]) for r in pheno_recs
            }

            out[(pheno, side, bp, ep)] = {
                "D_mean": D_mean,
                "n_contributing_animals_per_cell": n_contrib.astype(np.int64),
                "contributing_animals": contributing_animals,
                "n_pre_trials_per_animal": n_pre_trials_per_animal,
                "n_post_trials_per_animal": n_post_trials_per_animal,
                "extent": extent,
                "n_animals": len(contributing_animals),
            }
    return out


# ---------------------------------------------------------------------------
# Q-lock 12 Addendum #5 — phenotype-pooled W-2 recovery aggregator
# ---------------------------------------------------------------------------


def aggregate_phenotype_pooled_wasserstein(
    per_animal_w2_records: Iterable[Mapping[str, object]],
    animals: Mapping[str, AnimalInfo],
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    """Phenotype-pool W-2 scalars across animals: mean ± SEM.

    Per Phase 9.1 Q-lock 12 Addendum #5 Stage 5d: each animal's
    per-(side, bodypart, post_epoch) scalar W-2 (Wasserstein-2 distance
    between its pre-pool and post-epoch histograms) is averaged across
    animals sharing the same ``recovery_phenotype``. Mean ± SEM per
    Priya 2026-05-28 direction (n=1 phenotype tiers report ``sem=nan``;
    the line plot draws a marker with no error bar in that case).

    Parameters
    ----------
    per_animal_w2_records : Iterable[Mapping]
        Each record contains keys: ``animal`` (str), ``side``,
        ``bodypart``, ``post_epoch``, ``w2`` (float or NaN — NaN means
        no contribution for that combination). Typically produced by
        the Stage 1 wrapper +
        :func:`stroke_orofacial.stats.spatial_wasserstein.compute_per_animal_wasserstein2`.
    animals : Mapping[str, AnimalInfo]
        Animal-ID → AnimalInfo. Records whose animal lacks
        ``recovery_phenotype`` are dropped.

    Returns
    -------
    dict[tuple[str, str, str, str], dict[str, object]]
        Keyed by ``(recovery_phenotype, side, bodypart, post_epoch)``.
        Each value:

        - ``w2_mean`` (float): mean across contributing animals with
          finite W-2.
        - ``w2_sem`` (float): standard error of the mean
          (``std / sqrt(n)``, ``ddof=1``). NaN when n ≤ 1.
        - ``w2_per_animal`` (dict[str, float]): per-animal W-2 values
          (NaN dropped).
        - ``n_animals`` (int): number of contributing animals.
        - ``contributing_animals`` (list[str]): sorted IDs.

    Raises
    ------
    ValueError
        On missing keys in a record.
    """
    required = {"animal", "side", "bodypart", "post_epoch", "w2"}
    buckets: dict[tuple[str, str, str, str], dict[str, float]] = {}
    pheno_by_animal: dict[str, str] = {}
    for rec in per_animal_w2_records:
        if not isinstance(rec, Mapping):
            raise TypeError(
                f"per_animal_w2_records entries must be Mapping; got "
                f"{type(rec).__name__}.",
            )
        missing = required - set(rec.keys())
        if missing:
            raise ValueError(
                f"per-animal W-2 record missing keys {sorted(missing)}; "
                f"got {sorted(rec.keys())}.",
            )
        animal_id = str(rec["animal"])
        info = animals.get(animal_id)
        if info is None or info.recovery_phenotype is None:
            continue
        w2 = rec["w2"]
        if w2 is None or (isinstance(w2, float) and not np.isfinite(w2)):
            continue
        pheno_by_animal[animal_id] = info.recovery_phenotype
        key = (
            info.recovery_phenotype,
            str(rec["side"]),
            str(rec["bodypart"]),
            str(rec["post_epoch"]),
        )
        buckets.setdefault(key, {})[animal_id] = float(w2)

    out: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for key, per_animal in buckets.items():
        vals = np.fromiter(per_animal.values(), dtype=np.float64)
        n = int(vals.size)
        w2_mean = float(vals.mean())
        if n <= 1:
            w2_sem = float("nan")
        else:
            w2_sem = float(vals.std(ddof=1) / np.sqrt(n))
        out[key] = {
            "w2_mean": w2_mean,
            "w2_sem": w2_sem,
            "w2_per_animal": dict(per_animal),
            "n_animals": n,
            "contributing_animals": sorted(per_animal.keys()),
        }
    return out


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _empty_long_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "animal", "date", "trial_index", "side", "endpoint", "value",
    ])
