"""Calibrate the 2pRAM-era four-camera rig per animal batch (see stroke_orofacial.pose3d.rig / .calibration).

    python scripts/pose3d_2pram/calibrate.py detect            # ChArUco rows per recording x camera (cached)
    python scripts/pose3d_2pram/calibrate.py solve             # pinhole intrinsics, offsets, bundle -> toml/json

Raw videos are READ from the camera tree (never written); everything lands under
<pipeline_outputs>/pose3d/calibration/{<recording>/rows_<cam>.pkl, <batch>/calibration.{json,toml}}.
Needs opencv + aniposelib (the analysis desktop's `dlc` env has both).
"""

from __future__ import annotations

import argparse
import glob
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd

from stroke_orofacial._writeguard import assert_safe_write_path
from stroke_orofacial.paths import PathResolver
from stroke_orofacial.pose3d import calibration as cal
from stroke_orofacial.pose3d import rig


def _out(resolver) -> Path:
    return Path(resolver.pipeline_outputs("pose3d")) / "calibration"


def _detect_one(args):
    import pickle

    raw, out, rec, cam = args
    n = cam[-1]
    video = glob.glob(str(Path(raw) / rec / f"video{n}_*.avi"))[0]
    counter = pd.read_csv(glob.glob(str(Path(raw) / rec / f"timestamp{n}_*.csv"))[0], header=None)[
        0
    ].values
    d = cal.detect_video(video, counter, cam)
    dest = Path(out) / rec
    assert_safe_write_path(str(dest))
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"rows_{cam}.pkl").write_bytes(pickle.dumps(d))
    return f"{rec} {cam}: {len(d['rows'])} rows, {d['n_video']} frames"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("step", choices=("detect", "solve"))
    ap.add_argument("--batch", action="append", choices=sorted(rig.CALIBRATIONS), default=None)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--refresh", action="store_true", help="detect: redo cached recordings")
    a = ap.parse_args(argv)
    r = PathResolver()
    out = _out(r)
    batches = a.batch or sorted(rig.CALIBRATIONS)
    if a.step == "detect":
        jobs = [
            (str(r.root("camera_raw")), str(out), rec, cam)
            for b in batches
            for rec in rig.CALIBRATIONS[b]
            for cam in rig.CAMS
            if a.refresh or not (out / rec / f"rows_{cam}.pkl").exists()
        ]
        with Pool(min(a.jobs, max(1, len(jobs)))) as p:
            for line in p.imap_unordered(_detect_one, jobs):
                print(line, flush=True)
        return 0
    for b in batches:
        print(f"[{b}]", flush=True)
        rep, cg = cal.solve_batch({rec: out / rec for rec in rig.CALIBRATIONS[b]})
        for f in cal.write(rep, cg, out / b):
            print(f"  -> {f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
