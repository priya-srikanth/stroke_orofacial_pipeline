"""Occlusion check, by eye: front (raw video2, read-only) and below (video4 trial clip) frames for 8 below-view-only
tongue runs on PS46 03-16 (gated p > 0.4, >= 3 frames, > 6 frames from any front-view tongue-out / gap frame).
Run from the lateral-test work dir; writes occl_0316.png. Result 11-19: all 8 = no tongue in either view (water drop
on the spout or face labeled as tongue)."""

import glob
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

A, d = "PS46", "20250316"
Z = np.load(f"clips/{A}_{d}_index.npz")
idx4, trig2, trig4 = Z["idx4"], Z["trig2"], Z["trig4"]
m = np.full(int(trig2[-1]) + 1, -1)
m[trig2] = np.arange(len(trig2))
t = trig4[idx4]
f2 = np.where((t >= 0) & (t < len(m)), m[np.clip(t, 0, len(m) - 1)], -1)
P = pd.read_csv(glob.glob(f"preds/{A}_{d}_video4_trials_*.csv")[0], header=[0, 1, 2], index_col=0)
P.columns = P.columns.droplevel(0)
tg = P["tongue"][["x", "y", "likelihood"]].to_numpy(float)
tips = json.loads(Path(f"clips/{A}_{d}_tips.json").read_text())["tips"]
x0 = int(Z["x0"])
rod_y = np.mean([y for _, y, _ in tips])
mx = np.mean([x for x, _, _ in tips]) - x0
s4 = abs(tips[1][0] - tips[0][0])
below = (tg[:, 2] > 0.4) & (tg[:, 1] - rod_y > -40)
FC = np.load(f"clips/{A}_{d}_front_cleaned.npz")
fill = np.full(len(f2), -1)
ok = f2 >= 0
fill[ok] = FC["tongue_fill"][f2[ok]]
act = np.where((fill == 0) | (fill == 1))[0]
ar = np.arange(len(fill))
pos = np.searchsorted(act, ar)
dist = np.minimum(
    np.abs(ar - act[np.clip(pos - 1, 0, len(act) - 1)]),
    np.abs(act[np.clip(pos, 0, len(act) - 1)] - ar),
)
cand = below & (fill == 3)
runs = []
i = 0
while i < len(cand):
    if cand[i]:
        j = i
        while j < len(cand) and cand[j]:
            j += 1
        if j - i >= 3 and dist[i:j].min() > 6:
            runs.append((i, j))
        i = j
    else:
        i += 1
raw = pd.read_csv(
    glob.glob(f"M:/MICROSCOPE/Priya/DeepLabCut/O2_analysis/{A}/video2_2025-03-16T*_filtered.csv")[
        0
    ],
    header=[0, 1, 2],
    index_col=0,
)
raw.columns = raw.columns.droplevel(0)
fp = raw["tongue"]["likelihood"].to_numpy()
v2 = cv2.VideoCapture(
    glob.glob(
        f"M:/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera/{d}/{A}/video2_*.avi"
    )[0]
)
v4 = cv2.VideoCapture(f"clips/{A}_{d}_video4_trials.mp4")
sel = [runs[k] for k in np.linspace(0, len(runs) - 1, 8).astype(int)]
tiles = []
for a, b in sel:
    r = (a + b) // 2
    v2.set(cv2.CAP_PROP_POS_FRAMES, int(f2[r]))
    _, im2 = v2.read()
    v4.set(cv2.CAP_PROP_POS_FRAMES, r)
    _, im4 = v4.read()
    cv2.circle(im4, (int(tg[r, 0]), int(tg[r, 1])), 9, (0, 0, 255), 2)
    im2 = (
        cv2.resize(im2, (im4.shape[1] * im2.shape[0] // im2.shape[0], im4.shape[0]))
        if False
        else cv2.resize(im2, (600, 600))
    )
    im4 = cv2.resize(im4, (600, 600))
    lab = f"row {r} run {b - a}fr lat {(tg[r, 0] - mx) / s4:+.2f} front p {fp[f2[r]]:.2f} (max in run {fp[f2[a:b]].max():.2f})"
    tile = np.hstack([im2, im4])
    cv2.putText(tile, lab, (8, 25), 0, 0.7, (0, 255, 255), 2)
    tiles.append(cv2.resize(tile, (600, 300)))
cv2.imwrite("occl_0316.png", np.vstack([np.hstack(tiles[k : k + 2]) for k in range(0, 8, 2)]))
print(
    len(runs),
    "runs; front tongue p within runs, median of run max:",
    np.median([fp[f2[a:b]].max() for a, b in runs]).round(2),
)
