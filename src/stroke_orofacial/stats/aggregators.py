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


# ---------------------------------------------------------------------------
# JSON readers
# ---------------------------------------------------------------------------


def load_session_phase_aligned_endpoints_long(
    animal: str,
    date: datetime.date,
    resolver: PathResolver,
) -> pd.DataFrame:
    """Load one per-trial endpoints JSON; return long-form rows.

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


# ---------------------------------------------------------------------------
# Baseline-delta computation (per Priya 2026-05-27)
# ---------------------------------------------------------------------------


def compute_per_animal_baseline(
    per_session_df: pd.DataFrame,
) -> pd.DataFrame:
    """Per-(animal, side, endpoint) pre-stroke baseline mean of session medians.

    Baseline = mean of ``median`` for rows where ``epoch_label == "pre"``.
    Returns one row per (animal, side, endpoint) with a ``baseline_mean``
    column. Animals × sides × endpoints lacking any pre-epoch rows get
    ``baseline_mean = NaN`` — downstream ``apply_baseline_delta`` drops
    those rows (they can't contribute a meaningful delta).
    """
    required = {"animal", "side", "endpoint", "epoch_label", "median"}
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
        pre.groupby(["animal", "side", "endpoint"], as_index=False)["median"]
        .mean()
        .rename(columns={"median": "baseline_mean"})
    )
    return agg


def apply_baseline_delta(
    per_session_df: pd.DataFrame,
    baseline: pd.DataFrame,
) -> pd.DataFrame:
    """Attach ``delta_median = median − baseline_mean`` column.

    Sessions whose (animal, side, endpoint) has no baseline (pre-epoch
    absent) are dropped. Returns a copy; input is not mutated.
    """
    if per_session_df.empty:
        out = per_session_df.copy()
        out["delta_median"] = pd.Series(dtype=float)
        return out
    joined = per_session_df.merge(
        baseline, on=["animal", "side", "endpoint"], how="inner",
    )
    joined = joined.dropna(subset=["baseline_mean"]).copy()
    joined["delta_median"] = joined["median"] - joined["baseline_mean"]
    return joined


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
# Private helpers
# ---------------------------------------------------------------------------


def _empty_long_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "animal", "date", "trial_index", "side", "endpoint", "value",
    ])
