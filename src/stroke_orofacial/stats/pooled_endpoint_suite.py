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

Optional (``within_animal=True``, 2026-09-17): a within-animal permutation test
(pre/post labels shuffled only among each animal's own sessions) and a
within-animal session bootstrap CI, both on an animal-balanced effect
(``wa_*`` columns). Sensitivity analysis for the session-pooled MWU.

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


def _animal_groups(sub: pd.DataFrame, value_col: str, epoch_col: str,
                   animal_col: str, post_epoch: str):
    """Per-animal (pre, post) finite value arrays; animals lacking either dropped."""
    groups = []
    for animal, g in sub.groupby(animal_col, sort=True):
        pre = _finite(g.loc[g[epoch_col] == PRE_LABEL, value_col])
        post = _finite(g.loc[g[epoch_col] == post_epoch, value_col])
        if pre.size and post.size:
            groups.append((animal, pre, post))
    return groups


def _balanced_t_batch(pre_blocks: list[np.ndarray],
                      post_blocks: list[np.ndarray]) -> np.ndarray:
    """Animal-balanced studentized difference for a batch of relabelings.

    ``pre_blocks[a]`` / ``post_blocks[a]`` have shape (B, n_pre_a) /
    (B, n_post_a): one row per relabeling. Statistic per row:
    ``D = mean_a(mean(post_a) - mean(pre_a))`` divided by
    ``sqrt(sum_a(s2_pre/n_pre_a + s2_post/n_post_a)) / A`` with within-animal
    session variances pooled across animals. If a pooled variance has no
    degrees of freedom the other one is used; if neither does, D is returned
    unscaled.
    """
    A = len(pre_blocks)
    d = np.mean([po.mean(axis=1) - pr.mean(axis=1)
                 for pr, po in zip(pre_blocks, post_blocks)], axis=0)

    def pooled(blocks):
        ss = sum(((b - b.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
                 for b in blocks)
        df = sum(b.shape[1] - 1 for b in blocks)
        return (ss / df if df > 0 else None), df

    s2_pre, df_pre = pooled(pre_blocks)
    s2_post, df_post = pooled(post_blocks)
    if s2_pre is None and s2_post is None:
        return d
    s2_pre = s2_post if s2_pre is None else s2_pre
    s2_post = s2_pre if s2_post is None else s2_post
    var = sum(s2_pre / pr.shape[1] + s2_post / po.shape[1]
              for pr, po in zip(pre_blocks, post_blocks))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = d / (np.sqrt(var) / A)
    return np.where(np.isfinite(t), t, 0.0)


def within_animal_permutation_test(
    cell_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value_norm",
    epoch_col: str = "epoch_label",
    animal_col: str = "animal",
    n_perm: int = 5000,
    seed: int = 0,
) -> dict[str, Any]:
    """Two-sided permutation test with pre/post labels shuffled WITHIN animal.

    Unit = session; each animal's session count per label is preserved, so
    between-animal differences and unequal session counts cannot drive the
    result. Statistic = animal-balanced studentized post-pre difference
    (each animal weighted equally). ``p = (1 + #{|T*| >= |T|}) / (1 + n_perm)``.
    ``wa_min_p`` is the smallest p attainable given the number of distinct
    within-animal relabelings. ``wa_n_animals_same_sign`` counts animals whose
    own post-pre difference has the sign of the balanced effect; a call where
    this is < ``wa_n_animals`` is driven by animals that disagree.
    """
    from math import comb, prod
    sub = cell_df[cell_df[epoch_col].isin((PRE_LABEL, post_epoch))]
    groups = _animal_groups(sub, value_col, epoch_col, animal_col, post_epoch)
    diffs = [q.mean() - p.mean() for _, p, q in groups]
    bal = float(np.mean(diffs)) if diffs else np.nan
    out: dict[str, Any] = {
        "wa_stat": np.nan, "wa_p": np.nan,
        "wa_n_animals": len(groups), "wa_min_p": np.nan,
        # how many animals individually moved in the direction of the
        # animal-balanced effect (the permutation test does NOT require
        # animals to agree: with 2 animals moving in opposite directions the
        # balanced mean can still be "significant").
        "wa_n_animals_same_sign": int(sum(np.sign(d) == np.sign(bal)
                                          for d in diffs)) if diffs else 0,
    }
    if not groups or sum(len(p) + len(q) for _, p, q in groups) < 3:
        return out
    obs = float(_balanced_t_batch([p[None, :] for _, p, _ in groups],
                                  [q[None, :] for _, _, q in groups])[0])
    rng = np.random.default_rng(seed)
    pre_b, post_b = [], []
    for _, p, q in groups:
        joint = np.concatenate([p, q])
        idx = rng.permuted(np.tile(np.arange(joint.size), (n_perm, 1)), axis=1)
        perm = joint[idx]
        pre_b.append(perm[:, :p.size])
        post_b.append(perm[:, p.size:])
    null = _balanced_t_batch(pre_b, post_b)
    n_distinct = prod(comb(p.size + q.size, q.size) for _, p, q in groups)
    pval = (1.0 + np.sum(np.abs(null) >= abs(obs) - 1e-12)) / (1.0 + n_perm)
    out.update({"wa_stat": obs,
                "wa_p": float(max(pval, 1.0 / n_distinct)),
                "wa_min_p": 1.0 / n_distinct})
    return out


def within_animal_bootstrap_ci(
    cell_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value_norm",
    epoch_col: str = "epoch_label",
    animal_col: str = "animal",
    n_boot: int = 5000,
    ci: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    """Bootstrap CI of the animal-balanced post-pre difference.

    Resamples sessions with replacement WITHIN each animal (pre and post
    separately, counts preserved); animals themselves are fixed, so the CI is
    conditional on the animals studied.
    """
    sub = cell_df[cell_df[epoch_col].isin((PRE_LABEL, post_epoch))]
    groups = _animal_groups(sub, value_col, epoch_col, animal_col, post_epoch)
    if not groups:
        return {"wa_effect": np.nan, "wa_effect_ci_lo": np.nan,
                "wa_effect_ci_hi": np.nan, "wa_excludes_zero": False}
    rng = np.random.default_rng(seed)
    obs = float(np.mean([q.mean() - p.mean() for _, p, q in groups]))
    d = np.zeros(n_boot)
    for _, p, q in groups:
        bp = p[rng.integers(0, p.size, (n_boot, p.size))].mean(axis=1)
        bq = q[rng.integers(0, q.size, (n_boot, q.size))].mean(axis=1)
        d += bq - bp
    d /= len(groups)
    lo_q = (1.0 - ci) / 2.0
    lo, hi = np.quantile(d, [lo_q, 1.0 - lo_q])
    return {"wa_effect": obs, "wa_effect_ci_lo": float(lo),
            "wa_effect_ci_hi": float(hi),
            "wa_excludes_zero": bool(lo > 0 or hi < 0)}


#: Cohort-2 (widefield_pipeline ``analysis_kit``) bootstrap constants, kept equal
#: so the two cohorts' CIs are drawn the same way (Priya 2026-11-19).
NESTED_N_BOOT: int = 4000
NESTED_PCTL: tuple[float, float] = (2.5, 97.5)


def nested_animal_bootstrap_ci(
    cell_df: pd.DataFrame,
    *,
    post_epoch: str,
    value_col: str = "value_norm",
    epoch_col: str = "epoch_label",
    animal_col: str = "animal",
    n_boot: int = NESTED_N_BOOT,
    seed: int = 0,
) -> dict[str, Any]:
    """Paired, animal-weighted animals -> sessions bootstrap of the post - pre change.

    Port of widefield_pipeline ``analysis_kit.paired_animal_draws`` /
    ``boot_delta`` (the cohort-2 rule), so cohort 1 and cohort 2 use one CI:

    1. only animals with sessions in BOTH arms count;
    2. each animal's change = mean(its post sessions) - mean(its pre sessions);
    3. the change = the MEAN OVER ANIMALS (animals weigh equally, so a
       heavily-sampled animal cannot decide it);
    4. each draw resamples animals with replacement ONCE (shared by both arms,
       which makes it paired), then sessions within each drawn animal.

    Needs >= 2 animals (cohort 2's ``len(post_a) >= 2`` guard): with one animal
    there is nothing to resample at the animal level, so the CI is NaN and
    ``nb_excludes_zero`` is False. Percentile CI at ``NESTED_PCTL``.
    """
    sub = cell_df[cell_df[epoch_col].isin((PRE_LABEL, post_epoch))]
    groups = _animal_groups(sub, value_col, epoch_col, animal_col, post_epoch)
    out: dict[str, Any] = {"nb_effect": np.nan, "nb_ci_lo": np.nan, "nb_ci_hi": np.nan,
                           "nb_excludes_zero": False, "nb_n_animals": len(groups)}
    if len(groups) < 2:
        return out
    out["nb_effect"] = float(np.mean([q.mean() - p.mean() for _, p, q in groups]))
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        d = []
        for j in rng.integers(0, len(groups), len(groups)):
            _, p, q = groups[j]
            # Same order as analysis_kit: post sessions drawn before pre.
            qa = q[rng.integers(0, q.size, q.size)].mean()
            pa = p[rng.integers(0, p.size, p.size)].mean()
            d.append(qa - pa)
        draws[i] = np.mean(d)
    lo, hi = np.percentile(draws, NESTED_PCTL)
    out.update({"nb_ci_lo": float(lo), "nb_ci_hi": float(hi),
                "nb_excludes_zero": bool(lo > 0 or hi < 0)})
    return out


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
    within_animal: bool = False,
    n_perm: int = 5000,
    test_set: str = "legacy",
) -> dict[str, Any]:
    """Run the scalar tests for ONE (phenotype × side × endpoint × post_epoch)
    cell on the Δ metric. ``cell_df`` holds per-session rows (one per session)
    with ``value_col`` (Δ-from-pre), ``epoch_col``, ``animal_col`` for `pre` +
    this `post_epoch`. Returns a flat dict (caller adds the grouping keys + FDR).

    ``test_set``:
      * ``"legacy"`` (default; reproduces the published sheets): paired
        Wilcoxon, session MWU, LMM, session bootstrap.
      * ``"c2_aligned"`` (Priya 2026-11-19, aligned to the six-position
        cohort): session MWU + the nested animals -> sessions bootstrap
        (:func:`nested_animal_bootstrap_ci`). The Wilcoxon (cannot reach
        p < 0.05 at 1-4 animals) and the LMM (non-estimable at this size)
        are not run.
    """
    if test_set not in ("legacy", "c2_aligned"):
        raise ValueError(f"unknown test_set {test_set!r}")
    sub = cell_df[cell_df[epoch_col].isin((PRE_LABEL, post_epoch))]
    pre_vals = sub.loc[sub[epoch_col] == PRE_LABEL, value_col].to_numpy()
    post_vals = sub.loc[sub[epoch_col] == post_epoch, value_col].to_numpy()
    if test_set == "c2_aligned":
        mwu_u, mwu_p = _session_mwu(pre_vals, post_vals)
        res: dict[str, Any] = {
            "post_epoch": post_epoch,
            "mwu_session_u": mwu_u, "mwu_session_p": mwu_p,
            "n_pre_sessions": int(_finite(pre_vals).size),
            "n_post_sessions": int(_finite(post_vals).size),
        }
        res.update(nested_animal_bootstrap_ci(
            sub, post_epoch=post_epoch, value_col=value_col,
            epoch_col=epoch_col, animal_col=animal_col))
        if within_animal:
            res.update(within_animal_permutation_test(
                sub, post_epoch=post_epoch, value_col=value_col,
                epoch_col=epoch_col, animal_col=animal_col, n_perm=n_perm))
        return res

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
    wa: dict[str, Any] = {}
    if within_animal:
        wa.update(within_animal_permutation_test(
            sub, post_epoch=post_epoch, value_col=value_col,
            epoch_col=epoch_col, animal_col=animal_col, n_perm=n_perm))
        wa.update(within_animal_bootstrap_ci(
            sub, post_epoch=post_epoch, value_col=value_col,
            epoch_col=epoch_col, animal_col=animal_col, n_boot=n_boot))

    return {
        "post_epoch": post_epoch,
        "wilcoxon_stat": wil.statistic, "wilcoxon_p": wil.p_value,
        "wilcoxon_n": wil.n_observations,
        "wilcoxon_status": wil.details.get("status", "ok"),
        "mwu_session_u": mwu_u, "mwu_session_p": mwu_p,
        "lmm_coef": lmm_stat, "lmm_p": lmm_p, "lmm_status": lmm_status,
        **boot,
        **wa,
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
