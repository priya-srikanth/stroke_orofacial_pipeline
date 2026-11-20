"""Multi-camera calibration of the 2pRAM-era face rig from its ChArUco recordings (aniposelib bundle adjustment).

PORTED (copied, then reduced) from the widefield_pipeline repo, ``wfield_local/dlc_anipose.py`` @ 2026-11-18:
the rig-tuned ChArUco detector, one-row-per-pose thinning, pooled intrinsics, per-pair stereo, the rig-unmoved
test and the extrinsics-only bundle adjustment. No import crosses the repos. What changed for this rig and why:

* **Pinhole intrinsics: principal point pinned to the frame center, NO distortion, focal length free.** The
  board was not swept through enough depth / tilt (15-28 distinct poses per camera) to separate distortion and
  principal point from focal length: solved freely, the principal points land 0.36-0.41 image widths off
  center (video2 OUTSIDE its frame) and k1 reaches -2.7, at 0.5-0.7 px RMS. The lenses (Thorlabs MVL25TM23,
  low distortion, stopped down) justify zero distortion; the frame center is an ASSUMPTION (the 800x600 window's
  position on the 1280x1024 sensor was not recorded). Focal length IS identifiable: fixing f on a grid raises
  the RMS 3-6x at 1,700 px and the minimum sits at 4,900-5,700 px, i.e. at the 25 mm lens (``rig.NOMINAL_F_PX``),
  which ``check_intrinsics`` enforces.
* **Frames pair by TRIGGER index** (``rig.trigger_index``) plus a per-camera offset fitted from the board
  (``fit_offsets``), because the cameras drop frames and record no sync line.
* **video4 is detected on its un-mirrored frame** (``rig.detection_frame``).

Results 2026-11-18 (units = nominal 3.5 mm squares): PS46-50 (two March recordings, rig-unmoved test passed on
all 4 pairs, 0.05-0.29 deg) bundle reprojection 0.33 px; PS51-55 (one May recording, 7-20 poses per camera)
0.17 px.
"""

from __future__ import annotations

import itertools
import json
import pickle
from pathlib import Path

import numpy as np

from stroke_orofacial.pose3d import rig

#: aniposelib's own thresholds (CameraGroup.calibrate_rows): a view enters the intrinsics at >= 9 ChArUco
#: corners and a row enters the bundle adjustment at >= 8. Mirrored so reports quote what is applied.
MIN_CORNERS_INTRINSIC = 9
MIN_CORNERS_BUNDLE = 8
#: Board held still for a second at 250 fps is 250 frames and ONE view: rows closer than this are one pose.
POSE_GAP_S = 0.5
#: Views per camera handed to cv2.calibrateCamera; past this the solution stops moving and the runtime does not.
MAX_VIEWS = 150
#: Rig-unmoved test between two recordings of the same pair. Distances are in the solve's (nominal) units.
MAX_RIG_DRIFT_DEG = 1.0
MAX_RIG_DRIFT_UNITS = 2.0
#: A pair is JUDGED by the rig-unmoved test only with this many shared board poses in each recording. Below it
#: the pair's own stereo estimate is noise-limited: on 11-18 the side-below pairs (9-24 poses) disagreed by
#: 0.4-0.7 deg / 2.0-2.4 units between the March recordings while every camera's pose relative to video2
#: (85-145 poses per pair) agreed to 0.05-0.09 deg / ~0.5 units -- so the cameras had not moved relative to one
#: another, and the weak pairs only measure their own estimation noise. They are reported, not judged.
MIN_PAIR_POSES = 30
#: A focal length further than this from the lens's nominal value means the solve is not describing the lens.
MAX_F_DEVIATION = 0.15
MAX_ASPECT_ERROR = 0.05
OFFSET_SEARCH = range(-8, 9)


