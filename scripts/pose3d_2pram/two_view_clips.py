"""Two-view 3-D check clips for the PS46-PS55 rig (the cohort-2 four-camera clips, for this rig).

Top: video2 (front; 2025 DLC: tongue / jaw = the pipeline's cleaned traces, small open circle = interpolated frame;
nose / eyes / rods = raw DLC, p > 0.6) and video4 (from below, shown in widefield-cam1 orientation; widefield cam1 LP
model run zero-shot, p > 0.9) with their 2-D keypoints (dot), the rod tips (rings) and the tongue / jaw / nose
3-D point projected back into each camera (x). Bottom: the 3-D points in a per-session frame, projected flat from below
(lateral x forward) and from the front (lateral x up): rods as rings, nose, and the last 120 ms of tongue and jaw.

3-D = linear triangulation of the two views with the batch calibration (pose3d/calibration/<batch>/calibration.toml).
The two models do not share label definitions (front-view DLC vs below-view widefield cam1 labels), so a 3-D point is
"the ray intersection of two related labels": the per-session median reprojection error says how related.
Frame pairing: trigger index (counter - counter[0]), offset 0 (the board's video4-vs-video2 value; it cannot be refitted
on these keypoints, see run()).

Session frame: origin = midpoint of the two rod tips; x = lateral (DLC L_spout -> R_spout); z = up (away from the
below camera); y = forward (toward the nose). Units = nominal mm (board square assumed 3.5 mm; true scale unknown,
angles unaffected).

Inputs come from the lateral-angle test (trial windows tone .. tone + 1 s; per-session index npz from prep.py, LP
predictions, rod tips). Run (dlc env; a pose env, cv2 + aniposelib):

    PYTHONPATH=src python scripts/pose3d_2pram/two_view_clips.py PS46:20250310 PS46:20250316 \
        --work C:/Users/SabatiniLab/lp_stage/pram_3d_20261118/latangle
"""

from __future__ import annotations

import argparse
import glob
import io
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from stroke_orofacial.pose3d import rig

DLC = "M:/MICROSCOPE/Priya/DeepLabCut/O2_analysis"
RAW = "M:/MICROSCOPE/Rich/data/2pRAM/facerhythm_stroke_biomarker_exp/camera"
OUT = "M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs/pose3d"
STROKE = {
    "PS46": "20250313",
    "PS47": "20250313",
    "PS48": "20250313",
    "PS49": "20250317",
    "PS50": "20250323",
}
PARTS3D = ["tongue", "jaw", "nose"]
BGR = {
    "nose": (0, 215, 255),
    "jaw": (60, 220, 60),
    "tongue": (60, 60, 255),
    "eye": (255, 120, 255),
    "rod": (255, 200, 0),
}
HEX = {"nose": "#ffd700", "jaw": "#3cdc3c", "tongue": "#ff3c3c", "rod": "#00c8ff"}
#: widefield cam1 LP model on video4, per-part cutoffs. Tongue 0.4 + a position gate (below_tongue_cutoff.py, 11-19:
#: vs the front view's cleaned tongue, p 0.9 -> 0.4 raises recall of front-"out" frames from 28-37 % to 46-57 %, the
#: added points 90-96 % on tongue-out frames, lateral r with the front 0.86-0.92; below 0.4 adds ~1-2 %). Jaw 0.6 =
#: the cohort-2 cam1 analysis cutoff. Nose stays 0.9.
P4 = {"tongue": 0.4, "jaw": 0.6, "nose": 0.9}
#: the zero-shot model puts "tongue" on the NOSE TIP (between the nostrils, ~126 px above the rod tips) while the tongue
#: is in -- PS46 03-16: 34 % of front-"in" frames. A real tongue point is never > 40 px above the rod-tip line
#: (front-"out" frames: p1 -23 .. -47 px, p50 +17 .. +26 px; 03-16 p1 -114 = those nose frames).
TONGUE_GATE_PX = 40.0
#: 2025 DLC (video2), RAW labels (nose, eyes, rods): this cohort used low cutoffs (Priya 11-19: "0.6 or 0.5").
#: Tongue and jaw do not use raw DLC at all: they come from the pipeline's CLEANED traces (export_front_cleaned.py).
DLC_P = {}
DLC_P_DEFAULT = 0.60
CLEANED = ("tongue", "jaw")


def dlc_p(part):
    return DLC_P.get(part, DLC_P_DEFAULT)


