"""Rod tips for PS50 / PS55 median frames -> clips/<animal>_<date>_tips.json, with manual overrides (2026-11-19).

rods.rod_tips failed on these tips (checked by eye, rod_tips/rods_check_ps5055.png in the outputs):
* PS50 03-26 left rod: the face under it is dim, the centerline jump is ~+25 (< the +30 rule), the walk ran to the
  image bottom (y 594). Real end y 315 (centerline gray profile; right rod 317).
* PS55 05-02 (both rods) / 05-03 (both): a water drop on the rod end widens the dark blob, so the edge-read x and the
  tip row shift. Ends read from the profile (y 340-345, as on the clean PS55 sessions).
* PS55 05-28 left rod: a drop on its end; auto tip at y 261 (mid-rod), real end y 305 (right rod 301).
Override x = fitted centerline (top-row edge lines, unaffected by the drop) + the median (edge-read - centerline)
offset of the same rod on the same animal's clean sessions. Each override is recorded in the JSON ("override")."""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

# run from the lateral-test work dir; the package comes from this repo's src/
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from stroke_orofacial.pose3d import rods


def centerlines(m):
    ag = np.abs(cv2.Sobel(m.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3))
    prof = ag[20:150].mean(0)
    cols = np.where(prof > 0.3 * prof.max())[0]
    groups = np.split(cols, np.where(np.diff(cols) > 60)[0] + 1)
    groups = sorted([g for g in groups if g.max() - g.min() > 15], key=lambda g: -prof[g].sum())[:2]
    out = []
    for g in sorted(groups, key=lambda g: g.min()):
        mid = (g.min() + g.max()) // 2
        L = [rods._edge_line(ag, g.min() - 4, mid), rods._edge_line(ag, mid, g.max() + 5)]
        out.append(lambda y, L=L: (np.polyval(L[0], y) + np.polyval(L[1], y)) / 2)
    return out


clean = {
    "PS50": ["20250320", "20250321", "20250322", "20250324", "20250325"],
    "PS55": ["20250423", "20250426", "20250429"],
}
off = {}
for a, ds in clean.items():
    o = []
    for d in ds:
        m = np.load(f"median_{a}_{d}.npy")
        t = rods.rod_tips(m)
        c = centerlines(m)
        o.append([t[i][0] - c[i](t[i][1]) for i in range(2)])
    o = np.array(o)
    off[a] = np.median(o, 0)
    print(a, "offsets per session (L,R):", np.round(o, 1).tolist(), "median", np.round(off[a], 1))
fix = {
    ("PS50", "20250326"): {0: 315},
    ("PS55", "20250502"): {0: 345, 1: 345},
    ("PS55", "20250503"): {0: 345, 1: 340},
    ("PS55", "20250528"): {0: 305},
}
# sessions whose auto tips are fine but are not used for the offsets (PS55 late post, added 11-19 evening)
also = {"PS55": ["20250529", "20250610"]}
for a, ds in clean.items():
    for d in sorted(set(ds) | set(also.get(a, [])) | {dd for (aa, dd) in fix if aa == a}):
        m = np.load(f"median_{a}_{d}.npy")
        t = [list(x) for x in rods.rod_tips(m)]
        note = {}
        if (a, d) in fix:
            c = centerlines(m)
            for i, y in fix[(a, d)].items():
                old = t[i][:2]
                t[i] = [float(c[i](y) + off[a][i]), float(y), t[i][2]]
                note[str(i)] = (
                    f"manual 2026-11-19: auto tip {[round(v) for v in old]} wrong; y read from centerline gray profile, x = fitted centerline + {a} clean-session edge offset"
                )
        Path(f"clips/{a}_{d}_tips.json").write_text(
            json.dumps({"tips": t, **({"override": note} if note else {})})
        )
        print(a, d, [(round(x, 1), round(y)) for x, y, w in t], "FIXED" if note else "")
