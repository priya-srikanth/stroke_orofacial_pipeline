"""Within-animal (restricted) cluster-based permutation test for
phase-aligned trajectories.

Why this exists
---------------
``figures.phase_aligned_trajectories.compute_trajectory_cluster_permutation_stats``
pools every session of a (phenotype, side) cell and permutes pre/post labels
freely ACROSS animals. Sessions are nested in animals, so free exchange treats
them as independent (pseudoreplication) and lets between-animal differences
leak into the pre-vs-post contrast. This module keeps the same Maris-Oostenveld
cluster-mass logic but respects the animal > session > trial nesting:

* **Unit** = session trajectory (trials averaged within session, so trial
  variability is carried inside each session mean; ``n_trials`` retained).
* **Statistic per bin** = animal-balanced difference
  ``D = mean_a( mean(post_a) - mean(pre_a) )`` divided by its nested SE
  ``SE = sqrt( sum_a (s2_pre / n_pre_a + s2_post / n_post_a) ) / A``, where
  ``s2_pre`` / ``s2_post`` are within-animal session variances pooled across
  animals (pooled df = sum_a (n_a - 1)). If every animal has exactly one
  post session (df_post == 0) the pooled pre variance is used for both.
  Each animal gets equal weight regardless of how many sessions it has.
* **Exchangeability** = pre/post labels are shuffled ONLY among a single
  animal's own sessions (per-animal counts preserved). Animals lacking
  either pre or post sessions for the comparison are excluded.
* **Clusters** = contiguous same-sign runs with ``|T| > t_threshold``;
  mass = sum |T|. Null = max cluster mass (either sign) per permutation.
  ``p = (1 + #{null >= obs}) / (1 + n_permutations)``.
* **Multiplicity** = BH-FDR across all observed clusters in the output table
  (same family definition as the pooled test, for comparability).

Inference is conditional on the animals studied (n = 2-4 per 3-tier
phenotype): it asks whether, within these mice, post-stroke sessions differ
from their own pre-stroke sessions, not whether the effect generalizes to new
mice.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import comb, prod

import numpy as np
import pandas as pd

POST_EPOCHS: tuple[str, ...] = ("acute", "sub_acute", "chronic")
SIDE_ORDER: tuple[str, ...] = ("L", "R")
DEFAULT_SIGNALS: tuple[str, ...] = ("angle_deg", "x_centered", "y_centered")


def session_trajectories(
    densified: pd.DataFrame, value_col: str,
) -> pd.DataFrame:
    """Trial x bin rows -> one row per session, bins as columns.

    Returns a wide frame indexed by (animal, date, epoch_label) with
    integer phase-bin columns plus an ``n_trials`` column.
    """
    sub = densified[["animal", "date", "epoch_label", "trial_index",
                     "phase_bin", value_col]].copy()
    sub["_val"] = pd.to_numeric(sub[value_col], errors="coerce")
    sub = sub.dropna(subset=["_val"])
    if sub.empty:
        return pd.DataFrame()
    keys = ["animal", "date", "epoch_label"]
    wide = sub.pivot_table(index=keys, columns="phase_bin",
                           values="_val", aggfunc="mean").sort_index(axis=1)
    wide.columns = [int(c) for c in wide.columns]
    ntr = sub.groupby(keys)["trial_index"].nunique().rename("n_trials")
    return wide.join(ntr).reset_index()


def _pooled_var(groups: list[np.ndarray]) -> tuple[np.ndarray, int]:
    """Within-group variance pooled across animals, per bin (NaN-aware)."""
    ss = None
    df = None
    for g in groups:
        if g.shape[0] < 2:
            continue
        dev = g - np.nanmean(g, axis=0)
        s = np.nansum(dev ** 2, axis=0)
        d = np.sum(np.isfinite(g), axis=0) - 1
        ss = s if ss is None else ss + s
        df = d if df is None else df + d
    if ss is None:
        return np.full(groups[0].shape[1], np.nan), 0
    with np.errstate(invalid="ignore", divide="ignore"):
        var = np.where(df > 0, ss / np.maximum(df, 1), np.nan)
    return var, int(np.nanmax(df)) if np.size(df) else 0


def animal_balanced_t(
    pre: list[np.ndarray], post: list[np.ndarray],
) -> np.ndarray:
    """Per-bin animal-balanced t (see module docstring).

    ``pre[a]`` / ``post[a]`` are (n_sessions, n_bins) arrays for animal a.
    """
    A = len(pre)
    with np.errstate(invalid="ignore", divide="ignore"):
        diffs = np.vstack([np.nanmean(po, axis=0) - np.nanmean(pr, axis=0)
                           for pr, po in zip(pre, post)])
        d_mean = np.nanmean(diffs, axis=0)
        s2_pre, df_pre = _pooled_var(pre)
        s2_post, df_post = _pooled_var(post)
        if df_post == 0:
            s2_post = s2_pre
        if df_pre == 0:
            s2_pre = s2_post
        var_sum = np.zeros_like(d_mean)
        for pr, po in zip(pre, post):
            n_pr = np.sum(np.isfinite(pr), axis=0)
            n_po = np.sum(np.isfinite(po), axis=0)
            var_sum = var_sum + s2_pre / np.maximum(n_pr, 1) + s2_post / np.maximum(n_po, 1)
        se = np.sqrt(var_sum) / A
        t = d_mean / se
    return np.where(np.isfinite(t) & (se > 0), t, np.nan)


def find_signed_clusters(
    t_arr: np.ndarray, threshold: float,
) -> list[dict[str, float]]:
    """Contiguous same-sign runs with |t| > threshold."""
    clusters: list[dict[str, float]] = []
    n = len(t_arr)
    i = 0
    while i < n:
        ti = t_arr[i]
        if not (np.isfinite(ti) and abs(ti) > threshold):
            i += 1
            continue
        sgn = np.sign(ti)
        j = i
        while j < n and np.isfinite(t_arr[j]) and abs(t_arr[j]) > threshold \
                and np.sign(t_arr[j]) == sgn:
            j += 1
        clusters.append({
            "start_bin": int(i), "end_bin": int(j - 1),
            "mass": float(np.sum(np.abs(t_arr[i:j]))), "sign": float(sgn),
        })
        i = j
    return clusters


def n_distinct_permutations(pre_counts: Sequence[int],
                            post_counts: Sequence[int]) -> int:
    """Number of distinct within-animal label assignments."""
    return prod(comb(a + b, b) for a, b in zip(pre_counts, post_counts))


def within_animal_cluster_test(
    sessions: pd.DataFrame,
    bins: Sequence[int],
    post_epoch: str,
    *,
    n_permutations: int,
    t_threshold: float,
    rng: np.random.Generator,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run one pre-vs-post_epoch comparison. Returns (cluster rows, info)."""
    per_animal = []
    for animal, g in sessions.groupby("animal", sort=True):
        pr = g[g.epoch_label == "pre"][list(bins)].to_numpy(float)
        po = g[g.epoch_label == post_epoch][list(bins)].to_numpy(float)
        if len(pr) and len(po):
            per_animal.append((animal, pr, po))
    info: dict[str, object] = {
        "n_animals": len(per_animal),
        "animals": ",".join(a for a, _, _ in per_animal),
        "n_pre": int(sum(len(p) for _, p, _ in per_animal)),
        "n_post": int(sum(len(q) for _, _, q in per_animal)),
    }
    if not per_animal or (info["n_pre"] + info["n_post"]) < 3:
        info["status"] = "insufficient_data"
        return [], info
    pre = [p for _, p, _ in per_animal]
    post = [q for _, _, q in per_animal]
    n_distinct = n_distinct_permutations([len(p) for p in pre],
                                         [len(q) for q in post])
    info["n_distinct_perms"] = n_distinct
    info["min_attainable_p"] = 1.0 / n_distinct
    obs = find_signed_clusters(animal_balanced_t(pre, post), t_threshold)
    if not obs:
        info["status"] = "no_cluster"
        return [], info

    joints = [np.vstack([p, q]) for p, q in zip(pre, post)]
    n_pre_a = [len(p) for p in pre]
    null = np.zeros(n_permutations)
    for k in range(n_permutations):
        ppre, ppost = [], []
        for J, npre in zip(joints, n_pre_a):
            idx = rng.permutation(J.shape[0])
            ppre.append(J[idx[:npre]])
            ppost.append(J[idx[npre:]])
        cl = find_signed_clusters(animal_balanced_t(ppre, ppost), t_threshold)
        null[k] = max((c["mass"] for c in cl), default=0.0)

    rows = []
    for ci, c in enumerate(obs):
        p = (1.0 + np.sum(null >= c["mass"])) / (1.0 + n_permutations)
        rows.append({"cluster_idx": ci, "start_bin": c["start_bin"],
                     "end_bin": c["end_bin"], "cluster_mass": c["mass"],
                     "sign": c["sign"], "p_value": float(max(p, 1.0 / n_distinct))})
    info["status"] = "ok"
    return rows, info


