"""Mean vs median for per-lick kinematic measures, both cohorts (CC-B, 2026-11-23; Priya: justify the session
aggregation with data). Descriptive only; no statistics family is touched.

Lick sets: all post-cue licks, licks 1-5 of each trial, first lick of each trial.
Session aggregations: mean, median, per-trial median -> session mean (sets all / 1-5; the live two-tone form),
mean over FULL licks only (licks >= 50 % of the animal's pre-stroke median for that measure, side / position and set).

Cohort 1 (two-tone, #1-#8 = PS46-PS55, 2-D front camera; session unit = animal x date x cue side):
  trials: non-sentinel rows of stats/inputs/filtered_v1/<slug>/ (xy slug for protrusion / angle / times,
  vxy slug for speed), as scripts/manuscript/c1_sessmean_scalars.py;
  protrusion = hypot(x, y) at each lick's peak and angle = peak_angle_deg (dlc_kinematics/lick_events, v7-kept licks,
  [70, 3000] ms); lick order by t_ms within the trial (as c1_licks15_candidate.py);
  speed = onset -> peak per-lick vxy peak (stats/inputs/sessmean_licks/speed_onsetpeak_per_lick, lick_k order);
  latency = t_ms of the trial's first lick; ILI = successive t_ms differences within the trial.
Cohort 2 (six-position, #9-#12 = PS92-PS95, four-camera 3-D; session unit = session x spout position):
  pose3d_4cam_3net_20261121_sync60/kinematics_fused_postcue/licks.csv.gz (post-cue fused train; measures only where
  n_views >= 2, i.e. finite reach_mm), early pre sessions (< 0806) dropped as c2_lick3d_session_summary.py;
  reach = reach_mm, speed = speed_peak (onset -> 3-D extension peak), angle = midline (deg, atan2(lateral, sagittal)
  at the 3-D peak); latency = on_ms of lick_idx 0; ILI = successive daq_peak_s differences within the trial.

Usage: python scripts/manuscript/mean_vs_median_licks.py build|analyze OUT_DIR
Writes NEW files under OUT_DIR only.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
PO = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs")
C2_LICKS = Path("M:/MICROSCOPE/Priya/DeepLabCut/Widefield/session_poses/pose3d_4cam_3net_20261121_sync60/"
                "kinematics_fused_postcue/licks.csv.gz")
LABEL = {"PS47": "#1", "PS48": "#2", "PS49": "#3", "PS50": "#4", "PS46": "#5", "PS51": "#6", "PS54": "#7",
         "PS55": "#8", "PS92": "#9", "PS93": "#10", "PS94": "#11", "PS95": "#12"}
GRADE = {"PS47": "mild", "PS48": "mild", "PS49": "mild", "PS50": "mild", "PS46": "moderate", "PS51": "moderate",
         "PS54": "severe", "PS55": "severe"}
EPOCHS = ["pre", "acute", "subacute", "chronic"]
SETS = ["all", "first5", "first"]
SIZE = {"protrusion", "speed"}
AGGS = ["mean", "median", "trialmed_mean", "fullmean"]
MIN_N = {"c1": 5, "c2": 20}
U = ["cohort", "animal", "session", "group", "epoch"]   # session unit


# ----------------------------------------------------------------------------------------------------------- build
def _c1_trials(slug: str) -> pd.DataFrame:
    t = pd.concat([pd.read_parquet(p) for p in sorted((PO / "stats/inputs/filtered_v1" / slug).glob("*.parquet"))])
    t = t[~t.is_sentinel.astype(bool)].dropna(subset=["value"])
    t["session"] = pd.to_datetime(t.date).dt.strftime("%Y%m%d")
    return t[["animal", "session", "trial_idx", "side", "ipsi_contra", "epoch_label"]].drop_duplicates()


def build_c1() -> pd.DataFrame:
    out = []
    T = _c1_trials("tongue_median_xy_peak_per_trial")
    for (animal, ses), tr in T.groupby(["animal", "session"]):
        le = pd.read_parquet(PO / "dlc_kinematics/lick_events/tongue" / animal / f"{ses}.parquet",
                             columns=["trial", "side", "t_ms", "x", "y", "peak_angle_deg"])
        le = le.rename(columns={"trial": "trial_idx"})
        le["t_ms"] = pd.to_numeric(le.t_ms, errors="coerce")
        le["protrusion"] = np.hypot(le.x.astype(float), le.y.astype(float))
        le = le[np.isfinite(le.protrusion) & np.isfinite(le.t_ms)].sort_values(["trial_idx", "side", "t_ms"])
        le["k"] = le.groupby(["trial_idx", "side"]).cumcount()
        le["ili"] = le.groupby(["trial_idx", "side"]).t_ms.diff()
        le = le.merge(tr, on=["trial_idx", "side"])
        for m, col in (("protrusion", "protrusion"), ("angle", "peak_angle_deg"), ("ili", "ili")):
            d = le[["animal", "session", "ipsi_contra", "epoch_label", "trial_idx", "k", col]].rename(columns={col: "value"})
            out.append(d.assign(measure=m))
        f = le[le.k == 0][["animal", "session", "ipsi_contra", "epoch_label", "trial_idx", "k", "t_ms"]]
        out.append(f.rename(columns={"t_ms": "value"}).assign(measure="latency"))
    V = pd.concat([pd.read_parquet(p) for p in sorted((PO / "stats/inputs/sessmean_licks/speed_onsetpeak_per_lick")
                                                       .glob("speed_onsetpeak_PS*.parquet"))])
    V["session"] = pd.to_datetime(V.date).dt.strftime("%Y%m%d")
    V = V.merge(_c1_trials("tongue_median_vxy_peak_per_trial"), on=["animal", "session", "trial_idx", "side"])
    out.append(V[["animal", "session", "ipsi_contra", "epoch_label", "trial_idx", "lick_k", "vxy_peak"]]
               .rename(columns={"lick_k": "k", "vxy_peak": "value"}).assign(measure="speed"))
    L = pd.concat(out, ignore_index=True).rename(columns={"ipsi_contra": "group", "epoch_label": "epoch",
                                                         "trial_idx": "trial"})
    L["epoch"] = L.epoch.replace({"sub_acute": "subacute"})
    return L.assign(cohort="c1")


def build_c2() -> pd.DataFrame:
    L = pd.read_csv(C2_LICKS, usecols=["trial_id", "lick_idx", "position", "reach_mm", "speed_peak", "midline", "animal",
                                       "date", "session", "epoch", "on_ms", "daq_peak_s"])
    L = L[~((L.epoch == "pre") & (L.date.astype(str).str[4:] < "0806"))]
    L = L.sort_values(["session", "trial_id", "lick_idx"])
    L["ili"] = L.groupby(["session", "trial_id"]).daq_peak_s.diff() * 1000
    out = []
    for m, col in (("protrusion", "reach_mm"), ("speed", "speed_peak"), ("angle", "midline"), ("ili", "ili")):
        out.append(L[["animal", "session", "position", "epoch", "trial_id", "lick_idx", col]]
                   .rename(columns={col: "value"}).assign(measure=m))
    f = L[L.lick_idx == 0]
    out.append(f[["animal", "session", "position", "epoch", "trial_id", "lick_idx", "on_ms"]]
               .rename(columns={"on_ms": "value"}).assign(measure="latency"))
    L = pd.concat(out, ignore_index=True).rename(columns={"position": "group", "trial_id": "trial", "lick_idx": "k"})
    return L.assign(cohort="c2")


# --------------------------------------------------------------------------------------------------------- analyze
def lickset(L: pd.DataFrame, s: str) -> pd.DataFrame:
    return L if s == "all" else L[L.k < 5] if s == "first5" else L[L.k == 0]


def bimodality(v: np.ndarray, rng) -> dict:
    """skew, bimodality coefficient (> 0.555 suggests bimodal), 2- vs 1-component Gaussian mixture (BIC)."""
    from sklearn.mixture import GaussianMixture
    n = len(v)
    sk, ku = stats.skew(v), stats.kurtosis(v)
    bc = (sk ** 2 + 1) / (ku + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))
    x = (rng.choice(v, 1500, replace=False) if n > 1500 else v).reshape(-1, 1)
    g1 = GaussianMixture(1, random_state=0).fit(x)
    g2 = GaussianMixture(2, random_state=0, n_init=2).fit(x)
    lo = int(np.argmin(g2.means_.ravel()))
    return {"skew": sk, "bc": bc, "dbic_2v1": g1.bic(x) - g2.bic(x), "w_low": g2.weights_[lo],
            "mu_low_rel": g2.means_.ravel()[lo] / g2.means_.ravel()[1 - lo]}


def session_table(L: pd.DataFrame, rng) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per session unit x measure x set: aggregations, short-lick share, distribution shape, split-half halves."""
    rows, shape = [], []
    for (coh, meas), Lm in L.groupby(["cohort", "measure"]):
        if meas in ("latency", "ili"):
            continue
        for s in SETS:
            d = lickset(Lm, s).dropna(subset=["value"])
            ref = d[d.epoch == "pre"].groupby(["animal", "group"]).value.median().rename("ref")
            d = d.join(ref, on=["animal", "group"])
            for key, g in d.groupby(U):
                v = g.value.to_numpy(float)
                if len(v) < MIN_N[coh]:
                    continue
                r = dict(zip(U, key), measure=meas, lickset=s, n=len(v), n_trials=g.trial.nunique(),
                         mean=v.mean(), median=np.median(v),
                         trialmed_mean=g.groupby("trial").value.median().mean() if s != "first" else np.nan)
                if meas in SIZE:
                    full = v >= 0.5 * g.ref.iloc[0]
                    r.update(short_share=1 - full.mean(), fullmean=v[full].mean() if full.any() else np.nan)
                # split-half by trial parity (odd / even trial index)
                for h, gg in g.groupby(g.trial % 2):
                    vv = gg.value.to_numpy(float)
                    r[f"h{h}_mean"], r[f"h{h}_median"] = vv.mean(), np.median(vv)
                    r[f"h{h}_trialmed_mean"] = gg.groupby("trial").value.median().mean() if s != "first" else np.nan
                    if meas in SIZE:
                        fv = vv[vv >= 0.5 * g.ref.iloc[0]]
                        r[f"h{h}_fullmean"] = fv.mean() if len(fv) else np.nan
                rows.append(r)
                if len(v) >= 30:
                    shape.append({**dict(zip(U, key)), "measure": meas, "lickset": s, "n": len(v), **bimodality(v, rng)})
    return pd.DataFrame(rows), pd.DataFrame(shape)


