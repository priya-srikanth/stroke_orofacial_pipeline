"""Six-position (PS92-95) WITHIN-TRIAL aim correction: angle contrasts across the licks of the SAME trials (CC-B,
2026-11-25; PROMPT_CC_B_withintrial_aim_2026-11-25 items 1, 3; suffix _ccB1125).

Input: the production fused four-camera lick list (as the bout-controlled lick-order table
ccB_caption_review_2026-11-23/bylicknum/c2_v2_bout10, made by widefield_pipeline scripts/sixpos_bylicknum_1123.py
--min-bout 10). The angle-per-session table is rebuilt here with the SAME code (angle only) so that a >= 15-lick
version can be made; the >= 10 rebuild is checked against the persisted bout10 table (must match exactly).

Angle = 3-D aim angle atan2(side_ml, hypot(out_ap, down_dv)) in degrees, + = contralesional; per session x position x
lick number the MEAN over licks (cell kept if >= 5 licks); chg = that minus the animal's own pre mean at the same
position AND lick number (August pre only). Trials: >= MIN_BOUT post-cue licks, lick numbers 1..MIN_BOUT.

Per-session x position contrasts of chg (each lick number weighted equally; the session x position needs every lick
number 1..MIN_BOUT):
  a  = licks 2-5 minus lick 1          (>= 10-lick trials)
  b  = licks 6-10 minus licks 3-5      (>= 10-lick trials)
  c  = licks 11-15 minus licks 1-5     (>= 15-lick trials; optional control, item 3)
Sensitivity (CC-A's exploratory definition): a_bins = mean(bin 2, bin 3-5) minus bin 1, b_bins = bin 6-10 minus
bin 3-5 (bins weighted equally; sessions need all four bins).
Groups: each of the six positions; "pooled" = per session the mean of the contrast over the positions present.

Statistics = the manuscript rule, the lick-order family's implementation (wfield_local.orofacial_stats
.session_change_tests, deltas_given=True: session MWU post vs pre of the contrast + 4,000-draw paired animal-weighted
nested animal -> session boot_delta, seed 0), BH via apply_family_fdr within the family; star = q < 0.05 AND the CI
excludes 0. Families: 'withintrial' = a, b x 7 groups x 3 epochs (42 cells, primary); 'withintrial_bins' (42,
sensitivity); 'withintrial15' = c x 7 x 3 (21); and 'merged_lickorder' = the 42 primary cells BH'd together with the
published six-position lick-order family (18 late-minus-early cells of c2_cells_bylicknum_v2_ccB1123) to show the
stars do not depend on the family split.

Env: locanmf + PYTHONPATH = a widefield_pipeline checkout (wfield_local; run used wf_ccb_bylicknum1123 @ 1a4fd73c).
    python c2_withintrial_aim.py --out DIR        (NEW files only; refuses to overwrite)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

P3D = Path("M:/MICROSCOPE/Priya/DeepLabCut/Widefield/session_poses/pose3d_4cam_3net_20261121_sync60")
LICKS = P3D / "kinematics_fused_postcue/licks.csv.gz"
BYL = Path("M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/vls_stroke_paper/ccB_caption_review_2026-11-23"
           "/bylicknum")
PERSISTED10 = BYL / "c2_v2_bout10/c2_session_position_bin_values_bout10_bylicknum_v2_ccB1123.csv"
LICKORDER_FAMILY = BYL / "c2_v2/c2_cells_bylicknum_v2_ccB1123.csv"
LR_POS = dict(zip(["close_L", "close_center", "close_R", "far_L", "far_center", "far_R"],
                  ["close_ipsi", "close_mid", "close_contra", "far_ipsi", "far_mid", "far_contra"]))
POS_ORDER = ["close_ipsi", "close_mid", "close_contra", "far_ipsi", "far_mid", "far_contra", "pooled"]
MS = {"PS92": "#9", "PS93": "#10", "PS94": "#11", "PS95": "#12"}
EPOCHS = ("acute", "subacute", "chronic")
BINS = [("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("11-15", 11, 15), ("16+", 16, 10**6)]
MIN_N = 5
SUFFIX = "_ccB1125"
G = ["animal", "session", "date", "epoch", "pos"]


def save(df, out, name):
    p = out / f"{name}{SUFFIX}.csv"
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    df.to_csv(p, index=False, lineterminator="\n")
    print("wrote", p, len(df), flush=True)


def binlab(n):
    for lab, lo, hi in BINS:
        if lo <= n <= hi:
            return lab
    return None


def load_licks():
    from wfield_local import config
    L = pd.read_csv(LICKS, usecols=["trial_id", "lick_idx", "position", "side_ml", "out_ap", "down_dv", "animal",
                                    "date", "session", "epoch"], dtype={"date": str})
    L = L[~((L.epoch == "pre") & L.date.map(config.early_pre))].reset_index(drop=True)
    L["pos"] = L.position.map(LR_POS)
    L["angle_deg"] = np.degrees(np.arctan2(L.side_ml, np.hypot(L.out_ap, L.down_dv)))   # + = right = contralesional
    L["n"] = L.lick_idx + 1
    L["bin"] = L.n.map(binlab)
    return L


def angle_table(L, min_bout):
    """sixpos_bylicknum_1123.main, angle rows only (bins + lick numbers), trials >= min_bout licks."""
    nb = L.groupby(["session", "trial_id"]).n.transform("max")
    L = L[(nb >= min_bout) & (L.n <= min_bout)].reset_index(drop=True)
    print(f"min bout {min_bout}: {len(L)} licks kept", flush=True)
    d = L.dropna(subset=["angle_deg"])
    s = d.groupby(G + ["bin"]).angle_deg.agg(["mean", "size"]).reset_index().assign(kind="bin")
    k = d[d.n <= 15].groupby(G + ["n"]).angle_deg.agg(["mean", "size"]).reset_index()
    k = k.assign(bin=k.n.astype(str), kind="licknum").drop(columns="n")
    S = pd.concat([s, k], ignore_index=True).rename(columns={"mean": "value", "size": "n_licks"})
    S = S[S.n_licks >= MIN_N].copy()
    base = S[S.epoch == "pre"].groupby(["kind", "bin", "animal", "pos"]).value.mean().rename("pre_mean")
    S = S.join(base, on=["kind", "bin", "animal", "pos"]).dropna(subset=["pre_mean"])
    S["chg"] = S.value - S.pre_mean
    return S.assign(measure="angle")


def check_persisted(S10):
    P = pd.read_csv(PERSISTED10, dtype={"date": str})
    P = P[P.measure == "angle"].copy()
    P["bin"] = P.bin.astype(str)
    S = S10.copy()
    S["date"] = S.date.astype(str)
    k = G + ["kind", "bin"]
    m = P.merge(S, on=k, how="outer", suffixes=("_p", "_n"), indicator=True)
    both = m[m._merge == "both"]
    dmax = float(np.nanmax(np.abs(both.chg_p - both.chg_n)))
    print(f"CHECK rebuild vs persisted bout10 angle rows: persisted {len(P)}, rebuilt {len(S)}, matched {len(both)}, "
          f"max |chg diff| {dmax:.3g}", flush=True)
    if len(both) != len(P) or len(both) != len(S) or dmax > 1e-9:
        sys.exit("rebuild does not reproduce the persisted bout10 table")


def contrasts(S, min_bout):
    K = S[S.kind == "licknum"].pivot_table(index=G, columns="bin", values="chg")
    K.columns = K.columns.astype(int)
    need = list(range(1, min_bout + 1))
    K = K[K.reindex(columns=need).notna().all(1)]
    out = pd.DataFrame(index=K.index)
    if min_bout == 10:
        out["a"] = K[[2, 3, 4, 5]].mean(1) - K[1]
        out["b"] = K[[6, 7, 8, 9, 10]].mean(1) - K[[3, 4, 5]].mean(1)
        B = S[S.kind == "bin"].pivot_table(index=G, columns="bin", values="chg")
        B = B[B.reindex(columns=["1", "2", "3-5", "6-10"]).notna().all(1)]
        bb = pd.DataFrame({"a_bins": (B["2"] + B["3-5"]) / 2 - B["1"], "b_bins": B["6-10"] - B["3-5"]})
        out = out.join(bb, how="outer")
    else:
        out["c"] = K[list(range(11, 16))].mean(1) - K[[1, 2, 3, 4, 5]].mean(1)
    out = out.reset_index()
    metrics = [c for c in out.columns if c not in G]
    pooled = out.groupby(["animal", "session", "date", "epoch"])[metrics].mean().reset_index().assign(pos="pooled")
    return pd.concat([out, pooled], ignore_index=True), metrics


def per_animal(C, metrics):
    rows = []
    for m in metrics:
        for (pos, a), x in C.groupby(["pos", "animal"]):
            pre = x.loc[x.epoch == "pre", m].dropna()
            for e in EPOCHS:
                post = x.loc[x.epoch == e, m].dropna()
                if len(post) and len(pre):
                    rows.append(dict(metric=m, pos=pos, epoch=e, animal=a, animal_ms=MS[a],
                                     post_mean=post.mean(), pre_mean=pre.mean(), change=post.mean() - pre.mean(),
                                     n_sessions=len(post), n_pre_sessions=len(pre)))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    from wfield_local import orofacial_stats as st
    L = load_licks()
    allR, allC = [], []
    for mb in (10, 15):
        S = angle_table(L, mb)
        if mb == 10:
            check_persisted(S)
        save(S.assign(animal_ms=S.animal.map(MS)), out, f"c2_angle_session_position_licknum_bout{mb}")
        C, metrics = contrasts(S, mb)
        save(C.assign(animal_ms=C.animal.map(MS)), out, f"c2_withintrial_session_contrasts_bout{mb}")
        PA = per_animal(C, metrics)
        save(PA, out, f"c2_withintrial_per_animal_bout{mb}")
        print(f"\n=== PER-ANIMAL (bout >= {mb}; change of the contrast vs own pre; far_contra and pooled) ===")
        print(PA[PA.pos.isin(["far_contra", "pooled"])].pivot_table(index=["metric", "pos", "epoch"],
              columns="animal_ms", values="change").round(2).to_string(), flush=True)
        R = st.session_change_tests(C, metrics, deltas_given=True, n_boot=4000)
        R["min_bout"] = mb
        allR.append(R)
        allC.append(C)
    R = pd.concat(allR, ignore_index=True)
    R["family"] = R.metric.map({"a": "withintrial", "b": "withintrial", "a_bins": "withintrial_bins",
                                "b_bins": "withintrial_bins", "c": "withintrial15"})
    R = st.apply_family_fdr(R, family_cols=["family"])
    R["star"] = (R.q_fdr < 0.05) & R.boot_sig
    # merged sensitivity: primary 42 + the published lick-order family (18 late-minus-early cells)
    LO = pd.read_csv(LICKORDER_FAMILY)
    LO = LO[LO.fam == "trend"].copy()
    assert len(LO) == 18, len(LO)
    M = pd.concat([R[R.family == "withintrial"].assign(src="withintrial"), LO.assign(src="lickorder_v2")],
                  ignore_index=True)[["src", "metric", "pos", "epoch", "p", "boot_lo", "boot_hi", "q_fdr", "star"]]
    M = M.rename(columns={"q_fdr": "q_own_family", "star": "star_own_family"})
    from wfield_local.orofacial_stats import bh_fdr
    M["q_merged"] = bh_fdr(M.p.to_numpy(float))
    M["star_merged"] = (M.q_merged < 0.05) & ((M.boot_lo > 0) | (M.boot_hi < 0))
    R = R.merge(M[M.src == "withintrial"][["metric", "pos", "epoch", "q_merged", "star_merged"]],
                on=["metric", "pos", "epoch"], how="left")
    R["pos"] = pd.Categorical(R.pos, POS_ORDER, ordered=True)
    R = R.sort_values(["family", "metric", "pos", "epoch"]).reset_index(drop=True)
    save(R, out, "c2_withintrial_cells")
    save(M, out, "c2_withintrial_merged_with_lickorder_family")
    ch = M[M.src == "lickorder_v2"]
    print(f"\nlick-order family stars changed by merging: {int((ch.star_own_family != ch.star_merged).sum())} of 18",
          flush=True)
    cols = ["metric", "pos", "epoch", "n_sessions", "n_animals", "boot_change", "boot_lo", "boot_hi", "p", "q_fdr",
            "star", "q_merged", "star_merged"]
    pd.set_option("display.width", 250)
    for fam, d in R.groupby("family"):
        print(f"\n=== family {fam} ({len(d)} cells) ===")
        print(d[cols].round(4).to_string(), flush=True)


if __name__ == "__main__":
    main()