# ----------------------------------------------------------------------------------------------- detection
def tuned_board(spec=None):
    """aniposelib CharucoBoard with detector parameters for tens-of-pixel markers (geometry untouched).

    aniposelib's ladder starts at a 50 px adaptive-threshold window, larger than a marker in these views.
    """
    import cv2
    from aniposelib.boards import CharucoBoard

    spec = spec or rig.BOARD
    b = CharucoBoard(
        spec["squares_x"],
        spec["squares_y"],
        square_length=spec["square_mm"],
        marker_length=spec["marker_mm"],
        marker_bits=int(str(spec["dictionary"]).split("_")[1][0]),
        dict_size=int(str(spec["dictionary"]).split("_")[-1]),
    )
    p = b.detector_params
    p.adaptiveThreshWinSizeMin = 3
    p.adaptiveThreshWinSizeMax = 45
    p.adaptiveThreshWinSizeStep = 6
    p.adaptiveThreshConstant = 7
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    b.detector = cv2.aruco.ArucoDetector(b.dictionary, p)
    b.charuco_detector = cv2.aruco.CharucoDetector(b.board)
    b.charuco_detector.setDetectorParameters(p)
    return b


def detect_video(video, counter, cam: str, step: int = 1, spec=None) -> dict:
    """ChArUco rows for one calibration video, ``framenum`` = TRIGGER index (not the file frame index).

    ``grab()`` walks the file so only sampled frames are decoded. ``counter`` is column 0 of the matching
    timestamp CSV; a length mismatch with the video is refused rather than guessed around.
    """
    import cv2

    trig = rig.trigger_index(counter)
    board = tuned_board(spec)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    rows, i = [], 0
    try:
        while cap.grab():
            if i % step == 0:
                ok, frame = cap.retrieve()
                if ok and i < len(trig):
                    c, ids = board.detect_image(rig.detection_frame(frame, cam))
                    if c is not None and len(c) > 0:
                        rows.append({"framenum": int(trig[i]), "corners": c, "ids": ids})
            i += 1
    finally:
        cap.release()
    if i != len(trig):
        raise ValueError(f"{video}: {i} video frames vs {len(trig)} timestamp rows")
    return {
        "rows": board.fill_points_rows(rows),
        "size": size,
        "spec": dict(spec or rig.BOARD),
        "n_video": i,
        "n_ts": len(trig),
        "cam": cam,
    }


def load_rows(rec_dir: Path, cam: str, spec=None) -> dict:
    """Cached detections for one camera; refuses a cache made with a different board spec."""
    d = pickle.loads((Path(rec_dir) / f"rows_{cam}.pkl").read_bytes())
    want = {k: v for k, v in (spec or rig.BOARD).items()}
    got = {k: d["spec"].get(k) for k in want}
    if any(
        abs(float(got[k]) - float(want[k])) > 1e-6
        if isinstance(want[k], float)
        else got[k] != want[k]
        for k in want
    ):
        raise ValueError(
            f"{rec_dir}/{cam}: cached with board {d['spec']}, expected {want} -- re-detect"
        )
    return d


# ------------------------------------------------------------------------------------------------ helpers
def _framenum(row) -> int:
    f = row["framenum"]
    return int(f[1]) if isinstance(f, (tuple, list)) else int(f)


def one_per_pose(rows, fps: float = rig.FPS, gap_s: float = POSE_GAP_S):
    """One row per distinct board pose (rows more than ``gap_s`` apart)."""
    out, last = [], -1e18
    for r in sorted(rows, key=_framenum):
        f = _framenum(r)
        if (f - last) / fps > gap_s:
            out.append(r)
            last = f
    return out


def count_poses(rows, min_corners: int) -> int:
    f = np.sort(
        [_framenum(r) for r in rows if r["ids"] is not None and len(r["ids"]) >= min_corners]
    )
    return 0 if f.size == 0 else 1 + int((np.diff(f) / rig.FPS > POSE_GAP_S).sum())


def shifted(rows, s: int):
    out = []
    for r in rows:
        q = dict(r)
        q["framenum"] = _framenum(r) + int(s)
        out.append(q)
    return out