def compute_trajectory_cluster_permutation_within_animal(
    densified: pd.DataFrame,
    *,
    phenotype_order: Iterable[str],
    signals: Iterable[str] = DEFAULT_SIGNALS,
    variants: Iterable[str] = ("raw", "delta"),
    n_permutations: int = 5000,
    t_threshold: float = 2.0,
    rng_seed: int = 42,
) -> pd.DataFrame:
    """Within-animal cluster permutation over the full results family.

    ``densified`` = trial x bin rows (``densify_phase_rows_via_interp`` output
    after ``attach_metadata`` + ``apply_phase_bin_baseline_delta``), with
    columns animal, date, trial_index, side, phase_bin, epoch_label,
    recovery_phenotype, and ``<signal>`` / ``<signal>_delta``.

    Output columns mirror ``trajectory_cluster_permutation_bh_fdr.csv`` plus
    ``n_animals``, ``animals``, ``n_distinct_perms``, ``min_attainable_p``,
    ``test``.
    """
    from stroke_orofacial.stats.multiple_comparisons import (
        apply_correction_to_results_df,
    )
    rng = np.random.default_rng(rng_seed)
    out: list[dict[str, object]] = []
    for phen in phenotype_order:
        for side in SIDE_ORDER:
            cell = densified[(densified.recovery_phenotype == phen)
                             & (densified.side == side)]
            for sig in signals:
                for var in variants:
                    col = sig if var == "raw" else f"{sig}_delta"
                    key = {"recovery_phenotype": phen, "side": side,
                           "signal": sig, "variant": var}
                    sess = (session_trajectories(cell, col)
                            if (not cell.empty and col in cell) else pd.DataFrame())
                    for ep in POST_EPOCHS:
                        base = {**key, "post_epoch": ep,
                                "test": "within_animal_cluster_perm"}
                        if sess.empty:
                            out.append({**base, "cluster_idx": 0, "start_bin": -1,
                                        "end_bin": -1, "p_value": np.nan,
                                        "status": "insufficient_data",
                                        "n_pre": 0, "n_post": 0, "n_animals": 0})
                            continue
                        bins = [c for c in sess.columns if isinstance(c, int)]
                        rows, info = within_animal_cluster_test(
                            sess, bins, ep, n_permutations=n_permutations,
                            t_threshold=t_threshold, rng=rng)
                        if not rows:
                            pv = 1.0 if info["status"] == "no_cluster" else np.nan
                            out.append({**base, **info, "cluster_idx": 0,
                                        "start_bin": -1, "end_bin": -1,
                                        "cluster_mass": 0.0, "sign": 0.0,
                                        "p_value": pv})
                        for r in rows:
                            out.append({**base, **info, **r})
    res = pd.DataFrame(out)
    res = apply_correction_to_results_df(res, p_value_col="p_value",
                                         method="bh_fdr", group_cols=())
    return res