def reliability(S: pd.DataFrame) -> pd.DataFrame:
    """Per cohort x measure x set x aggregation: SNR of the epoch effect, epoch eta^2, pre CV, pre ICC, split-half."""
    out = []
    for (coh, meas, s), d in S.groupby(["cohort", "measure", "lickset"]):
        for a in AGGS:
            if d[a].isna().all():
                continue
            snr, eta, cv, sh_a, sh_b, sampfrac, ws = [], [], [], [], [], [], []
            pre_units = []
            for (an, gr), g in d.groupby(["animal", "group"]):
                g = g.dropna(subset=[a])
                pre = g[g.epoch == "pre"]
                if len(pre) < 2:
                    continue
                base = pre[a].mean()
                y = g[a] - base if meas == "angle" else 100 * (g[a] / base - 1)   # % change from own pre (deg for angle)
                g = g.assign(y=y)
                ss_w, df_w = 0.0, 0
                for ep, ge in g.groupby("epoch"):
                    if len(ge) >= 2:
                        ss_w += ((ge.y - ge.y.mean()) ** 2).sum(); df_w += len(ge) - 1
                if df_w < 2:
                    continue
                sd_w = np.sqrt(ss_w / df_w)
                ws.append(sd_w)
                for ep in EPOCHS[1:]:
                    ge = g[g.epoch == ep]
                    if len(ge) >= 1:
                        snr.append({"animal": an, "group": gr, "epoch": ep, "snr": abs(ge.y.mean() - g[g.epoch == "pre"].y.mean()) / sd_w})
                ss_t = ((g.y - g.y.mean()) ** 2).sum()
                eta.append(1 - ss_w / ss_t if ss_t > 0 and len(g.epoch.unique()) > 1 else np.nan)
                pre = g[g.epoch == "pre"]
                cv.append(pre.y.std(ddof=1))      # pre session-to-session SD in % of own pre (deg for angle)
                pre_units.append(pre.assign(unit=f"{an}|{gr}"))
                h0, h1 = pre[f"h0_{a}"], pre[f"h1_{a}"]
                ok = h0.notna() & h1.notna()
                if ok.sum() >= 3:
                    sh_a.append(h0[ok] - h0[ok].mean()); sh_b.append(h1[ok] - h1[ok].mean())
                    samp = np.var(h0[ok] - h1[ok], ddof=1) / 4     # sampling variance of the full-session value
                    tot = np.var(pre[a][ok], ddof=1)
                    sampfrac.append(samp / tot if tot > 0 else np.nan)
            if not snr:
                continue
            SN = pd.DataFrame(snr)
            if sh_a:
                ha, hb = pd.concat(sh_a), pd.concat(sh_b)
                r = np.corrcoef(ha, hb)[0, 1]; rsb = 2 * r / (1 + r)
            else:
                rsb = np.nan
            P = pd.concat(pre_units)
            icc = icc1(P, a)
            out.append({"cohort": coh, "measure": meas, "lickset": s, "agg": a, "snr_median": SN.snr.median(),
                        "snr_mean": SN.snr.mean(), "n_cells": len(SN), "eta2_median": np.nanmedian(eta),
                        "within_sd_median": np.median(ws), "pre_sd_median": np.nanmedian(cv), "icc1_pre": icc,
                        "splithalf_sb": rsb, "sampling_share_median": np.nanmedian(sampfrac)})
    return pd.DataFrame(out)