# --------------------------------------------------------------------------------------------- intrinsics
def pinhole_intrinsics(views_by_rec: dict, size, cam: str):
    """``(K, dist, rms, n_views)``: pinhole, principal point at the frame center, zero distortion, f free.

    ``views_by_rec`` maps a recording name to that camera's detection dict; views pool across recordings
    (same optics assumed -- nobody refocused between them; the rig-unmoved test is the check on that).
    """
    import cv2

    obj, img = [], []
    for d in views_by_rec.values():
        board = tuned_board(d["spec"])
        o, i = board.get_all_calibration_points(
            one_per_pose(d["rows"]), min_points=MIN_CORNERS_INTRINSIC
        )
        for a, b in zip(o, i):
            if len(a) >= MIN_CORNERS_INTRINSIC:
                obj.append(a)
                img.append(b)
    if len(obj) < 5:
        raise RuntimeError(f"{cam}: {len(obj)} usable views; cannot solve intrinsics")
    if len(obj) > MAX_VIEWS:
        k = np.linspace(0, len(obj) - 1, MAX_VIEWS).round().astype(int)
        obj, img = [obj[j] for j in k], [img[j] for j in k]
    f0 = rig.NOMINAL_F_PX[cam]
    K0 = np.array([[f0, 0, size[0] / 2.0], [0, f0, size[1] / 2.0], [0, 0, 1.0]])
    flags = (
        cv2.CALIB_USE_INTRINSIC_GUESS
        | cv2.CALIB_FIX_PRINCIPAL_POINT
        | cv2.CALIB_ZERO_TANGENT_DIST
        | cv2.CALIB_FIX_K1
        | cv2.CALIB_FIX_K2
        | cv2.CALIB_FIX_K3
    )
    rms, K, dist, _, _ = cv2.calibrateCamera(obj, img, tuple(size), K0, np.zeros(5), flags=flags)
    return K, dist, float(rms), len(obj)


def check_intrinsics(K, cam: str) -> list[str]:
    """Problems with a solved K, judged against the LENS (not the residual, which cannot see them)."""
    fx, fy = float(K[0, 0]), float(K[1, 1])
    f0 = rig.NOMINAL_F_PX[cam]
    out = []
    if abs((fx + fy) / 2 - f0) / f0 > MAX_F_DEVIATION:
        out.append(
            f"f={(fx + fy) / 2:.0f} px is >{MAX_F_DEVIATION:.0%} from the {rig.LENS_MM[cam]:g} mm lens "
            f"({f0:.0f} px)"
        )
    if abs(fx - fy) / max(fx, fy) > MAX_ASPECT_ERROR:
        out.append(f"fx={fx:.0f} vs fy={fy:.0f}: non-square pixels")
    return out


# --------------------------------------------------------------------------------------------- extrinsics
def pair_extrinsics(rows_a, rows_b, spec, size_a, size_b, Ka, da, Kb, db):
    """``(R, T, rms, n)`` for one camera pair in ONE recording, intrinsics fixed, one frame per pose."""
    import cv2

    board = tuned_board(spec)
    objp = board.get_object_points().reshape(-1, 3)
    by_a = {_framenum(r): r for r in rows_a}
    obj, ia, ib, last = [], [], [], -1e18
    for rb in sorted(rows_b, key=_framenum):
        f = _framenum(rb)
        ra = by_a.get(f)
        if ra is None or (f - last) / rig.FPS <= POSE_GAP_S:
            continue
        ids = np.intersect1d(np.asarray(ra["ids"]).ravel(), np.asarray(rb["ids"]).ravel())
        if len(ids) < MIN_CORNERS_BUNDLE:
            continue
        pa = ra["filled"].reshape(-1, 2)[ids]
        pb = rb["filled"].reshape(-1, 2)[ids]
        if np.isnan(pa).any() or np.isnan(pb).any():
            continue
        obj.append(np.float32(objp[ids]))
        ia.append(np.float32(pa))
        ib.append(np.float32(pb))
        last = f
    if len(obj) < 4:
        return None, None, float("nan"), len(obj)
    rms, *_, R, T, _, _ = cv2.stereoCalibrate(
        obj, ia, ib, Ka, da, Kb, db, tuple(size_a), flags=cv2.CALIB_FIX_INTRINSIC
    )
    return R, T, float(rms), len(obj)


