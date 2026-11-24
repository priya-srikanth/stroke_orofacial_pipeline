"""Two-tone (cohort 1, mice #1-#8) kinematics BY LICK NUMBER within the trial (CC-B, 2026-11-23; suffix _bylicknum_ccB1123).

Question (Priya 11-23): is the post-stroke deficit present from the first licks of a trial, with a later deficit that
builds over the bout?

Licks and measures exactly as the two-tone grid (c1_twotone_grid.py): v7-kept post-cue licks, peak 70-3000 ms after
the cue, filtered_v1 trials; speed = peak 2-D tip speed lick onset -> full extension (speed_onsetpeak per-lick table,
trials of tongue_median_vxy_peak_per_trial); xy = peak protrusion hypot(x, y) at each lick peak (lick_events, trials of
tongue_median_xy_peak_per_trial). Lick number = order of the lick within the trial (by peak time), 1-based.

Per session x cue side x lick-number bin: the MEDIAN of the per-lick values (cell kept if >= 5 licks). Bins 1, 2, 3-5,
6-10, 11-15, 16+ and individual lick numbers 1-15. Change = session value minus the animal's own pre-stroke mean in the
SAME bin and cue side (normalize_to_pre_baseline). Trend contrast per session = mean(change 6-10, change 11-15) minus
mean(change 1, 2, 3-5) (session needs all five bins); slope = OLS slope of change over lick numbers 1-15 (per 10 licks,
session needs >= 8 lick numbers).

Stats per grade (mild / moderate / severe; moderate-severe -> moderate) x cue side x post epoch: session MWU (post vs
pre sessions of the change) + the 4,000-draw paired nested animal -> session bootstrap (nested_animal_bootstrap_ci,
seed 0). Single-animal cells (moderate acute = #5 only) get the within-animal bootstrap and are never starred.
Family = the late-minus-early contrast cells of both measures (BH once); per-bin cells get their own BH family
(descriptive). Star = q < 0.05 AND the bootstrap CI excludes 0.

Writes NEW files only under <out> (refuses to overwrite).  Usage: python scripts/manuscript/c1_bylicknum.py <out_dir>"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from scripts.manuscript.c1_dagger_single_animal import DAGGER, MS_NUM, cell_result
from scripts.manuscript.c1_sessmean_scalars import REMAP3, kept_trials

from stroke_orofacial.animals import load_animals
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df

r = PathResolver()
SM = r.pipeline_outputs(subdir="stats") / "inputs/sessmean_licks"
OUT = Path(sys.argv[1])
#: optional sensitivity: keep only trials with >= MIN_BOUT licks, lick numbers 1..MIN_BOUT (late bin = 6-10 only)
MIN_BOUT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
OUT.mkdir(parents=True, exist_ok=True)
SUFFIX = (f"_bout{MIN_BOUT}" if MIN_BOUT else "") + "_bylicknum_v3_ccB1123"
#: per-bin session summary: median for speed / xy; MEAN for the angle (angles are means everywhere, Priya 11-23)
AGG = {"speed": "median", "xy": "median", "angle": "mean"}
KEY = ["animal", "date", "trial_idx", "side"]
MIN_N = 5
BINS = [("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("11-15", 11, 15), ("16+", 16, 10**6)]
EARLY, LATE = ["1", "2", "3-5"], (["6-10"] if MIN_BOUT else ["6-10", "11-15"])
EPOCHS = ("acute", "sub_acute", "chronic")
SIDE_NAME = {"L": "ipsilesional", "R": "contralesional"}   # all-left-lesion cohort


def save(df, name):
    p = OUT / f"{name}{SUFFIX}.csv"
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    df.to_csv(p, index=False, encoding="utf-8")
    print("wrote", p, len(df), flush=True)


def trials(slug):
    t = kept_trials(r, slug)
    t["date"] = pd.to_datetime(t["date"]).dt.date
    return t[KEY + ["epoch_label"]].drop_duplicates()


V = pd.concat([pd.read_parquet(p) for p in sorted((SM / "speed_onsetpeak_per_lick").glob("speed_onsetpeak_PS*.parquet"))])
V["date"] = pd.to_datetime(V["date"]).dt.date
V = V[np.isfinite(V.vxy_peak)].rename(columns={"vxy_peak": "value", "lick_k": "k"})
SPD = V.merge(trials("tongue_median_vxy_peak_per_trial"), on=KEY)


#: two-tone angle per lick WITH its lick number, rebuilt from the Fig 2G producer (c1_angle_licks_source.py): Fig 2G's
#: own session set (filtered_v1 DLC session filter), no trial filter, lick number from the source's per-trial lick list
ANG_SRC = (r.pipeline_outputs(subdir="vls_stroke_paper") / "ccB_caption_review_2026-11-23/bylicknum/c1_v3"
           / "c1_angle_per_lick_source_bylicknum_v3_ccB1123.parquet")


def angle_licks():
    """All-lick peak tongue angle (Fig 2G), one row per lick: trial_idx, side, k (0-based order of the lick peaks in the
    trial), value (sign flipped so + = contralesional, vls_style.ANGLE_SIGN_C1). Epoch labels = the filtered_v1 session
    labels used by every other two-tone row (same sessions; the producer's assign_epoch_label is compared and printed).
    Also checks the lick numbers against the earlier row-by-row join to the speed per-lick table."""
    A = pd.read_parquet(ANG_SRC).rename(columns={"trial_index": "trial_idx"})
    A["date"] = pd.to_datetime(A["date"]).dt.date
    A = A[np.isfinite(A.peak_angle_deg.astype(float))].copy()
    A["value"] = -A.peak_angle_deg.astype(float)
    lab = trials("tongue_median_vxy_peak_per_trial").drop_duplicates(["animal", "date"]).set_index(
        ["animal", "date"]).epoch_label
    src_lab = A.epoch_label
    A["epoch_label"] = [lab.get((x, d), np.nan) for x, d in zip(A.animal, A.date)]
    dif = A.loc[A.epoch_label.astype(str) != src_lab.astype(str), ["animal", "date"]].drop_duplicates()
    print("angle: sessions whose producer epoch label differs from the filtered_v1 label:", len(dif),
          dif.to_dict("records")[:20], flush=True)
    # cross-check: the lick numbers of the earlier join (speed per-lick table, same row order as the 2G table)
    J = pd.concat([pd.read_parquet(p) for p in sorted((SM / "speed_onsetpeak_per_lick").glob("speed_onsetpeak_PS*.parquet"))])
    J["date"] = pd.to_datetime(J["date"]).dt.date
    m = A.merge(J[["animal", "date", "trial_idx", "side", "t_ms", "lick_k"]].rename(columns={"t_ms": "peak_t_ms"}),
                on=["animal", "date", "trial_idx", "side", "peak_t_ms"], how="left")
    print(f"angle: lick number vs the earlier join: matched {int(m.lick_k.notna().sum())} / {len(m)}, "
          f"identical {int((m.lick_k == m.k).sum())}", flush=True)
    return A[["animal", "date", "trial_idx", "side", "k", "peak_t_ms", "value", "epoch_label"]]


ANG = angle_licks()
print("angle licks (Fig 2G session set, finite):", len(ANG), flush=True)


def xy_licks(T):
    rows = []
    for (animal, date), tr in T.groupby(["animal", "date"]):
        le = pd.read_parquet(r.pipeline_outputs(subdir="dlc_kinematics") / "lick_events" / "tongue" / animal
                             / f"{date.strftime('%Y%m%d')}.parquet", columns=["trial", "side", "t_ms", "x", "y"])
        le = le.rename(columns={"trial": "trial_idx"}).assign(animal=animal, date=date)
        le["value"] = np.hypot(le.x.astype(float), le.y.astype(float))
        le = le[np.isfinite(le.value)].sort_values(["trial_idx", "side", "t_ms"])
        le["k"] = le.groupby(["trial_idx", "side"]).cumcount()
        rows.append(le.merge(tr, on=KEY))
    return pd.concat(rows, ignore_index=True)


XY = xy_licks(trials("tongue_median_xy_peak_per_trial"))
for _T in (SPD, XY, ANG):
    _T["side"] = _T.side.map(SIDE_NAME)
LICKS = {"speed": SPD, "xy": XY, "angle": ANG}
if MIN_BOUT:   # same trials supply every lick number 1..MIN_BOUT (removes the bout-length selection)
    for _m, _L in list(LICKS.items()):
        _nb = _L.groupby(["animal", "date", "trial_idx", "side"]).k.transform("max") + 1
        LICKS[_m] = _L[(_nb >= MIN_BOUT) & (_L.k < MIN_BOUT)].reset_index(drop=True)
        print(_m, "min bout", MIN_BOUT, len(LICKS[_m]), "licks kept", flush=True)
amap = {a: REMAP3.get(i.recovery_phenotype, i.recovery_phenotype) for a, i in load_animals().items()}
print("epoch labels", sorted(SPD.epoch_label.unique()), "sides", sorted(SPD.side.unique()), flush=True)


def binlab(n):
    for lab, lo, hi in BINS:
        if lo <= n <= hi:
            return lab
    return None


# ---- lick counts per bin x epoch, and bout length (licks per trial) per session
cnt, bout = [], []
for meas, L in LICKS.items():
    L = L.assign(n=L.k + 1)
    L["bin"] = L.n.map(binlab)
    c = L.groupby(["epoch_label", "bin"]).size().rename("n_licks").reset_index().assign(measure=meas)
    cnt.append(c)
    if meas == "xy":   # bout length = number of post-cue licks in the trial (xy lick list)
        t = L.groupby(["animal", "date", "side", "trial_idx", "epoch_label"]).n.max().rename("bout").reset_index()
        b = t.groupby(["animal", "date", "side", "epoch_label"]).agg(
            bout_median=("bout", "median"), bout_mean=("bout", "mean"), frac_ge6=("bout", lambda x: (x >= 6).mean()),
            frac_ge11=("bout", lambda x: (x >= 11).mean()), n_trials=("bout", "size")).reset_index()
        bout.append(b)
C = pd.concat(cnt, ignore_index=True)
C = C.pivot_table(index=["measure", "epoch_label"], columns="bin", values="n_licks").reset_index()
save(C, "c1_lick_counts_per_bin")
B = pd.concat(bout)
B["grade"] = B.animal.map(amap)
B["animal_ms"] = B.animal.map(MS_NUM)
save(B, "c1_bout_length_per_session")

# ---- per session x side x bin medians (bins + individual lick numbers 1-15)
sess = []
for meas, L in LICKS.items():
    L = L.assign(n=L.k + 1)
    g = ["animal", "date", "side", "epoch_label"]
    for lab, lo, hi in BINS:
        s = L[(L.n >= lo) & (L.n <= hi)].groupby(g).value.agg([AGG[meas], "size"]).reset_index()
        s = s.rename(columns={AGG[meas]: "value"})
        sess.append(s.assign(measure=meas, bin=lab, kind="bin"))
    s = L[L.n <= 15].groupby(g + ["n"]).value.agg([AGG[meas], "size"]).reset_index()
    s = s.rename(columns={AGG[meas]: "value"})
    sess.append(s.assign(measure=meas, bin=s.n.astype(str), kind="licknum").drop(columns="n"))
S = pd.concat(sess, ignore_index=True).rename(columns={"size": "n_licks"})
S = S[S.n_licks >= MIN_N].copy()
S["grade"] = S.animal.map(amap)
# change from own pre in the same bin x side
parts = []
for (meas, kind, b), d in S.groupby(["measure", "kind", "bin"]):
    parts.append(SUITE.normalize_to_pre_baseline(d, group_cols=("animal", "side"), value_col="value"))
S = pd.concat(parts, ignore_index=True)
S = S.dropna(subset=["value_norm"])
save(S.assign(animal_ms=S.animal.map(MS_NUM)), "c1_session_bin_values")

# ---- per-session contrast (late - early) and slope
g = ["measure", "animal", "date", "side", "epoch_label", "grade"]
W = S[S.kind == "bin"].pivot_table(index=g, columns="bin", values="value_norm").reset_index()
W["late_minus_early"] = np.where(W[EARLY + LATE].notna().all(1), W[LATE].mean(1) - W[EARLY].mean(1), np.nan)
K = S[S.kind == "licknum"].assign(n=lambda d: d.bin.astype(int))


def _slope(d):
    return np.polyfit(d.n, d.value_norm, 1)[0] * 10 if len(d) >= 8 else np.nan


sl = K.groupby(g).apply(_slope).rename("slope_per10").reset_index()
W = W.merge(sl, on=g, how="left")
save(W.assign(animal_ms=W.animal.map(MS_NUM)), "c1_session_contrast")

# ---- cells
long = pd.concat([
    S[["measure", "kind", "bin", "animal", "date", "side", "epoch_label", "grade", "value_norm"]],
    W.melt(id_vars=g, value_vars=["late_minus_early", "slope_per10"], var_name="bin", value_name="value_norm")
     .assign(kind="trend")], ignore_index=True).dropna(subset=["value_norm"])
rows, peran = [], []
for (meas, kind, b, side, grade), d in long.groupby(["measure", "kind", "bin", "side", "grade"]):
    for post in EPOCHS:
        if post not in set(d.epoch_label):
            continue
        sub = d[d.epoch_label.isin(("pre", post))]
        pre_v = sub.loc[sub.epoch_label == "pre", "value_norm"].to_numpy()
        post_v = sub.loc[sub.epoch_label == post, "value_norm"].to_numpy()
        _, p = SUITE._session_mwu(pre_v, post_v)
        nb = SUITE.nested_animal_bootstrap_ci(sub, post_epoch=post, value_col="value_norm")
        animals = sorted(set(sub.loc[sub.epoch_label == post, "animal"]) & set(sub.loc[sub.epoch_label == "pre", "animal"]))
        res = dict(measure=meas, kind=kind, bin=b, side=side, grade=grade, epoch=post, p=p,
                   n_sessions=len(post_v), n_pre_sessions=len(pre_v), n_animals=len(animals),
                   animals_ms=" ".join(MS_NUM[a] for a in animals), **nb)
        if len(animals) == 1:
            # the manuscript single-animal rule (SECTION_dagger_single_animal.md): c1_dagger_single_animal.cell_result,
            # unchanged (re-checks the MWU p, 4,000-draw within-animal session bootstrap, seed 0)
            wa = cell_result(sub, post, p, f"{meas}/{kind}/{b}/{side}/{grade}/{post}")
            res.update(wa1_effect=wa["wa1_effect"], wa1_ci_lo=wa["wa1_ci_lo"], wa1_ci_hi=wa["wa1_ci_hi"],
                       wa1_excludes_zero=wa["wa1_excludes_zero"])
        rows.append(res)
        for a in animals:
            x = sub[sub.animal == a]
            peran.append({"measure": meas, "kind": kind, "bin": b, "side": side, "grade": grade, "epoch": post, "animal": a,
                              "animal_ms": MS_NUM[a], "change": x.loc[x.epoch_label == post, "value_norm"].mean()
                              - x.loc[x.epoch_label == "pre", "value_norm"].mean(),
                              "n_sessions": int((x.epoch_label == post).sum())})
R = pd.DataFrame(rows)
R["single_animal"] = R.n_animals == 1
R["fam"] = np.where(R.kind == "trend", np.where(R.bin == "late_minus_early", "trend", "slope"), R.kind)
out = []
for fam, d in R.groupby("fam"):
    d = d.rename(columns={"p": "p_value"}).assign(family=fam)
    ok = d.p_value.notna()   # single-animal cells ARE in the family (manuscript rule: their q is the family q)
    dd = apply_correction_to_results_df(d[ok].copy(), group_cols=("family",))
    d.loc[ok, "q"] = dd["p_adj"].to_numpy()
    out.append(d.rename(columns={"p_value": "p"}))
R = pd.concat(out, ignore_index=True)
R["epoch"] = R.epoch.replace({"sub_acute": "subacute"})
R["star"] = (R.q < 0.05) & R.nb_excludes_zero.astype(bool) & ~R.single_animal
R["dagger"] = R.single_animal & (R.q < 0.05) & R.get("wa1_excludes_zero", False).fillna(False).astype(bool)
R["mark"] = np.where(R.star, "*", np.where(R.dagger, DAGGER, ""))
save(R, "c1_cells")
save(pd.DataFrame(peran).replace({"epoch": {"sub_acute": "subacute"}}), "c1_per_animal")
t = R[R.fam == "trend"]
print(t[["measure", "side", "grade", "epoch", "nb_effect", "nb_ci_lo", "nb_ci_hi", "q", "star", "n_sessions",
         "animals_ms", "wa1_effect"]].to_string(), flush=True)
print(R[(R.kind == "bin")].pivot_table(index=["measure", "side", "grade", "epoch"], columns="bin",
                                       values="nb_effect").round(1).to_string(), flush=True)