def icc1(P: pd.DataFrame, a: str) -> float:
    """ICC(1) of pre session values, subjects = animal x group (raw units; between-animal spread counts as signal)."""
    g = P.groupby("unit")[a]
    k = g.size(); n = len(k)
    if n < 2:
        return np.nan
    grand = P[a].mean()
    msb = (k * (g.mean() - grand) ** 2).sum() / (n - 1)
    msw = ((P[a] - g.transform("mean")) ** 2).sum() / (len(P) - n)
    k0 = (k.sum() - (k ** 2).sum() / k.sum()) / (n - 1)
    return (msb - msw) / (msb + (k0 - 1) * msw)


def paired_snr(S: pd.DataFrame) -> pd.DataFrame:
    """Per cell (animal x group x post epoch) SNR, paired across aggregations: share of cells where agg beats mean."""
    rel = []
    for (coh, meas, s), d in S.groupby(["cohort", "measure", "lickset"]):
        per = {}
        for a in AGGS:
            if d[a].isna().all():
                continue
            vals = {}
            for (an, gr), g in d.groupby(["animal", "group"]):
                g = g.dropna(subset=[a])
                pre = g[g.epoch == "pre"]
                if len(pre) < 2:
                    continue
                y = (g[a] - pre[a].mean()) if meas == "angle" else 100 * (g[a] / pre[a].mean() - 1)
                g = g.assign(y=y)
                gg = g.groupby("epoch").y
                v = (gg.var(ddof=1) * (gg.size() - 1)).sum() / (gg.size() - 1).clip(lower=0).sum()
                for ep in EPOCHS[1:]:
                    if (g.epoch == ep).any():
                        vals[(an, gr, ep)] = abs(g[g.epoch == ep].y.mean() - g[g.epoch == "pre"].y.mean()) / np.sqrt(v)
            per[a] = pd.Series(vals)
        if "mean" not in per:
            continue
        for a, sr in per.items():
            if a == "mean":
                continue
            j = pd.concat([per["mean"], sr], axis=1, keys=["m", "a"]).dropna()
            p = stats.wilcoxon(j.a, j.m).pvalue if len(j) > 5 else np.nan
            rel.append({"cohort": coh, "measure": meas, "lickset": s, "agg_vs_mean": a, "n_cells": len(j),
                        "share_cells_higher_snr": (j.a > j.m).mean(), "median_ratio": (j.a / j.m).median(),
                        "wilcoxon_p": p})
    return pd.DataFrame(rel)


