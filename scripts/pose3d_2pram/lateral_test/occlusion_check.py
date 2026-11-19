"""Does the below view (video4) see tongue the front view (video2) lost? PS46, all trial-window frames.
Front classes (cleaned tongue fill_method): 0 tracked out, 1 interpolated gap, 3 in. Below tongue = p > 0.4 and within
40 px above the rod-tip line (the clips' gate)."""

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = sys.argv[1] if len(sys.argv) > 1 else "PS46"
rows = []
for f in sorted(glob.glob(f"clips/{A}_*_front_cleaned.npz")):
    d = f.split("_")[1]
    Z = np.load(f"clips/{A}_{d}_index.npz")
    idx4, trig2, trig4 = Z["idx4"], Z["trig2"], Z["trig4"]
    m = np.full(int(trig2[-1]) + 1, -1)
    m[trig2] = np.arange(len(trig2))
    t = trig4[idx4]
    f2 = np.where((t >= 0) & (t < len(m)), m[np.clip(t, 0, len(m) - 1)], -1)
    P = pd.read_csv(
        glob.glob(f"preds/{A}_{d}_video4_trials_*.csv")[0], header=[0, 1, 2], index_col=0
    )
    P.columns = P.columns.droplevel(0)
    tg = P["tongue"][["x", "y", "likelihood"]].to_numpy(float)
    tips = json.loads(Path(f"clips/{A}_{d}_tips.json").read_text())["tips"]
    x0 = int(Z["x0"])
    rod_y = np.mean([y for _, y, _ in tips])
    mx = np.mean([x for x, _, _ in tips]) - x0
    s4 = abs(tips[1][0] - tips[0][0])
    below = (tg[:, 2] > 0.4) & (tg[:, 1] - rod_y > -40)
    FC = np.load(f)
    ok = f2 >= 0
    fill = np.full(len(f2), -1)
    fill[ok] = FC["tongue_fill"][f2[ok]]
    # distance (frames, video4 rows; rows are contiguous within a trial clip) to nearest front-out/gap frame
    act = np.where((fill == 0) | (fill == 1))[0]
    dist = np.full(len(fill), 10**6)
    if len(act):
        pos = np.searchsorted(act, np.arange(len(fill)))
        lo = act[np.clip(pos - 1, 0, len(act) - 1)]
        hi = act[np.clip(pos, 0, len(act) - 1)]
        dist = np.minimum(np.abs(np.arange(len(fill)) - lo), np.abs(hi - np.arange(len(fill))))
    # runs of below-tongue frames during front "in"
    cand = below & (fill == 3)
    runs, i = [], 0
    while i < len(cand):
        if cand[i]:
            j = i
            while j < len(cand) and cand[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    far = [(a, b) for a, b in runs if b - a >= 3 and dist[a:b].min() > 6]
    lat = [np.median((tg[a:b, 0] - mx) / s4) for a, b in far]
    # front lick bouts = runs of fill 0/1
    fo = (fill == 0) | (fill == 1)
    nb = int(((fo[1:]) & (~fo[:-1])).sum() + fo[0])
    rows.append(
        {
            "date": d,
            "front_out": int((fill == 0).sum()),
            "front_gap": int((fill == 1).sum()),
            "gap_seen_below": round(float(below[fill == 1].mean()), 2)
            if (fill == 1).any()
            else np.nan,
            "front_bouts": nb,
            "below_in_runs": len(runs),
            "runs_ge3_far": len(far),
            "far_runs_at_spout": int(sum(abs(abs(v) - 0.5) < 0.2 for v in lat)),
            "far_frames": int(sum(b - a for a, b in far)),
        }
    )
R = pd.DataFrame(rows)
print(R.to_string(index=False))
R.to_csv(f"occlusion_check_{A}.csv", index=False)
