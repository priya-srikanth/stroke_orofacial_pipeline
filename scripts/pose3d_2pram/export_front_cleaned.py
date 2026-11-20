"""Front-view (video2) cleaned tongue / jaw traces back in video2 IMAGE pixels, for the two-view 3-D clips.

The cleaned traces (dlc_kinematics/cleaned_traces/<part>/<animal>/<date>.parquet) are in a centered frame that is a
pure per-session translation of the DLC image coordinates (PS46 03-10: raw - cleaned is constant on every tracked
frame, IQR 0). The translation is recovered as the median of (raw DLC - cleaned) over tracked frames (fill_method 0)
and checked to be constant. Output per session: <work>/clips/<animal>_<date>_front_cleaned.npz with <part>_xy
(image px, NaN when the tongue is in = fill_method 3) and <part>_fill (0 tracked, 1 interpolated, 3 baseline).

Run in the stroke_orofacial env (needs pyarrow):
    conda run -n stroke_orofacial python scripts/pose3d_2pram/export_front_cleaned.py PS46:20250310 --work <dir>
"""

from __future__ import annotations

import argparse
import glob

import numpy as np
import pandas as pd

OUT = "M:/MICROSCOPE/Priya/stroke_orofacial_pipeline_outputs"
DLC = "M:/MICROSCOPE/Priya/DeepLabCut/O2_analysis"


def export(animal: str, date: str, work: str) -> None:
    dd = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    raw = pd.read_csv(
        glob.glob(f"{DLC}/{animal}/video2_{dd}T*_filtered.csv")[0], header=[0, 1, 2], index_col=0
    )
    raw.columns = raw.columns.droplevel(0)
    out = {}
    for part in ("tongue", "jaw"):
        c = pd.read_parquet(f"{OUT}/dlc_kinematics/cleaned_traces/{part}/{animal}/{date}.parquet")
        assert len(c) == len(raw), (part, len(c), len(raw))
        fill = c["fill_method"].to_numpy()
        tracked = fill == 0
        d = (
            raw[part][["x", "y"]].to_numpy()[tracked]
            - c[["x_final", "y_final"]].to_numpy()[tracked]
        )
        d = d[np.all(np.isfinite(d), 1)]  # a few raw DLC rows are NaN (PS46 03-24 tongue)
        shift = np.median(d, 0)
        spread = np.percentile(np.abs(d - shift), 99, axis=0)
        if np.any(spread > 0.01):
            raise RuntimeError(
                f"{animal} {date} {part}: cleaned trace is not a pure translation of DLC ({spread})"
            )
        xy = c[["x_final", "y_final"]].to_numpy() + shift
        xy[fill == 3] = np.nan
        out[f"{part}_xy"], out[f"{part}_fill"], out[f"{part}_shift"] = xy, fill, shift
        print(
            animal,
            date,
            part,
            "shift",
            shift.round(2),
            "tracked",
            tracked.sum(),
            "interp",
            (fill == 1).sum(),
        )
    np.savez(f"{work}/clips/{animal}_{date}_front_cleaned.npz", **out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    for s in a.sessions:
        export(*s.split(":"), a.work)


if __name__ == "__main__":
    main()
