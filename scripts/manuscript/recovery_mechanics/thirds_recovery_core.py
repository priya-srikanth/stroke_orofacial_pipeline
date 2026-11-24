"""Within- vs between-session aim recovery on session thirds: ONE analysis for both cohorts (Priya 11-23).

Shared by the two-tone S8E (`c1_thirds_boot.py`, stroke_orofacial_pipeline) and the six-position S12F
(`scripts/caption_review_1123/s12f_thirds_boot.py`, widefield_pipeline). The two copies of this file are identical;
only the bootstrap callable (each repo's own paired animals -> sessions bootstrap, which are ports of one another)
and the plot colors differ.

Input: a session table with one row per scored session: animal, label, day (calendar day relative to stroke), post
(0 = pre-stroke, 1 = post-stroke window), early / mid / late (mean of the first, middle and last third of the
session's scored first licks, np.array_split order) and M (mean of all scored first licks).

Quantities (per animal, then change from the animal's own pre-stroke value):
  W  within-session       late third - early third of the same session (one value per session);
  O  overnight            early third of the next session - late third of this session (one value per pair);
  S  session-to-session   next session mean - this session mean (one value per pair).
Pairs: consecutive scored sessions of an animal in the same period (pre-pre or post-post), gap <= MAX_GAP days
(primary) or gap == 1 day (secondary).

Stroke effect = mean over animals of (animal's post mean - animal's pre mean): the paired, animal-weighted
animals -> sessions bootstrap (4,000 draws, seed 0, 95% percentile CI; * = CI excludes 0).
Backup: linear mixed model on the thirds themselves, random intercept per animal and per session (W) or per session
pair (O, S), nested in the animal; REML, Wald 95% CI; the stroke effect is the interaction term.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MAX_GAP = 2
QUANT = [("W", "within session (late - early third)", None),
         ("O", "overnight (next early - this late third)", MAX_GAP),
         ("S", "session to session (next - this session mean)", MAX_GAP),
         ("O1", "overnight, 1-day gaps only", 1),
         ("S1", "session to session, 1-day gaps only", 1)]


def pairs(S: pd.DataFrame, max_gap: int) -> pd.DataFrame:
    rows = []
    for an, g in S.sort_values(["animal", "day"]).groupby("animal", sort=True):
        g = g.reset_index(drop=True)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            gap = int(b.day - a.day)
            if gap < 1 or gap > max_gap or a.post != b.post:
                continue
            rows.append({"animal": an, "label_d": a.label, "label_d1": b.label, "day_d": int(a.day), "gap": gap,
                         "post": int(a.post), "O": b.early - a.late, "S": b.M - a.M,
                         "late_d": a.late, "early_d1": b.early, "M_d": a.M, "M_d1": b.M})
    return pd.DataFrame(rows)


def unit_tables(S: pd.DataFrame) -> dict:
    """quantity -> per-unit table (animal, post, value)."""
    W = S.assign(value=S.late - S.early)[["animal", "label", "day", "post", "value"]]
    out = {"W": W}
    for k, gap in (("", MAX_GAP), ("1", 1)):
        P = pairs(S, gap)
        out["O" + k] = P.assign(value=P.O)
        out["S" + k] = P.assign(value=P.S)
    return out


def per_animal(U: pd.DataFrame) -> pd.DataFrame:
    g = U.groupby(["animal", "post"]).value.agg(["mean", "size"]).unstack("post")
    r = pd.DataFrame({"pre": g[("mean", 0)], "post": g[("mean", 1)], "n_pre": g[("size", 0)],
                      "n_post": g[("size", 1)]}) if (("mean", 0) in g and ("mean", 1) in g) else pd.DataFrame()
    if len(r):
        r["effect"] = r.post - r.pre
    return r


def lmm(S: pd.DataFrame, q: str) -> dict:
    """Backup mixed model on the thirds: y ~ k * post, random intercept animal + session (W) / pair (O, S)."""
    import statsmodels.formula.api as smf
    if q == "W":
        d = pd.concat([S.assign(y=S.early, k=0), S.assign(y=S.late, k=1)])
        d["unit"] = d.label
    else:
        P = pairs(S, 1 if q.endswith("1") else MAX_GAP).reset_index(drop=True)
        P["unit"] = np.arange(len(P)).astype(str)
        a, b = ("late_d", "early_d1") if q.startswith("O") else ("M_d", "M_d1")
        d = pd.concat([P.assign(y=P[a], k=0), P.assign(y=P[b], k=1)])
    d = d[["animal", "unit", "post", "k", "y"]].dropna().reset_index(drop=True)
    res = {"lmm_n_obs": len(d), "lmm_n_units": d.unit.nunique(), "lmm_n_animals": d.animal.nunique()}
    if d.post.nunique() < 2 or d.animal.nunique() < 2:
        return {**res, "lmm_note": "not estimable"}
    try:
        m = smf.mixedlm("y ~ k * post", d, groups=d["animal"], vc_formula={"unit": "0 + C(unit)"},
                        re_formula="1").fit(reml=True, method=["lbfgs", "powell"])
        ci = m.conf_int()
        return {**res, "lmm_pre": float(m.params["k"]), "lmm_effect": float(m.params["k:post"]),
                "lmm_lo": float(ci.loc["k:post", 0]), "lmm_hi": float(ci.loc["k:post", 1]),
                "lmm_p": float(m.pvalues["k:post"]), "lmm_converged": bool(m.converged)}
    except Exception as ex:  # noqa: BLE001
        return {**res, "lmm_note": f"error: {str(ex)[:120]}"}


def analyze(S: pd.DataFrame, group: str, boot, num: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """boot(post: {animal: [values]}, pre: {animal: [values]}) -> (effect, lo, hi). Returns (summary, per-animal)."""
    U = unit_tables(S)
    rows, pa_rows = [], []
    for q, name, gap in QUANT:
        T = U[q].dropna(subset=["value"])
        A = per_animal(T)
        if len(A):   # manuscript-label order (#1, #2, ...)
            A = A.loc[sorted(A.index, key=lambda a: int(str(num.get(a, "#0")).lstrip("#") or 0))]
        pre = {a: list(h.value) for a, h in T[T.post == 0].groupby("animal")}
        post = {a: list(h.value) for a, h in T[T.post == 1].groupby("animal")}
        eff, lo, hi = boot(post, pre) if len(set(pre) & set(post)) >= 2 else (np.nan, np.nan, np.nan)
        same = int(((np.sign(A.effect) == np.sign(eff)) & (A.effect != 0)).sum()) if len(A) and np.isfinite(eff) else 0
        rows.append({"group": group, "quantity": q, "name": name, "max_gap_days": gap,
                     "pre_value": A.pre.mean() if len(A) else np.nan,
                     "post_value": A.post.mean() if len(A) else np.nan,
                     "boot_effect": eff, "boot_lo": lo, "boot_hi": hi,
                     "star": bool(np.isfinite(lo) and (lo > 0 or hi < 0)),
                     "n_animals": len(A), "n_same_sign": same,
                     "n_units_pre": int((T.post == 0).sum()), "n_units_post": int((T.post == 1).sum()),
                     "per_animal": "; ".join(f"{num.get(a, a)} {r.pre:+.1f} -> {r.post:+.1f} ({r.effect:+.1f})"
                                             for a, r in A.iterrows()),
                     **lmm(S, q)})
        for a, r in A.iterrows():
            pa_rows.append({"group": group, "quantity": q, "animal": a, "num": num.get(a, a), **r.to_dict()})
    return pd.DataFrame(rows), pd.DataFrame(pa_rows)


def fmt_row(r) -> str:
    lm = (f"{r.lmm_effect:+.1f} [{r.lmm_lo:+.1f}, {r.lmm_hi:+.1f}], p = {r.lmm_p:.3f}"
          if np.isfinite(r.get("lmm_effect", np.nan)) else r.get("lmm_note", "n/a"))
    bo = (f"{r.boot_effect:+.1f} [{r.boot_lo:+.1f}, {r.boot_hi:+.1f}]{' *' if r.star else ''}"
          if np.isfinite(r.boot_effect) else "n/a")
    return (f"| {r['name']} | {r.pre_value:+.1f} | {r.post_value:+.1f} | {bo} | {lm} | {r.per_animal} | "
            f"{r.n_same_sign}/{r.n_animals} |")


def draw_animal(ax, d: pd.DataFrame, color_of, marker: str, ms: float, n_pre: int = 3, pre_label_fs: float = 6.5):
    """One animal: last n_pre pre-stroke sessions (gray) then the post-stroke window, each session its early / mid /
    late thirds joined by a solid line; dashed = next calendar day, dotted = longer gap. y = change from the animal's
    pre-stroke value (mean of its pre-stroke session means). No day axis."""
    d = d.sort_values("day")
    b0 = d[d.post == 0].M.mean()
    seq = pd.concat([d[d.post == 0].tail(n_pre), d[d.post == 1]])
    x, prev = 0.0, None
    for _, r in seq.iterrows():
        xs = [x, x + 0.5, x + 1.0]
        ys = [r.early - b0, r.mid - b0, r.late - b0]
        col = "0.3" if r.post == 0 else color_of(r)
        ax.plot(xs, ys, "-", color=col, lw=0.9, zorder=2)
        ax.plot(xs, ys, marker, color=col, ms=ms, mec="none", zorder=3)
        if prev is not None:
            ax.plot([prev[0], xs[0]], [prev[1], ys[0]], "--" if r.day - prev[2] == 1 else ":", color="0.55", lw=0.7,
                    zorder=1)
        prev = (xs[-1], ys[-1], r.day)
        x += 1.6
    npre = min(n_pre, int((d.post == 0).sum()))
    ax.axhline(0, color="0.6", lw=0.6, ls="--", zorder=0)
    ax.set_xticks([])
    ax.set_xlim(-0.5, x - 0.1)
    ax.text((npre - 1) * 1.6 / 2 + 0.5, -0.03, "pre", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=pre_label_fs, color="0.3")
    return b0
