"""Cued-trial outcome classes and their change after stroke (two-tone cohort).

Manuscript Figure 2B (v41). Ported from the manuscript's
``figures/c1_trial_classes_extract.py`` (classes) and the cohort-1 part of
``figures/trial_class_distribution.py`` (statistics); the cohort-2 test lives
in widefield_pipeline.

Classes, one per cued trial:

- ``complete``: at least one spout-contact lick (DAQ, either spout) in
  (tone, tone + 5 s] (:data:`CONTACT_WINDOW_S`);
- ``incomplete``: no contact, but at least one DLC tongue protrusion in the
  tongue/jaw-mismatch window (``n_licks_in_quiet_win > 0``; 70-5000 ms);
- ``jaw_only``: no contact, no tongue, jaw deflection above threshold
  (``candidate_no_lick_with_jaw_move``);
- ``no_resp``: none of the above.

Statistics: per session, the fraction of cued trials in each class; for each
grade x cue side x post epoch x class, two-sided Mann-Whitney U of the post
sessions against the pre sessions (sessions pooled within grade; p = 1 when
both groups together hold at most two distinct values), Benjamini-Hochberg
over every test in the table; ``*`` when q < 0.05.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CONTACT_WINDOW_S: tuple[float, float] = (0.0, 5.0)
CLASSES: tuple[str, ...] = ("complete", "incomplete", "jaw_only", "no_resp")
POST_EPOCHS: tuple[str, ...] = ("acute", "subacute", "chronic")
Q_STAR = 0.05


def classify_session(npz_path: Path, candidate_trials: pd.DataFrame, animal: str, date: str) -> pd.DataFrame | None:
    """Outcome class of every cued trial of one session.

    Parameters
    ----------
    npz_path : Path
        ``spout_behavior/licks_and_rewards/<animal>/<date>.npz`` (``Fs``,
        ``Tone_R``, ``Tone_L``, ``Lick_R``, ``Lick_L`` in samples).
    candidate_trials : pd.DataFrame
        ``dlc_kinematics/tongue_jaw_mismatch/candidate_trials/<animal>/<date>.parquet``.

    Returns
    -------
    pd.DataFrame or None
        Columns ``animal``, ``date``, ``rel_day``, ``trial``, ``cue_side``,
        ``cls``, ``jaw_pass_qc``; None when the trial counts disagree (the
        session is skipped, as in the manuscript).
    """
    z = np.load(npz_path, allow_pickle=True)
    fs = float(z["Fs"])
    # Trials in tone-onset order; trial_index of the candidate table indexes this list.
    tones = sorted([(int(t), "R") for t in z["Tone_R"]] + [(int(t), "L") for t in z["Tone_L"]])
    licks = np.sort(np.concatenate([z["Lick_R"], z["Lick_L"]]))
    if len(candidate_trials) != len(tones):
        return None
    rows = []
    for r in candidate_trials.itertuples(index=False):
        t, side = tones[int(r.trial_index)]
        lo, hi = t + CONTACT_WINDOW_S[0] * fs, t + CONTACT_WINDOW_S[1] * fs
        if bool(((licks > lo) & (licks <= hi)).any()):
            c = "complete"
        elif r.n_licks_in_quiet_win > 0:
            c = "incomplete"
        elif bool(r.candidate_no_lick_with_jaw_move):
            c = "jaw_only"
        else:
            c = "no_resp"
        rows.append({"animal": animal, "date": date, "rel_day": int(r.rel_day), "trial": int(r.trial_index),
                     "cue_side": side, "cls": c, "jaw_pass_qc": bool(r.jaw_pass_qc)})
    return pd.DataFrame(rows)


def session_fractions(trials: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Per-session class fractions (columns :data:`CLASSES`, missing classes = 0)."""
    f = (trials.groupby([*keys, "animal", "date", "epoch"]).cls.value_counts(normalize=True)
         .unstack().reindex(columns=list(CLASSES)).fillna(0))
    return f.reset_index()


def bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values (the manuscript's implementation; equals statsmodels fdr_bh)."""
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = np.empty_like(p)
    m = len(p)
    q[o] = np.minimum.accumulate((p[o] * m / np.arange(1, m + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def mwu_vs_pre(trials: pd.DataFrame) -> pd.DataFrame:
    """Session MWU of each post epoch vs pre per grade x cue side x class, BH over the table.

    ``trials`` needs ``grp`` (grade), ``side`` (``contra`` / ``ipsi``),
    ``epoch`` (``pre`` / :data:`POST_EPOCHS`), ``animal``, ``date``, ``cls``.
    ``delta`` = mean post-session fraction minus mean pre-session fraction.
    """
    from scipy.stats import mannwhitneyu

    s = session_fractions(trials, ["grp", "side"])
    rows = []
    for (g, sd), d in s.groupby(["grp", "side"]):
        pre = d[d.epoch == "pre"]
        for e in POST_EPOCHS:
            post = d[d.epoch == e]
            for c in CLASSES:
                if len(post) and len(pre):
                    # MWU is undefined when every value is tied; such a cell cannot differ.
                    p = mannwhitneyu(post[c], pre[c]).pvalue if (post[c].nunique() + pre[c].nunique()) > 2 else 1.0
                    rows.append({"cohort": 1, "group": g, "side": sd, "epoch": e, "cls": c,
                                 "delta": post[c].mean() - pre[c].mean(), "p": p,
                                 "n_pre": len(pre), "n_post": len(post)})
    t = pd.DataFrame(rows)
    t["q"] = bh(t.p)
    t["star"] = np.where(t.q < Q_STAR, "*", "")
    return t


def aligned_vs_pre(trials: pd.DataFrame) -> pd.DataFrame:
    """Fig 2B cells under the cohort-aligned rule (Priya 2026-11-19 / 11-20).

    Same cells as :func:`mwu_vs_pre` (grade x cue side x post epoch x class), but
    each session fraction is first expressed as the change from the animal's OWN
    pre-stroke mean (per animal x cue side x class); then per cell the session
    Mann-Whitney U (post vs pre changes) and the nested animals -> sessions
    bootstrap CI (``pooled_endpoint_suite.compute_endpoint_cell_suite(
    test_set="c2_aligned")``, 4,000 draws, 95 % percentile). BH-FDR over every
    row of the table (one family, as in :func:`mwu_vs_pre`);
    ``star = "**"`` when q < 0.05 AND the bootstrap CI excludes 0.
    Animals without pre sessions on that cue side drop out of the cell.
    """
    from stroke_orofacial.stats import pooled_endpoint_suite as suite

    s = session_fractions(trials, ["grp", "side"])
    long = s.melt(id_vars=["grp", "side", "animal", "date", "epoch"], value_vars=list(CLASSES),
                  var_name="cls", value_name="value")
    pre = (long[long.epoch == "pre"].groupby(["animal", "side", "cls"]).value.mean().rename("pre_mean"))
    long = long.merge(pre.reset_index(), on=["animal", "side", "cls"], how="left")
    long["value_norm"] = long.value - long.pre_mean
    long = long.dropna(subset=["value_norm"])
    rows = []
    for (g, sd, c), d in long.groupby(["grp", "side", "cls"]):
        for e in POST_EPOCHS:
            if not (d.epoch == e).any() or not (d.epoch == "pre").any():
                continue
            r = suite.compute_endpoint_cell_suite(d, post_epoch=e, value_col="value_norm", epoch_col="epoch",
                                                  animal_col="animal", test_set="c2_aligned")
            rows.append({"cohort": 1, "group": g, "side": sd, "epoch": e, "cls": c,
                         "delta": r["nb_effect"], "ci_lo": r["nb_ci_lo"], "ci_hi": r["nb_ci_hi"],
                         "ci_excludes_0": r["nb_excludes_zero"], "p": r["mwu_session_p"],
                         "n_animals": r["nb_n_animals"], "n_pre": r["n_pre_sessions"],
                         "n_post": r["n_post_sessions"],
                         "session_mean_delta": float(d[d.epoch == e].value_norm.mean())})
    t = pd.DataFrame(rows)
    # MWU p is NaN only when a cell has no finite values; such a cell cannot be starred.
    t["q"] = np.nan
    ok = t.p.notna()
    t.loc[ok, "q"] = bh(t.loc[ok, "p"])
    t["star"] = np.where((t.q < Q_STAR) & t.ci_excludes_0.astype(bool), "**", "")
    return t


def compare_stars(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Old (session MWU, q < 0.05) vs aligned (q < 0.05 AND CI excludes 0) star per cell."""
    k = ["group", "side", "epoch", "cls"]
    o = old[k + ["delta", "p", "q", "star"]].rename(columns={"delta": "old_delta", "p": "old_p", "q": "old_q",
                                                            "star": "old_star"})
    n = new[k + ["delta", "ci_lo", "ci_hi", "p", "q", "star", "n_animals"]].rename(
        columns={"delta": "new_delta", "p": "new_p", "q": "new_q", "star": "new_star"})
    m = o.merge(n, on=k, how="outer")
    for c in ("old_star", "new_star"):
        m[c] = m[c].fillna("")
    was, now = m.old_star != "", m.new_star != ""
    m["change"] = np.select([was & now, was & ~now, ~was & now], ["kept", "lost", "gained"], "none")
    return m


def override_jaw_only(trials: pd.DataFrame, flags: pd.DataFrame, col: str) -> pd.DataFrame:
    """Re-split the no-contact, no-tongue trials into ``jaw_only`` / ``no_resp`` from a per-trial boolean.

    ``flags`` is keyed by ``animal``, ``date`` (YYYYMMDD) and ``trial_index`` (the candidate-table index =
    ``trials.trial``) and carries the boolean ``col`` (True = jaw-only trial under the new rule). ``complete``
    and ``incomplete`` are untouched; every trial currently ``jaw_only`` or ``no_resp`` must have a flag row
    (raises otherwise). A NaN flag = unknown: that jaw_only / no_resp trial is DROPPED (as cohort 2 drops
    'unknown'). Returns a copy with ``cls`` rewritten and ``cls_v1`` = the original class.
    """
    f = flags[["animal", "date", "trial_index", col]].copy()
    f["date"] = f.date.astype(str)
    f = f.rename(columns={"trial_index": "trial", col: "_jaw"})
    if f.duplicated(["animal", "date", "trial"]).any():
        raise ValueError("jaw flags: duplicate animal/date/trial_index rows")
    t = trials.copy()
    t["date"] = t.date.astype(str)
    t = t.merge(f, on=["animal", "date", "trial"], how="left", validate="many_to_one", indicator=True)
    open_ = t.cls.isin(["jaw_only", "no_resp"])
    miss = open_ & (t._merge == "left_only")
    if miss.any():
        raise ValueError(f"jaw flags missing for {int(miss.sum())} jaw_only/no_resp trials "
                         f"(e.g. {t.loc[miss, ['animal', 'date', 'trial']].head(3).to_dict('records')})")
    t = t[~(open_ & t._jaw.isna())].copy()            # unknown -> dropped
    open_ = t.cls.isin(["jaw_only", "no_resp"])
    t["cls_v1"] = t.cls
    t.loc[open_, "cls"] = np.where(t.loc[open_, "_jaw"].astype(bool), "jaw_only", "no_resp")
    return t.drop(columns=["_jaw", "_merge"])


def distribution_vs_pre(trials: pd.DataFrame, **kw) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fig 2B: ONE change-in-distribution test per bar (grade x cue side x post epoch; Priya 2026-11-20).

    Same session x (grade, cue side) class fractions as :func:`aligned_vs_pre`; the test (per-animal TVD of the
    epoch vs own-pre mean composition, animal-weighted D, within-animal label permutation, BH over every cell,
    ``star_dist`` = q < 0.05) is :func:`stroke_orofacial.stats.composition_test.distribution_tests`.
    Returns (cells, per_animal); ``group`` = grade.
    """
    from stroke_orofacial.stats import composition_test as ct

    s = session_fractions(trials, ["grp", "side"])
    cells, per = ct.distribution_tests(s, CLASSES, ["grp", "side"], POST_EPOCHS, **kw)
    cells.insert(0, "cohort", 1)
    return cells.rename(columns={"grp": "group"}), per.rename(columns={"grp": "group"})


def compare_distribution_aligned(cells: pd.DataFrame, aligned: pd.DataFrame) -> pd.DataFrame:
    """Each bar's distribution star next to the per-class aligned stars of the same bar."""
    k = ["group", "side", "epoch"]
    st = (aligned[aligned.star.fillna("") != ""].groupby(k).cls.apply(";".join).rename("aligned_classes"))
    m = cells[[*k, "star_dist", "D", "p", "p_min", "q", "n_animals"]].merge(st.reset_index(), on=k, how="left")
    m["aligned_classes"] = m.aligned_classes.fillna("")
    m["any_aligned_star"] = (m.aligned_classes != "").astype(int)
    m["agree"] = (m.any_aligned_star == m.star_dist).astype(int)
    return m
