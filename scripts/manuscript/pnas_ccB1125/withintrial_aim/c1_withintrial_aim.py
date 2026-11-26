"""Two-tone (PS46-55) WITHIN-TRIAL aim correction: tongue-angle contrasts across the licks of the SAME trials (CC-B,
2026-11-25; PROMPT_CC_B_withintrial_aim_2026-11-25 items 2, 3; suffix _ccB1125).

Input = the inputs of the bout-controlled lick-order table ccB_caption_review_2026-11-23/bylicknum/c1_v3_bout10 (made by
scripts/manuscript/c1_bylicknum.py <out> 10, branch ccB-bylicknum-20261123 @ d07bac7): the Fig 2G all-lick peak tongue
angle per lick with its lick number (c1_v3/c1_angle_per_lick_source_bylicknum_v3_ccB1123.parquet; sign flipped so
+ = contralesional) and the filtered_v1 session epoch labels. The angle rows of that table are rebuilt here with the
same code so a >= 15-lick version can be made; the >= 10 rebuild is checked against the persisted table (exact).

Per session x cue side x lick number: MEAN angle (>= 5 licks); value_norm = minus the animal's own pre mean at the same
side and lick number (normalize_to_pre_baseline). Trials: >= MIN_BOUT licks, lick numbers 1..MIN_BOUT.
Contrasts per session x side (each lick number weighted equally; every lick number 1..MIN_BOUT present):
  a = licks 2-5 minus lick 1; b = licks 6-10 minus licks 3-5 (>= 10-lick trials); c = licks 11-15 minus 1-5 (>= 15).
Sensitivity a_bins / b_bins = CC-A's bin-weighted definition (bins 1, 2, 3-5, 6-10).

Statistics = c1_bylicknum.py's lick-order implementation unchanged: per grade x side x post epoch, session MWU (post vs
pre) + 4,000-draw paired animal-weighted nested bootstrap (nested_animal_bootstrap_ci, seed 0); single-animal cells
(moderate acute, #5) in the family with the manuscript dagger rule (c1_dagger_single_animal.cell_result); BH
(apply_correction_to_results_df) within the family. star = q < 0.05 AND CI excludes 0 (not single-animal);
dagger = single animal, q < 0.05 AND within-animal CI excludes 0. Families: withintrial (a, b: 32 cells),
withintrial_bins (32), withintrial15 (c: 16), plus the primary 32 BH'd with the published two-tone lick-order family
(48 late-minus-early cells of c1_cells_bylicknum_v3_ccB1123) as a sensitivity.

Env: stroke_orofacial, MKL_THREADING_LAYER=SEQUENTIAL, PYTHONPATH="<worktree>/src;<worktree>".
    python scripts/manuscript/pnas_ccB1125/withintrial_aim/c1_withintrial_aim.py <out_dir>   (NEW files only)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from scripts.manuscript.c1_dagger_single_animal import DAGGER, MS_NUM, cell_result  # noqa: E402
from scripts.manuscript.c1_sessmean_scalars import REMAP3, kept_trials  # noqa: E402

from stroke_orofacial.animals import load_animals  # noqa: E402
from stroke_orofacial.paths import PathResolver  # noqa: E402
from stroke_orofacial.stats import pooled_endpoint_suite as SUITE  # noqa: E402
from stroke_orofacial.stats.multiple_comparisons import apply_correction_to_results_df  # noqa: E402

r = PathResolver()
BYL = r.pipeline_outputs(subdir="vls_stroke_paper") / "ccB_caption_review_2026-11-23/bylicknum"
ANG_SRC = BYL / "c1_v3/c1_angle_per_lick_source_bylicknum_v3_ccB1123.parquet"
PERSISTED10 = BYL / "c1_v3_bout10/c1_session_bin_values_bout10_bylicknum_v3_ccB1123.csv"
LICKORDER_FAMILY = BYL / "c1_v3/c1_cells_bylicknum_v3_ccB1123.csv"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SUFFIX = "_ccB1125"
KEY = ["animal", "date", "trial_idx", "side"]
G = ["animal", "date", "side", "epoch_label", "grade"]
MIN_N = 5
BINS = [("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("11-15", 11, 15), ("16+", 16, 10**6)]
EPOCHS = ("acute", "sub_acute", "chronic")
SIDE_NAME = {"L": "ipsilesional", "R": "contralesional"}
FAM = {"a": "withintrial", "b": "withintrial", "a_bins": "withintrial_bins", "b_bins": "withintrial_bins",
       "c": "withintrial15"}


def save(df, name):
    p = OUT / f"{name}{SUFFIX}.csv"
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    df.to_csv(p, index=False, encoding="utf-8")
    print("wrote", p, len(df), flush=True)


def angle_licks():
    """c1_bylicknum.angle_licks (without its earlier-join print check): one row per lick, + = contralesional."""
    A = pd.read_parquet(ANG_SRC).rename(columns={"trial_index": "trial_idx"})
    A["date"] = pd.to_datetime(A["date"]).dt.date
    A = A[np.isfinite(A.peak_angle_deg.astype(float))].copy()
    A["value"] = -A.peak_angle_deg.astype(float)
    t = kept_trials(r, "tongue_median_vxy_peak_per_trial")
    t["date"] = pd.to_datetime(t["date"]).dt.date
    lab = t[KEY + ["epoch_label"]].drop_duplicates().drop_duplicates(["animal", "date"]).set_index(
        ["animal", "date"]).epoch_label
    A["epoch_label"] = [lab.get((x, d), np.nan) for x, d in zip(A.animal, A.date)]
    A["side"] = A.side.map(SIDE_NAME)
    return A[["animal", "date", "trial_idx", "side", "k", "value", "epoch_label"]]


def angle_table(A, min_bout, amap):
    nb = A.groupby(["animal", "date", "trial_idx", "side"]).k.transform("max") + 1
    L = A[(nb >= min_bout) & (A.k < min_bout)].assign(n=lambda d: d.k + 1)
    print(f"min bout {min_bout}: {len(L)} angle licks kept", flush=True)
    g = ["animal", "date", "side", "epoch_label"]
    sess = []
    for lab, lo, hi in BINS:
        s = L[(L.n >= lo) & (L.n <= hi)].groupby(g).value.agg(["mean", "size"]).reset_index()
        sess.append(s.rename(columns={"mean": "value"}).assign(bin=lab, kind="bin"))
    s = L[L.n <= 15].groupby(g + ["n"]).value.agg(["mean", "size"]).reset_index().rename(columns={"mean": "value"})
    sess.append(s.assign(bin=s.n.astype(str), kind="licknum").drop(columns="n"))
    S = pd.concat(sess, ignore_index=True).rename(columns={"size": "n_licks"})
    S = S[S.n_licks >= MIN_N].copy()
    S["grade"] = S.animal.map(amap)
    S["measure"] = "angle"
    parts = [SUITE.normalize_to_pre_baseline(d, group_cols=("animal", "side"), value_col="value")
             for _, d in S.groupby(["kind", "bin"])]
    return pd.concat(parts, ignore_index=True).dropna(subset=["value_norm"])


def check_persisted(S10):
    P = pd.read_csv(PERSISTED10)
    P = P[P.measure == "angle"].copy()
    P["date"] = pd.to_datetime(P.date).dt.date
    P["bin"] = P.bin.astype(str)
    k = ["animal", "date", "side", "epoch_label", "kind", "bin"]
    m = P.merge(S10, on=k, how="outer", suffixes=("_p", "_n"), indicator=True)
    both = m[m._merge == "both"]
    dmax = float(np.nanmax(np.abs(both.value_norm_p - both.value_norm_n)))
    print(f"CHECK rebuild vs persisted bout10 angle rows: persisted {len(P)}, rebuilt {len(S10)}, matched {len(both)},"
          f" max |value_norm diff| {dmax:.3g}", flush=True)
    if len(both) != len(P) or len(both) != len(S10) or dmax > 1e-9:
        sys.exit("rebuild does not reproduce the persisted bout10 table")


def contrasts(S, min_bout):
    K = S[S.kind == "licknum"].pivot_table(index=G, columns="bin", values="value_norm")
    K.columns = K.columns.astype(int)
    K = K[K.reindex(columns=list(range(1, min_bout + 1))).notna().all(1)]
    out = pd.DataFrame(index=K.index)
    if min_bout == 10:
        out["a"] = K[[2, 3, 4, 5]].mean(1) - K[1]
        out["b"] = K[[6, 7, 8, 9, 10]].mean(1) - K[[3, 4, 5]].mean(1)
        B = S[S.kind == "bin"].pivot_table(index=G, columns="bin", values="value_norm")
        B = B[B.reindex(columns=["1", "2", "3-5", "6-10"]).notna().all(1)]
        out = out.join(pd.DataFrame({"a_bins": (B["2"] + B["3-5"]) / 2 - B["1"], "b_bins": B["6-10"] - B["3-5"]}),
                       how="outer")
    else:
        out["c"] = K[list(range(11, 16))].mean(1) - K[[1, 2, 3, 4, 5]].mean(1)
    return out.reset_index()


def cells(C, metrics):
    long = C.melt(id_vars=G, value_vars=metrics, var_name="metric", value_name="value_norm").dropna(
        subset=["value_norm"])
    rows, peran = [], []
    for (m, side, grade), d in long.groupby(["metric", "side", "grade"]):
        for post in EPOCHS:
            if post not in set(d.epoch_label):
                continue
            sub = d[d.epoch_label.isin(("pre", post))]
            pre_v = sub.loc[sub.epoch_label == "pre", "value_norm"].to_numpy()
            post_v = sub.loc[sub.epoch_label == post, "value_norm"].to_numpy()
            _, p = SUITE._session_mwu(pre_v, post_v)
            nb = SUITE.nested_animal_bootstrap_ci(sub, post_epoch=post, value_col="value_norm")
            animals = sorted(set(sub.loc[sub.epoch_label == post, "animal"])
                             & set(sub.loc[sub.epoch_label == "pre", "animal"]))
            res = dict(metric=m, side=side, grade=grade, epoch=post, p=p, n_sessions=len(post_v),
                       n_pre_sessions=len(pre_v), n_animals=len(animals),
                       animals_ms=" ".join(MS_NUM[a] for a in animals), **nb)
            if len(animals) == 1:
                wa = cell_result(sub, post, p, f"{m}/{side}/{grade}/{post}")
                res.update(wa1_effect=wa["wa1_effect"], wa1_ci_lo=wa["wa1_ci_lo"], wa1_ci_hi=wa["wa1_ci_hi"],
                           wa1_excludes_zero=wa["wa1_excludes_zero"])
            rows.append(res)
            for a in animals:
                x = sub[sub.animal == a]
                peran.append(dict(metric=m, side=side, grade=grade, epoch=post, animal=a, animal_ms=MS_NUM[a],
                                  change=x.loc[x.epoch_label == post, "value_norm"].mean()
                                  - x.loc[x.epoch_label == "pre", "value_norm"].mean(),
                                  n_sessions=int((x.epoch_label == post).sum())))
    return pd.DataFrame(rows), pd.DataFrame(peran)


def bh(d, fam_col):
    d = d.rename(columns={"p": "p_value"})
    ok = d.p_value.notna()
    dd = apply_correction_to_results_df(d[ok].copy(), group_cols=(fam_col,))
    d.loc[ok, "q"] = dd["p_adj"].to_numpy()
    return d.rename(columns={"p_value": "p"})


def marks(R):
    R["single_animal"] = R.n_animals == 1
    R["star"] = (R.q < 0.05) & R.nb_excludes_zero.astype(bool) & ~R.single_animal
    wa = R["wa1_excludes_zero"] if "wa1_excludes_zero" in R else pd.Series(False, index=R.index)
    R["dagger"] = R.single_animal & (R.q < 0.05) & wa.astype("boolean").fillna(False).astype(bool)
    R["mark"] = np.where(R.star, "*", np.where(R.dagger, DAGGER, ""))
    return R


def main():
    amap = {a: REMAP3.get(i.recovery_phenotype, i.recovery_phenotype) for a, i in load_animals().items()}
    A = angle_licks()
    Rs, PAs = [], []
    for mb in (10, 15):
        S = angle_table(A, mb, amap)
        if mb == 10:
            check_persisted(S)
        save(S.assign(animal_ms=S.animal.map(MS_NUM)), f"c1_angle_session_side_licknum_bout{mb}")
        C = contrasts(S, mb)
        save(C.assign(animal_ms=C.animal.map(MS_NUM)), f"c1_withintrial_session_contrasts_bout{mb}")
        metrics = [c for c in C.columns if c not in G]
        R, PA = cells(C, metrics)
        PA["epoch"] = PA.epoch.replace({"sub_acute": "subacute"})
        save(PA, f"c1_withintrial_per_animal_bout{mb}")
        print(f"\n=== PER-ANIMAL (bout >= {mb}; change of the contrast vs own pre) ===")
        print(PA.pivot_table(index=["metric", "side", "grade", "epoch"], columns="animal_ms", values="change")
              .round(2).to_string(), flush=True)
        Rs.append(R.assign(min_bout=mb))
    R = pd.concat(Rs, ignore_index=True)
    R["family"] = R.metric.map(FAM)
    R = marks(bh(R, "family"))
    R["epoch"] = R.epoch.replace({"sub_acute": "subacute"})
    # merged sensitivity: primary 32 cells + the published two-tone lick-order family (48 late-minus-early cells)
    LO = pd.read_csv(LICKORDER_FAMILY)
    LO = LO[LO.fam == "trend"].copy()
    assert len(LO) == 48, len(LO)
    prim = R[R.family == "withintrial"].copy()
    M = pd.concat([prim.assign(src="withintrial"), LO.assign(src="lickorder_v3", metric=LO.measure)],
                  ignore_index=True)
    M = M.rename(columns={"q": "q_own_family", "star": "star_own_family", "dagger": "dagger_own_family"})
    M["merged"] = "all"
    M = M.rename(columns={"p": "p_value"})
    ok = M.p_value.notna()
    dd = apply_correction_to_results_df(M[ok].copy(), group_cols=("merged",))
    M.loc[ok, "q"] = dd["p_adj"].to_numpy()
    M = marks(M.rename(columns={"p_value": "p"}))
    M = M.rename(columns={"q": "q_merged", "star": "star_merged", "dagger": "dagger_merged"})
    M = M[["src", "metric", "side", "grade", "epoch", "p", "nb_effect", "nb_ci_lo", "nb_ci_hi", "q_own_family",
           "star_own_family", "dagger_own_family", "q_merged", "star_merged", "dagger_merged"]]
    save(M, "c1_withintrial_merged_with_lickorder_family")
    lo = M[M.src == "lickorder_v3"]
    print(f"\nlick-order family marks changed by merging: stars {int((lo.star_own_family != lo.star_merged).sum())},"
          f" daggers {int((lo.dagger_own_family != lo.dagger_merged).sum())} of 48", flush=True)
    R = R.merge(M[M.src == "withintrial"][["metric", "side", "grade", "epoch", "q_merged", "star_merged",
                                           "dagger_merged"]], on=["metric", "side", "grade", "epoch"], how="left")
    save(R, "c1_withintrial_cells")
    cols = ["metric", "side", "grade", "epoch", "n_sessions", "animals_ms", "nb_effect", "nb_ci_lo", "nb_ci_hi",
            "wa1_effect", "wa1_ci_lo", "wa1_ci_hi", "p", "q", "mark", "q_merged", "star_merged"]
    pd.set_option("display.width", 260)
    for fam, d in R.groupby("family"):
        print(f"\n=== family {fam} ({len(d)} cells) ===")
        print(d[[c for c in cols if c in d]].round(4).to_string(), flush=True)


if __name__ == "__main__":
    main()
