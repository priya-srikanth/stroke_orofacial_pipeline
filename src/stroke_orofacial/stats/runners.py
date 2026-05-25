"""Phase 9 Task 4 per-axis runners with multi-granularity dispatch.

Each runner consumes a long-format stats-inputs DataFrame (from Phase 9
Commit A/B/C materialization) and dispatches to the appropriate
``fit_*`` model wrapper based on (axis, granularity, value_type).
Returns a single :class:`FitResult` (or a list of them when run across
multiple endpoints / granularities).

Dispatch (per Addenda #4 + #5 + #6):

- **scalar_per_session / scalar_per_trial / bool_per_trial** →
  standard fit functions
  (:func:`~models.fit_paired_pre_post_wilcoxon`,
  :func:`~models.fit_recovery_mixedlm`,
  :func:`~models.fit_ipsi_contra_wilcoxon`,
  :func:`~models.fit_trial_group_friedman`)
- **vector_per_session** (e.g. ``latency_hist``) → KS distribution-
  shape test (:func:`~models.fit_pre_post_ks_distribution_shape`,
  Addendum #4)
- **scalar_per_animal_time** (spatial endpoints, 48 slugs) →
  :func:`~models.fit_recovery_mixedlm` at ``per_bin`` granularity;
  ``per_session`` uses raw values (no per-animal baseline subtraction
  for spatial — the leave-one-out pre-stroke noise floor IS the
  baseline reference in the raw values per Addendum #6)
- **vector_per_trial** → SKIP (not primary per the inventory's
  is_primary=false flag for all vector_per_trial endpoints)

Granularity (per Addendum #6 revision of Addendum #5):

- ``per_session`` — one row per (animal, date) ; raw input
- ``per_bin`` — bin per-session rows by ``cohort_bin_size`` days
- ``per_epoch`` — RUNTIME view (NOT a separate emit granularity); filter
  per_session rows by ``epoch_label`` + apply additive baseline
  normalization (:func:`~normalization.difference_from_baseline`); fit
  with :func:`~models.fit_per_epoch_lmm`

Confirmatory dispatch (per Addendum #5): when ``is_confirmatory=True``,
emit both BH-FDR and Bonferroni-corrected p-values at the
confirmatory granularity (default per_session for non-spatial; per_bin
for spatial).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from scipy.stats import ks_2samp

from stroke_orofacial.stats.models import (
    FitResult,
    fit_ipsi_contra_wilcoxon,
    fit_paired_pre_post_wilcoxon,
    fit_per_epoch_lmm,
    fit_pre_post_ks_distribution_shape,
    fit_recovery_mixedlm,
    fit_trial_group_friedman,
)


Axis = Literal["pre_post", "recovery", "ipsi_contra", "trial_group"]
Granularity = Literal["per_session", "per_bin", "per_epoch"]
ValueType = Literal[
    "scalar_per_session", "scalar_per_trial", "bool_per_trial",
    "scalar_per_session_trial_group", "scalar_per_animal_time",
    "vector_per_session", "vector_per_trial",
    "trajectory_per_animal", "categorical_per_trial",
]


# Value types skipped at axis-runner level. Per Phase 9 inventory:
# vector_per_trial endpoints are all is_primary=false (held for figures,
# not stats); trajectory_per_animal + categorical_per_trial are out-of-
# scope for the 4 standard axes.
_SKIPPED_VALUE_TYPES: frozenset[str] = frozenset({
    "vector_per_trial", "trajectory_per_animal", "categorical_per_trial",
})


# Spatial endpoints: scalar_per_animal_time. The pre-stroke baseline is
# already encoded in the raw values via the leave-one-out pre-pool
# computation in materialize_spatial.py (Addendum #6 D). So the runner
# fits directly on raw value; no per-animal additive normalization.
_SPATIAL_VALUE_TYPE: str = "scalar_per_animal_time"


def _aggregate_per_session_to_per_bin(
    inputs_df: pd.DataFrame,
    *,
    value_col: str = "value",
    bin_size_col: str = "cohort_bin_size",
    group_cols: tuple[str, ...] = ("animal", "side"),
) -> pd.DataFrame:
    """Aggregate per_session rows to per_bin via cohort_bin_size grouping.

    For spatial endpoints with `granularity == "per_bin"` already
    materialized (rows where ``granularity`` column exists and equals
    ``"per_bin"``), this function is a no-op filter rather than an
    aggregation — caller passes the spatial subset through.

    For non-spatial endpoints: groups per_session rows by
    ``(animal, *group_cols, ceil(rel_day / cohort_bin_size))`` and
    averages ``value_col`` within each bin.

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Long-format stats inputs (per_session granularity).
    value_col : str, default "value"
    bin_size_col : str, default "cohort_bin_size"
        Column carrying each animal's bin width (typically constant
        per-animal at 7 days).
    group_cols : tuple[str], default ("animal", "side")
        Carry-forward columns beyond animal — typically (animal, side)
        for per-side endpoints; pass ("animal",) for spatial.

    Returns
    -------
    pd.DataFrame
        Same columns as input + a ``bin_idx`` column; one row per
        (animal, *group_cols, bin_idx) with averaged ``value_col``.
    """
    if "granularity" in inputs_df.columns and (
        inputs_df["granularity"] == "per_bin"
    ).any():
        # Spatial path: rows already carry per_bin tag; filter.
        return inputs_df[inputs_df["granularity"] == "per_bin"].copy()

    df = inputs_df.copy()
    if "rel_day" not in df.columns or bin_size_col not in df.columns:
        raise ValueError(
            f"inputs_df missing 'rel_day' or '{bin_size_col}' columns; "
            f"got {list(df.columns)}",
        )
    # bin_idx: ceil(rel_day / cohort_bin_size). For rel_day <= 0, bin_idx
    # is <= 0 (pre-stroke bins).
    df["bin_idx"] = np.ceil(
        df["rel_day"].astype(float) / df[bin_size_col].astype(float)
    ).astype("Int64")
    grouped = df.groupby(
        ["animal", *group_cols, "bin_idx"], dropna=False,
    )[value_col].mean().reset_index()
    return grouped


def _ks_on_flat_per_trial(
    inputs_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value",
    epoch_col: str = "epoch_label",
    pre_label: str = "pre",
) -> FitResult:
    """KS test on flat per-trial parquet (vector_per_session emit choice).

    Pools the scalar ``value_col`` across pre rows + post rows
    (excluding sentinels + NaN) and runs scipy's ``ks_2samp``. Returns
    a FitResult with ``model_name="pre_post_ks_distribution_shape"``
    so downstream consumers don't distinguish the schema bridge.
    """
    pre_mask = (
        (inputs_df[epoch_col] == pre_label)
        & inputs_df[value_col].notna()
        & (~inputs_df["is_sentinel"].astype(bool) if "is_sentinel" in inputs_df.columns
           else pd.Series(True, index=inputs_df.index))
    )
    post_mask = (
        (inputs_df[epoch_col] == post_epoch)
        & inputs_df[value_col].notna()
        & (~inputs_df["is_sentinel"].astype(bool) if "is_sentinel" in inputs_df.columns
           else pd.Series(True, index=inputs_df.index))
    )
    pre = inputs_df.loc[pre_mask, value_col].to_numpy(dtype=float)
    post = inputs_df.loc[post_mask, value_col].to_numpy(dtype=float)
    if pre.size == 0 or post.size == 0:
        return FitResult(
            model_name="pre_post_ks_distribution_shape",
            statistic=float("nan"), p_value=float("nan"),
            n_observations=int(pre.size + post.size),
            details={
                "status": "insufficient_data",
                "post_epoch": post_epoch,
                "n_pre_samples": int(pre.size),
                "n_post_samples": int(post.size),
                "schema": "flat_per_trial",
            },
        )
    res = ks_2samp(pre, post, alternative="two-sided")
    return FitResult(
        model_name="pre_post_ks_distribution_shape",
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        n_observations=int(pre.size + post.size),
        details={
            "status": "ok", "post_epoch": post_epoch,
            "n_pre_samples": int(pre.size),
            "n_post_samples": int(post.size),
            "schema": "flat_per_trial",
        },
    )


def _filter_to_per_session(inputs_df: pd.DataFrame) -> pd.DataFrame:
    """Filter spatial-emit rows to per_session granularity (no-op for
    non-spatial inputs where ``granularity`` column doesn't exist)."""
    if "granularity" in inputs_df.columns and (
        inputs_df["granularity"] == "per_session"
    ).any():
        return inputs_df[inputs_df["granularity"] == "per_session"].copy()
    return inputs_df


@dataclass(frozen=True)
class AxisRunnerSpec:
    """Identifies (axis, granularity, value_type) for runner dispatch."""
    axis: Axis
    granularity: Granularity
    value_type: ValueType
    is_confirmatory: bool = False


def _skip(spec: AxisRunnerSpec, reason: str) -> FitResult:
    """Build a NaN FitResult tagged with the runner spec + skip reason."""
    return FitResult(
        model_name=f"{spec.axis}_{spec.granularity}",
        statistic=float("nan"),
        p_value=float("nan"),
        n_observations=0,
        details={
            "status": "skipped",
            "reason": reason,
            "axis": spec.axis,
            "granularity": spec.granularity,
            "value_type": spec.value_type,
            "is_confirmatory": spec.is_confirmatory,
        },
    )


# ---------------------------------------------------------------------------
# Per-axis runners
# ---------------------------------------------------------------------------

def run_pre_post(
    inputs_df: pd.DataFrame,
    *,
    granularity: Granularity = "per_session",
    value_type: ValueType = "scalar_per_session",
    is_confirmatory: bool = False,
    post_epoch: str = "acute",
    aggregator: str = "mean",
) -> FitResult:
    """Pre-stroke vs post-stroke comparison axis.

    Dispatch:

    - ``value_type="vector_per_session"`` (latency_hist) →
      :func:`fit_pre_post_ks_distribution_shape`
    - scalar value types → :func:`fit_paired_pre_post_wilcoxon`
    - skipped value types → NaN FitResult tagged ``status="skipped"``

    Granularity effect:

    - ``per_session`` / ``per_bin`` / ``per_epoch`` all aggregate to
      one (pre, post_epoch) pair per animal before pairing; the choice
      controls only WHICH post-stroke rows enter the post pool.

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Long-format stats inputs.
    granularity : str
        For now identical pairing per the kickoff; differs in which
        post-stroke rows are pooled. Reserved for future granularity-
        specific aggregation choices.
    value_type : str
        From the endpoint inventory.
    is_confirmatory : bool
        Forwarded into ``details`` for downstream BH/Bonferroni
        partition.
    post_epoch : str, default "acute"
        Forwarded to the underlying fit functions.
    aggregator : str, default "mean"

    Returns
    -------
    FitResult
        ``model_name`` carries the underlying fit's name; ``details``
        includes ``axis="pre_post"``, ``granularity``, and
        ``is_confirmatory`` so downstream FDR/Bonferroni can partition.
    """
    spec = AxisRunnerSpec(
        axis="pre_post", granularity=granularity,
        value_type=value_type, is_confirmatory=is_confirmatory,
    )
    if value_type in _SKIPPED_VALUE_TYPES:
        return _skip(spec, f"value_type={value_type} not supported for pre_post axis")

    df = _filter_to_per_session(inputs_df)

    if value_type == "vector_per_session":
        # Addendum #4 emit choice: latency_hist parquet uses a flat
        # per-trial schema (one row per trial, scalar ``value``) rather
        # than a per-session vector-valued ``value_vector`` column.
        # Pool the scalar values across all pre rows + all post rows
        # (excluding sentinels) and call ks_2samp directly. Falls back
        # to :func:`fit_pre_post_ks_distribution_shape` for the
        # alternative ``value_vector`` schema if that's what the
        # caller provides.
        if "value_vector" in df.columns:
            result = fit_pre_post_ks_distribution_shape(
                df, post_epoch=post_epoch,
            )
        else:
            result = _ks_on_flat_per_trial(df, post_epoch=post_epoch)
    else:
        result = fit_paired_pre_post_wilcoxon(
            df, post_epoch=post_epoch, aggregator=aggregator,
        )
    # Augment details with axis + granularity tags.
    new_details = {
        **result.details,
        "axis": "pre_post",
        "granularity": granularity,
        "value_type": value_type,
        "is_confirmatory": is_confirmatory,
    }
    return FitResult(
        model_name=result.model_name,
        statistic=result.statistic,
        p_value=result.p_value,
        n_observations=result.n_observations,
        details=new_details,
    )


def run_recovery(
    inputs_df: pd.DataFrame,
    *,
    granularity: Granularity = "per_session",
    value_type: ValueType = "scalar_per_session",
    is_confirmatory: bool = False,
) -> FitResult:
    """Recovery slope axis — value ~ rel_day + (1 | animal).

    Dispatch:

    - Spatial endpoints (``value_type="scalar_per_animal_time"``):
      uses raw values directly (Addendum #6 D — LOO pre-stroke baseline
      is already in the raw values; no additive normalization).
    - Other scalar types: also fits raw value; per-animal random
      intercept absorbs baseline differences.
    - ``vector_per_session`` / ``vector_per_trial`` / etc → skip.

    Granularity:

    - ``per_session`` — raw per-session rows enter the LMM (rel_day
      is days-post-stroke). Post-stroke only (include_pre=False) is
      the default; pass include_pre=True via a future kwarg if you
      want pre rows in the fit.
    - ``per_bin`` — bin per_session rows first, fit on bin-aggregated
      values. For spatial endpoints this uses the materialized
      ``granularity == "per_bin"`` rows directly.
    - ``per_epoch`` — special: delegates to :func:`fit_per_epoch_lmm`
      via :func:`run_per_epoch`, but with the ``recovery`` axis tag.
    """
    spec = AxisRunnerSpec(
        axis="recovery", granularity=granularity,
        value_type=value_type, is_confirmatory=is_confirmatory,
    )
    if value_type in _SKIPPED_VALUE_TYPES:
        return _skip(spec, f"value_type={value_type} not supported for recovery axis")

    if granularity == "per_epoch":
        return run_per_epoch(
            inputs_df, axis="recovery",
            value_type=value_type, is_confirmatory=is_confirmatory,
        )

    if granularity == "per_bin":
        df = _aggregate_per_session_to_per_bin(
            inputs_df, group_cols=(),
        )
        # Per_bin DataFrames use bin_idx as the rel_day proxy.
        if "bin_idx" in df.columns:
            df = df.rename(columns={"bin_idx": "rel_day"})
    else:
        df = _filter_to_per_session(inputs_df)

    result = fit_recovery_mixedlm(df)
    new_details = {
        **result.details,
        "axis": "recovery",
        "granularity": granularity,
        "value_type": value_type,
        "is_confirmatory": is_confirmatory,
    }
    return FitResult(
        model_name=result.model_name,
        statistic=result.statistic,
        p_value=result.p_value,
        n_observations=result.n_observations,
        details=new_details,
    )


def run_ipsi_contra(
    inputs_df: pd.DataFrame,
    *,
    granularity: Granularity = "per_session",
    value_type: ValueType = "scalar_per_session",
    is_confirmatory: bool = False,
    epoch: str | None = None,
) -> FitResult:
    """Ipsi vs contra side axis — paired Wilcoxon per animal.

    Requires inputs with ``ipsi_contra`` column populated (typically
    set in materialize_inputs.py from the per-animal L/R-to-ipsi/contra
    mapping in animals.yaml). Endpoints with ``side="global"`` skip
    this axis.
    """
    spec = AxisRunnerSpec(
        axis="ipsi_contra", granularity=granularity,
        value_type=value_type, is_confirmatory=is_confirmatory,
    )
    if value_type in _SKIPPED_VALUE_TYPES:
        return _skip(spec, f"value_type={value_type} not supported for ipsi_contra axis")

    df = _filter_to_per_session(inputs_df)
    if "ipsi_contra" not in df.columns:
        return _skip(spec, "inputs_df has no ipsi_contra column")
    if (df["ipsi_contra"] == "global").all():
        return _skip(spec, "all rows have ipsi_contra='global' (side-blind endpoint)")

    result = fit_ipsi_contra_wilcoxon(df, epoch=epoch)
    new_details = {
        **result.details,
        "axis": "ipsi_contra",
        "granularity": granularity,
        "value_type": value_type,
        "is_confirmatory": is_confirmatory,
    }
    return FitResult(
        model_name=result.model_name,
        statistic=result.statistic,
        p_value=result.p_value,
        n_observations=result.n_observations,
        details=new_details,
    )


def run_trial_group(
    inputs_df: pd.DataFrame,
    *,
    granularity: Granularity = "per_session",
    value_type: ValueType = "scalar_per_session",
    is_confirmatory: bool = False,
    epoch: str | None = None,
    groups: tuple[str, ...] = ("L", "R", "all"),
) -> FitResult:
    """Trial-group comparison axis — Friedman across L / R / all.

    Per Task 3 deviation #1: requires >= 3 groups. For 2-group L/R
    endpoints (e.g. lick_switch_rate), this axis is not applicable;
    caller should use the ipsi_contra axis instead. The runner
    surfaces the 2-group case as ``status="skipped"``.
    """
    spec = AxisRunnerSpec(
        axis="trial_group", granularity=granularity,
        value_type=value_type, is_confirmatory=is_confirmatory,
    )
    if value_type in _SKIPPED_VALUE_TYPES:
        return _skip(spec, f"value_type={value_type} not supported for trial_group axis")
    if len(groups) < 3:
        return _skip(
            spec,
            f"trial_group axis requires >=3 groups; got {len(groups)} ({list(groups)})",
        )

    df = _filter_to_per_session(inputs_df)
    result = fit_trial_group_friedman(df, epoch=epoch, groups=groups)
    new_details = {
        **result.details,
        "axis": "trial_group",
        "granularity": granularity,
        "value_type": value_type,
        "is_confirmatory": is_confirmatory,
    }
    return FitResult(
        model_name=result.model_name,
        statistic=result.statistic,
        p_value=result.p_value,
        n_observations=result.n_observations,
        details=new_details,
    )


def run_per_epoch(
    inputs_df: pd.DataFrame,
    *,
    axis: Axis = "pre_post",
    value_type: ValueType = "scalar_per_session",
    is_confirmatory: bool = False,
    apply_additive_baseline: bool | None = None,
) -> FitResult:
    """Per-epoch LMM runner (Addendum #6).

    Filters to post-stroke rows + apply additive baseline subtraction
    (per animal) + fits ``value ~ C(epoch_label) + (1|animal)``.

    Per Task 3 deviation #2: with ``apply_additive_baseline=True`` AND
    only 2 epoch levels (pre + 1 post), the LMM hits a singular matrix
    because reference-level rows become zero-mean per animal. Caller
    falls back to :func:`run_pre_post` for that case.

    Spatial endpoints (``scalar_per_animal_time``): the LOO pre-stroke
    baseline is already in raw values, so ``apply_additive_baseline``
    defaults to False for those. For non-spatial scalar endpoints it
    defaults to True (the canonical Addendum #6 choice).

    Parameters
    ----------
    inputs_df : pd.DataFrame
    axis : Axis, default "pre_post"
        Logical axis label propagated to ``details`` for downstream
        FDR/Bonferroni partition. The same LMM fit serves both
        ``pre_post`` and ``recovery`` per_epoch runners by design.
    value_type : ValueType
    is_confirmatory : bool
    apply_additive_baseline : bool, optional
        Override the default (False for spatial, True otherwise).
    """
    spec = AxisRunnerSpec(
        axis=axis, granularity="per_epoch",
        value_type=value_type, is_confirmatory=is_confirmatory,
    )
    if value_type in _SKIPPED_VALUE_TYPES:
        return _skip(spec, f"value_type={value_type} not supported for per_epoch")
    if apply_additive_baseline is None:
        apply_additive_baseline = value_type != _SPATIAL_VALUE_TYPE

    df = _filter_to_per_session(inputs_df)
    result = fit_per_epoch_lmm(
        df, apply_additive_baseline=apply_additive_baseline,
    )
    new_details = {
        **result.details,
        "axis": axis,
        "granularity": "per_epoch",
        "value_type": value_type,
        "is_confirmatory": is_confirmatory,
    }
    return FitResult(
        model_name=result.model_name,
        statistic=result.statistic,
        p_value=result.p_value,
        n_observations=result.n_observations,
        details=new_details,
    )


# ---------------------------------------------------------------------------
# Dispatch map
# ---------------------------------------------------------------------------

_AXIS_RUNNERS: dict[str, Callable[..., FitResult]] = {
    "pre_post": run_pre_post,
    "recovery": run_recovery,
    "ipsi_contra": run_ipsi_contra,
    "trial_group": run_trial_group,
}


def run_axis_for_endpoint(
    inputs_df: pd.DataFrame,
    *,
    axis: Axis,
    granularity: Granularity,
    value_type: ValueType,
    is_confirmatory: bool = False,
    **kwargs,
) -> FitResult:
    """Dispatch to the correct axis runner.

    Convenience entry point for CLI drivers that read
    ``endpoint_inventory.csv`` and need a single dispatch call.
    Extra kwargs forward to the underlying runner.
    """
    if axis not in _AXIS_RUNNERS:
        raise ValueError(
            f"axis must be one of {list(_AXIS_RUNNERS)}; got {axis!r}.",
        )
    if granularity == "per_epoch":
        return run_per_epoch(
            inputs_df, axis=axis,
            value_type=value_type, is_confirmatory=is_confirmatory,
        )
    runner = _AXIS_RUNNERS[axis]
    return runner(
        inputs_df, granularity=granularity, value_type=value_type,
        is_confirmatory=is_confirmatory, **kwargs,
    )
