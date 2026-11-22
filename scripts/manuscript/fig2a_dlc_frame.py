"""Figure 2A: front-camera DeepLabCut frame with the tongue-angle construction.

Cohort 1 (two-tone, PS46-PS55), pre-stroke sessions. Reads the production DLC
predictions (``O2_analysis/<animal>/video2_<stamp>DLC_..._filtered.csv``) and
the raw front-camera video (``camera/<YYYYMMDD>/<animal>/video2_<stamp>.avi``,
read-only), then draws one frame in grayscale with current-frame labels only.

Tongue angle, as in ``stroke_orofacial.dlc_kinematics._angle``
(``_compute_signed_tongue_angle_deg``, sign_flip = -1) with the reference
points from ``tongue_pertrial._resolve_eye_midpoint_session_median``:

* E = midpoint of the session-median L_eye and R_eye (frames with both eye
  likelihoods >= 0.70);
* S = midpoint of the session-median L_spout and R_spout (likelihood >= 0.70);
* reference vector E -> S (the midline); tongue vector E -> tongue;
* theta = -atan2(cross(ref, v), dot(ref, v)), degrees. Positive = toward
  image right (mouse left, L_spout); negative = toward image left (R_spout).

The pipeline then smooths the per-frame angle (Gaussian, sigma 8 ms); the
per-frame value drawn here is reported next to the smoothed value.

Usage
-----
Scan sessions for candidate frames (prints a ranked table)::

    python fig2a_dlc_frame.py scan --session PS51:2025-04-28 [...] --cache DIR

Render candidates::

    python fig2a_dlc_frame.py render --frame PS51:2025-04-28:65959 [...] \
        --out DIR --cache DIR

Writes ``<tag>.png`` per frame (height 109.8 pt at 600 dpi) and
``candidates.csv`` (keypoints, likelihoods, angles).
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Arc

O2 = "/Volumes/Neurobio/MICROSCOPE/Priya/DeepLabCut/O2_analysis"
CAM = "/Volumes/Neurobio/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera"
FFMPEG = os.environ.get("FFMPEG", "/Users/Priya2/opt/anaconda3/envs/DEEPLABCUT/bin/ffmpeg")
FPS = 250.0
W_PX, H_PX = 800, 600
BPS = ["nose", "jaw", "tongue", "L_eye", "R_eye", "L_spout", "R_spout"]
EYE_LIK_THR = 0.70          # configs/defaults.yaml angle.eye_likelihood_threshold
SIGN_FLIP = -1.0            # configs/defaults.yaml angle.sign_flip
SIGMA_MS = 8.0              # configs/defaults.yaml angle.smoothing_gaussian_sigma_ms

PANEL_H_PT = 109.8          # main.tex: \includegraphics[height=109.8pt]
CROP_W, CROP_H = 556, 550   # aspect 1.011, as the v9 panel (378 x 374 px)
DPI = 600

# Fig 3C (cam_frames.svg) palette; eyes added.
COL = {
    "tongue": "#ff3b1f", "jaw": "#2b8cff", "nose": "#00e5ff",
    "L_spout": "#b45ff0", "R_spout": "#b45ff0",
    "L_eye": "#ffd21f", "R_eye": "#ffd21f",
}
LABEL = {
    "tongue": "tongue tip", "jaw": "jaw", "nose": "nose",
    "L_eye": "eye L", "R_eye": "eye R", "L_spout": "spout L", "R_spout": "spout R",
}


def _pipeline_angle_fn():
    """Load ``_compute_signed_tongue_angle_deg`` from the pipeline source
    without running the package ``__init__`` (which needs pyarrow)."""
    src = Path(__file__).resolve().parents[2] / "src" / "stroke_orofacial"
    for name, path in (("stroke_orofacial", src), ("stroke_orofacial.dlc_kinematics", src / "dlc_kinematics")):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [str(path)]
            sys.modules[name] = m
    spec = importlib.util.spec_from_file_location(
        "stroke_orofacial.dlc_kinematics._angle", src / "dlc_kinematics" / "_angle.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod._compute_signed_tongue_angle_deg, mod._gaussian_smooth_nan


ANGLE_FN, SMOOTH_FN = _pipeline_angle_fn()


def dlc_csv(animal: str, date: str) -> str:
    hits = sorted(glob.glob(f"{O2}/{animal}/video2_{date}T*_filtered.csv"))
    if len(hits) != 1:
        raise FileNotFoundError(f"{animal} {date}: {hits}")
    return hits[0]


def video_path(animal: str, date: str) -> str:
    hits = sorted(glob.glob(f"{CAM}/{date.replace('-', '')}/{animal}/video2_{date}T*.avi"))
    if len(hits) != 1:
        raise FileNotFoundError(f"{animal} {date}: {hits}")
    return hits[0]


def load_dlc(animal: str, date: str, cache: str) -> dict[str, np.ndarray]:
    os.makedirs(cache, exist_ok=True)
    cf = os.path.join(cache, f"cache_{animal}_{date}.npz")
    if os.path.exists(cf):
        z = np.load(cf)
        return {k: z[k] for k in z.files}
    df = pd.read_csv(dlc_csv(animal, date), header=[0, 1, 2], index_col=0)
    df.columns = [f"{b}_{c}" for _, b, c in df.columns]
    d = {f"{b}_{c}": df[f"{b}_{c}"].to_numpy(np.float64) for b in BPS for c in ("x", "y", "likelihood")}
    np.savez(cf, **d)
    return d


def session_refs(d: dict[str, np.ndarray]) -> tuple[float, float, float, float]:
    """(E_x, E_y, S_x, S_y) in image px, as the pipeline resolves them."""
    def med(b, mask):
        return np.median(d[f"{b}_x"][mask]), np.median(d[f"{b}_y"][mask])
    both = (d["L_eye_likelihood"] >= EYE_LIK_THR) & (d["R_eye_likelihood"] >= EYE_LIK_THR)
    lx, ly = med("L_eye", both)
    rx, ry = med("R_eye", both)
    slx, sly = med("L_spout", d["L_spout_likelihood"] >= EYE_LIK_THR)
    srx, sry = med("R_spout", d["R_spout_likelihood"] >= EYE_LIK_THR)
    return 0.5 * (lx + rx), 0.5 * (ly + ry), 0.5 * (slx + srx), 0.5 * (sly + sry)


def angles(d, refs):
    ex, ey, sx, sy = refs
    # Spout-centred frame, as the pipeline's input parquet.
    tx, ty = d["tongue_x"] - sx, d["tongue_y"] - sy
    raw = ANGLE_FN(tx, ty, ex - sx, ey - sy, sign_flip=SIGN_FLIP)
    return raw


def smoothed_at(d, refs, frame, lik_thr=0.5, half=50):
    lo, hi = max(0, frame - half), frame + half + 1
    sub = {k: v[lo:hi] for k, v in d.items()}
    a = angles(sub, refs)
    a[sub["tongue_likelihood"] < lik_thr] = np.nan
    s = SMOOTH_FN(a, SIGMA_MS / 1000.0 * FPS, mode="nearest")
    return float(s[frame - lo])


def grab_frame(animal: str, date: str, frame: int) -> np.ndarray:
    cmd = [FFMPEG, "-v", "error", "-ss", f"{frame / FPS:.6f}", "-i", video_path(animal, date),
           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H_PX, W_PX)


# --------------------------------------------------------------------------- scan
def scan(sessions, cache, top=8):
    rows = []
    for a, dt in sessions:
        d = load_dlc(a, dt, cache)
        refs = session_refs(d)
        ang = angles(d, refs)
        tl = d["tongue_likelihood"]
        stable = np.minimum.reduce([np.roll(tl, k) for k in (-1, 0, 1)])
        others = np.min([d[f"{b}_likelihood"] for b in BPS if b != "tongue"], axis=0)
        ext = d["tongue_y"] - d["jaw_y"]          # tongue below jaw (px)
        dy = np.gradient(d["tongue_y"])           # > 0: protruding
        m = (stable >= 0.95) & (others >= 0.90) & (np.abs(ang) >= 2.5) & (ext > 15) & (ext < 60)
        for i in np.where(m)[0]:
            rows.append(dict(animal=a, date=dt, frame=int(i), angle=ang[i], ext=ext[i], dy=dy[i],
                             minlik=min(others[i], tl[i])))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for (a, s), g in df.groupby(["animal", np.sign(df.angle)]):
        print(g.sort_values("minlik", ascending=False).head(top).round(3).to_string(index=False))
    return df


# ------------------------------------------------------------------------- render
def _txt(ax, x, y, s, color, ha="center", va="center", size=5.0):
    t = ax.text(x, y, s, color=color, ha=ha, va=va, fontsize=size, fontweight="bold",
                family="Arial")
    t.set_path_effects([pe.withStroke(linewidth=0.9, foreground="black", alpha=0.55)])
    return t


def render(animal, date, frame, out_dir, cache):
    d = load_dlc(animal, date, cache)
    refs = session_refs(d)
    ex, ey, sx, sy = refs
    img = grab_frame(animal, date, frame)
    p = {b: (d[f"{b}_x"][frame], d[f"{b}_y"][frame]) for b in BPS}
    lik = {b: float(d[f"{b}_likelihood"][frame]) for b in BPS}
    theta = float(angles({k: v[frame:frame + 1] for k, v in d.items()}, refs)[0])
    theta_s = smoothed_at(d, refs, frame)

    # Crop centred on the eye midpoint, bottom of the frame kept.
    x0 = int(round(np.clip(ex - CROP_W / 2, 0, W_PX - CROP_W)))
    y0 = H_PX - CROP_H
    crop = img[y0:y0 + CROP_H, x0:x0 + CROP_W].astype(np.float64)
    # Linear display stretch (0.5th-99.9th percentile); grayscale, no other processing.
    lo_v, hi_v = np.percentile(crop, (0.5, 99.9))
    crop = np.clip((crop - lo_v) / (hi_v - lo_v) * 255.0, 0, 255)

    h_in = PANEL_H_PT / 72.0
    w_in = h_in * CROP_W / CROP_H
    fig = plt.figure(figsize=(w_in, h_in), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(crop, cmap="gray", vmin=0, vmax=255, interpolation="lanczos",
              extent=(x0 - 0.5, x0 + CROP_W - 0.5, y0 + CROP_H - 0.5, y0 - 0.5))
    ax.set_xlim(x0 - 0.5, x0 + CROP_W - 0.5)
    ax.set_ylim(y0 + CROP_H - 0.5, y0 - 0.5)
    ax.axis("off")

    dot = dict(linewidth=0.5, linestyle=(0, (1.2, 1.6)), alpha=0.7, solid_capstyle="round",
               dash_capstyle="round")
    # eye to eye (current frame)
    ax.plot([p["L_eye"][0], p["R_eye"][0]], [p["L_eye"][1], p["R_eye"][1]], color="white", **dot)
    # midline: eye midpoint E -> spout midpoint S (session medians, as the pipeline)
    ax.plot([ex, sx], [ey, sy], color="white", **dot)
    # tongue vector: E -> tongue tip
    ax.plot([ex, p["tongue"][0]], [ey, p["tongue"][1]], color=COL["tongue"], **dot)
    for (x, y) in ((ex, ey), (sx, sy)):
        ax.plot(x, y, "o", ms=1.1, mfc="white", mec="none", alpha=0.85)

    # theta arc at E, between the midline and the tongue vector
    r = 0.72 * np.hypot(sx - ex, sy - ey)
    a_ref = np.degrees(np.arctan2(sy - ey, sx - ex))
    a_tng = np.degrees(np.arctan2(p["tongue"][1] - ey, p["tongue"][0] - ex))
    lo, hi = sorted((a_ref, a_tng))
    ax.add_patch(Arc((ex, ey), 2 * r, 2 * r, theta1=lo, theta2=hi, color="white", lw=0.6, alpha=0.95))
    side = 1 if p["tongue"][0] > sx else -1
    a_lab = np.radians(a_tng)
    _txt(ax, ex + r * np.cos(a_lab) + side * 13, ey + r * np.sin(a_lab) + 2, "θ", "white",
         size=6.0)

    # keypoints, current frame only
    for b in BPS:
        ax.plot(*p[b], "o", ms=2.6, mfc="none", mec=COL[b], mew=0.6)
    off = 11
    _txt(ax, p["L_eye"][0] + 4, p["L_eye"][1] - off - 2, LABEL["L_eye"], COL["L_eye"], ha="left")
    _txt(ax, p["R_eye"][0] - 4, p["R_eye"][1] - off - 2, LABEL["R_eye"], COL["R_eye"], ha="right")
    _txt(ax, p["nose"][0] + 8, p["nose"][1] - 6, LABEL["nose"], COL["nose"], ha="left")
    # jaw label on the side opposite the tongue, clear of the midline
    jaw_side = -1 if p["tongue"][0] > sx else 1
    jx = (min(p["jaw"][0], sx) - 7) if jaw_side < 0 else (max(p["jaw"][0], sx) + 7)
    _txt(ax, jx, p["jaw"][1] - 9, LABEL["jaw"], COL["jaw"], ha="left" if jaw_side > 0 else "right")
    _txt(ax, p["R_spout"][0] - 8, p["R_spout"][1] + 10, LABEL["R_spout"], COL["R_spout"], ha="right")
    _txt(ax, p["L_spout"][0] + 8, p["L_spout"][1] + 10, LABEL["L_spout"], COL["L_spout"], ha="left")
    t_side = -1 if p["tongue"][0] < sx else 1
    _txt(ax, p["tongue"][0] + t_side * 2, p["tongue"][1] + 14, LABEL["tongue"], COL["tongue"],
         ha="center")

    tag = f"fig2A_{animal}_{date.replace('-', '')}_f{frame}"
    fig.savefig(os.path.join(out_dir, tag + ".png"), dpi=DPI)
    plt.close(fig)

    cur_mid = (0.5 * (p["L_eye"][0] + p["R_eye"][0]), 0.5 * (p["L_eye"][1] + p["R_eye"][1]))
    row = dict(file=tag + ".png", animal=animal, date=date, frame=frame,
               time_s=round(frame / FPS, 3), video=video_path(animal, date), dlc_csv=dlc_csv(animal, date),
               theta_frame_deg=round(theta, 2), theta_smoothed_deg=round(theta_s, 2),
               eye_mid_session=f"({ex:.1f}, {ey:.1f})", spout_mid_session=f"({sx:.1f}, {sy:.1f})",
               eye_mid_frame_offset_px=round(float(np.hypot(cur_mid[0] - ex, cur_mid[1] - ey)), 1),
               crop=f"x {x0}-{x0 + CROP_W}, y {y0}-{y0 + CROP_H}")
    for b in BPS:
        row[f"{b}_lik"] = round(lik[b], 3)
        row[f"{b}_xy"] = f"({p[b][0]:.1f}, {p[b][1]:.1f})"
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--session", nargs="+", required=True, help="ANIMAL:YYYY-MM-DD")
    s.add_argument("--cache", required=True)
    r = sub.add_parser("render")
    r.add_argument("--frame", nargs="+", required=True, help="ANIMAL:YYYY-MM-DD:FRAME")
    r.add_argument("--out", required=True)
    r.add_argument("--cache", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        scan([tuple(x.split(":")) for x in a.session], a.cache)
    else:
        os.makedirs(a.out, exist_ok=True)
        rows = []
        for spec in a.frame:
            an, dt, fr = spec.split(":")
            rows.append(render(an, dt, int(fr), a.out, a.cache))
        out_csv = os.path.join(a.out, "candidates.csv")
        if os.path.exists(out_csv):
            raise FileExistsError(out_csv)
        pd.DataFrame(rows).to_csv(out_csv, index=False)
        print(pd.DataFrame(rows).T.to_string())


if __name__ == "__main__":
    main()
