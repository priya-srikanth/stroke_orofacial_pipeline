"""Time to return of contralesional correct licking (two-tone cohort grading).

Manuscript v41 (Priya 2026-11-19) grades the two-tone animals by the first
post-stroke day on which correct contralesional licks per trial reach a
fraction of the animal's baseline. Port of the manuscript's
``figures/supp_c1_recovery_time.py`` (computation only) and of the k-means
check in ``analysis/c1_severity_features_kmeans.py``.

Definition (per animal):

- Input: the materialized endpoint ``num_correct_licks_per_trial_rw``
  (spout-contact correct licks per trial, response window cue + 70 ms to
  cue + 8 s; DECISIONS 2026-11-19), ``stats/inputs/no_filter``; sentinel rows
  (``is_sentinel``) dropped.
- Per day: mean ``value`` per (``rel_day``, ``ipsi_contra``); the
  contralesional series is used.
- Baseline: mean of the last :data:`BASELINE_N_SESSIONS` pre-stroke days
  (``rel_day < 0``; the stroke day itself is not baseline, as in the
  manuscript script).
- Recovery day: the first post-stroke day (``rel_day > 0``) whose value is at
  least ``threshold`` x baseline. Not required to be sustained. If no day
  qualifies, the value is censored at the last recorded post-stroke day + 1
  (``censored = True``).

Threshold sensitivity: k-means (k = 3, :data:`KMEANS_N_INIT` restarts,
``random_state=0``) on log recovery days at each threshold, compared with the
grade (adjusted Rand index; ARI = 1 means the clusters equal the grades).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ENDPOINT_SLUG = "num_correct_licks_per_trial_rw"
BASELINE_N_SESSIONS = 5
THRESHOLDS: tuple[float, ...] = (0.25, 0.5, 0.75)
PRIMARY_THRESHOLD = 0.5
KMEANS_K = 3
# Same restarts / seed as the manuscript's c1_severity_features_kmeans.py.
KMEANS_N_INIT = 200
KMEANS_RANDOM_STATE = 0


def contra_fraction_of_baseline(df: pd.DataFrame) -> pd.Series:
    """Post-stroke contralesional values as a fraction of the pre-stroke baseline.

    Parameters
    ----------
    df : pd.DataFrame
        One animal's materialized endpoint rows with columns ``rel_day``,
        ``ipsi_contra``, ``value``, ``is_sentinel``.

    Returns
    -------
    pd.Series
        Indexed by post-stroke ``rel_day`` (> 0), sorted, NaN days dropped.
    """
    x = df[~df["is_sentinel"].astype(bool)]
    s = x.groupby(["rel_day", "ipsi_contra"])["value"].mean().unstack()["contra"]
    pre = s[s.index < 0].sort_index().tail(BASELINE_N_SESSIONS).mean()
    return (s[s.index > 0].sort_index() / pre).dropna()


def recovery_day(frac: pd.Series, threshold: float) -> tuple[int, bool]:
    """First post-stroke day with ``frac >= threshold``.

    Returns ``(day, censored)``; when no day qualifies, ``day`` is the last
    recorded post-stroke day + 1 and ``censored`` is True.
    """
    hit = frac[frac >= threshold]
    if hit.empty:
        return int(frac.index.max()) + 1, True
    return int(hit.index[0]), False


def recovery_time_table(
    inputs_dir: Path,
    grades: dict[str, str],
    thresholds: tuple[float, ...] = THRESHOLDS,
) -> pd.DataFrame:
    """Per-animal recovery days at each threshold.

    Parameters
    ----------
    inputs_dir : Path
        ``stats/inputs/<filter>/<ENDPOINT_SLUG>`` directory (one parquet per
        animal).
    grades : dict
        ``{animal: grade}`` (3-tier grade); defines the animals and row order.

    Returns
    -------
    pd.DataFrame
        One row per animal: ``animal``, ``grade``, ``baseline_n_sessions``,
        ``last_post_day`` and, per threshold ``t`` (as a percentage ``P``),
        ``days_P`` and ``censored_P``.
    """
    rows = []
    for a, g in grades.items():
        frac = contra_fraction_of_baseline(pd.read_parquet(Path(inputs_dir) / f"{a}.parquet"))
        r = {"animal": a, "grade": g, "baseline_n_sessions": BASELINE_N_SESSIONS,
             "last_post_day": int(frac.index.max())}
        for t in thresholds:
            d, c = recovery_day(frac, t)
            r[f"days_{round(100 * t)}"] = d
            r[f"censored_{round(100 * t)}"] = c
        rows.append(r)
    return pd.DataFrame(rows)


def kmeans_log_days(table: pd.DataFrame, thresholds: tuple[float, ...] = THRESHOLDS) -> pd.DataFrame:
    """k-means (k = 3) on log recovery days at each threshold vs the grades.

    Clustering is 1-D, so the standardization used in the manuscript script
    does not change the partition; it is kept for parity.

    Returns one row per threshold with the cluster label of each animal
    (relabelled in order of first appearance), the adjusted Rand index against
    the grades, and ``matches_grades`` (ARI == 1).
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score

    g = pd.factorize(table["grade"].to_numpy())[0]
    out = []
    for t in thresholds:
        col = f"days_{round(100 * t)}"
        x = np.log(table[col].astype(float).to_numpy())
        z = (x - x.mean()) / x.std(ddof=0)
        km = KMeans(KMEANS_K, n_init=KMEANS_N_INIT, random_state=KMEANS_RANDOM_STATE).fit(z.reshape(-1, 1))
        lab = pd.factorize(km.labels_)[0]
        ari = float(adjusted_rand_score(g, lab))
        out.append({"threshold_pct": round(100 * t),
                    "clusters": " ".join(f"{a}:{k}" for a, k in zip(table["animal"], lab)),
                    "ari_vs_grades": round(ari, 4), "matches_grades": bool(np.isclose(ari, 1.0))})
    return pd.DataFrame(out)
