"""Stage the plot-ready tables of the within-trial aim SI panel (CC-B 2026-11-25; PROMPT_CC_B_withintrial_aim item 4).

Lines: per lick number 1-10, the paired animal-weighted nested bootstrap change from own pre (4,000 draws, seed 0;
wfield_local.orofacial_stats.session_change_tests, deltas_given) of the six-position 3-D angle, trials with >= 10 licks,
on EXACTLY the session x position cells the contrast test used (every lick number 1-10 present); "pooled" = per
session the mean over those positions. Because the point estimate is linear, mean(line 2-5) - line 1 equals the
contrast-(a) point estimate (checked below). Marks: contrast (a) cells (licks 2-5 minus lick 1) of
c2_withintrial_cells_ccB1125.csv, family 'withintrial' (BH over 42 cells).

    python stage_withintrial_panel.py <c2_dir> <kit_dir>     (locanmf + wfield_local; NEW files only)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

C2, KIT = Path(sys.argv[1]), Path(sys.argv[2])
KIT.mkdir(parents=True, exist_ok=True)
G = ["animal", "session", "date", "epoch", "pos"]


def save(df, name):
    p = KIT / name
    if p.exists():
        sys.exit(f"refusing to overwrite {p}")
    df.to_csv(p, index=False, lineterminator="\n")
    print("wrote", p, len(df))


def main():
    from wfield_local import orofacial_stats as st
    S = pd.read_csv(C2 / "c2_angle_session_position_licknum_bout10_ccB1125.csv", dtype={"date": str})
    K = S[S.kind == "licknum"].pivot_table(index=G, columns="bin", values="chg")
    K.columns = [f"L{int(c)}" for c in K.columns]
    cols = [f"L{i}" for i in range(1, 11)]
    K = K[cols].dropna().reset_index()
    pooled = K.groupby(["animal", "session", "date", "epoch"])[cols].mean().reset_index().assign(pos="pooled")
    P = pd.concat([K[K.pos == "far_contra"], pooled], ignore_index=True)
    R = st.session_change_tests(P, cols, deltas_given=True, n_boot=4000)
    R["lick"] = R.metric.str[1:].astype(int)
    lines = R[["pos", "epoch", "lick", "boot_change", "boot_lo", "boot_hi", "n_sessions", "n_animals"]].rename(
        columns={"boot_change": "est", "boot_lo": "lo", "boot_hi": "hi"})
    # n_animals = animals with post sessions in that cell
    na = P.groupby(["pos", "epoch"]).animal.nunique().rename("n_animals_post")
    lines = lines.join(na, on=["pos", "epoch"]).sort_values(["pos", "epoch", "lick"])
    cells = pd.read_csv(C2 / "c2_withintrial_cells_ccB1125.csv")
    m = cells[(cells.metric == "a") & cells.pos.isin(["pooled", "far_contra"])]
    marks = m[["pos", "epoch", "metric", "boot_change", "boot_lo", "boot_hi", "p", "q_fdr", "star", "n_sessions",
               "n_animals"]].rename(columns={"boot_change": "est", "boot_lo": "lo", "boot_hi": "hi"})
    for (pos, ep), d in lines.groupby(["pos", "epoch"]):
        e = d.set_index("lick").est
        a_lines = e.loc[[2, 3, 4, 5]].mean() - e.loc[1]
        a_cell = marks[(marks.pos == pos) & (marks.epoch == ep)].est.iloc[0]
        print(f"CHECK {pos} {ep}: mean(lines 2-5) - line 1 = {a_lines:.6f}, contrast (a) = {a_cell:.6f}")
        assert abs(a_lines - a_cell) < 1e-9
    save(lines, "lines_withintrial_aim_c2_bout10_ccB1125.csv")
    save(marks, "marks_withintrial_aim_c2_bout10_ccB1125.csv")
    print(lines.round(2).to_string())


if __name__ == "__main__":
    main()