TILE = 420
TRAIL = 30  # frames = 120 ms
CROP_X0 = 100  # video4 cam1-orientation crop = x 100:700 of the vertically flipped raw frame
#: A session whose rods (static) reproject worse than this does not match the calibration: a camera moved (PS46
#: 2025-03-20: rods 29-37 px, every part ~35-39 px at any frame offset; 03-10 / 03-16: rods 0-12, parts 3-11 px).
#: No clips are written for it (its 3-D would be wrong); the summary records why.
MAX_ROD_REPROJ_PX = 20.0


def v4crop_to_cal(xy):
    """video4 keypoints in the cam1-orientation crop -> the calibration's video4 frame (raw, horizontally flipped)."""
    xy = np.asarray(xy, float)
    return np.stack([799.0 - (xy[..., 0] + CROP_X0), 599.0 - xy[..., 1]], -1)


def cal_to_v4crop(xy):
    xy = np.asarray(xy, float)
    return np.stack([799.0 - xy[..., 0] - CROP_X0, 599.0 - xy[..., 1]], -1)


def cal_to_v4full(xy):
    """calibration video4 frame -> full-width cam1 orientation (vertical flip of raw)."""
    xy = np.asarray(xy, float)
    return np.stack([799.0 - xy[..., 0], 599.0 - xy[..., 1]], -1)


def load_dlc(animal, date):
    dd = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    f = glob.glob(f"{DLC}/{animal}/video2_{dd}T*_filtered.csv")[0]
    d = pd.read_csv(f, header=[0, 1, 2], index_col=0)
    d.columns = d.columns.droplevel(0)
    return {
        bp: d[bp][["x", "y", "likelihood"]].to_numpy(float)
        for bp in d.columns.get_level_values(0).unique()
    }


def load_lp(work, animal, date):
    p = glob.glob(f"{work}/preds/{animal}_{date}_video4_trials_*.csv")[0]
    d = pd.read_csv(p, header=[0, 1, 2], index_col=0)
    d.columns = d.columns.droplevel(0)
    return {bp: d[bp][["x", "y", "likelihood"]].to_numpy(float) for bp in ("nose", "jaw", "tongue")}


def triangulate(cg, a2, a4):
    """a2, a4: (N, 2) in calibration pixels (NaN where missing) -> (N, 3), (N,) mean reprojection error (px)."""
    pts = np.stack([a2, a4])
    X = cg.triangulate(pts, progress=False)
    rep = cg.project(X).reshape(2, -1, 2)
    err = np.nanmean(np.linalg.norm(rep - pts, axis=-1), 0)
    return X, err


