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
