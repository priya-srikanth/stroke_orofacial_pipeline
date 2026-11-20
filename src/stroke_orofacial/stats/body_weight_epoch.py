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
