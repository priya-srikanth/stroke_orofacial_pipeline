"""Scalar phenotype-pooled endpoint stats suite (the foundational engine).

Brings the q13b phase-aligned ENDPOINTS (and the other pooled-phenotype scalar
families: per-endpoint scalars incl. spout-behavior, wasserstein /
normalized_wasserstein) up to the powered TRAJECTORY suite, on the
pre-stroke-baseline-normalized Δ metric at **session grain**.

Per Priya 2026-06-01 (see docs/prompts/archive/chore-pooled-phenotype-stats-suite-kickoff.md):
each (phenotype × side[cue] × endpoint × post_epoch ∈ {acute, sub_acute, chronic})
cell, both scopes (3_tier, 4_tier), `pre` as reference, gets:

1. **Per-animal paired Wilcoxon** — `fit_paired_pre_post_wilcoxon` (aggregator mean).
2. **Session-wise Mann-Whitney U** — unpaired, per-session Δ values.
3. **LMM** — `fit_per_epoch_lmm` (value ~ epoch + (1|animal)), session grain.
4. **Bootstrap effect-CI** — resampling unit = SESSIONS (this module), 95% CI of
   the post−pre Δ + `excludes_zero` flag.

(Cluster permutation is trajectory-only — no phase dim here. Per-trial MWU skipped.)

This module is the reusable per-cell engine; a driver (next) iterates it across
every pooled family + writes the consolidated per-scope sheet.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from stroke_orofacial.stats.models import (
    fit_paired_pre_post_wilcoxon,
    fit_per_epoch_lmm,
)
from stroke_orofacial.stats.normalization import difference_from_baseline

POST_EPOCHS: tuple[str, ...] = ("acute", "sub_acute", "chronic")
PRE_LABEL = "pre"


def _finite(a: Any) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    return arr[np.isfinite(arr)]


def session_bootstrap_effect_ci(
    pre_vals: np.ndarray,
    post_vals: np.ndarray,
    *,
    n_boot: int = 5000,
    ci: float = 0.95,
    seed: int = 0,
) -> dict[str, float | bool | int]:
    """Session-resampled bootstrap CI of the (post − pre) mean Δ.

    Resamples SESSIONS with replacement (unit = sessions, Priya 2026-06-01) from
    the pre and post pools independently, recomputes ``mean(post) - mean(pre)``
    per resample, and returns the median + percentile CI + an ``excludes_zero``
    flag (CI does not span 0 → effect significant by CI).
    """
    pre = _finite(pre_vals)
    post = _finite(post_vals)
    if pre.size == 0 or post.size == 0:
        return {"effect_median": np.nan, "effect_ci_lo": np.nan,
                "effect_ci_hi": np.nan, "excludes_zero": False,
                "n_pre_sessions": int(pre.size), "n_post_sessions": int(post.size)}
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        bp = rng.choice(pre, size=pre.size, replace=True)
        bq = rng.choice(post, size=post.size, replace=True)
        diffs[i] = bq.mean() - bp.mean()
    lo_q = (1.0 - ci) / 2.0
    lo, hi = np.quantile(diffs, [lo_q, 1.0 - lo_q])
    return {
        "effect_median": float(np.median(diffs)),
        "effect_ci_lo": float(lo), "effect_ci_hi": float(hi),
        "excludes_zero": bool(lo > 0 or hi < 0),
        "n_pre_sessions": int(pre.size), "n_post_sessions": int(post.size),
    }


def _session_mwu(pre_vals: np.ndarray, post_vals: np.ndarray) -> tuple[float, float]:
    """Unpaired Mann-Whitney U on per-session Δ (post vs pre). (stat, p)."""
    from scipy.stats import mannwhitneyu
    pre = _finite(pre_vals)
    post = _finite(post_vals)
    if pre.size < 1 or post.size < 1:
        return float("nan"), float("nan")
    try:
        u, p = mannwhitneyu(post, pre, alternative="two-sided")
        return float(u), float(p)
    except ValueError:
        return float("nan"), float("nan")


def compute_endpoint_cell_suite(
    cell_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value_norm",
    epoch_col: str = "epoch_label",
    animal_col: str = "animal",
    n_boot: int = 5000,
) -> dict[str, Any]:
    """Run the 4 scalar tests for ONE (phenotype × side × endpoint × post_epoch)
    cell on the Δ metric. ``cell_df`` holds per-session rows (one per session)
    with ``value_col`` (Δ-from-pre), ``epoch_col``, ``animal_col`` for `pre` +
    this `post_epoch`. Returns a flat dict (caller adds the grouping keys + FDR).
    """
    sub = cell_df[cell_df[epoch_col].isin((PRE_LABEL, post_epoch))]
    pre_vals = sub.loc[sub[epoch_col] == PRE_LABEL, value_col].to_numpy()
    post_vals = sub.loc[sub[epoch_col] == post_epoch, value_col].to_numpy()

    wil = fit_paired_pre_post_wilcoxon(
        sub, post_epoch=post_epoch, value_col=value_col,
        animal_col=animal_col, epoch_col=epoch_col, aggregator="mean",
    )
    mwu_u, mwu_p = _session_mwu(pre_vals, post_vals)
    try:
        lmm = fit_per_epoch_lmm(
            sub, value_col=value_col, epoch_col=epoch_col, animal_col=animal_col,
        )
        lmm_stat = lmm.statistic
        lmm_p = lmm.p_value
        lmm_status = lmm.details.get("status", "ok")
    except Exception as exc:  # pragma: no cover — surfaced as status
        lmm_stat, lmm_p, lmm_status = float("nan"), float("nan"), f"error:{exc}"
    boot = session_bootstrap_effect_ci(pre_vals, post_vals, n_boot=n_boot)

    return {
        "post_epoch": post_epoch,
        "wilcoxon_stat": wil.statistic, "wilcoxon_p": wil.p_value,
        "wilcoxon_n": wil.n_observations,
        "wilcoxon_status": wil.details.get("status", "ok"),
        "mwu_session_u": mwu_u, "mwu_session_p": mwu_p,
        "lmm_coef": lmm_stat, "lmm_p": lmm_p, "lmm_status": lmm_status,
        **boot,
    }


def normalize_to_pre_baseline(
    long_df: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("animal", "side"),
    value_col: str = "value",
) -> pd.DataFrame:
    """Add ``value_norm`` = value − per-(group) pre-stroke baseline mean.

    Thin wrapper over :func:`stats.normalization.difference_from_baseline` so the
    suite always tests the pre-stroke-normalized Δ metric (Priya 2026-06-01).
    """
    df = long_df
    if "is_sentinel" not in df.columns:
        df = df.assign(is_sentinel=False)
    return difference_from_baseline(
        df, group_cols=list(group_cols), value_col=value_col,
        baseline_label=PRE_LABEL,
    )
