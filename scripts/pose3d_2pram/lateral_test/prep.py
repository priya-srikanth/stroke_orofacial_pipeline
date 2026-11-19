"""Per session: trial windows (tone .. tone+1 s) in video4, paired to video2 by trigger index, written as one
600x600 cam1-orientation clip (vflip, x 100:700) for the cam1 LP model. Also rod tips from the median frame.
Usage: prep.py ANIMAL DATE"""

import glob
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from stroke_orofacial.pose3d.rods import rod_tips  # run with PYTHONPATH=<repo>/src

RAW = "M:/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera"
FF = glob.glob(
    "C:/Users/SabatiniLab/miniconda3/envs/lp/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*.exe"
)[0]
WIN = 250  # frames after the tone (1 s): covers the first 3-5 licks
X0 = 100  # crop offset (cam1 frame = x 100:700)
animal, date = sys.argv[1], sys.argv[2]
E = json.loads(Path(f"clips/{animal}_{date}_events.json").read_text())  # from events.py
rd = f"{RAW}/{date}/{animal}"
trig = {}
for i in (2, 4):
    c = np.loadtxt(
        glob.glob(f"{rd}/timestamp{i}_*.csv")[0], delimiter=",", usecols=0, dtype=np.int64
    )
    trig[i] = c - c[0]
    assert np.all(np.diff(trig[i]) > 0)
tone2 = np.array(E["tone2"])
pos = np.searchsorted(trig[4], trig[2][tone2])
pos = np.minimum(pos, len(trig[4]) - 1)
exact = trig[4][pos] == trig[2][tone2]
cap = cv2.VideoCapture(glob.glob(f"{rd}/video4_*.avi")[0])
n4 = int(cap.get(7))
assert n4 == len(trig[4]), (n4, len(trig[4]))
# median frame -> rod tips (cam1 orientation, full width)
fr = []
for i in np.linspace(1000, n4 - 1000, 40).astype(int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
    ok, f = cap.read()
    if ok:
        fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[::-1, :])
med = np.median(fr, 0).astype(np.float32)
np.save(f"median_{animal}_{date}.npy", med)
tips = rod_tips(med)
out = f"clips/{animal}_{date}_video4_trials.mp4"
p = subprocess.Popen(
    [
        FF,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-s",
        "600x600",
        "-r",
        "250",
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-crf",
        "12",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        out,
    ],
    stdin=subprocess.PIPE,
)
idx4 = []
for k, f4 in enumerate(pos):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(f4))
    for j in range(WIN):
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[::-1, :][:, X0 : X0 + 600]
        p.stdin.write(np.ascontiguousarray(g).tobytes())
        idx4.append(int(f4) + j)
p.stdin.close()
p.wait()
np.savez(
    f"clips/{animal}_{date}_index.npz",
    idx4=np.array(idx4),
    trig2=trig[2],
    trig4=trig[4],
    tone2=tone2,
    tone4=pos,
    exact=exact,
    sides=np.array(E["sides"]),
    tips=np.array(tips),
    x0=X0,
)
print(
    animal,
    date,
    "trials",
    len(tone2),
    "exact trigger match",
    int(exact.sum()),
    "frames",
    len(idx4),
    "rod tips",
    [(round(x), round(y)) for x, y, w in tips],
    flush=True,
)
