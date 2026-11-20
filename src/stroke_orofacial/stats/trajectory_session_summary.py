"""Session-level summaries of the phase-aligned tongue trajectories (manuscript).

Ported from the manuscript's ``analysis/c1_traj_session_stats.py``,
``c1_xy_traj_session_stats.py`` and ``c1_path_session_sem.py`` (Priya
2026-11-19: trajectory lines and bands are the mean and SEM ACROSS SESSIONS in
both cohorts; the pipeline's ``phenotype_pooled_phase_bin_mean_sem.csv`` pools
trials).

All three start from the trial x phase-bin substrate that the cluster tests
use (``scripts/manuscript/run_within_animal_cluster_perm.build_substrate``:
v7-cleaned trace, filtered_v1 trial + session filters, 3-tier grades, delta =
minus the animal's own pre-stroke per-bin baseline). Per session (animal,
date): mean over its trials in each phase bin. Then per grade x epoch x cue
side x bin: mean across sessions, SD (ddof 1), SEM = SD / sqrt(n_sessions)
(NaN for one session), n_sessions, n_animals. Each session counts once.
"""
from __future__ import annotations

import pandas as pd

TRAJ_SIGNALS: tuple[str, ...] = ("angle_deg", "x_centered", "y_centered")
CELL_KEYS: list[str] = ["recovery_phenotype", "epoch_label", "side", "phase_bin"]
OUT_COLUMNS: list[str] = ["lick_set", "recovery_phenotype", "epoch_label", "side", "phase_bin", "signal",
                          "variant", "phase_bin_center", "mean", "sd", "n_sessions", "n_animals", "sem"]


def summarise_sessions(sub: pd.DataFrame, signals: tuple[str, ...] = TRAJ_SIGNALS) -> pd.DataFrame:
    """Session mean / SEM per cell for ``signals`` and their ``_delta`` columns.

    Returns long format: one row per cell x signal x variant (``raw`` /
    ``delta``) with ``phase_bin_center``, ``mean``, ``sd``, ``n_sessions``,
    ``n_animals``, ``sem``. Sessions with a NaN session mean in a bin are not
    counted in that bin.
    """
    cols = list(signals) + [f"{s}_delta" for s in signals]
    sess = sub.groupby(CELL_KEYS + ["animal", "date"])[cols + ["phase_bin_center"]].mean().reset_index()
    long = sess.melt(id_vars=CELL_KEYS + ["animal", "date", "phase_bin_center"], value_vars=cols,
                     var_name="col", value_name="v").dropna(subset=["v"])
    long["variant"] = long.col.str.endswith("_delta").map({True: "delta", False: "raw"})
    long["signal"] = long.col.str.replace("_delta", "", regex=False)
    g = long.groupby(CELL_KEYS + ["signal", "variant"])
    out = g.agg(phase_bin_center=("phase_bin_center", "mean"), mean=("v", "mean"), sd=("v", "std"),
                n_sessions=("v", "size"), n_animals=("animal", "nunique")).reset_index()
    out["sem"] = out["sd"] / out["n_sessions"] ** 0.5
    return out


def summarise_xy_sessions(d: pd.DataFrame) -> pd.DataFrame:
    """As :func:`summarise_sessions` for the ``xy_dist`` substrate.

    Kept as the manuscript's own loop (raw then delta, NaN sessions dropped per
    variant before the session mean is taken across sessions) so the row
    order and values match ``c1_traj_xy_sessions*.csv``.
    """
    sess = d.groupby(CELL_KEYS + ["animal", "date"])[["xy_dist", "xy_dist_delta", "phase_bin_center"]].mean().reset_index()
    rows = []
    for col, var in (("xy_dist", "raw"), ("xy_dist_delta", "delta")):
        s = sess.dropna(subset=[col])
        o = s.groupby(CELL_KEYS).agg(phase_bin_center=("phase_bin_center", "mean"), mean=(col, "mean"),
                                     sd=(col, "std"), n_sessions=(col, "size"),
                                     n_animals=("animal", "nunique")).reset_index()
        o["sem"] = o["sd"] / o["n_sessions"] ** 0.5
        o["signal"], o["variant"] = "xy_dist", var
        rows.append(o)
    return pd.concat(rows, ignore_index=True)


def path_session_sem(d: pd.DataFrame) -> pd.DataFrame:
    """First-lick 2-D path: SEM across sessions of x_centered / y_centered per cell.

    The manuscript's Figure 2 path band (``c1_path_session_sem.csv``): columns
    ``x_centered_sem_sessions``, ``y_centered_sem_sessions``, ``n_sessions``.
    """
    keys = ["recovery_phenotype", "epoch_label", "side"]
    s = d.groupby(keys + ["animal", "date", "phase_bin"])[["x_centered", "y_centered"]].mean().reset_index()
    g = s.groupby(keys + ["phase_bin"])[["x_centered", "y_centered"]]
    return g.sem().add_suffix("_sem_sessions").join(g.size().rename("n_sessions")).reset_index()
