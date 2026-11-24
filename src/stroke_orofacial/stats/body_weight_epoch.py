"""Body weight by recovery epoch with a linear mixed model (two-tone cohort).

Manuscript Figure 1F (v41). Ported from the cohort-1 part of the manuscript's
``figures/weights_by_epoch.py``; the six-position cohort's model lives in
widefield_pipeline.

- Weight on each day as % of the animal's mean pre-stroke weight (all
  pre-stroke days, ``day <= 0``, in the Weights sheet).
- Epoch per animal-day: ``pre`` (day <= 0), ``acute`` (day <= acute max),
  ``subacute`` (day < chronic min), else ``chronic``; boundaries are the
  stamped ones (``configs/animals.yaml``, or the stamped columns of an epoch
  table such as ``derived_epoch_boundaries_ps47d5.csv``).
- Model (statsmodels MixedLM, REML, random intercept per animal, animal-day
  observations): ``pct ~ C(epoch, pre) * C(grade, mild)``; each post epoch vs
  pre within each grade (9 linear contrasts, Wald z, normal 95% CI),
  Benjamini-Hochberg over the 9; marks ``*`` q < 0.05, ``**`` < 0.01,
  ``***`` < 0.001.
- ``epoch_tests_c2_aligned`` (2026-11-23, Figure 1K as unified): the same
  animal-days tested by the two-tone behavior-panel rule (session MWU + BH over
  the 9 cells, AND the nested animals -> days bootstrap; ``**`` only).
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

import numpy as np
import pandas as pd

EPOCHS: tuple[str, ...] = ("pre", "acute", "subacute", "chronic")
GRADES: tuple[str, ...] = ("mild", "moderate", "severe")
# Layout of the Weights sheet of Stroke_quantification.xlsx: two blocks, each a
# date column followed by one column per animal; data rows start at row 3.
WEIGHTS_SHEET = "Weights"
WEIGHTS_BLOCKS: tuple[tuple[int, tuple[tuple[int, str], ...]], ...] = (
    (0, ((1, "PS46"), (2, "PS47"), (3, "PS48"), (4, "PS49"), (5, "PS50"))),
    (7, ((8, "PS51"), (9, "PS54"), (10, "PS55"))),
)
WEIGHTS_FIRST_ROW = 2


def read_weights_sheet(xlsx, stroke_dates: Mapping[str, dt.date]) -> pd.DataFrame:
    """Daily weights (g) per animal with ``day`` relative to the stroke date.

    Returns columns ``animal``, ``day``, ``g`` and ``pct`` (% of the animal's
    mean pre-stroke weight).
    """
    w = pd.read_excel(xlsx, sheet_name=WEIGHTS_SHEET, header=None)
    rows = []
    for _, r in w.iloc[WEIGHTS_FIRST_ROW:].iterrows():
        for dcol, mice in WEIGHTS_BLOCKS:
            d = pd.to_datetime(r.iloc[dcol], errors="coerce")
            if pd.isna(d):
                continue
            for c, m in mice:
                v = pd.to_numeric(r.iloc[c], errors="coerce")
                if pd.notna(v):
                    rows.append((m, (d.date() - stroke_dates[m]).days, float(v)))
    df = pd.DataFrame(rows, columns=["animal", "day", "g"])
    df["pct"] = 100 * df.g / df.animal.map(df[df.day <= 0].groupby("animal").g.mean())
    return df


def assign_epochs(df: pd.DataFrame, bounds: Mapping[str, tuple[int, int]]) -> pd.Series:
    """Epoch per row from ``{animal: (acute_max_day, chronic_min_day)}``."""
    def ep(a, d):
        if d <= 0:
            return "pre"
        am, cm = bounds[a]
        return "acute" if d <= am else "subacute" if d < cm else "chronic"
    return pd.Series([ep(a, d) for a, d in zip(df.animal, df.day)], index=df.index)


def lmm_epoch_by_grade(df: pd.DataFrame, grades: tuple[str, ...] = GRADES) -> pd.DataFrame:
    """Epoch-vs-pre contrasts within each grade from ``pct ~ epoch * grade`` (random intercept animal).

    ``df`` needs ``pct``, ``epoch``, ``group`` (grade), ``animal``. Returns
    ``group``, ``epoch``, ``diff_pct``, ``ci_lo``, ``ci_hi``, ``p``, ``q``, ``stars``.
    """
    import statsmodels.formula.api as smf
    from scipy.stats import norm
    from statsmodels.stats.multitest import multipletests

    x = df.copy()
    x["epoch"] = pd.Categorical(x.epoch, list(EPOCHS))
    x["group"] = pd.Categorical(x.group, list(grades))
    r = smf.mixedlm(f"pct ~ C(epoch, Treatment('pre')) * C(group, Treatment('{grades[0]}'))", x,
                    groups=x.animal).fit(reml=True)
    names = list(r.params.index)
    cov = r.cov_params()
    rows = []
    for g in grades:
        for e in EPOCHS[1:]:
            L = pd.Series(0.0, index=names)
            L[f"C(epoch, Treatment('pre'))[T.{e}]"] = 1
            if g != grades[0]:
                L[f"C(epoch, Treatment('pre'))[T.{e}]:C(group, Treatment('{grades[0]}'))[T.{g}]"] = 1
            L = L[[n for n in names if n in cov.index]]
            est = float(L @ r.params[L.index])
            se = float(np.sqrt(L @ cov.loc[L.index, L.index] @ L))
            rows.append((g, e, est, est - 1.96 * se, est + 1.96 * se, 2 * norm.sf(abs(est / se))))
    t = pd.DataFrame(rows, columns=["group", "epoch", "diff_pct", "ci_lo", "ci_hi", "p"])
    t["q"] = multipletests(t.p, method="fdr_bh")[1]
    t["stars"] = ["***" if q < 0.001 else "**" if q < 0.01 else "*" if q < 0.05 else "" for q in t.q]
    return t


def epoch_tests_c2_aligned(df: pd.DataFrame, *, n_boot: int, grades: tuple[str, ...] = GRADES,
                           seed: int = 0) -> pd.DataFrame:
    """Each post epoch vs pre within each grade, by the rule of the two-tone behavior panels (VLS manuscript, 2026-11-23).

    The c2-aligned scalar rule (``pooled_endpoint_suite.compute_endpoint_cell_suite(test_set="c2_aligned")`` plus
    ``build_pooled_phenotype_stats._attach_c2_aligned``) applied to body weight, with one animal-day as the session:

    - value = each day's ``pct`` minus the animal's own mean pre-stroke ``pct`` (= ``pct - 100``, since ``pct`` is
      already % of that mean);
    - session-level two-sided Mann-Whitney U, post-epoch days vs pre-stroke days of the grade
      (``pooled_endpoint_suite._session_mwu``);
    - paired, animal-weighted nested bootstrap (animals, then days within animal) of the change
      (``nested_animal_bootstrap_ci``; ``n_boot`` is required so the caller states it; a cell with < 2 animals has no
      interval and is not marked);
    - Benjamini-Hochberg over the grade x epoch cells of this call only (the weight panel's own family);
    - ``star`` = ``"**"`` when q < 0.05 AND the interval excludes 0, else ``""`` (the behavior panels draw no single
      ``*``); ``boot_only`` flags cells whose interval excludes 0 without the MWU passing.

    ``df`` needs ``animal``, ``pct``, ``epoch`` and ``group`` (grade). Returns one row per (group, epoch).
    """
    from statsmodels.stats.multitest import multipletests

    from stroke_orofacial.stats import pooled_endpoint_suite as suite

    x = df.copy()
    x["value"] = x.pct - x.animal.map(x[x.epoch == "pre"].groupby("animal").pct.mean())
    rows = []
    for g in grades:
        sub = x[x.group == g]
        pre = sub.loc[sub.epoch == "pre", "value"].to_numpy()
        for e in EPOCHS[1:]:
            post = sub.loc[sub.epoch == e, "value"].to_numpy()
            if post.size == 0:
                continue
            u, p = suite._session_mwu(pre, post)
            nb = suite.nested_animal_bootstrap_ci(sub, post_epoch=e, value_col="value", epoch_col="epoch",
                                                  animal_col="animal", n_boot=n_boot, seed=seed)
            rows.append({"group": g, "epoch": e, "n_animals": int(sub.loc[sub.epoch == e, "animal"].nunique()),
                         "n_pre_days": int(pre.size), "n_post_days": int(post.size),
                         "mean_change_days": float(post.mean() - pre.mean()),
                         "mwu_u": u, "mwu_p": p, **nb, "n_boot": int(n_boot)})
    t = pd.DataFrame(rows)
    ok = np.isfinite(t.mwu_p.to_numpy(float))
    t["mwu_q"] = np.nan
    if ok.any():
        t.loc[ok, "mwu_q"] = multipletests(t.loc[ok, "mwu_p"], method="fdr_bh")[1]
    t["headline_sig"] = t.mwu_q < 0.05
    t["headline_and_bootstrap_sig"] = t.headline_sig & t.nb_excludes_zero.astype(bool)
    t["boot_only"] = t.nb_excludes_zero.astype(bool) & ~t.headline_sig
    t["star"] = np.where(t.headline_and_bootstrap_sig, "**", "")
    return t
