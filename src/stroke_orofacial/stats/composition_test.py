"""One change-in-distribution test per stacked outcome bar (group x post epoch vs pre).

Decided rule (Priya 2026-11-20), the same code in widefield_pipeline (cohort 2, Fig 3B / 4B) and
stroke_orofacial_pipeline (cohort 1, Fig 2B):

- unit = session; each session x group carries a composition vector (fraction of each outcome class);
- per animal: pre mean composition (mean over its pre sessions) and epoch mean composition (mean over its sessions in
  that post epoch); distance = total variation distance TVD = 0.5 * sum |p_epoch - p_pre|;
- statistic D = mean over animals (animal-weighted) of TVD; only animals with >= 1 pre and >= 1 epoch session enter;
- null: within-animal permutation of the pre / epoch session labels (each animal's pre + that-epoch sessions shuffled
  among themselves, counts kept); exact enumeration of the joint label space when it holds <= ``max_exact``
  relabellings (p = fraction with D_perm >= D_obs, the observed labelling included), else ``n_perm`` random
  relabellings (numpy default_rng(seed)), p = (1 + #{D_perm >= D_obs}) / (1 + n_perm);
- p_min = smallest achievable p: exact -> share of relabellings tied at the maximum D (TVD is symmetric, so e.g. an
  animal with 1 pre + 1 epoch session contributes the same TVD under both labellings); random -> 1 / (1 + n_perm);
- BH-FDR over every cell of the table (one family per cohort); star_dist = q < 0.05;
- descriptive: per-class animal-weighted mean of (p_epoch - p_pre) (``d_<class>`` columns).
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

TOL = 1e-12


def tvd(p, q) -> float:
    """Total variation distance 0.5 * sum |p - q|."""
    return 0.5 * float(np.abs(np.asarray(p, float) - np.asarray(q, float)).sum())


def bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values."""
    p = np.asarray(p, float)
    o = np.argsort(p)
    m = len(p)
    q = np.empty_like(p)
    q[o] = np.minimum.accumulate((p[o] * m / np.arange(1, m + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def _animal_tvd_all(x: np.ndarray, n_ep: int) -> np.ndarray:
    """TVD of every relabelling of one animal's sessions (rows of x) choosing n_ep of them as 'epoch'."""
    n = len(x)
    idx = np.array(list(itertools.combinations(range(n), n_ep)))
    mask = np.zeros((len(idx), n), bool)
    mask[np.arange(len(idx))[:, None], idx] = True
    ep = (mask[:, :, None] * x[None]).sum(1) / n_ep
    pre = (~mask[:, :, None] * x[None]).sum(1) / (n - n_ep)
    return 0.5 * np.abs(ep - pre).sum(1)


def cell_test(per_animal: dict, n_perm: int = 10_000, max_exact: int = 20_000, seed: int = 0) -> dict:
    """Permutation test of D for one cell.

    per_animal : {animal: (pre_matrix, epoch_matrix)}, each (n_sessions x n_classes) of session compositions; the
    original session order is the observed labelling (pre rows first).
    """
    an = sorted(per_animal)
    xs = [np.vstack([per_animal[a][0], per_animal[a][1]]).astype(float) for a in an]
    k = [len(per_animal[a][1]) for a in an]
    t_obs = np.array([tvd(per_animal[a][1].mean(0), per_animal[a][0].mean(0)) for a in an])
    d_obs = float(t_obs.mean())
    n_comb = [math.comb(len(x), kk) for x, kk in zip(xs, k)]
    total = math.prod(n_comb)
    if total <= max_exact:
        d = np.zeros(1)
        for x, kk in zip(xs, k):                     # joint D over the full product space
            d = (d[:, None] + _animal_tvd_all(x, kk)[None, :]).ravel()
        d = d / len(an)
        p = float(np.mean(d >= d_obs - TOL))
        p_min = float(np.mean(d >= d.max() - TOL))
        method, n_null = "exact", total
    else:
        rng = np.random.default_rng(seed)
        d = np.empty(n_perm)
        for b in range(n_perm):
            s = 0.0
            for x, kk in zip(xs, k):
                perm = rng.permutation(len(x))
                s += tvd(x[perm[:kk]].mean(0), x[perm[kk:]].mean(0))   # first kk = 'epoch', rest = 'pre'
            d[b] = s / len(an)
        p = float((1 + np.sum(d >= d_obs - TOL)) / (1 + n_perm))
        p_min = 1.0 / (1 + n_perm)
        method, n_null = "random", n_perm
    return {"D": d_obs, "p": p, "p_min": p_min, "method": method, "n_null": n_null, "n_relabellings": total,
            "tvd_by_animal": dict(zip(an, t_obs))}


def distribution_tests(frac: pd.DataFrame, classes, group_cols, post_epochs, *, animal_col="animal",
                       epoch_col="epoch", pre="pre", n_perm=10_000, max_exact=20_000, seed=0, alpha=0.05):
    """Run :func:`cell_test` for every group x post epoch of a session x group fraction table.

    frac : one row per session x group, columns ``group_cols``, ``animal_col``, ``epoch_col`` and ``classes``.
    Returns (cells, per_animal): cells has D, p, p_min, q (BH over all cells), star_dist, n_animals,
    n_pre_sessions, n_epoch_sessions, d_<class> (animal-weighted mean change); per_animal has the per-animal TVD,
    pre / epoch means and session counts.
    """
    classes = list(classes)
    group_cols = list(group_cols)
    rows, arows = [], []
    for g, d in frac.groupby(group_cols, sort=True):
        g = g if isinstance(g, tuple) else (g,)
        key = dict(zip(group_cols, g))
        for e in post_epochs:
            per = {}
            for a, da in d.groupby(animal_col):
                x0 = da[da[epoch_col] == pre][classes].to_numpy(float)
                x1 = da[da[epoch_col] == e][classes].to_numpy(float)
                if len(x0) and len(x1):
                    per[a] = (x0, x1)
            if not per:
                continue
            r = cell_test(per, n_perm=n_perm, max_exact=max_exact, seed=seed)
            delta = np.mean([per[a][1].mean(0) - per[a][0].mean(0) for a in sorted(per)], axis=0)
            rows.append({**key, "epoch": e, "D": r["D"], "p": r["p"], "p_min": r["p_min"], "method": r["method"],
                         "n_null": r["n_null"], "n_animals": len(per),
                         "n_pre_sessions": sum(len(v[0]) for v in per.values()),
                         "n_epoch_sessions": sum(len(v[1]) for v in per.values()),
                         **{f"d_{c}": v for c, v in zip(classes, delta)}})
            for a in sorted(per):
                m0, m1 = per[a][0].mean(0), per[a][1].mean(0)
                arows.append({**key, "epoch": e, "animal": a, "tvd": r["tvd_by_animal"][a],
                              "n_pre_sessions": len(per[a][0]), "n_epoch_sessions": len(per[a][1]),
                              **{f"pre_{c}": v for c, v in zip(classes, m0)},
                              **{f"epoch_{c}": v for c, v in zip(classes, m1)}})
    cells = pd.DataFrame(rows)
    cells["q"] = bh(cells.p)
    cells["star_dist"] = (cells.q < alpha).astype(int)
    cells["star_possible"] = (cells.p_min < alpha).astype(int)   # BH best case: every cell at its p_min -> q = p_min
    lead = [*group_cols, "epoch", "star_dist", "D", "p", "p_min", "q", "n_animals", "n_pre_sessions",
            "n_epoch_sessions"]
    cells = cells[lead + [c for c in cells.columns if c not in lead]]
    return cells, pd.DataFrame(arows)
