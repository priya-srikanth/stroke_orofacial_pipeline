"""Per-animal baseline normalization helpers for Phase 9 stats inputs.

All functions consume a long-format inputs DataFrame produced by
:mod:`scripts.phase_9_stats.materialize_inputs` (or its spatial
counterpart) and return a NEW DataFrame with a baseline-normalized
``value_norm`` column (or equivalent). The original ``value`` column is
preserved.

The canonical normalization for Task 4 mixed-effects models is
:func:`difference_from_baseline` — additive per Addendum #6 (revises
Addendum #5's earlier multiplicative leaning). Multiplicative
(:func:`ratio_to_baseline`) and z-score (:func:`zscore_to_baseline`)
helpers are retained for figure-tier consumers + diagnostic plots; they
are NOT the default for inferential models.

Baseline = pre-stroke rows (``epoch_label == "pre"``) by default,
configurable via ``baseline_label``. Sentinel rows (``is_sentinel ==
True``) are dropped from baseline aggregation but PASS THROUGH the
normalization step with ``value_norm = NaN`` so the output row count
matches input row count exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


_DEFAULT_GROUP_COLS: tuple[str, ...] = ("animal",)
_DEFAULT_VALUE_COL: str = "value"
_DEFAULT_BASELINE_LABEL: str = "pre"


def per_animal_baseline_stats(
    inputs_df: pd.DataFrame,
    *,
    group_cols: Sequence[str] = _DEFAULT_GROUP_COLS,
    value_col: str = _DEFAULT_VALUE_COL,
    baseline_label: str = _DEFAULT_BASELINE_LABEL,
) -> pd.DataFrame:
    """Compute per-group baseline statistics from pre-stroke rows.

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Long-format stats inputs. Required columns:
        ``epoch_label`` (str), ``is_sentinel`` (bool),
        the columns in ``group_cols``, and ``value_col``.
    group_cols : Sequence[str], default ("animal",)
        Columns to group by when computing the baseline. For per-side
        endpoints (e.g. ``lick_switch_rate`` with side='L'/'R'), pass
        ``group_cols=("animal", "side")``. For spatial endpoints with
        side='global', the default ``("animal",)`` is correct.
    value_col : str, default "value"
        Numeric column whose baseline stats are computed.
    baseline_label : str, default "pre"
        Value of ``epoch_label`` that defines baseline. Typically "pre"
        for stroke recovery analyses.

    Returns
    -------
    pd.DataFrame
        One row per unique combination of ``group_cols`` values present
        in baseline rows. Columns: ``group_cols`` + ``baseline_mean,
        baseline_std, baseline_median, baseline_n``.

        Groups with zero non-sentinel baseline rows are OMITTED — the
        caller (typically :func:`difference_from_baseline` et al.) joins
        on ``group_cols`` so omitted groups propagate as NaN in the
        normalized output.

    Notes
    -----
    Standard deviation is computed with ``ddof=1`` (sample SD). For
    groups with ``baseline_n == 1``, ``baseline_std`` is NaN (not zero).
    Downstream :func:`zscore_to_baseline` propagates this NaN, so 1-row
    baselines yield NaN z-scores — preferable to silently dividing by
    zero or by a degenerate population SD.
    """
    required = {"epoch_label", "is_sentinel", value_col, *group_cols}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}; "
            f"got columns {list(inputs_df.columns)}.",
        )

    mask = (
        (inputs_df["epoch_label"] == baseline_label)
        & (~inputs_df["is_sentinel"].astype(bool))
        & (inputs_df[value_col].notna())
    )
    baseline = inputs_df.loc[mask]
    if baseline.empty:
        return pd.DataFrame(
            columns=list(group_cols)
            + ["baseline_mean", "baseline_std", "baseline_median", "baseline_n"],
        )

    grouped = baseline.groupby(list(group_cols), dropna=False)[value_col]
    stats = grouped.agg(
        baseline_mean="mean",
        baseline_std=lambda s: s.std(ddof=1),
        baseline_median="median",
        baseline_n="count",
    ).reset_index()
    return stats


def _merge_baseline(
    inputs_df: pd.DataFrame,
    baseline_stats: pd.DataFrame,
    group_cols: Sequence[str],
) -> pd.DataFrame:
    """Left-join inputs_df with baseline_stats on group_cols.

    Groups absent from baseline_stats propagate as NaN, so downstream
    normalization on those rows yields NaN ``value_norm``. This keeps
    the output row count == input row count (no silent row drop) and
    surfaces missing-baseline groups via NaN inspection.
    """
    return inputs_df.merge(baseline_stats, on=list(group_cols), how="left")


def difference_from_baseline(
    inputs_df: pd.DataFrame,
    *,
    group_cols: Sequence[str] = _DEFAULT_GROUP_COLS,
    value_col: str = _DEFAULT_VALUE_COL,
    baseline_stats: pd.DataFrame | None = None,
    baseline_label: str = _DEFAULT_BASELINE_LABEL,
) -> pd.DataFrame:
    """Additive baseline correction — canonical Task 4 LMM input.

    Returns a copy of ``inputs_df`` with a new ``value_norm`` column
    equal to ``value - baseline_mean`` (per-group baseline mean joined
    from :func:`per_animal_baseline_stats`).

    Per Addendum #6: additive is the canonical default for inferential
    models. It keeps the residual on the same scale across animals and
    avoids inflating variance on animals with small baseline values
    (which multiplicative ratios would do).

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Long-format stats inputs.
    group_cols : Sequence[str], default ("animal",)
        Pass-through to :func:`per_animal_baseline_stats` if
        ``baseline_stats`` is None.
    value_col : str, default "value"
    baseline_stats : pd.DataFrame, optional
        Precomputed baseline stats from
        :func:`per_animal_baseline_stats`. If None, computed inline.
    baseline_label : str, default "pre"
        Forwarded to :func:`per_animal_baseline_stats` when computing
        inline. Ignored if ``baseline_stats`` is provided.

    Returns
    -------
    pd.DataFrame
        Original columns + ``baseline_mean, baseline_std,
        baseline_median, baseline_n, value_norm`` (the last = ``value -
        baseline_mean``).

    Notes
    -----
    Sentinel rows (``is_sentinel=True``) pass through; their
    ``value_norm`` becomes NaN naturally because ``value`` is NaN for
    sentinels.
    """
    if baseline_stats is None:
        baseline_stats = per_animal_baseline_stats(
            inputs_df,
            group_cols=group_cols,
            value_col=value_col,
            baseline_label=baseline_label,
        )
    merged = _merge_baseline(inputs_df, baseline_stats, group_cols)
    merged["value_norm"] = merged[value_col] - merged["baseline_mean"]
    return merged


def zscore_to_baseline(
    inputs_df: pd.DataFrame,
    *,
    group_cols: Sequence[str] = _DEFAULT_GROUP_COLS,
    value_col: str = _DEFAULT_VALUE_COL,
    baseline_stats: pd.DataFrame | None = None,
    baseline_label: str = _DEFAULT_BASELINE_LABEL,
) -> pd.DataFrame:
    """Standardize each row against per-group baseline mean + SD.

    Returns ``value_norm = (value - baseline_mean) / baseline_std``.

    Useful for cross-endpoint comparisons (e.g. heatmap rows where each
    endpoint has very different native units) and for diagnostic plots.
    NOT the canonical LMM input — :func:`difference_from_baseline` is.

    Groups with ``baseline_n == 1`` produce ``baseline_std = NaN`` →
    ``value_norm = NaN`` for that group's rows. This is a deliberate
    safety: a single-baseline-row group has no within-group variance
    estimate, so z-scoring is undefined.

    Parameters mirror :func:`difference_from_baseline`.
    """
    if baseline_stats is None:
        baseline_stats = per_animal_baseline_stats(
            inputs_df,
            group_cols=group_cols,
            value_col=value_col,
            baseline_label=baseline_label,
        )
    merged = _merge_baseline(inputs_df, baseline_stats, group_cols)
    merged["value_norm"] = (
        merged[value_col] - merged["baseline_mean"]
    ) / merged["baseline_std"]
    return merged


def ratio_to_baseline(
    inputs_df: pd.DataFrame,
    *,
    group_cols: Sequence[str] = _DEFAULT_GROUP_COLS,
    value_col: str = _DEFAULT_VALUE_COL,
    baseline_stats: pd.DataFrame | None = None,
    baseline_label: str = _DEFAULT_BASELINE_LABEL,
) -> pd.DataFrame:
    """Multiplicative baseline correction — ``value_norm = value / baseline_mean``.

    Retained for figure-tier consumers that explicitly want
    proportional change (e.g. "lick rate at 7 days post is 0.3x baseline").
    NOT the canonical LMM input — see :func:`difference_from_baseline`.

    Returns NaN ``value_norm`` when ``baseline_mean == 0`` (no false
    inf/nan propagation; the row is flagged so caller can inspect).

    Parameters mirror :func:`difference_from_baseline`.
    """
    if baseline_stats is None:
        baseline_stats = per_animal_baseline_stats(
            inputs_df,
            group_cols=group_cols,
            value_col=value_col,
            baseline_label=baseline_label,
        )
    merged = _merge_baseline(inputs_df, baseline_stats, group_cols)
    # Zero-baseline rows -> NaN (not inf). Replace 0 -> NaN before divide.
    safe_baseline = merged["baseline_mean"].where(
        merged["baseline_mean"] != 0, other=np.nan,
    )
    merged["value_norm"] = merged[value_col] / safe_baseline
    return merged


def log1p_transform(
    inputs_df: pd.DataFrame,
    *,
    value_col: str = _DEFAULT_VALUE_COL,
    out_col: str = "value_log1p",
) -> pd.DataFrame:
    """Stabilize variance for skewed counts: ``out = log(1 + value)``.

    Common preprocessing step for count-like endpoints (e.g.
    ``num_correct_licks_per_trial``, ``tongue_n_right``) before LMM
    fitting. Adds ``out_col`` to the DataFrame; does not modify
    ``value_col``.

    Numpy ``log1p`` semantics for negative inputs: ``value < -1`` →
    NaN; ``value == -1`` → ``-inf``; ``value > -1`` → real. Sentinel
    rows pass through; ``value_log1p`` becomes NaN naturally because
    ``value`` is NaN.

    Parameters
    ----------
    inputs_df : pd.DataFrame
    value_col : str, default "value"
        Column to transform.
    out_col : str, default "value_log1p"
        Output column name.
    """
    if value_col not in inputs_df.columns:
        raise ValueError(
            f"value_col {value_col!r} not in inputs_df columns "
            f"{list(inputs_df.columns)}.",
        )
    out = inputs_df.copy()
    # np.log1p on (value < -1) returns NaN with a RuntimeWarning;
    # value == -1 returns -inf with a divide-by-zero warning. Both
    # warnings reflect documented behavior — suppress so callers don't
    # get noise on every batch normalization.
    with np.errstate(invalid="ignore", divide="ignore"):
        out[out_col] = np.log1p(out[value_col].to_numpy(dtype=float))
    return out


def rank_within_animal(
    inputs_df: pd.DataFrame,
    *,
    group_cols: Sequence[str] = _DEFAULT_GROUP_COLS,
    value_col: str = _DEFAULT_VALUE_COL,
    out_col: str = "value_rank",
    method: str = "average",
) -> pd.DataFrame:
    """Convert values to within-group ranks (default: per animal).

    Useful for non-parametric mixed-effects approximations + for
    rank-transformed permutation tests on heavily-skewed endpoints
    where the parametric LMM assumption is shaky.

    Sentinel rows (``is_sentinel=True``) and NaN values participate
    in the rank only as NaN -- they keep their NaN ``value_rank``,
    which pandas's :meth:`groupby.rank` honors when ``na_option`` is
    its default "keep" (NaNs stay NaN, not assigned a rank).

    Parameters
    ----------
    inputs_df : pd.DataFrame
    group_cols : Sequence[str], default ("animal",)
        Within-group rank computation. For per-side comparisons pass
        ``("animal", "side")``.
    value_col : str, default "value"
    out_col : str, default "value_rank"
    method : str, default "average"
        Forwarded to :meth:`pandas.Series.rank` -- typical alternatives
        ``"min"``, ``"dense"``, ``"first"``. ``"average"`` matches the
        scipy default for tied ranks.
    """
    out = inputs_df.copy()
    out[out_col] = out.groupby(list(group_cols), dropna=False)[value_col].rank(
        method=method, na_option="keep",
    )
    return out
