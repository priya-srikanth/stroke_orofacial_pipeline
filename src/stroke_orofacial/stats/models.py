"""Statistical model wrappers for Phase 9 Task 4 hypothesis tests.

Each ``fit_*`` function takes a long-format DataFrame (typically the
output of Phase 9 Commit A/B/C materialization, optionally normalized
via :mod:`stroke_orofacial.stats.normalization`) and returns a
:class:`FitResult` with a uniform schema. Downstream pipeline code
collects FitResults into a results DataFrame, then applies
multiple-comparisons correction via
:mod:`stroke_orofacial.stats.multiple_comparisons`.

Model dispatch (kickoff + Addenda):

- :func:`fit_paired_pre_post_wilcoxon` — paired Wilcoxon signed-rank
  on pre-stroke baseline vs a post-stroke epoch (acute / sub_acute /
  chronic), one pair per animal.
- :func:`fit_recovery_mixedlm` — mixed-effects linear model with
  rel_day as a fixed slope and animal as a random intercept.
- :func:`fit_ipsi_contra_wilcoxon` — paired Wilcoxon for ipsi vs
  contra side comparisons within a single epoch.
- :func:`fit_trial_group_friedman` — Friedman test across L / R / all
  trial groups within an animal × epoch.
- :func:`fit_pre_post_ks_distribution_shape` (Addendum #4) — KS test
  on the distribution shape of vector_per_session endpoints (e.g.
  ``latency_hist``) between pre and post.
- :func:`fit_per_epoch_lmm` (Addendum #6) — per-epoch LMM with
  additive baseline normalization; tests whether the per-epoch mean
  differs from baseline (intercept-only design with epoch fixed
  effect).

All ``fit_*`` functions are robust to small-n cases: they return
``FitResult(... p_value=NaN, statistic=NaN, ...)`` rather than raising,
when there isn't enough data to compute a meaningful test. The caller
distinguishes "no data" via ``np.isnan(result.p_value)`` and via
``result.details["status"]``.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, ks_2samp, wilcoxon


@dataclass(frozen=True)
class FitResult:
    """Uniform result schema for all ``fit_*`` model wrappers.

    Attributes
    ----------
    model_name : str
        Human-readable identifier (e.g. ``"paired_pre_post_wilcoxon"``,
        ``"recovery_mixedlm"``). Used for results-table provenance.
    statistic : float
        Test statistic. ``W`` for Wilcoxon, chi-squared for Friedman,
        ``D`` for KS, fixed-effect coefficient for LMM. NaN when the
        fit couldn't be computed.
    p_value : float
        Two-sided p-value (or one-sided per the model). NaN when
        unavailable.
    n_observations : int
        Number of observations entering the test. For paired tests,
        the number of pairs.
    details : dict
        Model-specific extras: per-coefficient SE / CI for LMM,
        alternative-hypothesis label, convergence flag, etc. Always
        contains ``"status": str`` — one of ``"ok"``, ``"insufficient
        _data"``, ``"singular"``, ``"convergence_failed"``.
    """
    model_name: str
    statistic: float
    p_value: float
    n_observations: int
    details: dict[str, Any] = field(default_factory=dict)


def _empty_result(
    model_name: str, *, status: str, n: int = 0, **extras: Any,
) -> FitResult:
    """Build a NaN-result for insufficient-data / failure cases."""
    return FitResult(
        model_name=model_name,
        statistic=float("nan"),
        p_value=float("nan"),
        n_observations=n,
        details={"status": status, **extras},
    )


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank: paired pre vs post
# ---------------------------------------------------------------------------

def fit_paired_pre_post_wilcoxon(
    inputs_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value",
    animal_col: str = "animal",
    epoch_col: str = "epoch_label",
    pre_label: str = "pre",
    aggregator: str = "mean",
) -> FitResult:
    """Wilcoxon signed-rank test on paired (pre, post_epoch) per-animal aggregates.

    For each animal, aggregates the pre-stroke values with ``aggregator``
    (default mean) and the post-stroke ``post_epoch`` values with the
    same aggregator. Then pairs the two per-animal aggregates and runs
    a paired Wilcoxon signed-rank test.

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Long-format inputs. Requires ``animal_col``, ``epoch_col``,
        ``value_col``.
    post_epoch : str
        Value of ``epoch_col`` for the post-stroke side of the pair
        (typically ``"acute"``, ``"sub_acute"``, or ``"chronic"``).
    value_col, animal_col, epoch_col, pre_label : str
        Column / label overrides.
    aggregator : {"mean", "median"}, default "mean"
        Per-animal aggregator before pairing.

    Returns
    -------
    FitResult
        ``model_name = "paired_pre_post_wilcoxon"``. NaN p-value
        (status=``"insufficient_data"``) when fewer than 2 animals
        have BOTH pre and post observations.

    Notes
    -----
    The Wilcoxon signed-rank test requires at least one non-zero
    difference. If all paired differences are zero, scipy raises;
    we catch and return ``p_value = 1.0, status = "all_zero_diffs"``.
    """
    model_name = "paired_pre_post_wilcoxon"
    if aggregator not in ("mean", "median"):
        raise ValueError(f"aggregator must be 'mean' or 'median'; got {aggregator!r}.")
    required = {animal_col, epoch_col, value_col}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )

    grouped = inputs_df.groupby([animal_col, epoch_col])[value_col].agg(aggregator)
    wide = grouped.unstack(epoch_col)
    if pre_label not in wide.columns or post_epoch not in wide.columns:
        return _empty_result(model_name, status="insufficient_data", n=0)
    paired = wide[[pre_label, post_epoch]].dropna()
    n = len(paired)
    if n < 2:
        return _empty_result(model_name, status="insufficient_data", n=n)
    diffs = paired[post_epoch].to_numpy() - paired[pre_label].to_numpy()
    if np.all(diffs == 0):
        return FitResult(
            model_name=model_name,
            statistic=0.0,
            p_value=1.0,
            n_observations=n,
            details={"status": "all_zero_diffs", "post_epoch": post_epoch},
        )
    res = wilcoxon(paired[post_epoch], paired[pre_label], alternative="two-sided")
    return FitResult(
        model_name=model_name,
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        n_observations=n,
        details={
            "status": "ok",
            "post_epoch": post_epoch,
            "aggregator": aggregator,
            "median_diff": float(np.median(diffs)),
        },
    )


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank: paired ipsi vs contra
# ---------------------------------------------------------------------------

def fit_ipsi_contra_wilcoxon(
    inputs_df: pd.DataFrame,
    *,
    epoch: str | None = None,
    value_col: str = "value",
    animal_col: str = "animal",
    ipsi_contra_col: str = "ipsi_contra",
    epoch_col: str = "epoch_label",
    aggregator: str = "mean",
) -> FitResult:
    """Paired Wilcoxon for ipsi vs contra side comparison.

    Aggregates each animal's ipsi and contra values (optionally within
    a single ``epoch``), pairs them, and runs a paired Wilcoxon. Useful
    for testing whether stroke-side preference persists/changes across
    epochs.

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Must contain ``animal_col`` and ``ipsi_contra_col``; values in
        ``ipsi_contra_col`` must include ``"ipsi"`` and ``"contra"``.
    epoch : str, optional
        If provided, filters to one ``epoch_label``. If None, pools
        across all available epochs (use with caution — typically
        you want a per-epoch test).
    value_col, animal_col, ipsi_contra_col, epoch_col : str
    aggregator : {"mean", "median"}, default "mean"
    """
    model_name = "ipsi_contra_wilcoxon"
    if aggregator not in ("mean", "median"):
        raise ValueError(f"aggregator must be 'mean' or 'median'; got {aggregator!r}.")
    required = {animal_col, ipsi_contra_col, value_col}
    if epoch is not None:
        required.add(epoch_col)
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )

    df = inputs_df
    if epoch is not None:
        df = df[df[epoch_col] == epoch]
    grouped = df.groupby([animal_col, ipsi_contra_col])[value_col].agg(aggregator)
    wide = grouped.unstack(ipsi_contra_col)
    if "ipsi" not in wide.columns or "contra" not in wide.columns:
        return _empty_result(
            model_name, status="insufficient_data", n=0, epoch=epoch,
        )
    paired = wide[["ipsi", "contra"]].dropna()
    n = len(paired)
    if n < 2:
        return _empty_result(
            model_name, status="insufficient_data", n=n, epoch=epoch,
        )
    diffs = paired["ipsi"].to_numpy() - paired["contra"].to_numpy()
    if np.all(diffs == 0):
        return FitResult(
            model_name=model_name, statistic=0.0, p_value=1.0,
            n_observations=n,
            details={"status": "all_zero_diffs", "epoch": epoch},
        )
    res = wilcoxon(paired["ipsi"], paired["contra"], alternative="two-sided")
    return FitResult(
        model_name=model_name,
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        n_observations=n,
        details={
            "status": "ok",
            "epoch": epoch,
            "aggregator": aggregator,
            "median_diff": float(np.median(diffs)),
        },
    )


# ---------------------------------------------------------------------------
# Friedman: trial group comparison
# ---------------------------------------------------------------------------

def fit_trial_group_friedman(
    inputs_df: pd.DataFrame,
    *,
    epoch: str | None = None,
    value_col: str = "value",
    animal_col: str = "animal",
    side_col: str = "side",
    epoch_col: str = "epoch_label",
    aggregator: str = "mean",
    groups: Sequence[str] = ("L", "R", "all"),
) -> FitResult:
    """Friedman test across trial groups (L / R / all) within animal.

    For each animal, aggregates per-side values (within ``epoch`` if
    specified) and treats the per-side aggregate as a repeated measure.
    Friedman tests whether the side has a systematic effect.

    Friedman requires at least 3 groups. For 2-group endpoints (e.g.
    lick_switch_rate with side ∈ {L, R}), use
    :func:`fit_ipsi_contra_wilcoxon` (or the paired Wilcoxon directly)
    — this function will return ``status="insufficient_data"`` with
    NaN p-value for any ``len(groups) < 3``.

    Returns
    -------
    FitResult
        ``model_name = "trial_group_friedman"``. NaN p-value if fewer
        than ``len(groups)`` animals have all groups present, OR if
        ``len(groups) < 3``.
    """
    model_name = "trial_group_friedman"
    if aggregator not in ("mean", "median"):
        raise ValueError(f"aggregator must be 'mean' or 'median'; got {aggregator!r}.")
    if len(groups) < 3:
        return _empty_result(
            model_name, status="insufficient_data", n=0,
            reason="friedman_requires_3_or_more_groups",
            n_groups=len(groups),
        )
    required = {animal_col, side_col, value_col}
    if epoch is not None:
        required.add(epoch_col)
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )

    df = inputs_df
    if epoch is not None:
        df = df[df[epoch_col] == epoch]
    df = df[df[side_col].isin(list(groups))]
    grouped = df.groupby([animal_col, side_col])[value_col].agg(aggregator)
    wide = grouped.unstack(side_col)
    missing_groups = [g for g in groups if g not in wide.columns]
    if missing_groups:
        return _empty_result(
            model_name, status="insufficient_data", n=0,
            epoch=epoch, missing_groups=missing_groups,
        )
    paired = wide[list(groups)].dropna()
    n = len(paired)
    if n < len(groups):
        return _empty_result(
            model_name, status="insufficient_data", n=n, epoch=epoch,
        )
    arrays = [paired[g].to_numpy() for g in groups]
    res = friedmanchisquare(*arrays)
    return FitResult(
        model_name=model_name,
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        n_observations=n,
        details={
            "status": "ok", "epoch": epoch,
            "groups": list(groups), "aggregator": aggregator,
        },
    )


# ---------------------------------------------------------------------------
# KS test: distribution shape (Addendum #4 — vector_per_session)
# ---------------------------------------------------------------------------

def fit_pre_post_ks_distribution_shape(
    inputs_df: pd.DataFrame,
    *,
    post_epoch: str,
    vector_col: str = "value_vector",
    epoch_col: str = "epoch_label",
    pre_label: str = "pre",
    animal_col: str = "animal",
    pool_strategy: str = "concat",
) -> FitResult:
    """Two-sample KS test on vector_per_session distribution shape (Addendum #4).

    For ``vector_per_session`` endpoints (e.g. ``latency_hist``) each
    row's ``value_vector`` column carries a 1-D distribution sample,
    not a scalar. This test compares the POOLED pre-stroke vector(s)
    against the POOLED post-stroke (``post_epoch``) vector(s).

    Parameters
    ----------
    inputs_df : pd.DataFrame
        Must contain ``vector_col`` whose entries are numpy arrays
        (or lists). Cross-row pooling per ``pool_strategy``.
    post_epoch : str
        Post epoch label.
    vector_col : str, default "value_vector"
        Column whose entries are per-row 1-D arrays.
    epoch_col, pre_label, animal_col : str
        Column / label overrides.
    pool_strategy : {"concat"}, default "concat"
        How to pool vectors across rows. "concat" concatenates all
        pre vectors and all post vectors before the KS test
        (treats each frame/sample equally regardless of session).

    Returns
    -------
    FitResult
        ``model_name = "pre_post_ks_distribution_shape"``. statistic =
        KS D, p_value = scipy 2-sample p-value.

    Notes
    -----
    Sessions with empty / NaN-only vectors are dropped from the pool.
    Returns NaN when either pre or post pool is empty.
    """
    model_name = "pre_post_ks_distribution_shape"
    if pool_strategy != "concat":
        raise ValueError(
            f"pool_strategy must be 'concat'; got {pool_strategy!r}.",
        )
    required = {epoch_col, vector_col}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )

    def _pool(rows: pd.Series) -> np.ndarray:
        chunks = []
        for v in rows:
            if v is None:
                continue
            arr = np.asarray(v, dtype=float).ravel()
            arr = arr[~np.isnan(arr)]
            if arr.size > 0:
                chunks.append(arr)
        if not chunks:
            return np.array([])
        return np.concatenate(chunks)

    pre_pool = _pool(inputs_df.loc[inputs_df[epoch_col] == pre_label, vector_col])
    post_pool = _pool(inputs_df.loc[inputs_df[epoch_col] == post_epoch, vector_col])
    if pre_pool.size == 0 or post_pool.size == 0:
        return _empty_result(
            model_name, status="insufficient_data",
            n=int(pre_pool.size + post_pool.size),
            n_pre=int(pre_pool.size), n_post=int(post_pool.size),
        )
    res = ks_2samp(pre_pool, post_pool, alternative="two-sided")
    return FitResult(
        model_name=model_name,
        statistic=float(res.statistic),
        p_value=float(res.pvalue),
        n_observations=int(pre_pool.size + post_pool.size),
        details={
            "status": "ok", "post_epoch": post_epoch,
            "n_pre_samples": int(pre_pool.size),
            "n_post_samples": int(post_pool.size),
        },
    )


# ---------------------------------------------------------------------------
# MixedLM: recovery curve
# ---------------------------------------------------------------------------

def fit_recovery_mixedlm(
    inputs_df: pd.DataFrame,
    *,
    value_col: str = "value",
    rel_day_col: str = "rel_day",
    animal_col: str = "animal",
    include_pre: bool = False,
) -> FitResult:
    """Mixed-effects linear model: value ~ rel_day + (1 | animal).

    Tests whether ``value`` has a systematic slope vs days post-stroke.
    Random intercept per animal absorbs per-animal baseline differences.

    Parameters
    ----------
    inputs_df : pd.DataFrame
    value_col : str, default "value"
    rel_day_col : str, default "rel_day"
    animal_col : str, default "animal"
    include_pre : bool, default False
        If False (default), drop ``rel_day <= 0`` rows so the slope
        estimates the POST-stroke recovery trajectory. If True, include
        pre-stroke rows.

    Returns
    -------
    FitResult
        ``model_name = "recovery_mixedlm"``. ``statistic`` = fixed-
        effect slope estimate; ``p_value`` = two-sided Wald p-value
        for slope. ``details`` carries ``slope``, ``slope_se``,
        ``intercept``, ``aic``, ``converged``.
    """
    model_name = "recovery_mixedlm"
    required = {value_col, rel_day_col, animal_col}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )

    df = inputs_df[[value_col, rel_day_col, animal_col]].dropna()
    if not include_pre:
        df = df[df[rel_day_col] > 0]
    if len(df) < 5:
        return _empty_result(
            model_name, status="insufficient_data", n=len(df),
        )
    if df[animal_col].nunique() < 2:
        return _empty_result(
            model_name, status="insufficient_data", n=len(df),
            n_animals=int(df[animal_col].nunique()),
        )

    from statsmodels.regression.mixed_linear_model import MixedLM

    md = MixedLM.from_formula(
        f"{value_col} ~ {rel_day_col}",
        groups=df[animal_col],
        data=df,
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdf = md.fit(method="lbfgs", reml=True)
    except Exception as exc:
        return _empty_result(
            model_name, status="convergence_failed", n=len(df),
            error=str(exc),
        )
    if not mdf.converged:
        return _empty_result(
            model_name, status="convergence_failed", n=len(df),
            n_animals=int(df[animal_col].nunique()),
        )
    slope = float(mdf.fe_params[rel_day_col])
    slope_se = float(mdf.bse_fe[rel_day_col])
    p = float(mdf.pvalues[rel_day_col])
    return FitResult(
        model_name=model_name,
        statistic=slope,
        p_value=p,
        n_observations=len(df),
        details={
            "status": "ok",
            "slope": slope,
            "slope_se": slope_se,
            "intercept": float(mdf.fe_params["Intercept"]),
            "aic": float(mdf.aic),
            "converged": True,
            "n_animals": int(df[animal_col].nunique()),
        },
    )


# ---------------------------------------------------------------------------
# Per-epoch LMM (Addendum #6)
# ---------------------------------------------------------------------------

def fit_per_epoch_lmm(
    inputs_df: pd.DataFrame,
    *,
    value_col: str = "value",
    epoch_col: str = "epoch_label",
    animal_col: str = "animal",
    apply_additive_baseline: bool = False,
    reference_epoch: str = "pre",
) -> FitResult:
    """Per-epoch LMM ``value ~ C(epoch_label) + (1|animal)`` (Addendum #9).

    Tests whether the per-epoch mean of ``value`` differs across
    epochs. Random intercept per animal absorbs between-animal baseline
    offsets — no additive baseline subtraction needed at test time
    (per Addendum #9 (B), which supersedes Addendum #6 D-F).

    Each non-reference epoch coefficient directly tests "this epoch
    differs from pre by X units" on the raw value scale. Cross-epoch
    contrasts (e.g. acute vs chronic) are available as linear
    combinations of the fitted coefficients in ``details["per_epoch"]``.

    Parameters
    ----------
    inputs_df : pd.DataFrame
    value_col : str, default "value"
    epoch_col : str, default "epoch_label"
    animal_col : str, default "animal"
    apply_additive_baseline : bool, default False (Addendum #9)
        If True, computes per-animal mean of ``value`` for rows with
        ``epoch == reference_epoch`` and subtracts before fitting.
        **Not recommended for inferential use** — the LMM's random
        intercept already absorbs between-animal shifts; subtracting
        pre-mean only creates the singular matrix pin (see Edge case
        below). The parameter is preserved as a callable for legacy
        / inspection use and for the figure-render-time normalization
        path (Addendum #9 D moves that to Task 7 / Phase 9.1 render
        code, not here).
    reference_epoch : str, default "pre"
        Categorical reference level.

    Returns
    -------
    FitResult
        ``model_name = "per_epoch_lmm"``. ``statistic`` = -log10 of
        the smallest p-value across non-reference epoch coefficients
        (a single scalar summary). ``p_value`` = the corresponding
        smallest p-value. ``details`` carries the per-epoch coefficients
        + p-values keyed by epoch label.

    Notes
    -----
    For the typical Phase 9 cohort with 4 epoch levels (pre, acute,
    sub_acute, chronic), the LMM has 3 non-reference fixed-effect
    coefficients (acute, sub_acute, chronic). The ``statistic`` field
    summarizes them via the min-p — analogous to a Wald chi-square
    omnibus but reported as -log10(p) for tail visibility.

    **Edge case (degenerate design) — VESTIGIAL under Addendum #9:**
    The singular-matrix path that fires with
    ``apply_additive_baseline=True`` + 2-epoch input is preserved as a
    safety net but is no longer reachable from the current Task 5
    cohort emit (which uses ``apply_additive_baseline=False`` per
    Addendum #9). Documented here for forward-compat if a future
    caller flips ``apply_additive_baseline=True``. For 2-epoch
    paired tests prefer :func:`fit_paired_pre_post_wilcoxon`
    regardless.
    """
    model_name = "per_epoch_lmm"
    required = {value_col, epoch_col, animal_col}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(
            f"inputs_df missing required column(s) {sorted(missing)}.",
        )
    df = inputs_df[[value_col, epoch_col, animal_col]].dropna()
    if df[epoch_col].nunique() < 2:
        return _empty_result(
            model_name, status="insufficient_data", n=len(df),
            n_epochs=int(df[epoch_col].nunique()),
        )
    if df[animal_col].nunique() < 2 or len(df) < 5:
        return _empty_result(
            model_name, status="insufficient_data", n=len(df),
            n_animals=int(df[animal_col].nunique()),
        )

    if apply_additive_baseline:
        baseline = (
            df[df[epoch_col] == reference_epoch]
            .groupby(animal_col)[value_col].mean()
            .rename("baseline_mean")
        )
        df = df.merge(baseline, on=animal_col, how="left")
        df["_value_norm"] = df[value_col] - df["baseline_mean"]
        fit_col = "_value_norm"
        # Drop rows where baseline is missing (no pre data for that animal).
        df = df.dropna(subset=["baseline_mean"])
        if len(df) < 5:
            return _empty_result(
                model_name, status="insufficient_data", n=len(df),
                reason="too_few_rows_after_baseline_join",
            )
    else:
        fit_col = value_col

    # Set categorical with reference level via pd.Categorical so
    # statsmodels uses it as the omitted (baseline) level.
    epoch_levels = sorted(df[epoch_col].dropna().unique().tolist())
    if reference_epoch in epoch_levels:
        # statsmodels Treatment uses the first level by default; reorder
        # so reference is first.
        epoch_levels = [reference_epoch] + [
            e for e in epoch_levels if e != reference_epoch
        ]
    df = df.copy()
    df[epoch_col] = pd.Categorical(
        df[epoch_col], categories=epoch_levels, ordered=False,
    )

    from statsmodels.regression.mixed_linear_model import MixedLM

    md = MixedLM.from_formula(
        f"{fit_col} ~ C({epoch_col})",
        groups=df[animal_col],
        data=df,
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdf = md.fit(method="lbfgs", reml=True)
    except Exception as exc:
        return _empty_result(
            model_name, status="convergence_failed", n=len(df),
            error=str(exc),
        )
    if not mdf.converged:
        return _empty_result(
            model_name, status="convergence_failed", n=len(df),
        )

    # Collect per-non-ref-epoch coefficients + p-values.
    per_epoch: dict[str, dict[str, float]] = {}
    for param_name, coef in mdf.fe_params.items():
        if param_name == "Intercept":
            continue
        # Pattern: C(epoch_label)[T.acute] — extract the epoch label.
        epoch_label = param_name.split("[T.")[-1].rstrip("]")
        per_epoch[epoch_label] = {
            "coef": float(coef),
            "se": float(mdf.bse_fe[param_name]),
            "p_value": float(mdf.pvalues[param_name]),
        }
    if not per_epoch:
        return _empty_result(
            model_name, status="insufficient_data", n=len(df),
            reason="no_non_reference_epochs",
        )
    min_p = min(v["p_value"] for v in per_epoch.values())
    # -log10(p) summary; clamp to a finite max for numerical sanity.
    log10_stat = float(-np.log10(max(min_p, 1e-300)))
    return FitResult(
        model_name=model_name,
        statistic=log10_stat,
        p_value=float(min_p),
        n_observations=len(df),
        details={
            "status": "ok",
            "per_epoch": per_epoch,
            "reference_epoch": reference_epoch,
            "additive_baseline_applied": apply_additive_baseline,
            "aic": float(mdf.aic),
            "converged": True,
        },
    )
