"""Fit-free pre->post comparison: change in lateral position (rod-tip spacings from the rod midpoint) per session x
trial side, front view (L2 = spout-centered x at the max-angle frame / front rod spacing) vs below view (L4).
Run twice: all licks, and with a plausibility gate on the below-view point (|L4| <= 1 and |F4| <= 0.6 rod spacings:
a tongue point near the mouth; PS50's zero-shot model also labels points up to 2.7 spacings lateral / 1.9 behind)."""

import sys

import numpy as np
import pandas as pd

rows = []
for A in sys.argv[1:]:
    D0 = pd.read_csv(f"licks_{A}.csv").dropna(subset=["A2", "L2", "L4"])
    for gate in ("all", "gated"):
        D = D0 if gate == "all" else D0[(D0.L4.abs() <= 1) & (D0.F4.abs() <= 0.6)]
        S = D.groupby(["date", "epoch", "side"])[["L2", "L4"]].agg(["mean", "size"])
        S.columns = ["L2", "n", "L4", "_"]
        S = S.drop(columns="_").reset_index()
        base = S[S.epoch == "pre"].groupby("side")[["L2", "L4"]].mean()
        S["dL2"] = S.L2 - S.side.map(base.L2)
        S["dL4"] = S.L4 - S.side.map(base.L4)
        r = D.groupby("date")[["L2", "L4"]].apply(lambda g: np.corrcoef(g.L2, g.L4)[0, 1])
        S["r_session"] = S.date.map(r)
        S.insert(0, "gate", gate)
        S.insert(0, "animal", A)
        rows.append(S)
        print(f"== {A} {gate}: kept {len(D)}/{len(D0)} licks; per-session r {r.round(2).tolist()}")
        print(
            S[S.epoch == "post"][["date", "side", "n", "dL2", "dL4"]]
            .round(3)
            .to_string(index=False)
        )
pd.concat(rows).round(4).to_csv("fitfree_" + "_".join(sys.argv[1:]) + ".csv", index=False)