def fit_offsets(rec: dict, K: dict, dist: dict) -> dict:
    """Per camera, the trigger offset vs ``rig.REFERENCE_CAM`` that minimizes the pair's stereo RMS.

    Returns ``{cam: {"shift", "rms", "n", "curve"}}``. A minimum on the edge of the search is refused: it
    means the true offset is outside the range, not that the edge is right.
    """
    ref = rig.REFERENCE_CAM
    out = {ref: {"shift": 0, "rms": None, "n": None, "curve": {}}}
    for cam in rig.CAMS:
        if cam == ref:
            continue
        curve = {}
        for s in OFFSET_SEARCH:
            _R, _T, e, n = pair_extrinsics(
                rec[ref]["rows"],
                shifted(rec[cam]["rows"], s),
                rec[ref]["spec"],
                rec[ref]["size"],
                rec[cam]["size"],
                K[ref],
                dist[ref],
                K[cam],
                dist[cam],
            )
            if np.isfinite(e):
                curve[s] = (e, n)
        best = min(curve, key=lambda s: curve[s][0])
        if best in (min(OFFSET_SEARCH), max(OFFSET_SEARCH)):
            raise RuntimeError(
                f"{cam}: offset minimum at the search edge ({best}); widen OFFSET_SEARCH"
            )
        out[cam] = {
            "shift": int(best),
            "rms": curve[best][0],
            "n": curve[best][1],
            "curve": {int(s): round(e, 3) for s, (e, _n) in curve.items()},
        }
    return out


def rig_unmoved(recs: dict, K: dict, dist: dict) -> list[dict]:
    """Same camera pair solved separately per recording: rotation / translation disagreement."""
    per_pair = {}
    for name, rec in recs.items():
        for a, b in itertools.combinations(rig.CAMS, 2):
            R, T, _rms, n = pair_extrinsics(
                rec[a]["rows"],
                rec[b]["rows"],
                rec[a]["spec"],
                rec[a]["size"],
                rec[b]["size"],
                K[a],
                dist[a],
                K[b],
                dist[b],
            )
            if R is not None:
                per_pair.setdefault((a, b), []).append((name, R, T, n))
    out = []
    for (a, b), got in sorted(per_pair.items()):
        for (n1, R1, T1, c1), (n2, R2, T2, c2) in itertools.combinations(got, 2):
            ang = float(np.degrees(np.arccos(np.clip((np.trace(R2 @ R1.T) - 1) / 2, -1, 1))))
            d = float(np.linalg.norm(T2.ravel() - T1.ravel()))
            judged = bool(min(c1, c2) >= MIN_PAIR_POSES)
            out.append(
                {
                    "pair": f"{a}-{b}",
                    "a": n1,
                    "b": n2,
                    "deg": round(ang, 3),
                    "units": round(d, 3),
                    "n_a": c1,
                    "n_b": c2,
                    "judged": judged,
                    "ok": bool(ang <= MAX_RIG_DRIFT_DEG and d <= MAX_RIG_DRIFT_UNITS),
                }
            )
    return out