def run(session, work, out_dir, n_per_side=1):
    import matplotlib
    from aniposelib.cameras import CameraGroup

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    animal, date = session.split(":")
    cg = CameraGroup.load(
        f"{OUT}/calibration/{rig.BATCH_OF[animal]}/calibration.toml"
    ).subset_cameras_names(["video2", "video4"])
    Z = np.load(f"{work}/clips/{animal}_{date}_index.npz")
    idx4, trig2, trig4, tone2 = Z["idx4"], Z["trig2"], Z["trig4"], Z["tone2"]
    sides = Z["sides"]
    rods4 = np.array(
        json.loads(Path(f"{work}/clips/{animal}_{date}_tips.json").read_text())["tips"]
    )[:, :2]  # full-width cam1
    rods4_cal = np.stack([799.0 - rods4[:, 0], 599.0 - rods4[:, 1]], -1)
    D2, L4 = load_dlc(animal, date), load_lp(work, animal, date)
    FC = np.load(
        f"{work}/clips/{animal}_{date}_front_cleaned.npz"
    )  # cleaned tongue / jaw, video2 image px
    f2_of_trig = np.full(int(trig2[-1]) + 1, -1)
    f2_of_trig[trig2] = np.arange(len(trig2))

    def paired(offset):
        """clip rows with their video2 frame, at a video4-minus-video2 trigger offset."""
        t = trig4[idx4] - offset
        ok = (t >= 0) & (t < len(f2_of_trig))
        f2 = np.full(len(idx4), -1)
        f2[ok] = f2_of_trig[t[ok]]
        return f2

    rod_y = float(rods4[:, 1].mean())

    def ok4(part):
        """video4 frames whose `part` label is kept (cutoff; tongue also the nose-tip gate)."""
        m = L4[part][:, 2] > P4[part]
        if part == "tongue":
            m &= L4[part][:, 1] - rod_y > -TONGUE_GATE_PX
        return m

    def views(part, f2):
        good = f2 >= 0
        a2 = np.full((len(f2), 2), np.nan)
        if part in CLEANED:  # tracked + interpolated frames of the cleaned trace (NaN = tongue in)
            a2[good] = FC[f"{part}_xy"][f2[good]]
        else:
            a2[good] = np.where(
                D2[part][f2[good], 2:3] > dlc_p(part), D2[part][f2[good], :2], np.nan
            )
        a4 = np.where(ok4(part)[:, None], v4crop_to_cal(L4[part][:, :2]), np.nan)
        return a2, a4

    # Frame offset: fixed at 0 (trigger index), the value the board fitted for video4 vs video2 in calibration_2.
    # It cannot be refitted on keypoints here: the two models' labels are not the same physical point, and that
    # constant mismatch (nose ~5 px, jaw ~6, tongue ~11) swamps the timing term -- on PS46 03-10 the median error
    # moved < 1.5 px over -20..+20 frames. The scan is still reported (diagnostic only).
    errs = {}
    for k in range(-6, 7, 2):
        a2, a4 = views("tongue", paired(k))
        both = np.isfinite(a2[:, 0]) & np.isfinite(a4[:, 0])
        if both.sum() > 200:
            errs[k] = round(float(np.median(triangulate(cg, a2[both], a4[both])[1])), 2)
    offset = 0
    f2 = paired(offset)

    # rods: which video4 rod is DLC L_spout? pick the pairing with the smaller reprojection error
    rod2 = np.array(
        [
            [np.median(D2[s][D2[s][:, 2] > dlc_p(s), i]) for i in (0, 1)]
            for s in ("L_spout", "R_spout")
        ]
    )
    best = None
    for order in ((0, 1), (1, 0)):
        Xr, er = triangulate(cg, rod2, rods4_cal[list(order)])
        if best is None or er.mean() < best[2].mean():
            best = (order, Xr, er)
    order, rodX, rod_err = best
    rods4_full = rods4[list(order)]

    X, E = {}, {}
    for p in PARTS3D:
        a2, a4 = views(p, f2)
        X[p], E[p] = triangulate(cg, a2, a4)
    # session frame: x = lateral (rod L_spout -> R_spout), z = up (away from the below camera, orthogonal to x),
    # y = forward (sign: the nose has y > 0). Display frame only -- not necessarily right-handed.
    origin = rodX.mean(0)
    ex = (rodX[1] - rodX[0]) / np.linalg.norm(rodX[1] - rodX[0])
    M4 = cg.cameras[[c.get_name() for c in cg.cameras].index("video4")].get_extrinsics_mat()
    down = (-M4[:3, :3].T @ M4[:3, 3]) - origin
    ez = -(down - down.dot(ex) * ex)
    ez /= np.linalg.norm(ez)
    ey = np.cross(ez, ex)
    if (np.nanmedian(X["nose"], 0) - origin).dot(ey) < 0:
        ey = -ey
    R = np.stack([ex, ey, ez])

    def to_frame(P):
        return (np.asarray(P) - origin) @ R.T

    XF = {p: to_frame(X[p]) for p in PARTS3D}
    rodF = to_frame(rodX)
    summary = {
        "session": session,
        "frame_offset_video4_minus_video2": offset,
        "offset_scan_px": errs,
        "rod_reprojection_px": rod_err.round(2).tolist(),
        "rod_separation_nominal_mm": float(np.linalg.norm(rodX[1] - rodX[0])),
        "median_reprojection_px": {p: float(np.nanmedian(E[p])) for p in PARTS3D},
        "frames_3d_fraction": {p: float(np.isfinite(E[p]).mean()) for p in PARTS3D},
    }
    summary["matches_calibration"] = bool(np.max(rod_err) <= MAX_ROD_REPROJ_PX)
    print(json.dumps(summary, indent=1), flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"twoview_{animal}_{date}_summary.json").write_text(json.dumps(summary, indent=1))
    if not summary["matches_calibration"]:
        print(
            f"{session}: rods reproject at {rod_err.round(1)} px > {MAX_ROD_REPROJ_PX}: a camera moved since the "
            "calibration -> no clips",
            flush=True,
        )
        return []

    # trials: per side, the n trials with the most two-view tongue frames
    n_tr = len(tone2)
    per_trial = len(idx4) // n_tr
    t_ok = np.isfinite(E["tongue"]).reshape(n_tr, per_trial).sum(1)
    picks = []
    for s in ("L", "R"):
        cand = [i for i in np.argsort(-t_ok) if sides[i] == s][:n_per_side]
        picks += cand
    out_dir.mkdir(parents=True, exist_ok=True)
    epoch = "pre" if date < STROKE[animal] else "post"
    cap2 = cv2.VideoCapture(glob.glob(f"{RAW}/{date}/{animal}/video2_*.avi")[0])
    cap4 = cv2.VideoCapture(glob.glob(f"{RAW}/{date}/{animal}/video4_*.avi")[0])
    # Crop boxes: a square that holds EVERY point drawn in the picked trials (2-D labels incl. the cleaned tongue at
    # full extension, the 3-D points reprojected, rods), plus a margin -- a fixed box around the face cut off long
    # front-view licks and the below-view jaw (Priya 11-19). video4 is drawn from the FULL-width flipped frame (not
    # the model's 600-px crop) so the box can extend past it; all video4 coordinates below are full-width cam1.
    rows_all = np.concatenate([np.arange(t * per_trial, (t + 1) * per_trial) for t in picks])
    rows_all = rows_all[f2[rows_all] >= 0]
    pts2, pts4 = [rod2], [rods4_full]
    ff = f2[rows_all]
    for b in ("L_eye", "R_eye", "L_spout", "R_spout", *PARTS3D):
        if b in CLEANED:
            pts2.append(FC[f"{b}_xy"][ff])
        else:
            q = D2[b][ff]
            pts2.append(q[q[:, 2] > dlc_p(b), :2])
    for p in PARTS3D:
        q = L4[p][rows_all]
        pts4.append(q[ok4(p)[rows_all], :2] + [CROP_X0, 0])
        ok = np.isfinite(E[p][rows_all])
        if ok.any():
            rp = cg.project(X[p][rows_all[ok]]).reshape(2, -1, 2)
            pts2.append(rp[0])
            pts4.append(cal_to_v4full(rp[1]))

    def fit_box(pts, margin):
        pts = np.vstack(pts)
        pts = pts[np.all(np.isfinite(pts), 1)]
        lo, hi = pts.min(0) - margin, pts.max(0) + margin
        s = int(np.ceil(max(hi - lo)))
        c = (lo + hi) / 2
        return (int(np.round(c[0] - s / 2)), int(np.round(c[1] - s / 2)), s)

    box2, box4 = fit_box(pts2, 40), fit_box(pts4, 40)
    print(f"{session}: front box {box2}, below box {box4} (x0, y0, side px)", flush=True)

    allpts = np.vstack([XF["tongue"], XF["jaw"], XF["nose"], rodF])
    lim = np.nanpercentile(allpts, [0.5, 99.5], axis=0)
    shown = np.vstack([XF[p][rows_all] for p in PARTS3D])  # never clip a 3-D point that is drawn
    lim = np.stack(
        [
            np.nanmin(np.vstack([lim[0], rodF.min(0), np.nanmin(shown, 0)]), 0),
            np.nanmax(np.vstack([lim[1], rodF.max(0), np.nanmax(shown, 0)]), 0),
        ]
    ) + [[-1], [1]]

    def crop(im, box):
        x0, y0, s = box
        pad = cv2.copyMakeBorder(im, s, s, s, s, cv2.BORDER_CONSTANT)
        return cv2.resize(pad[y0 + s : y0 + 2 * s, x0 + s : x0 + 2 * s], (TILE, TILE)), TILE / s

    def mark(im, xy, box, sc, color, kind):
        if xy is None or not np.all(np.isfinite(xy)):
            return
        x, y = (np.asarray(xy) - box[:2]) * sc
        p = (round(x), round(y))
        if kind == "dot":
            cv2.circle(im, p, 5, color, -1, cv2.LINE_AA)
        elif kind == "iring":  # interpolated cleaned-trace frame
            cv2.circle(im, p, 5, color, 1, cv2.LINE_AA)
        elif kind == "ring":
            cv2.circle(im, p, 8, color, 2, cv2.LINE_AA)
        else:
            cv2.drawMarker(im, p, color, cv2.MARKER_TILTED_CROSS, 14, 2, cv2.LINE_AA)

    written = []
    for tr in picks:
        rows = np.arange(tr * per_trial, (tr + 1) * per_trial)
        path = out_dir / f"twoview_{animal}_{date}_{epoch}_trial{tr:03d}_{sides[tr]}.mp4"
        vw = None
        for j, r in enumerate(rows):
            if f2[r] < 0:
                continue
            cap2.set(cv2.CAP_PROP_POS_FRAMES, int(f2[r]))
            ok2, im2 = cap2.read()
            cap4.set(cv2.CAP_PROP_POS_FRAMES, int(idx4[r]))
            okr4, im4 = cap4.read()
            if not (ok2 and okr4):
                continue
            im4 = np.ascontiguousarray(im4[::-1])  # cam1 orientation, full width
            t2, s2 = crop(im2, box2)
            t4, s4 = crop(im4, box4)
            for b in ("L_spout", "R_spout"):
                mark(
                    t2,
                    D2[b][f2[r], :2] if D2[b][f2[r], 2] > dlc_p(b) else None,
                    box2,
                    s2,
                    BGR["rod"],
                    "ring",
                )
            for b in ("L_eye", "R_eye"):
                mark(
                    t2,
                    D2[b][f2[r], :2] if D2[b][f2[r], 2] > dlc_p(b) else None,
                    box2,
                    s2,
                    BGR["eye"],
                    "dot",
                )
            for rp in rods4_full:
                mark(t4, rp, box4, s4, BGR["rod"], "ring")
            for p in PARTS3D:
                if p in CLEANED:
                    fl = FC[f"{p}_fill"][f2[r]]
                    mark(t2, FC[f"{p}_xy"][f2[r]], box2, s2, BGR[p], "dot" if fl == 0 else "iring")
                elif D2[p][f2[r], 2] > dlc_p(p):
                    mark(t2, D2[p][f2[r], :2], box2, s2, BGR[p], "dot")
                if ok4(p)[r]:
                    mark(t4, L4[p][r, :2] + [CROP_X0, 0], box4, s4, BGR[p], "dot")
                if np.isfinite(E[p][r]):
                    rep = cg.project(X[p][r][None]).reshape(2, 2)
                    mark(t2, rep[0], box2, s2, BGR[p], "x")
                    mark(t4, cal_to_v4full(rep[1]), box4, s4, BGR[p], "x")
            for t, lab in (
                (t2, "video2 (front) - DLC 2025"),
                (t4, "video4 (below) - widefield cam1 model"),
            ):
                cv2.putText(
                    t, lab, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA
                )
            top = np.hstack([t2, t4])

            fig, axs = plt.subplots(1, 2, figsize=(2 * TILE / 100, 3.6), dpi=100)
            lo = max(0, j - TRAIL)
            for ax, (a, b, ttl, yl) in zip(
                axs,
                (
                    (0, 1, "3-D from below", "forward (nominal mm)"),
                    (0, 2, "3-D from the front", "up (nominal mm)"),
                ),
            ):
                ax.scatter(
                    rodF[:, a],
                    rodF[:, b],
                    s=70,
                    facecolors="none",
                    edgecolors=HEX["rod"],
                    linewidths=1.5,
                )
                for p in ("tongue", "jaw"):
                    trl = XF[p][rows[lo : j + 1]]
                    ax.plot(trl[:, a], trl[:, b], c=HEX[p], lw=1.2, alpha=0.7)
                for p in PARTS3D:
                    if np.all(np.isfinite(XF[p][r])):
                        ax.scatter(XF[p][r, a], XF[p][r, b], s=28, c=HEX[p], zorder=3)
                ax.set_xlim(lim[0, a], lim[1, a])
                ax.set_ylim(lim[0, b], lim[1, b])
                ax.set_aspect("equal")
                ax.set_xlabel("lateral, toward R_spout (nominal mm)", fontsize=7)
                ax.set_ylabel(yl, fontsize=7)
                ax.tick_params(labelsize=6)
                ax.spines[["top", "right"]].set_visible(False)
                ax.set_title(ttl, fontsize=8)
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            plt.close(fig)
            bot = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR)
            bot = cv2.resize(bot, (top.shape[1], int(bot.shape[0] * top.shape[1] / bot.shape[1])))
            head = np.zeros((34, top.shape[1], 3), np.uint8)
            t_ms = j * 1000.0 / rig.FPS
            cv2.putText(
                head,
                f"{animal} {date} ({epoch}-stroke)  trial {tr} {sides[tr]}  tone + {t_ms:4.0f} ms   "
                f"(10x slow)  dot = 2-D label, x = 3-D point reprojected, big ring = rod tip",
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.47,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            frame = np.vstack([head, top, bot])
            if vw is None:
                vw = cv2.VideoWriter(
                    str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25, (frame.shape[1], frame.shape[0])
                )
            vw.write(frame)
        if vw is not None:
            vw.release()
            written.append(path)
            print("wrote", path, flush=True)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sessions", nargs="+", help="ANIMAL:YYYYMMDD")
    ap.add_argument("--work", required=True, help="lateral-test work dir (clips/, preds/)")
    ap.add_argument("--out", default=f"{OUT}/clips/twoview_cam1zeroshot_20261119")
    ap.add_argument("--per-side", type=int, default=1)
    a = ap.parse_args(argv)
    for s in a.sessions:
        run(s, a.work, Path(a.out), a.per_side)


if __name__ == "__main__":
    main()