def short_share_summary(S: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = S[S.measure.isin(SIZE)].copy()
    z["grp2"] = np.where(z.cohort == "c1", z.animal.map(GRADE).fillna(""), "all")
    by = (z.groupby(["cohort", "measure", "lickset", "grp2", "epoch"]).short_share
          .agg(["count", "median", lambda x: x.quantile(.1), lambda x: x.quantile(.9)]).reset_index())
    by.columns = ["cohort", "measure", "lickset", "grade", "epoch", "n_sessions", "median", "p10", "p90"]
    w = (z.groupby(["cohort", "measure", "lickset", "animal", "group", "epoch"]).short_share.std(ddof=1)
         .groupby(["cohort", "measure", "lickset", "epoch"]).median().rename("within_animal_epoch_sd").reset_index())
    # correlation of (mean - median) with short share: raw across sessions and within animal x group (centered)
    rows = []
    for (coh, meas, s), d in z.groupby(["cohort", "measure", "lickset"]):
        diff = 100 * (d["mean"] - d["median"]) / d["median"]
        rs = stats.spearmanr(diff, d.short_share).correlation
        c = d.assign(diff=diff)
        c["dc"] = c["diff"] - c.groupby(["animal", "group"])["diff"].transform("mean")
        c["sc"] = c.short_share - c.groupby(["animal", "group"]).short_share.transform("mean")
        rw = np.corrcoef(c.dc, c.sc)[0, 1]
        sl = np.polyfit(c.sc, c.dc, 1)[0]
        rows.append({"cohort": coh, "measure": meas, "lickset": s, "n_sessions": len(d), "spearman_raw": rs,
                     "pearson_within_animal": rw, "slope_pct_per_unit_share": sl,
                     "median_mean_minus_median_pct": diff.median()})
    return by.merge(w, on=["cohort", "measure", "lickset", "epoch"], how="left"), pd.DataFrame(rows)


def figures(L: pd.DataFrame, S: pd.DataFrame, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    unit = {"c1": {"protrusion": "% of own pre median", "speed": "% of own pre median", "angle": "deg from own pre median"},
            "c2": {"protrusion": "% of own pre median", "speed": "% of own pre median", "angle": "deg from own pre median"}}
    mname = {"c1": {"protrusion": "peak protrusion (xy)", "speed": "peak speed (onset to peak)", "angle": "lick angle"},
             "c2": {"protrusion": "peak 3-D reach", "speed": "peak 3-D speed (onset to peak)", "angle": "lick angle (midline)"}}
    cols = {"pre": "#555555", "acute": "#d62728", "subacute": "#ff7f0e", "chronic": "#1f77b4"}
    for coh in ("c1", "c2"):
        Lc = L[(L.cohort == coh)]
        grps = ["mild", "moderate", "severe"] if coh == "c1" else ["all"]
        fig, ax = plt.subplots(len(SETS) * 3, len(grps), figsize=(2.4 * len(grps) + 0.6, 10), squeeze=False)
        for i, (s, meas) in enumerate([(s, m) for m in ("protrusion", "speed", "angle") for s in SETS]):
            d = lickset(Lc[Lc.measure == meas], s).dropna(subset=["value"])
            ref = d[d.epoch == "pre"].groupby(["animal", "group"]).value.median().rename("ref")
            d = d.join(ref, on=["animal", "group"])
            d["z"] = d.value - d.ref if meas == "angle" else 100 * d.value / d.ref
            d["grade"] = d.animal.map(GRADE).fillna("all")
            bins = np.linspace(-40, 40, 81) if meas == "angle" else np.linspace(0, 200, 81)
            for j, gname in enumerate(grps):
                a = ax[i, j]
                for ep in EPOCHS:
                    v = d[(d.grade == gname) & (d.epoch == ep)].z
                    if len(v) > 50:
                        a.hist(v, bins=bins, density=True, histtype="step", color=cols[ep], lw=1, label=ep)
                if meas != "angle":
                    a.axvline(50, color="k", ls=":", lw=0.7)
                if i == 0:
                    a.set_title(gname)
                if j == 0:
                    a.set_ylabel(f"{mname[coh][meas]}\n{ {'all': 'all licks', 'first5': 'licks 1-5', 'first': 'first lick'}[s]}",
                                 fontsize=7)
                a.set_yticks([])
                if i == len(SETS) * 3 - 1 or (i + 1) % 3 == 0:
                    a.set_xlabel(unit[coh][meas], fontsize=7)
        ax[0, -1].legend(frameon=False, fontsize=6)
        fig.suptitle(("Cohort 1 (two-tone, #1-#8)" if coh == "c1" else "Cohort 2 (six-position, #9-#12)")
                     + ": per-lick distributions by epoch, normalized to the animal's own pre median (dotted = 50 %)",
                     fontsize=8)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            fig.savefig(out / f"MVM_fig1_distributions_{coh}.{ext}", dpi=200)
        plt.close(fig)
    # fig 2: mean - median vs short share (all licks + licks 1-5), per cohort x measure
    z = S[S.measure.isin(SIZE)]
    fig, ax = plt.subplots(2, 4, figsize=(10, 5), squeeze=False)
    for i, coh in enumerate(("c1", "c2")):
        for j, (meas, s) in enumerate([(m, s) for m in ("protrusion", "speed") for s in ("all", "first5")]):
            d = z[(z.cohort == coh) & (z.measure == meas) & (z.lickset == s)]
            a = ax[i, j]
            a.scatter(100 * d.short_share, 100 * (d["mean"] - d["median"]) / d["median"], s=4,
                      c=[cols[e] for e in d.epoch], alpha=0.6, linewidths=0)
            a.axhline(0, color="k", lw=0.5)
            a.set_title(f"{'C1' if coh == 'c1' else 'C2'} {mname[coh][meas]}, {'all licks' if s == 'all' else 'licks 1-5'}",
                        fontsize=7)
            a.set_xlabel("short-lick share (%)"); a.set_ylabel("(mean - median) / median (%)")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"MVM_fig2_meanminusmedian_vs_shortshare.{ext}", dpi=200)
    plt.close(fig)


def summary_grid(R: pd.DataFrame) -> pd.DataFrame:
    g = R[R.measure.isin(["protrusion", "speed", "angle"])].copy()
    g["cell"] = (g.snr_median.map("{:.2f}".format) + " / " + g.pre_sd_median.map("{:.1f}".format) + " / "
                 + g.splithalf_sb.map(lambda x: "nan" if pd.isna(x) else f"{x:.2f}"))
    return g.pivot_table(index=["cohort", "measure", "lickset"], columns="agg", values="cell", aggfunc="first")


def main(argv=None) -> int:
    mode, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "tables" / "MVM_per_lick_long.parquet"
    (out / "tables").mkdir(exist_ok=True)
    if mode == "build":
        if cache.exists():
            sys.exit(f"refusing to overwrite {cache}")
        L = pd.concat([build_c1(), build_c2()], ignore_index=True)
        L["session"] = L.session.astype(str); L["group"] = L.group.astype(str)
        L.to_parquet(cache, index=False)
        print(L.groupby(["cohort", "measure"]).value.describe().to_string())
        return 0
    L = pd.read_parquet(cache)
    L = L[L.epoch.isin(EPOCHS)]
    rng = np.random.default_rng(0)
    T = out / "tables"
    S, SH = session_table(L, rng)
    S.to_csv(T / "MVM_session_values.csv", index=False)
    SH.to_csv(T / "MVM_session_shape.csv", index=False)
    SH["grade"] = np.where(SH.cohort == "c1", SH.animal.map(GRADE).fillna(""), "all")
    shp = SH.groupby(["cohort", "measure", "lickset", "grade", "epoch"]).agg(
        n_sessions=("skew", "size"), skew_median=("skew", "median"), bc_median=("bc", "median"),
        share_bc_gt_0555=("bc", lambda x: (x > 0.555).mean()), share_dbic_gt10=("dbic_2v1", lambda x: (x > 10).mean()),
        w_low_median=("w_low", "median"), mu_low_rel_median=("mu_low_rel", "median")).reset_index()
    shp.to_csv(T / "MVM_shape_summary.csv", index=False)
    R = reliability(S); R.to_csv(T / "MVM_reliability.csv", index=False)
    P = paired_snr(S); P.to_csv(T / "MVM_paired_snr_vs_mean.csv", index=False)
    SS, C = short_share_summary(S)
    SS.to_csv(T / "MVM_short_share_summary.csv", index=False); C.to_csv(T / "MVM_meanminusmedian_vs_shortshare.csv", index=False)
    summary_grid(R).to_csv(T / "MVM_summary_grid.csv")
    # angle symmetry + times skew
    ang = S[S.measure == "angle"].copy()
    ang["d"] = ang["mean"] - ang["median"]
    A = ang.groupby(["cohort", "lickset"]).agg(n=("d", "size"), mean_minus_median_deg_median=("d", "median"),
                                              abs_p90=("d", lambda x: x.abs().quantile(.9)),
                                              r_mean_median=("d", lambda x: np.nan)).reset_index()
    for i, rr in A.iterrows():
        d = ang[(ang.cohort == rr.cohort) & (ang.lickset == rr.lickset)]
        A.loc[i, "r_mean_median"] = np.corrcoef(d["mean"], d["median"])[0, 1]
        A.loc[i, "between_session_sd_deg"] = d["mean"].std()
    A.to_csv(T / "MVM_angle_symmetry.csv", index=False)
    tm = []
    for (coh, meas), d in L[L.measure.isin(["latency", "ili"])].dropna(subset=["value"]).groupby(["cohort", "measure"]):
        d = d[d.value > 0]
        sk = d.groupby(U).value.agg(lambda x: stats.skew(x) if len(x) >= 20 else np.nan).dropna()
        mm = d.groupby(U).value.agg(lambda x: (x.mean() - x.median()) / x.median() if len(x) >= 20 else np.nan).dropna()
        tm.append({"cohort": coh, "measure": meas, "n_sessions": len(sk), "skew_median": sk.median(),
                   "share_skew_gt0": (sk > 0).mean(), "mean_over_median_minus1_median": mm.median()})
    pd.DataFrame(tm).to_csv(T / "MVM_times_skew.csv", index=False)
    figures(L, S, out)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    for name in ("MVM_reliability", "MVM_paired_snr_vs_mean", "MVM_meanminusmedian_vs_shortshare", "MVM_angle_symmetry",
                 "MVM_times_skew"):
        print("==", name); print(pd.read_csv(T / f"{name}.csv").round(3).to_string())
    print("== shape"); print(shp.round(3).to_string())
    print("== short share"); print(SS.round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