# ---------------------------------------------------------------------------------------------------- solve
def solve_batch(rec_dirs: dict, thin: int = 5, verbose: bool = True) -> tuple[dict, object]:
    """Calibrate one animal batch from its recordings' cached detections.

    ``rec_dirs`` maps recording name -> directory holding ``rows_<cam>.pkl``. Returns (report, CameraGroup).
    Extrinsics pool across recordings only when the rig-unmoved test passes for every testable pair.
    """
    from aniposelib.cameras import CameraGroup

    recs = {name: {cam: load_rows(d, cam) for cam in rig.CAMS} for name, d in rec_dirs.items()}
    size = {cam: next(iter(recs.values()))[cam]["size"] for cam in rig.CAMS}
    K, dist, rep = {}, {}, {"recordings": list(rec_dirs), "board": rig.BOARD, "cameras": {}}
    for cam in rig.CAMS:
        K[cam], dist[cam], rms, n = pinhole_intrinsics(
            {r: recs[r][cam] for r in recs}, size[cam], cam
        )
        probs = check_intrinsics(K[cam], cam)
        rep["cameras"][cam] = {
            "intrinsic_rms_px": rms,
            "n_views": n,
            "problems": probs,
            "poses_bundle": {
                r: count_poses(recs[r][cam]["rows"], MIN_CORNERS_BUNDLE) for r in recs
            },
        }
        if verbose:
            print(
                f"  {cam}: f={K[cam][0, 0]:.0f} px (lens {rig.NOMINAL_F_PX[cam]:.0f}), RMS {rms:.3f} px, "
                f"{n} views{'  PROBLEM: ' + '; '.join(probs) if probs else ''}",
                flush=True,
            )
        if probs:
            raise RuntimeError(f"{cam}: {'; '.join(probs)}")

    rep["offsets"] = {}
    for name, rec in recs.items():
        off = fit_offsets(rec, K, dist)
        rep["offsets"][name] = off
        for cam in rig.CAMS:
            rec[cam]["rows"] = shifted(rec[cam]["rows"], off[cam]["shift"])
        if verbose:
            print(
                f"  {name} offsets vs {rig.REFERENCE_CAM}: "
                + ", ".join(
                    f"{c} {o['shift']:+d}" for c, o in off.items() if c != rig.REFERENCE_CAM
                ),
                flush=True,
            )

    agree = rig_unmoved(recs, K, dist) if len(recs) > 1 else []
    rep["rig_unmoved_test"] = agree
    judged = [a for a in agree if a["judged"]]
    pooled = bool(judged) and all(a["ok"] for a in judged)
    if len(recs) > 1 and not pooled:
        raise RuntimeError(f"rig-unmoved test failed or untestable: {agree}")
    if verbose:
        for a in agree:
            verdict = (
                ("consistent" if a["ok"] else "MOVED")
                if a["judged"]
                else f"not judged ({min(a['n_a'], a['n_b'])} < {MIN_PAIR_POSES} poses)"
            )
            print(
                f"  rig-unmoved {a['pair']}: {a['deg']:.3f} deg, {a['units']:.3f} units, "
                f"poses {a['n_a']}/{a['n_b']} -- {verdict}",
                flush=True,
            )

    cgroup = CameraGroup.from_names(list(rig.CAMS))
    for cam, c in zip(rig.CAMS, cgroup.cameras):
        c.set_size(size[cam])
        c.set_camera_matrix(K[cam].copy())
        c.set_distortions(np.asarray(dist[cam]).ravel().copy())
    per_cam = {c: [] for c in rig.CAMS}
    for i, name in enumerate(recs):
        for cam in rig.CAMS:
            for r in recs[name][cam]["rows"]:
                if _framenum(r) % thin == 0:
                    q = dict(r)
                    q["framenum"] = (i, _framenum(r))
                    per_cam[cam].append(q)
    err = cgroup.calibrate_rows(
        [per_cam[c] for c in rig.CAMS],
        tuned_board(rig.BOARD),
        init_intrinsics=False,
        init_extrinsics=True,
        verbose=verbose,
        only_extrinsics=True,
    )
    rep["reprojection_error_px"] = float(err)
    rep["thin"] = thin
    rep["camera_params"] = {c.get_name(): c.get_dict() for c in cgroup.cameras}
    if verbose:
        print(f"  bundle-adjusted reprojection error {err:.3f} px", flush=True)
    return rep, cgroup


def write(rep: dict, cgroup, dest: Path) -> list[Path]:
    """``calibration.json`` (provenance + checks) and ``calibration.toml`` (what triangulation loads)."""
    from stroke_orofacial._writeguard import assert_safe_write_path

    dest = Path(dest)
    assert_safe_write_path(str(dest))
    dest.mkdir(parents=True, exist_ok=True)
    j, t = dest / "calibration.json", dest / "calibration.toml"
    j.write_text(
        json.dumps(
            rep, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o)
        ),
        encoding="utf-8",
    )
    cgroup.dump(str(t))
    return [j, t]
